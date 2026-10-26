"""Actual Linux container full suite, official uploads and automatic timer evidence."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4
import xml.etree.ElementTree as ET

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from deployment_checks import official_cases, save
from run_docker_acceptance import Meter


def main():
    assert sys.platform == 'linux' and Path('/.dockerenv').exists()
    assert not os.environ.get('DEEPSEEK_API_KEY') and not os.environ.get('DEEPSEEK_MODEL')
    root = ROOT/'data/final-deployment'/uuid4().hex
    root.mkdir(parents=True)
    report = root/'container.json'
    result = {'scope':'容器内官方 pdf/ 真文件与全量层', 'output_root':str(root), 'credentials':'未设置', 'passed':False}
    with httpx.Client(base_url='http://127.0.0.1:8000', timeout=2400, trust_env=False) as client:
        health = client.get('/api/v1/papers?page_size=1')
        result['initial_health'] = {'status':health.status_code,'total':health.json().get('total')}
        assert health.status_code == 200 and health.json()['total'] == 0, 'Fresh empty backend required'
        assert os.statvfs('/corpus').f_flag & os.ST_RDONLY, 'Official corpus must be read-only'
        names = [str(p.relative_to(ROOT)) for p in (ROOT/'backend/scholar_graph').glob('*.py')]
        names += ['Dockerfile','docker-compose.yml','.dockerignore','backend/pyproject.toml',
                  'frontend/package-lock.json','tests/run_final_deployment_container.py','tests/conftest.py']
        result['source_sha256'] = {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
        started = time.perf_counter()
        with (root/'model-download.log').open('wb') as handle:
            try:
                download = subprocess.run([os.environ['SCHOLAR_GRAPH_VECTOR_PYTHON'], 'backend/download_bge_m3.py'],
                    cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, timeout=2400)
                result['model_download'] = {'exit_code':download.returncode}
            except subprocess.TimeoutExpired:
                result['model_download'] = {'exit_code':124}
        result['model_download']['elapsed_seconds'] = round(time.perf_counter()-started,6)
        save(report,result)
        print(json.dumps({'stage':'model_download', **result['model_download']}),flush=True)
        junit = root/'container-pytest.xml'
        started = time.perf_counter()
        with (root/'pytest-console.txt').open('wb') as handle:
            test = subprocess.run([sys.executable,'tests/run_regression.py','full','--no-key','--corpus-dir','/corpus',
                '--junit',str(junit)],cwd=ROOT,stdout=handle,stderr=subprocess.STDOUT,timeout=3600)
        suites = ET.parse(junit).getroot().findall('testsuite')
        stats = {k:sum(int(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
        stats.update(exit_code=test.returncode, elapsed_seconds=round(time.perf_counter()-started,6),
            skipped_cases=[{'name':c.get('name'),'reason':c.find('skipped').get('message')} for s in suites
                           for c in s.findall('testcase') if c.find('skipped') is not None])
        result['regression'] = stats
        save(report,result)
        print(json.dumps({'stage':'container_full',**stats}),flush=True)
        result['cases'] = official_cases(client,Path('/corpus'),ROOT/'data/records',root,Meter)
        pid = 'paper-'+result['cases']['dedup']['uploads'][0]['sha256']
        answer = client.post('/api/v1/papers/'+pid+'/qa',json={'question':'Which optimizer?'})
        result['no_key_qa'] = {'http_status':answer.status_code,'body':answer.json()}
        result['scheduler'] = client.get('/api/v1/retrieval/tracking/status').json()
        events = ROOT/'data/records/tracking/scheduler-events.jsonl'
        result['scheduler_events'] = [json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []
        import sqlite3
        with sqlite3.connect(ROOT/'data/records/tracking/state.sqlite3') as db:
            runs = [json.loads(row[0]) for row in db.execute('SELECT payload FROM runs ORDER BY started')]
        result['automatic_public_runs'] = [r for r in runs if r.get('queries')]
        result['automatic_timer_triggered'] = len(result['automatic_public_runs']) >= 2
        result['passed'] = (test.returncode == 0 and result['model_download']['exit_code'] == 0
            and all(c['passed'] for c in result['cases'].values()) and result['automatic_timer_triggered']
            and answer.status_code == 200 and not answer.json().get('refused',True))
    save(report,result)
    print(json.dumps({'passed':result['passed'],'report':str(report)}),flush=True)
    return int(not result['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
