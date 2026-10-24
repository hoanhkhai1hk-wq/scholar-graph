import copy
import json

import httpx
import pytest

from sample_pdfs import make_pdf
from scholar_graph.errors import PipelineError
from scholar_graph.grobid import GrobidClient
from scholar_graph.normalize import citation_links
from scholar_graph.pipeline import Pipeline
from scholar_graph.storage import RecordStore
from scholar_graph.validation import ContractGate
from test_validation_status import example_bundle


def test_actual_mineru_local_text_pdf(tmp_path):
    source = make_pdf(tmp_path / "v1.pdf")
    pipeline = Pipeline(tmp_path / "output")
    bundle = pipeline.parse(source)
    assert bundle["paper_meta"]["version"] == "v1"
    assert bundle["paper_meta"]["doi"] == "10.5555/scholar-synthetic"
    assert bundle["paper_meta"]["page_count"] == 2
    assert bundle["paper_meta"]["has_text_layer"] is True
    assert len(bundle["reference_entries"]) == len(bundle["citation_links"]) == 1
    assert bundle["reference_entries"][0]["doi"] == "10.5555/prior"
    assert {chunk["page_number"] for chunk in bundle["chunks"]} == {1, 2}
    assert pipeline.store.load(pipeline.last_output) == bundle
    assert pipeline.last_job.current["status"] == "completed"
    assert "ocr" not in [row["status"] for row in pipeline.last_job.history]
    # Exact re-upload returns the immutable group, without creating a duplicate paper.
    assert pipeline.parse(source) == bundle
    assert len(list((tmp_path / "output" / "papers").iterdir())) == 1


def test_mineru_preserves_physical_page_after_blank_cover(tmp_path):
    source = make_pdf(tmp_path / "cover.pdf", blank_cover=True)
    bundle = Pipeline(tmp_path / "output").parse(source)
    assert bundle["paper_meta"]["page_count"] == 3
    assert min(chunk["page_number"] for chunk in bundle["chunks"]) == 2
    assert max(chunk["page_number"] for chunk in bundle["chunks"]) == 3


def test_no_partial_paper_for_invalid_contract_output(tmp_path):
    store = RecordStore(tmp_path / "never-created", ContractGate())
    invalid = example_bundle()
    invalid["chunks"][0]["extra"] = True
    with pytest.raises(PipelineError):
        store.paper(invalid)
    assert not store.root.exists()


def test_atomic_write_failure_does_not_publish_group(tmp_path, monkeypatch):
    import scholar_graph.storage as storage
    store = RecordStore(tmp_path / "output", ContractGate())
    def fail(*args):
        raise OSError("synthetic disk failure")
    monkeypatch.setattr(storage, "write_json", fail)
    with pytest.raises(OSError):
        store.paper(example_bundle())
    assert list((store.root / "papers").iterdir()) == []


@pytest.mark.parametrize("kind", ["malformed", "encrypted"])
def test_unreadable_pdf_fails_with_contract_status(tmp_path, kind):
    source = tmp_path / "bad.pdf"
    if kind == "malformed":
        source.write_bytes(b"%PDF-invalid")
    else:
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(612, 792)
        writer.encrypt("not-a-real-secret")
        writer.write(source)
    pipeline = Pipeline(tmp_path / "output")
    with pytest.raises(PipelineError):
        pipeline.parse(source)
    status = pipeline.last_job.current
    assert status["status"] == "failed" and status["progress"] < 100
    assert status["error_code"] == "PARSE_FAILED" and status["error_message"]
    assert not (pipeline.store.root / "papers").exists()


def test_ocr_failure_is_explicit_and_does_not_publish(tmp_path):
    class Engines:
        def text(self, path):
            return {"schema": "docvortex.middle", "is_full_document": True, "pages": [{"page_idx": 0}]}
        def ocr(self, path, pages):
            assert pages == [0]
            raise PipelineError("OCR_FAILED", "自制 OCR 故障注入")
    pipeline = Pipeline(tmp_path / "output", engines=Engines())
    with pytest.raises(PipelineError, match="自制 OCR"):
        pipeline.parse(make_pdf(tmp_path / "scan.pdf", scan=True))
    states = [record["status"] for record in pipeline.last_job.history]
    assert "ocr" in states and states[-1] == "failed"
    assert not (pipeline.store.root / "papers").exists()


