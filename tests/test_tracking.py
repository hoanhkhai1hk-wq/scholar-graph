"""Offline tracker protocol tests; real public runs have a separate probe/report."""

import copy
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from graph_samples import graph_bundles
from sample_pdfs import make_pdf
from scholar_graph.api import create_app
from scholar_graph.arxiv_fetch import ArxivClient
from scholar_graph.errors import PipelineError
from scholar_graph.tracking import seed_queries
from scholar_graph.tracking_cli import main
from scholar_graph.tracking_state import operation_lock
from test_arxiv_fetch import ATOM


def prepared(tmp_path):
    app = create_app(data_dir=tmp_path)
    bundles = graph_bundles()
    for bundle in bundles:
        app.state.repository.store.paper(bundle)
    return TestClient(app), app


def test_two_runs_candidates_related_and_no_second_import(tmp_path):
    client, app = prepared(tmp_path)
    raw = make_pdf(tmp_path / "source.pdf").read_bytes()
    atom = ATOM.replace(b"Synthetic ScholarGraph Study", b"Synthetic Graph Study")
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(200, content=atom if request.url.path == "/api/query" else raw)
    app.state.arxiv_fetcher.client = ArxivClient(app.state.repository.gate, transport=httpx.MockTransport(handle), interval=0)
    body = {"paper_ids": ["paper-graph-a"], "max_candidates": 2, "max_imports": 2}
    first = client.post("/api/v1/retrieval/tracking/run", json=body).json()
    second = client.post("/api/v1/retrieval/tracking/run", json=body).json()
    assert first["status"] == second["status"] == "completed"
    assert first["candidate_count"] == 1 and first["imported_count"] == 1
    assert second["imported_count"] == 0 and second["duplicate_count"] == 1
    candidate = first["candidates"][0]
    assert candidate["arxiv_id"] == "2601.00001v1" and candidate["title"] == "Synthetic Graph Study"
    assert candidate["related_to"][0]["paper_id"] == "paper-graph-a"
    assert "主题词重合" in candidate["related_to"][0]["reason"]
    assert sum(request.url.path.startswith("/pdf/") for request in requests) == 1
    assert client.get("/api/v1/retrieval/tracking/status").json()["latest_run"] == second
    recreated = TestClient(create_app(data_dir=tmp_path))
    assert recreated.get("/api/v1/retrieval/tracking/status").json()["latest_run"] == second
    queries = [request.url.params for request in requests if request.url.path == "/api/query"]
    assert all(q["sortBy"] == "submittedDate" and q["sortOrder"] == "descending" for q in queries)


def test_topic_and_reference_seeds_are_real_and_anchored(tmp_path):
    _, app = prepared(tmp_path)
    queries = seed_queries(app.state.repository, ["paper-graph-a"])
    assert {q["kind"] for q in queries} == {"topic", "citation"}
    citation = next(q for q in queries if q["kind"] == "citation")
    app.state.repository.gate.anchor(citation["anchor"], [app.state.repository.paper("paper-graph-a")])
    assert citation["reference"]["title"] in citation["query"]


def test_nullable_legacy_metadata_uses_true_title_and_reference_chunks(tmp_path):
    client, app = prepared(tmp_path)
    bundle = graph_bundles()[0]
    bundle["paper_meta"].update(id="paper-legacy", title=None, doi=None)
    original = bundle["chunks"][0]
    original.update(paper_id="paper-legacy", chunk_id="legacy-title", text="Attention Is All You Need",
                    section_path=[], heading_1=None)
    body = copy.deepcopy(original)
    body.update(chunk_id="legacy-body", text="We cite [1].")
    ref_chunk = copy.deepcopy(original)
    ref_chunk.update(chunk_id="legacy-ref", text="[1] Jimmy Lei Ba, Jamie Ryan Kiros, and Geoffrey E Hinton. Layer normalization. arXiv preprint arXiv:1607.06450, 2016.")
    bundle["chunks"] = [original, body, ref_chunk]
    bundle["reference_entries"][0].update(paper_id="paper-legacy", title=None)
    bundle["citation_links"][0].update(paper_id="paper-legacy", chunk_id="legacy-body")
    app.state.repository.store.paper(bundle)
    queries = seed_queries(app.state.repository, ["paper-legacy"])
    assert queries[0]["query"] == 'all:"attention"'
    assert queries[0]["anchor"]["chunk_id"] == "legacy-title"
    assert queries[1]["reference_title_excerpt"] == "Layer normalization"
    assert queries[1]["reference_anchor"]["chunk_id"] == "legacy-ref"
    for query in queries:
        app.state.repository.gate.anchor(query["anchor"], [bundle])


