"""Self-made contract corpus and CSV: real HTTP/Matplotlib, no model, key or Docker."""

import argparse
import base64
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
from graph_samples import graph_bundles
from scholar_graph.api import create_app

BASELINE = "aee2853ed9cc8d294860496fef65085046f310aa"


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = args.output_root.resolve()
    check(root.is_relative_to(ROOT / "data") and not root.exists(), "Use a fresh output directory under project data/.")
    root.mkdir(parents=True)
    report = {"scope": "自制样例、非官方 pdf/ 用例；未运行官方三用例。摘录式草稿，不是大模型生成。",
              "run_utc": datetime.now(timezone.utc).isoformat(), "baseline": BASELINE,
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, encoding="utf-8").strip(),
              "real_model_calls": 0, "real_api_keys_used": False, "versions": {name: version(name) for name in ("matplotlib", "fastapi", "jsonschema")},
              "cases": [], "frozen_contracts": []}
    app = create_app(data_dir=root / "records")
    for bundle in graph_bundles():
        app.state.repository.store.paper(bundle)
    before = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob("records/papers/*/*.json")}
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    report["implemented_endpoints"] = [f"{method.upper()} {path}" for path, methods in paths.items() for method in methods]
    check(len(report["implemented_endpoints"]) == 19, "Expected 19/19 implemented business endpoints")
    ids = [bundle["paper_meta"]["id"] for bundle in graph_bundles()]
    def call(name, path, body):
        response = client.post(path, json=body)
        check(response.status_code == 200, "Writing HTTP request failed")
        record = {"name": name, "request": {"method": "POST", "path": path, "body": body},
                  "http_status": response.status_code, "response": response.json()}
        report["cases"].append(record)
        return record
    framework = call("framework", "/api/v1/frameworks", {"paper_ids": ids})
    outline = framework["response"]
    framework["summary"] = {"chapters": len(outline["chapters"]),
        "anchor_occurrences": sum(len(chapter["anchors"]) for chapter in outline["chapters"]),
        "unique_anchors": len({json.dumps(anchor, sort_keys=True) for chapter in outline["chapters"] for anchor in chapter["anchors"]}),
        "unverifiable": 0, "future_directions": len(outline["chapters"][-1]["writing_points"])}
    check(framework["summary"] == {"chapters": 4, "anchor_occurrences": 5, "unique_anchors": 4, "unverifiable": 0, "future_directions": 2}, "Unexpected framework evidence")
    for name, requirements in (("review-extracts", []), ("review-missing", ["zzzzquantumteleportation"])):
        case = call(name, "/api/v1/reviews", {"paper_ids": ids, "framework": outline, "requirements": requirements})
        value = case["response"]
        case["summary"] = {"chapters": len(value["chapters"]), "points": sum(len(chapter["points"]) for chapter in value["chapters"]),
            "anchor_occurrences": sum(len(point["anchors"]) for chapter in value["chapters"] for point in chapter["points"]),
            "unique_anchors": len({json.dumps(anchor, sort_keys=True) for chapter in value["chapters"] for point in chapter["points"] for anchor in point["anchors"]}),
            "unverifiable": value["unverifiable_count"], "mode": value["mode"]}
        check(value["unverifiable_count"] == (4 if requirements else 0), "Unsupported request was filled with invented content")
    raw = b"step,samples\n1,12\n2,18\n"
    (root / "synthetic.csv").write_bytes(raw)
    for name, raw_input, caption, code in (("chart", raw, None, None), ("bad-csv", b"broken", None, "CSV_INVALID"),
                                            ("bad-caption", raw, "CSV values: 999.", "CHART_VALIDATION_FAILED")):
        data = {"chart_type": "bar", "value_columns": '["samples"]'}
        if caption is not None:
            data["caption"] = caption
        response = client.post("/api/v1/charts/csv", files={"file": ("synthetic.csv", raw_input, "text/csv")}, data=data)
        value = response.json()
        case = {"name": name, "request": {"path": "/api/v1/charts/csv", "fields": data,
            "input_utf8": raw_input.decode("utf-8"), "input_sha256": hashlib.sha256(raw_input).hexdigest()},
                "http_status": response.status_code, "response": value}
        if code is None:
            check(response.status_code == 200, "Chart generation failed")
            png = base64.b64decode(value["image_ref"].split(",", 1)[1])
            (root / "chart.png").write_bytes(png)
            case["summary"] = {"csv_data_rows": 2, "caption": value["caption"], "caption_source_cells": value["numeric_checks"],
                               "png_bytes": len(png), "png_sha256": hashlib.sha256(png).hexdigest()}
            check(value["caption"] == "CSV values: 12, 18.", "Wrong CSV caption")
        else:
            check(response.status_code == 422 and value["error_code"] == code and set(value) == {"error_code", "message", "details"}, "Wrong chart/CSV error wrapper")
        report["cases"].append(case)
    after = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob("records/papers/*/*.json")}
    check(before == after, "Writing mutated published paper records")
    report["input_record_sha256"] = before
    report["inputs_unchanged"] = True
    for path in sorted((ROOT / "contracts").glob("*.json")):
        if path.name.startswith("framework-outline."):
            continue
        relative = path.relative_to(ROOT).as_posix()
        original = subprocess.check_output(["git", "rev-parse", f"{BASELINE}:{relative}"], cwd=ROOT, encoding="utf-8").strip()
        current = subprocess.check_output(["git", "hash-object", relative], cwd=ROOT, encoding="utf-8").strip()
        check(current == original, "Existing contract schema/example changed")
        report["frozen_contracts"].append({"file": relative, "git_blob": current, "unchanged": True})
    check(len(report["frozen_contracts"]) == 22, "Expected eleven frozen records and examples")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"endpoints": 19, "cases": len(report["cases"]), "frozen_files": 22,
                      "framework": framework["summary"], "report": str(args.report)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
