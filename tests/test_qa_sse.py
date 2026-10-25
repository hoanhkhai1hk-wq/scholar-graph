"""Offline stream protocol and fallback tests. Mocks are never live acceptance evidence."""
import asyncio
import json
import threading

import httpx
import pytest
from fastapi.testclient import TestClient

from scholar_graph.api import create_app
from scholar_graph.deepseek_client import DeepSeekClient, StreamCancelled
from scholar_graph.qa_sse import answer_stream
from scholar_graph.validation import ContractGate
from test_validation_status import example_bundle


def parse_events(text):
    events = []
    for block in text.replace('\r\n', '\n').split('\n\n'):
        fields = dict(line.split(': ', 1) for line in block.splitlines() if ': ' in line and not line.startswith(':'))
        if 'event' in fields:
            events.append({'id': int(fields['id']), 'event': fields['event'], 'data': json.loads(fields['data'])})
    return events


def api(tmp_path):
    app = create_app(data_dir=tmp_path)
    bundle = example_bundle()
    app.state.repository.store.paper(bundle)
    return TestClient(app), app, bundle['paper_meta']['id']


def mock_gateway(monkeypatch, *, invalid=0, fail_phase=None, truncate=False):
    count = {'qa': 0}
    def handle(request):
        body = json.loads(request.content)
        if not body['stream']:
            if fail_phase == 'plan':
                return httpx.Response(500, text='unit-private-upstream-body')
            pid = json.loads(body['messages'][-1]['content'])['paper_ids'][0]
            return httpx.Response(200, json={'choices': [{'finish_reason': 'tool_calls', 'message': {
                'content': '', 'tool_calls': [{'id': 'unit_call', 'type': 'function', 'function': {'name': 'search',
                'arguments': json.dumps({'paper_ids': [pid], 'query': 'samples', 'limit': 4})}}]}}]})
        if fail_phase == 'qa':
            return httpx.Response(401, text='unit-private-upstream-body')
        assert body['stream_options']['include_usage'] and body['thinking']['type'] == 'disabled'
        payload = json.loads(body['messages'][-1]['content'])
        item = payload['evidence'][0]
        count['qa'] += 1
        value = {'answers': [{'paper_id': payload['paper_ids'][0], 'refused': False, 'claims': [{
            'evidence_id': item['evidence_id'], 'quote': 'Invented 9999 samples.' if count['qa'] <= invalid else item['quote']}]}]}
        content = json.dumps(value)
        chunks = [': heartbeat\n\n']
        for n in range(0, len(content), 13):
            chunks.append('data: ' + json.dumps({'choices': [{'index': 0, 'delta': {'content': content[n:n+13],
                'reasoning_content': 'unit-private-reasoning'}, 'finish_reason': None}]}) + '\n\n')
        if not truncate:
            chunks += ['data: ' + json.dumps({'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}],
                      'usage': {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30}}) + '\n\n', 'data: [DONE]\n\n']
        return httpx.Response(200, text=''.join(chunks), headers={'Content-Type': 'text/event-stream'})
    gateway = DeepSeekClient(key='unit-credential-not-real', model='deepseek-mock', transport=httpx.MockTransport(handle))
    monkeypatch.setenv('SCHOLAR_GRAPH_QA_MODE', 'deepseek')
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'unit-credential-not-real')
    monkeypatch.setenv('DEEPSEEK_MODEL', 'deepseek-mock')
    monkeypatch.setattr('scholar_graph.qa_sse.DeepSeekClient.environment', lambda: gateway)
    return gateway


