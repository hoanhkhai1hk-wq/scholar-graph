import copy
import pytest
from fastapi.testclient import TestClient
from graph_samples import graph_bundles
from scholar_graph.api import create_app
from scholar_graph.frameworks import generate_outline
from scholar_graph.reviews import generate_review, validate_review, MISSING_POINT
from scholar_graph.validation import ContractGate
from scholar_graph.errors import PipelineError
from test_api_read import assert_error


def prepared():
    bundles, gate = graph_bundles(), ContractGate()
    return bundles, gate, generate_outline(bundles, gate)


def test_review_is_exact_anchored_quotes_and_missing_requests_are_unverifiable():
    bundles, gate, outline = prepared()
    result = generate_review(bundles, outline, ["zzzzquantumteleportation"], gate)
    assert result["mode"] == "extractive" and result["unverifiable_count"] == 4
    for chapter in result["chapters"]:
        for point in chapter["points"]:
            if point["status"] == "verified":
                gate.anchor(point["anchors"][0], bundles, quote=point["text"])
            else:
                assert point["text"] == MISSING_POINT and point["anchors"] == []


def test_future_requirements_cannot_reintroduce_excluded_topic_from_same_chunk():
    bundles, gate, outline = prepared()
    result = generate_review(bundles, outline, ["cross-lingual transfer"], gate)
    future = result["chapters"][-1]
    assert future["points"][-1]["status"] == "unverifiable"
    assert all("cross-lingual" not in point["text"] for point in future["points"])


def test_numeric_quote_reuses_qa_numeric_gate():
    bundles, gate, outline = prepared()
    bundles[3]["chunks"][0]["text"] = "The synthetic experiment uses 12 samples."
    outline = generate_outline(bundles, gate)
    result = generate_review(bundles, outline, [], gate)
    point = next(chapter for chapter in result["chapters"] if "isolated" in chapter["chapter_id"])["points"][0]
    assert point["numeric_fact_check"]["status"] == "passed"
    assert point["numeric_fact_check"]["checks"][0]["evidence"] == point["anchors"]


@pytest.mark.parametrize("damage", ["quote", "anchor", "status", "count"])
def test_review_gate_rejects_fabricated_text_or_evidence(damage):
    bundles, gate, outline = prepared()
    result = generate_review(bundles, outline, ["zzzzmissing"], gate)
    point = result["chapters"][0]["points"][0]
    if damage == "quote":
        point["text"] = "Invented result."
    elif damage == "anchor":
        point["anchors"][0]["page_number"] = 99
    elif damage == "status":
        result["chapters"][0]["points"][-1]["status"] = "verified"
    else:
        result["unverifiable_count"] = 0
    with pytest.raises(PipelineError):
        validate_review(result, bundles, outline, ["zzzzmissing"], gate)


def test_reviews_endpoint_uses_supplied_framework_and_rejects_tampering(tmp_path):
    app = create_app(data_dir=tmp_path)
    bundles, gate, outline = prepared()
    for bundle in bundles:
        app.state.repository.store.paper(bundle)
    client = TestClient(app)
    body = {"paper_ids": outline["paper_ids"], "framework": outline, "requirements": ["zzzzmissing"]}
    response = client.post("/api/v1/reviews", json=body)
    assert response.status_code == 200 and response.json()["unverifiable_count"] == 4
    bad = copy.deepcopy(body)
    bad["framework"]["chapters"][0]["writing_points"][0]["text"] = "Unsupported assertion."
    assert_error(client.post("/api/v1/reviews", json=bad), 422, "VALIDATION_ERROR")
    bad = copy.deepcopy(body)
    bad["paper_ids"] = ["missing"]
    assert_error(client.post("/api/v1/reviews", json=bad), 404, "PAPER_NOT_FOUND")
