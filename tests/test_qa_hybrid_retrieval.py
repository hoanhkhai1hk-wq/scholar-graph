"""Deterministic QA wiring tests; fake vectors/rerankers are not live evidence."""
import copy
import json
import math
import subprocess
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from scholar_graph.api import create_app
from scholar_graph.api_repository import ApiRepository
from scholar_graph.orchestration import EvidenceAgent
from scholar_graph.qa_retrieval import LocalReranker, QAHybridRetriever
from scholar_graph.retrieval import VectorUnavailable
from scholar_graph.validation import ContractGate
from test_agent_orchestration import Model, repository
from test_validation_status import example_bundle
from test_qa_sse import parse_events


class Vector:
    def __init__(self, *, fail=False, invalid=False):
        self.fail, self.invalid, self.last_evidence = fail, invalid, None
    def search(self, chunks, query):
        if self.fail:
            raise VectorUnavailable
        self.last_evidence = {"dense": {c["chunk_id"]: .8 - n*.01 for n, c in enumerate(chunks)},
            "timing": {"model_load_seconds": 1.25, "index_seconds": .2, "query_seconds": .1}, "indexed_chunks": len(chunks)}
        if self.invalid:
            self.last_evidence["dense"] = {"stale": float("nan")}
        return []


def make(tmp_path, **kwargs):
    repo = ApiRepository(tmp_path, ContractGate())
    bundle = example_bundle()
    repo.store.paper(bundle)
    return repo, bundle, QAHybridRetriever(repo, Vector(**kwargs))


def test_hybrid_recall_retains_real_anchors_and_measured_timing(tmp_path):
    repo, bundle, service = make(tmp_path)
    evidence, meta = service.retrieve(bundle, "How many samples?")
    assert meta["method"] == "hybrid" and meta["vector_status"] == "READY"
    assert meta["lexical_recalled"] == meta["vector_recalled"] == 1
    assert meta["vector_timing"]["model_load_seconds"] == 1.25
    assert meta["evidence_count"] == len(evidence)
    for row in evidence:
        repo.gate.anchor(row["anchor"], [bundle], quote=row["quote"])


def test_retrieval_trace_metadata_is_a_snapshot(tmp_path):
    _, bundle, service = make(tmp_path)
    service.retrieve(bundle, "samples")
    first = service.metadata()
    service.retrieve(bundle, "sample size")
    assert len(first["retrieval"]) == 1 and len(service.metadata()["retrieval"]) == 2


def test_corrupt_rerank_policy_keeps_actual_vector_route(tmp_path):
    repo, bundle, _ = make(tmp_path)
    path = tmp_path / "qa-retrieval/reranker-policy.json"
    path.parent.mkdir()
    path.write_text("not JSON", encoding="utf-8")
    _, info = QAHybridRetriever(repo, Vector(), LocalReranker(tmp_path, "missing", "missing")).retrieve(bundle, "samples")
    assert info["method"] == "hybrid" and info["rerank"]["reason"] == "INVALID_RERANKER_POLICY"


def test_vector_only_recalls_cross_language_without_word_overlap(tmp_path):
    _, bundle, service = make(tmp_path)
    evidence, meta = service.retrieve(bundle, "规模多大？")
    assert meta["method"] == "vector" and not meta["lexical_recalled"] and evidence


@pytest.mark.parametrize("invalid", [False, True])
def test_unavailable_or_invalid_vectors_are_explicit_lexical_fallback(tmp_path, invalid):
    _, bundle, service = make(tmp_path, fail=not invalid, invalid=invalid)
    evidence, meta = service.retrieve(bundle, "How many samples?")
    assert meta["method"] == "lexical-fallback" and meta["vector_status"] == "UNAVAILABLE" and evidence
    assert "vector_timing" not in meta


def test_disabled_vector_preserves_strict_extractive_refusal(tmp_path):
    repo, bundle, _ = make(tmp_path)
    service = QAHybridRetriever(repo)
    evidence, meta = service.extractive(bundle, "规模多大？")
    assert not evidence and meta["method"] == "lexical-fallback" and meta["reason"] == "LOCAL_VECTOR_NOT_CONFIGURED"


def test_local_rerank_order_is_used_after_union(tmp_path):
    repo, bundle, _ = make(tmp_path)
    class Reranker:
        def order(self, query, chunks):
            return [c["chunk_id"] for c in reversed(chunks)], {"method": "bge-reranker-large", "timing": {"rerank_seconds": .1}}
    _, meta = QAHybridRetriever(repo, Vector(), Reranker()).retrieve(bundle, "samples")
    assert meta["rerank"]["method"] == "bge-reranker-large"


