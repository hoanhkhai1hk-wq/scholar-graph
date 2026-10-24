"""Reproduce the previously reported schema boundaries; count actual cases only.

Run from the repository root with Python 3.12 and jsonschema==4.26.0.
This uses synthetic contract examples, not official PDF test cases.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import subprocess
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def run() -> dict:
    validators, examples, definitions = {}, {}, {}
    inputs = {}
    for path in sorted((ROOT / "contracts").glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        example_path = path.with_name(path.name.replace(".schema.", ".example."))
        example = json.loads(example_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        validator.validate(example)
        name = schema["title"]
        definitions[name], validators[name], examples[name] = schema, validator, example
        assert set(schema["properties"]) == set(schema["required"]) == set(example)
        assert schema["additionalProperties"] is False
        for item in (path, example_path):
            inputs[item.relative_to(ROOT).as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
    assert len(definitions) == 9
    results = []

    def case(category, name, validator, candidate, expected):
        actual = validator.is_valid(candidate)
        results.append({"id": f"{category}/{name}", "category": category,
                        "expected_valid": expected, "actual_valid": actual,
                        "passed": actual == expected})

    for name in ("DedupDecision", "DiffSummary", "ParseStatus", "ChartOutput"):
        example, schema, validator = examples[name], definitions[name], validators[name]
        for field in schema["required"]:
            invalid = copy.deepcopy(example)
            del invalid[field]
            case("required_extra_version", f"{name}-missing-{field}", validator, invalid, False)
        case("required_extra_version", f"{name}-extra", validator, {**example, "extra": True}, False)
        case("required_extra_version", f"{name}-wrong-version", validator,
             {**example, "schema_version": "1.0.0"}, False)

    anchor_schema = definitions["QAAnswer"]["properties"]["anchors"]["items"]
    for name in ("DedupDecision", "DiffSummary"):
        assert definitions[name]["$defs"]["chunk_anchor"] == anchor_schema
        invalid = copy.deepcopy(examples[name])
        anchor = invalid["evidence"][0]["anchor"] if name == "DedupDecision" else invalid["key_sentences"][0]["anchor"]
        anchor["page_number"] = 0
        case("anchor_shape", f"{name}-page-zero", validators[name], invalid, False)
        anchor["page_number"] = 1
        anchor["extra"] = True
        case("anchor_shape", f"{name}-extra", validators[name], invalid, False)

    dv, d = validators["DedupDecision"], examples["DedupDecision"]
    for index, (similarity, valid) in enumerate(((0, True), (1, True), (-0.01, False),
                                               (1.01, False), ("0.5", False), (True, False))):
        case("dedup", f"similarity-{index}", dv, {**d, "similarity": similarity}, valid)
    case("dedup", "empty-evidence", dv, {**d, "evidence": []}, False)
    invalid = copy.deepcopy(d)
    invalid["evidence"][0]["reason"] = "   "
    case("dedup", "blank-reason", dv, invalid, False)
    original = json.dumps(d, sort_keys=True)
    human = {**copy.deepcopy(d), "human_override": True, "recommendation": "keep_both"}
    case("dedup", "human-decision", dv, human, True)
    assert json.dumps(d, sort_keys=True) == original
    assert definitions["DedupDecision"]["properties"]["human_override"]["default"] is False

    fv, f = validators["DiffSummary"], examples["DiffSummary"]
    for index, anchor in enumerate((None, f["key_sentences"][0]["anchor"])):
        for status in ("verified", "unverified"):
            item = {**f["key_sentences"][0], "anchor": anchor, "status": status}
            case("diff", f"anchor-{index}-{status}", fv, {**f, "key_sentences": [item]},
                 anchor is not None or status == "unverified")
    invalid = copy.deepcopy(f)
    del invalid["key_sentences"][0]["anchor"]
    case("diff", "missing-anchor", fv, invalid, False)
    for index, (text, valid) in enumerate((("未检出章节级差异", True), ("No changes.", False), ("", False))):
        case("diff", f"empty-sections-{index}", fv,
             {**f, "changed_sections": [], "summary_text": text}, valid)

    pv, p = validators["ParseStatus"], examples["ParseStatus"]
    for status in ("queued", "parsing", "ocr", "indexing", "completed", "failed"):
        for progress in range(-1, 102):
            candidate = {**p, "status": status, "progress": progress,
                         "error_code": "OCR_FAILED" if status == "failed" else None,
                         "error_message": "failure" if status == "failed" else None}
            valid = progress == 0 if status == "queued" else (progress == 100 if status == "completed" else 0 <= progress <= 99)
            case("parse_progress", f"{status}-{progress}", pv, candidate, valid)
    for field in ("error_code", "error_message"):
        for index, value in enumerate((None, "", "   ")):
            case("parse_errors", f"{field}-{index}", pv, {**p, field: value}, False)
    case("parse_errors", "fractional-progress", pv, {**p, "progress": 12.5}, False)
    case("parse_errors", "unknown-code", pv, {**p, "error_code": "UNKNOWN_CODE"}, False)
    ev = pv.evolve(schema={"$ref": "#/$defs/api_error"})
    for code in definitions["ParseStatus"]["$defs"]["error_code"]["enum"]:
        case("shared_error_codes", f"status-{code}", pv, {**p, "error_code": code}, True)
        case("shared_error_codes", f"envelope-{code}", ev,
             {"error_code": code, "message": "failure", "details": None}, True)
    error = {"error_code": "OCR_FAILED", "message": "failure",
             "details": {"stage": "ocr", "retryable": False}}
    case("error_envelope", "scalar-details", ev, error, True)
    for field in ("error_code", "message", "details"):
        invalid = copy.deepcopy(error)
        del invalid[field]
        case("error_envelope", f"missing-{field}", ev, invalid, False)
    case("error_envelope", "business-extra", ev, {**error, "paper": examples["PaperMeta"]}, False)
    case("error_envelope", "nested-business", ev, {**error, "details": {"paper": examples["PaperMeta"]}}, False)
    case("error_envelope", "business-array", ev, {**error, "details": {"chunks": [examples["Chunk"]]}}, False)
    case("error_envelope", "unknown-code", ev, {**error, "error_code": "UNKNOWN_CODE"}, False)

    cv, c = validators["ChartOutput"], examples["ChartOutput"]
    for kind in ("line", "bar", "scatter", "histogram"):
        case("chart", kind, cv, {**c, "chart_type": kind}, True)
    case("chart", "unsupported-type", cv, {**c, "chart_type": "pie"}, False)
    case("chart", "empty-checks", cv, {**c, "numeric_checks": []}, False)
    invalid = copy.deepcopy(c)
    invalid["numeric_checks"][0]["verified"] = "true"
    case("chart", "string-boolean", cv, invalid, False)
    invalid = copy.deepcopy(c)
    invalid["numeric_checks"][0]["csv_anchor"]["row_number"] = 1
    case("chart", "header-row", cv, invalid, False)
    invalid = copy.deepcopy(c)
    del invalid["series"][0]["name"]
    case("chart", "missing-series-name", cv, invalid, False)
    invalid = copy.deepcopy(c)
    invalid["numeric_checks"][0]["verified"] = False
    case("chart", "false-check-is-valid-shape", cv, invalid, True)

    assert len({r["id"] for r in results}) == len(results)
    counts = Counter(r["category"] for r in results)
    failed = [r for r in results if not r["passed"]]
    return {"run_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
            "jsonschema": version("jsonschema"), "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "scope": "自制契约样例、非官方 pdf/ 用例；结构边界验证，不证明真实论文解析或数字事实正确。",
            "preflight": "九份 Schema 与 example 校验通过；预检不计入边界用例数。",
            "previously_reported_total": 722, "total": len(results), "passed": len(results) - len(failed),
            "failed": len(failed), "categories": dict(sorted(counts.items())), "input_sha256": inputs,
            "cases": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, help="Write JSON details and Markdown summary here.")
    args = parser.parse_args()
    result = run()
    print(json.dumps({k: result[k] for k in ("total", "passed", "failed", "categories")}, ensure_ascii=False))
    if args.report_dir:
        args.report_dir.mkdir(parents=True, exist_ok=True)
        (args.report_dir / "contract-boundaries.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lines = ["# v1.1 契约边界验证报告", "", result["scope"], "", f"运行时间：{result['run_utc']}",
                 f"脚本提交：`{result['source_commit']}`", f"脚本 SHA-256：`{result['script_sha256']}`", "",
                 f"总数：{result['total']}；通过：{result['passed']}；失败：{result['failed']}。",
                 "计数来自实际执行的唯一用例，没有通过重复复制或断言固定总数补齐 722。", "",
                 "| 用例分类 | 数量 |", "| --- | ---: |"]
        lines.extend(f"| {name} | {count} |" for name, count in result["categories"].items())
        lines.extend(["", result["preflight"], "", "复现（仓库根目录 PowerShell）：", "", "```powershell",
                      "backend/.venv/Scripts/python.exe tests/verify_contract_boundaries.py --report-dir tests/reports",
                      "```", "", f"环境：Python {result['python']}，jsonschema {result['jsonschema']}。",
                      "完整用例结果、期望/实际判定和十八份输入文件 SHA-256 见同目录 contract-boundaries.json。",
                      "包含故意无效输入：这些输入被 Schema 拒绝才算用例通过。",
                      "ChartOutput 的 false-check 用例只证明布尔字段形状可接受，不表示该数字可写入图注。",
                      "没有运行官方三用例，也没有证明锚点外键真实性；实际管线的语义校验另测。", ""])
        (args.report_dir / "contract-boundaries.md").write_text("\n".join(lines), encoding="utf-8")
    return int(result["failed"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
