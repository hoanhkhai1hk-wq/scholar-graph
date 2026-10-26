"""Single-leader interval scheduling, started/stopped by the API lifespan."""
from dataclasses import dataclass
import json
import logging
import os
import threading
import time
from uuid import uuid4

from .atomic_io import windows_retry
from .errors import PipelineError
from .storage import write_json
from .tracking_state import operation_lock, utc_now

LOGGER = logging.getLogger('scholar_graph.tracking_scheduler')


@dataclass(frozen=True)
class ScheduleConfig:
    enabled: bool = False
    interval_seconds: int = 86400
    initial_delay_seconds: int = 15
    max_candidates: int = 3
    max_imports: int = 1
    paper_ids: tuple = ()

    @classmethod
    def environment(cls):
        try:
            flag = os.environ.get('SCHOLAR_GRAPH_TRACKING_ENABLED', 'false').casefold()
            if flag not in {'true', 'false', '1', '0'}:
                raise ValueError
            result = cls(enabled=flag in {'true', '1'}, **{key: int(os.environ.get(
                'SCHOLAR_GRAPH_TRACKING_' + key.upper(), getattr(cls(), key))) for key in
                ('interval_seconds', 'initial_delay_seconds', 'max_candidates', 'max_imports')},
                paper_ids=tuple(filter(None, os.environ.get('SCHOLAR_GRAPH_TRACKING_PAPER_IDS', '').split(','))))
            if not (60 <= result.interval_seconds <= 2592000 and 0 <= result.initial_delay_seconds <= 86400
                    and 1 <= result.max_candidates <= 20 and 0 <= result.max_imports <= 5
                    and len(result.paper_ids) <= 5):
                raise ValueError
            return result
        except (ValueError, TypeError):
            raise PipelineError('VALIDATION_ERROR', '自动追踪配置不合法：间隔须为60秒至30天。') from None


class TrackingScheduler:
    def __init__(self, service, config):
        self.service, self.config = service, config
        self.root = service.repository.root / 'tracking'
        self.stop_event, self.thread = threading.Event(), None
        self.state = {'enabled': config.enabled, 'mechanism': 'backend_interval', 'active': False,
            'interval_seconds': config.interval_seconds, 'initial_delay_seconds': config.initial_delay_seconds,
            'max_imports': config.max_imports, 'run_count': 0, 'pid': os.getpid(), 'last_event': None}

    def event(self, kind, **fields):
        event = {'event': kind, 'timestamp': utc_now(), 'pid': os.getpid(), **fields}
        self.state['last_event'] = event
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / 'scheduler-events.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + '\n')
        temporary = self.root / ('scheduler-' + uuid4().hex + '.tmp')
        try:
            write_json(temporary, self.state)
            windows_retry(lambda: os.replace(temporary, self.root / 'scheduler-status.json'))
        finally:
            temporary.unlink(missing_ok=True)
        LOGGER.info(json.dumps(event, ensure_ascii=False))

    def snapshot(self):
        return dict(self.state)

    def tick(self):
        available = [p['id'] for p in self.service.repository.papers()]
        ids = [pid for pid in self.config.paper_ids if pid in available] if self.config.paper_ids else available[:1]
        if not ids:
            self.event('waiting_for_papers')
            return
        scheduled_id = uuid4().hex
        started = time.monotonic()
        self.event('run_started', scheduled_id=scheduled_id, paper_ids=ids)
        result = self.service.run(paper_ids=ids, force=False, interval_seconds=self.config.interval_seconds,
            max_candidates=self.config.max_candidates, max_imports=self.config.max_imports)
        self.state['run_count'] += 1
        self.event('run_finished', scheduled_id=scheduled_id, run_id=result.get('run_id'),
            status=result.get('status', 'skipped'), reason=result.get('reason'),
            elapsed_seconds=round(time.monotonic() - started, 6), candidate_count=result.get('candidate_count', 0),
            imported_count=result.get('imported_count', 0), errors=result.get('errors', []))

    def loop(self):
        try:
            with operation_lock(self.service.repository.root, 'scheduler-leader'):
                self.state['active'] = True
                self.event('scheduler_started', interval_seconds=self.config.interval_seconds)
                try:
                    if self.stop_event.wait(self.config.initial_delay_seconds):
                        return
                    while not self.stop_event.is_set():
                        try:
                            self.tick()
                        except PipelineError as error:
                            self.event('run_error', error=error.envelope())
                        except Exception:
                            self.event('run_error', error={'error_code': 'INTERNAL_ERROR',
                                'message': '自动追踪未完成，未伪造结果。', 'details': None})
                        # Fixed delay after completion; no overlapping catch-up jobs.
                        if self.stop_event.wait(self.config.interval_seconds):
                            break
                finally:
                    self.state['active'] = False
                    self.event('scheduler_stopped')
        except PipelineError:
            # Another process owns the directory lease. Do not overwrite its
            # journal or publish a false active-leader status.
            self.state['last_event'] = {'event': 'leader_already_active', 'timestamp': utc_now()}

    def start(self):
        if self.config.enabled and self.thread is None:
            self.thread = threading.Thread(target=self.loop, name='arxiv-tracking-scheduler', daemon=True)
            self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
            # A bounded upstream request may still be returning; do not claim
            # the thread stopped before it actually did.
            if self.thread.is_alive():
                self.state['stopping'] = True
