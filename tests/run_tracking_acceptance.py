"""Live public arXiv runs, existing official-paper seeds, no model or API key."""

import hashlib
import argparse
import io
from contextlib import redirect_stdout
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.api_repository import ApiRepository
from scholar_graph.storage import write_json
from scholar_graph.validation import ContractGate
from scholar_graph.tracking import topic_terms
from scholar_graph.tracking_cli import main as scheduled_task


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/tracking-acceptance-final-v4")
    args = parser.parse_args()
    if os.environ.get("DEEPSEEK_API_KEY"):
        raise RuntimeError("Run the public probe in a child environment without model credentials")
    output = args.data_dir.resolve()
    records = output / "records"
    if (records / "tracking/state.sqlite3").exists():
        raise RuntimeError("Acceptance root already used; preserve evidence and use a new root")
    gate = ContractGate()
    source = ApiRepository(ROOT / "data/real-model/records", gate)
    ids = json.loads((ROOT / "data/real-model/sources.json").read_text(encoding="utf-8"))
    app = create_app(data_dir=records)
    for key in ("attention_id", "bert_id"):
        app.state.repository.store.paper(source.paper(ids[key]))
    client = TestClient(app)
    before = client.get("/api/v1/papers?page_size=100").json()
    proof = {"input_kind": "真实公开 arXiv 数据；种子为此前已解析官方 pdf/ 真文件 Attention 与公开 BERT；新候选由本轮实际下载并走原解析管线",
             "model_api_key": "未设置", "seed_ids": [ids["attention_id"], ids["bert_id"]], "papers_before": before["total"],
             "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "rounds": []}
    body = {"paper_ids": [ids["attention_id"]], "max_candidates": 2, "max_imports": 2}
    proof["request"] = body
    for round_number in (1, 2):
        start = time.monotonic()
        response = client.post("/api/v1/retrieval/tracking/run", json=body)
        run = response.json()
        papers = app.state.repository.papers()
        proof["rounds"].append({"round": round_number, "http_status": response.status_code,
            "elapsed_seconds": round(time.monotonic() - start, 6), "run": run,
            "papers_after": len(papers), "paper_ids_after": [p["id"] for p in papers],
            "chunk_counts": {p["id"]: len(app.state.repository.paper(p["id"])["chunks"]) for p in papers}})
        write_json(ROOT / "tests/reports/tracking-live-results.json", proof)
        print(json.dumps({"round": round_number, "status": run.get("status"), "candidates": run.get("candidate_count"),
                          "imported": run.get("imported_count"), "duplicates": run.get("duplicate_count"),
                          "failed": run.get("failed_count"), "seconds": proof["rounds"][-1]["elapsed_seconds"]}))
    # Natural library cleanup and separate explicit fault-injection are distinguished.
    cleanup_app = create_app(data_dir=output / "cleanup-fixture")
    seed_bundle = source.paper(ids["attention_id"])
    cleanup_app.state.repository.store.paper(seed_bundle)
    path = cleanup_app.state.repository.root / "papers" / ids["attention_id"] / "citation-links.json"
    write_json(path, seed_bundle["citation_links"] + [seed_bundle["citation_links"][0]] * 2)
    proof["citation_cleanup_fault_injection"] = {"description": "独立副本上明确注入两条相同链接，不冒充真实语料原生重复",
        "first": TestClient(cleanup_app).post("/api/v1/retrieval/citations/cleanup").json(),
        "second": TestClient(cleanup_app).post("/api/v1/retrieval/citations/cleanup").json()}
    # A real related paper for transfer of feedback to a different, similar title.
    # Kept separate from the two polling rounds and their import counts.
    extra_start = time.monotonic()
    extra = client.post("/api/v1/retrieval/fetch", json={"title": "Reformer: The Efficient Transformer"})
    proof["feedback_extra_public_import"] = {"request": {"title": "Reformer: The Efficient Transformer"},
        "http_status": extra.status_code, "result": extra.json(), "seconds": round(time.monotonic() - extra_start, 6)}
    query = {"paper_id": ids["attention_id"], "as_of_year": 2026, "page_size": 100}
    ranking_before = client.get("/api/v1/recommendations", params=query).json()
    candidates = ranking_before["items"]
    if len(candidates) >= 2:
        # Prefer a low-ranked candidate that one real +50 feedback term can move past rank one.
        top = candidates[0]["score"]
        eligible = [item for item in reversed(candidates[1:]) if top - item["score"] < 50]
        target = next((item for item in eligible if any(other["paper"]["id"] != item["paper"]["id"] and
            topic_terms(item["paper"]) & topic_terms(other["paper"]) for other in candidates)), eligible[0] if eligible else candidates[-1])
        feedback_response = client.post("/api/v1/recommendations/feedback", json={"paper_id": target["paper"]["id"],
            "seed_paper_id": ids["attention_id"], "vote": "like", "as_of_year": 2026})
        after = client.get("/api/v1/recommendations", params=query).json()
        restarted = TestClient(create_app(data_dir=records))
        proof["feedback"] = {"http_status": feedback_response.status_code, "event": feedback_response.json(),
            "before": ranking_before, "after": after,
            "after_restart": restarted.get("/api/v1/recommendations", params=query).json(),
            "persisted_profile": restarted.get("/api/v1/recommendations/feedback").json()}
    else:
        proof["feedback"] = {"failed": "真实入库候选不足，无法证明排序变化。"}
    proof["latest_status"] = client.get("/api/v1/retrieval/tracking/status").json()
    captured = io.StringIO()
    with redirect_stdout(captured):
        exit_code = scheduled_task(["--data-dir", str(records), "--due"])
    proof["scheduled_task_not_due"] = {"exit_code": exit_code, "result": json.loads(captured.getvalue())}
    source_paths = ["backend/scholar_graph/" + name for name in (
        "api.py", "api_uploads.py", "arxiv_fetch.py", "citation_cleanup.py", "recommendations.py",
        "recommendation_feedback.py", "retrieval_routes.py", "tracking.py", "tracking_cli.py", "tracking_routes.py", "tracking_state.py")]
    source_paths.append("tests/run_tracking_acceptance.py")
    proof["source_sha256_lf"] = {path: hashlib.sha256((ROOT / path).read_text(encoding="utf-8").encode()).hexdigest() for path in source_paths}
    proof["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_json(ROOT / "tests/reports/tracking-live-results.json", proof)
    print(json.dumps({"report": "tests/reports/tracking-live-results.json", "rounds": len(proof["rounds"]),
        "feedback_event": proof["feedback"].get("event", {}).get("event_id")}))


if __name__ == "__main__":
    main()
