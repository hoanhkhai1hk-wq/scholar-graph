"""Rank real published Chunks; transport wrappers never alter frozen records."""

import math

from .errors import PipelineError
from .qa_evidence import terms, numbers
from .validation import chunk_anchor


def load_bundles(repository, paper_ids=None):
    ids = paper_ids if paper_ids is not None else [paper["id"] for paper in repository.papers()]
    if len(ids) != len(set(ids)):
        raise PipelineError("VALIDATION_ERROR", "论文集合不接受重复 id。")
    return [repository.paper(pid) for pid in ids]


def lexical_ranking(chunks, question):
    def tokens(text):
        return terms(text) | {"number:" + value for value in numbers(text)}
    query = tokens(question)
    documents = [tokens(chunk["text"]) for chunk in chunks]
    if not chunks or not query:
        return []
    vocab = set().union(query, *documents)
    idf = {word: 1 + math.log((len(chunks) + 1) / (1 + sum(word in doc for doc in documents))) for word in vocab}
    qnorm = math.sqrt(sum(idf[word] ** 2 for word in query))
    result = []
    for chunk, document in zip(chunks, documents, strict=True):
        overlap = query & document
        if overlap:
            dnorm = math.sqrt(sum(idf[word] ** 2 for word in document))
            score = sum(idf[word] ** 2 for word in overlap) / (qnorm * dnorm)
            result.append((chunk["chunk_id"], min(1.0, score)))
    return sorted(result, key=lambda item: (-item[1], item[0]))


def fuse_ranks(dense, sparse, k=60):
    """Equal-weight reciprocal rank fusion; zero sparse matches contribute nothing."""
    dense_order = sorted(dense, key=lambda cid: (-dense[cid], cid))
    sparse_order = sorted((cid for cid in sparse if sparse[cid] > 0), key=lambda cid: (-sparse[cid], cid))
    scores = {cid: 0.5 * (k + 1) / (k + rank) for rank, cid in enumerate(dense_order, 1)}
    for rank, cid in enumerate(sparse_order, 1):
        scores[cid] = scores.get(cid, 0) + 0.5 * (k + 1) / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


class SearchService:
    def __init__(self, repository, vector=None):
        self.repository, self.vector = repository, vector

    def search(self, question, paper_ids=None, minimum=0):
        bundles = load_bundles(self.repository, paper_ids)
        chunks = [chunk for bundle in bundles for chunk in bundle["chunks"]]
        by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
        if len(by_id) != len(chunks):
            raise PipelineError("VALIDATION_ERROR", "检索集合 Chunk id 必须全局唯一。")
        method, vector_status = "lexical", "NOT_ENABLED"
        if self.vector and chunks:
            try:
                ranked = self.vector.search(chunks, question)
                method, vector_status = "bge_m3_hybrid", "READY"
            except VectorUnavailable:
                ranked = lexical_ranking(chunks, question)
                vector_status = "UNAVAILABLE"
        else:
            ranked = lexical_ranking(chunks, question)
        items, seen = [], set()
        for cid, score in ranked:
            if cid not in by_id or cid in seen or not math.isfinite(score) or not 0 <= score <= 1:
                raise PipelineError("VALIDATION_ERROR", "检索结果包含错误索引或非法相关度。")
            seen.add(cid)
            if score < minimum or score <= 0:
                continue
            chunk = by_id[cid]
            anchor = chunk_anchor(chunk)
            self.repository.gate.record("Chunk", chunk)
            self.repository.gate.anchor(anchor, bundles)
            items.append({"chunk": chunk, "anchor": anchor, "relevance": score, "retrieval_method": method})
        reason = "OK" if items else "EMPTY_CORPUS" if not chunks else "NO_MATCHING_CHUNKS"
        return items, {"method": method, "vector_status": vector_status, "reason": reason}


class VectorUnavailable(Exception):
    """Dependency/model/worker unavailable: explicit lexical fallback, never fake vectors."""