def configured_reranker(tmp_path, budget=5):
    python, model = tmp_path / "python.exe", tmp_path / "model"
    python.touch()
    model.mkdir()
    (model / "model.safetensors").touch()
    return LocalReranker(tmp_path / "records", python, model, budget_seconds=budget)


def test_slow_reranker_persists_measured_rrf_policy(tmp_path, monkeypatch):
    reranker = configured_reranker(tmp_path, budget=-1)  # Explicit test-only budget forces observed-time branch.
    monkeypatch.setenv("SYNTHETIC_API_KEY", "unit-not-real")
    def run(*args, **kwargs):
        assert "SYNTHETIC_API_KEY" not in kwargs["env"] and kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        return SimpleNamespace(returncode=0, stdout=json.dumps({"scores": {"a": .8}, "timing": {
            "model_load_seconds": 1, "rerank_seconds": 2}, "model": "BAAI/bge-reranker-large", "revision": "test"}))
    monkeypatch.setattr(subprocess, "run", run)
    order, info = reranker.order("query", [{"chunk_id": "a", "text": "actual test text"}])
    assert order is None and info["reason"] == "MEASURED_CPU_BUDGET_EXCEEDED" and info["timing"]["rerank_seconds"] == 2
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: pytest.fail("cached measured policy must not rerun slow model"))
    assert reranker.order("query", [])[1] == info


@pytest.mark.parametrize("mode", ["timeout", "exit", "invalid_ids", "nan"])
def test_rerank_failure_retains_fusion_not_fake_model_success(tmp_path, monkeypatch, mode):
    reranker = configured_reranker(tmp_path)
    def run(*args, **kwargs):
        if mode == "timeout":
            raise subprocess.TimeoutExpired("test", 90)
        return SimpleNamespace(returncode=1 if mode == "exit" else 0, stdout=json.dumps({"scores": {
            "stale" if mode == "invalid_ids" else "a": float("nan") if mode == "nan" else .1}}))
    monkeypatch.setattr(subprocess, "run", run)
    order, info = reranker.order("query", [{"chunk_id": "a", "text": "source"}])
    assert order is None and info["method"] == "rrf" and info["reason"] != "OK"


def test_agent_retrieve_and_tool_metadata_use_hybrid(tmp_path):
    repo, ids = repository(tmp_path)
    service = QAHybridRetriever(repo, Vector())
    value, meta = EvidenceAgent(repo, client=Model(), retriever=service).run(ids, "How many samples?")
    assert not any(record["refused"] for record in value["per_paper"])
    assert meta["method"] == "hybrid" and len(meta["retrieval"]) == 2
    retrieve = next(row for row in meta["trace"] if row["node"] == "retrieve")
    assert retrieve["retrieval"]["method"] == "hybrid"
    assert all(row["return_summary"]["method"] == "hybrid" for row in meta["tool_calls"])


def test_direct_and_compare_extractive_metadata_are_present(tmp_path, monkeypatch):
    app = create_app(data_dir=tmp_path)
    from test_dedup import versions
    bundles = versions()
    for bundle in bundles:
        app.state.repository.store.paper(bundle)
    monkeypatch.setattr("scholar_graph.qa_routes.qa_retriever", lambda repo: QAHybridRetriever(repo, Vector()))
    client = TestClient(app)
    single = client.post(f'/api/v1/papers/{bundles[0]["paper_meta"]["id"]}/qa', json={"question": "How many samples?"})
    assert single.status_code == 200 and json.loads(unquote(single.headers["X-ScholarGraph-QA-Meta"]))["method"] == "hybrid"
    compare = client.post("/api/v1/compare", json={"paper_ids": [b["paper_meta"]["id"] for b in bundles], "question": "How many samples?"})
    assert json.loads(unquote(compare.headers["X-ScholarGraph-QA-Meta"]))["method"] == "hybrid"


def test_no_key_sse_still_uses_hybrid_retrieve_and_emits_no_fake_tokens(tmp_path, monkeypatch):
    repo, bundle, service = make(tmp_path)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("scholar_graph.orchestration.qa_retriever", lambda _: service)
    app = create_app(data_dir=tmp_path)
    response = TestClient(app).post(f'/api/v1/papers/{bundle["paper_meta"]["id"]}/qa/stream', json={"question": "How many samples?"})
    events = parse_events(response.text)
    assert not any(e["event"] == "token" for e in events)
    assert events[-1]["data"]["metadata"]["method"] == "hybrid"
    assert events[-2]["data"]["anchors"]
