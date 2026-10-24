"""Module-five HTTP evidence from hand-made persisted contract data, not real papers."""

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.graph_service import validate_graph
from graph_samples import graph_bundles

BASELINE = "de74511f9f579af910bd683820b409698a301020"


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def hashes(root):
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.glob("papers/*/*.json"))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = args.output_root.resolve()
    check(root.is_relative_to(ROOT / "data") and not root.exists(), "Choose a fresh output root under project data/.")
    root.mkdir(parents=True)
    report = {"scope": "自制多篇落盘契约记录、非官方 pdf/ 用例；未调用解析器，不声称真实论文或官方三用例通过。",
        "run_utc": datetime.now(timezone.utc).isoformat(), "baseline_commit": BASELINE,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "real_model_calls": 0, "vector_database_used": False, "cases": [], "frozen_contracts": []}
    for name in ("chain-and-isolate", "missing-anchor"):
        bundles = graph_bundles()
        if name == "missing-anchor":
            bundles[1]["citation_links"] = []
        data = root / name
        app = create_app(data_dir=data)
        store = app.state.repository.store
        for bundle in bundles:
            store.paper(bundle)
        before = hashes(data)
        client = TestClient(app)
        ids = [bundle["paper_meta"]["id"] for bundle in bundles]
        response = client.get("/api/v1/graph", params=[("paper_ids", pid) for pid in ids])
        check(response.status_code == 200, "Graph request failed")
        value = response.json()
        loaded = [app.state.repository.paper(pid) for pid in ids]
        validate_graph(value, loaded, app.state.repository.gate)
        check(before == hashes(data), "Graph query mutated published input records")
        check(len(value["nodes"]) == 4 and len(value["edges"]) == 2, "Unexpected graph size")
        check(value["layers"]["isolated"] == (["paper-graph-d"] if name == "chain-and-isolate" else ["paper-graph-c", "paper-graph-d"]), "Isolate handling failed")
        fw = value["future_work"]
        counts = {key: len(fw[key]) for key in ("worth_exploring", "excluded", "unverifiable")}
        check(counts == ({"worth_exploring": 2, "excluded": 1, "unverifiable": 0} if name == "chain-and-isolate"
                         else {"worth_exploring": 3, "excluded": 0, "unverifiable": 0}), "Future-work filtering mismatch")
        report["cases"].append({"case": name, "request": {"method": "GET", "path": "/api/v1/graph", "paper_ids": ids},
            "http_status": response.status_code, "input_record_sha256": before,
            "summary": {"nodes": len(value["nodes"]), "edges": len(value["edges"]),
                "verified_edges": sum(edge["status"] == "verified" for edge in value["edges"]),
                "cornerstones": value["layers"]["cornerstone"], "future_before": sum(counts.values()),
                "future_after": counts["worth_exploring"], "excluded": counts["excluded"], "unverifiable": counts["unverifiable"]},
            "response": value, "inputs_unchanged": True})
    for path in sorted((ROOT / "contracts").glob("*.json")):
        if ".v1.2." in path.name:
            continue
        relative = path.relative_to(ROOT).as_posix()
        original = subprocess.check_output(["git", "rev-parse", f"{BASELINE}:{relative}"], cwd=ROOT, text=True).strip()
        current = subprocess.check_output(["git", "hash-object", relative], cwd=ROOT, text=True).strip()
        check(original == current, "Frozen legacy contract changed")
        report["frozen_contracts"].append({"file": relative, "git_blob": current, "unchanged": True})
    check(len(report["frozen_contracts"]) == 18, "Expected original nine schemas and examples")
    forbidden = subprocess.check_output(["git", "diff", BASELINE, "--name-only", "--", "frontend", "prompts", "experiments", "test-records", "docker-compose.yml"], cwd=ROOT, text=True)
    check(not forbidden.strip(), "Forbidden files changed")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"report": args.report.as_posix(), "cases": [item["summary"] for item in report["cases"]],
                      "legacy_frozen_files": 18}, ensure_ascii=False))


if __name__ == "__main__":
    main()
