"""Graph transport view assembled from frozen records, with a final publication gate."""

from .citation_graph import citation_edges, graph_nodes
from .errors import PipelineError
from .future_work import filter_future_work
import copy,hashlib,json,threading,weakref
from collections import OrderedDict

_caches=weakref.WeakKeyDictionary()
_cache_lock=threading.RLock()


def _assemble(bundles, gate, year_bases=None, bibliography_fallback=False):
    edges, unresolved, identity = citation_edges(bundles, gate, with_evidence=True, year_bases=year_bases,bibliography_fallback=bibliography_fallback)
    nodes, layers, diagnostics = graph_nodes(bundles, edges, gate)
    return {"nodes": nodes, "edges": edges, "layers": layers,
            "future_work": filter_future_work(bundles, edges, gate),
            "diagnostics": {"unresolved_references": unresolved, "pagerank": diagnostics, **identity}}


def validate_graph(value, bundles, gate, year_bases=None, *, bibliography_fallback=False):
    # Recompute from immutable loaded records: returned metadata, links, scores, years,
    # source quotations and resolution decisions must all agree, not just fit a schema.
    if value != _assemble(bundles, gate, year_bases,bibliography_fallback):
        raise PipelineError("VALIDATION_ERROR", "图谱输出与真实记录、锚点、排名或时间过滤不一致。")


def build_graph(bundles, gate, *, year_bases=None, bibliography_fallback=False):
    # Cache only fully validated output under the entire effective input content.
    # Corrections, references, anchors and chronology all change the key.
    key=hashlib.sha256(json.dumps({'bundles':sorted(bundles,key=lambda b:b['paper_meta']['id']),
        'year_bases':year_bases,'bibliography_fallback':bibliography_fallback},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    with _cache_lock:
        cache=_caches.setdefault(gate,OrderedDict())
        if key in cache:
            cache.move_to_end(key)
            return copy.deepcopy(cache[key])
    value = _assemble(bundles, gate, year_bases,bibliography_fallback)
    validate_graph(value, bundles, gate, year_bases,bibliography_fallback=bibliography_fallback)
    with _cache_lock:
        # At most two <=100-paper graphs per contract gate; callers get copies.
        cache[key]=copy.deepcopy(value)
        while len(cache)>2:cache.popitem(last=False)
    return value
