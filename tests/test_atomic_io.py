import os

import pytest

from scholar_graph.atomic_io import BACKOFF, windows_retry
from scholar_graph.storage import RecordStore
from scholar_graph.validation import ContractGate
from test_validation_status import example_bundle
from storage_lock_probe import probe


def winerror(code):
    error = OSError("controlled filesystem error")
    error.winerror = code
    return error


@pytest.mark.skipif(os.name != "nt", reason="Windows error/backoff semantics")
@pytest.mark.parametrize("code", [5, 32, 33])
def test_transient_lock_retries_with_backoff(monkeypatch, code):
    attempts, sleeps = [], []
    monkeypatch.setattr("scholar_graph.atomic_io.time.sleep", sleeps.append)
    def operation():
        attempts.append(True)
        if len(attempts) <= 3:
            raise winerror(code)
        return "published"
    assert windows_retry(operation) == "published"
    assert sleeps == list(BACKOFF[:3]) and len(attempts) == 4


@pytest.mark.skipif(os.name != "nt", reason="Windows error/backoff semantics")
def test_permanent_access_error_is_not_swallowed(monkeypatch, tmp_path):
    from pathlib import Path
    attempts = []
    monkeypatch.setattr("scholar_graph.atomic_io.time.sleep", lambda delay: None)
    def denied(*args):
        attempts.append(True)
        raise winerror(5)
    monkeypatch.setattr(Path, "rename", denied)
    store = RecordStore(tmp_path, ContractGate())
    with pytest.raises(OSError):
        store.paper(example_bundle())
    assert len(attempts) == 8
    assert list((tmp_path / "papers").iterdir()) == []  # No partial public record or leaked staging.


@pytest.mark.parametrize("code", [2, 17, 183])
def test_missing_or_existing_path_is_not_retried(monkeypatch, code):
    def sleep(delay):
        pytest.fail("Non-lock errors must not be retried")
    monkeypatch.setattr("scholar_graph.atomic_io.time.sleep", sleep)
    with pytest.raises(OSError):
        windows_retry(lambda: (_ for _ in ()).throw(winerror(code)))


@pytest.mark.skipif(os.name != "nt", reason="Real native Windows handle test")
def test_real_directory_lock_blocks_native_rename_then_releases(tmp_path):
    result = probe(tmp_path / "controlled-lock")
    assert result["native_without_retry"]["winerror"] in {5, 32, 33}
    assert result["retry_error_codes"] and result["published_complete"]
