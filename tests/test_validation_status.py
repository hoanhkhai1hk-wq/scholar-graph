import copy
import json
from pathlib import Path

import pytest

from scholar_graph.errors import PipelineError
from scholar_graph.status import ParseJob
from scholar_graph.validation import ContractGate, chunk_anchor

ROOT = Path(__file__).resolve().parents[1]


def example_bundle():
    def read(slug):
        return json.loads((ROOT / "contracts" / f"{slug}.v1.example.json").read_text(encoding="utf-8"))
    return {"paper_meta": read("paper-meta"), "chunks": [read("chunk")],
            "reference_entries": [read("reference-entry")], "citation_links": [read("citation-link")]}


@pytest.mark.parametrize("bad_field", ["paper_id", "page_number", "section", "chunk_id"])
def test_anchor_foreign_key_fields(bad_field):
    bundle = example_bundle()
    anchor = chunk_anchor(bundle["chunks"][0])
    anchor[bad_field] = {"paper_id": "other-paper", "page_number": 2,
                         "section": ["Unknown"], "chunk_id": "absent-chunk"}[bad_field]
    with pytest.raises(PipelineError):
        ContractGate().anchor(anchor, [bundle])


def test_valid_anchor_and_exact_quote():
    bundle = example_bundle()
    gate = ContractGate()
    gate.bundle(bundle)
    anchor = chunk_anchor(bundle["chunks"][0])
    gate.anchor(anchor, [bundle], quote="12 samples")
    with pytest.raises(PipelineError):
        gate.anchor(anchor, [bundle], quote="18 samples")


@pytest.mark.parametrize("damage", ["heading", "bbox", "link", "duplicate", "doi", "nan"])
def test_bundle_semantic_gate(damage):
    bundle = example_bundle()
    if damage == "heading":
        bundle["chunks"][0]["heading_1"] = "Unrelated"
    elif damage == "bbox":
        bundle["chunks"][0]["bbox"] = [0.9, 0.1, 0.2, 0.8]
    elif damage == "link":
        bundle["citation_links"][0]["ref_id"] = "missing-ref"
    elif damage == "duplicate":
        bundle["chunks"].append(copy.deepcopy(bundle["chunks"][0]))
    elif damage == "doi":
        bundle["paper_meta"]["doi"] = "https://doi.org/10.5555/demo"
    elif damage == "nan":
        bundle["chunks"][0]["bbox"][0] = float("nan")
    with pytest.raises(PipelineError):
        ContractGate().bundle(bundle)


@pytest.mark.parametrize("needs_ocr", [False, True])
def test_status_success_and_terminal_state(needs_ocr):
    published = []
    job = ParseJob("paper-test", ContractGate(), published.append)
    job.move("parsing", "本地解析", progress=10)
    if needs_ocr:
        job.move("ocr", "OCR", progress=40)
    job.move("indexing", "验证锚点", progress=80)
    job.move("completed", "完成")
    assert job.current["progress"] == 100
    assert job.current["error_code"] is None
    assert len(published) == len(job.history)
    with pytest.raises(PipelineError):
        job.move("failed", "非法迁移", error=PipelineError("PARSE_FAILED", "失败"))


def test_failure_retains_progress_and_closed_error_codes():
    job = ParseJob("paper-test", ContractGate())
    job.move("parsing", "解析", progress=10)
    job.move("failed", "失败", error=PipelineError("PARSE_FAILED", "安全错误说明"))
    assert job.current["progress"] == 10
    assert job.current["error_code"] == "PARSE_FAILED"
    assert job.current["error_message"]


@pytest.mark.parametrize("target,progress", [("completed", 100), ("ocr", 50), ("parsing", 100), ("parsing", -1)])
def test_invalid_state_or_progress_not_published(target, progress):
    job = ParseJob("paper-test", ContractGate())
    before = copy.deepcopy(job.history)
    with pytest.raises(PipelineError):
        job.move(target, "非法", progress=progress)
    assert job.history == before
