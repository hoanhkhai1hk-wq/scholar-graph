"""Synthetic Atom/PDF inputs; network is mocked, existing local MinerU is real."""

import json
import httpx
import pytest

from sample_pdfs import make_pdf
from scholar_graph.api_repository import ApiRepository
from scholar_graph.arxiv_fetch import ArxivClient, ArxivFetcher
from scholar_graph.errors import PipelineError
from scholar_graph.pipeline import Pipeline
from scholar_graph.validation import ContractGate

TITLE = "Synthetic ScholarGraph Study"
ATOM = b'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
<entry><id>http://arxiv.org/abs/2601.00001v1</id><title>Synthetic ScholarGraph Study</title>
<published>2026-01-01T00:00:00Z</published><summary>Synthetic test metadata, not a real arXiv entry.</summary>
<author><name>Demo Author</name><arxiv:affiliation>Synthetic Institute</arxiv:affiliation></author>
<arxiv:doi>https://doi.org/10.5555/scholar-synthetic</arxiv:doi></entry></feed>'''


def fetcher(tmp_path, *, atom=ATOM, pdf=b"not a PDF", status=200, pdf_status=200):
    repository = ApiRepository(tmp_path / "output", ContractGate())
    def handle(request):
        if request.url.path == "/api/query":
            return httpx.Response(status, content=atom)
        assert request.url.host == "arxiv.org" and request.url.path == "/pdf/2601.00001v1"
        return httpx.Response(pdf_status, content=pdf)
    client = ArxivClient(repository.gate, transport=httpx.MockTransport(handle), interval=0)
    return ArxivFetcher(repository, client=client)


def test_actual_existing_mineru_pipeline_receives_public_metadata(tmp_path):
    service = fetcher(tmp_path, pdf=make_pdf(tmp_path / "source.pdf").read_bytes())
    result = service.fetch(title=TITLE)
    assert result["succeeded"] and result["error"] is None
    assert result["initial_parse_status"]["status"] == "queued"
    assert result["initial_parse_status"]["progress"] == 0
    assert result["parse_status"]["status"] == "completed"
    paper = result["paper"]
    assert paper["id"].startswith("paper-") and paper["page_count"] == 2
    assert paper["arxiv_id"] == "2601.00001v1" and paper["doi"] == "10.5555/scholar-synthetic"
    assert paper["institutions"] == ["Synthetic Institute"]
    bundle = service.repository.paper(paper["id"])
    assert len(bundle["chunks"]) > 0
    assert len(bundle["reference_entries"]) == len(bundle["citation_links"]) == 1
    assert result["metadata"]["id"] != paper["id"]
    path = service.repository.root / "catalog" / result["metadata"]["id"] / "paper-meta.json"
    assert json.loads(path.read_text(encoding="utf-8")) == result["metadata"]


@pytest.mark.parametrize("kwargs,code", [
    ({"status": 503}, "UPSTREAM_ERROR"),
    ({"atom": b'<feed xmlns="http://www.w3.org/2005/Atom"/>'}, "PAPER_NOT_FOUND"),
    ({"atom": ATOM.replace(b"Synthetic ScholarGraph Study", b"Different title")}, "PAPER_NOT_FOUND"),
    ({"atom": b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///D:/private">]><feed>&x;</feed>'}, "UPSTREAM_ERROR"),
])
def test_metadata_failure_never_fabricates_paper(tmp_path, kwargs, code):
    service = fetcher(tmp_path, **kwargs)
    result = service.fetch(title=TITLE)
    assert not result["succeeded"] and result["error"]["error_code"] == code
    assert set(result["error"]) == {"error_code", "message", "details"}
    assert result["paper"] is result["metadata"] is result["parse_status"] is None
    assert service.repository.papers() == []


def test_pdf_download_failure_retains_only_real_catalog_metadata(tmp_path):
    service = fetcher(tmp_path, pdf_status=403)
    result = service.fetch(title=TITLE)
    assert not result["succeeded"] and result["metadata"]["title"] == TITLE
    assert result["parse_status"] is result["initial_parse_status"] is None
    assert result["error"]["error_code"] == "UPSTREAM_ERROR"
    assert service.repository.papers() == []


def test_bad_pdf_uses_existing_failed_parse_status(tmp_path):
    service = fetcher(tmp_path)
    result = service.fetch(title=TITLE)
    assert result["initial_parse_status"]["status"] == "queued"
    assert result["parse_status"]["status"] == "failed"
    assert result["parse_status"]["error_code"] == result["error"]["error_code"] == "PARSE_FAILED"
    assert result["paper"] is None and service.repository.papers() == []


def test_reference_lookup_uses_verified_identifier(tmp_path):
    service = fetcher(tmp_path)
    # Use the frozen example and change only synthetic values in memory.
    from test_validation_status import example_bundle
    reference = example_bundle()["reference_entries"][0].copy()
    reference.update(arxiv_id="2601.00001v1", doi=None)
    assert service.fetch(reference=reference)["metadata"]["arxiv_id"] == reference["arxiv_id"]
    reference["arxiv_id"] = "../private"
    assert service.fetch(reference=reference)["error"]["error_code"] == "VALIDATION_ERROR"


def test_redirect_to_non_public_arxiv_host_is_rejected(tmp_path):
    client = ArxivClient(ContractGate(), transport=httpx.MockTransport(
        lambda request: httpx.Response(302, headers={"location": "https://evil.invalid/private"})), interval=0)
    with pytest.raises(PipelineError) as caught:
        client.metadata(title=TITLE)
    assert caught.value.code == "UPSTREAM_ERROR"


def test_metadata_enrichment_cannot_change_actual_file_identity(tmp_path):
    pipeline = Pipeline(tmp_path / "output", metadata_enricher=lambda paper: {**paper, "id": "fake"})
    with pytest.raises(PipelineError) as caught:
        pipeline.parse(make_pdf(tmp_path / "source.pdf"))
    assert caught.value.code == "VALIDATION_ERROR"
    assert pipeline.last_job.current["status"] == "failed"
    assert not (tmp_path / "output" / "papers").exists()
