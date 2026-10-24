"""Transparent local recommendations from module-five graph and actual metadata."""

import re
from urllib.parse import urlparse

from .citation_graph import citation_edges, graph_nodes
from .retrieval import load_bundles

WEIGHTS = {"graph_neighbor": 0.40, "pagerank_normalized": 0.35, "recency": 0.15, "github_link": 0.10}
FORMULA = "score = 100 * (0.40*G + 0.35*P + 0.15*T + 0.10*C); missing terms contribute 0, without reweighting"


def github_signals(paper):
    result = []
    for field in ("abstract", "source"):
        for raw in re.findall(r"https://[^\s<>\"'()]+", paper[field] or ""):
            url = raw.rstrip(".,;:。；，")
            parsed = urlparse(url)
            parts = parsed.path.strip("/").split("/")
            if (parsed.hostname == "github.com" and not parsed.username and not parsed.password
                    and not parsed.query and not parsed.fragment and len(parts) == 2
                    and all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts)):
                if url not in {item["url"] for item in result}:
                    result.append({"metadata_field": field, "url": url})
    return result


def recommendations(repository, seed_id, as_of_year):
    repository.paper(seed_id)  # Missing seed is a 404, not an empty recommendation record.
    bundles = load_bundles(repository)
    edges, unresolved = citation_edges(bundles, repository.gate)
    nodes, _, _ = graph_nodes(bundles, edges, repository.gate)
    by_id = {node["paper_id"]: node for node in nodes}
    maximum = max(node["pagerank"] for node in nodes)
    result = []
    for bundle in bundles:
        paper = bundle["paper_meta"]
        pid = paper["id"]
        if pid == seed_id:
            continue
        links = [edge for edge in edges if edge["status"] == "verified"
                 and {edge["from_paper_id"], edge["to_paper_id"]} == {seed_id, pid}]
        node = by_id[pid]
        year = paper["year"]
        recency = max(0.0, 1 - (as_of_year - year) / 10) if year is not None and year <= as_of_year else None
        code = github_signals(paper)
        signals = {"graph_neighbor": int(bool(links)), "pagerank_normalized": node["pagerank"] / maximum,
                   "recency": recency, "github_link": 1 if code else None}
        score = 100 * sum(WEIGHTS[key] * (value if value is not None else 0) for key, value in signals.items())
        reasons = [{"signal": "pagerank_normalized", "text": "复用模块五在当前本地论文集合计算的 PageRank，不是全网引用数或科研质量。",
                    "evidence": {"graph_node": node, "scope_size": len(nodes), "maximum_pagerank": maximum}}]
        if links:
            reasons.append({"signal": "graph_neighbor", "text": "与种子论文存在直接、已核验的局域引用边。", "evidence": {"edges": links}})
        if recency is not None:
            reasons.append({"signal": "recency", "text": "使用元数据发表年份与指定评分年份计算十年线性时效项。",
                            "evidence": {"metadata_field": "year", "year": year, "as_of_year": as_of_year}})
        if code:
            reasons.append({"signal": "github_link", "text": "元数据包含 GitHub 仓库链接；未核验仓库可访问性、内容或开源许可证。", "evidence": {"links": code}})
        missing = (["publication_year" if year is None else "publication_year_after_as_of_year"] if recency is None else [])
        if not code:
            missing.append("github_link")  # Unknown, never assert that the paper has no code.
        result.append({"paper": paper, "score": score, "signals": signals, "reasons": reasons,
                       "missing_signals": missing, "scoring_version": "module-four-v1", "as_of_year": as_of_year})
    return sorted(result, key=lambda item: (-item["score"], item["paper"]["id"]))
