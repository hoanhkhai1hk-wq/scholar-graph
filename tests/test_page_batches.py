"""Deterministic fault injection for page limits, durable OCR and bounded native batches."""
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from sample_pdfs import make_pdf
from scholar_graph.api import create_app
from scholar_graph.adapters import LocalEngines
from scholar_graph.batching import ParseLimits
from scholar_graph.errors import PipelineError
from scholar_graph.pipeline import Pipeline
from scholar_graph.api_repository import ApiRepository
from scholar_graph.validation import ContractGate


def native_pages(path, count):
    doc = canvas.Canvas(str(path))
    for n in range(count):
        doc.drawString(40, 700, f'Physical page {n + 1} contains real test text.')
        doc.showPage()
    doc.save()
    return path


class Pages(LocalEngines):
    def __init__(self, root):
        super().__init__(cache_dir=root / 'models')
        self.fail = set()
        self.text_sizes = []
        self.ocr_calls = []
        self.before_ocr = None

    def text(self, path, *, timeout=None):
        with path.open('rb') as handle:
            count = len(PdfReader(handle).pages)
        self.text_sizes.append(count)
        return {'schema': 'docvortex.middle', 'is_full_document': True, 'pages': [
            {'page_idx': n, 'blocks': [{'type': 'text', 'content': f'Native batch page {n + 1}.'}]} for n in range(count)]}

    def ocr(self, path, pages, *, timeout=None):
        assert len(pages) == 1 and 0 < timeout <= 90
        n = pages[0]
        self.ocr_calls.append(n)
        if self.before_ocr:
            self.before_ocr(n)
        if n in self.fail:
            raise PipelineError('OCR_FAILED', '故障注入：此页超时。')
        return {'pages': [{'page_idx': n, 'blocks': [{'type': 'text', 'content': f'OCR physical page {n + 1} has 12 samples.'}]}]}


def test_ocr_failure_preserves_successful_pages_and_retry_resumes(tmp_path):
    one = make_pdf(tmp_path / 'one.pdf', scan=True)
    source = tmp_path / 'three.pdf'
    writer = PdfWriter()
    with one.open('rb') as handle:
        reader = PdfReader(handle)
        for _ in range(3):
            writer.add_page(reader.pages[0])
        writer.write(source)
    root = tmp_path / 'records'
    engine = Pages(root)
    engine.fail = {1}
    pipeline = Pipeline(root, engines=engine)
    client = TestClient(create_app(data_dir=root, pipeline_factory=lambda: pipeline))
    pid = 'paper-' + hashlib.sha256(source.read_bytes()).hexdigest()
    observations = []

    def observe(n):
        if n == 1:
            current = client.get(f'/api/v1/papers/{pid}/chunks')
            observations.append(current.json()['total'])
            assert client.get(f'/api/v1/papers/{pid}/parse-status').json()['status'] == 'ocr'
    engine.before_ocr = observe
    response = client.post('/api/v1/papers', files={'file': ('three.pdf', source.read_bytes(), 'application/pdf')})
    assert observations == [1]
    assert response.status_code == 422
    assert response.json()['details']['failed_pages'] == '2'
    assert response.json()['details']['published_chunks'] == 2
    assert '2' in response.json()['message']
    chunks = client.get(f'/api/v1/papers/{pid}/chunks').json()['items']
    assert {c['page_number'] for c in chunks} == {1, 3}
    assert not (root / 'papers' / pid).exists()  # Partial data never masquerades as completed.
    engine.fail.clear()
    engine.before_ocr = None
    value = pipeline.parse(source)
    assert len(value['chunks']) == 3 and len({c['chunk_id'] for c in value['chunks']}) == 3
    assert [c['page_number'] for c in value['chunks']] == [1, 2, 3]
    assert engine.ocr_calls == [0, 1, 2, 1]
    assert pipeline.last_metrics['resumed_pages'] == 2
    assert pipeline.last_job.current['status'] == 'completed'


