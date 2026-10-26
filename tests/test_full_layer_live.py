"""Acceptance-only real inference and official longbook; never part of fast commits."""
import os
from pathlib import Path
import sys

import pytest

from scholar_graph.pipeline import Pipeline
from scholar_graph.vector_search import BgeChromaSearch
from scholar_graph.chunk_index import ChunkIndex
from test_validation_status import example_bundle

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.real_vector
def test_real_local_bge_m3_dense_sparse_chroma(tmp_path, record_property):
    python = os.environ.get('SCHOLAR_GRAPH_VECTOR_PYTHON') or str(ROOT/'data/module-four-runtime/.venv/Scripts/python.exe')
    model = os.environ.get('SCHOLAR_GRAPH_BGE_M3_PATH') or str(ROOT/'data/module-four-models/bge-m3')
    assert Path(python).is_file(), 'Full layer requires an actual isolated vector Python'
    assert (Path(model)/'config.json').is_file(), 'Full layer requires actual pinned BGE-M3 weights'
    base = example_bundle()['chunks'][0]
    chunks = [{**base, 'chunk_id': 'live-vector-' + str(n), 'text': text} for n, text in enumerate([
        'We train the model with the Adam optimizer and learning rate warmup.',
        'The geographical study measures rainfall in forests.',
        'The encoder and decoder use attention layers.',
        'Our dataset contains twelve labelled examples.',
    ])]
    engine = BgeChromaSearch(python, model, tmp_path/'chroma', timeout=300)
    ranking = engine.search(chunks, 'Which optimizer trains the neural model?')
    assert ranking[0][0] == 'live-vector-0'
    evidence = engine.last_evidence
    assert evidence['dimension'] == 1024 and evidence['indexed_chunks'] == evidence['updated_chunks'] == 4
    assert set(evidence['dense']) == set(evidence['sparse']) == {c['chunk_id'] for c in chunks}
    for key in ('versions', 'timing', 'worker_seconds', 'revision'):
        record_property('actual_vector_' + key, str(evidence[key]))


@pytest.mark.longbook
def test_official_541_page_longbook_full_layer(tmp_path, request, record_property):
    corpus = Path(request.config.getoption('--corpus-dir') or ROOT/'pdf')
    source = corpus/'UnderstandingDeepLearning_02_09_26_C.pdf'
    assert source.is_file(), 'Official longbook required for the full layer'
    pipeline = Pipeline(tmp_path/'longbook')
    result = pipeline.parse(source)
    assert result['paper_meta']['page_count'] == 541 and len(result['chunks']) > 0
    index = ChunkIndex(pipeline.store.root, result['paper_meta']['id'])
    first = index.page(1, 100)
    assert first['total'] == len(result['chunks'])
    last = index.page(first['total_pages'], 100)
    assert max(c['page_number'] for c in last['items']) == 541
    assert pipeline.last_job.current['status'] == 'completed'
    record_property('official_longbook_chunks', len(result['chunks']))
    record_property('official_longbook_indexing_seconds', pipeline.last_metrics['indexing_seconds'])
