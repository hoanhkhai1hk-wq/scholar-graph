import pytest
from scholar_graph.api_repository import ApiRepository
from scholar_graph.validation import ContractGate
from scholar_graph.recommendations import recommendations, github_signals, WEIGHTS
from scholar_graph.errors import PipelineError
from graph_samples import graph_bundles


def prepared(tmp_path, change=None):
    bundles = graph_bundles()
    if change:
        change(bundles)
    repo = ApiRepository(tmp_path, ContractGate())
    for bundle in bundles:
        repo.store.paper(bundle)
    return repo


def test_recommendation_order_scores_and_real_neighbor_reasons(tmp_path):
    repo = prepared(tmp_path)
    values = recommendations(repo, "paper-graph-a", 2026)
    assert [item["paper"]["id"] for item in values] == ["paper-graph-b", "paper-graph-c", "paper-graph-d"]
    first = values[0]
    assert first["signals"]["graph_neighbor"] == 1
    assert first["score"] == pytest.approx(100 * sum(WEIGHTS[k] * (v or 0) for k, v in first["signals"].items()))
    proof = next(reason for reason in first["reasons"] if reason["signal"] == "graph_neighbor")["evidence"]["edges"][0]
    repo.gate.anchor(proof["anchor"], [repo.paper("paper-graph-a")])
    assert all("github_link" in item["missing_signals"] for item in values)
    assert all(not any(reason["signal"] == "github_link" for reason in item["reasons"]) for item in values)


def test_only_actual_metadata_github_urls_count_and_license_not_assumed(tmp_path):
    repo = prepared(tmp_path, lambda bundles: bundles[3]["paper_meta"].update(abstract="Code: https://github.com/synthetic/example-repo."))
    candidate = next(item for item in recommendations(repo, "paper-graph-a", 2026) if item["paper"]["id"] == "paper-graph-d")
    assert candidate["signals"]["github_link"] == 1 and "github_link" not in candidate["missing_signals"]
    assert next(reason for reason in candidate["reasons"] if reason["signal"] == "github_link")["evidence"]["links"][0]["metadata_field"] == "abstract"
    for url in ["https://github.com.evil.invalid/user/repo", "https://user@github.com/user/repo", "https://github.com/user/repo/issues/1"]:
        assert github_signals({"abstract": url, "source": None}) == []


@pytest.mark.parametrize("year", [None, 2030])
def test_unknown_or_future_year_does_not_create_recency(tmp_path, year):
    repo = prepared(tmp_path, lambda bundles: bundles[3]["paper_meta"].update(year=year))
    candidate = next(item for item in recommendations(repo, "paper-graph-a", 2026) if item["paper"]["id"] == "paper-graph-d")
    assert candidate["signals"]["recency"] is None
    assert not any(reason["signal"] == "recency" for reason in candidate["reasons"])


def test_missing_seed_is_not_fake_recommendation(tmp_path):
    with pytest.raises(PipelineError):
        recommendations(prepared(tmp_path), "missing", 2026)


def test_unverified_neighbor_is_not_a_positive_recommendation_signal(tmp_path):
    repo = prepared(tmp_path, lambda bundles: bundles[0].update(citation_links=[]))
    candidate = next(item for item in recommendations(repo, "paper-graph-a", 2026) if item["paper"]["id"] == "paper-graph-b")
    assert candidate["signals"]["graph_neighbor"] == 0
    assert not any(reason["signal"] == "graph_neighbor" for reason in candidate["reasons"])
