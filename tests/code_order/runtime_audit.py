"""Verify all actual deployments and non-destructive repair of old records."""
import json
import sqlite3
import subprocess
import sys
import time
import httpx
from common import ROOT, BASE, PID, write, digest

sys.path.insert(0, str(ROOT / 'backend'))
from scholar_graph.code_layout import code_ranges, join_code
from live_acceptance import verify_code

if __name__ == '__main__':
    backend = {str(p.relative_to(ROOT / 'backend/scholar_graph')).replace('\\', '/'): digest(p) for p in (ROOT / 'backend/scholar_graph').rglob('*.py')}
    frontend = {str(p.relative_to(ROOT / 'frontend')).replace('\\', '/'): digest(p) for name in ['app', 'components', 'lib']
                for p in (ROOT / 'frontend' / name).rglob('*') if p.suffix in ['.ts', '.tsx']}
    frontend.update({name: digest(ROOT / 'frontend' / name) for name in ['next.config.mjs', '.next/BUILD_ID']})
    report = {'deployments': []}
    for project, port, count in [('scholar-graph', 8030, 0), ('scholar-graph-item04', 8100, 37), ('scholar-graph-item05', 8120, 20),
                                  ('scholar-graph-item06', 8140, 21), ('scholar-graph-code-order', 8160, 2)]:
        row = {'project': project, 'backend_port': port, 'services': {}}
        for service, expected, folder in [('backend', backend, '/app/backend/scholar_graph/'), ('frontend', frontend, '/app/frontend/')]:
            name = project + '-' + service + '-1'
            value = json.loads(subprocess.check_output(['docker', 'inspect', name]))[0]
            assert value['State']['Health']['Status'] == 'healthy' and not value['State']['OOMKilled']
            if service == 'backend':
                code = 'import json,hashlib;from pathlib import Path;r=Path(' + repr(folder) + ');print(json.dumps({str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in r.rglob("*.py")}))'
                actual = json.loads(subprocess.check_output(['docker', 'exec', name, 'python', '-c', code]))
            else:
                code = 'const f=require("fs"),c=require("crypto");let r={};for(const n of ' + json.dumps(list(expected)) + ')r[n]=c.createHash("sha256").update(f.readFileSync(' + json.dumps(folder) + '+n)).digest("hex");process.stdout.write(JSON.stringify(r));'
                actual = json.loads(subprocess.check_output(['docker', 'exec', name, 'node', '-e', code]))
            assert actual == expected, (project, service, 'source/build mismatch')
            row['services'][service] = {'health': 'healthy', 'oom_killed': False, 'source_files_verified': len(actual),
                                         'image_id': value['Image'], 'restart': value['HostConfig']['RestartPolicy']['Name']}
        dns = subprocess.check_output(['docker', 'exec', project + '-frontend-1', 'getent', 'hosts', 'backend']).decode().strip()
        assert dns.startswith('172.')
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=60) as client:
            system = client.get('/api/v2/system').json()
            assert system['model_configured']
            actual_count = client.get('/api/v2/papers?page_size=100').json()['total']
            assert actual_count == count
            row.update(paper_count=actual_count, model_configured=True, backend_dns=dns)
            if project == 'scholar-graph-item06':
                readings = []
                for number in [1, 2]:
                    response = client.get(f'/api/v2/papers/{PID}/reading?physical_page={number}')
                    response.raise_for_status()
                    readings.extend(response.json()['chunks'])
                spans = code_ranges(readings)
                report['historical_record_source_checks'] = verify_code(join_code([c['text'] for c in readings if c['chunk_id'] in spans]))
                latencies = []
                for _ in range(5):
                    started = time.perf_counter()
                    client.get(f'/api/v2/papers/{PID}/reading?physical_page=2').raise_for_status()
                    latencies.append(round((time.perf_counter() - started) * 1000, 3))
                report['historical_warm_read_ms_five_samples'] = latencies
                with sqlite3.connect(ROOT / 'data/item06-20261029/records/workspace.sqlite3') as db:
                    source = json.loads(db.execute("select value from records where kind='code_layout' and id=?", (PID,)).fetchone()[0])
                    assert source['changes'] and source['source_sha256'] == PID.removeprefix('paper-')
                    report['historical_sidecar'] = {k: v for k, v in source.items() if k != 'chunks'}
        report['deployments'].append(row)
    before = json.loads((BASE / 'workspace-before.json').read_text(encoding='utf8'))
    for group in ['originals', 'frozen', 'old_evidence']:
        assert all(digest(ROOT / name) == sha for name, sha in before[group].items()), group + ' changed'
        report[group + '_unchanged'] = len(before[group])
    report['passed'] = True
    write(BASE / 'runtime-audit.json', report)
    print(json.dumps({'healthy_services': 10, 'paper_counts': [r['paper_count'] for r in report['deployments']],
                      'original_pdfs_unchanged': len(before['originals']), 'frozen_json_unchanged': len(before['frozen']),
                      'old_evidence_unchanged': len(before['old_evidence']), 'historical_source_code': 'passed'}))
