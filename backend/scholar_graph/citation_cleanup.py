"""Explicit maintenance: remove identical citation occurrences, never distinct anchors."""

import hashlib
import json
import os
from uuid import uuid4

from .atomic_io import windows_retry
from .storage import FILES, write_json
from .tracking_state import operation_lock, utc_now


def clean_citations(repository, *, locked=False):
    if not locked:
        with operation_lock(repository.root, "ingestion", timeout=30):
            return clean_citations(repository, locked=True)
    result = {"papers_scanned": 0, "papers_changed": 0, "links_before": 0, "links_after": 0,
              "removed_count": 0, "changes": []}
    for directory in sorted((repository.root / "papers").glob("*")):
        if not directory.is_dir() or directory.name.startswith("."):
            continue
        bundle = {key: json.loads((directory / filename).read_text(encoding="utf-8")) for key, filename in FILES.items()}
        seen, retained = set(), []
        for link in bundle["citation_links"]:
            repository.gate.record("CitationLink", link)
            key = tuple(link[field] for field in ("paper_id", "citation_number", "page_number", "chunk_id", "ref_id"))
            if key not in seen:
                seen.add(key)
                retained.append(link)
        before = len(bundle["citation_links"])
        bundle["citation_links"] = retained
        repository.gate.bundle(bundle)  # Bad foreign keys/anchors still fail, never silently removed.
        result["papers_scanned"] += 1
        result["links_before"] += before
        result["links_after"] += len(retained)
        if before == len(retained):
            continue
        target = directory / FILES["citation_links"]
        temporary = directory / (".citations-" + uuid4().hex + ".tmp")
        audit = repository.root / "tracking" / "citation-cleanups" / uuid4().hex
        audit.mkdir(parents=True)
        # Durable preimage enables recovery/audit; only the citation file is atomically replaced.
        write_json(audit / "before.json", json.loads(target.read_text(encoding="utf-8")))
        try:
            write_json(temporary, retained)
            change = {"paper_id": bundle["paper_meta"]["id"], "removed_count": before - len(retained),
                "at": utc_now(), "before_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "after_sha256": hashlib.sha256(temporary.read_bytes()).hexdigest(),
                "audit_ref": str(audit.relative_to(repository.root)).replace("\\", "/")}
            write_json(audit / "intent.json", change)
            windows_retry(lambda: os.replace(temporary, target))
            write_json(audit / "completed.json", change)
        finally:
            windows_retry(lambda: temporary.unlink(missing_ok=True))
        result["papers_changed"] += 1
        result["removed_count"] += before - len(retained)
        result["changes"].append(change)
    return result
