"""Audit actual official uploads, calibrated scores, model identity and publication."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.semantic_vectors import band, calibrate
from scholar_graph.storage import write_json
from scholar_graph.validation import ContractGate

BASELINE = "8d15d1229451703805848f5ca3023a40fd5e027c"


def main():
    live = json.loads((ROOT / "tests/reports/semantic-dedup-live.json").read_text(encoding="utf-8"))
    calibration = json.loads((ROOT / "tests/reports/semantic-dedup-calibration.json").read_text(encoding="utf-8"))
    policy = json.loads((ROOT / "backend/scholar_graph/semantic_thresholds.json").read_text(encoding="utf-8"))
    checks = []
    def check(name, value):
        checks.append({"check": name, "passed": bool(value)})
    check("三组官方真文件且无模型Key", live["input_kind"] == "官方 pdf/ 真文件" and live["model_api_key"] == "未设置")
    for name, value in live["checks"].items():
        check("实测:" + name, value)
    for group, entry in live["groups"].items():
        repository = ApiRepository(ROOT / "data/semantic-dedup-acceptance-final" / group, ContractGate())
        check("已发布论文数:" + group, len(repository.papers()) == entry["paper_count"])
        for n, row in enumerate(entry["uploads"]):
            path = ROOT / "pdf" / row["source"]
            check("官方输入SHA:" + group + str(n), hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"] == row["paper"]["file_hash"])
            bundle = repository.paper(row["paper"]["id"])
            repository.gate.bundle(bundle)
            check("真实Chunk计数:" + group + str(n), len(bundle["chunks"]) == row["chunks"])
            evidence = row["assessment"]["encoder"]
            check("本地1024维固定模型:" + group + str(n), evidence["dimension"] == 1024 and evidence["device"] == "cpu" and evidence["revision"] == policy["model_revision"])
            chunks = {c["chunk_id"] for c in bundle["chunks"]}
            check("代表段均来自真实Chunk:" + group + str(n), 1 <= len(evidence["representatives"][row["paper"]["id"]]) <= 8 and set(evidence["representatives"][row["paper"]["id"]]) <= chunks)
        second = entry["uploads"][1]
        check("分数符合冻结阈值:" + group, band(second["metadata"]["score"], policy) == second["metadata"]["band"])
    version = live["groups"]["versions"]["uploads"][1]
    repo = ApiRepository(ROOT / "data/semantic-dedup-acceptance-final/versions", ContractGate())
    bundles = [repo.paper(row["paper"]["id"]) for row in live["groups"]["versions"]["uploads"]]
    repo.gate.comparison(version["decision"]["body"], version["diff"]["body"], bundles)
    check("业务裁决确用语义分数且锚点有效", version["decision"]["body"]["similarity"] == version["metadata"]["score"] and
          "BGE-M3" in version["decision"]["body"]["evidence"][0]["reason"])
    check("保留较新v7预警原文", "建议保留库里较新版本（v7）" in version["warning"])
    renamed = live["groups"]["renamed"]["uploads"]
    check("换名确为同字节且未伪造自比较", renamed[0]["sha256"] == renamed[1]["sha256"] and renamed[0]["upload_filename"] != renamed[1]["upload_filename"] and renamed[1]["decision"]["http_status"] == 404)
    positive = [row["score"] for row in calibration["positive_pairs"]]
    negative = [row["score"] for row in calibration["negative_pairs"]]
    computed = calibrate(positive, negative)
    check("阈值由独立观测数据重算", all(policy[key] == value for key, value in computed.items()))
    check("校准与验收论文分离", not set(policy["calibration_files"]) & {row["source"] for entry in live["groups"].values() for row in entry["uploads"]})
    check("4组保留扰动通过", len(calibration["heldout_positive_pairs"]) == 4 and all(band(row["score"], policy) == "duplicate" for row in calibration["heldout_positive_pairs"]))
    for name, digest in calibration["source_sha256"].items():
        check("校准官方输入SHA:" + name, hashlib.sha256((ROOT / "pdf" / name).read_bytes()).hexdigest() == digest)
    check("最终实测源码SHA一致", all(hashlib.sha256((ROOT / name).read_text(encoding="utf-8").encode()).hexdigest() == digest for name, digest in live["source_sha256_lf"].items()))
    with (ROOT / "data/module-four-models/bge-m3/pytorch_model.bin").open("rb") as handle:
        model_sha = hashlib.file_digest(handle, "sha256").hexdigest()
    expected = json.loads((ROOT / "tests/reports/module-four-audit.json").read_text(encoding="utf-8"))["model_files"]["pytorch_model.bin"]["sha256"]
    check("权重SHA与既有BGE-M3一致", model_sha == expected)
    wheel = next((ROOT / "data/semantic-dedup-wheel-local").glob("scholar_graph_backend-*.whl"))
    with ZipFile(wheel) as archive:
        check("本地后端wheel包含阈值配置", json.loads(archive.read("scholar_graph/semantic_thresholds.json")) == policy)
    suites = ET.parse(ROOT / "tests/reports/semantic-dedup-pytest.xml").getroot().findall("testsuite")
    totals = {key: sum(int(s.get(key, "0")) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
    check("全量511通过无失败错误跳过", totals == {"tests": 511, "failures": 0, "errors": 0, "skipped": 0})
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()
    changed = git("diff", "--name-only", BASELINE).splitlines() + git("ls-files", "--others", "--exclude-standard").splitlines()
    check("仅修改backend和tests", all(name.startswith(("backend/", "tests/")) for name in changed))
    check("前端契约及协作目录零改动", not git("diff", BASELINE, "--", "frontend", "contracts", "docs", "prompts", "experiments", "test-records"))
    check("pdf仍忽略未跟踪", "pdf/" in git("check-ignore", "pdf/1706.03762v7.pdf") and not git("ls-files", "pdf"))
    check("数据与环境文件未跟踪", not git("ls-files", "data", ".env"))
    secrets = [value.encode() for key, value in os.environ.items() if "API_KEY" in key.upper() and len(value) >= 8]
    check("本单文件不含实际Key", all(not any(secret in (ROOT / name).read_bytes() for secret in secrets) for name in changed if (ROOT / name).is_file()))
    report = {"baseline": BASELINE, "checks": checks, "passed": sum(row["passed"] for row in checks),
              "failed": sum(not row["passed"] for row in checks), "regression": totals, "model_sha256": model_sha, "wheel": wheel.name}
    write_json(ROOT / "tests/reports/semantic-dedup-audit.json", report)
    print(json.dumps({key: report[key] for key in ("passed", "failed", "regression")}))
    return int(bool(report["failed"]))


if __name__ == "__main__":
    raise SystemExit(main())
