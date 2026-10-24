"""Module two evidence: self-made PDFs, real local parser, no real model/key."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.qa_compare import validate_comparison
from sample_pdfs import make_pdf
from test_proxy_compatibility import verify_proxy

BASELINE = "3038ee9adb3373adf4c3e2f337c5048e77df1d24"


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = args.output_root.resolve()
    check(root.is_relative_to(ROOT / "data") and not root.exists(), "Choose a new output directory under project data/.")
    root.mkdir(parents=True)
    os.environ["SCHOLAR_GRAPH_QA_MODE"] = "extractive"
    app = create_app(data_dir=root / "records")
    client = TestClient(app)
    gate = app.state.repository.gate
    report = {"run_utc": datetime.now(timezone.utc).isoformat(), "baseline_commit": BASELINE,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "scope": "自制样例、非官方 pdf/ 用例；未运行官方三用例，未验证浏览器问答页面。",
        "retrieval": "本单检索为词法兜底、向量检索待后续单",
        "model": {"mode": "extractive", "caller": "本地 QuestionAnswerer 确定性原文摘录", "provider": None,
                  "model_name": None, "real_model_calls": 0, "real_api_key_used": False,
                  "optional_adapter": "后端 httpx → DeepSeek，只有 Mock 测试，无真实联调"},
        "versions": {name: version(name) for name in ("fastapi", "starlette", "httpx", "pydantic", "mineru")},
        "uploads": [], "qa_examples": [], "cors": [], "frozen_contracts": []}
    bundles = []
    for label, kwargs in [("selfmade-v1", {}), ("selfmade-v7", {"version": "v7", "samples": 18})]:
        pdf = make_pdf(root / "inputs" / (label + ".pdf"), **kwargs)
        response = client.post("/api/v1/papers", files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")})
        check(response.status_code == 201, "Real local PDF upload failed")
        meta = response.json()
        bundle = app.state.repository.paper(meta["id"])
        gate.bundle(bundle)
        bundles.append(bundle)
        report["uploads"].append({"input": pdf.relative_to(ROOT).as_posix(), "paper_id": meta["id"],
            "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "counts": {"PaperMeta": 1, "Chunk": len(bundle["chunks"]), "ReferenceEntry": len(bundle["reference_entries"]),
                       "CitationLink": len(bundle["citation_links"])}})
    pid = bundles[0]["paper_meta"]["id"]
    for question, refused, numeric in [
        ("本文样本量是多少？", False, "passed"),
        ("Did the study use 12000 samples?", True, "failed"),
        ("作者报告的 F1 具体是多少？", True, "unverifiable"),
        ("What is the capital of France?", True, "not_applicable")]:
        response = client.post(f"/api/v1/papers/{pid}/qa", json={"question": question})
        check(response.status_code == 200, "QA request failed")
        value = response.json()
        gate.record("QAAnswer", value)
        check(value["refused"] == refused and value["numeric_fact_check"]["status"] == numeric, "QA verdict differs from expected evidence")
        for anchor in value["anchors"]:
            gate.anchor(anchor, [bundles[0]])
        report["qa_examples"].append({"request": {"method": "POST", "path": f"/api/v1/papers/{pid}/qa", "json": {"question": question}},
            "http_status": 200, "response": value})
    request = {"paper_ids": [bundle["paper_meta"]["id"] for bundle in bundles], "question": "How many samples?"}
    response = client.post("/api/v1/compare", json=request)
    check(response.status_code == 200, "Comparison failed")
    value = response.json()
    check(list(value) == ["evidence_table", "per_paper", "synthesis"], "Evidence is not serialized first")
    validate_comparison(value, bundles, gate)
    check(len(value["evidence_table"]) == 2 and all(not answer["refused"] for answer in value["per_paper"]), "Missing per-paper evidence")
    report["comparison"] = {"request": {"method": "POST", "path": "/api/v1/compare", "json": request},
        "http_status": 200, "response": value,
        "execution_order": "逐篇 QAAnswer 校验 → 去重证据表 → 原文并列综合 → 整包校验"}
    for origin in ("http://localhost:3000", "http://127.0.0.1:3000"):
        response = client.options(f"/api/v1/papers/{pid}/qa", headers={"Origin": origin,
            "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        check(response.status_code == 200 and response.headers["access-control-allow-origin"] == origin, "CORS preflight failed")
        report["cors"].append({"origin": origin, "http_status": response.status_code,
            "allow_methods": response.headers["access-control-allow-methods"],
            "allow_headers": response.headers["access-control-allow-headers"]})
    report["proxy"] = verify_proxy(root / "proxy-records")
    for path in sorted((ROOT / "contracts").glob("*.json")):
        relative = path.relative_to(ROOT).as_posix()
        before = subprocess.check_output(["git", "rev-parse", f"{BASELINE}:{relative}"], cwd=ROOT, text=True).strip()
        after = subprocess.check_output(["git", "hash-object", relative], cwd=ROOT, text=True).strip()
        check(before == after, "Frozen contract changed")
        report["frozen_contracts"].append({"file": relative, "git_blob": after, "unchanged": True})
    check(len(report["frozen_contracts"]) == 18, "Expected 18 frozen JSON files")
    forbidden = subprocess.check_output(["git", "diff", BASELINE, "--name-only", "--", "frontend", "experiments", "prompts", "test-records", "docker-compose.yml"], cwd=ROOT, text=True)
    check(not forbidden.strip(), "Files outside this task were modified")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"report": args.report.as_posix(), "qa_cases": len(report["qa_examples"]),
        "comparison_evidence_rows": len(value["evidence_table"]), "real_model_calls": 0,
        "proxy": [report["proxy"][key] for key in ("proxy_get_status", "proxy_qa_post_status", "proxy_multipart_status")],
        "frozen_json_files": 18}, ensure_ascii=False))


if __name__ == "__main__":
    main()