def test_long_document_batches_indexes_and_paginates_after_200(tmp_path):
    source = native_pages(tmp_path / 'long.pdf', 201)
    engine = Pages(tmp_path / 'records')
    pipeline = Pipeline(tmp_path / 'records', engines=engine)
    value = pipeline.parse(source)
    assert max(engine.text_sizes) <= 32 and len(engine.text_sizes) == 7
    assert {c['page_number'] for c in value['chunks']} == set(range(1, 202))
    assert pipeline.last_job.current['status'] == 'completed'
    assert pipeline.last_metrics['indexing_seconds'] > 0
    repo = ApiRepository(tmp_path / 'records', ContractGate())
    pid = value['paper_meta']['id']
    page = repo.chunk_page(pid, 3, 100)
    assert page['total'] == 201 and page['items'][0]['page_number'] == 201 and not page['has_next']
    assert repo.chunk_page(pid, 99, 100)['items'] == []
    assert len(repo.chunk_page(pid, 1, 999)['items']) == 100
    assert any('已发布' in status['current_stage'] for status in pipeline.last_job.history)


def test_configured_page_limit_is_explicit_and_default_covers_541(tmp_path, monkeypatch):
    assert ParseLimits.environment().max_pages >= 541
    monkeypatch.setenv('SCHOLAR_GRAPH_MAX_PAGES', '10')
    pipeline = Pipeline(tmp_path / 'records')
    with pytest.raises(PipelineError, match='10'):
        pipeline.parse(native_pages(tmp_path / 'too-many.pdf', 11))
    assert pipeline.last_job.current['status'] == 'failed'


def test_native_batch_timeout_uses_real_fallback_interface(tmp_path):
    engine = Pages(tmp_path / 'records')
    def fail(path, *, timeout=None):
        raise PipelineError('PARSE_FAILED', '故障注入：MinerU超时')
    engine.text = fail
    pipeline = Pipeline(tmp_path / 'records', engines=engine, limits=ParseLimits(text_batch_pages=1))
    value = pipeline.parse(native_pages(tmp_path / 'two.pdf', 2))
    assert engine.ocr_calls == [0, 1]
    assert len(value['chunks']) == 2
    assert 'ocr' in [s['status'] for s in pipeline.last_job.history]


def test_whole_document_deadline_names_unattempted_pages(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from scholar_graph import batching
    clock = [0.0]
    monkeypatch.setattr(batching, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    engine = Pages(tmp_path / 'records')
    engine.text = lambda path, **kwargs: (_ for _ in ()).throw(PipelineError('PARSE_FAILED', '故障注入'))
    original = engine.ocr
    def slow(path, pages, **kwargs):
        value = original(path, pages, **kwargs)
        clock[0] = 2.0
        return value
    engine.ocr = slow
    pipeline = Pipeline(tmp_path / 'records', engines=engine,
                        limits=ParseLimits(text_batch_pages=1, total_timeout=1))
    with pytest.raises(PipelineError) as error:
        pipeline.parse(native_pages(tmp_path / 'bounded.pdf', 3))
    assert error.value.details['failed_pages'] == '2,3'
    assert pipeline.last_metrics['published_chunks'] == 1
    assert pipeline.last_job.current['status'] == 'failed'


def test_crash_after_batch_rename_rebuilds_index_and_resumes(tmp_path, monkeypatch):
    from scholar_graph.chunk_index import ChunkIndex
    root = tmp_path / 'records'
    source = native_pages(tmp_path / 'crash.pdf', 3)
    engine = Pages(root)
    pipeline = Pipeline(root, engines=engine, limits=ParseLimits(text_batch_pages=1))
    original = ChunkIndex.append
    with monkeypatch.context() as patch:
        patch.setattr(ChunkIndex, 'append', lambda *a, **kw: (_ for _ in ()).throw(OSError('injected index failure')))
        with pytest.raises(PipelineError):
            pipeline.parse(source)
    pid = 'paper-' + hashlib.sha256(source.read_bytes()).hexdigest()
    assert len(pipeline.store.partial(pid)['chunks']) == 1
    value = pipeline.parse(source)
    assert len(value['chunks']) == 3
    assert pipeline.last_metrics['resumed_pages'] == 1
    assert ChunkIndex(root, pid).page(1, 100)['total'] == 3
