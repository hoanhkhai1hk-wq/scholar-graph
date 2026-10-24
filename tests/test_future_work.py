import copy

import pytest
from scholar_graph.citation_graph import citation_edges
from scholar_graph.future_work import filter_future_work
from scholar_graph.graph_service import build_graph, validate_graph
from scholar_graph.errors import PipelineError
from scholar_graph.validation import ContractGate
from graph_samples import graph_bundles


def test_later_explicit_citing_resolution_excludes_only_supported_direction():
    bundles, gate = graph_bundles(), ContractGate()
    graph = build_graph(bundles, gate)
    result = graph["future_work"]
    assert len(result["excluded"]) == 1 and len(result["worth_exploring"]) == 2
    assert result["excluded"][0]["topic"] == "cross-lingual transfer"
    assert {item["topic"] for item in result["worth_exploring"]} == {"document-level extraction", "robust noisy labels"}
    entry = result["excluded"][0]
    assert entry["source"]["anchors"][0]["paper_id"] == "paper-graph-c"
    assert entry["resolutions"][0]["anchors"][0]["paper_id"] == "paper-graph-b"
    assert result["checks"][0]["decision"] == "accepted"


@pytest.mark.parametrize("year", [2017, 2018])
def test_earlier_or_same_year_cannot_resolve_future_work(year):
    bundles, gate = graph_bundles(), ContractGate()
    bundles[1]["paper_meta"]["year"] = year
    result = build_graph(bundles, gate)["future_work"]
    assert result["excluded"] == [] and len(result["worth_exploring"]) == 3
    assert result["checks"][0]["reason"] == "not_strictly_later"


@pytest.mark.parametrize("paper_index", [1, 2])
def test_unknown_year_does_not_pretend_unresolved_or_resolved(paper_index):
    bundles, gate = graph_bundles(), ContractGate()
    bundles[paper_index]["paper_meta"]["year"] = None
    result = build_graph(bundles, gate)["future_work"]
    assert result["excluded"] == [] and result["unverifiable"]


def test_no_verified_citation_no_exclusion_even_if_topic_and_year_match():
    bundles, gate = graph_bundles(), ContractGate()
    bundles[1]["citation_links"] = []
    result = build_graph(bundles, gate)["future_work"]
    assert result["excluded"] == [] and len(result["worth_exploring"]) == 3
    assert result["checks"][0]["reason"] == "no_verified_citation_in_resolution_chunk"


@pytest.mark.parametrize("text", [
    "We did not resolve cross-lingual transfer.",
    "We plan to resolve cross-lingual transfer.",
    "Resolved future direction: cross-lingual.",
])
def test_negation_plans_or_partial_topic_match_do_not_claim_resolution(text):
    bundles = graph_bundles()
    bundles[1]["chunks"][0]["text"] = text + "\nWe cite the old paper [1]."
    result = build_graph(bundles, ContractGate())["future_work"]
    assert len(result["worth_exploring"]) == 3 and result["excluded"] == []


def test_resolution_in_uncited_chunk_does_not_borrow_another_chunk_anchor():
    bundles = graph_bundles()
    other = copy.deepcopy(bundles[1]["chunks"][0])
    other["chunk_id"] += "-uncited"
    bundles[1]["chunks"][0]["text"] = "We cite the old paper [1]."
    bundles[1]["chunks"].append(other)
    assert build_graph(bundles, ContractGate())["future_work"]["excluded"] == []


@pytest.mark.parametrize("damage", ["invented_node", "wrong_rank", "wrong_page", "fake_quote", "wrong_resolution", "extra_field"])
def test_final_graph_gate_rejects_false_records_and_evidence(damage):
    bundles, gate = graph_bundles(), ContractGate()
    value = build_graph(bundles, gate)
    if damage == "invented_node":
        value["nodes"][0]["paper_id"] = "not-selected"
    elif damage == "wrong_rank":
        value["nodes"][0]["pagerank"] = 0.99
    elif damage == "wrong_page":
        value["edges"][0]["anchor"]["page_number"] = 2
    elif damage == "fake_quote":
        value["future_work"]["excluded"][0]["source"]["answer"] = "Invented future work."
    elif damage == "wrong_resolution":
        value["future_work"]["excluded"][0]["resolutions"][0]["anchors"][0]["paper_id"] = "paper-graph-d"
    else:
        value["nodes"][0]["extra"] = True
    with pytest.raises(PipelineError):
        validate_graph(value, bundles, gate)
