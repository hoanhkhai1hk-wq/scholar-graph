"""Deterministic, anchored outlines from the existing graph and retrieval modules."""

import json
from collections import deque

from .errors import PipelineError
from .graph_service import build_graph
from .recommendations import recommendations
from .retrieval import lexical_ranking
from .validation import chunk_anchor


class SelectedPapers:
    """Keep module-four recommendation signals inside the requested paper set."""
    def __init__(self, bundles, gate):
        self.bundles = {bundle["paper_meta"]["id"]: bundle for bundle in bundles}
        self.gate = gate

    def paper(self, paper_id):
        return self.bundles[paper_id]

    def papers(self):
        return [bundle["paper_meta"] for bundle in self.bundles.values()]


def unique_anchors(points):
    return list({json.dumps(point["anchor"], sort_keys=True): point["anchor"] for point in points}.values())


def paper_point(bundle, gate):
    chunks = sorted(bundle["chunks"], key=lambda chunk: (chunk["page_number"], chunk["chunk_id"]))
    ranked = lexical_ranking(chunks, bundle["paper_meta"]["title"] or "research")
    chunk = next((chunk for chunk in chunks if ranked and chunk["chunk_id"] == ranked[0][0]), chunks[0])
    quote = next(line.strip() for line in chunk["text"].splitlines() if line.strip())[:600]
    anchor = chunk_anchor(chunk)
    gate.anchor(anchor, [bundle], quote=quote)
    return {"text": quote, "anchor": anchor}


def assemble_outline(bundles, gate):
    if not bundles or len(bundles) > 100:
        raise PipelineError("VALIDATION_ERROR", "框架需要1–100篇不同的已落盘论文。")
    for bundle in bundles:
        gate.bundle(bundle)
    by_id = {bundle["paper_meta"]["id"]: bundle for bundle in bundles}
    if len(by_id) != len(bundles):
        raise PipelineError("VALIDATION_ERROR", "框架论文集合不接受重复id。")
    graph = build_graph(bundles, gate)
    cores = graph["layers"]["cornerstone"]
    neighbors = {pid: set() for pid in by_id}
    for edge in graph["edges"]:
        if edge["status"] == "verified":
            left, right = edge["from_paper_id"], edge["to_paper_id"]
            neighbors[left].add(right)
            neighbors[right].add(left)
    year = max((bundle["paper_meta"]["year"] or 1 for bundle in bundles))
    view = SelectedPapers(bundles, gate)
    scores = {core: {item["paper"]["id"]: item["score"] for item in recommendations(view, core, year)} for core in cores}
    groups = {core: [core] for core in cores}
    independent = []
    for pid in sorted(set(by_id) - set(cores)):
        distances, queue = {pid: 0}, deque([pid])
        while queue:
            current = queue.popleft()
            for neighbor in sorted(neighbors[current]):
                if neighbor not in distances:
                    distances[neighbor] = distances[current] + 1
                    queue.append(neighbor)
        reachable = [core for core in cores if core in distances]
        if reachable:
            core = min(reachable, key=lambda core: (distances[core], -scores[core][pid], core))
            groups[core].append(pid)
        else:
            independent.append(pid)
    chapters = []
    def chapter(kind, identity, ids, points, title):
        return {"chapter_id": "chapter-" + kind + "-" + identity, "kind": kind, "title": title,
                "paper_ids": ids, "anchors": unique_anchors(points), "writing_points": points}
    for core in cores:
        ids = [core] + sorted(groups[core][1:], key=lambda pid: (-scores[core][pid], pid))
        title = by_id[core]["paper_meta"]["title"] or core
        chapters.append(chapter("cornerstone", core, ids, [paper_point(by_id[pid], gate) for pid in ids], "基石论文：" + title))
    levels = {node["paper_id"]: node["level"] for node in graph["nodes"]}
    for pid in independent:
        kind = levels[pid]
        label = "独立论文：" if kind == "isolated" else "衍生论文："
        chapters.append(chapter(kind, pid, [pid], [paper_point(by_id[pid], gate)], label + (by_id[pid]["paper_meta"]["title"] or pid)))
    future = []
    for direction in graph["future_work"]["worth_exploring"]:
        source = direction["source"]
        quote = source["answer"].split("\n", 1)[1]
        future.append({"text": quote, "anchor": source["anchors"][0]})
    if future:
        chapters.append(chapter("future_work", "selected", sorted({p["anchor"]["paper_id"] for p in future}),
                                future, "未来方向（所选语料尚未证实已解决）"))
    return {"schema_version": "1.2.0", "paper_ids": sorted(by_id), "chapters": chapters}


def validate_outline(value, bundles, gate):
    gate.record("FrameworkOutline", value)
    if value != assemble_outline(bundles, gate):
        raise PipelineError("VALIDATION_ERROR", "框架章节、归位、要点或锚点与所选真实证据不一致。")
    for chapter in value["chapters"]:
        for point in chapter["writing_points"]:
            gate.anchor(point["anchor"], bundles, quote=point["text"])


def generate_outline(bundles, gate):
    value = assemble_outline(bundles, gate)
    validate_outline(value, bundles, gate)
    return value
