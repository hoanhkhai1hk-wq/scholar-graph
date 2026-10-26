"""Audit measurements separately from scope/security; unavailable GROBID stays failed."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from scholar_graph.storage import RecordStore
from scholar_graph.validation import ContractGate
from run_grobid_acceptance import tei_summary, bundle_summary
BASELINE = "523d07666767c0cafd9f54ed1a5980af3b26176d"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main():
    report = json.loads((ROOT / "tests/reports/grobid-integration-live.json").read_text(encoding="utf-8"))
    checks = []
    def check(name, passed, detail):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    source = ROOT / "pdf/1706.03762v7.pdf"
    check("official_file_identity", hashlib.sha256(source.read_bytes()).hexdigest() == report["input"]["sha256"], report["input"])
    ignored = subprocess.run(["git", "check-ignore", "pdf/1706.03762v7.pdf"], cwd=ROOT, capture_output=True, text=True)
    check("pdf_ignored", ignored.returncode == 0, ignored.stdout.strip())
    forbidden = ["frontend", "contracts", "docs", "prompts", "experiments", "test-records"]
    changes = git("diff", "--name-only", BASELINE, "--", *forbidden)
    check("protected_paths_unchanged", not changes, changes.splitlines())
    changes = git("diff", "--name-only", BASELINE).splitlines()
    check("no_pdf_added", not any(x.lower().endswith(".pdf") for x in changes), changes)
    config = yaml.safe_load((ROOT / "services/docker-compose.grobid.yml").read_text(encoding="utf-8"))
    service = config["services"]["grobid"]
    check("keyless_local_service", service["ports"] == ["127.0.0.1:8070:8070"] and
          not service.get("environment") and not service.get("env_file") and not service.get("build") and
          not service.get("volumes"), {"image": service["image"], "ports": service["ports"]})
    local = ROOT / report["local_artifacts"]
    check("fresh_mineru_records", (local / "mineru-only/papers").is_dir() and report["mineru"]["status"]["status"] == "completed", report["mineru"]["counts"])
    suites = ET.parse(ROOT / "tests/reports/grobid-integration-pytest.xml").getroot()
    summary = {key: sum(int(x.get(key, 0)) for x in suites.findall("testsuite")) for key in ("tests", "failures", "errors", "skipped")}
    check("regression_no_failures", summary["tests"] >= 535 and summary["failures"] == summary["errors"] == 0, summary)
    check("live_failure_not_called_success", report["passed"] == ("grobid" in report and "optional_pipeline" in report and
          report["optional_pipeline"]["schema_and_anchor_gate"] == "passed" and report["optional_pipeline"]["chunks_unchanged"]),
          {"live_passed": report["passed"], "error": report.get("grobid_error")})
    if report.get("service_evidence_passed"):
        payload = (local / "attention.tei.xml").read_bytes()
        measured = tei_summary(payload)
        check("tei_counts_hash_and_samples_match", all(measured[key] == report["grobid"][key]
              for key in ("counts", "samples", "tables", "reference_coverage", "tei_sha256", "tei_bytes")),
              {"sha256": measured["tei_sha256"], "counts": measured["counts"]})
        gate = ContractGate()
        pid = "paper-" + report["input"]["sha256"]
        bundles = []
        folders = [("mineru-only", "mineru")]
        if report.get("production_pipeline_passed"):
            folders.append(("mineru-with-grobid", "optional_pipeline"))
        for folder, key in folders:
            store = RecordStore(local / folder, gate)
            bundle = store.load(store.root / "papers" / pid)
            gate.bundle(bundle)
            summary = bundle_summary(bundle)
            check(key + "_records_schema_anchors_and_measurements", all(summary[x] == report[key][x]
                  for x in ("paper_meta", "counts", "reference_coverage", "samples")), summary["counts"])
            bundles.append(bundle)
        if report.get("production_pipeline_passed"):
            check("grobid_did_not_replace_chunks", bundles[0]["chunks"] == bundles[1]["chunks"],
                  "既有适配器只补题录/参考文献，保留所有 MinerU 物理页与坐标")
        else:
            failed = report["optional_pipeline"]
            groups = local / "mineru-with-grobid/papers"
            check("invalid_optional_records_not_published", failed["published_paper_groups"] == 0 and
                  not list(groups.glob("*/paper-meta.json")) and failed["status"]["status"] == "failed",
                  {"status": failed["status"], "published_groups": failed["published_paper_groups"]})
        checks_live = report["grobid"]["health_checks"]
        check("actual_service_http_succeeded", report["grobid"]["status"] == 200 and
              all(checks_live[x]["status"] == 200 for x in ("isalive", "version")), checks_live)
    artifacts = [ROOT / "tests/reports/grobid-integration-live.json", ROOT / "tests/reports/grobid-integration-pytest.xml",
                 ROOT / "tests/reports/grobid-integration-acceptance.md", ROOT / "services/docker-compose.grobid.yml"]
    secret = os.environ.get("DEEPSEEK_API_KEY")
    safe = all(not secret or secret.encode() not in path.read_bytes() for path in artifacts)
    check("credential_absent_from_artifacts", safe, "仅检查，不输出凭据；未调用模型 API")
    output = {"scope": "官方 pdf/ 真文件；审计通过不替代容器联调通过", "baseline": BASELINE,
              "checks": checks, "passed": all(x["passed"] for x in checks), "live_acceptance_passed": report["passed"],
              "service_evidence_passed": report.get("service_evidence_passed", False),
              "production_pipeline_passed": report.get("production_pipeline_passed", False)}
    (ROOT / "tests/reports/grobid-integration-audit.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"audit_passed": output["passed"], "checks": len(checks), "live_acceptance_passed": report["passed"]}))
    return 0 if output["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