def test_failure_is_persisted_not_fabricated_and_due_task_skips(tmp_path, capsys):
    client, app = prepared(tmp_path)
    def failed(*args):
        raise PipelineError("UPSTREAM_ERROR", "arXiv 公共接口返回 HTTP 503，未取得所需记录或文件。")
    app.state.arxiv_fetcher.client.search = failed
    result = client.post("/api/v1/retrieval/tracking/run", json={"paper_ids": ["paper-graph-a"]}).json()
    assert result["status"] == "failed" and result["candidate_count"] == 0
    assert len(result["errors"]) == 2 and result["errors"][0]["error_code"] == "UPSTREAM_ERROR"
    assert "503" in result["errors"][0]["message"]
    assert main(["--data-dir", str(tmp_path), "--due"]) == 0
    assert json.loads(capsys.readouterr().out)["reason"] == "NOT_DUE"


def test_empty_status_and_empty_seed_fail_explicitly(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))
    assert client.get("/api/v1/retrieval/tracking/status").json()["latest_run"] is None
    result = client.post("/api/v1/retrieval/tracking/run", json={}).json()
    assert result["status"] == "failed" and result["errors"][0]["error_code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("body", [{"max_candidates": 0}, {"max_imports": 6}, {"interval_seconds": 1},
                                   {"paper_ids": []}, {"force": "true"}, {"extra": 1}])
def test_invalid_tracking_requests(tmp_path, body):
    client, _ = prepared(tmp_path)
    assert client.post("/api/v1/retrieval/tracking/run", json=body).status_code == 422


def test_in_progress_lock_does_not_start_duplicate_run(tmp_path):
    client, _ = prepared(tmp_path)
    with operation_lock(tmp_path, "poll"):
        response = client.post("/api/v1/retrieval/tracking/run", json={})
    assert response.status_code == 422 and response.json()["error_code"] == "VALIDATION_ERROR"


def test_search_rejects_invalid_atom_and_records_no_fake_candidates(tmp_path):
    client = ArxivClient(create_app(data_dir=tmp_path).state.repository.gate,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"<not-feed/>")), interval=0)
    with pytest.raises(PipelineError, match="Atom"):
        client.search('all:"attention"')


def test_no_shared_terms_is_not_a_relevance_claim(tmp_path):
    client, app = prepared(tmp_path)
    metadata = copy.deepcopy(graph_bundles()[0]["paper_meta"])
    metadata.update(id="arxiv-2601.00001v1", arxiv_id="2601.00001v1", title="Unrelated medicine", abstract="Clinical results")
    app.state.arxiv_fetcher.client.search = lambda *args: [metadata]
    result = client.post("/api/v1/retrieval/tracking/run", json={"paper_ids": ["paper-graph-a"]}).json()
    assert result["candidate_count"] == result["imported_count"] == 0 and result["status"] == "completed"


def test_parse_failure_and_import_budget_are_not_success(tmp_path):
    client, app = prepared(tmp_path)
    atom = ATOM.replace(b"Synthetic ScholarGraph Study", b"Synthetic Graph Study")
    app.state.arxiv_fetcher.client = ArxivClient(app.state.repository.gate, transport=httpx.MockTransport(
        lambda request: httpx.Response(200, content=atom if request.url.path == "/api/query" else b"invalid PDF")), interval=0)
    result = client.post("/api/v1/retrieval/tracking/run", json={"paper_ids": ["paper-graph-a"]}).json()
    assert result["status"] == "partial" and result["failed_count"] == 1
    assert result["candidates"][0]["import"]["parse_status"]["status"] == "failed"
    deferred = client.post("/api/v1/retrieval/tracking/run", json={"paper_ids": ["paper-graph-a"], "max_imports": 0}).json()
    assert deferred["candidate_count"] == 1 and deferred["candidates"][0]["outcome"] == "deferred"
    assert len(app.state.repository.papers()) == 4


def test_interrupted_run_is_closed_and_missing_seed_does_not_disappear(tmp_path):
    client, app = prepared(tmp_path)
    app.state.tracking.state.run({"run_id": "old", "started_at": "2020-01-01T00:00:00+00:00", "status": "running"})
    result = client.post("/api/v1/retrieval/tracking/run", json={"paper_ids": ["missing"]}).json()
    assert result["status"] == "failed" and result["errors"][0]["error_code"] == "PAPER_NOT_FOUND"
    with app.state.tracking.state.connect() as db:
        old = json.loads(db.execute("SELECT payload FROM runs WHERE id='old'").fetchone()[0])
    assert old["status"] == "interrupted"
