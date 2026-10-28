"""Local citation identity joins and explicit, unweighted PageRank."""

from .errors import PipelineError
from .validation import chunk_anchor
from .reference_identity import bibliography_sources, paper_titles, resolve_reference

DAMPING, TOLERANCE, MAX_ITERATIONS = 0.85, 1e-12, 1000


def target_for(reference, papers):
    profiles = [{'paper': paper, 'titles': [{'text': paper['title'], 'anchor': None, 'source': 'PaperMeta.title'}]
                 if paper['title'] else []} for paper in papers]
    result = resolve_reference(reference, profiles)
    return result['target_paper_id'], result['reason']


def citation_edges(bundles, gate, *, with_evidence=False, year_bases=None):
    for bundle in bundles:
        gate.bundle(bundle)
    papers = [bundle["paper_meta"] for bundle in bundles]
    if len({paper["id"] for paper in papers}) != len(papers):
        raise PipelineError("VALIDATION_ERROR", "图谱不能重复选择论文。")
    profiles = [{'paper': bundle['paper_meta'], 'titles': paper_titles(bundle), 'year_basis': (year_bases or {}).get(bundle['paper_meta']['id'])} for bundle in bundles]
    edges, unresolved, resolutions, proofs, seen = [], [], [], [], {}
    for bundle in sorted(bundles, key=lambda item: item["paper_meta"]["id"]):
        chunks = {item["chunk_id"]: item for item in bundle["chunks"]}
        pid = bundle["paper_meta"]["id"]
        sources = {item['number']: item for item in bibliography_sources(bundle['chunks'])}
        for ref in sorted(bundle["reference_entries"], key=lambda item: item["number"]):
            source = sources.get(ref['number'], {})
            resolution = resolve_reference(ref, profiles, source.get('raw', ''))
            bibliography = [{'anchor': chunk_anchor(chunk), 'quote': chunk['text'][:600]}
                            for chunk in source.get('chunks', [])]
            for quote in bibliography:
                gate.anchor(quote['anchor'], bundles, quote=quote['quote'])
            resolution.update(paper_id=pid, ref_id=ref['ref_id'], reference_number=ref['number'],
                              bibliography=bibliography,
                              status='resolved' if resolution['target_paper_id'] else 'unresolved')
            resolutions.append(resolution)
            target, reason = resolution['target_paper_id'], resolution['reason']
            if target is None:
                unresolved.append({"paper_id": pid, "ref_id": ref["ref_id"], "reason": reason})
                continue
            links = [link for link in bundle["citation_links"] if link["ref_id"] == ref["ref_id"]]
            for link in links or [None]:
                anchor = chunk_anchor(chunks[link["chunk_id"]]) if link else None
                key = (pid, target, link["chunk_id"] if link else None)
                if key in seen:
                    proofs[seen[key]]['references'].append(resolution)
                    continue
                seen[key] = len(edges)
                edge = {"schema_version": "1.2.0", "from_paper_id": pid, "to_paper_id": target,
                        "anchor": anchor, "status": "verified" if anchor else "unverified"}
                gate.record("GraphEdge", edge)
                if anchor:
                    gate.anchor(anchor, bundles)
                edges.append(edge)
                proofs.append({'edge_index': len(edges) - 1, 'from_paper_id': pid, 'to_paper_id': target,
                    'anchor': anchor, 'citation_number': link['citation_number'] if link else None,
                    'body_quote': chunks[link['chunk_id']]['text'] if link else None,
                    'references': [resolution]})
    if with_evidence:
        return edges, unresolved, {'reference_resolutions': resolutions, 'edge_evidence': proofs,
            'reference_count': len(resolutions), 'unresolved_reference_count': len(unresolved),
            'resolved_reference_count': len(resolutions) - len(unresolved)}
    return edges, unresolved


def pagerank(paper_ids, pairs, *, damping=DAMPING, tolerance=TOLERANCE, max_iterations=MAX_ITERATIONS):
    nodes = sorted(paper_ids)
    if not nodes or len(set(nodes)) != len(nodes) or not 0 < damping < 1 or tolerance <= 0 or max_iterations < 1:
        raise PipelineError("VALIDATION_ERROR", "PageRank 输入或收敛参数不合法。")
    outgoing = {node: set() for node in nodes}
    for source, target in set(pairs):
        if source not in outgoing or target not in outgoing:
            raise PipelineError("VALIDATION_ERROR", "引用边端点不在所选论文中。")
        outgoing[source].add(target)
    size = len(nodes)
    values = {node: 1 / size for node in nodes}
    for iteration in range(1, max_iterations + 1):
        dangling = sum(values[node] for node in nodes if not outgoing[node])
        updated = {node: (1 - damping) / size + damping * dangling / size for node in nodes}
        for source in nodes:
            for target in sorted(outgoing[source]):
                updated[target] += damping * values[source] / len(outgoing[source])
        residual = sum(abs(updated[node] - values[node]) for node in nodes)
        values = updated
        if residual <= tolerance:
            return values, {"damping": damping, "tolerance": tolerance, "max_iterations": max_iterations,
                "iterations": iteration, "residual": residual, "verified_pair_count": sum(map(len, outgoing.values())),
                "uniform_baseline": 1 / size}
    raise PipelineError("INDEXING_FAILED", "PageRank 在限定迭代内未收敛，未返回伪造分数。")


def graph_nodes(bundles, edges, gate):
    pairs = {(edge["from_paper_id"], edge["to_paper_id"]) for edge in edges if edge["status"] == "verified"}
    values, diagnostics = pagerank([bundle["paper_meta"]["id"] for bundle in bundles], pairs)
    incoming = {target for _, target in pairs}
    connected = {pid for pair in pairs for pid in pair}
    nodes, layers = [], {"cornerstone": [], "derived": [], "isolated": []}
    for bundle in sorted(bundles, key=lambda item: item["paper_meta"]["id"]):
        paper = bundle["paper_meta"]
        pid = paper["id"]
        level = ("isolated" if pid not in connected else "cornerstone"
                 if pid in incoming and values[pid] > diagnostics["uniform_baseline"] + TOLERANCE else "derived")
        node = {"schema_version": "1.2.0", "paper_id": pid, "title": paper["title"], "year": paper["year"],
                "pagerank": values[pid], "level": level}
        gate.record("GraphNode", node)
        nodes.append(node)
        layers[level].append(pid)
    for level in layers:
        layers[level].sort(key=lambda pid: (-values[pid], pid))
    return nodes, layers, diagnostics
