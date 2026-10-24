import pytest
from fastapi.testclient import TestClient

from scholar_graph.api import create_app
from graph_samples import graph_bundles


@pytest.fixture
def api(tmp_path):
    app = create_app(data_dir=tmp_path)
    bundles = graph_bundles()
    for bundle in bundles:
        app.state.repository.store.paper(bundle)
    return TestClient(app), bundles


def test_real_persisted_graph_endpoint_is_deterministic_and_complete(api):
    client, bundles = api
    ids = [bundle["paper_meta"]["id"] for bundle in bundles]
    response = client.get("/api/v1/graph", params=[("paper_ids", pid) for pid in ids])
    assert response.status_code == 200
    value = response.json()
    assert set(value) == {"nodes", "edges", "layers", "future_work", "diagnostics"}
    assert len(value["nodes"]) == 4 and len(value["edges"]) == 2
    assert value["layers"]["cornerstone"] == ["paper-graph-c", "paper-graph-b"]
    assert len(value["future_work"]["worth_exploring"]) == 2
    assert len(value["future_work"]["excluded"]) == 1
    assert client.get("/api/v1/graph", params=[("paper_ids", pid) for pid in reversed(ids)]).json() == value


def test_single_isolate_graph(api):
    value = api[0].get("/api/v1/graph", params={"paper_ids": "paper-graph-d"}).json()
    assert len(value["nodes"]) == 1 and value["nodes"][0]["pagerank"] == 1
    assert value["edges"] == [] and value["layers"]["isolated"] == ["paper-graph-d"]


@pytest.mark.parametrize("ids,status", [([], 422), (["paper-graph-a"] * 2, 422),
    (["missing"], 404), (["paper-graph-a", "missing"], 404), ([str(n) for n in range(101)], 422)])
def test_bad_graph_selection_returns_uniform_error(api, ids, status):
    response = api[0].get("/api/v1/graph", params=[("paper_ids", pid) for pid in ids])
    assert response.status_code == status
    assert set(response.json()) == {"error_code", "message", "details"}


def test_graph_does_not_read_model_credentials(api, monkeypatch):
    monkeypatch.setenv("SCHOLAR_GRAPH_QA_MODE", "deepseek")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert api[0].get("/api/v1/graph", params={"paper_ids": "paper-graph-d"}).status_code == 200
