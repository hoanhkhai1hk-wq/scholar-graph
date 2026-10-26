"""Module one: inspect PDF, run local engines, normalize, gate, then publish."""

from __future__ import annotations

import hashlib
import io
import os
import re
import tempfile
from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader

from .adapters import LocalEngines
from .batching import ParseLimits, parse_batches
import pypdfium2 as pdfium
from .dedup import compare
from .errors import PipelineError
from .grobid import GrobidClient
from .normalize import block_text, doi, normalize
from .status import ParseJob
from .storage import RecordStore
from .validation import ContractGate
from .semantic_dedup import semantic_from_environment
from .storage import write_json
from .atomic_io import windows_retry


class Pipeline:
    def __init__(self, root: Path, *, engines=None, grobid=None, gate=None, metadata_enricher=None, limits=None, semantic=None):
        self.limits = limits or ParseLimits.environment()
        self.last_metrics = None
        self.gate = gate or ContractGate()
        self.store = RecordStore(root, self.gate)
        self.engines = engines or LocalEngines(cache_dir=root / "models")
        self.grobid = grobid
        self.metadata_enricher = metadata_enricher
        self.last_job = None
        self.last_output = None
        self.last_comparison = None
        self.last_warning = None
        self.semantic = semantic if semantic is not None else semantic_from_environment(root)
        self.last_dedup_metadata = None

    def parse(self, source: Path) -> dict:
        self.last_job, self.last_output = None, None
        self.last_comparison = None
        self.last_warning = None
        self.last_dedup_metadata = None
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
            paper, ocr_pages = self._inspect(raw, digest, max_pages=self.limits.max_pages, threshold=self.limits.text_batch_pages)
            existing = self.store.root / "papers" / pid
            if existing.is_dir():
                job.move("indexing", "文件哈希命中已发布论文；复用合法记录", progress=80)
                return self._publish(self.store.load(existing), job, pid)
            scratch = self.store.root / ".scratch"
            scratch.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="parse-", dir=scratch) as temporary:
                snapshot = Path(temporary) / "source.pdf"
                snapshot.write_bytes(raw)  # Immutable parser input, not a project contract output.
                if isinstance(self.engines, LocalEngines) and (ocr_pages or paper['page_count'] > self.limits.text_batch_pages):
                    bundle = parse_batches(self, snapshot, paper, ocr_pages)
                    job.move('indexing', '批次已发布；合并参考文献与引用锚点', progress=80)
                else:
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
                return self._publish(bundle, job, pid)
        except PipelineError as error:
            if job.current["status"] not in {"completed", "failed"}:
                job.move("failed", "解析未完成", error=error)
            raise
        except Exception:
            error = PipelineError("PARSE_FAILED", "解析未完成；未发布不合规记录。")
            if job.current["status"] not in {"completed", "failed"}:
                job.move("failed", "解析未完成", error=error)
            raise error from None

    def _publish(self, bundle, job, pid):
        already_present = (self.store.root / "papers" / pid).exists()
        if self.semantic is not None:
            prior, assessment = self.semantic.assess(bundle, self.store)
        else:
            prior = self.store.dedup_candidate(bundle) if not already_present else None
            assessment = {"status": "disabled", "method": "doi_identity_token_dice", "reason": "语义向量未启用。"}
        comparison = compare(prior, bundle, self.gate) if prior is not None and prior["paper_meta"]["id"] != pid else None
        if comparison and assessment["status"] == "ready":
            decision, diff = comparison
            decision["similarity"] = max(0.0, assessment["score"])
            if assessment["band"] == "manual_review":
                decision["recommendation"] = "manual_review"
            if assessment["band"] == "duplicate":
                old, new = prior["paper_meta"], bundle["paper_meta"]
                if old["arxiv_id"] and new["arxiv_id"] and re.sub(r"v\d+$", "", old["arxiv_id"]) == re.sub(r"v\d+$", "", new["arxiv_id"]):
                    a, b = re.fullmatch(r"v(\d+)", old["version"] or ""), re.fullmatch(r"v(\d+)", new["version"] or "")
                    if a and b and int(b[1]) > int(a[1]):
                        decision["recommendation"] = "keep_new"
                        for evidence in decision["evidence"]:
                            evidence["reason"] = f"建议保留本次较新版本（{new['version']}），依据同一 arXiv 身份及更高版本号；不代表学术质量更高。" + evidence["reason"]
            for evidence in decision["evidence"]:
                evidence["reason"] += f" 本地 BGE-M3 语义余弦={assessment['score']:.9f}；分档={assessment['band']}。{assessment['reason']}"
            self.gate.comparison(decision, diff, [prior, bundle])
        job.move("indexing", "Schema 与外键校验通过", progress=95)
        self.last_output = self.store.paper(bundle)
        self.last_comparison = self.store.comparison(*comparison, [prior, bundle]) if comparison else None
        if comparison:
            self.last_warning = comparison[0]["evidence"][0]["reason"]
            assessment["recommendation"] = comparison[0]["recommendation"]
        if already_present:
            self.last_warning = "同一文件内容已入库；换名重传触发重复判定，保留已有论文，不重复入库。"
            assessment.update(band="duplicate", recommendation="keep_old", exact_file_hash=True)
            if assessment["status"] != "ready":
                assessment.update(method="file_hash", score=None)
        self.last_dedup_metadata = assessment
        parent = self.store.root / "semantic-dedup" / "assessments" / pid
        parent.mkdir(parents=True, exist_ok=True)
        temporary = parent / (uuid4().hex + ".tmp")
        try:
            write_json(temporary, assessment)
            windows_retry(lambda: os.replace(temporary, parent / "latest.json"))
        finally:
            temporary.unlink(missing_ok=True)
        job.move("completed", "四类记录与去重判定已通过校验并发布")
        return bundle

    @staticmethod
    def _inspect(raw: bytes, digest: str, *, max_pages=2000, threshold=32):
        if not raw.startswith(b"%PDF-"):
            raise PipelineError("PARSE_FAILED", "文件内容不是合法 PDF。")
        try:
            reader = PdfReader(io.BytesIO(raw), strict=True)
            if reader.is_encrypted:
                raise PipelineError("PARSE_FAILED", "本单不处理加密 PDF。")
            count = len(reader.pages)
            if count < 1 or count > max_pages:
                raise PipelineError("PARSE_FAILED", f"PDF 页数必须在 1 到 {max_pages} 之间（可配置）。")
            if count > threshold:
                first, ocr_pages, has_text = '', [], False
                document = pdfium.PdfDocument(raw)
                try:
                    for n in range(count):
                        page = document[n]
                        textpage = page.get_textpage()
                        try:
                            text = textpage.get_text_range().strip()
                            if text:
                                has_text = True
                                if not first:
                                    first = text
                            elif any(obj.type == 3 for obj in page.get_objects()):
                                ocr_pages.append(n)
                        finally:
                            textpage.close()
                            page.close()
                finally:
                    document.close()
                meta = reader.metadata
            else:
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
                has_text = any(text.strip() for text in texts)
            version = re.search(r"(?:^|\n)\s*Version:\s*(v\d+)\b", first, re.I)
            arxiv = re.search(r'arXiv\s*:\s*(\d{4}\.\d{4,5})(v\d+)?', first, re.I)
            doi_line = re.search(r"(?:^|\n)\s*DOI:\s*([^\n]+)", first, re.I)
            year_line = re.search(r"(?:^|\n)\s*Year:\s*((?:18|19|20)\d{2})\b", first)
            paper = {"schema_version": "1.0.0", "id": "paper-" + digest,
                     "title": (str(meta.title).strip() or None) if meta and meta.title else None,
                     "authors": [str(meta.author).strip()] if meta and meta.author and str(meta.author).strip() else [],
                     "institutions": [], "abstract": None,
                     "year": int(year_line[1]) if year_line else None, "source": "local-upload",
                     "arxiv_id": arxiv[1] + (arxiv[2] or '') if arxiv else None, "doi": doi(doi_line[1]) if doi_line else None,
                     "version": version[1] if version else (arxiv[2] if arxiv else None), "file_hash": digest,
                     "page_count": count, "has_text_layer": has_text}
            return paper, ocr_pages
        except PipelineError:
            raise
        except Exception:
            raise PipelineError("PARSE_FAILED", "PDF 结构或文本层检查失败。") from None
