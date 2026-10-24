"""Deterministic, conservative version comparison; version numbers imply no quality ranking."""

from __future__ import annotations

import copy
import re
from collections import Counter, defaultdict

from .errors import PipelineError
from .validation import ContractGate, chunk_anchor, compact


def corpus(bundle):
    return "\n".join(chunk["text"] for chunk in bundle["chunks"])


def similarity(old, new):
    if compact(corpus(old)) == compact(corpus(new)):
        return 1.0
    left = Counter(re.findall(r"\w+", corpus(old).casefold()))
    right = Counter(re.findall(r"\w+", corpus(new).casefold()))
    total = sum(left.values()) + sum(right.values())
    return round(2 * sum((left & right).values()) / total, 6) if total else 0.0


def sections(bundle):
    result = defaultdict(list)
    for chunk in bundle["chunks"]:
        result[tuple(chunk["section_path"])].append(chunk)
    return result


def informative(chunks):
    # A heading establishes location; prefer actual body text as evidence for a content change.
    return next((chunk for chunk in chunks if chunk["text"] not in chunk["section_path"]), chunks[0])


def compare(old: dict, new: dict, gate: ContractGate) -> tuple[dict, dict]:
    gate.bundle(old)
    gate.bundle(new)
    old_id, new_id = old["paper_meta"]["id"], new["paper_meta"]["id"]
    if old_id == new_id:
        raise PipelineError("VALIDATION_ERROR", "相同文件记录无需生成跨版本裁决。")
    old_sections, new_sections = sections(old), sections(new)
    changed, key_sentences = [], []
    for path in sorted(old_sections.keys() | new_sections.keys()):
        before, after = old_sections.get(path, []), new_sections.get(path, [])
        if [compact(x["text"]) for x in before] == [compact(x["text"]) for x in after]:
            continue
        changed.append(" / ".join(path) if path else "Unsectioned")
        old_texts = {compact(chunk["text"]) for chunk in before}
        candidates = [chunk for chunk in after if compact(chunk["text"]) not in old_texts]
        if candidates:
            source = informative(candidates)
        else:
            new_texts = {compact(chunk["text"]) for chunk in after}
            candidates = [chunk for chunk in before if compact(chunk["text"]) not in new_texts]
            source = informative(candidates or before or after)
        key_sentences.append({"text": source["text"][:600], "anchor": chunk_anchor(source), "status": "verified"})
    identical = compact(corpus(old)) == compact(corpus(new))
    recommendation = "keep_old" if identical else "manual_review"
    reason = ("两份已解析正文一致；保留已有记录可避免重复。" if identical else
              "已检出文本变化，但文本相似度和版本序号不能证明新版质量更高；需人工核对差异。")
    # Include actual context from both versions; no invented comparative scientific findings.
    evidence_sources = None
    # Prefer a shared section containing changed body text in both versions. Metadata-only
    # changes remain available in DiffSummary, but do not displace substantive evidence.
    for path in sorted(old_sections.keys() & new_sections.keys(), key=lambda item: (not bool(item), item)):
        before, after = old_sections[path], new_sections[path]
        left = {compact(c["text"]) for c in before}
        right = {compact(c["text"]) for c in after}
        removed = [c for c in before if compact(c["text"]) not in right]
        added = [c for c in after if compact(c["text"]) not in left]
        if removed and added:
            evidence_sources = [informative(removed), informative(added)]
            break
    if evidence_sources is None:
        evidence_sources = [informative([c for c in bundle["chunks"] if c["section_path"]] or bundle["chunks"])
                            for bundle in (old, new)]
    evidence = [{"anchor": chunk_anchor(source), "reason": reason} for source in evidence_sources]
    decision = {"schema_version": "1.1.0", "old_paper_id": old_id, "new_paper_id": new_id,
                "similarity": similarity(old, new), "evidence": evidence,
                "recommendation": recommendation, "human_override": False}
    diff = {"schema_version": "1.1.0", "old_paper_id": old_id, "new_paper_id": new_id,
            "changed_sections": changed,
            "summary_text": ("检出章节文本差异：" + "；".join(changed) + "。关键句为对应版本的原文摘录，不代表质量排名。") if changed
                            else "未检出章节级差异；在本次已解析分块中未发现章节文本变化。",
            "key_sentences": key_sentences}
    gate.comparison(decision, diff, [old, new])
    return decision, diff


def human_decision(system: dict, choice: str, reason: str, diff: dict,
                   bundles: list[dict], gate: ContractGate) -> dict:
    gate.comparison(system, diff, bundles)
    if system["human_override"] or not reason.strip():
        raise PipelineError("VALIDATION_ERROR", "人工意见需要未覆盖的系统记录及明确依据。")
    result = copy.deepcopy(system)
    result["recommendation"], result["human_override"] = choice, True
    for item in result["evidence"]:
        item["reason"] = "人工意见：" + reason.strip() + "；原系统依据：" + item["reason"]
    gate.comparison(result, diff, bundles)
    return result
