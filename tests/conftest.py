import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def pytest_addoption(parser):
    parser.addoption('--layer', choices=('fast', 'full'), default='full')
    parser.addoption('--run-vector', action='store_true', help='Actual local BGE-M3/Chroma inference; missing model is a failure.')
    parser.addoption('--run-longbook', action='store_true', help='Actual official 541-page PDF parse/index.')
    parser.addoption('--corpus-dir', default=None)
    parser.addoption("--run-ocr", action="store_true", help="Run actual PaddleOCR integration; may download models.")
    parser.addoption('--run-real-model', action='store_true', help='Opt in to actual DeepSeek calls using process environment only.')


def pytest_configure(config):
    config.addinivalue_line('markers', 'real_vector: actual local BGE-M3 dense+sparse inference')
    config.addinivalue_line('markers', 'longbook: official 541-page PDF parse/index')
    config.addinivalue_line("markers", "ocr: real PaddleOCR integration using a self-made scan")
    config.addinivalue_line('markers', 'real_model: explicit real DeepSeek call; skip without credentials or opt-in')


def pytest_collection_modifyitems(config, items):
    import pytest
    import os
    from regression_layers import fast_case
    if config.getoption('--layer') == 'fast':
        selected = [item for item in items if fast_case(item)]
        config.hook.pytest_deselected(items=[item for item in items if item not in selected])
        items[:] = selected
    for item in items:
        for marker, option in [('real_vector', '--run-vector'), ('longbook', '--run-longbook')]:
            if marker in item.keywords and not config.getoption(option):
                item.add_marker(pytest.mark.skip(reason=option + ' is required for this acceptance-only case'))
        if 'real_model' in item.keywords and (not config.getoption('--run-real-model') or
                not os.environ.get('DEEPSEEK_API_KEY') or not os.environ.get('DEEPSEEK_MODEL')):
            item.add_marker(pytest.mark.skip(reason='real model disabled or environment credentials unset; never a fabricated live pass'))
    if not config.getoption("--run-ocr"):
        for item in items:
            if "ocr" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="actual OCR requires --run-ocr and optional dependencies"))


import pytest


@pytest.fixture(autouse=True)
def isolate_model_mode(monkeypatch, request):
    # Fast regression tests inject deterministic encoders explicitly. Actual local
    # BGE-M3 official-file acceptance is executed by run_semantic_dedup_acceptance.py.
    monkeypatch.setenv('SCHOLAR_GRAPH_DEDUP_MODE', 'off')
    monkeypatch.setenv('SCHOLAR_GRAPH_QA_RETRIEVAL_MODE', 'lexical')
    monkeypatch.setenv('SCHOLAR_GRAPH_TRACKING_ENABLED', 'false')
    monkeypatch.setenv('SCHOLAR_GRAPH_GROBID_ENABLED','false')
    if 'real_model' not in request.keywords:
        monkeypatch.setenv('SCHOLAR_GRAPH_QA_MODE', 'extractive')
    if request.config.getoption('--layer') == 'fast':
        from scholar_graph.adapters import LocalEngines
        def no_inference(*args, **kwargs):
            raise AssertionError('Fast layer must not invoke parsing/OCR/model workers')
        monkeypatch.setattr(LocalEngines, '_run', no_inference)
