"""Local BGE-M3 paper vectors; deterministic sampling, cache and cosine math."""

import hashlib
import json
import math
import os
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path

from .vector_search import MODEL_REVISION
from .retrieval import VectorUnavailable

REPRESENTATION = "paper-body-8x2000chars-512tokens-mean-unit-v1"


def representative_chunks(bundle):
    body = [c for c in bundle["chunks"] if c["type"] == "text" and len(c["text"].strip()) >= 80 and
            not any(part.casefold().strip() in {"references", "bibliography", "参考文献"} for part in c["section_path"])]
    if not body:
        body = [c for c in bundle["chunks"] if c["type"] == "text" and c["text"].strip()]
    if not body:
        raise VectorUnavailable("NO_REPRESENTATIVE_TEXT")
    selected = []
    for pattern in ("abstract", "introduction", "conclusion"):
        match = next((c for c in body if any(pattern in part.casefold() for part in c["section_path"])), None)
        if match and match not in selected:
            selected.append(match)
    for n in range(8):
        chunk = body[round(n * (len(body) - 1) / 7)]
        if chunk not in selected:
            selected.append(chunk)
        if len(selected) >= 8:
            break
    # Return original order so section priorities never become a hidden ordering signal.
    ids = {c["chunk_id"] for c in selected}
    return [c for c in body if c["chunk_id"] in ids][:8]


def unit(vector):
    if not isinstance(vector, list) or not vector or any(type(x) not in (int, float) or not math.isfinite(x) for x in vector):
        raise VectorUnavailable("INVALID_VECTOR")
    norm = math.sqrt(sum(x * x for x in vector))
    if not math.isfinite(norm) or norm <= 0:
        raise VectorUnavailable("ZERO_VECTOR")
    return [x / norm for x in vector]


def cosine(left, right):
    if len(left) != len(right):
        raise VectorUnavailable("DIMENSION_MISMATCH")
    left, right = unit(left), unit(right)
    return max(-1.0, min(1.0, sum(x * y for x, y in zip(left, right, strict=True))))


def calibrate(positive, negative):
    if len(positive) < 3 or len(negative) < 3 or any(not math.isfinite(x) or not -1 <= x <= 1 for x in positive + negative):
        raise ValueError("need finite scores and at least three pairs per class")
    lower, upper = max(negative), min(positive)
    if lower >= upper:
        raise ValueError("calibration classes overlap; automatic duplicate policy is unavailable")
    # Split the observed separation into three equal margins. Neither label boundary
    # sits on a training example; unseen scores in the middle require human review.
    return {"review_threshold": lower + (upper - lower) / 3,
            "duplicate_threshold": lower + 2 * (upper - lower) / 3,
            "negative_max": lower, "positive_min": upper,
            "positive_pairs": len(positive), "negative_pairs": len(negative)}


def band(score, policy):
    if not math.isfinite(score) or not -1 <= score <= 1:
        raise ValueError("invalid cosine")
    if score >= policy["duplicate_threshold"]:
        return "duplicate"
    return "manual_review" if score >= policy["review_threshold"] else "new_paper"


class BgePaperVectors:
    def __init__(self, root, python, model_path, *, timeout=240):
        self.root, self.python, self.model_path = Path(root), Path(python), Path(model_path)
        self.timeout = timeout
        self.last_metadata = None

    def encode(self, bundles):
        if not self.python.is_file() or not (self.model_path / "pytorch_model.bin").is_file():
            raise VectorUnavailable("LOCAL_MODEL_NOT_CONFIGURED")
        selected = [representative_chunks(bundle) for bundle in bundles]
        documents = [{"id": bundle["paper_meta"]["id"], "texts": [c["text"][:2000] for c in chunks]}
                     for bundle, chunks in zip(bundles, selected, strict=True)]
        keys = [hashlib.sha256(json.dumps([MODEL_REVISION, REPRESENTATION, doc["texts"]], ensure_ascii=False).encode()).hexdigest() for doc in documents]
        parent = self.root / "semantic-dedup"
        parent.mkdir(parents=True, exist_ok=True)
        vectors, fresh = {}, []
        with closing(sqlite3.connect(parent / "vectors.sqlite3", timeout=30)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS vectors (fingerprint TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            for doc, key in zip(documents, keys, strict=True):
                row = db.execute("SELECT payload FROM vectors WHERE fingerprint=?", (key,)).fetchone()
                if row:
                    value = json.loads(row[0])
                    vector = unit(value["vector"])
                    if len(vector) != 1024 or value.get("revision") != MODEL_REVISION:
                        raise VectorUnavailable("INVALID_CACHE")
                    vectors[doc["id"]] = vector
                else:
                    fresh.append(doc)
        metadata = {"model": "BAAI/bge-m3", "revision": MODEL_REVISION, "representation": REPRESENTATION,
                    "device": "cpu", "dimension": 1024, "encoded_papers": len(fresh), "cached_papers": len(documents) - len(fresh),
                    "representatives": {doc["id"]: [c["chunk_id"] for c in chunks] for doc, chunks in zip(documents, selected, strict=True)}}
        if fresh:
            env = {k: v for k, v in os.environ.items() if not any(term in k.upper() for term in ("API_KEY", "TOKEN", "SECRET", "PASSWORD"))}
            env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", TOKENIZERS_PARALLELISM="false")
            try:
                result = subprocess.run([str(self.python), str(Path(__file__).with_name("vector_worker.py"))],
                    input=json.dumps({"operation": "paper_embeddings", "model_path": str(self.model_path), "papers": fresh}),
                    capture_output=True, text=True, encoding="utf-8", env=env, timeout=self.timeout,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                if result.returncode:
                    raise VectorUnavailable("LOCAL_WORKER_FAILED")
                output = json.loads(result.stdout)
                if set(output["vectors"]) != {doc["id"] for doc in fresh}:
                    raise VectorUnavailable("WORKER_PAPER_IDS_MISMATCH")
                encoded = {pid: unit(vector) for pid, vector in output["vectors"].items()}
                if any(len(vector) != 1024 for vector in encoded.values()):
                    raise VectorUnavailable("WORKER_DIMENSION_MISMATCH")
                metadata["versions"] = output["versions"]
                with closing(sqlite3.connect(parent / "vectors.sqlite3", timeout=30)) as db, db:
                    for doc, key in zip(documents, keys, strict=True):
                        if doc["id"] in encoded:
                            db.execute("INSERT OR REPLACE INTO vectors VALUES (?,?)", (key, json.dumps({"vector": encoded[doc["id"]], "revision": MODEL_REVISION})))
                vectors.update(encoded)
            except subprocess.TimeoutExpired:
                raise VectorUnavailable("LOCAL_WORKER_TIMEOUT") from None
            except (OSError, ValueError, KeyError, TypeError):
                raise VectorUnavailable("LOCAL_WORKER_PROTOCOL_ERROR") from None
        self.last_metadata = metadata
        return vectors


def encoder_from_environment(root):
    project = Path(__file__).resolve().parents[2]
    return BgePaperVectors(root,
        os.environ.get("SCHOLAR_GRAPH_VECTOR_PYTHON", str(project / "data/module-four-runtime/.venv/Scripts/python.exe")),
        os.environ.get("SCHOLAR_GRAPH_BGE_M3_PATH", str(project / "data/module-four-models/bge-m3")))
