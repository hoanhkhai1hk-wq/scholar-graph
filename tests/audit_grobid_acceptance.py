"""Audit measurements separately from scope/security; unavailable GROBID stays failed."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from xml.etree import ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[1]
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
    artifacts = [ROOT / "tests/reports/grobid-integration-live.json", ROOT / "tests/reports/grobid-integration-pytest.xml",
                 ROOT / "tests/reports/grobid-integration-acceptance.md", ROOT / "services/docker-compose.grobid.yml"]
    secret = os.environ.get("DEEPSEEK_API_KEY")
    safe = all(not secret or secret.encode() not in path.read_bytes() for path in artifacts)
    check("credential_absent_from_artifacts", safe, "仅检查，不输出凭据；未调用模型 API")
    output = {"scope": "官方 pdf/ 真文件；审计通过不替代容器联调通过", "baseline": BASELINE,
              "checks": checks, "passed": all(x["passed"] for x in checks), "live_acceptance_passed": report["passed"]}
    (ROOT / "tests/reports/grobid-integration-audit.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"audit_passed": output["passed"], "checks": len(checks), "live_acceptance_passed": report["passed"]}))
    return 0 if output["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
