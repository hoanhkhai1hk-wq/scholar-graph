"""Read validated module-one publications without changing their format."""

import json
import re
from pathlib import Path

from .errors import PipelineError
from .storage import RecordStore
from .chunk_index import ChunkIndex
from .api_transport import paginate


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
            return self.store.partial(paper_id)
        return self.store.load(target)

    def chunk_page(self, paper_id, page, page_size):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', paper_id):
            raise PipelineError('PAPER_NOT_FOUND', '无该论文记录。')
        index = ChunkIndex(self.root, paper_id)
        if not index.path.is_file():
            return paginate(self.paper(paper_id)['chunks'], page, page_size)
        # Each batch was gated before indexing. Validate returned records again, without
        # loading every page/layout payload just to serve one page of results.
        value = index.page(page, min(100, page_size))
        for chunk in value['items']:
            self.gate.record('Chunk', chunk)
            if chunk['paper_id'] != paper_id:
                raise PipelineError('VALIDATION_ERROR', '索引分块归属不一致。')
        return value

    def papers(self, *, title=None, year=None, source=None):
        parent = self.root / "papers"
        values = []
        if parent.exists():
            for directory in sorted(parent.iterdir()):
                if directory.is_dir() and not directory.name.startswith("."):
                    metadata_path = directory / "paper-meta.json"
                    try:
                        meta = json.loads(metadata_path.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        raise PipelineError("VALIDATION_ERROR", "论文基础信息不可读取。") from None
                    self.gate.record("PaperMeta", meta)
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

    def comparison(self, paper_id, *, kind):
        candidates = []
        for directory in (self.root / "comparisons").glob("comparison-*"):
            if not directory.is_dir():
                continue
            try:
                decisions = json.loads((directory / "dedup-decisions.json").read_text(encoding="utf-8"))
                diff = json.loads((directory / "diff-summary.json").read_text(encoding="utf-8"))
                if not isinstance(decisions, list) or not decisions:
                    raise ValueError
                self.gate.record("DiffSummary", diff)
                for decision in decisions:
                    self.gate.record("DedupDecision", decision)
                if diff["new_paper_id"] != paper_id:
                    continue
                bundles = [self.paper(diff[key]) for key in ("old_paper_id", "new_paper_id")]
                for decision in decisions:
                    self.gate.comparison(decision, diff, bundles)
                # Any human decision takes precedence over subsequent system-only suggestions.
                selected = next((item for item in reversed(decisions) if item["human_override"]), decisions[-1])
                candidates.append((selected["human_override"], directory.stat().st_mtime_ns,
                                   directory.name, selected, diff))
            except (ValueError, OSError):
                raise PipelineError("VALIDATION_ERROR", "去重或差异记录不可读取。") from None
        if not candidates:
            message = "无该新版论文的去重记录。" if kind == "decision" else "无该新版论文的差异记录。"
            raise PipelineError("PAPER_NOT_FOUND", message)
        selected = max(candidates, key=lambda item: item[:3])
        return selected[3 if kind == "decision" else 4]
