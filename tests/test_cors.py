import pytest
from fastapi.testclient import TestClient
from scholar_graph.api import create_app


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:3000"])
def test_local_development_preflight_and_actual_response(tmp_path, origin):
    client = TestClient(create_app(data_dir=tmp_path))
    response = client.options("/api/v1/papers", headers={"Origin": origin,
        "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert set(response.headers["access-control-allow-methods"].split(", ")) == {"GET", "POST"}
    response = client.get("/api/v1/papers", headers={"Origin": origin})
    assert response.status_code == 200 and response.headers["access-control-allow-origin"] == origin
    assert "Location" in response.headers["access-control-expose-headers"]
    error = client.get("/api/v1/papers/absent", headers={"Origin": origin})
    assert error.status_code == 404 and error.headers["access-control-allow-origin"] == origin


def test_disallowed_origins_and_proxy_upstream_without_origin(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))
    response = client.options("/api/v1/papers", headers={"Origin": "https://unlisted.invalid",
        "Access-Control-Request-Method": "POST"})
    assert response.status_code == 400 and "access-control-allow-origin" not in response.headers
    response = client.get("/api/v1/papers")  # Same-origin Next server proxy makes this upstream request.
    assert response.status_code == 200 and response.json()["items"] == []


def test_unexpected_error_keeps_local_cors_without_exposing_exception(tmp_path, monkeypatch):
    app = create_app(data_dir=tmp_path)
    def broken(**kwargs):
        raise RuntimeError("private upstream diagnostic")
    monkeypatch.setattr(app.state.repository, "papers", broken)
    client = TestClient(app, raise_server_exceptions=False)
    for origin in ("http://localhost:3000", "https://unlisted.invalid"):
        response = client.get("/api/v1/papers", headers={"Origin": origin})
        assert response.status_code == 500 and "private" not in response.text
        assert set(response.json()) == {"error_code", "message", "details"}
        assert ("access-control-allow-origin" in response.headers) == (origin == "http://localhost:3000")
