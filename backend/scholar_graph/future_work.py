"""Conservative, auditable extraction and chronological resolution in selected papers."""

import hashlib
import re
from collections import defaultdict

from .qa import validate_answer, quote_blocks
from .qa_evidence import numbers
from .validation import chunk_anchor

FUTURE = re.compile(r"(?:Future work|Future direction|未来工作|未来方向)\s*[:：]\s*(.+)", re.I)
RESOLVED = re.compile(r"(?:Resolved future direction|We resolved the previously open direction|已解决的未来方向)\s*[:：]\s*(.+)", re.I)


def topic_key(text):
    return " ".join(text.rstrip(".。 ").casefold().split())


def marked_quotes(bundle, pattern):
    for chunk in sorted(bundle["chunks"], key=lambda item: (item["page_number"], item["chunk_id"])):
        for line in chunk["text"].splitlines():
            quote = line.strip()
            match = pattern.fullmatch(quote)
            if match and 0 < len(quote) <= 600 and topic_key(match[1]):
                yield chunk, quote, match[1].rstrip(".。 ")


def anchored_quote(bundle, chunk, quote, gate):
    evidence = [{"anchor": chunk_anchor(chunk), "quote": quote}]
    checks = [{"claim": quote, "status": "passed", "evidence": [evidence[0]["anchor"]],
               "reason": "数字连同原文上下文回溯至该 Chunk；不代表独立实验验证。"}] if numbers(quote) else []
    record = {"schema_version": "1.0.0", "answer": quote_blocks(evidence)[0],
              "anchors": [evidence[0]["anchor"]], "numeric_fact_check": {
                  "status": "passed" if checks else "not_applicable", "checks": checks}, "refused": False}
    validate_answer(record, bundle, evidence, gate)
    return record


def filter_future_work(bundles, edges, gate):
    candidates = defaultdict(list)
    for bundle in sorted(bundles, key=lambda item: item["paper_meta"]["id"]):
        for chunk, quote, topic in marked_quotes(bundle, RESOLVED):
            candidates[topic_key(topic)].append((bundle, chunk, quote))
    verified_citations = {(edge["from_paper_id"], edge["to_paper_id"], edge["anchor"]["chunk_id"])
                          for edge in edges if edge["status"] == "verified"}
    result = {"worth_exploring": [], "excluded": [], "unverifiable": [], "checks": []}
    seen = set()
    for source in sorted(bundles, key=lambda item: item["paper_meta"]["id"]):
        paper = source["paper_meta"]
        for chunk, quote, topic in marked_quotes(source, FUTURE):
            identity = (paper["id"], topic_key(topic))
            if identity in seen:
                continue
            seen.add(identity)
            direction_id = "direction-" + hashlib.sha256("\0".join(identity).encode()).hexdigest()[:20]
            entry = {"direction_id": direction_id, "topic": topic,
                     "source": anchored_quote(source, chunk, quote, gate), "resolutions": []}
            unknown_time = paper["year"] is None
            for candidate, resolution_chunk, resolution_quote in candidates[identity[1]]:
                later = candidate["paper_meta"]
                if later["id"] == paper["id"]:
                    continue
                cited = (later["id"], paper["id"], resolution_chunk["chunk_id"]) in verified_citations
                if not cited:
                    reason = "no_verified_citation_in_resolution_chunk"
                elif paper["year"] is None or later["year"] is None:
                    reason = "unknown_publication_year"
                    unknown_time = True
                elif later["year"] <= paper["year"]:
                    reason = "not_strictly_later"
                else:
                    reason = "explicit_same_topic_later_citing_evidence"
                    entry["resolutions"].append(anchored_quote(candidate, resolution_chunk, resolution_quote, gate))
                result["checks"].append({"direction_id": direction_id, "candidate_paper_id": later["id"],
                    "decision": "accepted" if reason == "explicit_same_topic_later_citing_evidence" else "rejected", "reason": reason})
            bucket = "excluded" if entry["resolutions"] else "unverifiable" if unknown_time else "worth_exploring"
            result[bucket].append(entry)
    return result
