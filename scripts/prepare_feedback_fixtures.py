"""Prepare isolated real native/OCR PDFs for the teacher-feedback browser checks."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "tests")]
from sample_pdfs import make_pdf
from scholar_graph.pipeline import Pipeline
from scholar_graph.pdf_files import PdfFiles
from scholar_graph.evidence_location import evidence_location


def main():
    root = ROOT / "data/teacher-feedback-20261114"
    os.environ["SCHOLAR_GRAPH_DEDUP_MODE"] = "off"
    os.environ["SCHOLAR_GRAPH_GROBID_ENABLED"] = "false"
    os.environ["SCHOLAR_GRAPH_QA_RETRIEVAL_MODE"] = "lexical"
    cache = ROOT / "data/repair-ocr-model-smoke/models/paddlex"
    if cache.is_dir():
        os.environ.setdefault("SCHOLAR_GRAPH_OCR_CACHE_DIR", str(cache))
    result = {}
    for kind in ("native", "scan"):
        source = make_pdf(root / (kind + ".pdf"), scan=kind == "scan")
        bundle = Pipeline(root / "records").parse(source)
        PdfFiles(root / "records").retain(source, bundle["paper_meta"])
        chunk = next(c for c in bundle["chunks"] if "12" in c["text"])
        result[kind] = {"paper_id": bundle["paper_meta"]["id"], "chunk_id": chunk["chunk_id"],
                        "page": chunk["page_number"], "location": evidence_location(chunk)}
        print(kind, result[kind], flush=True)
    (root / "fixtures.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
