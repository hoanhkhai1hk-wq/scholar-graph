"""Contribution accounting must reconstruct scores and retain every recall route."""
import json

import pytest

from scholar_graph.rank_fusion import contribution_fusion
from scholar_graph.qa_retrieval import QAHybridRetriever
from test_qa_hybrid_retrieval import make, Vector


def test_asymmetric_recall_produces_nonconstant_bounded_weights_and_known_order():
    ranked, trace = contribution_fusion({"dense": ["a", "b", "c"], "lexical": ["b", "c"]})
    assert [cid for cid, _ in ranked] == ["b", "c", "a"]
    assert trace["routes"]["dense"]["weight"] == .65
    assert trace["routes"]["lexical"]["weight"] == .35
    assert trace["routes"]["dense"]["unique"] == 1
    assert trace["routes"]["lexical"]["shared"] == 2
    assert dict(ranked)["b"] == pytest.approx(.65 * 61 / 62 + .35)


@pytest.mark.parametrize("routes", [
    {"dense": [], "lexical": []}, {"dense": ["a", "b"], "lexical": []},
    {"dense": [], "lexical": ["a", "b"]},
    {"dense": ["a", "b"], "lexical": ["b", "c", "d"]},
    {"dense": ["a", "b", "c"], "lexical": ["a", "b", "c"]},
])
def test_replay_from_ranks_weights_and_credit_shares_reconstructs_all_scores(routes):
    ranked, trace = contribution_fusion(routes)
    assert {cid for cid, _ in ranked} == set().union(*map(set, routes.values()))
    weights = {name: row["weight"] for name, row in trace["routes"].items()}
    assert sum(weights.values()) == pytest.approx(1 if ranked else 0)
    for name, row in trace["routes"].items():
        assert row["recalled"] == row["unique"] + row["shared"]
        if not routes[name]:
            assert row["weight"] == 0
        expected_mass = sum(61 / (60 + rank) / sum(cid in route for route in routes.values())
                            for rank, cid in enumerate(routes[name], 1))
        assert row["credit_mass"] == pytest.approx(expected_mass)
    for cid, score in ranked:
        assert 0 < score <= 1
        contributions = trace["hits"][cid]["contributions"]
        for name in routes:
            rank = routes[name].index(cid) + 1 if cid in routes[name] else None
            assert trace["hits"][cid]["ranks"][name] == rank
            assert contributions[name] == pytest.approx(weights[name] * 61 / (60 + rank) if rank else 0)
        assert sum(contributions.values()) == pytest.approx(score)
    assert contribution_fusion(routes) == (ranked, trace)


def test_inactive_route_does_not_halve_scores_or_penalize_minimum_relevance():
    ranked, trace = contribution_fusion({"dense": ["a", "b"], "lexical": []})
    assert dict(ranked)["a"] == 1 and trace["routes"]["dense"]["weight"] == 1


def test_duplicate_route_ids_are_not_double_counted():
    with pytest.raises(ValueError):
        contribution_fusion({"dense": ["a", "a"], "lexical": []})


def test_qa_records_actual_weights_and_full_trace_without_query_or_source_text(tmp_path):
    repo, bundle, service = make(tmp_path)
    evidence, meta = service.retrieve(bundle, "samples")
    assert evidence[0]["location"]["bbox"] == bundle["chunks"][0]["bbox"]
    fusion = meta["fusion"]
    assert fusion["method"] == "contribution_weighted_rrf" and fusion["recording_status"] == "SAVED"
    path = tmp_path / "qa-retrieval" / "fusion" / (fusion["trace_id"] + ".json")
    trace = json.loads(path.read_text(encoding="utf-8"))
    assert trace["routes"] == fusion["routes"]
    cid = evidence[0]["anchor"]["chunk_id"]
    assert trace["hits"][cid]["score"] == sum(trace["hits"][cid]["contributions"].values())
    assert trace["final_order"] == [cid]
    assert bundle["chunks"][0]["text"] not in path.read_text(encoding="utf-8")


def test_trace_write_failure_keeps_real_vector_results_and_reports_recording_failure(tmp_path, monkeypatch):
    _, bundle, service = make(tmp_path)
    def fail(*args):
        raise OSError("test-only disk failure")
    monkeypatch.setattr("scholar_graph.qa_retrieval.write_json", fail)
    evidence, meta = service.retrieve(bundle, "samples")
    assert evidence and meta["method"] == "hybrid"
    assert meta["fusion"]["recording_status"] == "UNAVAILABLE" and "trace_id" not in meta["fusion"]
