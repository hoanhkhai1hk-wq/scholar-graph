"""Deterministic audit of live data, journals, anchors, source hashes and regressions."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from scholar_graph.api import create_app
from scholar_graph.api_repository import ApiRepository
from scholar_graph.storage import write_json
from scholar_graph.tracking_state import TrackingState
from scholar_graph.validation import ContractGate

BASELINE = "b42f3d21918bdb24c037c7845bd5129af6b1f9e3"


def main():
    proof = json.loads((ROOT / "tests/reports/tracking-live-results.json").read_text(encoding="utf-8"))
    root = ROOT / "data/tracking-acceptance-final-v4/records"
    repository = ApiRepository(root, ContractGate())
    checks = []
    def check(name, condition):
        checks.append({"check": name, "passed": bool(condition)})
    rounds = proof["rounds"]
    check("真实两轮运行均完成且HTTP200", len(rounds) == 2 and all(row["http_status"] == 200 and row["run"]["status"] == "completed" for row in rounds))
    first, second = [row["run"] for row in rounds]
    check("第一轮2候选2入库无失败", first["candidate_count"] == first["imported_count"] == 2 and first["failed_count"] == 0)
    check("第二轮零新增且跳过2重复", second["imported_count"] == 0 and second["duplicate_count"] == 2 and second["failed_count"] == 0)
    check("两轮已发布论文id集合不变", rounds[0]["paper_ids_after"] == rounds[1]["paper_ids_after"])
    check("候选基础arXiv身份唯一", len({c["arxiv_id"].split("v")[0] for c in first["candidates"]}) == 2)
    check("公共请求无模型Key", proof["model_api_key"] == "未设置")
    check("种子同时包含主题与真实引用关系", {q["kind"] for q in first["queries"]} == {"topic", "citation"})
    seeds = [repository.paper(pid) for pid in proof["seed_ids"]]
    for query in first["queries"]:
        for field in ("anchor", "reference_anchor"):
            if query.get(field):
                repository.gate.anchor(query[field], seeds)
    check("全部种子锚点回溯真实Chunk", True)
    for left, right in zip(first["candidates"], second["candidates"], strict=True):
        record = left["import"]
        repository.gate.record("PaperMeta", left["metadata"])
        bundle = repository.paper(record["paper"]["id"])
        repository.gate.bundle(bundle)
        check("实际解析发布和Chunk计数:" + left["arxiv_id"], bool(bundle["chunks"]) and
              len(bundle["chunks"]) == rounds[0]["chunk_counts"][record["paper"]["id"]])
        check("真实queued到completed:" + left["arxiv_id"], record["initial_parse_status"]["status"] == "queued" and record["parse_status"]["status"] == "completed")
        check("重复复用同一论文且不伪造初始状态:" + left["arxiv_id"], right["import"]["paper"] == record["paper"] and
              right["import"]["already_present"] and right["import"]["initial_parse_status"] is None)
    duplicates = TrackingState(root).duplicates()
    check("去重日志仅两行且身份唯一", len(duplicates) == len({r["identity"] for r in duplicates}) == 2)
    check("重复计数与运行一致", sum(row["occurrences"] for row in duplicates) == second["duplicate_count"])
    check("原生引用数据未虚报删除", all(row["run"]["cleanup"]["removed_count"] == 0 for row in rounds))
    cleanup = proof["citation_cleanup_fault_injection"]
    check("明确注入的两条重复引用被清理", cleanup["first"]["links_before"] == 71 and cleanup["first"]["links_after"] == 69 and cleanup["first"]["removed_count"] == 2)
    check("二次清理幂等", cleanup["second"]["removed_count"] == 0)
    for item in cleanup["first"]["changes"]:
        audit = root.parent / "cleanup-fixture" / item["audit_ref"]
        check("保留引用原件与完成凭据", (audit / "before.json").is_file() and (audit / "completed.json").is_file())
        path = root.parent / "cleanup-fixture/papers" / item["paper_id"] / "citation-links.json"
        check("清理后文件SHA匹配审计", hashlib.sha256(path.read_bytes()).hexdigest() == item["after_sha256"])
    f = proof["feedback"]
    event = f["event"]
    voted = event["paper_id"]
    before = next(item for item in event["before"] if item["paper_id"] == voted)
    after = next(item for item in event["after"] if item["paper_id"] == voted)
    check("一次点赞真实改变排名", before["rank"] > after["rank"] and after["score"] > before["score"])
    check("同主题的其他论文有真实加分证据", any(item["paper"]["id"] != voted and item.get("feedback_adjustment", 0) > 0 and
        item["reasons"][-1]["evidence"]["votes"][0]["matched_terms"] for item in f["after"]["items"]))
    check("画像与排序重启持久化", f["after"] == f["after_restart"] and len(f["persisted_profile"]["votes"]) == 1 and
          f["persisted_profile"]["events"][0] == event)
    extra = proof["feedback_extra_public_import"]["result"]
    check("额外真实Reformer入库与两轮计数分开", extra["succeeded"] and extra["paper"]["arxiv_id"].startswith("2001.04451") and extra["parse_status"]["status"] == "completed")
    check("定时任务未到期不重复轮询", proof["scheduled_task_not_due"]["exit_code"] == 0 and proof["scheduled_task_not_due"]["result"]["reason"] == "NOT_DUE")
    source_match = all(hashlib.sha256((ROOT / path).read_text(encoding="utf-8").encode()).hexdigest() == digest for path, digest in proof["source_sha256_lf"].items())
    check("实测源码SHA与当前源码一致", source_match)
    suites = ET.parse(ROOT / "tests/reports/tracking-pytest.xml").getroot().findall("testsuite")
    totals = {key: sum(int(s.get(key, "0")) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
    check("最终全量481通过零失败错误跳过", totals == {"tests": 481, "failures": 0, "errors": 0, "skipped": 0})
    initial = ET.parse(ROOT / "tests/reports/tracking-initial-pytest.xml").getroot().findall("testsuite")
    check("保留首次15失败回归证据", sum(int(s.get("failures", "0")) for s in initial) == 15)
    failed_candidates = json.loads((ROOT / "tests/reports/tracking-candidate-failure-results.json").read_text(encoding="utf-8"))
    check("不隐瞒额外候选解析失败原文", all(row["run"]["status"] == "partial" and any(c["outcome"] == "failed" and
        c["import"]["error"]["message"] == "参考文献编号重复，不能确认正文引用目标。" for c in row["run"]["candidates"]) for row in failed_candidates["rounds"]))
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()
    tracked = git("diff", "--name-only", BASELINE).splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    check("只修改backend和tests", all(path.startswith(("backend/", "tests/")) for path in tracked + untracked))
    check("既有契约和前端及协作目录零改动", not git("diff", BASELINE, "--", "contracts", "frontend", "docs", "prompts", "experiments", "test-records"))
    check("pdf仍被Git忽略", "pdf/" in git("check-ignore", "pdf/1706.03762v7.pdf"))
    check("语料与环境文件均未跟踪", not git("ls-files", "pdf", ".env", "data"))
    secrets = [value.encode() for name, value in os.environ.items() if value and "API_KEY" in name.upper() and len(value) >= 8]
    check("本单文件不含实际环境Key", all(not any(secret in (ROOT / path).read_bytes() for secret in secrets)
          for path in set(tracked + untracked) if (ROOT / path).is_file()))
    paths = create_app(data_dir=root).openapi()["paths"]
    check("注册28条业务端点", sum(len(methods) for methods in paths.values()) == 28)
    report = {"baseline": BASELINE, "checks": checks, "passed": sum(c["passed"] for c in checks),
              "failed": sum(not c["passed"] for c in checks), "regression": totals}
    write_json(ROOT / "tests/reports/tracking-audit.json", report)
    print(json.dumps({"passed": report["passed"], "failed": report["failed"], "regression": totals}))
    return int(bool(report["failed"]))


if __name__ == "__main__":
    raise SystemExit(main())
