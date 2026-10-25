"""Persisted, auditable feedback with deterministic self-made topic examples."""

import pytest
from fastapi.testclient import TestClient

from graph_samples import graph_bundles
from scholar_graph.api import create_app


def prepare(tmp_path):
    app = create_app(data_dir=tmp_path)
    bundles = graph_bundles()
    for bundle, title in zip(bundles, ["Graph Seed", "Graph Calibration", "Neural Transfer", "Neural Transfer Extensions"], strict=True):
        bundle["paper_meta"]["title"] = title
        app.state.repository.store.paper(bundle)
    return TestClient(app)


def rankings(client, profile="local"):
    return client.get("/api/v1/recommendations", params={"paper_id": "paper-graph-a", "as_of_year": 2026, "profile_id": profile}).json()["items"]


def test_one_like_changes_similar_paper_rank_and_survives_restart(tmp_path):
    client = prepare(tmp_path)
    before = rankings(client)
    response = client.post("/api/v1/recommendations/feedback", json={"paper_id": "paper-graph-d",
        "seed_paper_id": "paper-graph-a", "vote": "like", "as_of_year": 2026})
    assert response.status_code == 200
    event = response.json()
    assert event["before"][0]["paper_id"] == "paper-graph-b"
    assert event["after"][0]["paper_id"] == "paper-graph-d"
    after = rankings(client)
    related = next(item for item in after if item["paper"]["id"] == "paper-graph-c")
    assert related["feedback_adjustment"] > 0
    proof = related["reasons"][-1]["evidence"]["votes"][0]
    assert proof["matched_terms"] == ["neural", "transfer"]
    restarted = TestClient(create_app(data_dir=tmp_path))
    assert rankings(restarted) == after
    profile = restarted.get("/api/v1/recommendations/feedback").json()
    assert len(profile["votes"]) == len(profile["events"]) == 1
    assert profile["events"][0] == event
    assert rankings(restarted, "other") == before


def test_dislike_replaces_vote_without_stacking_and_missing_paper_is_404(tmp_path):
    client = prepare(tmp_path)
    body = {"paper_id": "paper-graph-d", "seed_paper_id": "paper-graph-a", "vote": "like", "as_of_year": 2026}
    client.post("/api/v1/recommendations/feedback", json=body)
    for _ in range(2):
        result = client.post("/api/v1/recommendations/feedback", json={**body, "vote": "dislike"})
        assert result.status_code == 200
    profile = client.get("/api/v1/recommendations/feedback").json()
    assert len(profile["votes"]) == 1 and len(profile["events"]) == 3
    assert profile["votes"][0]["vote"] == -1
    item = next(item for item in rankings(client) if item["paper"]["id"] == "paper-graph-d")
    assert item["feedback_adjustment"] == -50
    response = client.post("/api/v1/recommendations/feedback", json={**body, "paper_id": "missing"})
    assert response.status_code == 404 and set(response.json()) == {"error_code", "message", "details"}


def test_pure_recommendation_view_and_framework_do_not_read_profile_storage(tmp_path):
    from scholar_graph.frameworks import SelectedPapers, generate_outline
    from scholar_graph.recommendations import recommendations
    from scholar_graph.validation import ContractGate
    bundles = graph_bundles()
    view = SelectedPapers(bundles, ContractGate())
    assert recommendations(view, "paper-graph-a", 2026)[0]["scoring_version"] == "module-four-v1"
    assert generate_outline(bundles, view.gate)["chapters"]


@pytest.mark.parametrize("patch", [{"vote": "neutral"}, {"profile_id": "../other"}, {"as_of_year": 0}, {"extra": 1}])
def test_invalid_feedback_is_not_persisted(tmp_path, patch):
    client = prepare(tmp_path)
    body = {"paper_id": "paper-graph-d", "seed_paper_id": "paper-graph-a", "vote": "like", **patch}
    assert client.post("/api/v1/recommendations/feedback", json=body).status_code == 422
    assert client.get("/api/v1/recommendations/feedback").json()["events"] == []
