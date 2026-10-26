"""Mocked isolated-worker protocol and cache; not a claim of real model execution."""
import json
import subprocess
from types import SimpleNamespace

import pytest

from scholar_graph.semantic_vectors import BgePaperVectors
from scholar_graph.retrieval import VectorUnavailable
from test_dedup import versions


def configured(tmp_path):
    python = tmp_path / "python.exe"
    python.touch()
    model = tmp_path / "model"
    model.mkdir()
    (model / "pytorch_model.bin").touch()
    return BgePaperVectors(tmp_path / "records", python, model)


def test_worker_is_offline_secret_free_and_cache_reuses_real_result(tmp_path, monkeypatch):
    service = configured(tmp_path)
    monkeypatch.setenv("SYNTHETIC_API_KEY", "synthetic-only")
    bundle, _ = versions()
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        assert "SYNTHETIC_API_KEY" not in kwargs["env"]
        assert kwargs["env"]["HF_HUB_OFFLINE"] == kwargs["env"]["TRANSFORMERS_OFFLINE"] == "1"
        payload = json.loads(kwargs["input"])
        assert payload["operation"] == "paper_embeddings"
        assert all(len(text) <= 2000 for paper in payload["papers"] for text in paper["texts"])
        return SimpleNamespace(returncode=0, stdout=json.dumps({"vectors": {bundle["paper_meta"]["id"]: [1.0] + [0.0]*1023}, "versions": {"test": "fake"}}))
    monkeypatch.setattr(subprocess, "run", run)
    first = service.encode([bundle])
    assert service.encode([bundle]) == first and len(calls) == 1
    assert service.last_metadata["cached_papers"] == 1


@pytest.mark.parametrize("mode", ["wrong_ids", "dimension", "nan", "zero", "timeout", "exit", "garbage"])
def test_worker_failure_is_not_a_semantic_score(tmp_path, monkeypatch, mode):
    service = configured(tmp_path)
    bundle, _ = versions()
    def run(*args, **kwargs):
        if mode == "timeout":
            raise subprocess.TimeoutExpired("worker", 240)
        vector = [float("nan")] * 1024 if mode == "nan" else [0]*1024 if mode == "zero" else [1] if mode == "dimension" else [1]*1024
        return SimpleNamespace(returncode=1 if mode == "exit" else 0,
            stdout="garbage" if mode == "garbage" else json.dumps({"vectors": {"wrong" if mode == "wrong_ids" else bundle["paper_meta"]["id"]: vector}, "versions": {}}))
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(VectorUnavailable):
        service.encode([bundle])
