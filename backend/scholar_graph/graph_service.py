"""Graph transport view assembled from frozen records, with a final publication gate."""

from .citation_graph import citation_edges, graph_nodes
from .errors import PipelineError
from .future_work import filter_future_work


def _assemble(bundles, gate):
    edges, unresolved, identity = citation_edges(bundles, gate, with_evidence=True)
    nodes, layers, diagnostics = graph_nodes(bundles, edges, gate)
    return {"nodes": nodes, "edges": edges, "layers": layers,
            "future_work": filter_future_work(bundles, edges, gate),
            "diagnostics": {"unresolved_references": unresolved, "pagerank": diagnostics, **identity}}


def validate_graph(value, bundles, gate):
    # Recompute from immutable loaded records: returned metadata, links, scores, years,
    # source quotations and resolution decisions must all agree, not just fit a schema.
    if value != _assemble(bundles, gate):
        raise PipelineError("VALIDATION_ERROR", "图谱输出与真实记录、锚点、排名或时间过滤不一致。")


def build_graph(bundles, gate):
    value = _assemble(bundles, gate)
    validate_graph(value, bundles, gate)
    return value
