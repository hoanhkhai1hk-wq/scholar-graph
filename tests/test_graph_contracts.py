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
