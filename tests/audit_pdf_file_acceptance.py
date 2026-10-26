"""Recheck original bytes and scope; never disguise the real arXiv query failure."""
import json
import os
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from scholar_graph.pdf_files import PdfFiles, file_digest


def main():
    data = json.loads((ROOT / "tests/reports/pdf-file-endpoint-live.json").read_text(encoding="utf-8"))
    expected = file_digest(ROOT / "pdf/1706.03762v7.pdf")
    checks = {}
    checks["official_source_identity"] = expected == (data["input"]["sha256"], data["input"]["bytes"])
    for key, value in (("upload", data["upload"]["file"]), ("final", data["final_file_check"]),
                       ("historical", data["historical_arxiv"]["after"]), ("real_arxiv_pdf", data["verified_metadata_arxiv"]["file"])):
        checks[key + "_original_matches_response"] = ((value["sha256"], value["bytes"]) == expected and
            value["status"] == 200 and value["content_type"] == "application/pdf" and value["content_disposition"].startswith("inline;"))
        checks[key + "_bounded_asgi_stream"] = (value["asgi"]["max_chunk_bytes"] <= 65536 and
            value["asgi"]["chunks"] > 1 and (value["asgi"]["sha256"], value["asgi"]["bytes"]) == expected)
    root = ROOT / data["local_artifacts"]
    archived = PdfFiles(root / "upload").locate(data["upload"]["paper_id"])
    checks["private_archived_bytes_match"] = file_digest(archived) == expected
    checks["traversal_and_unknown_rejected"] = all(x["status"] == 404 and
        set(x["body"]) == {"error_code", "message", "details"} and x["body"]["error_code"] == "PAPER_NOT_FOUND" for x in data["rejected"])
    checks["legacy_same_hash_recovery"] = data["historical_arxiv"]["before"]["status"] == 404 and data["historical_arxiv"]["same_hash_reupload_status"] == 201
    checks["real_public_download_matches_saved_original"] = (data["verified_metadata_arxiv"]["succeeded"] and
        data["verified_metadata_arxiv"]["download"]["sha256"] == expected[0])
    checks["metadata_query_failure_not_reported_as_success"] = data["fresh_public_arxiv_passed"] == data["arxiv"]["succeeded"]
    ignored = subprocess.run(["git", "check-ignore", "pdf/1706.03762v7.pdf"], cwd=ROOT, capture_output=True)
    checks["pdf_ignored"] = ignored.returncode == 0
    diff = subprocess.check_output(["git", "diff", "a60dffd2bb94e8542bf2874e2c0fe4f430ae992f", "--name-only", "--",
        "contracts", "frontend", "docs", "prompts", "experiments", "test-records"], cwd=ROOT, text=True)
    checks["protected_paths_unchanged"] = not diff.strip()
    suites = ET.parse(ROOT / "tests/reports/pdf-file-endpoint-pytest.xml").getroot().findall("testsuite")
    regression = {key: sum(int(s.get(key, 0)) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
    checks["final_regression_passes"] = regression["tests"] >= 552 and regression["failures"] == regression["errors"] == 0
    key = os.environ.get("DEEPSEEK_API_KEY")
    paths = [ROOT / "tests/reports/pdf-file-endpoint-live.json", ROOT / "tests/reports/pdf-file-endpoint-acceptance.md",
             ROOT / "tests/reports/pdf-file-endpoint-pytest.xml"]
    checks["credential_absent"] = all(not key or key.encode() not in path.read_bytes() for path in paths)
    result = {"checks": checks, "regression": regression, "passed": all(checks.values()),
              "endpoint_checks_passed": data["endpoint_checks_passed"], "fresh_metadata_api_passed": data["fresh_public_arxiv_passed"]}
    (ROOT / "tests/reports/pdf-file-endpoint-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
