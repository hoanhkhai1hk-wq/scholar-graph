"""Official upload + real public arXiv fetch; no model API and no PDF in Git."""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.arxiv_fetch import ArxivClient, ArxivFetcher
from scholar_graph.pdf_files import file_digest
from scholar_graph.storage import RecordStore


def stream_measurement(app, pid):
    sizes, digest, statuses = [], hashlib.sha256(), []
    async def send(message):
        if message["type"] == "http.response.start":
            statuses.append(message["status"])
        if message["type"] == "http.response.body":
            block = message.get("body", b"")
            sizes.append(len(block))
            digest.update(block)
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}
    path = f"/api/v1/papers/{pid}/file"
    asyncio.run(app({"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1", "method": "GET", "scheme": "http", "path": path,
        "raw_path": path.encode(), "query_string": b"", "headers": [], "root_path": "",
        "server": ("testserver", 80), "client": ("testclient", 1)}, receive, send))
    return {"status": statuses, "chunks": len(sizes), "max_chunk_bytes": max(sizes, default=0),
            "bytes": sum(sizes), "sha256": digest.hexdigest()}


def file_check(app, pid):
    with TestClient(app) as client, client.stream("GET", f"/api/v1/papers/{pid}/file") as response:
        digest, size = hashlib.sha256(), 0
        for block in response.iter_bytes():
            digest.update(block)
            size += len(block)
        return {"status": response.status_code, "content_type": response.headers.get("content-type"),
            "content_disposition": response.headers.get("content-disposition"), "bytes": size,
            "sha256": digest.hexdigest(), "asgi": stream_measurement(app, pid)}


def verified_metadata_download():
    """Download a real PDF using already verified metadata; do not claim a fresh Atom query."""
    for key, value in (("SCHOLAR_GRAPH_QA_MODE", "extractive"), ("SCHOLAR_GRAPH_RETRIEVAL_MODE", "lexical"),
                       ("SCHOLAR_GRAPH_DEDUP_MODE", "off")):
        os.environ[key] = value
    path = ROOT / "tests/reports/pdf-file-endpoint-live.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    history = json.loads((ROOT / "tests/reports/module-four-smoke.json").read_text(encoding="utf-8"))
    metadata = next(x for x in history["cases"] if x["name"] == "LIVE-public-arxiv-reference")["response"]["metadata"]
    app = create_app(data_dir=ROOT / report["local_artifacts"] / ("verified-metadata-arxiv-" + uuid4().hex))
    class Measured(ArxivClient):
        def pdf(self, paper):
            raw = super().pdf(paper)
            self.download = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            return raw
    upstream = Measured(app.state.repository.gate)
    service = ArxivFetcher(app.state.repository, client=upstream, lock=app.state.uploads.lock)
    started = time.perf_counter()
    result = service.fetch_metadata(metadata)
    row = {"provenance": "historical verified Atom metadata; fresh real arxiv.org PDF download via existing fetch_metadata; not fresh metadata API",
           "succeeded": result["succeeded"], "elapsed_seconds": round(time.perf_counter()-started, 6),
           "error": result["error"], "download": getattr(upstream, "download", None)}
    if result["succeeded"]:
        paper = result["paper"]
        row.update(paper_id=paper["id"], source=paper["source"], file_hash=paper["file_hash"], file=file_check(app, paper["id"]))
    report["verified_metadata_arxiv"] = row
    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key and key in raw:
        raise RuntimeError("credential in report; not saved")
    path.write_text(raw, encoding="utf-8")
    print(json.dumps(row, ensure_ascii=False, indent=2))
    return 0 if result["succeeded"] else 1


