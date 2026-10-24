import copy
import json
from pathlib import Path
import pytest
from scholar_graph.validation import ContractGate
from scholar_graph.errors import PipelineError

ROOT = Path(__file__).resolve().parents[1]


def test_outline_all_nested_fields_required_and_no_extra_properties():
    schema = json.loads((ROOT / "contracts/framework-outline.v1.2.schema.json").read_text(encoding="utf-8"))
    example = json.loads((ROOT / "contracts/framework-outline.v1.2.example.json").read_text(encoding="utf-8"))
    gate = ContractGate()
    gate.record("FrameworkOutline", example)
    def walk(node):
        if node.get("type") == "object":
            assert set(node["properties"]) == set(node["required"])
            assert node["additionalProperties"] is False
        for value in node.values():
            if isinstance(value, dict):
                walk(value)
    walk(schema)
    for location in ((), ("chapters", 0), ("chapters", 0, "writing_points", 0), ("chapters", 0, "anchors", 0)):
        target = example
        for key in location:
            target = target[key]
        for key in (*target, "extra"):
            bad = copy.deepcopy(example)
            part = bad
            for segment in location:
                part = part[segment]
            if key == "extra":
                part[key] = True
            else:
                del part[key]
            with pytest.raises(PipelineError):
                gate.record("FrameworkOutline", bad)


def test_framework_example_uses_existing_real_example_anchor_and_quote():
    from test_validation_status import example_bundle
    value = json.loads((ROOT / "contracts/framework-outline.v1.2.example.json").read_text(encoding="utf-8"))
    for point in value["chapters"][0]["writing_points"]:
        ContractGate().anchor(point["anchor"], [example_bundle()], quote=point["text"])
