import hashlib

import pytest
from fastapi.testclient import TestClient

from scholar_graph.api import create_app
from sample_pdfs import make_pdf
from test_api_read import assert_error


@pytest.fixture(scope="module")
def live_uploads(tmp_path_factory):
    root = tmp_path_factory.mktemp("api-local-engines")
    client = TestClient(create_app(data_dir=root / "records"))
    first = make_pdf(root / "first.pdf")
    second = make_pdf(root / "second.pdf", version="v7", samples=18)
    # Real local MinerU, no dependency mocks or Docker.
    response = client.post("/api/v1/papers", files={"file": ("first.pdf", first.read_bytes(), "application/pdf")})
    assert response.status_code == 201, response.text
    batch = client.post("/api/v1/papers/batch", files=[
        ("files", ("second.pdf", second.read_bytes(), "application/pdf")),
        ("files", ("broken.pdf", b"%PDF-invalid", "application/pdf")),
        ("files", ("not-pdf.txt", b"wrong extension", "text/plain")),
        ("files", ("first-again.pdf", first.read_bytes(), "application/pdf")),
    ])
    return client, response, batch, root


def test_real_single_upload_and_children(live_uploads):
    client, response, _, _ = live_uploads
    meta = response.json()
    assert len(meta) == 14
    assert client.get(response.headers["location"]).json() == meta
    assert client.get(response.headers["location"] + "/parse-status").json()["progress"] == 100
    for child in ("chunks", "references", "citation-links"):
        assert client.get(response.headers["location"] + "/" + child).json()["total"] >= 1


def test_real_batch_partial_failure_and_continuation(live_uploads):
    client, _, response, _ = live_uploads
    assert response.status_code == 200
    value = response.json()
    assert set(value) == {"succeeded", "failed", "succeeded_count", "failed_count"}
    assert value["succeeded_count"] == value["failed_count"] == 2
    assert [item["filename"] for item in value["failed"]] == ["broken.pdf", "not-pdf.txt"]
    assert [item["error_code"] for item in value["failed"]] == ["PARSE_FAILED", "UNSUPPORTED_FILE_TYPE"]
    for item in value["succeeded"]:
        assert item["parse_status"]["status"] == "queued" and item["parse_status"]["progress"] == 0
        assert client.get(f'/api/v1/papers/{item["paper_id"]}/parse-status').json()["status"] == "completed"
    failed_pid = "paper-" + hashlib.sha256(b"%PDF-invalid").hexdigest()
    status = client.get(f"/api/v1/papers/{failed_pid}/parse-status").json()
    assert status["status"] == "failed" and status["error_code"] == "PARSE_FAILED"
    assert_error(client.get(f"/api/v1/papers/{failed_pid}"), 404, "PAPER_NOT_FOUND")


def test_batch_empty_and_bad_fields(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))
    assert client.post("/api/v1/papers/batch").json()["succeeded_count"] == 0
    response = client.post("/api/v1/papers/batch", files={"wrong": ("file.pdf", b"bad")})
    assert response.status_code == 200 and response.json()["failed"][0]["filename"] == "file.pdf"
    assert response.json()["failed"][0]["error_code"] == "VALIDATION_ERROR"
    assert_error(client.post("/api/v1/papers"), 422, "VALIDATION_ERROR")
    assert_error(client.post("/api/v1/papers", files={"file": ("bad.txt", b"bad")}), 415, "UNSUPPORTED_FILE_TYPE")
