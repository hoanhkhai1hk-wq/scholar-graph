import json
from urllib.parse import unquote

from fastapi.testclient import TestClient

from scholar_graph.api import create_app
from scholar_graph.errors import PipelineError
from test_dedup import versions


def api(tmp_path):
    app = create_app(data_dir=tmp_path)
    for bundle in versions():
        app.state.repository.store.paper(bundle)
    return TestClient(app), [b['paper_meta']['id'] for b in versions()]


def test_direct_deepseek_missing_configuration_returns_upstream_error(tmp_path, monkeypatch):
    client, ids = api(tmp_path)
    monkeypatch.setenv('SCHOLAR_GRAPH_QA_MODE', 'deepseek')
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.delenv('DEEPSEEK_MODEL', raising=False)
    response = client.post(f'/api/v1/papers/{ids[0]}/qa', json={'question': 'How many samples?'})
    assert response.status_code == 502
    assert response.json()['error_code'] == 'UPSTREAM_ERROR'
    assert set(response.json()) == {'error_code', 'message', 'details'}
    response = client.post('/api/v1/compare', json={'paper_ids': ids, 'question': 'How many samples?'})
    assert response.status_code == 502


def test_explicit_agent_fallback_is_visible_and_record_schema_unchanged(tmp_path, monkeypatch):
    client, ids = api(tmp_path)
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.delenv('DEEPSEEK_MODEL', raising=False)
    response = client.post('/api/v1/compare?agent=true', json={'paper_ids': ids, 'question': 'How many samples?'})
    assert response.status_code == 200
    metadata = json.loads(unquote(response.headers['X-ScholarGraph-Agent-Meta']))
    assert metadata['fallback_reason'] == 'MODEL_CONFIGURATION_UNAVAILABLE'
    assert metadata['model_calls'] == metadata['tool_calls'] == []
    assert set(response.json()) == {'evidence_table', 'per_paper', 'synthesis'}
