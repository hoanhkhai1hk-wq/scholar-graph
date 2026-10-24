"""Compare only after validated per-paper answers and a Chunk-level evidence table."""

from .errors import PipelineError
from .qa import validate_answer, MISSING, PREMISE


def synthesis_from_table(table, *, refused):
    lines = [f'原文并列：{quote} [{row["evidence_id"]}]'
             for row in table for quote in row["quotes"]]
    if refused:
        lines.append("不可验证：部分论文未形成可回答证据，不能据此得出跨篇结论。")
    else:
        lines.append("不可验证：这些摘录不证明跨篇因果关系，也不支持不同指标之间的优劣排名。")
    return "\n".join(lines)


def validate_comparison(value, bundles, gate):
    if set(value) != {"evidence_table", "per_paper", "synthesis"} or len(value["per_paper"]) != len(bundles):
        raise PipelineError("VALIDATION_ERROR", "跨篇响应必须保留证据表、逐篇 QAAnswer 与综合文本。")
    table = value["evidence_table"]
    if not isinstance(table, list):
        raise PipelineError("VALIDATION_ERROR", "证据表必须为数组。")
    used = set()
    for index, row in enumerate(table):
        if (set(row) != {"evidence_id", "per_paper_index", "anchor", "quotes"}
                or row["evidence_id"] != f"E{index + 1}"
                or type(row["per_paper_index"]) is not int
                or not 0 <= row["per_paper_index"] < len(bundles)
                or not isinstance(row["quotes"], list) or len(row["quotes"]) != 1):
            raise PipelineError("VALIDATION_ERROR", "证据行的形状或逐篇关联错误。")
        paper_index = row["per_paper_index"]
        record = value["per_paper"][paper_index]
        gate.record("QAAnswer", record)
        anchor = row["anchor"]
        key = (anchor["paper_id"], anchor["chunk_id"])
        if key in used or anchor not in record["anchors"]:
            raise PipelineError("VALIDATION_ERROR", "证据行重复或未回指逐篇答案锚点。")
        used.add(key)
        gate.anchor(anchor, [bundles[paper_index]], quote=row["quotes"][0])
    for index, (record, bundle) in enumerate(zip(value["per_paper"], bundles, strict=True)):
        gate.record("QAAnswer", record)
        rows = [row for row in table if row["per_paper_index"] == index]
        if record["anchors"] != [row["anchor"] for row in rows]:
            raise PipelineError("VALIDATION_ERROR", "逐篇答案锚点与证据表不完整对应。")
        for row in rows:
            quote = row["quotes"][0]
            if quote not in record["answer"]:
                raise PipelineError("VALIDATION_ERROR", "综合引用的原文未出现在逐篇答案中。")
        evidence = [{"anchor": row["anchor"], "quote": row["quotes"][0]} for row in rows]
        prefix = next((text for text in (MISSING, PREMISE) if record["answer"].startswith(text)), "")
        validate_answer(record, bundle, evidence, gate, prefix=prefix)
    expected = synthesis_from_table(table, refused=any(record["refused"] for record in value["per_paper"]))
    if value["synthesis"] != expected:
        raise PipelineError("VALIDATION_ERROR", "综合含无证据、错引或改写的论断。")


def compare_papers(bundles, question, answerer):
    if len({bundle["paper_meta"]["id"] for bundle in bundles}) != len(bundles):
        raise PipelineError("VALIDATION_ERROR", "跨篇比较不接受重复论文。")
    # Phase one completes all per-paper schema/semantic gates. No synthesis exists yet.
    prepared = [answerer.answer(bundle, question) for bundle in bundles]
    records = [record for record, _ in prepared]
    table = []
    # Phase two builds a deduplicated Chunk table from accepted per-paper evidence only.
    for index, (_, evidence) in enumerate(prepared):
        for item in evidence:
            table.append({"evidence_id": f"E{len(table) + 1}", "per_paper_index": index,
                          "anchor": item["anchor"], "quotes": [item["quote"]]})
    # Phase three can only copy accepted quotes and refer back to this table.
    value = {"evidence_table": table, "per_paper": records,
             "synthesis": synthesis_from_table(table, refused=any(record["refused"] for record in records))}
    validate_comparison(value, bundles, answerer.gate)
    return value
