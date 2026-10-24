import copy
import json
from pathlib import Path

import pytest
from scholar_graph.errors import PipelineError
from scholar_graph.validation import ContractGate

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("slug,kind", [("graph-node", "GraphNode"), ("graph-edge", "GraphEdge")])
def test_graph_contract_all_fields_required_and_no_extras(slug, kind):
    schema = json.loads((ROOT / "contracts" / f"{slug}.v1.2.schema.json").read_text(encoding="utf-8"))
    example = json.loads((ROOT / "contracts" / f"{slug}.v1.2.example.json").read_text(encoding="utf-8"))
    gate = ContractGate()
    gate.record(kind, example)
    assert set(schema["properties"]) == set(schema["required"]) == set(example)
    assert schema["additionalProperties"] is False
    for field in example:
        bad = copy.deepcopy(example)
        del bad[field]
        with pytest.raises(PipelineError):
            gate.record(kind, bad)
    with pytest.raises(PipelineError):
        gate.record(kind, {**example, "extra": True})


def test_graph_edge_missing_anchor_must_be_unverified():
    edge = json.loads((ROOT / "contracts/graph-edge.v1.2.example.json").read_text(encoding="utf-8"))
    gate = ContractGate()
    with pytest.raises(PipelineError):
        gate.record("GraphEdge", {**edge, "anchor": None})
    gate.record("GraphEdge", {**edge, "anchor": None, "status": "unverified"})
    with pytest.raises(PipelineError):
        gate.record("GraphEdge", {**edge, "status": "unverified"})


def test_new_examples_align_with_existing_paper_and_chunk_examples():
    def read(name):
        return json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))
    paper, chunk = read("paper-meta.v1.example.json"), read("chunk.v1.example.json")
    node, edge = read("graph-node.v1.2.example.json"), read("graph-edge.v1.2.example.json")
    assert (node["paper_id"], node["title"], node["year"]) == (paper["id"], paper["title"], paper["year"])
    assert edge["anchor"] == {"paper_id": chunk["paper_id"], "page_number": chunk["page_number"],
                              "section": chunk["section_path"], "chunk_id": chunk["chunk_id"]}
