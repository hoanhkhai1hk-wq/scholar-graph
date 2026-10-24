import base64
import copy
import json
import pytest
from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.charts import generate_chart, validate_chart, MAX_BYTES
from scholar_graph.errors import PipelineError
from scholar_graph.validation import ContractGate
from test_api_read import assert_error

CSV = b"step,samples\n1,12\n2,18\n"


@pytest.mark.parametrize("kind,x", [("line", "step"), ("bar", None), ("scatter", "step"), ("histogram", None)])
def test_all_chart_types_have_real_png_exact_series_and_csv_cell_checks(kind, x):
    gate = ContractGate()
    value = generate_chart(CSV, kind, ["samples"], x, None, gate)
    gate.record("ChartOutput", value)
    assert value["series"][-1] == {"name": "samples", "values": [12, 18]}
    assert base64.b64decode(value["image_ref"].split(",", 1)[1]).startswith(b"\x89PNG\r\n\x1a\n")
    sample_checks = [check for check in value["numeric_checks"] if check["csv_anchor"]["column_name"] == "samples"]
    assert [check["csv_anchor"]["row_number"] for check in sample_checks] == [2, 3]
    assert [check["value"] for check in sample_checks] == [12, 18]
    assert all(check["verified"] for check in value["numeric_checks"])


@pytest.mark.parametrize("raw", [b"", b"x\n", b"x,x\n1,2\n", b"x,y\n1\n", b'"x\n1', b"x\n\xff",
    b"x\nNaN\n", b"x\nInf\n", b"x\n12%\n", b"x\n1e309\n", b"x\n0.1234567890123456789\n",
    b"x\n\x00\n", b" x\n1\n", b"x\n1\n\n", pytest.param(b"x" * (MAX_BYTES + 1), id="oversize-csv")])
def test_invalid_csv_never_returns_fabricated_chart(raw):
    with pytest.raises(PipelineError) as caught:
        generate_chart(raw, "bar", ["x"], None, None, ContractGate())
    assert caught.value.code == "CSV_INVALID"


@pytest.mark.parametrize("kind,columns,x,caption", [
    ("pie", ["samples"], None, None), ("bar", ["missing"], None, None),
    ("scatter", ["samples"], None, None), ("histogram", ["samples"], "step", None),
    ("bar", ["samples", "samples"], None, None),
    ("bar", ["samples"], None, "CSV values: 999."),
    ("bar", ["samples"], None, "CSV values: 12%."),
    ("bar", ["samples"], None, "共两组数据"), ("bar", ["samples"], None, "Samples increased by 6."),
])
def test_unsupported_config_and_untraced_caption_are_chart_validation_failures(kind, columns, x, caption):
    with pytest.raises(PipelineError) as caught:
        generate_chart(CSV, kind, columns, x, caption, ContractGate())
    assert caught.value.code == "CHART_VALIDATION_FAILED"


@pytest.mark.parametrize("damage", ["value", "cell", "verified", "caption", "image", "extra"])
def test_publication_gate_rejects_forged_series_anchor_check_caption_or_image(damage):
    gate = ContractGate()
    value = generate_chart(CSV, "bar", ["samples"], None, None, gate)
    if damage == "value":
        value["series"][0]["values"][0] = 99
    elif damage == "cell":
        value["numeric_checks"][0]["csv_anchor"]["row_number"] = 3
    elif damage == "verified":
        value["numeric_checks"][0]["verified"] = False
    elif damage == "caption":
        value["caption"] = "CSV values: 999."
    elif damage == "image":
        value["image_ref"] = "charts/missing.png"
    else:
        value["extra"] = "unapproved"
    with pytest.raises(PipelineError) as caught:
        validate_chart(value, CSV, "bar", ["samples"], None, gate)
    assert caught.value.code == "CHART_VALIDATION_FAILED"


def test_csv_endpoint_returns_frozen_record_and_uniform_error_codes(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))
    def post(raw=CSV, **fields):
        return client.post("/api/v1/charts/csv", files={"file": ("synthetic.csv", raw, "text/csv")},
                           data={"value_columns": json.dumps(["samples"]), **fields})
    response = post()
    assert response.status_code == 200
    assert response.json()["caption"] == "CSV values: 12, 18."
    assert set(response.json()) == {"schema_version", "chart_id", "chart_type", "series", "image_ref", "caption", "numeric_checks"}
    assert_error(post(raw=b"broken"), 422, "CSV_INVALID")
    assert_error(post(caption="CSV values: 999."), 422, "CHART_VALIDATION_FAILED")
    assert_error(post(value_columns="not JSON"), 422, "CHART_VALIDATION_FAILED")


def test_negative_decimal_scientific_notation_and_bom_are_exactly_traced():
    raw = b"\xef\xbb\xbfx\n-1.5\n1e-3\n"
    value = generate_chart(raw, "line", ["x"], None, None, ContractGate())
    assert value["series"][0]["values"] == [-1.5, .001]
    assert value["caption"] == "CSV values: -1.5, 1e-3."
