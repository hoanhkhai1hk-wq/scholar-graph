"""Run actual local engines against self-made PDFs and record evidence, not claimed accuracy."""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from importlib.metadata import distributions, version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sample_pdfs import make_pdf
from scholar_graph.dedup import compare, human_decision
from scholar_graph.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]


def relative(path):
    return path.resolve().relative_to(ROOT).as_posix()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.output_root.exists():
        parser.error("output-root already exists; choose a new directory instead of replaying an existing smoke run")
    args.output_root.mkdir(parents=True)
    pipeline = Pipeline(args.output_root / "output")
    report = {"scope": "自制样例、非官方 pdf/ 用例；未运行官方三用例。",
              "run_utc": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "python": platform.python_version(),
              "engines": {name: version(name) for name in ["mineru", "paddleocr", "paddlepaddle"]},
              "grobid": {"status": "待验证", "reason": "无 Docker Desktop/CLI；仅测试 Mock HTTP/TEI，未调用真实 GROBID。"},
              "ocr": {"status": "待验证"}, "parses": []}
    bundles = []
    for label, kwargs in [("selfmade-v1", {}), ("selfmade-v7", {"version": "v7", "samples": 18}),
                          ("selfmade-scan", {"scan": True})]:
        source = make_pdf(args.output_root / "inputs" / f"{label}.pdf", **kwargs)
        start = time.perf_counter()
        bundle = pipeline.parse(source)
        elapsed = time.perf_counter() - start
        stored = pipeline.store.load(pipeline.last_output)
        if stored != bundle:
            raise RuntimeError("Published records differ from validated output")
        record_files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in sorted(pipeline.last_output.glob("*.json"))}
        report["parses"].append({"input": relative(source), "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                                 "output_directory": relative(pipeline.last_output), "elapsed_seconds": round(elapsed, 3),
                                 "counts": {"PaperMeta": 1, "Chunk": len(bundle["chunks"]),
                                            "ReferenceEntry": len(bundle["reference_entries"]), "CitationLink": len(bundle["citation_links"])},
                                 "paper_meta": bundle["paper_meta"], "status_history": pipeline.last_job.history,
                                 "record_sha256": record_files})
        if label == "selfmade-scan":
            if not any("12 samples" in c["text"] for c in bundle["chunks"]):
                raise RuntimeError("Self-made scan did not recover the expected source text")
            report["ocr"] = {"status": "已接通", "engine": "PaddleOCR 3.7.0 / PaddlePaddle 3.3.1 / PP-OCRv5 / CPU",
                             "recognized_texts": [c["text"] for c in bundle["chunks"]]}
        bundles.append(bundle)
    decision, diff = compare(bundles[0], bundles[1], pipeline.gate)
    human = human_decision(decision, "keep_both", "自制验收：保留两个版本用于比较。", diff, bundles[:2], pipeline.gate)
    target = pipeline.store.comparison(decision, diff, bundles[:2], human=human)
    report["comparison"] = {"output_directory": relative(target), "system_decision": decision,
                            "human_decision": human, "diff_summary": diff,
                            "system_record_preserved": json.loads((target / "dedup-decisions.json").read_text(encoding="utf-8"))[0] == decision}
    report["contracts_sha256"] = {relative(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in sorted((ROOT / "contracts").glob("*.json"))}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    environment = {"python": platform.python_version(), "platform": platform.platform(),
                   "packages": dict(sorted((d.metadata["Name"], d.version) for d in distributions() if d.metadata["Name"]))}
    args.report.with_name("module-one-environment.json").write_text(json.dumps(environment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"parses": [{"input": row["input"], "counts": row["counts"]} for row in report["parses"]],
                      "comparison": {"DedupDecision": 2, "DiffSummary": 1},
                      "grobid": report["grobid"]["status"], "ocr": report["ocr"]["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
