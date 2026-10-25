"""Validated, atomic publication and immutable paper/comparison directories."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from .errors import PipelineError
from .validation import ContractGate
from .atomic_io import windows_retry
from .dedup import similarity

FILES = {"paper_meta": "paper-meta.json", "chunks": "chunks.json",
         "reference_entries": "reference-entries.json", "citation_links": "citation-links.json"}


def write_json(path: Path, value):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def discard_staging(path: Path, parent: Path):
    resolved, allowed = path.resolve(), parent.resolve()
    if resolved.parent != allowed or not resolved.name.startswith(".pending-"):
        raise PipelineError("VALIDATION_ERROR", "临时目录超出允许清理范围。")
    windows_retry(lambda: shutil.rmtree(resolved))


class RecordStore:
    def __init__(self, root: Path, gate: ContractGate):
        self.root, self.gate = root.resolve(), gate

    def statuses(self, job_id: str, history: list[dict]):
        for record in history:
            self.gate.record("ParseStatus", record)
        parent = self.root / "jobs" / job_id
        parent.mkdir(parents=True, exist_ok=True)
        temporary = parent / f".status-{uuid4().hex}.tmp"
        try:
            write_json(temporary, history)
            windows_retry(lambda: os.replace(temporary, parent / "parse-status.json"))
        finally:
            windows_retry(lambda: temporary.unlink(missing_ok=True))

    def paper(self, bundle: dict) -> Path:
        self.gate.bundle(bundle)  # No directory or file is created before this returns.
        parent = self.root / "papers"
        target = parent / bundle["paper_meta"]["id"]
        if target.exists():
            if self.load(target) != bundle:
                raise PipelineError("VALIDATION_ERROR", "已有论文记录不可覆盖。")
            return target
        parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".pending-", dir=parent))
        try:
            for key, filename in FILES.items():
                write_json(staging / filename, bundle[key])
            # Rename within the same filesystem; incomplete groups are never visible as papers.
            windows_retry(lambda: staging.rename(target))
        finally:
            if staging.exists():
                discard_staging(staging, parent)
        return target

    def load(self, directory: Path) -> dict:
        try:
            bundle = {key: json.loads((directory / filename).read_text(encoding="utf-8"))
                      for key, filename in FILES.items()}
            self.gate.bundle(bundle)
            return bundle
        except PipelineError:
            raise
        except (OSError, ValueError):
            raise PipelineError("VALIDATION_ERROR", "不能读取完整、合法的论文记录组。") from None

    def previous_version(self, paper: dict) -> dict | None:
        """Exact local identity lookup for uploads, not semantic retrieval or recommendation."""
        self.gate.record("PaperMeta", paper)
        parent = self.root / "papers"
        if not parent.exists():
            return None
        matches = []
        def title_authors(record):
            return (" ".join((record["title"] or "").casefold().split()),
                    tuple(" ".join(name.casefold().split()) for name in record["authors"]))
        for directory in parent.iterdir():
            if not directory.is_dir() or not directory.name.startswith("paper-"):
                continue
            other = self.load(directory)
            metadata = other["paper_meta"]
            if metadata["id"] == paper["id"]:
                continue
            # Explicit conflicting persistent identifiers take precedence over title similarity.
            if paper["doi"] and metadata["doi"]:
                same = paper["doi"].casefold() == metadata["doi"].casefold()
            elif paper["arxiv_id"] and metadata["arxiv_id"]:
                same = re.sub(r"v\d+$", "", paper["arxiv_id"]) == re.sub(r"v\d+$", "", metadata["arxiv_id"])
            else:
                title, names = title_authors(paper)
                same = bool(title and names and (title, names) == title_authors(metadata))
            if same:
                matches.append((directory.stat().st_mtime_ns, directory.name, other))
        # This is local ingestion order only, never a publication date or quality ranking.
        return max(matches, key=lambda item: item[:2])[2] if matches else None

    def dedup_candidate(self, bundle: dict, *, threshold: float = .90) -> dict | None:
        """Exact identity first, then real token Dice; conflicting identifiers never pair."""
        exact = self.previous_version(bundle['paper_meta'])
        if exact is not None:
            return exact
        paper, candidates = bundle['paper_meta'], []
        for directory in (self.root / 'papers').glob('paper-*'):
            if not directory.is_dir() or directory.name == paper['id']:
                continue
            other = self.load(directory)
            meta = other['paper_meta']
            if paper['doi'] and meta['doi'] and paper['doi'].casefold() != meta['doi'].casefold():
                continue
            if paper['arxiv_id'] and meta['arxiv_id'] and re.sub(r'v\d+$', '', paper['arxiv_id']) != re.sub(r'v\d+$', '', meta['arxiv_id']):
                continue
            score = similarity(other, bundle)
            if score >= threshold:
                candidates.append((score, directory.name, other))
        return max(candidates, key=lambda row: row[:2])[2] if candidates else None

    def comparison(self, decision, diff, bundles, *, human=None) -> Path:
        self.gate.comparison(decision, diff, bundles)
        if decision["human_override"]:
            raise PipelineError("VALIDATION_ERROR", "必须先保留未覆盖的系统裁决。")
        if human is not None:
            self.gate.comparison(human, diff, bundles)
            if not human["human_override"]:
                raise PipelineError("VALIDATION_ERROR", "人工裁决必须显式标记。")
        parent = self.root / "comparisons"
        parent.mkdir(parents=True, exist_ok=True)
        target = parent / ("comparison-" + uuid4().hex)
        staging = Path(tempfile.mkdtemp(prefix=".pending-", dir=parent))
        try:
            write_json(staging / "dedup-decisions.json", [decision] + ([human] if human is not None else []))
            write_json(staging / "diff-summary.json", diff)
            windows_retry(lambda: staging.rename(target))
        finally:
            if staging.exists():
                discard_staging(staging, parent)
        return target
