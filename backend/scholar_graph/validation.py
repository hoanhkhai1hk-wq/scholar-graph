"""Validate existing contracts and their foreign keys before any record is published."""

from __future__ import annotations

import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

from .errors import PipelineError

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


class ContractGate:
    def __init__(self, directory: Path = CONTRACTS):
        self.validators = {}
        for path in directory.glob("*.schema.json"):
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            self.validators[schema["title"]] = Draft202012Validator(schema)
        if len(self.validators) != 9:
            raise PipelineError("VALIDATION_ERROR", "需要仓库中完整的九类已发布契约。")

    def record(self, kind: str, value: dict) -> None:
        try:
            json.dumps(value, allow_nan=False)
            self.validators[kind].validate(value)
        except (ValueError, TypeError, KeyError) as exc:
            raise PipelineError("VALIDATION_ERROR", "记录不是合法契约 JSON。") from None
        except Exception:
            raise PipelineError("VALIDATION_ERROR", f"{kind} 未通过 Schema 校验。") from None

    def error(self, value: dict) -> None:
        validator = self.validators["ParseStatus"].evolve(schema={"$ref": "#/$defs/api_error"})
        if not validator.is_valid(value):
            raise PipelineError("VALIDATION_ERROR", "错误响应不符合统一封装。")

    def bundle(self, bundle: dict) -> None:
        # The dict is an internal aggregate; only the four existing record types are serialized.
        if set(bundle) != {"paper_meta", "chunks", "reference_entries", "citation_links"}:
            raise PipelineError("VALIDATION_ERROR", "解析结果必须包含四类记录。")
        paper = bundle["paper_meta"]
        self.record("PaperMeta", paper)
        pid = paper["id"]
        if paper["page_count"] is None or paper["file_hash"] is None:
            raise PipelineError("VALIDATION_ERROR", "已解析 PDF 必须有页数与原文件哈希。")
        for key in ("doi",):
            if paper[key] is not None and not re.fullmatch(r"10\.\d{4,9}/\S+", paper[key], re.I):
                raise PipelineError("VALIDATION_ERROR", "DOI 必须使用裸 DOI。")
        chunks = {}
        for chunk in bundle["chunks"]:
            self.record("Chunk", chunk)
            if chunk["paper_id"] != pid or chunk["chunk_id"] in chunks:
                raise PipelineError("VALIDATION_ERROR", "分块归属错误或标识重复。")
            if chunk["page_number"] > paper["page_count"] or not chunk["text"].strip():
                raise PipelineError("VALIDATION_ERROR", "分块页码超限或正文为空。")
            expected = (chunk["section_path"] + [None] * 3)[:3]
            if [chunk[f"heading_{n}"] for n in (1, 2, 3)] != expected:
                raise PipelineError("VALIDATION_ERROR", "分块标题与章节路径不一致。")
            if chunk["bbox"] is not None:
                x0, y0, x1, y1 = chunk["bbox"]
                if not (x0 < x1 and y0 < y1):
                    raise PipelineError("VALIDATION_ERROR", "分块坐标顺序不合法。")
            chunks[chunk["chunk_id"]] = chunk
        if not chunks:
            raise PipelineError("PARSE_FAILED", "PDF 未产生可验证的正文分块。")
        refs, numbers = {}, set()
        for ref in bundle["reference_entries"]:
            self.record("ReferenceEntry", ref)
            if ref["paper_id"] != pid or ref["ref_id"] in refs or ref["number"] in numbers:
                raise PipelineError("VALIDATION_ERROR", "参考文献归属或唯一性不合法。")
            if ref["doi"] is not None and not re.fullmatch(r"10\.\d{4,9}/\S+", ref["doi"], re.I):
                raise PipelineError("VALIDATION_ERROR", "参考文献 DOI 必须使用裸 DOI。")
            refs[ref["ref_id"]] = ref
            numbers.add(ref["number"])
        links = set()
        for link in bundle["citation_links"]:
            self.record("CitationLink", link)
            chunk, ref = chunks.get(link["chunk_id"]), refs.get(link["ref_id"])
            if (link["paper_id"] != pid or chunk is None or ref is None
                    or link["page_number"] != chunk["page_number"]
                    or link["citation_number"] != ref["number"]):
                raise PipelineError("VALIDATION_ERROR", "正文引用指向不存在或不一致的分块/条目。")
            key = tuple(link[k] for k in ("paper_id", "citation_number", "page_number", "chunk_id", "ref_id"))
            if key in links:
                raise PipelineError("VALIDATION_ERROR", "正文引用重复。")
            links.add(key)

    def anchor(self, value: dict, bundles: list[dict], *, quote: str | None = None) -> None:
        # Reuse the exact published four-field anchor schema, even outside a parent record.
        validator = self.validators["QAAnswer"].evolve(
            schema=self.validators["QAAnswer"].schema["properties"]["anchors"]["items"])
        if not validator.is_valid(value):
            raise PipelineError("VALIDATION_ERROR", "锚点必须具有四个合法结构字段。")
        matches = [chunk for bundle in bundles for chunk in bundle["chunks"]
                   if chunk["chunk_id"] == value["chunk_id"]]
        if len(matches) != 1:
            raise PipelineError("VALIDATION_ERROR", "锚点未唯一指向真实 Chunk。")
        chunk = matches[0]
        if (value["paper_id"] != chunk["paper_id"]
                or value["page_number"] != chunk["page_number"]
                or value["section"] != chunk["section_path"]):
            raise PipelineError("VALIDATION_ERROR", "锚点论文、物理页码或章节不匹配。")
        if quote is not None and (len(quote) > 600 or not compact(quote) or compact(quote) not in compact(chunk["text"])):
            raise PipelineError("VALIDATION_ERROR", "已验证关键句不是目标 Chunk 的原文子串。")

    def comparison(self, decision: dict, diff: dict, bundles: list[dict]) -> None:
        for bundle in bundles:
            self.bundle(bundle)
        ids = {bundle["paper_meta"]["id"] for bundle in bundles}
        for kind, record in (("DedupDecision", decision), ("DiffSummary", diff)):
            self.record(kind, record)
            if {record["old_paper_id"], record["new_paper_id"]} != ids or len(ids) != 2:
                raise PipelineError("VALIDATION_ERROR", "比较必须指向两条不同的 PaperMeta。")
        if (decision["old_paper_id"], decision["new_paper_id"]) != (diff["old_paper_id"], diff["new_paper_id"]):
            raise PipelineError("VALIDATION_ERROR", "裁决与差异摘要的比较方向不一致。")
        for item in decision["evidence"]:
            self.anchor(item["anchor"], bundles)
        if decision["recommendation"] == "keep_new" and not any(
                e["anchor"]["paper_id"] == decision["new_paper_id"] for e in decision["evidence"]):
            raise PipelineError("VALIDATION_ERROR", "保留新版必须包含新版证据。")
        for item in diff["key_sentences"]:
            if item["anchor"] is not None:
                self.anchor(item["anchor"], bundles,
                            quote=item["text"] if item["status"] == "verified" else None)


def chunk_anchor(chunk: dict) -> dict:
    return {"paper_id": chunk["paper_id"], "page_number": chunk["page_number"],
            "section": list(chunk["section_path"]), "chunk_id": chunk["chunk_id"]}
