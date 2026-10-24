"""Cross-check public-equivalent evidence against actual files and immutable records."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.validation import ContractGate
from public_pdf_support import BASELINE, SCOPE, save


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, encoding="utf-8").strip()


def digest(path):
    path = Path(path).resolve()
    assert path.is_relative_to(ROOT / "data")
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            hasher.update(block)
    return hasher.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    gate = ContractGate()
    directory = ROOT / "tests" / "reports"
    def read(name):
        value = json.loads((directory / (name + ".json")).read_text(encoding="utf-8"))
        assert "公开等价物、非官方 pdf/ 文件" in value["scope"]
        assert value["baseline"] == BASELINE
        return value
    dedup, normal, extended, book = [read("public-equivalent-" + name) for name in ("dedup", "ocr", "ocr-extended", "longbook")]
    for source in dedup["sources"]:
        assert digest(source["file"]) == source["sha256"]
    assert dedup["sources"][0]["sha256"] != dedup["sources"][1]["sha256"]
    raw_repo = ApiRepository(ROOT / "data/public-equivalents/dedup-release/raw-records", gate)
    for request in dedup["raw_uploads"]:
        assert request["http_status"] == 201
        bundle = raw_repo.paper(request["response"]["id"])
        counts = request["parsed"]["record_counts"]
        assert len(bundle["chunks"]) == counts["Chunk"]
        assert len(bundle["reference_entries"]) == counts["ReferenceEntry"]
        assert len(bundle["citation_links"]) == counts["CitationLink"]
        assert request["comparison"]["decision"]["http_status"] == 404
        gate.error(request["comparison"]["decision"]["response"])
    fetch_repo = ApiRepository(ROOT / "data/public-equivalents/dedup-release/fetch-records", gate)
    compare = dedup["fetch_controls"][-1]["comparison"]
    assert fetch_repo.comparison(compare["decision"]["response"]["new_paper_id"], kind="decision") == compare["decision"]["response"]
    assert fetch_repo.comparison(compare["diff"]["response"]["new_paper_id"], kind="diff") == compare["diff"]["response"]
    assert normal["scan"]["sha256"] == extended["scan"]["sha256"] == digest(normal["scan"]["file"])
    assert digest(extended["scan"]["file"]) == normal["scan"]["sha256"]
    for value, name in ((normal, "ocr-release"), (extended, "ocr-extended-release")):
        assert value["scan"]["physical_pages"] == 15
        assert value["rasterization"]["text_layer_chars_by_page"] == [0] * 15
        assert value["ocr_branch_entered"]
        repo = ApiRepository(ROOT / "data/public-equivalents" / name / "records", gate)
        if value["upload"]["http_status"] == 201:
            bundle = repo.paper(value["upload"]["response"]["id"])
            assert len(bundle["chunks"]) == value["ocr_text"]["chunk_count"]
            assert {chunk["page_number"] for chunk in bundle["chunks"]} == set(range(1, 16))
        else:
            gate.error(value["upload"]["response"])
            assert not (repo.root / "papers" / ("paper-" + value["scan"]["sha256"])).exists()
            assert value["ocr_text"]["chunk_count"] == 0
    assert book["source"]["physical_pages"] == 541
    assert digest(book["source"]["file"]) == book["source"]["sha256"]
    assert book["upload"]["http_status"] == 422 and book["published_chunk_count"] == 0
    assert book["indexing"]["entered"] is False and book["indexing"]["elapsed_seconds"] is None
    assert book["pagination"]["chunks_first"]["http_status"] == 404
    gate.error(book["upload"]["response"])
    frozen = []
    for name in git("ls-tree", "-r", "--name-only", BASELINE, "contracts").splitlines():
        expected, actual = git("rev-parse", BASELINE + ":" + name), git("hash-object", name)
        assert expected == actual, name
        frozen.append({"file": name, "git_blob": actual, "unchanged": True})
    paths = sorted(set(git("diff", BASELINE, "--name-only").splitlines() + git("ls-files", "--others", "--exclude-standard").splitlines()))
    assert all(path.startswith("tests/") for path in paths)
    pattern = re.compile(rb'(?:sk-[A-Za-z0-9]{24,}|hf_[A-Za-z0-9]{24,}|ghp_[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|[?&](?:jwt|sig)=)')
    assert not [name for name in paths if pattern.search((ROOT / name).read_bytes())]
    value = {"scope": SCOPE, "baseline": BASELINE, "evidence_consistency_checks_passed": True,
             "business_acceptance_all_passed": False, "scope_tests_only": True,
             "frozen_contract_files": frozen, "changed_paths": paths,
             "secret_pattern_matches": 0, "secret_scan_limits": "常见模式检查，不保证覆盖所有秘密；未读取.env或使用真实API Key。",
             "notes": "校验报告与真实数据文件一致，不把证据一致性或pytest通过混同于业务验收通过。"}
    save(args.report, value)
    print(json.dumps({"scope": SCOPE, "evidence_consistent": True, "business_acceptance_all_passed": False,
                      "frozen_contract_files": len(frozen), "scope_tests_only": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
