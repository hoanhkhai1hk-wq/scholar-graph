"""Official pdf/ real-file upload acceptance using only local BGE-M3, no key."""
import hashlib
import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.storage import write_json


def upload(client, app, name, filename=None):
    path = ROOT / "pdf" / name
    start = time.monotonic()
    response = client.post("/api/v1/papers", files={"file": (filename or name, path.read_bytes(), "application/pdf")})
    result = {"source": name, "upload_filename": filename or name, "http_status": response.status_code,
        "elapsed_seconds": round(time.monotonic() - start, 6), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "paper": response.json(), "warning": unquote(response.headers.get("X-ScholarGraph-Dedup-Warning", "")),
        "metadata": json.loads(unquote(response.headers["X-ScholarGraph-Dedup-Meta"])) if "X-ScholarGraph-Dedup-Meta" in response.headers else None}
    if response.status_code == 201:
        pid = response.json()["id"]
        result["chunks"] = len(app.state.repository.paper(pid)["chunks"])
        for field, suffix in (("decision", "dedup-decision"), ("diff", "diff-summary")):
            r = client.get(f"/api/v1/papers/{pid}/{suffix}")
            result[field] = {"http_status": r.status_code, "body": r.json()}
        result["assessment"] = json.loads((app.state.repository.root / "semantic-dedup/assessments" / pid / "latest.json").read_text(encoding="utf-8"))
    print(json.dumps({"source": name, "filename": filename or name, "status": response.status_code,
        "seconds": result["elapsed_seconds"], "score": (result["metadata"] or {}).get("score"), "band": (result["metadata"] or {}).get("band")}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/semantic-dedup-acceptance-final")
    args = parser.parse_args()
    if os.environ.get("DEEPSEEK_API_KEY"):
        raise RuntimeError("public local-vector acceptance must run without credentials")
    root = args.data_dir.resolve()
    if root.exists():
        raise RuntimeError("preserve earlier evidence; acceptance root must be fresh")
    os.environ["SCHOLAR_GRAPH_DEDUP_MODE"] = "auto"
    result = {"input_kind": "官方 pdf/ 真文件", "model_api_key": "未设置", "embedding": "BAAI/bge-m3 local CPU; no external API", "groups": {}}
    for group, inputs in (("versions", [("1706.03762v7.pdf", None), ("1706.03762v1.pdf", None)]),
                          ("renamed", [("1706.03762v7.pdf", None), ("1706.03762v7.pdf", "attention-renamed.pdf")]),
                          ("different", [("1706.03762v7.pdf", None), ("N19-1423.pdf", None)])):
        app = create_app(data_dir=root / group)
        client = TestClient(app)
        rows = [upload(client, app, name, renamed) for name, renamed in inputs]
        result["groups"][group] = {"uploads": rows, "paper_count": len(app.state.repository.papers())}
        write_json(ROOT / "tests/reports/semantic-dedup-live.json", result)
    a, b, c = [result["groups"][key] for key in ("versions", "renamed", "different")]
    av, bv, cv = [entry["uploads"][1] for entry in (a, b, c)]
    result["checks"] = {"all_http_201": all(row["http_status"] == 201 for entry in (a,b,c) for row in entry["uploads"]),
        "all_actual_bge_ready": all(row["metadata"] and row["metadata"]["status"] == "ready" for entry in (a,b,c) for row in entry["uploads"]),
        "version_warn_keep_v7": "建议保留库里较新版本（v7）" in av["warning"] and av["decision"]["http_status"] == av["diff"]["http_status"] == 200 and av["decision"]["body"]["recommendation"] == "keep_old",
        "renamed_duplicate_single_paper": b["paper_count"] == 1 and bv["metadata"]["band"] == "duplicate" and bool(bv["warning"]),
        "different_not_duplicate": cv["metadata"]["band"] == "new_paper" and not cv["warning"] and cv["decision"]["http_status"] == 404}
    result["source_sha256_lf"] = {str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()
        for path in [*(ROOT / "backend/scholar_graph").glob("semantic_*.py"), ROOT / "backend/scholar_graph/vector_worker.py", ROOT / "backend/scholar_graph/pipeline.py", ROOT / "backend/scholar_graph/api_uploads.py", Path(__file__)]}
    write_json(ROOT / "tests/reports/semantic-dedup-live.json", result)
    print(json.dumps({"checks": result["checks"]}))
    return int(not all(result["checks"].values()))


if __name__ == "__main__":
    raise SystemExit(main())
