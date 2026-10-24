"""Reproducible HTTP evidence: synthetic corpus, optional real local BGE and public arXiv."""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import httpx
from fastapi.testclient import TestClient
from graph_samples import graph_bundles
from sample_pdfs import make_pdf
from scholar_graph.api import create_app
from scholar_graph.arxiv_fetch import ArxivClient, ArxivFetcher
from scholar_graph.retrieval import SearchService
from scholar_graph.recommendations import FORMULA
from scholar_graph.vector_search import BgeChromaSearch
from test_arxiv_fetch import ATOM, TITLE
from test_validation_status import example_bundle

BASELINE = "5e3e0dce8dbc51b441bbebe7fa88c785e10ccb04"


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--vector-python", type=Path)
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--live-arxiv", action="store_true")
    args = parser.parse_args()
    root = args.output_root.resolve()
    check(root.is_relative_to(ROOT / "data") and not root.exists(), "Use a fresh directory under ignored data/.")
    root.mkdir(parents=True)
    report = {"scope": "自制样例、非官方 pdf/ 用例；无官方三用例、前端或真实大模型验收。公开 arXiv 探针另记，不冒充自制或官方用例。",
              "run_utc": datetime.now(timezone.utc).isoformat(), "baseline": BASELINE,
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "formula": FORMULA, "cases": [], "frozen_contracts": []}
    app = create_app(data_dir=root / "records")
    for bundle in graph_bundles():
        app.state.repository.store.paper(bundle)
    client = TestClient(app)
    report["implemented_endpoints"] = [f"{method.upper()} {path}" for path, methods in client.get("/openapi.json").json()["paths"].items() for method in methods]
    check(len(report["implemented_endpoints"]) == 16, "Expected 16 implemented business endpoints")
    def call(name, method, path, *, body=None, params=None):
        start = time.monotonic()
        response = client.request(method, path, json=body, params=params)
        case = {"name": name, "request": {"method": method, "path": path, "body": body, "params": params},
                "http_status": response.status_code, "elapsed_seconds": round(time.monotonic() - start, 3),
                "headers": {key: value for key, value in response.headers.items() if key.startswith("x-scholargraph-")},
                "response": response.json()}
        report["cases"].append(case)
        check(response.status_code == 200, "HTTP smoke request failed")
        return case
    query = {"question": "cross-lingual transfer", "page_size": 999}
    app.state.search = SearchService(app.state.repository)
    lexical = call("lexical", "POST", "/api/v1/retrieval/search", body=query)
    check(lexical["headers"]["x-scholargraph-search-mode"] == "lexical", "Lexical mode not disclosed")
    empty = call("empty-lexical", "POST", "/api/v1/retrieval/search", body={"question": "zzzznonexistent"})
    check(empty["response"]["items"] == [], "Empty result was fabricated")
    call("out-of-range", "POST", "/api/v1/retrieval/search", body={**query, "page": 999})
    if args.vector_python and args.model_path:
        vector = BgeChromaSearch(args.vector_python, args.model_path, root / "chroma")
        app.state.search = SearchService(app.state.repository, vector)
        actual = call("real-bge-m3-hybrid", "POST", "/api/v1/retrieval/search", body=query)
        check(actual["headers"]["x-scholargraph-search-mode"] == "bge_m3_hybrid", "Actual BGE worker fell back; inspect environment, do not claim vector success")
        actual["native_evidence"] = vector.last_evidence
        check(vector.last_evidence["indexed_chunks"] == 4 and vector.last_evidence["dimension"] == 1024, "Wrong index size/dimension")
        subset = call("persistent-vector-subset", "POST", "/api/v1/retrieval/search",
                      body={**query, "paper_ids": ["paper-graph-c"]})
        subset["native_evidence"] = vector.last_evidence
        check(vector.last_evidence["updated_chunks"] == 0, "Expected persisted vector reuse")
        check(all(hit["anchor"]["paper_id"] == "paper-graph-c" for hit in subset["response"]["items"]), "Stale corpus leaked into evidence")
    rec = call("recommendations", "GET", "/api/v1/recommendations", params={"paper_id": "paper-graph-a", "as_of_year": 2026})
    check([item["paper"]["id"] for item in rec["response"]["items"]] == ["paper-graph-b", "paper-graph-c", "paper-graph-d"], "Unexpected recommendation order")
    pdf = make_pdf(root / "self-made.pdf").read_bytes()
    def public_mock(request):
        return httpx.Response(200, content=ATOM if request.url.path == "/api/query" else pdf)
    repo = app.state.repository
    app.state.arxiv_fetcher = ArxivFetcher(repo, client=ArxivClient(repo.gate, transport=httpx.MockTransport(public_mock), interval=0), lock=app.state.uploads.lock)
    fetched = call("synthetic-atom-real-mineru", "POST", "/api/v1/retrieval/fetch", body={"title": TITLE})
    check(fetched["response"]["succeeded"], "Synthetic PDF parsing failed")
    bundle = repo.paper(fetched["response"]["paper"]["id"])
    fetched["record_counts"] = {key: len(value) if isinstance(value, list) else 1 for key, value in bundle.items()}
    fetched["input_pdf_sha256"] = hashlib.sha256(pdf).hexdigest()
    app.state.arxiv_fetcher = ArxivFetcher(repo, client=ArxivClient(repo.gate,
        transport=httpx.MockTransport(lambda request: httpx.Response(503)), interval=0), lock=app.state.uploads.lock)
    failed = call("public-interface-failure-injection", "POST", "/api/v1/retrieval/fetch", body={"title": TITLE})
    check(not failed["response"]["succeeded"] and failed["response"]["metadata"] is None, "Fabricated failure metadata")
    if args.live_arxiv:
        # No environment key, model caller or arbitrary fetch URL is used here.
        app.state.arxiv_fetcher = ArxivFetcher(repo, lock=app.state.uploads.lock)
        reference = example_bundle()["reference_entries"][0].copy()
        reference.update(arxiv_id="1706.03762", doi=None)
        live = call("LIVE-public-arxiv-reference", "POST", "/api/v1/retrieval/fetch", body={"reference": reference})
        live["scope"] = "真实公开接口探针；不是官方 pdf/ 用例。失败保留真实错误，不计为成功。"
        if live["response"]["succeeded"]:
            bundle = repo.paper(live["response"]["paper"]["id"])
            live["record_counts"] = {key: len(value) if isinstance(value, list) else 1 for key, value in bundle.items()}
    for path in sorted((ROOT / "contracts").glob("*.json")):
        relative = path.relative_to(ROOT).as_posix()
        original = subprocess.check_output(["git", "rev-parse", f"{BASELINE}:{relative}"], cwd=ROOT, text=True).strip()
        current = subprocess.check_output(["git", "hash-object", relative], cwd=ROOT, text=True).strip()
        check(original == current, "Frozen schema or example changed")
        report["frozen_contracts"].append({"file": relative, "git_blob": current, "unchanged": True})
    check(len(report["frozen_contracts"]) == 22, "Expected eleven frozen schemas plus examples")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"cases": len(report["cases"]), "frozen_contract_files": 22,
                      "vector_executed": bool(args.vector_python and args.model_path),
                      "live_arxiv_executed": args.live_arxiv, "report": str(args.report)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
