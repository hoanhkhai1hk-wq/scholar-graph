"""Module one: inspect PDF, run local engines, normalize, gate, then publish."""

from __future__ import annotations

import hashlib
import io
import re
import tempfile
from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader

from .adapters import LocalEngines
from .dedup import compare
from .errors import PipelineError
from .grobid import GrobidClient
from .normalize import block_text, doi, normalize
from .status import ParseJob
from .storage import RecordStore
from .validation import ContractGate


class Pipeline:
    def __init__(self, root: Path, *, engines=None, grobid=None, gate=None, metadata_enricher=None):
        self.gate = gate or ContractGate()
        self.store = RecordStore(root, self.gate)
        self.engines = engines or LocalEngines(cache_dir=root / "models")
        self.grobid = grobid
        self.metadata_enricher = metadata_enricher
        self.last_job = None
        self.last_output = None
        self.last_comparison = None

    def parse(self, source: Path) -> dict:
        self.last_job, self.last_output = None, None
        self.last_comparison = None
        try:
            if source.suffix.lower() != ".pdf":
                raise PipelineError("UNSUPPORTED_FILE_TYPE", "输入必须为 PDF 文件。")
            if source.stat().st_size > 50 * 1024 * 1024:
                raise PipelineError("FILE_TOO_LARGE", "PDF 超过本地管线的 50 MiB 限制。")
            raw = source.read_bytes()
            if len(raw) > 50 * 1024 * 1024:
                raise PipelineError("FILE_TOO_LARGE", "PDF 超过本地管线的 50 MiB 限制。")
        except PipelineError:
            raise
        except OSError:
            raise PipelineError("VALIDATION_ERROR", "无法读取输入 PDF。") from None
        digest = hashlib.sha256(raw).hexdigest()
        pid = "paper-" + digest
        job_id = "job-" + uuid4().hex
        job = ParseJob(pid, self.gate, lambda history: self.store.statuses(job_id, history))
        self.last_job = job
        try:
            job.move("parsing", "检查 PDF 与文本层", progress=5)
            paper, ocr_pages = self._inspect(raw, digest)
            scratch = self.store.root / ".scratch"
            scratch.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="parse-", dir=scratch) as temporary:
                snapshot = Path(temporary) / "source.pdf"
                snapshot.write_bytes(raw)  # Immutable parser input, not a project contract output.
                native = self.engines.text(snapshot)
                indices = [page.get("page_idx") for page in native["pages"]]
                if (native.get("schema") != "docvortex.middle" or native.get("is_full_document") is not True
                        or any(type(index) is not int for index in indices)
                        or len(indices) != paper["page_count"]
                        or set(indices) != set(range(paper["page_count"]))):
                    raise PipelineError("PARSE_FAILED", "MinerU 未返回全部 PDF 物理页的完整中间结果。")
                job.move("parsing", "MinerU 本地文本解析完成", progress=30)
                ocr = None
                if ocr_pages:
                    job.move("ocr", "扫描页 OCR", progress=40)
                    ocr = self.engines.ocr(snapshot, ocr_pages)
                    ocr_indices = [page.get("page_idx") for page in ocr["pages"]]
                    if (any(type(index) is not int for index in ocr_indices)
                            or len(ocr_indices) != len(ocr_pages) or set(ocr_indices) != set(ocr_pages)):
                        raise PipelineError("OCR_FAILED", "OCR 未覆盖全部待识别物理页。")
                    if any(not any(block_text(block.get("content")).strip() for block in page.get("blocks", []))
                           for page in ocr["pages"]):
                        raise PipelineError("OCR_FAILED", "扫描页未识别出可验证文本。")
                    job.move("ocr", "扫描页 OCR 完成", progress=70)
                job.move("indexing", "生成契约记录与锚点索引", progress=80)
                bundle = normalize(native, ocr, paper, ocr_pages)
                if self.grobid is not None:
                    bundle = self.grobid.enrich(bundle, raw)
                if self.metadata_enricher is not None:
                    original = bundle["paper_meta"]
                    enriched = self.metadata_enricher(dict(original))
                    protected = ("id", "schema_version", "file_hash", "page_count", "has_text_layer")
                    if any(enriched.get(key) != original[key] for key in protected):
                        raise PipelineError("VALIDATION_ERROR", "元数据补充不得改变实际文件身份、页数或文本层。")
                    bundle["paper_meta"] = enriched
                self.gate.bundle(bundle)
                already_present = (self.store.root / "papers" / pid).exists()
                prior = self.store.previous_version(bundle["paper_meta"]) if not already_present else None
                comparison = compare(prior, bundle, self.gate) if prior is not None else None
                job.move("indexing", "Schema 与外键校验通过", progress=95)
                target = self.store.paper(bundle)
                comparison_target = self.store.comparison(*comparison, [prior, bundle]) if comparison else None
                job.move("completed", "四类记录已通过校验并原子发布")
                self.last_output = target
                self.last_comparison = comparison_target
                return bundle
        except PipelineError as error:
            if job.current["status"] not in {"completed", "failed"}:
                job.move("failed", "解析未完成", error=error)
            raise
        except Exception:
            error = PipelineError("PARSE_FAILED", "解析未完成；未发布不合规记录。")
            if job.current["status"] not in {"completed", "failed"}:
                job.move("failed", "解析未完成", error=error)
            raise error from None

    @staticmethod
    def _inspect(raw: bytes, digest: str):
        if not raw.startswith(b"%PDF-"):
            raise PipelineError("PARSE_FAILED", "文件内容不是合法 PDF。")
        try:
            reader = PdfReader(io.BytesIO(raw), strict=True)
            if reader.is_encrypted:
                raise PipelineError("PARSE_FAILED", "本单不处理加密 PDF。")
            count = len(reader.pages)
            if count < 1 or count > 200:
                raise PipelineError("PARSE_FAILED", "PDF 页数必须在 1 到 200 之间。")
            texts = [page.extract_text() or "" for page in reader.pages]
            # ReportLab and other writers can emit a stream containing only font/state setup
            # for a blank page. Only painting operations make an empty text layer an OCR candidate.
            painting = {b"Do", b"Tj", b"TJ", b"'", b'"', b"S", b"s", b"f", b"F", b"f*",
                        b"B", b"B*", b"b", b"b*", b"sh"}
            ocr_pages = []
            for n, (page, text) in enumerate(zip(reader.pages, texts, strict=True)):
                contents = page.get_contents()
                if not text.strip() and contents is not None and any(op in painting for _, op in contents.operations):
                    ocr_pages.append(n)
            meta = reader.metadata
            first = next((text for text in texts if text.strip()), "")
            version = re.search(r"(?:^|\n)\s*Version:\s*(v\d+)\b", first, re.I)
            doi_line = re.search(r"(?:^|\n)\s*DOI:\s*([^\n]+)", first, re.I)
            year_line = re.search(r"(?:^|\n)\s*Year:\s*((?:18|19|20)\d{2})\b", first)
            paper = {"schema_version": "1.0.0", "id": "paper-" + digest,
                     "title": (str(meta.title).strip() or None) if meta and meta.title else None,
                     "authors": [str(meta.author).strip()] if meta and meta.author and str(meta.author).strip() else [],
                     "institutions": [], "abstract": None,
                     "year": int(year_line[1]) if year_line else None, "source": "local-upload",
                     "arxiv_id": None, "doi": doi(doi_line[1]) if doi_line else None,
                     "version": version[1] if version else None, "file_hash": digest,
                     "page_count": count, "has_text_layer": any(text.strip() for text in texts)}
            return paper, ocr_pages
        except PipelineError:
            raise
        except Exception:
            raise PipelineError("PARSE_FAILED", "PDF 结构或文本层检查失败。") from None
