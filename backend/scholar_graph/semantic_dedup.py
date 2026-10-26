"""Calibrated semantic assessment with explicit identity and human-review safeguards."""

import json
import os
import re
import sqlite3
from pathlib import Path

from .retrieval import VectorUnavailable
from .semantic_vectors import encoder_from_environment, band, REPRESENTATION, cosine
from .vector_search import MODEL_REVISION


def conflict(left, right):
    if left["doi"] and right["doi"] and left["doi"].casefold() != right["doi"].casefold():
        return True
    return bool(left["arxiv_id"] and right["arxiv_id"] and re.sub(r"v\d+$", "", left["arxiv_id"]) != re.sub(r"v\d+$", "", right["arxiv_id"]))


class SemanticDedup:
    def __init__(self, root, *, encoder=None, policy=None):
        self.encoder = encoder or encoder_from_environment(root)
        self.policy = policy

    def assess(self, bundle, store):
        paper = bundle["paper_meta"]
        others = [store.load(path) for path in sorted((store.root / "papers").glob("paper-*")) if path.is_dir()]
        meta = {"status": "unavailable", "method": "bge_m3_dense_cosine", "paper_id": paper["id"],
                "score": None, "band": None, "reason": None, "candidates": [], "model_revision": MODEL_REVISION}
        # Bare DOI remains an authoritative, zero-encoding fast lane.
        for old in others:
            p = old["paper_meta"]
            if p["id"] != paper["id"] and p["doi"] and paper["doi"] and p["doi"].casefold() == paper["doi"].casefold():
                meta.update(status="identity_fast_path", method="doi_exact", band="duplicate", matched_paper_id=p["id"], reason="裸 DOI 精确一致；走身份快速通道，未伪造向量分数。")
                return old, meta
        try:
            policy = self.policy
            if policy is None:
                policy = json.loads(Path(__file__).with_name("semantic_thresholds.json").read_text(encoding="utf-8"))
            if (policy["model_revision"] != MODEL_REVISION or policy["representation"] != REPRESENTATION
                    or not -1 <= policy["review_threshold"] < policy["duplicate_threshold"] <= 1):
                raise VectorUnavailable("CALIBRATION_POLICY_MISMATCH")
            by_id = {b["paper_meta"]["id"]: b for b in [*others, bundle]}
            vectors = self.encoder.encode(list(by_id.values()))
            meta.update(status="ready", policy=policy, encoder=self.encoder.last_metadata)
            for old in others:
                pid = old["paper_meta"]["id"]
                score = cosine(vectors[paper["id"]], vectors[pid])
                category = band(score, policy)
                identity_conflict = conflict(paper, old["paper_meta"])
                if identity_conflict and category == "duplicate":
                    category = "manual_review"
                meta["candidates"].append({"paper_id": pid, "cosine": score, "band": category, "identity_conflict": identity_conflict})
            if not others:
                meta.update(band="new_paper", reason="库内无候选；已建立本地论文向量，不伪造相似度。")
                return None, meta
            best = max(meta["candidates"], key=lambda row: (row["cosine"], row["paper_id"]))
            meta.update(score=best["cosine"], band=best["band"], matched_paper_id=best["paper_id"])
            old = by_id[best["paper_id"]]
            if best["paper_id"] == paper["id"]:
                meta.update(band="duplicate", reason="同一文件内容已入库（SHA-256 一致）；换名重传不新增论文。本地 BGE-M3 向量余弦为 1。")
                return old, meta
            if best["band"] == "new_paper":
                meta["reason"] = "本地 BGE-M3 余弦低于人工核对阈值；判为新论文。"
                # Explicit identity still takes precedence if metadata says it is a version.
                exact = store.previous_version(paper)
                if exact is not None:
                    meta.update(band="manual_review", reason="向量低分与既有身份依据不一致，保留人工核对。")
                    return exact, meta
                return None, meta
            meta["reason"] = ("本地 BGE-M3 余弦达到重复阈值；版本偏好须另有真实版本依据。" if best["band"] == "duplicate" else
                              "本地 BGE-M3 余弦处于人工核对区间，或持久身份冲突；未自动判为重复。")
            return old, meta
        except (VectorUnavailable, OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
            reason = str(error) if isinstance(error, VectorUnavailable) and str(error) else type(error).__name__
            meta.update(reason="本地语义向量不可用，保留 DOI/身份与词频 Dice 及人工核对兜底。", fallback_reason=reason)
            return store.dedup_candidate(bundle), meta


def semantic_from_environment(root):
    return None if os.environ.get("SCHOLAR_GRAPH_DEDUP_MODE", "auto") == "off" else SemanticDedup(root)
