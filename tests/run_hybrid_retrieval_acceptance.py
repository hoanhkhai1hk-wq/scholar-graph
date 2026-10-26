"""Official six questions with real local retrieval and real grounded QA, no raw bodies."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tests"))
from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.api_repository import ApiRepository
from scholar_graph.qa_evidence import retrieve as old_extractive
from scholar_graph.grounded_model import evidence_candidates
from scholar_graph.qa_retrieval import qa_retriever
from scholar_graph.storage import write_json
from scholar_graph.validation import ContractGate
from run_real_model_acceptance import QUESTIONS, REFUSAL


def persist(value):
    raw = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key and key in raw:
        raise RuntimeError("credential in output")
    (ROOT / "tests/reports/hybrid-retrieval-live.json").write_text(raw + "\n", encoding="utf-8")


def main():
    if not os.environ.get("DEEPSEEK_API_KEY") or not os.environ.get("DEEPSEEK_MODEL"):
        raise RuntimeError("real QA environment is not configured; never fabricate answers")
    os.environ["SCHOLAR_GRAPH_QA_MODE"] = "deepseek"
    os.environ["SCHOLAR_GRAPH_QA_RETRIEVAL_MODE"] = "hybrid"
    folder = ROOT / "data/hybrid-retrieval-acceptance"
    folder.mkdir(parents=True, exist_ok=True)
    ids = json.loads((ROOT / "data/real-model/sources.json").read_text(encoding="utf-8"))
    source = ApiRepository(ROOT / "data/real-model/records", ContractGate())
    app = create_app(data_dir=folder / "records")
    for key in ("attention_id", "bert_id"):
        app.state.repository.store.paper(source.paper(ids[key]))
    client = TestClient(app, raise_server_exceptions=False)
    result = {"scope": "官方 pdf/ 真文件六题；模型原始响应体和Key不保存，只保留批准答案及调用元数据",
        "environment": {key: "已设置" if os.environ.get(key) else "未设置" for key in ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL")}, "cases": []}
    needles = [("aidan", "toronto"), ("0.9", "0.98"), ("8", "p100"), ("28.4", "26.36"), ("ba", "kiros", "hinton", "2016")]
    for n, question in enumerate(QUESTIONS):
        multi = n == 5
        started = time.perf_counter()
        response = client.post("/api/v1/compare" if multi else f'/api/v1/papers/{ids["attention_id"]}/qa',
            json={"question": question, **({"paper_ids": [ids["attention_id"], ids["bert_id"]]} if multi else {})})
        meta = json.loads(unquote(response.headers.get("X-ScholarGraph-QA-Meta", "%7B%7D")))
        agent = json.loads(unquote(response.headers.get("X-ScholarGraph-Agent-Meta", "%7B%7D")))
        value = response.json()
        row = {"case": n + 1, "question": question, "http_status": response.status_code,
               "elapsed_seconds": round(time.perf_counter() - started, 6), "metadata": meta, "agent": agent, "result": value, "passed": False}
        if response.status_code == 200:
            records = value["per_paper"] if multi else [value]
            for record in records:
                app.state.repository.gate.record("QAAnswer", record)
                for anchor in record["anchors"]:
                    app.state.repository.gate.anchor(anchor, [source.paper(anchor["paper_id"])])
            text = " ".join(record["answer"] for record in records).casefold()
            checks = {word: word in text for word in needles[n]} if not multi else {
                "encoder": "encoder" in text, "bidirectional": "bidirectional" in text,
                "decoder_or_encoder_stack": "decoder" in text or "encoder stack" in text, "vaswani": "vaswani" in text}
            checks.update(anchors=all(record["anchors"] and not record["refused"] for record in records),
                          actual_hybrid=meta.get("method") == "hybrid" and all(r["vector_status"] == "READY" for r in meta.get("retrieval", [])))
            if n in (1, 2, 3):
                checks["numeric"] = all(record["numeric_fact_check"]["status"] == "passed" for record in records)
            row.update(verification=checks, passed=all(checks.values()))
        result["cases"].append(row)
        persist(result)
        print(json.dumps({"case": n + 1, "status": response.status_code, "passed": row["passed"],
            "method": meta.get("method"), "evidence_counts": [r["evidence_count"] for r in meta.get("retrieval", [])], "seconds": row["elapsed_seconds"]}), flush=True)
    question = "基础网络借助哪种加速卡完成学习？"
    bundle = app.state.repository.paper(ids["attention_id"])
    retriever = qa_retriever(app.state.repository)
    evidence, info = retriever.retrieve(bundle, question)
    relevant = [item for item in evidence if "P100" in item["quote"] and "8" in item["quote"]]
    result["paraphrase"] = {"query": question, "legacy_extractive_count": len(old_extractive(bundle, question)),
        "legacy_model_candidates": len(evidence_candidates(bundle, question)), "metadata": info, "evidence": evidence,
        "target_hits": relevant, "advantage_observed": not evidence_candidates(bundle, question) and bool(relevant)}
    refusal = client.post(f'/api/v1/papers/{ids["attention_id"]}/qa', json={"question": REFUSAL})
    result["refusal"] = {"question": REFUSAL, "http_status": refusal.status_code, "result": refusal.json(),
        "metadata": json.loads(unquote(refusal.headers.get("X-ScholarGraph-QA-Meta", "%7B%7D")))}
    result["source_sha256_lf"] = {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_text(encoding="utf-8").encode()).hexdigest() for p in
        [*(ROOT / "backend/scholar_graph").glob("qa*.py"), *(ROOT / "backend/scholar_graph").glob("vector*.py"), ROOT / "backend/scholar_graph/orchestration.py", ROOT / "backend/scholar_graph/agent_tools.py", ROOT / "backend/scholar_graph/grounded_model.py"]}
    persist(result)
    print(json.dumps({"six_passed": sum(row["passed"] for row in result["cases"]), "paraphrase_advantage": result["paraphrase"]["advantage_observed"],
                      "refused": result["refusal"]["result"].get("refused")}))
    return int(not all(row["passed"] for row in result["cases"]))


if __name__ == "__main__":
    raise SystemExit(main())
