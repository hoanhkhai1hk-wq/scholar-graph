"""Evidence first, exact source quotations, frozen QAAnswer, then semantic gates."""

from copy import deepcopy

from .errors import PipelineError
from .qa_evidence import facets, measured_samples, neutral_question, numbers, numeric_question, retrieve


def aggregate(checks):
    states = {item["status"] for item in checks}
    return next((state for state in ("failed", "unverifiable", "passed") if state in states), "not_applicable")


def quote_blocks(evidence):
    return [f'【证据 {chr(65 + index)}】\n{item["quote"]}' for index, item in enumerate(evidence)]


def validate_answer(record, bundle, evidence, gate, *, prefix=""):
    gate.record("QAAnswer", record)
    expected = [item["anchor"] for item in evidence]
    # One evidence row per Chunk; every returned fact is an exact source quotation.
    if record["anchors"] != expected or len({a["chunk_id"] for a in expected}) != len(expected):
        raise PipelineError("VALIDATION_ERROR", "问答锚点不等于本次已核验的检索集合。")
    for item in evidence:
        gate.anchor(item["anchor"], [bundle], quote=item["quote"])
    if record["answer"] != "\n\n".join(([prefix] if prefix else []) + quote_blocks(evidence)):
        raise PipelineError("VALIDATION_ERROR", "答案含未绑定原文锚点的事实。")
    checks = record["numeric_fact_check"]["checks"]
    if record["numeric_fact_check"]["status"] != aggregate(checks):
        raise PipelineError("VALIDATION_ERROR", "数字校验汇总不一致。")
    for check in checks:
        for anchor in check["evidence"]:
            if anchor not in expected:
                raise PipelineError("VALIDATION_ERROR", "数字证据不在答案锚点中。")
            gate.anchor(anchor, [bundle])
        if check["status"] == "passed":
            supporting = [item for item in evidence if item["anchor"] in check["evidence"]]
            if not supporting or not any(check["claim"] == item["quote"] for item in supporting):
                raise PipelineError("VALIDATION_ERROR", "数字陈述未在同一原文证据中回溯。")
    for item in evidence:
        if numbers(item["quote"]) and not any(check["claim"] == item["quote"] and check["status"] == "passed"
                and item["anchor"] in check["evidence"] for check in checks):
            raise PipelineError("VALIDATION_ERROR", "原文数字没有逐项校验记录。")


class QuestionAnswerer:
    def __init__(self, gate, selector=None):
        self.gate, self.selector = gate, selector

    def answer(self, bundle, question):
        self.gate.bundle(bundle)
        candidates = retrieve(bundle, question)
        neutral = neutral_question(question)
        numeric = numeric_question(question)
        requested = facets(question)
        # A metric label alone does not supply its numeric result.
        missing_numeric = numeric and not numbers(question) and not any(numbers(item["quote"]) for item in candidates)
        refused = not neutral or not candidates or missing_numeric
        selected = candidates
        if not refused and self.selector is not None:
            indices = self.selector.select(question, deepcopy(candidates))
            if (not isinstance(indices, list) or len(indices) > 4 or
                    any(type(n) is not int or not 0 <= n < len(candidates) for n in indices) or len(set(indices)) != len(indices)):
                raise PipelineError("VALIDATION_ERROR", "模型选择了本次证据表以外的条目。")
            selected = [candidates[index] for index in indices]
            refused = not selected
            missing_numeric = numeric and not numbers(question) and not any(numbers(item["quote"]) for item in selected)
            refused = refused or missing_numeric
        evidence, seen = [], set()
        for item in selected:
            cid = item["anchor"]["chunk_id"]
            if cid not in seen and len(evidence) < 4:
                self.gate.anchor(item["anchor"], [bundle], quote=item["quote"])
                evidence.append({"anchor": item["anchor"], "quote": item["quote"]})
                seen.add(cid)
        checks = []
        prefix = ""
        if refused:
            if not selected or missing_numeric:
                prefix = "拒答：本文本无相关证据，未检索到足以回答该问题的原文或所需数值；不能据此断言全文未报告。"
            else:
                prefix = "拒绝按题设作肯定回答：保守摘录模式不能确认该前提；以下原文供纠错核对。"
            if numeric:
                actual = set().union(*(measured_samples(item["quote"]) for item in evidence)) if evidence else set()
                claimed = measured_samples(question)
                contradicted = bool(requested == {"samples"} and actual and claimed and claimed.isdisjoint(actual))
                status = "failed" if contradicted else "unverifiable"
                reason = "题设样本数与原文明确报告的样本数不同。" if contradicted else "未取得支持题设数字的同项原文；不以未找到作为反证。"
                checks.append({"claim": question, "status": status,
                               "evidence": [item["anchor"] for item in evidence] if contradicted else [], "reason": reason})
        for item in evidence:
            if numbers(item["quote"]):
                checks.append({"claim": item["quote"], "status": "passed", "evidence": [item["anchor"]],
                               "reason": "数字及其上下文逐字来自该 Chunk；仅核验原文回溯，不证明实验真实性或跨指标可比性。"})
        record = {"schema_version": "1.0.0", "answer": "\n\n".join(([prefix] if prefix else []) + quote_blocks(evidence)),
                  "anchors": [item["anchor"] for item in evidence],
                  "numeric_fact_check": {"status": aggregate(checks), "checks": checks}, "refused": refused}
        validate_answer(record, bundle, evidence, self.gate, prefix=prefix)
        return record, evidence
