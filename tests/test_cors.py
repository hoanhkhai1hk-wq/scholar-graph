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
