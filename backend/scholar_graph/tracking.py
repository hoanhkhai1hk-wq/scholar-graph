"""Bounded public arXiv polling from local topics and anchored references."""

import re
import time
from datetime import datetime, timezone
from uuid import uuid4

from .arxiv_fetch import base_identity
from .citation_cleanup import clean_citations
from .errors import PipelineError
from .qa_evidence import terms
from .tracking_state import TrackingState, operation_lock, utc_now
from .validation import chunk_anchor

TOPIC_STOP = {"all", "need", "you", "our", "their", "with", "from", "into", "also", "can", "new", "towards", "via", "based", "approach", "study", "analysis"}


def topic_terms(paper):
    words = {part for token in terms(paper.get("title") or "") for part in token.split("-")
             if re.fullmatch(r"[a-z]{3,}", part) and part not in TOPIC_STOP}
    return {word[:-1] if word.endswith("s") and not word.endswith("ss") and len(word) > 4 else word for word in words}


def seed_queries(repository, paper_ids):
    result = []
    for pid in paper_ids:
        bundle = repository.paper(pid)
        paper = bundle["paper_meta"]
        words = sorted(topic_terms(paper))[:4]
        topic_anchor = None
        if not words:
            # Older local imports have nullable titles: use an actual short first-page
            # text block, never fill or modify the frozen PaperMeta with a guessed title.
            for chunk in bundle["chunks"]:
                tokens = re.findall(r"\b[A-Za-z][A-Za-z-]*\b", chunk["text"])
                if (chunk["page_number"] == 1 and chunk["type"] == "text" and not chunk["section_path"]
                        and 3 <= len(tokens) <= 15 and "@" not in chunk["text"]):
                    words = sorted(topic_terms({"title": chunk["text"]}))[:4]
                    if words:
                        topic_anchor = chunk_anchor(chunk)
                        break
        if words:
            result.append({"paper_id": pid, "query": " AND ".join('all:"' + word + '"' for word in words),
                           "kind": "topic", "terms": words, "anchor": topic_anchor})
        refs = {ref["ref_id"]: ref for ref in bundle["reference_entries"]}
        chunks = {chunk["chunk_id"]: chunk for chunk in bundle["chunks"]}
        for link in bundle["citation_links"]:
            ref = refs[link["ref_id"]]
            reference_title = ref["title"]
            reference_anchor = None
            if not reference_title:
                for chunk in bundle["chunks"]:
                    if not re.match(r"^\[" + str(ref["number"]) + r"\]\s", chunk["text"]):
                        continue
                    match = re.search(r"\.\s+([^.]+)\.\s+(?:arXiv|CoRR|In\b)", chunk["text"])
                    if match:
                        reference_title = match[1]
                        reference_anchor = chunk_anchor(chunk)
                        break
            if not reference_title:
                continue
            title = re.sub(r'[^\w\s-]', ' ', reference_title).strip()[:300]
            if title:
                result.append({"paper_id": pid, "query": 'ti:"' + title + '"', "kind": "citation",
                    "reference": ref, "terms": sorted(topic_terms({"title": title})),
                    "reference_title_excerpt": reference_title, "reference_anchor": reference_anchor,
                    "anchor": chunk_anchor(chunks[link["chunk_id"]])})
                break  # Bound requests while keeping an actual, anchored citation seed.
    return result


