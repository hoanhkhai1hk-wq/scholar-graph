"""Self-made Atom/PDF fixtures, not live arXiv acceptance evidence."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from sample_pdfs import make_pdf
from test_arxiv_fetch import fetcher, TITLE
from scholar_graph.tracking_state import TrackingState, operation_lock
from scholar_graph.errors import PipelineError


def test_repeated_arxiv_versions_download_parse_and_publish_only_once(tmp_path):
    service = fetcher(tmp_path, pdf=make_pdf(tmp_path / "source.pdf").read_bytes())
    count = 0
    original = service.client.pdf
    def download(paper):
        nonlocal count
        count += 1
        return original(paper)
    service.client.pdf = download
    first = service.fetch(title=TITLE)
    assert first["succeeded"] and not first["already_present"]
    metadata = dict(first["metadata"], arxiv_id="2601.00001v7", version="v7", id="arxiv-2601.00001v7")
    for _ in range(3):
        second = service.fetch_metadata(metadata)
        assert second["succeeded"] and second["already_present"]
        assert second["paper"]["id"] == first["paper"]["id"]
        assert second["initial_parse_status"] is None
    assert count == 1
    assert len(service.repository.papers()) == 1
    rows = TrackingState(service.repository.root).duplicates()
    assert len(rows) == 1 and rows[0]["occurrences"] == 3 and rows[0]["reason"] == "ARXIV_ID"


def test_doi_exact_match_avoids_new_identity_import(tmp_path):
    service = fetcher(tmp_path, pdf=make_pdf(tmp_path / "source.pdf").read_bytes())
    first = service.fetch(title=TITLE)
    other = dict(first["metadata"], arxiv_id="2601.00002v1", id="arxiv-2601.00002v1")
    service.client.pdf = lambda _: pytest.fail("DOI duplicate must not download")
    duplicate = service.fetch_metadata(other)
    assert duplicate["already_present"] and duplicate["dedup"]["reason"] == "DOI_EXACT"
    assert len(service.repository.papers()) == 1


def test_concurrent_imports_have_one_published_paper(tmp_path):
    service = fetcher(tmp_path, pdf=make_pdf(tmp_path / "source.pdf").read_bytes())
    metadata = service.client.metadata(TITLE)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(service.fetch_metadata, [metadata, metadata]))
    assert all(row["succeeded"] for row in results)
    assert sorted(row["already_present"] for row in results) == [False, True]
    assert len(service.repository.papers()) == 1


def test_operation_locks_fail_explicitly_and_release(tmp_path):
    with operation_lock(tmp_path, "probe"):
        with pytest.raises(PipelineError):
            with operation_lock(tmp_path, "probe"):
                pytest.fail("lock must exclude concurrent operation")
    with operation_lock(tmp_path, "probe"):
        pass


def test_same_public_arxiv_without_job_history_is_real_existing_bundle(tmp_path):
    from graph_samples import graph_bundles
    service = fetcher(tmp_path)
    bundle = graph_bundles()[0]
    bundle["paper_meta"].update(arxiv_id="2601.00001v1")
    service.repository.store.paper(bundle)
    result = service.fetch(title=TITLE)
    assert result["succeeded"] and result["already_present"] and result["parse_status"] is None


def test_unknown_local_identity_uses_existing_dice_and_one_comparison(tmp_path):
    from scholar_graph.pipeline import Pipeline
    source = make_pdf(tmp_path / "source.pdf")
    service = fetcher(tmp_path, pdf=make_pdf(tmp_path / "different.pdf", samples=13).read_bytes())
    def anonymize(paper):
        return {**paper, "title": "Anonymous legacy local document", "authors": [], "doi": None, "arxiv_id": None}
    Pipeline(service.repository.root, metadata_enricher=anonymize).parse(source)
    first = service.fetch(title=TITLE)
    assert first["succeeded"] and first["dedup"]["reason"] == "DOI_OR_TOKEN_DICE"
    assert first["dedup"]["similarity"] >= .9
    second = service.fetch(title=TITLE)
    assert second["already_present"]
    assert len(list((service.repository.root / "comparisons").glob("comparison-*"))) == 1
    assert len(service.state.duplicates()) == 1
