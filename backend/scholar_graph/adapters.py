"""Local engines run in child processes; third-party logs never reach result/error logs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from .errors import PipelineError


class LocalEngines:
    def __init__(self, *, timeout: float = 300, language: str = "en", cache_dir: Path):
        self.timeout, self.language, self.cache_dir = timeout, language, cache_dir

    def _run(self, pdf: Path, mode: str, pages: list[int] | None = None) -> dict:
        env = dict(os.environ)
        # These modes perform local inference only and do not need any provider credentials.
        for key in list(env):
            if any(part in key.upper() for part in ("API_KEY", "TOKEN", "SECRET", "PASSWORD")):
                env.pop(key)
        cache = self.cache_dir.resolve()
        env.update({"PYTHONIOENCODING": "utf-8", "HF_HOME": str(cache / "huggingface"),
                    "MODELSCOPE_CACHE": str(cache / "modelscope"),
                    "PADDLE_PDX_CACHE_HOME": str(cache / "paddlex"),
                    "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "True"})
        command = [sys.executable, str(Path(__file__).with_name("_engine_worker.py")),
                   str(pdf), mode, self.language, json.dumps(pages or [])]
        code = "OCR_FAILED" if mode == "ocr" else "PARSE_FAILED"
        try:
            result = subprocess.run(command, capture_output=True, timeout=self.timeout, env=env,
                                    cwd=pdf.parent, check=False)
            if result.returncode:
                raise ValueError("worker failed")
            value = json.loads(result.stdout.decode("utf-8"))
            if not isinstance(value, dict) or not isinstance(value.get("pages"), list):
                raise ValueError("invalid worker response")
            return value
        except (OSError, ValueError, subprocess.TimeoutExpired):
            raise PipelineError(code, "本地 OCR 未完成，请检查依赖、模型与运行时限。" if mode == "ocr"
                                else "MinerU 本地解析未完成，请检查依赖与运行时限。") from None

    def text(self, pdf: Path) -> dict:
        return self._run(pdf, "mineru")

    def ocr(self, pdf: Path, pages: list[int]) -> dict:
        return self._run(pdf, "ocr", pages)
