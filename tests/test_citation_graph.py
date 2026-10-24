import copy

import pytest
from scholar_graph.citation_graph import citation_edges, graph_nodes, pagerank
from scholar_graph.errors import PipelineError
from scholar_graph.validation import ContractGate
from graph_samples import graph_bundles


def test_known_chain_rank_has_analytic_solution_and_isolate():
    bundles, gate = graph_bundles(), ContractGate()
    edges, unresolved = citation_edges(bundles, gate)
    assert len(edges) == 2 and unresolved == []
    nodes, layers, diagnostics = graph_nodes(bundles, edges, gate)
    d = 0.85
    base = 1 / (4 + 2 * d + d * d)
    expected = [base, (1 + d) * base, (1 + d + d * d) * base, base]
    assert [node["pagerank"] for node in nodes] == pytest.approx(expected, abs=1e-11)
    assert sum(node["pagerank"] for node in nodes) == pytest.approx(1)
    assert layers == {"cornerstone": ["paper-graph-c", "paper-graph-b"], "derived": ["paper-graph-a"], "isolated": ["paper-graph-d"]}
    assert diagnostics["residual"] <= 1e-12


def test_missing_citation_link_yields_unverified_edge_not_rank_evidence():
    bundles, gate = graph_bundles(), ContractGate()
    bundles[1]["citation_links"] = []
    edges, _ = citation_edges(bundles, gate)
    assert edges[1]["status"] == "unverified" and edges[1]["anchor"] is None
    nodes, _, stats = graph_nodes(bundles, edges, gate)
    assert stats["verified_pair_count"] == 1
    assert next(node for node in nodes if node["paper_id"] == "paper-graph-c")["level"] == "isolated"


@pytest.mark.parametrize("damage", ["paper", "page", "chunk", "ref"])
def test_invalid_citation_foreign_keys_cannot_create_edges(damage):
    bundles = graph_bundles()
    key, value = {"paper": ("paper_id", "wrong"), "page": ("page_number", 2),
                  "chunk": ("chunk_id", "missing"), "ref": ("ref_id", "missing")}[damage]
    bundles[0]["citation_links"][0][key] = value
    with pytest.raises(PipelineError):
        citation_edges(bundles, ContractGate())


def test_ambiguous_doi_and_conflicting_identity_are_not_guessed():
    bundles = graph_bundles()
    bundles[3]["paper_meta"]["doi"] = bundles[1]["paper_meta"]["doi"]
    edges, unresolved = citation_edges(bundles, ContractGate())
    assert len(edges) == 1 and unresolved[0]["reason"] == "ambiguous_identity"
    bundles = graph_bundles()
    bundles[0]["reference_entries"][0]["doi"] = "10.5555/not-in-selection"
    edges, unresolved = citation_edges(bundles, ContractGate())
    assert len(edges) == 1 and unresolved[0]["reason"] == "not_in_selection"


def test_duplicate_citation_occurrences_do_not_inflate_rank():
    bundles, gate = graph_bundles(), ContractGate()
    other = copy.deepcopy(bundles[0]["chunks"][0])
    other["chunk_id"] += "-second"
    bundles[0]["chunks"].append(other)
    link = {**bundles[0]["citation_links"][0], "chunk_id": other["chunk_id"]}
    bundles[0]["citation_links"].append(link)
    edges, _ = citation_edges(bundles, gate)
    assert len(edges) == 3
    assert graph_nodes(bundles, edges, gate)[2]["verified_pair_count"] == 2


def test_empty_bad_endpoint_or_nonconvergent_rank_returns_error():
    for ids, pairs, kwargs in [([], [], {}), (["a"], [("a", "missing")], {}),
                              (["a", "b"], [("a", "b")], {"max_iterations": 1})]:
        with pytest.raises(PipelineError):
            pagerank(ids, pairs, **kwargs)


def test_single_isolate_and_cycle_have_normalized_uniform_rank():
    assert pagerank(["a"], [])[0] == {"a": 1.0}
    values, _ = pagerank(["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a")])
    assert list(values.values()) == pytest.approx([1 / 3] * 3)
