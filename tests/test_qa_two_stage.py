"""Deterministic top-ten budget/IPC tests, with no model downloads or inference."""
import copy
import io
import json
import queue
import threading
from types import SimpleNamespace

import pytest

from scholar_graph.qa_retrieval import LocalReranker, QAHybridRetriever
from scholar_graph.rerank_worker import ResidentReranker, WorkerUnavailable, local_environment
from test_qa_hybrid_retrieval import make, Vector


@pytest.mark.parametrize('accepted', [True, False])
def test_rrf_only_sends_top_ten_to_reranker_and_retains_recall_tail(tmp_path, accepted):
    repo, bundle, _ = make(tmp_path)
    bundle = copy.deepcopy(bundle)
    bundle['chunks'] = [dict(bundle['chunks'][0], chunk_id=f'chunk-{i:03d}') for i in range(30)]
    bundle['reference_entries'], bundle['citation_links'] = [], []
    captured = []
    class Reranker:
        def order(self, question, chunks):
            captured.extend(c['chunk_id'] for c in chunks)
            return (list(reversed(captured)) if accepted else None,
                    {'method': 'bge-reranker-large' if accepted else 'rrf',
                     'reason': 'OK' if accepted else 'MEASURED_CPU_BUDGET_EXCEEDED'})
    evidence, info = QAHybridRetriever(repo, Vector(), Reranker()).retrieve(bundle, 'samples', limit=48)
    assert len(captured) == 10
    unique = list(dict.fromkeys(e['anchor']['chunk_id'] for e in evidence))
    assert unique[:10] == (list(reversed(captured)) if accepted else captured)
    assert len(unique) > 10 and info['union_recalled'] > 10
    assert info['ranking_method'] == ('reranked' if accepted else 'rrf')
    assert info['fallback_reason'] == (None if accepted else 'MEASURED_CPU_BUDGET_EXCEEDED')


def test_invalid_reranker_cannot_inject_other_chunks(tmp_path):
    repo, bundle, _ = make(tmp_path)
    class Invalid:
        def order(self, *args):
            return ['foreign-chunk'], {'method': 'bge-reranker-large'}
    evidence, info = QAHybridRetriever(repo, Vector(), Invalid()).retrieve(bundle, 'samples')
    assert info['method'] == 'lexical-fallback' and info['ranking_method'] == 'lexical'
    assert all(e['anchor']['chunk_id'] != 'foreign-chunk' for e in evidence)


def configured(tmp_path):
    python, model = tmp_path/'python', tmp_path/'model'
    python.touch(); model.mkdir(); (model/'model.safetensors').touch()
    return LocalReranker(tmp_path, python, model, resident=True)


def test_top_ten_strategy_rechecks_instead_of_reusing_old_36_candidate_policy(tmp_path, monkeypatch):
    service = configured(tmp_path)
    policy = tmp_path/'qa-retrieval/reranker-policy.json'
    policy.parent.mkdir()
    policy.write_text(json.dumps({'reason': 'MEASURED_CPU_BUDGET_EXCEEDED', 'candidate_count': 36}))
    def score(payload, budget):
        return {'scores': {'c': .5}, 'timing': {'rerank_seconds': .01}, 'model': 'local', 'revision': 'test'}, {'cold_start': False}
    monkeypatch.setattr('scholar_graph.qa_retrieval.resident_worker', lambda *a: SimpleNamespace(score=score))
    order, info = service.order('samples', [{'chunk_id': 'c', 'text': '12 samples'}])
    assert order == ['c'] and info['method'] == 'bge-reranker-large' and not info['cold_start']


@pytest.mark.parametrize('reason', ['LOCAL_RERANKER_COLD_START_BUDGET_EXCEEDED', 'MEASURED_CPU_BUDGET_EXCEEDED', 'LOCAL_RERANKER_BUSY'])
def test_resident_failure_keeps_rrf_with_reason_and_bounded_candidate_count(tmp_path, monkeypatch, reason):
    service = configured(tmp_path)
    def score(*args):
        raise WorkerUnavailable(reason)
    monkeypatch.setattr('scholar_graph.qa_retrieval.resident_worker', lambda *a: SimpleNamespace(score=score))
    order, info = service.order('samples', [{'chunk_id': 'c', 'text': '12 samples'}])
    assert order is None and info['method'] == 'rrf' and info['reason'] == reason
    assert info['candidate_count'] == 1 and info['budget_seconds'] == 5


def worker_fixture():
    worker = ResidentReranker.__new__(ResidentReranker)
    worker.ready, worker.lock, worker.results = threading.Event(), threading.Lock(), queue.Queue()
    worker.startup = {'ready': True, 'startup_seconds': 12}
    worker.process = SimpleNamespace(stdin=io.StringIO(), poll=lambda: None)
    return worker


def test_cold_budget_expires_without_submitting_query_and_next_warm_call_works():
    worker = worker_fixture()
    with pytest.raises(WorkerUnavailable, match='COLD_START_BUDGET'):
        worker.score({'question': 'private source query'}, .001)
    assert worker.process.stdin.getvalue() == ''
    worker.ready.set(); worker.results.put({'scores': {'c': .7}})
    output, meta = worker.score({'question': 'private source query'}, 1)
    assert output['scores'] == {'c': .7} and not meta['cold_start']


def test_inference_timeout_terminates_worker_to_prevent_stale_reply():
    worker = worker_fixture(); worker.ready.set()
    closed = []
    worker.close = lambda: closed.append(True)
    with pytest.raises(WorkerUnavailable, match='MEASURED_CPU_BUDGET_EXCEEDED'):
        worker.score({}, .001)
    assert closed and not worker.lock.locked()


def test_local_worker_environment_excludes_all_credential_variables(monkeypatch):
    for name in ['DEEPSEEK_API_KEY', 'HF_TOKEN', 'PRIVATE_SECRET', 'DATABASE_PASSWORD']:
        monkeypatch.setenv(name, 'test-private-value')
    env = local_environment()
    assert not any('test-private-value' == v for v in env.values())
    assert env['HF_HUB_OFFLINE'] == env['TRANSFORMERS_OFFLINE'] == '1'
