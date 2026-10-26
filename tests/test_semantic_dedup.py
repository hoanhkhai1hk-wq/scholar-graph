"""Deterministic fake-vector regression; real BGE-M3 evidence is a separate probe."""
import copy
import json
import math
from pathlib import Path
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from scholar_graph.api import create_app
from scholar_graph.dedup import similarity, human_decision
from scholar_graph.pipeline import Pipeline
from scholar_graph.retrieval import VectorUnavailable
from scholar_graph.semantic_dedup import SemanticDedup
from scholar_graph.semantic_vectors import band, calibrate, cosine, representative_chunks, REPRESENTATION
from scholar_graph.storage import RecordStore
from scholar_graph.validation import ContractGate
from scholar_graph.vector_search import MODEL_REVISION
from sample_pdfs import make_pdf
from test_dedup import versions

POLICY = {"review_threshold": .85, "duplicate_threshold": .93, "model_revision": MODEL_REVISION, "representation": REPRESENTATION}


class Vectors:
    last_metadata = {"method": "explicit_test_double_not_real_bge"}
    def __init__(self, score=0.98, failure=None):
        self.score, self.failure = score, failure
    def encode(self, bundles):
        if self.failure:
            raise VectorUnavailable(self.failure)
        return {b["paper_meta"]["id"]: [1, 0] if n == 0 else [self.score, math.sqrt(1 - self.score ** 2)] for n, b in enumerate(bundles)}


def prepare(tmp_path, score=.98):
    old, new = versions()
    for b in (old, new):
        b["paper_meta"].update(doi=None, arxiv_id=None, title=None, authors=[])
    new["chunks"][0]["text"] = "A substantially reworded investigation with entirely different lexical surface."
    store = RecordStore(tmp_path, ContractGate())
    store.paper(old)
    return old, new, store, SemanticDedup(tmp_path, encoder=Vectors(score), policy=POLICY)


def test_real_calibration_policy_has_observed_margin_and_independent_inputs():
    root = Path(__file__).resolve().parents[1]
    report = json.loads((root / "tests/reports/semantic-dedup-calibration.json").read_text(encoding="utf-8"))
    positive = [p["score"] for p in report["positive_pairs"]]
    negative = [p["score"] for p in report["negative_pairs"]]
    policy = json.loads((root / "backend/scholar_graph/semantic_thresholds.json").read_text(encoding="utf-8"))
    computed = calibrate(positive, negative)
    assert all(policy[k] == v for k, v in computed.items())
    assert max(negative) < policy["review_threshold"] < policy["duplicate_threshold"] < min(positive)
    assert all(band(pair["score"], policy) == "duplicate" for pair in report["heldout_positive_pairs"])
    assert not {"1706.03762v7.pdf", "1706.03762v1.pdf", "N19-1423.pdf"} & set(policy["calibration_files"])


@pytest.mark.parametrize("score,expected", [(.849999, "new_paper"), (.85, "manual_review"), (.929999, "manual_review"), (.93, "duplicate"), (1, "duplicate")])
def test_threshold_boundaries(score, expected):
    assert band(score, POLICY) == expected


@pytest.mark.parametrize("p,n", [([.7]*3,[.8]*3),([1],[.2]*3),([float("nan")]*3,[.2]*3)])
def test_insufficient_or_overlapping_calibration_cannot_auto_enable(p, n):
    with pytest.raises(ValueError):
        calibrate(p, n)


@pytest.mark.parametrize("left,right", [([0, 0],[1,0]),([float("nan")],[1]),([1],[1,0])])
def test_invalid_vectors_fail_instead_of_supplying_a_score(left, right):
    with pytest.raises(VectorUnavailable):
        cosine(left, right)


def test_semantic_match_can_trigger_when_dice_does_not(tmp_path):
    old, new, store, service = prepare(tmp_path)
    assert similarity(old, new) < .9 and store.dedup_candidate(new) is None
    prior, info = service.assess(new, store)
    assert prior == old and info["band"] == "duplicate" and info["score"] == pytest.approx(.98)


@pytest.mark.parametrize("score,category,found", [(.88, "manual_review", True), (.3, "new_paper", False)])
def test_middle_and_low_semantic_bands(tmp_path, score, category, found):
    old, new, store, service = prepare(tmp_path, score)
    prior, info = service.assess(new, store)
    assert info["band"] == category and (prior is not None) == found


