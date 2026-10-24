import pytest
from fastapi.testclient import TestClient
from graph_samples import graph_bundles
from scholar_graph.api import create_app
from scholar_graph.recommendations import FORMULA
from test_api_read import assert_error


def client_for(tmp_path, count=4):
    app = create_app(data_dir=tmp_path)
    bundles = graph_bundles()
    for bundle in bundles[:count]:
        app.state.repository.store.paper(bundle)
    return TestClient(app), app


def test_recommendation_signals_formula_scores_and_pagination(tmp_path):
    client, app = client_for(tmp_path)
    response = client.get("/api/v1/recommendations?paper_id=paper-graph-a&as_of_year=2026&page_size=1000")
    assert response.status_code == 200
    page = response.json()
    assert page["page_size"] == 100 and page["total"] == 3
    assert [item["paper"]["id"] for item in page["items"]] == ["paper-graph-b", "paper-graph-c", "paper-graph-d"]
    assert page["items"][0]["signals"]["graph_neighbor"] == 1
    assert all("github_link" in item["missing_signals"] for item in page["items"])
    assert all("citation_count" not in str(item) for item in page["items"])
    assert "without reweighting" in FORMULA
    over = client.get("/api/v1/recommendations?paper_id=paper-graph-a&page=999")
    assert over.json()["items"] == [] and over.headers["X-ScholarGraph-Recommendation-Reason"] == "PAGE_OUT_OF_RANGE"


def test_empty_recommendations_do_not_fabricate_candidates(tmp_path):
    client, app = client_for(tmp_path, count=1)
    response = client.get("/api/v1/recommendations?paper_id=paper-graph-a")
    assert response.json()["total"] == 0 and response.json()["items"] == []
    assert response.headers["X-ScholarGraph-Recommendation-Reason"] == "NO_CANDIDATES"


@pytest.mark.parametrize("query", ["", "paper_id=paper-graph-a&page=0", "paper_id=paper-graph-a&page_size=0",
                                  "paper_id=paper-graph-a&as_of_year=0"])
def test_invalid_recommendation_request_is_uniform_error(tmp_path, query):
    client, app = client_for(tmp_path)
    assert_error(client.get("/api/v1/recommendations?" + query), 422, "VALIDATION_ERROR")


def test_missing_seed_returns_not_found(tmp_path):
    client, app = client_for(tmp_path)
    assert_error(client.get("/api/v1/recommendations?paper_id=missing"), 404, "PAPER_NOT_FOUND")
