"""Local engines run in child processes; third-party logs never reach result/error logs."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

from .errors import PipelineError


class LocalEngines:
    def __init__(self, *, timeout: float = 300, language: str = "en", cache_dir: Path):
        self.timeout, self.language, self.cache_dir = timeout, language, cache_dir
        self._session_enabled = False
        self._process = None
        self._responses = None
        self.session_metrics = {'requests': 0, 'worker_launches': 0}

    @contextmanager
    def session(self):
        self._session_enabled = True
        self.session_metrics = {'requests': 0, 'worker_launches': 0}
        try:
            yield self
        finally:
            self._session_enabled = False
            self._close_session()

    def _close_session(self):
        process, self._process = self._process, None
        if process is None:
            return
        try:
            process.stdin.close()
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
            process.wait(timeout=5)
        finally:
            process.stdout.close()

    def _environment(self):
        env = dict(os.environ)
        for key in list(env):
            if any(part in key.upper() for part in ("API_KEY", "TOKEN", "SECRET", "PASSWORD")):
                env.pop(key)
        cache = self.cache_dir.resolve()
        env.update({"PYTHONIOENCODING": "utf-8", "HF_HOME": str(cache / "huggingface"),
                    "MODELSCOPE_CACHE": str(cache / "modelscope"),
                    "PADDLE_PDX_CACHE_HOME": str(Path(os.environ.get("SCHOLAR_GRAPH_OCR_CACHE_DIR", cache / "paddlex")).resolve()),
                    "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "True"})
        return env

    def _start_session(self, pdf):
        if self._process is not None:
            return
        process = subprocess.Popen([sys.executable, str(Path(__file__).with_name('_engine_session_worker.py'))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=self._environment(), cwd=pdf.parent)
        responses = queue.Queue(maxsize=1)
        self._process, self._responses = process, responses
        self.session_metrics['worker_launches'] += 1
        def read():
            try:
                while True:
                    # Bound a batch response rather than retaining arbitrary dependency output.
                    line = process.stdout.readline(16 * 1024 * 1024 + 1)
                    if not line or len(line) > 16 * 1024 * 1024:
                        responses.put(None)
                        return
                    responses.put(line)
            except (OSError, ValueError):
                pass
        threading.Thread(target=read, name='local-engine-response', daemon=True).start()

    def _run_session(self, pdf, mode, pages, timeout):
        code = 'OCR_FAILED' if mode == 'ocr' else 'PARSE_FAILED'
        try:
            self._start_session(pdf)
            self.session_metrics['requests'] += 1
            identity = self.session_metrics['requests']
            request = {'id': identity, 'path': str(pdf.resolve()), 'mode': mode, 'language': self.language, 'pages': pages or []}
            self._process.stdin.write((json.dumps(request) + '\n').encode('utf-8'))
            self._process.stdin.flush()
            raw = self._responses.get(timeout=min(self.timeout, timeout) if timeout is not None else self.timeout)
            reply = json.loads(raw) if raw else None
            value = reply.get('result') if isinstance(reply, dict) and reply.get('id') == identity else None
            if not isinstance(value, dict) or not isinstance(value.get('pages'), list):
                raise ValueError('Invalid local engine response')
            return value
        except queue.Empty:
            self._close_session()
            raise PipelineError(code, '本地页面批次超过运行时限。') from None
        except (OSError, ValueError):
            self._close_session()
            raise PipelineError(code, '本地解析会话未完成，已保留页面检查点，可重试。') from None

    def _run(self, pdf: Path, mode: str, pages: list[int] | None = None, *, timeout=None) -> dict:
        if self._session_enabled:
            return self._run_session(pdf, mode, pages, timeout)
        env = self._environment()
        command = [sys.executable, str(Path(__file__).with_name("_engine_worker.py")),
                   str(pdf), mode, self.language, json.dumps(pages or [])]
        code = "OCR_FAILED" if mode == "ocr" else "PARSE_FAILED"
        try:
            result = subprocess.run(command, capture_output=True, timeout=min(self.timeout, timeout) if timeout is not None else self.timeout, env=env,
                                    cwd=pdf.parent, check=False)
            if result.returncode:
                raise ValueError("worker failed")
            value = json.loads(result.stdout.decode("utf-8"))
            if not isinstance(value, dict) or not isinstance(value.get("pages"), list):
                raise ValueError("invalid worker response")
            return value
        except subprocess.TimeoutExpired:
            raise PipelineError(code, '本地页面批次超过运行时限。') from None
        except (OSError, ValueError):
            raise PipelineError(code, "本地 OCR 未完成，请检查依赖、模型与运行时限。" if mode == "ocr"
                                else "MinerU 本地解析未完成，请检查依赖与运行时限。") from None

    def text(self, pdf: Path, *, timeout=None) -> dict:
        return self._run(pdf, "mineru", timeout=timeout)

    def ocr(self, pdf: Path, pages: list[int], *, timeout=None) -> dict:
        return self._run(pdf, "ocr", pages, timeout=timeout)
