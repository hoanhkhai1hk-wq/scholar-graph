"""Offline audit of approved answers, real local retrieval and regression evidence."""
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.qa_compare import validate_comparison
from scholar_graph.storage import write_json
from scholar_graph.validation import ContractGate

BASELINE = "1dc443e6fb80840d4b0b49a5187ccce88129ce58"


def main():
    live = json.loads((ROOT / "tests/reports/hybrid-retrieval-live.json").read_text(encoding="utf-8"))
    first = json.loads((ROOT / "tests/reports/hybrid-retrieval-attempt-1.json").read_text(encoding="utf-8"))
    no_key = json.loads((ROOT / "tests/reports/hybrid-retrieval-no-key.json").read_text(encoding="utf-8"))
    repository = ApiRepository(ROOT / "data/hybrid-retrieval-acceptance/records", ContractGate())
    gate = repository.gate
    checks = []
    def check(label, value):
        checks.append({"check": label, "passed": bool(value)})
    check("官方六题全部HTTP200并通过", len(live["cases"]) == 6 and all(c["http_status"] == 200 and c["passed"] for c in live["cases"]))
    all_rows = []
    for case in live["cases"]:
        n = case["case"]
        rows = case["metadata"]["retrieval"]
        all_rows.extend(rows)
        check(f"第{n}题实际混合检索", case["metadata"]["method"] == "hybrid" and rows and all(row["method"] == "hybrid" and row["vector_status"] == "READY" for row in rows))
        check(f"第{n}题有双路真实召回计数", all(row["lexical_recalled"] > 0 and row["vector_recalled"] > 0 and row["evidence_count"] > 0 for row in rows))
        check(f"第{n}题使用实测慢重排后的RRF", all(row["rerank"]["method"] == "rrf" and row["rerank"]["reason"] == "MEASURED_CPU_BUDGET_EXCEEDED" for row in rows))
        check(f"第{n}题记录加载与索引计时", all(row["vector_timing"]["model_load_seconds"] > 0 and row["vector_timing"]["startup_to_model_ready_seconds"] >= row["vector_timing"]["model_load_seconds"] and row["worker_seconds"] > 0 for row in rows))
        records = case["result"]["per_paper"] if n == 6 else [case["result"]]
        for j, record in enumerate(records):
            gate.record("QAAnswer", record)
            check(f"第{n}题第{j+1}篇无拒答且有锚点", not record["refused"] and bool(record["anchors"]))
            quotes = re.findall(r"【证据 [A-H]】\n(.*?)(?=\n\n【证据 [A-H]】\n|\Z)", record["answer"], re.S)
            check(f"第{n}题第{j+1}篇摘录与锚点一一对应", len(quotes) == len(record["anchors"]))
            for quote, anchor in zip(quotes, record["anchors"], strict=True):
                bundle = repository.paper(anchor["paper_id"])
                gate.anchor(anchor, [bundle], quote=quote)
                chunk = next(c for c in bundle["chunks"] if c["chunk_id"] == anchor["chunk_id"])
                check(f"第{n}题真实连续原文:{anchor['chunk_id']}", quote in chunk["text"] and len(quote) <= 600)
            numeric = record["numeric_fact_check"]
            check(f"第{n}题第{j+1}篇数字通过项有真实证据", all(c["evidence"] and c["claim"] in quotes and all(a in record["anchors"] for a in c["evidence"]) for c in numeric["checks"] if c["status"] == "passed"))
        if n == 6:
            ids = list(dict.fromkeys(row["paper_id"] for row in rows))
            validate_comparison(case["result"], [repository.paper(pid) for pid in ids], gate)
            check("跨篇retrieve节点实际走混合", all(t["retrieval"]["method"] == "hybrid" for t in case["agent"]["trace"] if t["node"] == "retrieve"))
            check("跨篇模型Function Calling工具确用混合", case["agent"]["tool_calls"] and all(t["return_summary"]["method"] == "hybrid" for t in case["agent"]["tool_calls"] if t["tool_name"] == "search"))
    bleu = live["cases"][3]["result"]
    check("BLEU双来源支持确定性差值2.04", "28.4" in bleu["answer"] and "26.36" in bleu["answer"] and len(bleu["anchors"]) >= 2 and Decimal("28.4") - Decimal("26.36") == Decimal("2.04"))
    p = live["paraphrase"]
    check("真实改写查询旧词法均零而向量命中", p["advantage_observed"] and p["legacy_extractive_count"] == p["legacy_model_candidates"] == 0 and p["metadata"]["method"] == "vector")
    check("改写命中确为Base硬件原文", any("For our base models" in item["quote"] and "8 NVIDIA P100" in item["quote"] for item in p["target_hits"]))
    for item in p["evidence"]:
        gate.anchor(item["anchor"], [repository.paper(item["paper_id"])], quote=item["quote"])
    check("改写候选全部锚点合法", True)
    check("错误前提仍拒答", live["refusal"]["http_status"] == 200 and live["refusal"]["result"]["refused"])
    check("无Key真实本地向量QA", no_key["environment"] == "未设置模型Key" and no_key["http_status"] == 200 and no_key["metadata"]["method"] == "vector" and not no_key["result"]["refused"])
    check("缺本地向量真实词法回退", no_key["missing_vector"]["metadata"]["method"] == "lexical-fallback" and no_key["missing_vector"]["metadata"]["retrieval"][0]["vector_status"] == "UNAVAILABLE")
    check("保留首次跨篇三轮校验失败", not first["cases"][5]["passed"] and sum(t.get("validation") is False for t in first["cases"][5]["agent"]["trace"]) == 3)
    check("首次冷索引175和277条真实编码", any(row.get("updated_chunks") == 175 for c in first["cases"] for row in c["metadata"].get("retrieval", [])) and any(row.get("updated_chunks") == 277 for c in first["cases"] for row in c["metadata"].get("retrieval", [])))
    policy = json.loads((repository.root / "qa-retrieval/reranker-policy.json").read_text(encoding="utf-8"))
    check("实际大模型重排超过预设预算", policy["candidate_count"] == 36 and policy["worker_seconds"] > policy["budget_seconds"] == 5 and policy["timing"]["rerank_seconds"] > 0 and policy["revision"] == "55611d7bca2a7133960a6d3b71e083071bbfc312")
    with sqlite3.connect((repository.root / "chroma-qa-bge-m3/chroma.sqlite3").resolve().as_uri() + "?mode=ro", uri=True) as db:
        check("Chroma实际452条向量", db.execute("SELECT count(*) FROM embeddings").fetchone()[0] == 452)
    check("最终实测源码SHA一致", all(hashlib.sha256((ROOT / path).read_text(encoding="utf-8").encode()).hexdigest() == digest for path, digest in live["source_sha256_lf"].items()))
    model = ROOT / "data/module-four-models/bge-reranker-large/model.safetensors"
    with model.open("rb") as handle:
        model_sha = hashlib.file_digest(handle, "sha256").hexdigest()
    metadata = (model.parent / ".cache/huggingface/download/model.safetensors.metadata").read_text(encoding="utf-8").splitlines()
    check("重排权重与公开固定快照SHA一致", metadata[0] == policy["revision"] and metadata[1] == model_sha)
    suites = ET.parse(ROOT / "tests/reports/hybrid-retrieval-pytest.xml").getroot().findall("testsuite")
    totals = {k: sum(int(s.get(k, "0")) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
    check("最终528回归全过无跳过", totals == {"tests": 528, "failures": 0, "errors": 0, "skipped": 0})
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()
    paths = git("diff", "--name-only", BASELINE).splitlines() + git("ls-files", "--others", "--exclude-standard").splitlines()
    check("只改backend和tests", all(path.startswith(("backend/", "tests/")) for path in paths))
    check("前端契约和协作目录零改动", not git("diff", BASELINE, "--", "frontend", "contracts", "docs", "prompts", "experiments", "test-records"))
    check("pdf仍忽略未跟踪", "pdf/" in git("check-ignore", "pdf/1706.03762v7.pdf") and not git("ls-files", "pdf", "data", ".env"))
    secrets = [value.encode() for key, value in os.environ.items() if "API_KEY" in key.upper() and len(value) >= 8]
    check("本单文件没有实际Key", all(not any(secret in (ROOT / p).read_bytes() for secret in secrets) for p in paths if (ROOT / p).is_file()))
    result = {"baseline": BASELINE, "checks": checks, "passed": sum(c["passed"] for c in checks), "failed": sum(not c["passed"] for c in checks), "regression": totals, "reranker_sha256": model_sha}
    write_json(ROOT / "tests/reports/hybrid-retrieval-audit.json", result)
    print(json.dumps({k: result[k] for k in ("passed", "failed", "regression")}))
    return int(bool(result["failed"]))


if __name__ == "__main__":
    raise SystemExit(main())
