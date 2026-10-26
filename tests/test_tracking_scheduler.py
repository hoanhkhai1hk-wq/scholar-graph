import json
import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from scholar_graph.api import create_app
from scholar_graph.errors import PipelineError
from scholar_graph.tracking_scheduler import ScheduleConfig, TrackingScheduler


def service(root):
    return SimpleNamespace(repository=SimpleNamespace(root=root, papers=lambda: [{'id': 'seed'}]),
        run=lambda **kwargs: {'run_id': 'run', 'status': 'completed', 'candidate_count': 1})


@pytest.mark.parametrize('key,value', [('ENABLED', 'invalid'), ('INTERVAL_SECONDS', '0'),
    ('INTERVAL_SECONDS', '59'), ('MAX_IMPORTS', '6'), ('MAX_CANDIDATES', '0')])
def test_invalid_schedule_configuration_fails_explicitly(monkeypatch, key, value):
    monkeypatch.setenv('SCHOLAR_GRAPH_TRACKING_' + key, value)
    with pytest.raises(PipelineError):
        ScheduleConfig.environment()


def test_lifespan_automatically_runs_and_persists_without_trigger_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv('SCHOLAR_GRAPH_TRACKING_ENABLED', 'true')
    monkeypatch.setenv('SCHOLAR_GRAPH_TRACKING_INITIAL_DELAY_SECONDS', '0')
    app = create_app(data_dir=tmp_path)
    app.state.repository.papers = lambda: [{'id': 'seed'}]
    called = threading.Event()
    def run(**kwargs):
        assert kwargs['force'] is False and kwargs['paper_ids'] == ['seed']
        called.set()
        return {'run_id': 'synthetic', 'status': 'failed', 'candidate_count': 0,
                'errors': [{'error_code': 'UPSTREAM_ERROR', 'message': 'self-made upstream failure', 'details': None}]}
    app.state.tracking.run = run
    with TestClient(app) as client:
        assert called.wait(2)
        value = client.get('/api/v1/retrieval/tracking/status').json()
        assert value['scheduler'] == 'backend_interval' and value['scheduler_details']['enabled']
    events = [json.loads(line) for line in (tmp_path/'tracking/scheduler-events.jsonl').read_text().splitlines()]
    assert [e['event'] for e in events] == ['scheduler_started', 'run_started', 'run_finished', 'scheduler_stopped']
    assert events[2]['status'] == 'failed' and events[2]['errors'][0]['error_code'] == 'UPSTREAM_ERROR'
    assert not json.loads((tmp_path/'tracking/scheduler-status.json').read_text())['active']


def test_single_leader_and_interruptible_wait(tmp_path):
    first = TrackingScheduler(service(tmp_path), ScheduleConfig(enabled=True, initial_delay_seconds=100))
    first.start()
    # Poll a synchronization event rather than relying on a fixed sleep.
    for _ in range(100):
        if first.state['active']:
            break
        threading.Event().wait(.01)
    assert first.state['active']
    second = TrackingScheduler(service(tmp_path), ScheduleConfig(enabled=True))
    second.start()
    second.thread.join(1)
    assert second.state['last_event']['event'] == 'leader_already_active'
    assert not second.state['active']
    first.stop()
    assert not first.thread.is_alive()


def test_disabled_does_not_create_thread_and_empty_library_waits(tmp_path):
    scheduler = TrackingScheduler(service(tmp_path), ScheduleConfig())
    scheduler.start()
    assert scheduler.thread is None
    scheduler.service.repository.papers = lambda: []
    scheduler.tick()
    assert scheduler.state['last_event']['event'] == 'waiting_for_papers'
    assert scheduler.state['run_count'] == 0


def test_configured_seed_not_yet_uploaded_waits_without_fake_poll(tmp_path):
    scheduler = TrackingScheduler(service(tmp_path), ScheduleConfig(paper_ids=('not-uploaded',)))
    scheduler.tick()
    assert scheduler.state['last_event']['event'] == 'waiting_for_papers'
    assert scheduler.state['run_count'] == 0
