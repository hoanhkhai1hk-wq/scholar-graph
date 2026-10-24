import httpx
import pytest
from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.arxiv_fetch import ArxivClient, ArxivFetcher
from sample_pdfs import make_pdf
from test_arxiv_fetch import ATOM, TITLE
from test_api_read import assert_error


def client_for(tmp_path, *, upstream_status=200):
    app = create_app(data_dir=tmp_path / "output")
    pdf = make_pdf(tmp_path / "self-made.pdf").read_bytes()
    def handle(request):
        return httpx.Response(upstream_status, content=ATOM if request.url.path == "/api/query" else pdf)
    repository = app.state.repository
    app.state.arxiv_fetcher = ArxivFetcher(repository, client=ArxivClient(repository.gate,
        transport=httpx.MockTransport(handle), interval=0), lock=app.state.uploads.lock)
    return TestClient(app), app


def test_fetch_reuses_parsed_paper_routes_and_real_queued_state(tmp_path):
    client, app = client_for(tmp_path)
    response = client.post("/api/v1/retrieval/fetch", json={"title": TITLE})
    assert response.status_code == 200
    result = response.json()
    assert result["succeeded"] and result["error"] is None
    assert result["initial_parse_status"]["status"] == "queued"
    pid = result["paper"]["id"]
    assert client.get(f"/api/v1/papers/{pid}/parse-status").json() == result["parse_status"]
    assert client.get(f"/api/v1/papers/{pid}").json() == result["paper"]
    assert client.get(f"/api/v1/papers/{pid}/chunks").json()["total"] > 0


def test_fetch_failure_has_actual_reason_and_no_fake_meta(tmp_path):
    client, app = client_for(tmp_path, upstream_status=503)
    response = client.post("/api/v1/retrieval/fetch", json={"title": TITLE})
    result = response.json()
    assert response.status_code == 200 and not result["succeeded"]
    assert set(result["error"]) == {"error_code", "message", "details"}
    assert result["error"]["error_code"] == "UPSTREAM_ERROR" and "503" in result["error"]["message"]
    assert result["metadata"] is result["paper"] is result["initial_parse_status"] is None


@pytest.mark.parametrize("body", [{}, {"title": " "}, {"title": TITLE, "reference": {}}, {"extra": 1}])
def test_invalid_fetch_request_uses_uniform_http_error(tmp_path, body):
    client, app = client_for(tmp_path)
    assert_error(client.post("/api/v1/retrieval/fetch", json=body), 422, "VALIDATION_ERROR")


def test_invalid_reference_record_is_not_accepted(tmp_path):
    client, app = client_for(tmp_path)
    result = client.post("/api/v1/retrieval/fetch", json={"reference": {"title": TITLE}}).json()
    assert not result["succeeded"] and result["error"]["error_code"] == "VALIDATION_ERROR"
