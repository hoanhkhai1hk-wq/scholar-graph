"""Single-worker durable task queue. Cancellation never fabricates stopped work."""
from datetime import datetime, timezone
import queue
import threading
import uuid

from .errors import PipelineError
from .workspace import now


class TaskRunner:
    def __init__(self, workspace):
        self.workspace = workspace
        self.handlers = {}
        self.queue = queue.Queue()
        self.thread = None
        self.stop_event = threading.Event()
        self.lock = threading.RLock()

    def start(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                return
            self.stop_event.clear()
            for task in self.workspace.all('task'):
                if task['status'] in ('running', 'cancelling'):
                    task.update(status='interrupted', finished_at=now(), error={'error_code': 'INTERRUPTED', 'message': '服务重启中断了任务，输入已保留，可重试。', 'details': None})
                    self.workspace.put('task', task['id'], task)
                elif task['status'] == 'queued':
                    self.queue.put(task['id'])
            self.thread = threading.Thread(target=self._work, name='scholar-workspace-jobs', daemon=True)
            self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1)

    def get(self, identity):
        value = self.workspace.read('task', identity)
        if value is None:
            raise PipelineError('PAPER_NOT_FOUND', '任务不存在。')
        # Local input paths are operational state, never public task metadata.
        return {key: item for key, item in value.items() if key != 'parameters'}

    def submit(self, kind, parameters):
        if kind not in self.handlers:
            raise PipelineError('VALIDATION_ERROR', '该任务类型不可用。')
        self.start()
        with self.lock:
            active = [t for t in self.workspace.all('task') if t['status'] in ('queued', 'running', 'cancelling')]
            if len(active) >= 20:
                raise PipelineError('VALIDATION_ERROR', '待处理任务较多，请稍后重试。')
            identity = uuid.uuid4().hex
            value = {'id': identity, 'kind': kind, 'status': 'queued', 'created_at': now(), 'started_at': None,
                     'finished_at': None, 'cancel_requested': False, 'parameters': parameters,
                     'progress': {'completed_units': 0, 'total_units': None, 'label': '等待处理'}, 'result': None, 'error': None}
            self.workspace.put('task', identity, value, 'task_submitted')
            self.queue.put(identity)
            return self.get(identity)

    def update(self, identity, **changes):
        with self.lock:
            value = self.workspace.read('task', identity)
            value.update(changes)
            return self.workspace.put('task', identity, value)

    def progress(self, identity, completed, total, label):
        return self.update(identity, progress={'completed_units': completed, 'total_units': total, 'label': label})

    def cancelled(self, identity):
        return self.stop_event.is_set() or self.workspace.read('task', identity)['cancel_requested']

    def cancel(self, identity):
        with self.lock:
            value = self.workspace.read('task', identity)
            if value is None:
                raise PipelineError('PAPER_NOT_FOUND', '任务不存在。')
            if value['status'] == 'queued':
                self.update(identity, status='cancelled', cancel_requested=True, finished_at=now())
            elif value['status'] in ('running', 'cancelling'):
                self.update(identity, status='cancelling', cancel_requested=True)
            return self.get(identity)

    def retry(self, identity):
        value = self.workspace.read('task', identity)
        if not value or value['status'] not in ('failed', 'partial', 'interrupted', 'cancelled'):
            raise PipelineError('VALIDATION_ERROR', '该任务当前无需重试。')
        return self.submit(value['kind'], value['parameters'])

    def _work(self):
        while not self.stop_event.is_set():
            try:
                identity = self.queue.get(timeout=.2)
            except queue.Empty:
                continue
            try:
                task = self.workspace.read('task', identity)
                if task['status'] != 'queued':
                    continue
                self.update(identity, status='running', started_at=now())
                result = self.handlers[task['kind']](identity, task['parameters'], self)
                status = 'interrupted' if self.stop_event.is_set() else 'cancelled' if self.cancelled(identity) else (
                    'partial' if result.get('failed_count', 0) and result.get('succeeded_count', 0) else
                    'failed' if result.get('failed_count', 0) else 'completed')
                self.update(identity, status=status, result=result, finished_at=now())
            except Exception as error:
                envelope = error.envelope() if isinstance(error, PipelineError) else {
                    'error_code': 'INTERNAL_ERROR', 'message': '任务未完成，输入保留，可重试。', 'details': None}
                self.update(identity, status='interrupted' if self.stop_event.is_set() else 'cancelled' if self.cancelled(identity) else 'failed', error=envelope, finished_at=now())
            finally:
                self.queue.task_done()
