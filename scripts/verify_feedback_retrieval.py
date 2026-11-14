"""Replay equal/adaptive RRF over the SAME real BGE-M3 recalls on saved papers.

This measures source-chunk recall, never teacher scores or generated-answer quality.
No external model API is called and no private paper text is written to the report.
"""
import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.grounded_model import evidence_candidates
from scholar_graph.qa_retrieval import QAHybridRetriever
from scholar_graph.validation import ContractGate
from scholar_graph.vector_search import BgeChromaSearch


def main():
    root = ROOT / "data/teacher-feedback-20261114"
    root.mkdir(parents=True, exist_ok=True)
    ids = json.loads((ROOT / "data/real-model/sources.json").read_text(encoding="utf-8"))
    repo = ApiRepository(ROOT / "data/real-model/records", ContractGate())
    output_repo = ApiRepository(root / "recall-audit", repo.gate)
    cases = [
        ("sixth_author", "论文Attention Is All You Need的第6作者是谁，在哪个公司/机构工作？", ["p0001-c00004"]),
        ("adam", "其中Adam优化器的超参数β₁和β₂分别被设置为了多少？", ["p0007-c00088"]),
        ("base_gpu", "这篇论文中提到的Transformer架构，在训练Base模型时使用了多少个GPU？具体是什么型号？", ["p0007-c00086"]),
        ("bleu_baseline", "Transformer (big)模型在English-to-German任务上的BLEU分数是多少？当时的State-of-the-art模型是多少？提升了多少？", ["p0008-c00093", "p0008-c00098"]),
        ("layer_norm_reference", "请列出论文中引用的关于“Layer Normalization”的参考文献（References）的完整作者和年份。", ["p0010-c00127"]),
    ]
    cases = [(name, ids["attention_id"], question, expected) for name, question, expected in cases]
    relation = "根据《Attention Is All You Need》和《BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding》。请对比：BERT的架构和原始Transformer的Encoder有什么承袭关系？BERT丢弃了原始Transformer的哪个部分？"
    cases += [("architecture_attention", ids["attention_id"], relation, ["p0003-c00029"]),
              ("architecture_bert", ids["bert_id"], relation, ["p0003-c00040"])]
    engine = BgeChromaSearch(
        ROOT / "data/module-four-runtime/.venv/Scripts/python.exe",
        ROOT / "data/module-four-models/bge-m3", root / "chroma-recall-audit", timeout=600, resident=True)
    rows = []
    report_directory = ROOT / "test-records/teacher-feedback-20261114"
    report_directory.mkdir(parents=True, exist_ok=True)
    for name, prefix, question, expected in cases:
        bundle = repo.paper(prefix)
        expected = [prefix + "-" + suffix for suffix in expected]
        assert set(expected) <= {c["chunk_id"] for c in bundle["chunks"]}
        engine.search(bundle["chunks"], question)
        raw = dict(engine.last_evidence)
        dense = sorted(raw["dense"], key=lambda cid: (-raw["dense"][cid], cid))[:24]
        lexical = list(dict.fromkeys(e["anchor"]["chunk_id"] for e in evidence_candidates(bundle, question, limit=48)))[:24]
        scores = {}
        for route in (dense, lexical):
            for rank, cid in enumerate(route, 1):
                scores[cid] = scores.get(cid, 0) + .5 * 61 / (60 + rank)
        baseline = sorted(scores, key=lambda cid: (-scores[cid], cid))
        if re.search(r"作者|机构|author|affiliation", question, re.I):
            pages = {c["chunk_id"]: c["page_number"] for c in bundle["chunks"]}
            baseline.sort(key=lambda cid: pages[cid] != 1)
        class RecordedRecall:
            def search(self, chunks, query):
                assert query == question and chunks == bundle["chunks"]
                self.last_evidence = raw
        service = QAHybridRetriever(output_repo, RecordedRecall())
        _, metadata = service.retrieve(bundle, question)
        trace_id = metadata["fusion"]["trace_id"]
        trace = json.loads((output_repo.root / "qa-retrieval/fusion" / (trace_id + ".json")).read_text(encoding="utf-8"))
        adaptive = trace["final_order"]
        trace_name = "fusion-" + name + ".json"
        (report_directory / trace_name).write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
        def coverage(order, limit):
            return sum(cid in order[:limit] for cid in expected) / len(expected)
        row = {"case": name, "paper_id": prefix, "expected_chunk_ids": expected,
               "baseline_ranks": {cid: baseline.index(cid) + 1 if cid in baseline else None for cid in expected},
               "adaptive_ranks": {cid: adaptive.index(cid) + 1 if cid in adaptive else None for cid in expected},
               "baseline_recall_at_8": coverage(baseline, 8), "adaptive_recall_at_8": coverage(adaptive, 8),
               "baseline_recall_at_24": coverage(baseline, 24), "adaptive_recall_at_24": coverage(adaptive, 24),
               "fusion": metadata["fusion"], "trace_file": trace_name, "real_vector_revision": raw["revision"],
               "passed": coverage(adaptive, 8) >= coverage(baseline, 8) and coverage(adaptive, 24) >= coverage(baseline, 24)}
        rows.append(row)
        print(name, row["baseline_ranks"], row["adaptive_ranks"], "PASS" if row["passed"] else "FAIL", flush=True)
    report = {"scope": "Six fixed questions (seven paper-level retrieval cases) over real local BGE-M3 recalls; no generated answers or teacher-score claim",
              "cases": rows, "passed": all(row["passed"] for row in rows)}
    path = ROOT / "test-records/teacher-feedback-20261114/real-recall-comparison.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not report["passed"]:
        raise SystemExit("Source recall regressed on the fixed evaluation set")


if __name__ == "__main__":
    main()
