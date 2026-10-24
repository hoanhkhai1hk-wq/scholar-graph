"""Public equivalents, never official pdf/ files. Helpers for real local acceptance."""

import hashlib
import json
import os
import subprocess
import threading
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "7ac617a4ff818cc3840069098fc3477ca614b0e8"
SCOPE = "公开等价物、非官方 pdf/ 文件；未运行或宣称官方三用例通过。"


def prepare(root):
    root = root.resolve()
    if not root.is_relative_to(ROOT / "data") or root.exists():
        raise ValueError("Choose a fresh output root under project data/.")
    root.mkdir(parents=True)
    # No .env loading; no credential values are printed, persisted, or used.
    for key in list(os.environ):
        if any(part in key.upper() for part in ("API_KEY", "TOKEN", "SECRET", "PASSWORD")):
            del os.environ[key]
    os.environ.update(SCHOLAR_GRAPH_QA_MODE="extractive", SCHOLAR_GRAPH_RETRIEVAL_MODE="lexical")
    return root


def header(case):
    return {"scope": SCOPE, "case": case, "baseline": BASELINE,
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, encoding="utf-8").strip(),
            "run_utc": datetime.now(timezone.utc).isoformat(),
            "versions": {name: version(name) for name in ("mineru", "pypdf", "psutil", "fastapi")},
            "real_llm_calls": 0, "real_api_keys_used": False}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def file_info(path):
    from pypdf import PdfReader
    raw = path.read_bytes()
    with path.open("rb") as handle:
        reader = PdfReader(handle)
        return {"file": str(path.resolve()), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                "physical_pages": len(reader.pages), "pdf_title": reader.metadata.title if reader.metadata else None}


class Measure:
    """50ms RSS/private sampling of this process plus all descendants (not system RAM)."""
    def __enter__(self):
        self.process, self.done = psutil.Process(), threading.Event()
        self.result = {"sample_interval_seconds": .05, "rss_peak_bytes": 0, "private_peak_bytes": 0,
                       "sample_count": 0, "includes_descendant_processes": True}
        self.start = time.perf_counter()
        self.sample()
        self.result["rss_start_bytes"] = self.result["rss_peak_bytes"]
        self.thread = threading.Thread(target=self.poll, daemon=True)
        self.thread.start()
        return self

    def sample(self):
        try:
            processes = [self.process, *self.process.children(recursive=True)]
        except psutil.Error:
            processes = [self.process]
        rss, private = 0, 0
        for process in processes:
            try:
                memory = process.memory_info()
                rss += memory.rss
                private += getattr(memory, "private", memory.vms)
            except psutil.Error:
                continue
        self.result["rss_peak_bytes"] = max(rss, self.result["rss_peak_bytes"])
        self.result["private_peak_bytes"] = max(private, self.result["private_peak_bytes"])
        self.result["sample_count"] += 1

    def poll(self):
        while not self.done.wait(.05):
            self.sample()

    def __exit__(self, *args):
        self.done.set()
        self.thread.join()
        self.sample()
        self.result["elapsed_seconds"] = round(time.perf_counter() - self.start, 6)
        self.result["scope"] = "整个测试进程及全部子进程的采样合计，不是精确瞬时峰值；不含下载阶段。"


def upload(client, path):
    with Measure() as meter:
        with path.open("rb") as handle:
            response = client.post("/api/v1/papers", files={"file": (path.name, handle, "application/pdf")})
    return {"request": {"method": "POST", "path": "/api/v1/papers", "file_sha256": file_info(path)["sha256"]},
            "http_status": response.status_code, "response": response.json(), "measurement": meter.result}


def read(client, path):
    response = client.get(path)
    return {"path": path, "http_status": response.status_code, "response": response.json()}


def parsed_details(client, root, upload_result):
    if upload_result["http_status"] != 201:
        return {"published_chunks": 0, "indexing_seconds": None, "reason": "Upload did not publish a paper."}
    pid = upload_result["response"]["id"]
    records = {"PaperMeta": 1}
    for route, name in (("chunks", "Chunk"), ("references", "ReferenceEntry"), ("citation-links", "CitationLink")):
        records[name] = client.get(f"/api/v1/papers/{pid}/{route}").json()["total"]
    history = []
    for path in sorted((root / "jobs").glob("job-*/parse-status.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if value and value[-1]["paper_id"] == pid:
            history.append(value)
    return {"paper_id": pid, "record_counts": records, "latest_status": read(client, f"/api/v1/papers/{pid}/parse-status"),
            "status_histories": history}
