"""Item-four live acceptance helpers; isolated data and immutable run outputs."""
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from contextlib import contextmanager

import httpx

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'data/item04-20261028'
API = 'http://127.0.0.1:8100'
WEB = 'http://127.0.0.1:3400'


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


@contextmanager
def client():
    c = httpx.Client(base_url=API, timeout=120, trust_env=False)
    ready = False
    for _ in range(60):
        try:
            if c.get('/api/v2/system',timeout=3).status_code == 200:
                ready = True
                break
        except httpx.HTTPError:
            pass
        time.sleep(1)
    if not ready:
        c.close()
        raise TimeoutError('Isolated backend not ready; no mutation request sent')
    try:
        yield c
    finally:
        c.close()


def wait_task(c, identity, output, timeout=2400):
    started = time.monotonic()
    history = []
    while time.monotonic() - started < timeout:
        response = c.get('/api/v2/tasks/' + identity)
        response.raise_for_status()
        task = response.json()
        state = (task['status'], task['progress']['completed_units'], task['progress']['label'])
        if not history or history[-1]['state'] != list(state):
            history.append({'elapsed_seconds': round(time.monotonic()-started, 3), 'state': list(state)})
            write(output.with_suffix('.progress.json'), history)
            print(json.dumps({'task_id': identity, **history[-1]}, ensure_ascii=False), flush=True)
        write(output, task)
        if task['status'] not in {'queued', 'running', 'cancelling'}:
            return task
        time.sleep(1)
    raise TimeoutError(f'Task {identity} still active; evidence retained at {output}')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def snapshot():
    BASE.mkdir(parents=True, exist_ok=True)
    output = BASE/'workspace-before.json'
    if output.exists():
        raise FileExistsError(output)
    raw = subprocess.check_output(['git','ls-files','-m','-o','--exclude-standard','-z'],cwd=ROOT)
    paths = [p for p in raw.decode('utf-8').split('\0') if p and (ROOT/p).is_file() and not p.startswith('tests/item04/')]
    write(output, {'head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
                   'files': {p: digest(ROOT/p) for p in paths},
                   'official_pdfs': {p.name:digest(p) for p in (ROOT/'pdf').glob('*.pdf')}})
    print(json.dumps({'snapshotted_dirty_files':len(paths), 'official_pdfs':len(list((ROOT/'pdf').glob('*.pdf')))}))


if __name__ == '__main__':
    snapshot()
