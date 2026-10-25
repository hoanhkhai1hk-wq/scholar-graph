"""Explicitly corrupted self-made citation data; no official PDF assertions."""

import copy
import json

import pytest
from fastapi.testclient import TestClient

from graph_samples import graph_bundles
from scholar_graph.api import create_app
from scholar_graph.citation_cleanup import clean_citations
from scholar_graph.errors import PipelineError
from scholar_graph.storage import write_json


def prepare(tmp_path):
    app = create_app(data_dir=tmp_path)
    bundle = graph_bundles()[0]
    app.state.repository.store.paper(bundle)
    path = tmp_path / "papers" / bundle["paper_meta"]["id"] / "citation-links.json"
    return app, bundle, path


def test_duplicate_cleanup_is_atomic_validated_audited_and_idempotent(tmp_path):
    app, bundle, path = prepare(tmp_path)
    write_json(path, bundle["citation_links"] * 3)
    response = TestClient(app).post("/api/v1/retrieval/citations/cleanup")
    assert response.status_code == 200
    result = response.json()
    assert result["removed_count"] == 2 and result["links_before"] == 3 and result["links_after"] == 1
    assert app.state.repository.paper(bundle["paper_meta"]["id"]) == bundle
    audit = tmp_path / result["changes"][0]["audit_ref"]
    assert len(json.loads((audit / "before.json").read_text(encoding="utf-8"))) == 3
    assert (audit / "completed.json").is_file()
    assert clean_citations(app.state.repository)["removed_count"] == 0


def test_distinct_chunk_occurrences_remain_and_invalid_anchor_is_not_deleted(tmp_path):
    app, bundle, path = prepare(tmp_path)
    invalid = copy.deepcopy(bundle["citation_links"][0])
    invalid["chunk_id"] = "missing"
    write_json(path, bundle["citation_links"] * 2 + [invalid])
    before = path.read_bytes()
    with pytest.raises(PipelineError):
        clean_citations(app.state.repository)
    assert path.read_bytes() == before


def test_different_real_chunk_anchors_are_not_duplicates(tmp_path):
    app, bundle, path = prepare(tmp_path)
    second = copy.deepcopy(bundle["chunks"][0])
    second["chunk_id"] += "-other"
    bundle["chunks"].append(second)
    link = copy.deepcopy(bundle["citation_links"][0])
    link["chunk_id"] = second["chunk_id"]
    bundle["citation_links"].append(link)
    write_json(path.parent / "chunks.json", bundle["chunks"])
    write_json(path, bundle["citation_links"])
    result = clean_citations(app.state.repository)
    assert result["removed_count"] == 0 and result["links_after"] == 2
