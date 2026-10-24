"""Worker protocol tests use mocks, not proof of actual BGE-M3 encoding."""

import json
import subprocess
from types import SimpleNamespace
import pytest
from scholar_graph.vector_search import BgeChromaSearch, vector_from_environment
from scholar_graph.retrieval import VectorUnavailable


def configured(tmp_path):
    python, model = tmp_path / "python.exe", tmp_path / "model"
    python.touch()
    model.mkdir()
    (model / "config.json").write_text("{}")
    return BgeChromaSearch(python, model, tmp_path / "index")


def test_dense_and_sparse_protocol_and_worker_secret_isolation(tmp_path, monkeypatch):
    service = configured(tmp_path)
    monkeypatch.setenv("SYNTHETIC_API_KEY", "synthetic-not-real")
    def run(args, **kwargs):
        assert "SYNTHETIC_API_KEY" not in kwargs["env"]
        assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        payload = json.loads(kwargs["input"])
        assert payload["chunks"] == [{"chunk_id": "a"}, {"chunk_id": "b"}]
        return SimpleNamespace(returncode=0, stdout=json.dumps({"dense": {"a": .9, "b": .8}, "sparse": {"a": 0, "b": 2}}))
    monkeypatch.setattr(subprocess, "run", run)
    assert service.search([{"chunk_id": "a"}, {"chunk_id": "b"}], "question")[0][0] == "b"


@pytest.mark.parametrize("mode", ["timeout", "exit", "garbage", "stale_ids"])
def test_worker_failure_and_stale_index_never_fake_success(tmp_path, monkeypatch, mode):
    service = configured(tmp_path)
    def run(*args, **kwargs):
        if mode == "timeout":
            raise subprocess.TimeoutExpired("worker", 240)
        output = "garbage" if mode == "garbage" else json.dumps({"dense": {"stale": 1}, "sparse": {"stale": 1}})
        return SimpleNamespace(returncode=1 if mode == "exit" else 0, stdout=output)
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(VectorUnavailable):
        service.search([{"chunk_id": "a"}], "question")


def test_vector_is_explicitly_opt_in_and_missing_model_falls_back(tmp_path, monkeypatch):
    monkeypatch.delenv("SCHOLAR_GRAPH_RETRIEVAL_MODE", raising=False)
    assert vector_from_environment(tmp_path) is None
    monkeypatch.setenv("SCHOLAR_GRAPH_RETRIEVAL_MODE", "bge_m3_hybrid")
    with pytest.raises(VectorUnavailable):
        vector_from_environment(tmp_path).search([{"chunk_id": "a"}], "question")
