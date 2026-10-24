"""Optional actual BGE-M3 dense+sparse retrieval using an isolated local worker."""

import json
import os
import subprocess
import threading
from pathlib import Path

from .retrieval import VectorUnavailable, fuse_ranks

MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"


class BgeChromaSearch:
    def __init__(self, python, model_path, index_path, *, timeout=240, revision=MODEL_REVISION):
        self.python = Path(python).resolve()
        self.model_path, self.index_path = Path(model_path).resolve(), Path(index_path).resolve()
        self.timeout, self.revision = timeout, revision
        self.lock, self.last_evidence = threading.Lock(), None

    def search(self, chunks, question):
        if not self.python.is_file() or not (self.model_path / "config.json").is_file():
            raise VectorUnavailable
        payload = {"model_path": str(self.model_path), "index_path": str(self.index_path),
                   "revision": self.revision, "chunks": chunks, "question": question}
        env = {key: value for key, value in os.environ.items()
               if not any(term in key.upper() for term in ("API_KEY", "TOKEN", "SECRET", "PASSWORD"))}
        env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
                   ANONYMIZED_TELEMETRY="False", TOKENIZERS_PARALLELISM="false")
        worker = Path(__file__).with_name("vector_worker.py")
        try:
            with self.lock:
                result = subprocess.run([str(self.python), str(worker)], input=json.dumps(payload),
                                        capture_output=True, text=True, encoding="utf-8", env=env,
                                        timeout=self.timeout, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            if result.returncode:
                raise VectorUnavailable
            evidence = json.loads(result.stdout)
            ids = {chunk["chunk_id"] for chunk in chunks}
            if set(evidence["dense"]) != ids or set(evidence["sparse"]) != ids:
                raise VectorUnavailable
            self.last_evidence = evidence
            return fuse_ranks(evidence["dense"], evidence["sparse"])
        except (OSError, subprocess.TimeoutExpired, ValueError, KeyError):
            raise VectorUnavailable from None


def vector_from_environment(root):
    if os.environ.get("SCHOLAR_GRAPH_RETRIEVAL_MODE", "lexical") != "bge_m3_hybrid":
        return None
    return BgeChromaSearch(os.environ.get("SCHOLAR_GRAPH_VECTOR_PYTHON", "missing-vector-python"),
                          os.environ.get("SCHOLAR_GRAPH_BGE_M3_PATH", "missing-bge-m3-model"),
                          Path(root) / "chroma-bge-m3")