def main():
    for key, value in (("SCHOLAR_GRAPH_QA_MODE", "extractive"), ("SCHOLAR_GRAPH_RETRIEVAL_MODE", "lexical"),
                       ("SCHOLAR_GRAPH_QA_RETRIEVAL_MODE", "lexical"), ("SCHOLAR_GRAPH_DEDUP_MODE", "off")):
        os.environ[key] = value
    source = ROOT / "pdf/1706.03762v7.pdf"
    sha, size = file_digest(source)
    root = ROOT / "data/pdf-file-acceptance" / uuid4().hex
    app = create_app(data_dir=root / "upload")
    client = TestClient(app)
    started = time.perf_counter()
    with source.open("rb") as handle:
        uploaded = client.post("/api/v1/papers", files={"file": (source.name, handle, "application/pdf")})
    report = {"scope": "官方 pdf/ 真文件上传 + 真实公开 arXiv 抓取；无模型 API/Key",
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "local_artifacts": str(root.relative_to(ROOT)),
        "input": {"name": source.name, "sha256": sha, "bytes": size},
        "upload": {"status": uploaded.status_code, "elapsed_seconds": round(time.perf_counter()-started, 6)}, "passed": False}
    if uploaded.status_code != 201:
        report["upload"]["error"] = uploaded.json()
    else:
        paper = uploaded.json()
        pid = paper["id"]
        report["upload"].update(paper_id=pid, file_hash=paper["file_hash"], file=file_check(app, pid))
        report["range"] = {"status": client.get(f"/api/v1/papers/{pid}/file", headers={"Range": "bytes=0-31"}).status_code}
        report["rejected"] = []
        for identity in ("paper-unknown", "%2e%2e%5cprivate", "%2e%2e%2fprivate", "%252e%252e%255cprivate", "paper%27%20OR%201=1--"):
            path = "/api/v1/papers/" + identity + "/file"
            response = client.get(path)
            report["rejected"].append({"path": path, "status": response.status_code, "body": response.json()})
    # Separate empty store: cannot silently reuse the just-uploaded official PDF.
    fetched_app = create_app(data_dir=root / "arxiv")
    class MeasuredArxiv(ArxivClient):
        def pdf(self, paper):
            payload = super().pdf(paper)
            self.download = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
            return payload
    upstream = MeasuredArxiv(fetched_app.state.repository.gate)
    fetched_app.state.arxiv_fetcher = ArxivFetcher(fetched_app.state.repository, client=upstream,
                                                  lock=fetched_app.state.uploads.lock)
    reference_path = ROOT / "contracts/reference-entry.v1.example.json"
    if not reference_path.is_file():
        reference_path = next((ROOT / "contracts").glob("*reference*example.json"))
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    reference.update(arxiv_id="1706.03762v7", doi=None)
    started = time.perf_counter()
    response = TestClient(fetched_app).post("/api/v1/retrieval/fetch", json={"reference": reference})
    result = response.json()
    report["arxiv"] = {"http_status": response.status_code, "elapsed_seconds": round(time.perf_counter()-started, 6),
                       "succeeded": result["succeeded"], "error": result["error"], "download": getattr(upstream, "download", None)}
    if result["succeeded"]:
        paper = result["paper"]
        report["arxiv"].update(paper_id=paper["id"], arxiv_id=paper["arxiv_id"], file_hash=paper["file_hash"],
                              file=file_check(fetched_app, paper["id"]))
    # A real historical arXiv publication has no original archive from the old
    # implementation. Prove the documented same-hash re-upload recovery, without
    # relabeling cached metadata as a successful fresh public API request.
    history = json.loads((ROOT / "tests/reports/module-four-smoke.json").read_text(encoding="utf-8"))
    historical = next(x for x in history["cases"] if x["name"] == "LIVE-public-arxiv-reference")["response"]["paper"]
    legacy_app = create_app(data_dir=root / "historical-arxiv")
    previous = RecordStore(ROOT / "data/module-four-release/records", legacy_app.state.repository.gate)
    legacy_bundle = previous.load(previous.root / "papers" / historical["id"])
    if legacy_bundle["paper_meta"] != historical or historical["file_hash"] != sha:
        raise RuntimeError("historical arXiv evidence does not match the official original")
    legacy_app.state.repository.store.paper(legacy_bundle)
    legacy_client = TestClient(legacy_app)
    old_file = legacy_client.get(f'/api/v1/papers/{historical["id"]}/file')
    with source.open("rb") as handle:
        restored = legacy_client.post("/api/v1/papers", files={"file": (source.name, handle, "application/pdf")})
    report["historical_arxiv"] = {"provenance": "module-four-smoke.json/LIVE-public-arxiv-reference; not a fresh fetch",
        "paper_id": historical["id"], "arxiv_id": historical["arxiv_id"], "source": historical["source"],
        "file_hash": historical["file_hash"], "before": {"status": old_file.status_code, "body": old_file.json()},
        "same_hash_reupload_status": restored.status_code, "after": file_check(legacy_app, historical["id"])}
    upload_ok = (uploaded.status_code == 201 and report["upload"]["file"]["sha256"] == sha and
                 report["upload"]["file"]["asgi"]["sha256"] == sha and report["upload"]["file"]["status"] == 200 and
                 report["upload"]["file"]["content_type"] == "application/pdf")
    arxiv_ok = result["succeeded"] and report["arxiv"]["download"]["sha256"] == report["arxiv"]["file"]["sha256"] == result["paper"]["file_hash"]
    recovered = (old_file.status_code == 404 and restored.status_code == 201 and
                 report["historical_arxiv"]["after"]["status"] == 200 and report["historical_arxiv"]["after"]["sha256"] == sha)
    report["endpoint_checks_passed"] = bool(upload_ok and recovered and all(x["status"] == 404 for x in report["rejected"]))
    report["fresh_public_arxiv_passed"] = bool(arxiv_ok)
    report["passed"] = report["endpoint_checks_passed"] and report["fresh_public_arxiv_passed"]
    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key and key in raw:
        raise RuntimeError("credential in report; not saved")
    (ROOT / "tests/reports/pdf-file-endpoint-live.json").write_text(raw, encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(verified_metadata_download() if sys.argv[1:] == ["--verified-metadata-download"] else main())
