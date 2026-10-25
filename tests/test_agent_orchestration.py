import json

import pytest
from langsmith.run_helpers import get_tracing_context

from scholar_graph.agent_tools import AgentTools, FUNCTIONS
from scholar_graph.api_repository import ApiRepository
from scholar_graph.errors import PipelineError
from scholar_graph.orchestration import EvidenceAgent
from scholar_graph.validation import ContractGate
from test_dedup import versions


class Model:
    """Explicit simulation of protocol messages; never counted as a real provider call."""
    def __init__(self, *, invalid=0, unavailable=None):
        self.calls, self.invalid, self.unavailable = [], invalid, unavailable
        self.qa_count = 0

    def complete(self, messages, *, phase, **kwargs):
        assert get_tracing_context()['enabled'] is False
        self.calls.append({'provider': 'mock', 'model': 'deepseek-mock', 'phase': phase,
                           'elapsed_seconds': 0.0, 'total_tokens': 0, 'status': 'succeeded'})
        if phase == self.unavailable:
            raise PipelineError('UPSTREAM_ERROR', '模拟上游不可用')
        payload = json.loads(messages[-1]['content'])
        ids = payload['paper_ids']
        if phase in ('plan', 'retrieve_retry'):
            return {'role': 'assistant', 'content': '', 'tool_calls': [
                {'id': 'call_' + str(n), 'type': 'function', 'function': {'name': 'search',
                 'arguments': json.dumps({'paper_ids': [pid], 'query': 'samples', 'limit': 4})}} for n, pid in enumerate(ids)]}
        assert any(m['role'] == 'tool' and m.get('tool_call_id') for m in messages)
        self.qa_count += 1
        answers = []
        for pid in ids:
            item = next(e for e in payload['evidence'] if e['paper_id'] == pid)
            answers.append({'paper_id': pid, 'refused': False, 'claims': [
                {'evidence_id': item['evidence_id'], 'quote': 'Invented 9999 samples.' if self.qa_count <= self.invalid else item['quote']}]})
        return {'role': 'assistant', 'content': json.dumps({'answers': answers})}


def repository(tmp_path):
    repo = ApiRepository(tmp_path, ContractGate())
    for bundle in versions():
        repo.store.paper(bundle)
    return repo, [b['paper_meta']['id'] for b in versions()]


def test_real_langgraph_executes_model_tool_protocol_before_answer(tmp_path, monkeypatch):
    monkeypatch.setenv('LANGSMITH_TRACING', 'true')
    repo, ids = repository(tmp_path)
    result, meta = EvidenceAgent(repo, client=Model()).run(ids, 'How many samples?')
    assert [t['node'] for t in meta['trace']] == ['plan', 'retrieve', 'qa', 'validate']
    assert meta['validated'] and meta['fallback_reason'] is None
    assert len(meta['tool_calls']) == 2
    assert all(t['origin'] == 'model_function_call' and t['return_summary']['evidence_count'] > 0 for t in meta['tool_calls'])
    assert all(not r['refused'] for r in result['per_paper'])
    assert not meta['checkpointing'] and not meta['external_tracing']


def test_validation_retries_retrieval_and_succeeds_third_time(tmp_path):
    repo, ids = repository(tmp_path)
    result, meta = EvidenceAgent(repo, client=Model(invalid=2)).run(ids, 'How many samples?')
    assert meta['attempts'] == 3
    assert [t['validation'] for t in meta['trace'] if t['node'] == 'validate'] == [False, False, True]
    assert len(meta['tool_calls']) == 6
    assert not any(r['refused'] for r in result['per_paper'])


def test_third_invalid_attempt_refuses_without_unverified_facts(tmp_path):
    repo, ids = repository(tmp_path)
    result, meta = EvidenceAgent(repo, client=Model(invalid=99)).run(ids, 'How many samples?')
    assert meta['attempts'] == 3 and meta['trace'][-1]['node'] == 'refuse'
    assert all(r['refused'] and not r['anchors'] and '9999' not in r['answer'] for r in result['per_paper'])


@pytest.mark.parametrize('phase', ['plan', 'qa'])
def test_unavailable_model_uses_existing_extractive_and_explains_why(tmp_path, phase):
    repo, ids = repository(tmp_path)
    result, meta = EvidenceAgent(repo, client=Model(unavailable=phase)).run(ids, 'How many samples?')
    assert meta['fallback_reason'] == 'UPSTREAM_ERROR' and meta['validated']
    assert '12 samples' in result['per_paper'][0]['answer']
    assert len(meta['tool_calls']) == (0 if phase == 'plan' else 2)


def test_missing_configuration_is_explicit_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.delenv('DEEPSEEK_MODEL', raising=False)
    repo, ids = repository(tmp_path)
    _, meta = EvidenceAgent(repo).run(ids, 'How many samples?')
    assert meta['fallback_reason'] == 'MODEL_CONFIGURATION_UNAVAILABLE'
    assert meta['model_calls'] == meta['tool_calls'] == []


def call(name, args):
    return {'id': 'unit_call', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}


def test_tools_reject_extra_args_unknown_tools_and_outside_collection(tmp_path):
    repo, ids = repository(tmp_path)
    tools = AgentTools(repo, ids)
    for candidate in [call('execute_shell', {}), call('search', {'paper_ids': ids, 'query': 'samples', 'limit': 4, 'extra': True}),
                      call('search', {'paper_ids': ['outside'], 'query': 'samples', 'limit': 4})]:
        assert tools.execute(candidate, attempt=1)['error']['error_code'] == 'VALIDATION_ERROR'


def test_graph_and_authorized_arxiv_dispatch_reuse_existing_services(tmp_path):
    repo, ids = repository(tmp_path)
    tools = AgentTools(repo, ids)
    value = tools.execute(call('graph_query', {'paper_ids': ids}), attempt=1)
    assert len(value['nodes']) == 2
    assert tools.execute(call('arxiv_fetch', {'title': 'Exact paper title'}), attempt=1)['error']['error_code'] == 'VALIDATION_ERROR'
    seen = []
    class Fetcher:
        def fetch(self, **kwargs):
            seen.append(kwargs)
            return {'succeeded': False, 'paper': None, 'parse_status': None,
                    'error': {'error_code': 'PAPER_NOT_FOUND', 'message': '模拟未找到', 'details': None}}
    tools = AgentTools(repo, ids, fetcher=Fetcher(), allow_fetch=True)
    value = tools.execute(call('arxiv_fetch', {'title': 'Exact paper title'}), attempt=1)
    assert seen == [{'title': 'Exact paper title'}] and not value['succeeded']
    assert len(FUNCTIONS) == 3
