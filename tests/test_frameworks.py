import copy
import pytest
from fastapi.testclient import TestClient
from graph_samples import graph_bundles
from scholar_graph.api import create_app
from scholar_graph.frameworks import generate_outline, validate_outline
from scholar_graph.validation import ContractGate
from scholar_graph.errors import PipelineError
from test_api_read import assert_error


def test_cornerstones_derivatives_isolate_and_filtered_future_have_true_anchors():
    bundles, gate = graph_bundles(), ContractGate()
    outline = generate_outline(bundles, gate)
    assert len(outline["chapters"]) == 4
    assert outline["chapters"][1]["paper_ids"] == ["paper-graph-b", "paper-graph-a"]
    assert outline["chapters"][2]["kind"] == "isolated"
    future = outline["chapters"][-1]
    assert future["kind"] == "future_work" and len(future["writing_points"]) == 2
    assert not any("cross-lingual" in point["text"] for point in future["writing_points"])
    for chapter in outline["chapters"]:
        assert set(chapter["paper_ids"]) == {a["paper_id"] for a in chapter["anchors"]}
        for point in chapter["writing_points"]:
            gate.anchor(point["anchor"], bundles, quote=point["text"])


@pytest.mark.parametrize("damage", ["text", "page", "title", "assignment"])
def test_outline_gate_rejects_forged_evidence_and_structure(damage):
    bundles, gate = graph_bundles(), ContractGate()
    value = generate_outline(bundles, gate)
    chapter = value["chapters"][0]
    if damage == "text":
        chapter["writing_points"][0]["text"] = "Invented new scientific conclusion."
    elif damage == "page":
        chapter["writing_points"][0]["anchor"]["page_number"] = 99
    elif damage == "title":
        chapter["title"] = "Unsupported chapter conclusion"
    else:
        chapter["paper_ids"] = ["paper-graph-d"]
    with pytest.raises(PipelineError):
        validate_outline(value, bundles, gate)


def test_no_future_evidence_means_no_future_chapter():
    bundles = graph_bundles()
    bundles[2]["chunks"][0]["text"] = "Synthetic evidence without marked future directions."
    outline = generate_outline(bundles, ContractGate())
    assert all(chapter["kind"] != "future_work" for chapter in outline["chapters"])


def test_single_paper_without_citations_is_an_isolated_chapter():
    bundles = graph_bundles()[:1]
    bundles[0]["reference_entries"] = bundles[0]["citation_links"] = []
    assert generate_outline(bundles, ContractGate())["chapters"][0]["kind"] == "isolated"


def test_uniform_citation_cycle_has_derivative_chapters_without_inventing_cornerstones():
    bundles = graph_bundles()[:2]
    target = bundles[0]["paper_meta"]
    bundles[1]["reference_entries"][0].update(title=target["title"], year=target["year"],
                                             authors=target["authors"], doi=target["doi"])
    outline = generate_outline(bundles, ContractGate())
    assert len(outline["chapters"]) == 2
    assert all(chapter["kind"] == "derived" for chapter in outline["chapters"])
    assert all(len(chapter["paper_ids"]) == 1 for chapter in outline["chapters"])


def test_framework_endpoint_and_uniform_selection_errors(tmp_path):
    app = create_app(data_dir=tmp_path)
    bundles = graph_bundles()
    for bundle in bundles:
        app.state.repository.store.paper(bundle)
    client = TestClient(app)
    ids = [bundle["paper_meta"]["id"] for bundle in bundles]
    response = client.post("/api/v1/frameworks", json={"paper_ids": ids})
    assert response.status_code == 200 and len(response.json()["chapters"]) == 4
    assert_error(client.post("/api/v1/frameworks", json={"paper_ids": ["missing"]}), 404, "PAPER_NOT_FOUND")
    for invalid in ([], [ids[0], ids[0]]):
        assert_error(client.post("/api/v1/frameworks", json={"paper_ids": invalid}), 422, "VALIDATION_ERROR")
