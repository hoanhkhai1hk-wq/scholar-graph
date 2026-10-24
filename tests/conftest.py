import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def pytest_addoption(parser):
    parser.addoption("--run-ocr", action="store_true", help="Run actual PaddleOCR integration; may download models.")


def pytest_configure(config):
    config.addinivalue_line("markers", "ocr: real PaddleOCR integration using a self-made scan")


def pytest_collection_modifyitems(config, items):
    import pytest
    if not config.getoption("--run-ocr"):
        for item in items:
            if "ocr" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="actual OCR requires --run-ocr and optional dependencies"))
