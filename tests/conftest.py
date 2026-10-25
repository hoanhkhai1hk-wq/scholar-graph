import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def pytest_addoption(parser):
    parser.addoption("--run-ocr", action="store_true", help="Run actual PaddleOCR integration; may download models.")
    parser.addoption('--run-real-model', action='store_true', help='Opt in to actual DeepSeek calls using process environment only.')


def pytest_configure(config):
    config.addinivalue_line("markers", "ocr: real PaddleOCR integration using a self-made scan")
    config.addinivalue_line('markers', 'real_model: explicit real DeepSeek call; skip without credentials or opt-in')


def pytest_collection_modifyitems(config, items):
    import pytest
    import os
    for item in items:
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
    if 'real_model' not in request.keywords:
        monkeypatch.setenv('SCHOLAR_GRAPH_QA_MODE', 'extractive')
