"""QA dual-route recall, bounded local cross-encoder rerank and honest fallback."""
import json
import math
import os
import re
import subprocess
import time
from pathlib import Path
from uuid import uuid4

from .atomic_io import windows_retry
from .errors import PipelineError
from .grounded_model import evidence_candidates, evidence_from_chunks
from .qa_evidence import retrieve as extractive_retrieve
from .retrieval import VectorUnavailable
from .storage import write_json
from .vector_search import BgeChromaSearch
from .rerank_worker import resident_worker, local_environment, WorkerUnavailable


class LocalReranker:
    def __init__(self, root, python, model_path, *, budget_seconds=5, timeout=90, resident=False):
        self.root, self.python, self.path = Path(root), Path(python), Path(model_path)
        self.budget, self.timeout = budget_seconds, timeout
        self.resident = resident

    def order(self, question, chunks):
        policy_path = self.root / "qa-retrieval" / "reranker-policy.json"
        mode = os.environ.get("SCHOLAR_GRAPH_QA_RERANKER", "auto")
        if mode == "rrf":
            return None, {"method": "rrf", "reason": "EXPLICIT_RRF"}
        if mode == "auto" and not self.resident and policy_path.is_file():
            try:
                policy = json.loads(policy_path.read_text(encoding="utf-8"))
                if not isinstance(policy, dict):
                    raise ValueError("invalid policy")
            except (ValueError, OSError):
                return None, {"method": "rrf", "reason": "INVALID_RERANKER_POLICY"}
            if policy.get("reason") == "MEASURED_CPU_BUDGET_EXCEEDED":
                return None, policy
        if not self.python.is_file() or not (self.path / "model.safetensors").is_file():
            return None, {"method": "rrf", "reason": "LOCAL_RERANKER_NOT_CONFIGURED"}
        env = local_environment()
        start = time.perf_counter()
        try:
            payload = {"operation": "rerank", "question": question, "model_path": str(self.path),
                       "items": [{"id": c["chunk_id"], "text": c["text"][:2000]} for c in chunks]}
            worker_info = {}
            if self.resident:
                output, worker_info = resident_worker(self.python, self.path).score(payload, self.budget)
            else:
                result = subprocess.run([str(self.python), str(Path(__file__).with_name("vector_worker.py"))],
                    input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8", env=env, timeout=self.timeout,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                if result.returncode:
                    raise VectorUnavailable
                output = json.loads(result.stdout)
            scores = output["scores"]
            if set(scores) != {c["chunk_id"] for c in chunks} or any(type(s) not in (int, float) or not math.isfinite(s) for s in scores.values()):
                raise VectorUnavailable
            elapsed = time.perf_counter() - start
            info = {"method": "bge-reranker-large", "reason": "OK", "timing": output["timing"],
                    "worker_seconds": elapsed, "candidate_count": len(chunks), "budget_seconds": self.budget,
                    "model": output["model"], "revision": output["revision"], **worker_info}
            # This deployment's per-request extra rerank budget includes cold loading.
            if (self.resident or mode == "auto") and elapsed > self.budget:
                info.update(method="rrf", reason="MEASURED_CPU_BUDGET_EXCEEDED")
                if self.resident:
                    return None, info
                policy_path.parent.mkdir(parents=True, exist_ok=True)
                temporary = policy_path.with_name(uuid4().hex + ".tmp")
                try:
                    write_json(temporary, info)
                    windows_retry(lambda: os.replace(temporary, policy_path))
                finally:
                    temporary.unlink(missing_ok=True)
                return None, info
            return sorted(scores, key=lambda cid: (-scores[cid], cid)), info
        except WorkerUnavailable as error:
            return None, {"method": "rrf", "reason": str(error), "candidate_count": len(chunks),
                          "budget_seconds": self.budget, "elapsed_seconds": time.perf_counter() - start}
        except subprocess.TimeoutExpired:
            return None, {"method": "rrf", "reason": "LOCAL_RERANKER_TIMEOUT", "elapsed_seconds": time.perf_counter() - start}
        except (VectorUnavailable, OSError, ValueError, KeyError, TypeError):
            return None, {"method": "rrf", "reason": "LOCAL_RERANKER_FAILED", "elapsed_seconds": time.perf_counter() - start}


class QAHybridRetriever:
    def __init__(self, repository, vector=None, reranker=None):
        self.repository, self.vector, self.reranker = repository, vector, reranker
        self.calls = []

    def retrieve(self, bundle, question, *, limit=24):
        started = time.perf_counter()
        self.repository.gate.bundle(bundle)
        legacy = evidence_candidates(bundle, question, limit=48)
        lexical = list(dict.fromkeys(item["anchor"]["chunk_id"] for item in legacy))[:24]
        info = {"paper_id": bundle["paper_meta"]["id"], "method": "lexical-fallback", "vector_status": "NOT_CONFIGURED",
                "reason": "LOCAL_VECTOR_NOT_CONFIGURED", "lexical_recalled": len(lexical), "vector_recalled": 0,
                "rerank": {"method": "none"}, "evidence_count": 0}
        candidates = legacy[:limit]
        if self.vector is not None and bundle["chunks"]:
            try:
                self.vector.search(bundle["chunks"], question)
                raw = self.vector.last_evidence
                ids = {c["chunk_id"] for c in bundle["chunks"]}
                dense = raw["dense"]
                if set(dense) != ids or any(type(s) not in (int, float) or not math.isfinite(s) for s in dense.values()):
                    raise VectorUnavailable("INVALID_DENSE_RESULTS")
                vector = sorted(dense, key=lambda cid: (-dense[cid], cid))[:24]
                if not vector:
                    raise VectorUnavailable("EMPTY_DENSE_RESULTS")
                scores = {cid: .5 * 61 / (60 + n) for n, cid in enumerate(vector, 1)}
                for n, cid in enumerate(lexical, 1):
                    scores[cid] = scores.get(cid, 0) + .5 * 61 / (60 + n)
                ordered_ids = sorted(scores, key=lambda cid: (-scores[cid], cid))
                by_id = {c["chunk_id"]: c for c in bundle["chunks"]}
                # Expensive cross-encoding is restricted to the RRF top ten. The
                # remaining recall stays below that prefix for source coverage.
                pool = [by_id[cid] for cid in ordered_ids[:10]]
                reranked, rerank_info = self.reranker.order(question, pool) if self.reranker else (None, {"method": "rrf", "reason": "NOT_CONFIGURED"})
                if reranked is not None:
                    if set(reranked) != set(ordered_ids[:10]) or len(reranked) != len(pool):
                        raise VectorUnavailable("INVALID_RERANK_RESULTS")
                    ordered_ids = reranked + ordered_ids[10:]
                # Preserve the existing explicit page-one author routing; it is source
                # layout coverage, not a fabricated vector score or a new scientific fact.
                if re.search(r"作者|机构|author|affiliation", question, re.I):
                    ordered_ids.sort(key=lambda cid: by_id[cid]["page_number"] != 1)
                candidates = evidence_from_chunks(bundle, [by_id[cid] for cid in ordered_ids], question, limit=limit)
                info.update(method="hybrid" if lexical else "vector", vector_status="READY", reason="OK",
                    vector_recalled=len(vector), union_recalled=len(ordered_ids), rerank=rerank_info,
                    ranking_method="reranked" if reranked is not None else "rrf",
                    vector_timing=raw.get("timing", {}), worker_seconds=raw.get("worker_seconds"),
                    vector_residency=raw.get("residency"),
                    indexed_chunks=raw.get("indexed_chunks"), updated_chunks=raw.get("updated_chunks"),
                    model_revision=raw.get("revision"), versions=raw.get("versions"),
                    fusion={"method": "equal_weight_rrf", "k": 60, "route_limit": 24,
                            "lexical_expansion": "existing_grounded_model_aliases", "bge_sparse_scores_used": False})
            except (VectorUnavailable, KeyError, TypeError, ValueError, OSError):
                info.update(vector_status="UNAVAILABLE", reason="LOCAL_VECTOR_UNAVAILABLE")
                candidates = legacy[:limit]
        for item in candidates:
            self.repository.gate.anchor(item["anchor"], [bundle], quote=item["quote"])
        info.setdefault('ranking_method', 'lexical')
        info['fallback_reason'] = info['reason'] if info['method'] == 'lexical-fallback' else (
            info['rerank'].get('reason') if info['ranking_method'] != 'reranked' else None)
        info.update(evidence_count=len(candidates), elapsed_seconds=round(time.perf_counter() - started, 6))
        self.calls.append(info)
        return candidates, info

    def extractive(self, bundle, question):
        evidence, info = self.retrieve(bundle, question)
        if info["method"] == "lexical-fallback":
            evidence = extractive_retrieve(bundle, question)
            info["evidence_count"] = len(evidence)
        return evidence, info

    def metadata(self):
        methods = {row["method"] for row in self.calls}
        method = "lexical-fallback" if not methods or "lexical-fallback" in methods else "hybrid" if "hybrid" in methods else "vector"
        rankings = sorted({row['ranking_method'] for row in self.calls})
        return {"method": method, "ranking_method": rankings[0] if len(rankings) == 1 else 'mixed' if rankings else 'none',
                "fallback_reasons": list(dict.fromkeys(row['fallback_reason'] for row in self.calls if row['fallback_reason'])),
                "retrieval": list(self.calls)}


def qa_retriever(repository):
    root = Path(__file__).resolve().parents[2]
    python = os.environ.get("SCHOLAR_GRAPH_VECTOR_PYTHON", str(root / "data/module-four-runtime/.venv/Scripts/python.exe"))
    model = os.environ.get("SCHOLAR_GRAPH_BGE_M3_PATH", str(root / "data/module-four-models/bge-m3"))
    vector = None if os.environ.get("SCHOLAR_GRAPH_QA_RETRIEVAL_MODE", "hybrid") == "lexical" else BgeChromaSearch(
        python, model, repository.root / "chroma-qa-bge-m3", timeout=600,
        resident=os.environ.get('SCHOLAR_GRAPH_VECTOR_RESIDENT') == 'true')
    reranker = LocalReranker(repository.root, python, os.environ.get("SCHOLAR_GRAPH_RERANKER_PATH", str(root / "data/module-four-models/bge-reranker-large")), resident=True)
    return QAHybridRetriever(repository, vector, reranker)
