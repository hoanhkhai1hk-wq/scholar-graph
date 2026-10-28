"""Actual subprocess protocol/lifetime tests; not OCR or paper-quality evidence."""
import textwrap
import subprocess
import sys
from pathlib import Path

import pytest

from scholar_graph import adapters
from scholar_graph.adapters import LocalEngines
from scholar_graph.errors import PipelineError


def test_spawn_import_does_not_consume_the_parent_request_stream():
    path = Path(adapters.__file__).with_name('_engine_session_worker.py')
    command = [sys.executable, '-c',
        "import runpy,sys; sys.path.insert(0,sys.argv[1]); "
        "runpy.run_path(sys.argv[2],run_name='__mp_main__'); print('spawn-import-ok',flush=True)",
        str(path.parent), str(path)]
    process = subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        process.wait(timeout=5)  # stdin deliberately stays open, as in a persistent session.
        assert process.returncode == 0
        assert process.stdout.read().strip() == b'spawn-import-ok'
    finally:
        if process.poll() is None: process.kill(); process.wait(timeout=5)
        process.stdin.close(); process.stdout.close(); process.stderr.close()


@pytest.fixture
def engines(tmp_path, monkeypatch):
    worker = tmp_path / '_engine_session_worker.py'
    worker.write_text(textwrap.dedent('''
        import json, os, sys, time
        for line in sys.stdin:
            q = json.loads(line)
            name = os.path.basename(q['path'])
            if name == 'sleep.pdf': time.sleep(5)
            if name == 'exit.pdf': sys.exit(3)
            if name == 'malformed.pdf':
                print('not-json', flush=True)
                continue
            value = {'pages':[{'page_idx':0, 'worker_pid':os.getpid(),
                'secret_present':bool(os.getenv('DEEPSEEK_API_KEY')), 'mode':q['mode']}]}
            answer = {'id':q['id'] + (1 if name == 'wrong.pdf' else 0), 'result':value}
            if name == 'error.pdf': answer = {'id':q['id'], 'error':'failed'}
            print(json.dumps(answer), flush=True)
    '''), encoding='utf-8')
    monkeypatch.setattr(adapters, '__file__', str(tmp_path / 'adapters.py'))
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'unit-only-must-stay-in-parent')
    return LocalEngines(cache_dir=tmp_path / 'models', timeout=3), tmp_path


def test_two_requests_share_one_process_and_do_not_inherit_credentials(engines):
    engine, root = engines
    with engine.session():
        first = engine.text(root/'normal.pdf')['pages'][0]
        second = engine.ocr(root/'normal.pdf', [0])['pages'][0]
        assert first['worker_pid'] == second['worker_pid']
        assert not first['secret_present'] and not second['secret_present']
        assert first['mode'] == 'mineru' and second['mode'] == 'ocr'
        assert engine.session_metrics == {'requests': 2, 'worker_launches': 1}
        process = engine._process
    assert process.poll() is not None and engine._process is None


def test_timeout_kills_worker_and_next_request_recovers(engines):
    engine, root = engines
    with engine.session():
        engine._start_session(root/'sleep.pdf')
        process = engine._process
        with pytest.raises(PipelineError) as error:
            engine.text(root/'sleep.pdf', timeout=.15)
        assert error.value.code == 'PARSE_FAILED'
        assert process.poll() is not None
        assert engine.text(root/'normal.pdf')['pages']
        assert engine.session_metrics['worker_launches'] == 2


@pytest.mark.parametrize('name', ['wrong.pdf', 'malformed.pdf', 'exit.pdf', 'error.pdf'])
def test_invalid_response_cannot_be_published_and_worker_is_closed(engines, name):
    engine, root = engines
    with engine.session():
        with pytest.raises(PipelineError):
            engine.text(root/name)
        assert engine._process is None
        assert engine.text(root/'normal.pdf')['pages']


def test_caller_exception_also_releases_process(engines):
    engine, root = engines
    with pytest.raises(RuntimeError):
        with engine.session():
            engine.text(root/'normal.pdf')
            process = engine._process
            raise RuntimeError('test cancellation')
    assert process.poll() is not None and not engine._session_enabled
