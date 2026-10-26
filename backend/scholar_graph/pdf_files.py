"""Private original-PDF archive. Paper IDs are SQL keys, never filesystem paths."""
from contextlib import closing
import hashlib
import os
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from .atomic_io import windows_retry
from .errors import PipelineError

BLOCK_SIZE = 64 * 1024


def file_digest(path):
    digest, size = hashlib.sha256(), 0
    with path.open("rb") as source:
        while block := source.read(BLOCK_SIZE):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


class PdfFiles:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.folder = self.root / "original-pdfs"
        self.index = self.folder / "index.sqlite3"

    def _confined(self):
        if self.folder.is_symlink() or self.folder.resolve().parent != self.root or self.index.is_symlink():
            raise PipelineError("VALIDATION_ERROR", "PDF 原件存储位置不合法。")

    def _path(self, name):
        # Even a damaged index cannot introduce an arbitrary path or symlink.
        if not isinstance(name, str) or not re.fullmatch(r"[a-f0-9]{32}\.pdf", name):
            raise PipelineError("VALIDATION_ERROR", "PDF 原件映射不合法。")
        path = self.folder / name
        if path.is_symlink() or path.resolve().parent != self.folder.resolve():
            raise PipelineError("VALIDATION_ERROR", "PDF 原件路径不合法。")
        return path

    @staticmethod
    def _verified(path, digest, size):
        if not path.is_file():
            raise PipelineError("PAPER_NOT_FOUND", "该论文没有本地 PDF 原件；请重新上传同一原件补齐。")
        if file_digest(path) != (digest, size):
            raise PipelineError("VALIDATION_ERROR", "PDF 原件哈希或大小与入库记录不一致，拒绝返回。")

    def retain(self, source, paper):
        expected = paper.get("file_hash")
        if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
            raise PipelineError("VALIDATION_ERROR", "PDF 入库记录缺少合法文件哈希。")
        self._confined()
        self.folder.mkdir(parents=True, exist_ok=True)
        # Explicitly close SQLite handles, including on Windows and exception paths.
        with closing(sqlite3.connect(self.index, timeout=30)) as connection, connection:
            connection.execute("CREATE TABLE IF NOT EXISTS originals (paper_id TEXT PRIMARY KEY, "
                               "storage_name TEXT NOT NULL, sha256 TEXT NOT NULL, byte_count INTEGER NOT NULL)")
            connection.execute("BEGIN IMMEDIATE")
            old = connection.execute("SELECT storage_name, sha256, byte_count FROM originals WHERE paper_id=?",
                                     (paper["id"],)).fetchone()
            if old:
                if old[1] != expected:
                    raise PipelineError("VALIDATION_ERROR", "同一论文 id 的原件哈希不可改变。")
                path = self._path(old[0])
                if path.is_file():
                    self._verified(path, old[1], old[2])
                    return
            name = uuid4().hex + ".pdf"
            target = self._path(name)
            staging = self.folder / (".pending-" + uuid4().hex)
            published = False
            try:
                digest, size = hashlib.sha256(), 0
                with Path(source).open("rb") as original, staging.open("xb") as destination:
                    while block := original.read(BLOCK_SIZE):
                        destination.write(block)
                        digest.update(block)
                        size += len(block)
                    destination.flush()
                    os.fsync(destination.fileno())
                if digest.hexdigest() != expected:
                    raise PipelineError("VALIDATION_ERROR", "PDF 原件与已解析文件的 SHA-256 不一致。")
                windows_retry(lambda: os.replace(staging, target))
                connection.execute("INSERT INTO originals VALUES (?, ?, ?, ?) ON CONFLICT(paper_id) DO UPDATE SET "
                                   "storage_name=excluded.storage_name, sha256=excluded.sha256, byte_count=excluded.byte_count",
                                   (paper["id"], name, expected, size))
                connection.commit()
                published = True
            finally:
                staging.unlink(missing_ok=True)
                if not published:
                    target.unlink(missing_ok=True)

    def locate(self, paper_id):
        # Reject unsafe IDs before any lookup, but never form a path from the ID.
        if not isinstance(paper_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,255}", paper_id):
            raise PipelineError("PAPER_NOT_FOUND", "无该论文的 PDF 原件。")
        self._confined()
        if not self.index.is_file():
            raise PipelineError("PAPER_NOT_FOUND", "无该论文的本地 PDF 原件；历史记录需重新上传同一原件补齐。")
        with closing(sqlite3.connect(self.index.as_uri() + "?mode=ro", uri=True, timeout=30)) as connection:
            row = connection.execute("SELECT storage_name, sha256, byte_count FROM originals WHERE paper_id=?",
                                     (paper_id,)).fetchone()
        if row is None:
            raise PipelineError("PAPER_NOT_FOUND", "无该论文的本地 PDF 原件；历史记录需重新上传同一原件补齐。")
        path = self._path(row[0])
        self._verified(path, row[1], row[2])  # Bounded-memory integrity preflight, not read_bytes().
        return path
