"""One bounded, credential-free resident CPU reranker per local model/runtime."""
import atexit
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time


class WorkerUnavailable(Exception):
    pass


def local_environment():
    env = {k: v for k, v in os.environ.items()
           if not any(s in k.upper() for s in ('API_KEY', 'TOKEN', 'SECRET', 'PASSWORD'))}
    env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
               TOKENIZERS_PARALLELISM='false')
    return env


class ResidentReranker:
    def __init__(self, python, model_path):
        self.started = time.perf_counter()
        self.process = subprocess.Popen([str(python), str(Path(__file__).with_name('vector_worker.py')),
            '--reranker-server', str(model_path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding='utf-8', env=local_environment(),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.ready, self.lock, self.results = threading.Event(), threading.Lock(), queue.Queue(maxsize=1)
        self.startup = None
        threading.Thread(target=self._read, name='local-reranker-reader', daemon=True).start()

    def _read(self):
        try:
            first = json.loads(self.process.stdout.readline())
            if first.get('ready') is not True:
                raise ValueError('invalid worker readiness')
            self.startup = first
            self.ready.set()
            for line in self.process.stdout:
                self.results.put(json.loads(line))
        except (OSError, ValueError):
            pass
        finally:
            self.ready.set()

    def prepare(self, timeout=90):
        if not self.ready.wait(timeout) or not self.startup or self.process.poll() is not None:
            raise WorkerUnavailable('LOCAL_RERANKER_STARTUP_FAILED')
        return dict(self.startup)

    def score(self, payload, budget):
        started = time.perf_counter()
        cold = not self.ready.is_set()
        # Lock contention and cold loading count toward the same per-request budget.
        if not self.lock.acquire(timeout=max(0, budget)):
            raise WorkerUnavailable('LOCAL_RERANKER_BUSY')
        try:
            remaining = lambda: max(0, budget - (time.perf_counter() - started))
            if not self.ready.wait(remaining()):
                # The worker may finish warming in the background; no query was submitted.
                raise WorkerUnavailable('LOCAL_RERANKER_COLD_START_BUDGET_EXCEEDED')
            if not self.startup or self.process.poll() is not None:
                raise WorkerUnavailable('LOCAL_RERANKER_STARTUP_FAILED')
            self.process.stdin.write(json.dumps(payload, ensure_ascii=True, allow_nan=False) + '\n')
            self.process.stdin.flush()
            try:
                output = self.results.get(timeout=remaining())
            except queue.Empty:
                # Kill an overdue inference so its stale reply cannot serve the next request.
                self.close()
                raise WorkerUnavailable('MEASURED_CPU_BUDGET_EXCEEDED') from None
            return output, {'cold_start': cold, 'startup': dict(self.startup)}
        finally:
            self.lock.release()

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        for pipe in (self.process.stdin, self.process.stdout):
            if pipe:
                pipe.close()


_workers, _lock = {}, threading.Lock()


def resident_worker(python, model_path):
    key = (str(Path(python).absolute()), str(Path(model_path).resolve()))
    with _lock:
        worker = _workers.get(key)
        if worker is None or worker.process.poll() is not None:
            if worker is not None:
                worker.close()
            worker = _workers[key] = ResidentReranker(python, model_path)
        return worker


@atexit.register
def close_workers():
    with _lock:
        for worker in _workers.values():
            worker.close()
        _workers.clear()
