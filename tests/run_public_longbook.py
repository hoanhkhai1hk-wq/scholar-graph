"""公开等价物、非官方 pdf/ 文件: the full public 541-page UDL book, no split bypass."""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import httpx
from fastapi.testclient import TestClient
from pypdf import PdfReader
from scholar_graph.api import create_app
from public_pdf_support import prepare, header, save, file_info, upload, parsed_details, read

BOOK_URL = "https://github.com/udlbook/udlbook/releases/download/v5.0.3/UnderstandingDeepLearning_02_09_26_C.pdf"
BOOK_SHA256 = "f8237d393163900fa8e43210e680a3f987b45ccac7750b372e156fae3df0bf32"


def acquire(root):
    start = time.perf_counter()
    target = root / "understanding-deep-learning.pdf"
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        with client.stream("GET", BOOK_URL) as response:
            parts = urlsplit(str(response.url))
            provenance = {"scope": "公开等价物、非官方 pdf/ 文件", "url": BOOK_URL,
                          "http_status": response.status_code,
                          "final_url": urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")),
                          "redirect_query_omitted": True}
            if response.status_code != 200:
                return None, provenance
            size = 0
            with target.open("wb") as handle:
                for block in response.iter_bytes():
                    size += len(block)
                    if size > 100 * 1024 * 1024:
                        raise ValueError("Public download exceeded 100MiB test bound")
                    handle.write(block)
    provenance.update(file_info(target))
    provenance["elapsed_seconds"] = round(time.perf_counter() - start, 6)
    return target, {"attempts": [provenance]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--download-provenance", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = prepare(args.output_root)
    result = header("full-public-udl-longbook")
    try:
        if args.source:
            if args.download_provenance is None:
                raise ValueError("Existing source requires its real download provenance")
            source = args.source.resolve()
            provenance = json.loads(args.download_provenance.read_text(encoding="utf-8"))
            matching = [entry for entry in provenance["attempts"] if entry.get("sha256") == file_info(source)["sha256"]]
            if len(matching) != 1:
                raise ValueError("Source does not match the recorded public download hash")
        else:
            source, provenance = acquire(root)
        result["download"] = provenance
        if source is None:
            result["conclusion"] = "失败：公开等价物、非官方 pdf/ 文件未下载成功。"
            save(args.report, result)
            return
        result["source"] = file_info(source)
        if result["source"]["sha256"] != BOOK_SHA256 or result["source"]["physical_pages"] != 541:
            raise ValueError("Source is not the pinned complete official public release")
        with source.open("rb") as handle:
            text = PdfReader(handle).pages[0].extract_text() or ""
        result["identity_check"] = {"first_page_excerpt": text[:160],
            "full_book_not_page_subset": True, "request_pdf_page_subset_used": False}
        save(args.report, result)
        records = root / "records"
        app = create_app(data_dir=records)
        client = TestClient(app)
        value = upload(client, source)
        result["upload"] = value
        result["parsed"] = parsed_details(client, records, value)
        pid = "paper-" + result["source"]["sha256"]
        result["status"] = read(client, f"/api/v1/papers/{pid}/parse-status")
        result["status_histories"] = [json.loads(path.read_text(encoding="utf-8")) for path in (records / "jobs").glob("job-*/parse-status.json")]
        entered = any(item["status"] == "indexing" for history in result["status_histories"] for item in history)
        result["indexing"] = {"entered": entered, "elapsed_seconds": None,
            "note": "未进入indexing，不能把null写成索引耗时0秒或宣称索引完成。" if not entered else "状态快照不含时戳；本探针未提供独立索引阶段计时，不猜测耗时。",
            "vector_index_called": False}
        result["pagination"] = {
            "paper_list": read(client, "/api/v1/papers?page=1&page_size=100"),
            "chunks_first": read(client, f"/api/v1/papers/{pid}/chunks?page=1&page_size=100"),
            "chunks_overflow": read(client, f"/api/v1/papers/{pid}/chunks?page=999&page_size=100")}
        result["published_chunk_count"] = sum(len(json.loads(path.read_text(encoding="utf-8"))) for path in (records / "papers").glob("*/chunks.json"))
        result["conclusion"] = ("失败：541页原书在当前管线200页上限被拒绝；没有切块/索引或长书分页成功。不修改上限、不拆小冒充。"
            if value["http_status"] != 201 else "已上传；完整切块与索引阶段独立计时仍须核对，不能仅靠上传返回断言全通过。")
    except Exception as error:
        result["conclusion"] = "失败：公开等价物、非官方 pdf/ 文件验证未完成。"
        result["probe_error_type"] = type(error).__name__
    save(args.report, result)
    print(json.dumps({"scope": result["scope"], "pages": result.get("source", {}).get("physical_pages"),
        "upload_http": result.get("upload", {}).get("http_status"), "published_chunks": result.get("published_chunk_count"),
        "indexing": result.get("indexing"), "measurement": result.get("upload", {}).get("measurement"),
        "conclusion": result["conclusion"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
