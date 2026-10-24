import copy

import pytest
from fastapi.testclient import TestClient

from scholar_graph.api import create_app
from scholar_graph.errors import PipelineError
from scholar_graph.qa import QuestionAnswerer
from scholar_graph.qa_compare import compare_papers, validate_comparison
from scholar_graph.validation import ContractGate
from test_dedup import versions


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("SCHOLAR_GRAPH_QA_MODE", "extractive")


@pytest.fixture
def api(tmp_path):
    app = create_app(data_dir=tmp_path)
    bundles = versions()
    for bundle in bundles:
        app.state.repository.store.paper(bundle)
    return TestClient(app), app, bundles


def test_evidence_table_first_anchored_per_paper_then_synthesis(api):
    client, _, bundles = api
    response = client.post("/api/v1/compare", json={"paper_ids": [b["paper_meta"]["id"] for b in bundles],
                                                       "question": "How many samples?"})
    assert response.status_code == 200, response.text
    value = response.json()
    assert list(value) == ["evidence_table", "per_paper", "synthesis"]
    assert len(value["per_paper"]) == len(value["evidence_table"]) == 2
    assert "12 samples" in value["per_paper"][0]["answer"]
    assert "18 samples" in value["per_paper"][1]["answer"]
    assert "[E1]" in value["synthesis"] and "[E2]" in value["synthesis"]
    assert "不可验证" in value["synthesis"]  # No fabricated ranking or causality.
    validate_comparison(value, bundles, ContractGate())


def test_partial_and_all_refusals_do_not_fabricate_absence(api):
    client, _, bundles = api
    ids = [b["paper_meta"]["id"] for b in bundles]
    value = client.post("/api/v1/compare", json={"paper_ids": ids, "question": "What is the F1 score?"}).json()
    assert all(record["refused"] for record in value["per_paper"])
    assert value["evidence_table"] == [] and value["synthesis"].startswith("不可验证")
    assert "没有报告" not in value["synthesis"]
    # One source has an explicit negative efficiency statement; the other does not.
    first, second = copy.deepcopy(bundles)
    first["chunks"][0]["text"] = "We did not evaluate inference efficiency."
    value = compare_papers([first, second], "What is inference efficiency?", QuestionAnswerer(ContractGate()))
    assert [record["refused"] for record in value["per_paper"]] == [False, True]
    assert len(value["evidence_table"]) == 1 and "不可验证" in value["synthesis"]


@pytest.mark.parametrize("body", [
    {"paper_ids": [], "question": "what?"},
    {"paper_ids": ["one"], "question": "what?"},
    {"paper_ids": ["one", "one"], "question": "what?"},
    {"paper_ids": ["one", "two"], "question": " "},
    {"paper_ids": ["one", "two"], "question": "what?", "synthesis": "injected"},
    {"paper_ids": [str(i) for i in range(11)], "question": "what?"},
])
def test_invalid_compare_requests(api, body):
    response = api[0].post("/api/v1/compare", json=body)
    assert response.status_code == 422 and set(response.json()) == {"error_code", "message", "details"}


def test_missing_paper_returns_404_before_any_partial_comparison(api):
    response = api[0].post("/api/v1/compare", json={"paper_ids": [api[2][0]["paper_meta"]["id"], "missing"], "question": "How many samples?"})
    assert response.status_code == 404 and response.json()["error_code"] == "PAPER_NOT_FOUND"


@pytest.mark.parametrize("damage", ["invented_fact", "missing_cite", "wrong_quote", "wrong_anchor", "unbound_row", "duplicate_row"])
def test_comparison_gate_rejects_unbound_or_irrelevant_synthesis(damage):
    bundles = versions()
    gate = ContractGate()
    value = compare_papers(bundles, "How many samples?", QuestionAnswerer(gate))
    if damage == "invented_fact":
        value["synthesis"] += "\nThe second paper proves causal superiority. [E1]"
    elif damage == "missing_cite":
        value["synthesis"] = value["synthesis"].replace("[E1]", "")
    elif damage == "wrong_quote":
        value["evidence_table"][0]["quotes"] = ["The study uses 9000 samples."]
    elif damage == "wrong_anchor":
        value["evidence_table"][0]["anchor"]["page_number"] = 2
    elif damage == "unbound_row":
        value["evidence_table"][0]["per_paper_index"] = 1
    else:
        value["evidence_table"].append(copy.deepcopy(value["evidence_table"][0]))
    with pytest.raises(PipelineError):
        validate_comparison(value, bundles, gate)


def test_synthesis_is_not_executed_until_all_per_paper_gates_pass(monkeypatch):
    calls = []
    class BrokenAnswerer(QuestionAnswerer):
        def answer(self, bundle, question):
            calls.append("answer")
            if len(calls) == 2:
                raise PipelineError("VALIDATION_ERROR", "第二篇证据未通过门禁。")
            return super().answer(bundle, question)
    monkeypatch.setattr("scholar_graph.qa_compare.synthesis_from_table", lambda *a, **k: calls.append("synthesis"))
    with pytest.raises(PipelineError):
        compare_papers(versions(), "How many samples?", BrokenAnswerer(ContractGate()))
    assert calls == ["answer", "answer"]
