"""公开等价物、非官方 pdf/ 文件: rasterize all public v1 pages, then real upload/OCR."""

import argparse
import json
import shutil
import sys
import time
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from fastapi.testclient import TestClient
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import pypdfium2 as pdfium

from scholar_graph.api import create_app
from scholar_graph.pipeline import Pipeline
from scholar_graph.adapters import LocalEngines
from public_pdf_support import prepare, header, save, file_info, upload, parsed_details


def rasterize(source, target, preview, dpi):
    start = time.perf_counter()
    document = pdfium.PdfDocument(str(source))
    output = canvas.Canvas(str(target), invariant=1)
    output.setTitle("Rasterized public arXiv v1 - not an official competition scan")
    output.setAuthor("ScholarGraph public-equivalent OCR acceptance")
    sizes = []
    try:
        for index in range(len(document)):
            page = document[index]
            bitmap = page.render(scale=dpi / 72)
            image = bitmap.to_pil().convert("RGB")
            try:
                width, height = page.get_size()
                output.setPageSize((width, height))
                output.drawImage(ImageReader(image), 0, 0, width=width, height=height)
                output.showPage()
                sizes.append({"physical_page": index + 1, "pixel_width": image.width, "pixel_height": image.height})
                if index == 0:
                    image.save(preview)
            finally:
                image.close()
                bitmap.close()
                page.close()
        output.save()
    finally:
        document.close()
    with target.open("rb") as handle:
        reader = PdfReader(handle)
        text_lengths = [len((page.extract_text() or "").strip()) for page in reader.pages]
    if any(text_lengths):
        raise RuntimeError("Synthetic scan unexpectedly contains a selectable text layer")
    return {"method": "pypdfium2逐页RGB光栅化；ReportLab逐页drawImage，仅图片，无文本层；没有抽页或删页。",
            "dpi": dpi, "pages": sizes, "text_layer_chars_by_page": text_lengths,
            "elapsed_seconds": round(time.perf_counter() - start, 6), "tools": {
                name: version(name) for name in ("pypdfium2", "reportlab", "pypdf")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--cache-source", type=Path, default=ROOT / "data/module-one/models/paddlex")
    parser.add_argument("--engine-timeout", type=float, default=300)
    args = parser.parse_args()
    root = prepare(args.output_root)
    result = header("public-v1-full-raster-ocr")
    result["engine_timeout_seconds"] = args.engine_timeout
    result["default_api_configuration"] = args.engine_timeout == 300
    result["source"] = {**file_info(args.source), "url": "https://arxiv.org/pdf/1706.03762v1"}
    scan = root / "rasterized-attention-v1.pdf"
    result["rasterization"] = rasterize(args.source, scan, root / "first-page.png", dpi=150)
    result["scan"] = file_info(scan)
    records = root / "records"
    cache = records / "models" / "paddlex"
    if args.cache_source.is_dir():
        shutil.copytree(args.cache_source, cache, ignore=shutil.ignore_patterns("*.lock"))
        result["model_cache"] = {"preseeded_from": str(args.cache_source.resolve()),
            "files": sum(path.is_file() for path in cache.rglob("*")),
            "note": "复用本机既有模型缓存；没有修改模型、解析器或OCR阈值；实际引擎时限见engine_timeout_seconds。"}
    result["ocr_versions"] = {name: version(name) for name in ("paddleocr", "paddlepaddle")}
    save(args.report, result)
    factory = None if args.engine_timeout == 300 else lambda: Pipeline(records,
        engines=LocalEngines(timeout=args.engine_timeout, language="en", cache_dir=records / "models"))
    app = create_app(data_dir=records, pipeline_factory=factory)
    client = TestClient(app)
    value = upload(client, scan)
    result["upload"] = value
    result["parsed"] = parsed_details(client, records, value)
    histories = [json.loads(path.read_text(encoding="utf-8")) for path in (records / "jobs").glob("job-*/parse-status.json")]
    result["all_status_histories"] = histories
    result["ocr_branch_entered"] = any(item["status"] == "ocr" for history in histories for item in history)
    if value["http_status"] == 201:
        bundle = app.state.repository.paper(value["response"]["id"])
        page_chars = {str(n): sum(len(chunk["text"]) for chunk in bundle["chunks"] if chunk["page_number"] == n)
                      for n in range(1, result["scan"]["physical_pages"] + 1)}
        result["ocr_text"] = {"chars_by_physical_page": page_chars, "total_chars": sum(page_chars.values()),
            "chunk_count": len(bundle["chunks"]), "first_chunk_excerpt": bundle["chunks"][0]["text"][:160]}
        result["conclusion"] = "通过（限分支进入、产出文本与合规Chunk，不代表逐字准确率或官方img验证）。" if result["ocr_branch_entered"] and all(page_chars.values()) else "失败：未满足全页OCR文本与分支核验。"
    else:
        result["ocr_text"] = {"chunk_count": 0, "total_chars": 0, "note": "未发布；不能将中间可能识别文本冒充有效产出。"}
        result["conclusion"] = "失败：原始错误和状态见upload/all_status_histories，未发布有效Chunk。"
    save(args.report, result)
    print(json.dumps({"scope": result["scope"], "scan_pages": result["scan"]["physical_pages"],
        "http_status": value["http_status"], "ocr_branch_entered": result["ocr_branch_entered"],
        "chunks": result["ocr_text"]["chunk_count"], "elapsed_seconds": value["measurement"]["elapsed_seconds"],
        "conclusion": result["conclusion"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
