"""Ordered synchronous uploads using the existing local parsing pipeline."""

import tempfile
import json
from pathlib import Path
from threading import Lock
from urllib.parse import quote

from .errors import PipelineError
from .pipeline import Pipeline
from .tracking_state import operation_lock
from .pdf_files import PdfFiles
from .grobid_enrichment import DefaultGrobid
from .parse_provenance import response_header,summary as parse_summary

MAX_BYTES = 50 * 1024 * 1024


class UploadService:
    def __init__(self, root, gate, pipeline_factory=None):
        self.root, self.gate = root, gate
        self.factory = pipeline_factory or (lambda: Pipeline(root, gate=gate,enhancement=DefaultGrobid()))
        self.lock = Lock()

    def _one(self, upload, *, cancelled=None, on_page_progress=None):
        filename = upload.filename or "(unnamed)"
        if Path(filename).suffix.lower() != ".pdf":
            raise PipelineError("UNSUPPORTED_FILE_TYPE", "上传文件必须为 PDF。")
        parent = self.root / ".uploads"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="upload-", dir=parent) as directory:
            path = Path(directory) / "source.pdf"
            size = 0
            with path.open("wb") as output:
                while block := upload.file.read(1024 * 1024):
                    size += len(block)
                    if size > MAX_BYTES:
                        raise PipelineError("FILE_TOO_LARGE", "PDF 超过 50 MiB 限制。")
                    output.write(block)
            pipeline = self.factory()
            if cancelled is not None:
                pipeline.cancel_requested = cancelled
            if on_page_progress is not None:
                pipeline.on_page_progress = on_page_progress
            bundle = pipeline.parse(path)
            self.gate.bundle(bundle)
            PdfFiles(self.root).retain(path, bundle["paper_meta"])
            initial = pipeline.last_job.history[0]
            self.gate.record("ParseStatus", initial)
            return bundle["paper_meta"], initial, getattr(pipeline, 'last_warning', None), getattr(pipeline, 'last_dedup_metadata', None),getattr(pipeline,'last_parse_metadata',None)

    def single(self, upload, response=None):
        with self.lock, operation_lock(self.root, "ingestion", timeout=30):
            meta, _, warning, dedup,parse_metadata = self._one(upload)
            if response is not None:response_header(response,parse_metadata)
            if response is not None and dedup is not None:
                # Keep frozen PaperMeta intact. Bounded summary only; full scores are local.
                fields = ("status", "method", "score", "band", "reason", "fallback_reason", "matched_paper_id", "recommendation", "exact_file_hash")
                summary = {key: dedup[key] for key in fields if key in dedup}
                response.headers["X-ScholarGraph-Dedup-Meta"] = quote(json.dumps(summary, ensure_ascii=False, allow_nan=False), safe="")
            if warning and response is not None:
                response.headers['X-ScholarGraph-Dedup-Warning'] = quote(warning, safe='')
                response.headers['X-ScholarGraph-Dedup-Warning-Encoding'] = 'percent-encoded-utf-8'
                if not (dedup and dedup.get("exact_file_hash")):
                    response.headers['Link'] = f'</api/v1/papers/{meta["id"]}/dedup-decision>; rel="dedup-decision"'
            return meta

    def batch(self, parts):
        succeeded, failed = [], []
        with self.lock, operation_lock(self.root, "ingestion", timeout=30):
            for field, upload in parts:
                filename = getattr(upload, "filename", None) or "(unnamed)"
                try:
                    if field != "files" or not hasattr(upload, "file"):
                        raise PipelineError("VALIDATION_ERROR", "批量上传只接受 files 文件字段。")
                    meta, initial, warning, dedup,parse_metadata = self._one(upload)
                    succeeded.append({"paper_id": meta["id"], "parse_status": initial})
                    if parse_metadata is not None:succeeded[-1]['parse_metadata']=parse_summary(parse_metadata)
                    if warning:
                        succeeded[-1]['warning'] = warning
                    if dedup is not None:
                        succeeded[-1]['dedup_metadata'] = {key: dedup[key] for key in ("status", "method", "score", "band", "reason", "fallback_reason", "recommendation") if key in dedup}
                except Exception as error:
                    if not isinstance(error, PipelineError):
                        error = PipelineError("INTERNAL_ERROR", "该文件处理失败。")
                    self.gate.error(error.envelope())
                    failed.append({"filename": filename, "error_code": error.code,
                                   "error_message": error.message})
        return {"succeeded": succeeded, "failed": failed,
                "succeeded_count": len(succeeded), "failed_count": len(failed)}
