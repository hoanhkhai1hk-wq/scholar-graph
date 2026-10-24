import pytest
from fastapi.testclient import TestClient
from graph_samples import graph_bundles
from scholar_graph.api import create_app
from scholar_graph.retrieval import SearchService, VectorUnavailable
from test_api_read import assert_error


def prepared(tmp_path):
    app = create_app(data_dir=tmp_path)
    for bundle in graph_bundles():
        app.state.repository.store.paper(bundle)
    return TestClient(app), app


def test_search_real_anchors_order_pagination_cap_and_cors(tmp_path):
    client, app = prepared(tmp_path)
    response = client.post("/api/v1/retrieval/search", json={"question": "document-level extraction", "page_size": 999},
                           headers={"origin": "http://localhost:3000"})
    assert response.status_code == 200
    page = response.json()
    assert set(page) == {"items", "page", "page_size", "total", "total_pages", "has_next"}
    assert page["page_size"] == 100 and page["total"] > 0
    assert response.headers["X-ScholarGraph-Search-Mode"] == "lexical"
    assert "X-ScholarGraph-Search-Reason" in response.headers["access-control-expose-headers"]
    for hit in page["items"]:
        app.state.repository.gate.anchor(hit["anchor"], graph_bundles())
    overflow = client.post("/api/v1/retrieval/search", json={"question": "document-level extraction", "page": 999})
    assert overflow.json()["items"] == [] and overflow.json()["total"] == page["total"]
    assert overflow.headers["X-ScholarGraph-Search-Reason"] == "PAGE_OUT_OF_RANGE"


@pytest.mark.parametrize("body", [{"question": " "}, {"question": "test", "page": 0},
    {"question": "test", "paper_ids": []}, {"question": "test", "page_size": True},
    {"question": "test", "min_relevance": 2}, {"question": "test", "paper_ids": ["x", "x"]}])
def test_invalid_search_inputs_are_uniform_errors(tmp_path, body):
    client, app = prepared(tmp_path)
    assert_error(client.post("/api/v1/retrieval/search", json=body), 422, "VALIDATION_ERROR")


def test_empty_reason_and_missing_paper(tmp_path):
    client, app = prepared(tmp_path)
    response = client.post("/api/v1/retrieval/search", json={"question": "zzzznonexistent"})
    assert response.json()["items"] == []
    assert response.headers["X-ScholarGraph-Search-Reason"] == "NO_MATCHING_CHUNKS"
    assert_error(client.post("/api/v1/retrieval/search", json={"question": "test", "paper_ids": ["missing"]}), 404, "PAPER_NOT_FOUND")
    empty = TestClient(create_app(data_dir=tmp_path / "empty"))
    assert empty.post("/api/v1/retrieval/search", json={"question": "test"}).headers["X-ScholarGraph-Search-Reason"] == "EMPTY_CORPUS"


def test_worker_failure_is_explicit_not_false_vector_success(tmp_path):
    client, app = prepared(tmp_path)
    class Failing:
        def search(self, *args):
            raise VectorUnavailable
    app.state.search = SearchService(app.state.repository, Failing())
    response = client.post("/api/v1/retrieval/search", json={"question": "cross-lingual transfer"})
    assert response.headers["X-ScholarGraph-Search-Mode"] == "lexical"
    assert response.headers["X-ScholarGraph-Vector-Status"] == "UNAVAILABLE"
    assert all(hit["retrieval_method"] == "lexical" for hit in response.json()["items"])