@pytest.mark.parametrize('mode', ['extractive', 'deepseek'])
def test_fallback_trace_has_no_fake_tokens_and_final_is_exact_record(tmp_path, monkeypatch, mode):
    client, app, pid = api(tmp_path)
    monkeypatch.setenv('SCHOLAR_GRAPH_QA_MODE', mode)
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    response = client.post(f'/api/v1/papers/{pid}/qa/stream', json={'question': 'How many samples?'})
    assert response.status_code == 200 and response.headers['content-type'].startswith('text/event-stream')
    assert 'content-length' not in response.headers
    assert response.headers['x-accel-buffering'] == 'no' and 'no-cache' in response.headers['cache-control']
    events = parse_events(response.text)
    assert [e['id'] for e in events] == list(range(1, len(events) + 1))
    assert events[0]['event'] == 'mode' and '回落模式、非 token 流式' in events[0]['data']['message']
    assert not any(e['event'] in ('token', 'tool_start', 'tool_end') for e in events)
    assert [e['data']['node'] for e in events if e['event'] == 'node_start'] == ['plan', 'retrieve', 'qa', 'validate']
    assert [e['event'] for e in events[-2:]] == ['final', 'done']
    ContractGate().record('QAAnswer', events[-2]['data'])
    assert not events[-2]['data']['refused'] and events[-1]['data']['metadata']['model_calls'] == []


def test_deepseek_deltas_occur_inside_qa_with_actual_tool_events(tmp_path, monkeypatch):
    client, _, pid = api(tmp_path)
    gateway = mock_gateway(monkeypatch)
    events = parse_events(client.post(f'/api/v1/papers/{pid}/qa/stream', json={'question': 'How many samples?'}).text)
    start = next(n for n,e in enumerate(events) if e['event'] == 'node_start' and e['data']['node'] == 'qa')
    end = next(n for n,e in enumerate(events) if e['event'] == 'node_end' and e['data']['node'] == 'qa')
    tokens = [e for e in events[start+1:end] if e['event'] == 'token']
    assert tokens and all(not e['data']['verified'] for e in tokens)
    assert json.loads(''.join(e['data']['delta'] for e in tokens))['answers']
    tool = next(e for e in events if e['event'] == 'tool_end')['data']
    assert tool['origin'] == 'model_function_call' and tool['tool_name'] == 'search' and tool['evidence_count'] > 0
    assert events[-2]['event'] == 'final' and events[-1]['data']['status'] == 'completed'
    ContractGate().record('QAAnswer', events[-2]['data'])
    assert gateway.calls[-1]['total_tokens'] == 30
    assert all(secret not in json.dumps(events) for secret in ('unit-private-reasoning', 'unit-credential-not-real'))


@pytest.mark.parametrize('phase', ['plan', 'qa'])
def test_model_error_ends_stream_without_fallback_or_final(tmp_path, monkeypatch, phase):
    client, _, pid = api(tmp_path)
    mock_gateway(monkeypatch, fail_phase=phase)
    events = parse_events(client.post(f'/api/v1/papers/{pid}/qa/stream', json={'question': 'samples'}).text)
    assert [e['event'] for e in events[-2:]] == ['error', 'done']
    assert set(events[-2]['data']) == {'error_code', 'message', 'details'}
    assert events[-2]['data']['error_code'] == 'UPSTREAM_ERROR'
    assert not any(e['event'] == 'final' for e in events) and events[-1]['data']['status'] == 'error'
    assert 'unit-private-upstream-body' not in json.dumps(events)


def test_truncated_stream_never_returns_final(tmp_path, monkeypatch):
    client, _, pid = api(tmp_path)
    mock_gateway(monkeypatch, truncate=True)
    events = parse_events(client.post(f'/api/v1/papers/{pid}/qa/stream', json={'question': 'samples'}).text)
    assert [e['event'] for e in events[-2:]] == ['error', 'done']
    assert not any(e['event'] == 'final' for e in events)


@pytest.mark.parametrize('invalid', [2, 99])
def test_validation_rejection_reason_and_bounded_rounds_are_streamed(tmp_path, monkeypatch, invalid):
    client, _, pid = api(tmp_path)
    mock_gateway(monkeypatch, invalid=invalid)
    events = parse_events(client.post(f'/api/v1/papers/{pid}/qa/stream', json={'question': 'How many samples?'}).text)
    validation = [e['data'] for e in events if e['event'] == 'node_end' and e['data']['node'] == 'validate']
    assert len(validation) == 3 and validation[0]['validation'] is False
    assert validation[0]['validation_error'] == '模型摘录与候选原文字面不一致。'
    assert [e['data']['attempt'] for e in events if e['event'] == 'node_start' and e['data']['node'] == 'plan'] == [1,2,3]
    record = next(e['data'] for e in events if e['event'] == 'final')
    assert record['refused'] is (invalid == 99) and '9999' not in record['answer']


