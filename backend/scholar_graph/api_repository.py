"""Read validated module-one publications without changing their format."""

import json
import re
from pathlib import Path

from .errors import PipelineError
from .storage import RecordStore


class ApiRepository:
    def __init__(self, root, gate):
        self.root = Path(root).resolve()
        self.gate = gate
        self.store = RecordStore(self.root, gate)

    def paper(self, paper_id):
        parent = self.root / "papers"
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", paper_id):
            raise PipelineError("PAPER_NOT_FOUND", "无该论文记录。")
        target = (parent / paper_id).resolve()
        if target.parent != parent.resolve() or not target.is_dir():
            raise PipelineError("PAPER_NOT_FOUND", "无该论文记录。")
        return self.store.load(target)

    def papers(self, *, title=None, year=None, source=None):
        parent = self.root / "papers"
        values = []
        if parent.exists():
            for directory in sorted(parent.iterdir()):
                if directory.is_dir() and not directory.name.startswith("."):
                    meta = self.paper(directory.name)["paper_meta"]
                    if title is not None and title.casefold() not in (meta["title"] or "").casefold():
                        continue
                    if year is not None and year != meta["year"]:
                        continue
                    if source is not None and source != meta["source"]:
                        continue
                    values.append(meta)
        return values

    def status(self, paper_id):
        candidates = []
        for path in (self.root / "jobs").glob("job-*/parse-status.json"):
            try:
                history = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(history, list) or not history:
                    raise ValueError
                for item in history:
                    self.gate.record("ParseStatus", item)
                if any(item["paper_id"] != history[0]["paper_id"] for item in history):
                    raise ValueError
                if history[-1]["paper_id"] == paper_id:
                    candidates.append((path.stat().st_mtime_ns, path.parent.name, history[-1]))
            except (ValueError, OSError):
                raise PipelineError("VALIDATION_ERROR", "解析状态记录不可读取。") from None
        if not candidates:
            raise PipelineError("PAPER_NOT_FOUND", "无该论文的解析状态记录。")
        return max(candidates, key=lambda item: item[:2])[2]
