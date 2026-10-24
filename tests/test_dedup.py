import copy
import json

import pytest

from sample_pdfs import make_pdf
from scholar_graph.dedup import compare, human_decision
from scholar_graph.errors import PipelineError
from scholar_graph.pipeline import Pipeline
from scholar_graph.storage import RecordStore
from scholar_graph.validation import ContractGate
from test_validation_status import example_bundle


def versions():
    old = example_bundle()
    new = copy.deepcopy(old)
    new["paper_meta"].update(id="paper-version-seven", version="v7", file_hash="7" * 64)
    new["chunks"][0].update(paper_id="paper-version-seven", chunk_id="chunk-v7", text="The synthetic study contains 18 samples and cites [1].")
    new["reference_entries"][0].update(paper_id="paper-version-seven", ref_id="ref-v7")
    new["citation_links"][0].update(paper_id="paper-version-seven", chunk_id="chunk-v7", ref_id="ref-v7")
    return old, new


def test_different_versions_are_not_automatically_ranked():
    old, new = versions()
    decision, diff = compare(old, new, ContractGate())
    assert 0 <= decision["similarity"] <= 1
    assert decision["recommendation"] == "manual_review"
    assert diff["changed_sections"]
    assert diff["key_sentences"][0]["text"] == new["chunks"][0]["text"]
    assert diff["key_sentences"][0]["status"] == "verified"


def test_identical_content_is_redundant_not_a_new_quality_claim():
    old, new = versions()
    new["chunks"][0]["text"] = old["chunks"][0]["text"]
    decision, diff = compare(old, new, ContractGate())
    assert decision["recommendation"] == "keep_old" and decision["similarity"] == 1
    assert diff["changed_sections"] == []
    assert "未检出章节级差异" in diff["summary_text"]


@pytest.mark.parametrize("choice", ["keep_new", "keep_old", "keep_both", "manual_review"])
def test_human_override_keeps_system_recommendation_immutable(tmp_path, choice):
    old, new = versions()
    gate = ContractGate()
    decision, diff = compare(old, new, gate)
    snapshot = copy.deepcopy(decision)
    human = human_decision(decision, choice, "自制人工意见：核对新版协议后选择。", diff, [old, new], gate)
    target = RecordStore(tmp_path / "output", gate).comparison(decision, diff, [old, new], human=human)
    history = json.loads((target / "dedup-decisions.json").read_text(encoding="utf-8"))
    assert decision == snapshot == history[0]
    assert history[1]["human_override"] and history[1]["recommendation"] == choice


@pytest.mark.parametrize("damage", ["missing_chunk", "wrong_page", "wrong_section", "fabricated_quote", "null_verified"])
def test_invalid_comparison_never_published(tmp_path, damage):
    old, new = versions()
    gate = ContractGate()
    decision, diff = compare(old, new, gate)
    if damage == "missing_chunk":
        decision["evidence"][0]["anchor"]["chunk_id"] = "missing"
    elif damage == "wrong_page":
        diff["key_sentences"][0]["anchor"]["page_number"] = 2
    elif damage == "wrong_section":
        diff["key_sentences"][0]["anchor"]["section"] = ["Unrelated"]
    elif damage == "fabricated_quote":
        diff["key_sentences"][0]["text"] = "The study contains 9000 samples."
    else:
        diff["key_sentences"][0]["anchor"] = None
    store = RecordStore(tmp_path / "output", gate)
    with pytest.raises(PipelineError):
        store.comparison(decision, diff, [old, new])
    assert not store.root.exists()


def test_unanchored_unverified_sentence_is_not_claimed_verified():
    old, new = versions()
    gate = ContractGate()
    decision, diff = compare(old, new, gate)
    diff["key_sentences"].append({"text": "Unlocated claim.", "anchor": None, "status": "unverified"})
    gate.comparison(decision, diff, [old, new])


def test_actual_v1_to_v7_parse_compare_and_publish(tmp_path):
    pipeline = Pipeline(tmp_path / "output")
    old = pipeline.parse(make_pdf(tmp_path / "v1.pdf"))
    assert pipeline.last_comparison is None
    new = pipeline.parse(make_pdf(tmp_path / "v7.pdf", version="v7", samples=18))
    assert pipeline.last_comparison is not None
    automatic = json.loads((pipeline.last_comparison / "dedup-decisions.json").read_text(encoding="utf-8"))
    assert automatic[0]["old_paper_id"] == old["paper_meta"]["id"]
    assert automatic[0]["new_paper_id"] == new["paper_meta"]["id"]
    decision, diff = compare(old, new, pipeline.gate)
    target = pipeline.store.comparison(decision, diff, [old, new])
    assert "2 Protocol" in diff["changed_sections"]
    chunks = {c["chunk_id"]: c for bundle in [old, new] for c in bundle["chunks"]}
    assert "12 samples" in chunks[decision["evidence"][0]["anchor"]["chunk_id"]]["text"]
    assert "18 samples" in chunks[decision["evidence"][1]["anchor"]["chunk_id"]]["text"]
    assert any("additional controls" in item["text"] for item in diff["key_sentences"])
    assert (target / "diff-summary.json").exists()
    pipeline.gate.comparison(decision, diff, [old, new])


def test_conflicting_dois_do_not_auto_pair_same_titles(tmp_path):
    old, new = versions()
    old["paper_meta"]["doi"] = "10.5555/old-paper"
    new["paper_meta"]["doi"] = "10.5555/another-paper"
    store = RecordStore(tmp_path / "output", ContractGate())
    store.paper(old)
    assert store.previous_version(new["paper_meta"]) is None