def test_invalid_input_and_missing_paper_use_normal_http_errors(tmp_path):
    client, _, pid = api(tmp_path)
    missing = client.post('/api/v1/papers/missing/qa/stream', json={'question': 'samples'})
    assert missing.status_code == 404 and missing.json()['error_code'] == 'PAPER_NOT_FOUND'
    assert client.post(f'/api/v1/papers/{pid}/qa/stream', json={'question': ''}).status_code == 422


def test_closing_generator_prevents_worker_from_starting(tmp_path, monkeypatch):
    _, app, pid = api(tmp_path)
    started = []
    monkeypatch.setattr('scholar_graph.qa_sse.EvidenceAgent.run', lambda *a, **kw: started.append(True))
    async def scenario():
        response = answer_stream(app.state.repository, pid, 'samples')
        iterator = response.body_iterator
        assert 'event: mode' in await anext(iterator)
        await iterator.aclose()
    asyncio.run(scenario())
    assert started == []


def test_provider_chunks_are_forwarded_before_next_chunk_and_response_closes():
    seen, closed = [], []
    def packet(delta, reason=None, usage=None):
        return ('data: ' + json.dumps({'choices': [{'delta': {'content': delta}, 'finish_reason': reason}],
                                     'usage': usage}) + '\n\n').encode()
    class Wire(httpx.SyncByteStream):
        def __iter__(self):
            yield packet('{"ok":')
            assert seen == ['{"ok":']  # Would fail if buffered until completion.
            yield packet('true}')
            yield packet('', 'stop', {'prompt_tokens': 2, 'completion_tokens': 3, 'total_tokens': 5})
            yield b'data: [DONE]\n\n'
        def close(self):
            closed.append(True)
    gateway = DeepSeekClient(key='unit-private', model='deepseek-mock', transport=httpx.MockTransport(
        lambda request: httpx.Response(200, stream=Wire(), headers={'Content-Type': 'text/event-stream'})))
    message = gateway.stream_complete([], phase='qa', on_delta=seen.append)
    assert json.loads(message['content']) == {'ok': True} and closed
    assert gateway.calls[-1]['total_tokens'] == 5


def test_cancel_during_delta_closes_upstream_without_reading_more():
    closed, consumed = [], []
    class Wire(httpx.SyncByteStream):
        def __iter__(self):
            yield b'data: {"choices":[{"delta":{"content":"first"},"finish_reason":null}]}\n\n'
            consumed.append(True)
            yield b'data: [DONE]\n\n'
        def close(self):
            closed.append(True)
    gateway = DeepSeekClient(key='unit-private', model='deepseek-mock', transport=httpx.MockTransport(
        lambda request: httpx.Response(200, stream=Wire(), headers={'Content-Type': 'text/event-stream'})))
    def cancel(text):
        raise StreamCancelled
    with pytest.raises(StreamCancelled):
        gateway.stream_complete([], phase='qa', on_delta=cancel)
    assert closed and not consumed and gateway.calls[-1]['status'] == 'cancelled'


@pytest.mark.real_model
def test_real_deepseek_sse_endpoint_when_credentials_available(tmp_path, monkeypatch, request):
    monkeypatch.setenv('SCHOLAR_GRAPH_QA_MODE', 'deepseek')
    client, _, pid = api(tmp_path)
    response = client.post(f'/api/v1/papers/{pid}/qa/stream', json={'question': 'How many samples?'})
    events = parse_events(response.text)
    assert response.status_code == 200
    assert any(e['event'] == 'token' for e in events)
    assert not any(e['event'] == 'error' for e in events)
    record = next(e['data'] for e in events if e['event'] == 'final')
    ContractGate().record('QAAnswer', record)
    assert not record['refused'] and record['anchors']
    request.node.user_properties.append(('live_sse', 'real DeepSeek stream; no bodies retained in JUnit'))
