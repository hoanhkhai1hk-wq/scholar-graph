"""Repeat the previously failing tests without retries; retain every result."""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = args.output_root.resolve()
    if not root.is_relative_to(ROOT / "data") or root.exists() or not 1 <= args.rounds <= 30:
        parser.error("Use a new directory under data/ and 1..30 rounds")
    root.mkdir(parents=True)
    report = {"source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "run_utc": datetime.now(timezone.utc).isoformat(), "rounds": [],
              "scope": "重复旧四项去重取数测试及一项101条分页测试，不重试单个测试、不改权限。"}
    for index in range(args.rounds):
        command = [sys.executable, "-m", "pytest", "tests/test_api_comparison.py",
                   "tests/test_api_read.py::test_http_pagination_across_101_contract_examples", "-q",
                   "--basetemp", str(root / f"round-{index + 1:02}"),
                   "--junitxml", str(root / f"round-{index + 1:02}.xml")]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=120)
        report["rounds"].append({"round": index + 1, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr})
        print(f"round {index + 1}: exit {result.returncode}", flush=True)
    report["passed_rounds"] = sum(item["exit_code"] == 0 for item in report["rounds"])
    report["failed_rounds"] = args.rounds - report["passed_rounds"]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("passed_rounds", "failed_rounds")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