def test_conflicting_identity_cannot_auto_duplicate(tmp_path):
    old, new, store, service = prepare(tmp_path)
    new["paper_meta"]["doi"] = "10.5555/new"
    old["paper_meta"]["doi"] = "10.5555/old"
    other_store = RecordStore(tmp_path / "different", store.gate)
    other_store.paper(old)
    _, info = service.assess(new, other_store)
    assert info["band"] == "manual_review" and info["candidates"][0]["identity_conflict"]


def test_doi_fast_path_does_not_call_encoder(tmp_path):
    old, new = versions()
    old["paper_meta"]["doi"] = new["paper_meta"]["doi"] = "10.5555/semantic-same"
    store = RecordStore(tmp_path, ContractGate())
    store.paper(old)
    service = SemanticDedup(tmp_path, encoder=Vectors(failure="must not encode"), policy=POLICY)
    prior, info = service.assess(new, store)
    assert prior == old and info["status"] == "identity_fast_path" and info["score"] is None


def test_unavailable_encoder_retains_legacy_and_names_fallback(tmp_path):
    old, new, store, service = prepare(tmp_path)
    service.encoder = Vectors(failure="LOCAL_WORKER_TIMEOUT")
    prior, info = service.assess(new, store)
    assert prior is None and info["status"] == "unavailable" and info["score"] is None
    assert info["fallback_reason"] == "LOCAL_WORKER_TIMEOUT"


def test_representatives_are_real_bounded_and_exclude_bibliography():
    old, _ = versions()
    old["chunks"] = [dict(old["chunks"][0], chunk_id=f"c{i}", section_path=["References" if i == 0 else "Introduction"], text="evidence " * 30) for i in range(30)]
    selected = representative_chunks(old)
    assert 1 <= len(selected) <= 8 and all(c["chunk_id"] != "c0" for c in selected)


def test_same_bytes_different_name_warns_without_self_comparison_or_reparse(tmp_path):
    service = SemanticDedup(tmp_path, encoder=Vectors(), policy=POLICY)
    pipelines = []
    def factory():
        pipeline = Pipeline(tmp_path, semantic=service)
        pipelines.append(pipeline)
        return pipeline
    client = TestClient(create_app(data_dir=tmp_path, pipeline_factory=factory))
    raw = make_pdf(tmp_path / "source.pdf").read_bytes()
    first = client.post("/api/v1/papers", files={"file": ("original.pdf", raw, "application/pdf")})
    second = client.post("/api/v1/papers", files={"file": ("renamed.pdf", raw, "application/pdf")})
    assert first.status_code == second.status_code == 201 and first.json() == second.json()
    assert "换名重传触发重复判定" in unquote(second.headers["X-ScholarGraph-Dedup-Warning"])
    meta = json.loads(unquote(second.headers["X-ScholarGraph-Dedup-Meta"]))
    assert meta["band"] == "duplicate" and meta["score"] == pytest.approx(1)
    assert len(list((tmp_path / "papers").glob("paper-*"))) == 1
    assert not (tmp_path / "comparisons").exists()
    assert "Link" not in second.headers  # No invalid self-comparison endpoint is advertised.
    assert pipelines[-1].last_job.current["status"] == "completed"


@pytest.mark.parametrize("score,expected", [(.88, "manual_review"), (.98, "keep_new")])
def test_pipeline_publishes_schema_valid_semantic_decision_and_human_survives(tmp_path, score, expected):
    from scholar_graph.status import ParseJob
    old, new, store, service = prepare(tmp_path, score)
    if expected == "keep_new":
        old["paper_meta"].update(arxiv_id="1706.03762v1", version="v1")
        new["paper_meta"].update(arxiv_id="1706.03762v7", version="v7")
        store = RecordStore(tmp_path / "versioned", store.gate)
        store.paper(old)
    pipeline = Pipeline(store.root, semantic=service)
    job = ParseJob(new["paper_meta"]["id"], store.gate)
    job.move("parsing", "fixture", progress=5)
    job.move("indexing", "fixture", progress=80)
    pipeline._publish(new, job, new["paper_meta"]["id"])
    app = create_app(data_dir=store.root)
    decision = app.state.repository.comparison(new["paper_meta"]["id"], kind="decision")
    diff = app.state.repository.comparison(new["paper_meta"]["id"], kind="diff")
    assert decision["recommendation"] == expected and decision["similarity"] == pytest.approx(score)
    human = human_decision(decision, "keep_both", "人工保留两个版本", diff, [old, new], store.gate)
    store.comparison(decision, diff, [old, new], human=human)
    store.comparison(decision, diff, [old, new])
    assert app.state.repository.comparison(new["paper_meta"]["id"], kind="decision") == human
