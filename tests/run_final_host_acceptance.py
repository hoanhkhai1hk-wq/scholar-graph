"""No-key host full layer and official three cases, preserving previous reports."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from official_pdf_support import Measure
from deployment_checks import official_cases, save


def main():
    for key in list(os.environ):
        if any(part in key.upper() for part in ('API_KEY', 'TOKEN', 'SECRET', 'PASSWORD')):
            del os.environ[key]
    os.environ.pop('DEEPSEEK_MODEL', None)
    os.environ.update(SCHOLAR_GRAPH_QA_MODE='extractive', SCHOLAR_GRAPH_TRACKING_ENABLED='false',
        SCHOLAR_GRAPH_VECTOR_PYTHON=str(ROOT/'data/module-four-runtime/.venv/Scripts/python.exe'),
        SCHOLAR_GRAPH_BGE_M3_PATH=str(ROOT/'data/module-four-models/bge-m3'))
    root = ROOT/'data/final-deployment-host'/uuid4().hex
    root.mkdir(parents=True)
    junit = ROOT/'tests/reports/final-deployment-host-pytest.xml'
    started = time.perf_counter()
    with (root/'pytest-console.txt').open('wb') as handle:
        test = subprocess.run([sys.executable, 'tests/run_regression.py', 'full', '--no-key', '--corpus-dir',
            str(ROOT/'pdf'), '--junit', str(junit)], cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT)
    suites = ET.parse(junit).getroot().findall('testsuite')
    stats = {k: sum(int(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
    stats.update(exit_code=test.returncode, elapsed_seconds=round(time.perf_counter()-started,6))
    print(json.dumps({'stage':'host_full', **stats}), flush=True)
    result = {'scope':'宿主机官方 pdf/ 真文件与全量层', 'local_artifacts':str(root.relative_to(ROOT)), 'regression':stats}
    save(ROOT/'tests/reports/final-deployment-host.json', result)
    with TestClient(create_app(data_dir=root/'records')) as client:
        result['cases'] = official_cases(client, ROOT/'pdf', root/'records', root, Measure)
    result['passed'] = test.returncode == 0 and all(c['passed'] for c in result['cases'].values())
    save(ROOT/'tests/reports/final-deployment-host.json', result)
    print(json.dumps({'stage':'host_finished','passed':result['passed']}), flush=True)
    return int(not result['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
