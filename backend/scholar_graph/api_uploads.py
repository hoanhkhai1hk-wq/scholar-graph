"""Ordered synchronous uploads using the existing local parsing pipeline."""

import tempfile
from pathlib import Path
from threading import Lock

from .errors import PipelineError
from .pipeline import Pipeline

MAX_BYTES = 50 * 1024 * 1024


class UploadService:
    def __init__(self, root, gate, pipeline_factory=None):
        self.root, self.gate = root, gate
        self.factory = pipeline_factory or (lambda: Pipeline(root, gate=gate))
        self.lock = Lock()

    def _one(self, upload):
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
            bundle = pipeline.parse(path)
            self.gate.bundle(bundle)
            initial = pipeline.last_job.history[0]
            self.gate.record("ParseStatus", initial)
            return bundle["paper_meta"], initial

    def single(self, upload):
        with self.lock:
            return self._one(upload)[0]

    def batch(self, parts):
        succeeded, failed = [], []
        with self.lock:
            for field, upload in parts:
                filename = getattr(upload, "filename", None) or "(unnamed)"
                try:
                    if field != "files" or not hasattr(upload, "file"):
                        raise PipelineError("VALIDATION_ERROR", "批量上传只接受 files 文件字段。")
                    meta, initial = self._one(upload)
                    succeeded.append({"paper_id": meta["id"], "parse_status": initial})
                except Exception as error:
                    if not isinstance(error, PipelineError):
                        error = PipelineError("INTERNAL_ERROR", "该文件处理失败。")
                    self.gate.error(error.envelope())
                    failed.append({"filename": filename, "error_code": error.code,
                                   "error_message": error.message})
        return {"succeeded": succeeded, "failed": failed,
                "succeeded_count": len(succeeded), "failed_count": len(failed)}
