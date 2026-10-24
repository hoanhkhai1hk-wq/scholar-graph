import copy

import pytest
from fastapi.testclient import TestClient

from scholar_graph.api import create_app
from scholar_graph.errors import PipelineError
from scholar_graph.status import ParseJob
from test_validation_status import example_bundle


@pytest.fixture
def api(tmp_path):
    app = create_app(data_dir=tmp_path)
    bundle = example_bundle()
    app.state.repository.store.paper(bundle)
    return TestClient(app, raise_server_exceptions=False), app, bundle


def assert_error(response, status, code):
    assert response.status_code == status
    value = response.json()
    assert set(value) == {"error_code", "message", "details"}
    assert value["error_code"] == code and value["message"]


def test_detail_children_filters_and_pagination(api):
    client, app, bundle = api
    pid = bundle["paper_meta"]["id"]
    detail = client.get(f"/api/v1/papers/{pid}")
    assert detail.json() == bundle["paper_meta"]
    for route, key in [("chunks", "chunks"), ("references", "reference_entries"), ("citation-links", "citation_links")]:
        assert f"/api/v1/papers/{pid}/{route}" in detail.headers["link"]
        assert client.get(f"/api/v1/papers/{pid}/{route}").json()["items"] == bundle[key]
        assert client.get(f"/api/v1/papers/{pid}/{route}?page=999").json()["items"] == []
    assert client.get(f"/api/v1/papers/{pid}/citation-links?ref_id=absent").json()["total"] == 0
    assert client.get("/api/v1/papers?title=absent").json()["total"] == 0
    assert client.get("/api/v1/papers?page=999").json()["page"] == 999
    result = client.get("/api/v1/papers?page_size=1000").json()
    assert result["page_size"] == 100 and result["total"] == 1


@pytest.mark.parametrize("query", ["page=0", "page=-1", "page=abc", "page_size=0", "page_size=-1"])
def test_invalid_queries_uniform_error(api, query):
    assert_error(api[0].get("/api/v1/papers?" + query), 422, "VALIDATION_ERROR")


@pytest.mark.parametrize("suffix", ["", "/chunks", "/references", "/citation-links", "/parse-status"])
def test_missing_records(api, suffix):
    assert_error(api[0].get("/api/v1/papers/missing" + suffix), 404, "PAPER_NOT_FOUND")


def test_latest_status_including_failed_unpublished_paper(api):
    client, app, _ = api
    repo = app.state.repository
    job = ParseJob("paper-failed", repo.gate, lambda history: repo.store.statuses("job-first", history))
    job.move("parsing", "检查", progress=5)
    job.move("failed", "失败", error=PipelineError("PARSE_FAILED", "自制失败。"))
    assert client.get("/api/v1/papers/paper-failed/parse-status").json() == job.current
    newer = ParseJob("paper-failed", repo.gate, lambda history: repo.store.statuses("job-second", history))
    assert client.get("/api/v1/papers/paper-failed/parse-status").json() == newer.current


def test_unexpected_exception_is_redacted(api, monkeypatch):
    def fail(**kwargs):
        raise RuntimeError("private diagnostic must not escape")
    monkeypatch.setattr(api[1].state.repository, "papers", fail)
    response = api[0].get("/api/v1/papers")
    assert_error(response, 500, "INTERNAL_ERROR")
    assert "private" not in response.text
