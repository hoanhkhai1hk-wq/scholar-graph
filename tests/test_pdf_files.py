import asyncio
import hashlib
from pathlib import Path
import sqlite3

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter

from scholar_graph.api import create_app
from scholar_graph.pdf_files import PdfFiles
from scholar_graph.errors import PipelineError
from sample_pdfs import make_pdf
from test_api_read import assert_error
from test_arxiv_api import client_for


@pytest.fixture(scope="module")
def uploaded(tmp_path_factory):
    folder = tmp_path_factory.mktemp("original-pdf")
    source = make_pdf(folder / "input.pdf")
    app = create_app(data_dir=folder / "records")
    client = TestClient(app)
    value = client.post("/api/v1/papers", files={"file": ("../../renamed.pdf", source.read_bytes(), "application/pdf")})
    assert value.status_code == 201, value.text
    return app, client, source, value.json()["id"]


def test_uploaded_original_survives_temporary_cleanup_and_restart(uploaded):
    app, client, source, pid = uploaded
    response = client.get(f"/api/v1/papers/{pid}/file")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'inline; filename="paper.pdf"'
    assert response.content == source.read_bytes()
    assert hashlib.sha256(response.content).hexdigest() == pid.removeprefix("paper-")
    assert list((app.state.repository.root / ".uploads").iterdir()) == []
    restarted = TestClient(create_app(data_dir=app.state.repository.root))
    assert restarted.get(f"/api/v1/papers/{pid}/file").content == response.content
    assert '/file>; rel="file"' in client.get(f"/api/v1/papers/{pid}").headers["link"]