@pytest.mark.parametrize("response", [
    {"schema": "docvortex.middle", "is_full_document": False, "pages": [{"page_idx": 0}, {"page_idx": 1}]},
    {"schema": "docvortex.middle", "is_full_document": True, "pages": [{"page_idx": 0}]},
    {"schema": "docvortex.middle", "is_full_document": True, "pages": [{"page_idx": 0}, {"page_idx": 0}]},
])
def test_truncated_or_duplicate_physical_pages_are_rejected(tmp_path, response):
    class Engines:
        def text(self, path):
            return response
    pipeline = Pipeline(tmp_path / "output", engines=Engines())
    with pytest.raises(PipelineError) as caught:
        pipeline.parse(make_pdf(tmp_path / "source.pdf"))
    assert caught.value.code == "PARSE_FAILED"
    assert pipeline.last_job.current["status"] == "failed"
    assert not (pipeline.store.root / "papers").exists()


@pytest.mark.ocr
def test_actual_paddleocr_scanned_pdf(tmp_path):
    pipeline = Pipeline(tmp_path / "output")
    bundle = pipeline.parse(make_pdf(tmp_path / "scan.pdf", scan=True))
    assert bundle["paper_meta"]["has_text_layer"] is False
    assert bundle["reference_entries"] == bundle["citation_links"] == []
    assert any("12 samples" in chunk["text"] for chunk in bundle["chunks"])
    assert "ocr" in [row["status"] for row in pipeline.last_job.history]
    assert pipeline.last_job.current["status"] == "completed"
    ContractGate().bundle(pipeline.store.load(pipeline.last_output))


def test_reference_markers_group_ranges_and_unknown_ids():
    bundle = example_bundle()
    chunk = bundle["chunks"][0]
    chunk["text"] = "Citations [1, 2] and [1-3] repeat [1] and unknown [99]."
    refs = [bundle["reference_entries"][0]]
    refs.append({**refs[0], "number": 2, "ref_id": "ref-two"})
    links = citation_links([chunk], refs)
    assert [row["citation_number"] for row in links] == [1, 2]


def test_grobid_http_tei_adapter_mock_is_not_live_service():
    tei = b'''<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc>
      <titleStmt><title>Mock service title</title></titleStmt></fileDesc></teiHeader>
      <text><back><listBibl><biblStruct n="1"><analytic><title>Prior Mock Study</title></analytic>
      <monogr><title>Mock Proceedings</title><imprint><date when="2025"/></imprint></monogr>
      <idno type="DOI">https://doi.org/10.5555/prior</idno></biblStruct></listBibl></back></text></TEI>'''
    def handle(request):
        assert request.url.path == "/api/processFulltextDocument"
        assert b"consolidateHeader" in request.content and b"source.pdf" in request.content
        return httpx.Response(200, content=tei)
    bundle = GrobidClient("http://127.0.0.1:8070", transport=httpx.MockTransport(handle)).enrich(example_bundle(), b"%PDF-test")
    ContractGate().bundle(bundle)
    assert bundle["paper_meta"]["title"] == "Mock service title"
    assert bundle["reference_entries"][0]["title"] == "Prior Mock Study"


def test_grobid_failure_does_not_expose_transport_exception():
    def handle(request):
        raise httpx.ConnectError("sensitive-provider-detail", request=request)
    client = GrobidClient("http://127.0.0.1:8070", transport=httpx.MockTransport(handle))
    with pytest.raises(PipelineError) as caught:
        client.enrich(example_bundle(), b"%PDF-test")
    assert caught.value.code == "UPSTREAM_ERROR"
    assert "sensitive-provider-detail" not in str(caught.value)
