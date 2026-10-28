import json
import os

import pytest
from fastapi.testclient import TestClient

from scholar_graph.api import create_app
from scholar_graph.dedup import compare, human_decision
from test_api_read import assert_error
from test_dedup import versions


@pytest.mark.parametrize("suffix,label", [("dedup-decision", "去重"), ("diff-summary", "差异")])
def test_new_paper_key_and_no_record_404(tmp_path, suffix, label):
    app = create_app(data_dir=tmp_path)
    repo = app.state.repository
    old, new = versions()
    for bundle in (old, new):
        repo.store.paper(bundle)
    client = TestClient(app)
    decision, diff = compare(old, new, repo.gate)
    for pid in (old["paper_meta"]["id"], new["paper_meta"]["id"], "missing"):
        response = client.get(f"/api/v1/papers/{pid}/{suffix}")
        assert_error(response, 404, "PAPER_NOT_FOUND")
        assert f"无该新版论文的{label}记录" in response.json()["message"]
    repo.store.comparison(decision, diff, [old, new])
    assert client.get(f'/api/v1/papers/{new["paper_meta"]["id"]}/{suffix}').json() == (
        decision if suffix == "dedup-decision" else diff)
    assert_error(client.get(f'/api/v1/papers/{old["paper_meta"]["id"]}/{suffix}'), 404, "PAPER_NOT_FOUND")


def test_human_override_survives_later_system_and_reads_are_immutable(tmp_path):
    app = create_app(data_dir=tmp_path)
    repo = app.state.repository
    old, new = versions()
    for bundle in (old, new):
        repo.store.paper(bundle)
    decision, diff = compare(old, new, repo.gate)
    human = human_decision(decision, "keep_both", "人工核对后保留两版。", diff, [old, new], repo.gate)
    first = repo.store.comparison(decision, diff, [old, new], human=human)
    before = (first / "dedup-decisions.json").read_bytes()
    later = repo.store.comparison(decision, diff, [old, new])
    future = first.stat().st_mtime_ns + 1_000_000_000
    os.utime(later, ns=(future, future))
    with TestClient(app) as client:
        assert client.get(f'/api/v1/papers/{new["paper_meta"]["id"]}/dedup-decision').json() == human
        assert client.get(f'/api/v1/papers/{new["paper_meta"]["id"]}/diff-summary').json() == diff
    assert (first / "dedup-decisions.json").read_bytes() == before
    assert json.loads(before)[0] == decision


def test_nineteen_business_routes_including_module_six(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))
    paths = client.get("/openapi.json").json()["paths"]
    assert sum(len(methods) for path, methods in paths.items() if path.startswith('/api/v1/')) == 30
    assert 'get' in paths['/api/v2/system']
    assert "get" in paths["/api/v1/papers/{paper_id}/file"]
    assert 'post' in paths['/api/v1/papers/{paper_id}/qa/stream']
    assert 'post' in paths['/api/v1/compare/stream']
    assert 'post' in paths['/api/v1/papers/{paper_id}/translate']
    assert 'post' in paths['/api/v1/topologies']
    assert 'post' in paths['/api/v1/charts/csv/3d']
    for path in ("/reviews", "/charts/csv", "/frameworks"):
        assert "post" in paths["/api/v1" + path]
        assert_error(client.get("/api/v1" + path), 405, "VALIDATION_ERROR")