def test_range_and_local_browser_headers(uploaded):
    _, client, source, pid = uploaded
    response = client.get(f"/api/v1/papers/{pid}/file", headers={"Range": "bytes=0-31", "Origin": "http://localhost:3000"})
    assert response.status_code == 206 and response.content == source.read_bytes()[:32]
    assert response.headers["content-range"].startswith("bytes 0-31/")
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    preflight = client.options(f"/api/v1/papers/{pid}/file", headers={"Origin": "http://127.0.0.1:3000",
        "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "range,if-range"})
    assert preflight.status_code == 200
    assert_error(client.get(f"/api/v1/papers/{pid}/file", headers={"Range": "invalid"}), 400, "VALIDATION_ERROR")
    unsatisfied = client.get(f"/api/v1/papers/{pid}/file", headers={"Range": "bytes=99999999-"})
    assert_error(unsatisfied, 416, "VALIDATION_ERROR")
    assert unsatisfied.headers["content-range"] == f"bytes */{source.stat().st_size}"


@pytest.mark.parametrize("pid", ["unknown", "..", "%2e%2e%5cprivate", "%2e%2e%2fprivate", "%252e%252e%255cprivate", "C:%5cprivate", "paper%27%20OR%201=1--"])
def test_unknown_and_traversal_are_uniform_404(uploaded, pid):
    assert_error(uploaded[1].get(f"/api/v1/papers/{pid}/file"), 404, "PAPER_NOT_FOUND")


def test_legacy_paper_without_original_is_explicit_404(tmp_path):
    from test_validation_status import example_bundle
    app = create_app(data_dir=tmp_path)
    bundle = example_bundle()
    app.state.repository.store.paper(bundle)
    response = TestClient(app).get(f'/api/v1/papers/{bundle["paper_meta"]["id"]}/file')
    assert_error(response, 404, "PAPER_NOT_FOUND")
    assert "原件" in response.json()["message"]
    assert not (tmp_path / "original-pdfs").exists()  # GET never creates an empty archive/index.


def test_arxiv_fetch_preserves_its_actual_download_and_is_idempotent(tmp_path):
    client, app = client_for(tmp_path)
    first = client.post("/api/v1/retrieval/fetch", json={"title": "Synthetic ScholarGraph Study"}).json()
    assert first["succeeded"]
    pid = first["paper"]["id"]
    result = client.get(f"/api/v1/papers/{pid}/file")
    assert result.status_code == 200
    assert hashlib.sha256(result.content).hexdigest() == first["paper"]["file_hash"]
    second = client.post("/api/v1/retrieval/fetch", json={"title": "Synthetic ScholarGraph Study"}).json()
    assert second["succeeded"] and second["already_present"]
    assert len(list((app.state.repository.root / "original-pdfs").glob("*.pdf"))) == 1
    assert client.get(f"/api/v1/papers/{pid}/file").content == result.content


def test_hash_mismatch_cannot_register_a_source(tmp_path):
    source = make_pdf(tmp_path / "source.pdf")
    store = PdfFiles(tmp_path / "records")
    with pytest.raises(PipelineError, match="SHA-256"):
        store.retain(source, {"id": "paper-one", "file_hash": "0" * 64})
    assert not list(store.folder.glob("*.pdf"))
    assert not list(store.folder.glob(".pending-*"))
    with pytest.raises(PipelineError) as failure:
        store.locate("paper-one")
    assert failure.value.code == "PAPER_NOT_FOUND"


def test_storage_tampering_is_not_served(tmp_path):
    app = create_app(data_dir=tmp_path / "records")
    source = make_pdf(tmp_path / "source.pdf")
    store = PdfFiles(app.state.repository.root)
    store.retain(source, {"id": "paper-known", "file_hash": hashlib.sha256(source.read_bytes()).hexdigest()})
    target = store.locate("paper-known")
    target.write_bytes(b"corrupt")
    response = TestClient(app).get("/api/v1/papers/paper-known/file")
    assert_error(response, 422, "VALIDATION_ERROR")
    assert response.content != b"corrupt"


def test_bad_path_inside_index_cannot_escape_archive(tmp_path):
    app = create_app(data_dir=tmp_path / "records")
    source = make_pdf(tmp_path / "source.pdf")
    store = PdfFiles(app.state.repository.root)
    store.retain(source, {"id": "paper-known", "file_hash": hashlib.sha256(source.read_bytes()).hexdigest()})
    with sqlite3.connect(store.index) as db:
        db.execute("UPDATE originals SET storage_name='../source.pdf'")
    assert_error(TestClient(app).get("/api/v1/papers/paper-known/file"), 422, "VALIDATION_ERROR")


def test_large_response_emits_bounded_asgi_body_chunks_without_read_bytes(tmp_path, monkeypatch):
    source = make_pdf(tmp_path / "small.pdf")
    writer = PdfWriter(clone_from=PdfReader(source))
    writer.add_attachment("self-made-padding.bin", b"x" * (2 * 1024 * 1024))
    large = tmp_path / "large.pdf"
    writer.write(large)
    digest = hashlib.sha256(large.read_bytes()).hexdigest()
    app = create_app(data_dir=tmp_path / "records")
    PdfFiles(app.state.repository.root).retain(large, {"id": "paper-large", "file_hash": digest})
    def forbidden(*args, **kwargs):
        raise AssertionError("GET must not load the complete PDF with read_bytes")
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    sizes, received, status = [], hashlib.sha256(), []
    async def send(message):
        if message["type"] == "http.response.start":
            status.append(message["status"])
        if message["type"] == "http.response.body":
            sizes.append(len(message.get("body", b"")))
            received.update(message.get("body", b""))
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}
    asyncio.run(app({"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1", "method": "GET", "scheme": "http", "path": "/api/v1/papers/paper-large/file",
        "raw_path": b"/api/v1/papers/paper-large/file", "query_string": b"", "headers": [],
        "server": ("testserver", 80), "client": ("testclient", 1), "root_path": ""}, receive, send))
    assert status == [200] and received.hexdigest() == digest
    assert len(sizes) > 30 and max(sizes) <= 64 * 1024
    assert sum(sizes) == large.stat().st_size