class TrackingService:
    def __init__(self, repository, fetcher):
        self.repository, self.fetcher = repository, fetcher
        self.state = TrackingState(repository.root)

    def status(self):
        return {"latest_run": self.state.latest(), "dedup_records": self.state.duplicates(),
                "scheduler": "externally_triggered", "default_interval_seconds": 86400}

    def run(self, *, paper_ids=None, max_candidates=5, max_imports=2, interval_seconds=86400, force=True):
        with operation_lock(self.repository.root, "poll"):
            latest = self.state.latest()
            if not force and latest and latest["status"] != "running":
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(latest["started_at"])).total_seconds()
                if age < interval_seconds:
                    return {"skipped": True, "reason": "NOT_DUE", "latest_run": latest}
            if latest and latest["status"] == "running":
                latest.update(status="interrupted", finished_at=utc_now(), reason="前一进程退出，运行锁已释放；不冒充已完成。")
                self.state.run(latest)
            run = {"run_id": uuid4().hex, "started_at": utc_now(), "finished_at": None, "status": "running",
                   "duration_seconds": None, "candidate_count": 0, "candidates": [], "queries": [],
                   "imported_count": 0, "duplicate_count": 0, "failed_count": 0, "errors": [],
                   "cleanup": None, "interval_seconds": interval_seconds, "dedup_record_count": 0}
            start = time.monotonic()
            self.state.run(run)
            try:
                run["cleanup"] = clean_citations(self.repository)
                ids = paper_ids if paper_ids is not None else [p["id"] for p in self.repository.papers()][:5]
                if not ids or len(ids) > 5 or len(ids) != len(set(ids)):
                    raise PipelineError("VALIDATION_ERROR", "追踪需要 1 到 5 篇不重复的库内种子论文。")
                run["paper_ids"] = ids
                candidates = {}
                queries = seed_queries(self.repository, ids)
                if not queries:
                    raise PipelineError("VALIDATION_ERROR", "库内元数据与真实 Chunk 中未找到可核验的主题或引用种子，未执行空追踪冒充完成。")
                for query in queries:
                    entry = {**query, "returned_count": 0, "error": None}
                    run["queries"].append(entry)
                    try:
                        papers = self.fetcher.client.search(query["query"], max_candidates)
                        entry["returned_count"] = len(papers)
                        for paper in papers:
                            identity = base_identity(paper["arxiv_id"])
                            shared = sorted(set(query["terms"]) & topic_terms({"title": (paper["title"] or "") + " " + (paper["abstract"] or "")}))
                            if not shared:
                                continue  # The public search match alone is not a relevance assertion.
                            relation = {"paper_id": query["paper_id"], "kind": query["kind"], "matched_terms": shared,
                                "reason": ("与库内论文主题词重合：" if query["kind"] == "topic" else "与库内真实引用条目标题词重合：") + ", ".join(shared),
                                "anchor": query["anchor"], "reference_anchor": query.get("reference_anchor")}
                            if identity not in candidates:
                                candidates[identity] = {"arxiv_id": paper["arxiv_id"], "title": paper["title"],
                                    "metadata": paper, "related_to": [], "outcome": "deferred", "import": None}
                            candidates[identity]["related_to"].append(relation)
                    except PipelineError as error:
                        entry["error"] = error.envelope()
                        run["errors"].append({"query": query["query"], **error.envelope()})
                    self.state.run(run)
                run["candidates"] = list(candidates.values())[:max_candidates]
                run["candidate_count"] = len(run["candidates"])
                attempts = 0
                for candidate in run["candidates"]:
                    if attempts >= max_imports:
                        continue
                    attempts += 1
                    result = self.fetcher.fetch_metadata(candidate["metadata"])
                    candidate["import"] = result
                    if not result["succeeded"]:
                        candidate["outcome"] = "failed"
                        run["failed_count"] += 1
                    elif result["already_present"]:
                        candidate["outcome"] = "duplicate"
                        run["duplicate_count"] += 1
                    else:
                        candidate["outcome"] = "imported"
                        run["imported_count"] += 1
                    self.state.run(run)
                run["status"] = "partial" if run["errors"] or run["failed_count"] else "completed"
                if run["errors"] and not run["candidate_count"]:
                    run["status"] = "failed"
            except PipelineError as error:
                run["errors"].append(error.envelope())
                run["status"] = "failed"
            except Exception:
                run["errors"].append(PipelineError("INTERNAL_ERROR", "追踪运行未完成，未编造候选或入库结果。").envelope())
                run["status"] = "failed"
            finally:
                run.update(finished_at=utc_now(), duration_seconds=round(time.monotonic() - start, 6),
                           dedup_record_count=len(self.state.duplicates()))
                self.state.run(run)
            return run
