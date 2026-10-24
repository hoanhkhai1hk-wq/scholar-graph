"""Conservative conversion from MinerU/Paddle blocks to the four frozen v1 records."""

from __future__ import annotations

import re

from .errors import PipelineError

DOI = re.compile(r"10\.\d{4,9}/[^\s<>\"]+", re.I)
REFERENCE = re.compile(r"\[(\d+)\]\s*(.*?)(?=\s*\[\d+\]|$)", re.S)


def doi(text: str) -> str | None:
    match = DOI.search(text)
    return match.group().rstrip(".,;)") if match else None


def block_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(filter(None, (block_text(item) for item in value)))
    if isinstance(value, dict):
        # Only actual textual payloads are retained; image names do not become figure descriptions.
        return block_text(value.get("content", ""))
    return ""


def reference_entries(chunks: list[dict], paper_id: str) -> list[dict]:
    text = "\n".join(chunk["text"] for chunk in chunks if is_references(chunk))
    found = {}
    for match in REFERENCE.finditer(text):
        number, raw = int(match[1]), match[2].strip()
        if number < 1 or not raw:
            continue
        if number in found:
            raise PipelineError("PARSE_FAILED", "参考文献编号重复，不能确认正文引用目标。")
        structured = re.match(r"^(.+?)\s*\(((?:18|19|20)\d{2})\)\.\s*(.+?)\.\s*(.*)$", raw, re.S)
        found[number] = {"schema_version": "1.0.0", "ref_id": f"{paper_id}-ref-{number}",
                         "paper_id": paper_id, "number": number,
                         "authors": [structured[1].strip()] if structured else [],
                         "year": int(structured[2]) if structured else None,
                         "title": structured[3].strip() if structured else None,
                         "venue": (re.split(r"\s*(?:doi:|https?://doi\.org/)", structured[4], flags=re.I)[0].strip(" .") or None) if structured else None,
                         "doi": doi(raw), "arxiv_id": None}
    return [found[n] for n in sorted(found)]


def is_references(chunk: dict) -> bool:
    return any(re.fullmatch(r"(?:\d+(?:\.\d+)*\s+)?(?:references|bibliography|参考文献)",
                            section.strip(), re.I) for section in chunk["section_path"])


def citation_links(chunks: list[dict], references: list[dict]) -> list[dict]:
    by_number = {ref["number"]: ref for ref in references}
    links, seen = [], set()
    for chunk in chunks:
        if is_references(chunk):
            continue
        for marker in re.finditer(r"\[(\d+(?:\s*[,;–-]\s*\d+)*)\]", chunk["text"]):
            numbers = set()
            for token in re.split(r"[,;]", marker[1]):
                bounds = re.split(r"[–-]", token.strip())
                if len(bounds) == 1:
                    numbers.add(int(bounds[0]))
                else:
                    start, end = map(int, bounds)
                    # Intersect with actual references instead of expanding attacker-sized ranges.
                    numbers.update(n for n in by_number if start <= n <= end)
            for number in sorted(numbers & by_number.keys()):
                key = (chunk["chunk_id"], number)
                if key in seen:
                    continue
                seen.add(key)
                links.append({"schema_version": "1.0.0", "paper_id": chunk["paper_id"],
                              "citation_number": number, "page_number": chunk["page_number"],
                              "chunk_id": chunk["chunk_id"], "ref_id": by_number[number]["ref_id"]})
    return links


def normalize(native: dict, ocr: dict | None, paper: dict, ocr_pages: list[int]) -> dict:
    pages = {page["page_idx"]: page for page in native["pages"] if page["page_idx"] not in ocr_pages}
    if ocr:
        pages.update({page["page_idx"]: page for page in ocr["pages"] if page["page_idx"] in ocr_pages})
    chunks, path = [], []
    for page_index, page in sorted(pages.items()):
        if type(page_index) is not int or not 0 <= page_index < paper["page_count"]:
            raise PipelineError("PARSE_FAILED", "解析器返回无效的 PDF 物理页索引。")
        for block in page.get("blocks", []):
            text = block_text(block.get("content")).strip()
            if not text:
                continue
            kind = block.get("type", "text")
            number = re.match(r"^(\d+(?:\.\d+)*)\s+\S", text)
            reference_heading = re.fullmatch(r"references|bibliography|参考文献", text, re.I)
            if reference_heading:
                path = [text]
            elif kind in {"paragraph_title", "section_title", "title"} or number:
                depth = min(3, len(number[1].split("."))) if number else 1
                # Never fabricate missing ancestor headings.
                depth = min(depth, len(path) + 1)
                path = path[:depth - 1] + [text]
            fields = (path + [None] * 3)[:3]
            bbox = block.get("bbox")
            if not (isinstance(bbox, list) and len(bbox) == 4):
                bbox = None
            chunk_type = {"table": "table", "image": "figure", "figure": "figure",
                          "equation": "formula", "formula": "formula"}.get(kind, "text")
            chunks.append({"schema_version": "1.0.0", "chunk_id": f"{paper['id']}-p{page_index + 1:04d}-c{len(chunks) + 1:05d}",
                           "paper_id": paper["id"], "page_number": page_index + 1, "section_path": list(path),
                           "heading_1": fields[0], "heading_2": fields[1], "heading_3": fields[2],
                           "text": text, "bbox": bbox, "type": chunk_type})
    refs = reference_entries(chunks, paper["id"])
    return {"paper_meta": paper, "chunks": chunks, "reference_entries": refs,
            "citation_links": citation_links(chunks, refs)}
