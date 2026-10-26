"""Offline comparison stream protocol; synthetic records and simulated provider."""
import json

import pytest
from fastapi.testclient import TestClient

from scholar_graph.api import create_app
from scholar_graph.deepseek_client import StreamCancelled
from scholar_graph.qa_compare import validate_comparison
from scholar_graph.qa_retrieval import QAHybridRetriever
from test_agent_orchestration import Model, repository
from test_qa_hybrid_retrieval import Vector
from test_qa_sse import parse_events


class StreamingModel(Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cancelled = False
    def stream_complete(self, messages, *, on_delta, **kwargs):
        message = self.complete(messages, **kwargs)
        for i in range(0, len(message['content']), 19):
            on_delta(message['content'][i:i+19])
        return message
    def cancel(self):
        self.cancelled = True


def api(tmp_path, monkeypatch, *, vector=True, fail_vector=False, model=None):
    repo, ids = repository(tmp_path)
    app = create_app(data_dir=tmp_path)
    service = QAHybridRetriever(repo, Vector(fail=fail_vector) if vector else None)
    monkeypatch.setattr('scholar_graph.orchestration.qa_retriever', lambda _: service)
    monkeypatch.setenv('SCHOLAR_GRAPH_QA_MODE', 'deepseek')
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'unit-private-credential')
    monkeypatch.setenv('DEEPSEEK_MODEL', 'deepseek-mock')
    gateway = model or StreamingModel()
    monkeypatch.setattr('scholar_graph.qa_sse.DeepSeekClient.environment', lambda: gateway)
    return TestClient(app), repo, ids, gateway


def run(client, ids):
    response = client.post('/api/v1/compare/stream', json={'paper_ids': ids, 'question': 'How many samples?'})
    assert response.status_code == 200 and response.headers['content-type'].startswith('text/event-stream')
    assert 'content-length' not in response.headers
    return parse_events(response.text)


def final_record(events, repo, ids):
    assert [e['event'] for e in events[-2:]] == ['final', 'done']
    assert [e['id'] for e in events] == list(range(1, len(events)+1))
    value = events[-2]['data']
    validate_comparison(value, [repo.paper(pid) for pid in ids], repo.gate)
    assert not any(r['refused'] for r in value['per_paper'])
    assert events[-1]['data']['verified'] is True
    assert set(value) == {'evidence_table', 'per_paper', 'synthesis'}


def test_comparison_drafts_precede_validation_and_final_uses_existing_shape(tmp_path, monkeypatch):
    client, repo, ids, model = api(tmp_path, monkeypatch)
    events = run(client, ids)
    final_record(events, repo, ids)
    tokens = [e for e in events if e['event'] == 'token']
    assert tokens and all(not e['data']['verified'] and e['data']['channel'] == 'model_json_draft' for e in tokens)
    validation = next(e for e in events if e['event'] == 'node_start' and e['data']['node'] == 'validate')
    assert tokens[-1]['id'] < validation['id'] < events[-2]['id']
    assert events[-1]['data']['metadata']['method'] == 'hybrid'
    assert events[-1]['data']['metadata']['ranking_method'] == 'rrf'
    assert model.cancelled


@pytest.mark.parametrize('fallback', ['no_key', 'no_vector', 'failed_vector'])
def test_non_token_fallback_is_explicit_and_has_no_fabricated_deltas(tmp_path, monkeypatch, fallback):
    client, repo, ids, model = api(tmp_path, monkeypatch, vector=fallback != 'no_vector', fail_vector=fallback == 'failed_vector')
    if fallback == 'no_key':
        monkeypatch.delenv('DEEPSEEK_API_KEY')
    events = run(client, ids)
    final_record(events, repo, ids)
    assert not any(e['event'] == 'token' for e in events)
    assert not events[-1]['data']['token_streaming']
    assert events[-1]['data']['fallback_reason'] in ('MODEL_CONFIGURATION_UNAVAILABLE', 'LOCAL_VECTOR_NOT_CONFIGURED', 'LOCAL_VECTOR_UNAVAILABLE')
    modes = [e['data'] for e in events if e['event'] == 'mode']
    assert modes[-1]['token_streaming'] is False and '回落模式、非 token 流式' in modes[-1]['message']
    assert not model.calls or all(c['phase'] == 'plan' for c in model.calls)
    if fallback != 'failed_vector':
        assert not any(e['event'].startswith('tool_') for e in events)


@pytest.mark.parametrize('phase', ['plan', 'qa'])
def test_comparison_model_failure_sends_error_without_final(tmp_path, monkeypatch, phase):
    client, _, ids, _ = api(tmp_path, monkeypatch, model=StreamingModel(unavailable=phase))
    events = run(client, ids)
    assert [e['event'] for e in events[-2:]] == ['error', 'done']
    assert events[-2]['data']['error_code'] == 'UPSTREAM_ERROR'
    assert not any(e['event'] == 'final' for e in events)


def test_invalid_drafts_are_separate_from_the_accepted_third_attempt(tmp_path, monkeypatch):
    client, repo, ids, _ = api(tmp_path, monkeypatch, model=StreamingModel(invalid=2))
    events = run(client, ids)
    final_record(events, repo, ids)
    validations = [e['data'] for e in events if e['event'] == 'node_end' and e['data']['node'] == 'validate']
    assert [v['validation'] for v in validations] == [False, False, True]
    assert validations[0]['validation_error'] == '模型摘录与候选原文字面不一致。'
    assert {e['data']['attempt'] for e in events if e['event'] == 'token'} == {1, 2, 3}
    assert '9999' not in json.dumps(events[-2]['data'])


def test_missing_or_duplicate_papers_are_http_errors_before_sse(tmp_path, monkeypatch):
    client, _, ids, model = api(tmp_path, monkeypatch)
    for collection, status in [(ids[:1]+['missing'], 404), ([ids[0]]*2, 422)]:
        response = client.post('/api/v1/compare/stream', json={'paper_ids': collection, 'question': 'samples'})
        assert response.status_code == status and response.headers['content-type'].startswith('application/json')
        assert set(response.json()) == {'error_code', 'message', 'details'}
    assert not model.calls
