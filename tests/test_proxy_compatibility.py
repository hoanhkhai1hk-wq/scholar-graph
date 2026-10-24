import json
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from scholar_graph.api import create_app
from test_validation_status import example_bundle

ROOT = Path(__file__).resolve().parents[1]


def verify_proxy(root):
    app = create_app(data_dir=root)
    app.state.repository.store.paper(example_bundle())
    connection = socket.socket()
    connection.bind(("127.0.0.1", 0))
    port = connection.getsockname()[1]
    config = uvicorn.Config(app, log_level="critical", access_log=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={"sockets": [connection]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Backend test server did not start")
            time.sleep(0.05)
        result = subprocess.run([shutil.which("node"), str(ROOT / "tests/verify_proxy_compatibility.cjs"),
                                 f"http://127.0.0.1:{port}"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert result.returncode == 0, "Actual proxy route verification failed"
        return json.loads(result.stdout)
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        connection.close()


@pytest.mark.skipif(not shutil.which("node") or not (ROOT / "frontend/node_modules/typescript").exists(),
                    reason="Actual proxy route test requires existing Node/TypeScript; no frontend installation is performed")
def test_actual_unchanged_proxy_get_json_post_and_multipart(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHOLAR_GRAPH_QA_MODE", "extractive")
    result = verify_proxy(tmp_path)
    assert (result["proxy_get_status"], result["proxy_qa_post_status"], result["proxy_multipart_status"]) == (200, 200, 415)
