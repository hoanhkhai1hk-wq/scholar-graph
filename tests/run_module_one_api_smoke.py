"""Reproducible TestClient evidence with real local engines and self-made PDFs."""

import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
from sample_pdfs import make_pdf
from scholar_graph.api import create_app
from scholar_graph.dedup import human_decision
from test_validation_status import example_bundle

BASELINE = "4ac3909b01fab904d3077b469ceca0e01d03aaa7"


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = args.output_root.resolve()
    check(root.is_relative_to(ROOT / "data"), "Output root must be under ignored project data/.")
    check(not root.exists(), "Choose a fresh output root; existing evidence is not overwritten.")
    root.mkdir(parents=True)
    report = {"scope": "自制样例、非官方 pdf/ 用例；未运行官方三用例，未验证前端接通。",
              "run_utc": datetime.now(timezone.utc).isoformat(), "baseline_commit": BASELINE,
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "versions": {name: version(name) for name in ("fastapi", "starlette", "httpx", "python-multipart", "uvicorn", "mineru", "paddleocr", "paddlepaddle")},
              "grobid": {"status": "待验证", "docker_cli_found": shutil.which("docker") is not None,
                         "live_service_called": False}, "uploads": [], "examples": []}
    app = create_app(data_dir=root / "records")
    client = TestClient(app)
    repo = app.state.repository
    paths = client.get("/openapi.json").json()["paths"]
    report["implemented_endpoints"] = [f"{method.upper()} {path}" for path, methods in paths.items() for method in methods]
    check(len(report["implemented_endpoints"]) == 10, "Unexpected business endpoint count")
    bundles = []

    def read_upload(label, response, source, expected_status=201):
        check(response.status_code == expected_status, "Real upload/detail request failed")
        meta = response.json()
        gate = repo.gate
        gate.record("PaperMeta", meta)
        pid = meta["id"]
        bundle = {"paper_meta": meta}
        for child, key, kind in [("chunks", "chunks", "Chunk"), ("references", "reference_entries", "ReferenceEntry"),
                                 ("citation-links", "citation_links", "CitationLink")]:
            result = client.get(f"/api/v1/papers/{pid}/{child}")
            check(result.status_code == 200 and not result.json()["has_next"], "Unexpected child page")
            bundle[key] = result.json()["items"]
            for item in bundle[key]:
                gate.record(kind, item)
        gate.bundle(bundle)
        check(bundle == repo.paper(pid), "HTTP records differ from validated disk records")
        status = client.get(f"/api/v1/papers/{pid}/parse-status").json()
        gate.record("ParseStatus", status)
        check(status["status"] == "completed" and status["progress"] == 100, "Upload did not complete")
        histories = []
        for path in (root / "records" / "jobs").glob("*/parse-status.json"):
            history = json.loads(path.read_text(encoding="utf-8"))
            if history[0]["paper_id"] == pid:
                histories.append((path.stat().st_mtime_ns, path.parent.name, history))
        report["uploads"].append({"label": label, "input": source.relative_to(ROOT).as_posix(),
            "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "paper_id": pid,
            "counts": {"PaperMeta": 1, "Chunk": len(bundle["chunks"]),
                       "ReferenceEntry": len(bundle["reference_entries"]), "CitationLink": len(bundle["citation_links"])},
            "latest_status": status, "history": max(histories, key=lambda item: item[:2])[2]})
        return bundle

    first = make_pdf(root / "inputs" / "selfmade-v1.pdf")
    response = client.post("/api/v1/papers", files={"file": (first.name, first.read_bytes(), "application/pdf")})
    bundles.append(read_upload("selfmade-v1", response, first))
    second = make_pdf(root / "inputs" / "selfmade-v7.pdf", version="v7", samples=18)
    response = client.post("/api/v1/papers/batch", files=[
        ("files", (second.name, second.read_bytes(), "application/pdf")),
        ("files", ("broken.pdf", b"%PDF-invalid", "application/pdf")),
        ("files", ("wrong.txt", b"not PDF", "text/plain")),
        ("files", (first.name, first.read_bytes(), "application/pdf"))])
    value = response.json()
    check(response.status_code == 200 and value["succeeded_count"] == value["failed_count"] == 2, "Batch mismatch")
    check([item["filename"] for item in value["failed"]] == ["broken.pdf", "wrong.txt"], "Files lost or reordered")
    for item in value["failed"]:
        repo.gate.error({"error_code": item["error_code"], "message": item["error_message"], "details": None})
    for item in value["succeeded"]:
        repo.gate.record("ParseStatus", item["parse_status"])
        check(item["parse_status"]["status"] == "queued", "Initial snapshot was replaced")
    report["examples"].append({"request": "POST /api/v1/papers/batch",
        "files_in_order": [second.name, "broken.pdf", "wrong.txt", first.name],
        "http_status": response.status_code, "response": value, "processing": "按顺序同步，无异步队列"})
    new_id = value["succeeded"][0]["paper_id"]
    bundles.append(read_upload("selfmade-v7 (batch)", client.get(f"/api/v1/papers/{new_id}"), second, 200))
    scan = make_pdf(root / "inputs" / "selfmade-scan.pdf", scan=True)
    response = client.post("/api/v1/papers", files={"file": (scan.name, scan.read_bytes(), "application/pdf")})
    scanned = read_upload("selfmade-scan", response, scan)
    check(scanned["paper_meta"]["has_text_layer"] is False, "Scan unexpectedly has a text layer")
    check("ocr" in [item["status"] for item in report["uploads"][-1]["history"]], "OCR not actually used")
    report["ocr"] = {"status": "已接通", "engine": "PaddleOCR CPU", "real_http_upload": True}

    decision_response = client.get(f"/api/v1/papers/{new_id}/dedup-decision")
    diff_response = client.get(f"/api/v1/papers/{new_id}/diff-summary")
    check(decision_response.status_code == diff_response.status_code == 200, "Version records unavailable")
    decision, diff = decision_response.json(), diff_response.json()
    repo.gate.comparison(decision, diff, bundles)
    report["comparison"] = {"lookup_key": "new_paper_id", "decision": decision, "diff": diff}
    human = human_decision(decision, "keep_both", "测试脚本显式模拟人工核对，不是专家实际审核。", diff, bundles, repo.gate)
    target = repo.store.comparison(decision, diff, bundles, human=human)
    before = (target / "dedup-decisions.json").read_bytes()
    check(client.get(f"/api/v1/papers/{new_id}/dedup-decision").json() == human, "Human decision changed")
    check((target / "dedup-decisions.json").read_bytes() == before, "Read mutated decision history")
    check(json.loads(before)[0] == decision, "System decision overwritten")
    report["human_override"] = {"returned": human, "system_record_unchanged": True,
                               "history_sha256": hashlib.sha256(before).hexdigest()}
    for pid, endpoint in [(bundles[0]["paper_meta"]["id"], "dedup-decision"),
                          (scanned["paper_meta"]["id"], "diff-summary"), ("missing", "parse-status")]:
        path = f"/api/v1/papers/{pid}/{endpoint}"
        response = client.get(path)
        check(response.status_code == 404, "Missing record was not a 404")
        repo.gate.error(response.json())
        report["examples"].append({"request": "GET " + path, "http_status": 404, "response": response.json()})

    pagination_app = create_app(data_dir=root / "pagination-contract-examples")
    for index in range(101):
        bundle = copy.deepcopy(example_bundle())
        pid = f"paper-pagination-{index:03}"
        bundle["paper_meta"].update(id=pid, title=f"Synthetic {index}")
        for key in ("chunks", "reference_entries", "citation_links"):
            for item in bundle[key]:
                item["paper_id"] = pid
        pagination_app.state.repository.store.paper(bundle)
    pagination = TestClient(pagination_app)
    for query, expected in [("page=1&page_size=999", (100, 101, 2, True, 100)),
                             ("page=2&page_size=999", (1, 101, 2, False, 100)),
                             ("page=999&page_size=20", (0, 101, 6, False, 20)),
                             ("title=Synthetic%20100", (1, 1, 1, False, 20))]:
        path = "/api/v1/papers?" + query
        response = pagination.get(path)
        value = response.json()
        check(response.status_code == 200, "Pagination failed")
        actual = (len(value["items"]), value["total"], value["total_pages"], value["has_next"], value["page_size"])
        check(actual == expected, "Pagination boundary mismatch")
        summary = {key: item for key, item in value.items() if key != "items"}
        summary["items_count"] = len(value["items"])
        report["examples"].append({"request": "GET " + path, "http_status": 200, "response_summary": summary})

    report["frozen_contracts"] = []
    for path in sorted((ROOT / "contracts").glob("*.json")):
        rel = path.relative_to(ROOT).as_posix()
        baseline = subprocess.check_output(["git", "rev-parse", f"{BASELINE}:{rel}"], cwd=ROOT, text=True).strip()
        actual = subprocess.check_output(["git", "hash-object", str(path)], cwd=ROOT, text=True).strip()
        check(actual == baseline, "Frozen contract changed: " + rel)
        report["frozen_contracts"].append({"file": rel, "git_blob": actual, "unchanged": True})
    check(len(report["frozen_contracts"]) == 18, "Expected nine schemas and nine examples")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"report": args.report.as_posix(), "uploads": [item["counts"] for item in report["uploads"]],
                      "endpoints": len(report["implemented_endpoints"]), "frozen_files": 18,
                      "ocr": report["ocr"]["status"], "grobid": report["grobid"]["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
