"""Read-only verification of the actual demo; never emit environment values."""
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/tracking-fix-20261031'


def command(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, timeout=30).strip()


def summary(run):
    keys = ('run_id', 'status', 'phase', 'started_at', 'finished_at',
            'duration_seconds', 'query_total_count', 'query_succeeded_count',
            'query_failed_count', 'discovered_count', 'candidate_count',
            'imported_count', 'duplicate_count', 'failed_count', 'max_imports')
    return {**{key: run.get(key) for key in keys}, 'queries': len(run['queries']),
            'error_count': len(run['errors'])}


result = {'checked_at': datetime.now(timezone.utc).isoformat()}
result['http'] = {}
for url in ('http://127.0.0.1:3400/retrieval', 'http://127.0.0.1:8100/api/v2/system'):
    with urllib.request.urlopen(url, timeout=15) as response:
        result['http'][url] = response.status
result['backend_health'] = command('docker', 'inspect', '--format',
                                   '{{.State.Health.Status}}', 'scholar-graph-item04-backend-1')
result['frontend_healthcheck'] = command('docker', 'inspect', '--format',
                                         '{{if .State.Health}}{{.State.Health.Status}}{{else}}not_configured{{end}}',
                                         'scholar-graph-item04-frontend-1')
result['backend_dns'] = command('docker', 'exec', 'scholar-graph-item04-frontend-1',
                                 'getent', 'hosts', 'backend')
result['backend_configuration'] = json.loads(command('docker', 'exec', 'scholar-graph-item04-backend-1',
    'python', '-c', 'import os,json; print(json.dumps({"KEY_SET":bool(os.environ.get("DEEPSEEK_API_KEY")),"MODEL_SET":bool(os.environ.get("DEEPSEEK_MODEL"))}))'))
result['backend_sources_match'] = {}
for name in ('arxiv_fetch.py', 'tracking.py'):
    local = hashlib.sha256((ROOT / 'backend/scholar_graph' / name).read_bytes()).hexdigest()
    deployed = command('docker', 'exec', 'scholar-graph-item04-backend-1', 'python', '-c',
        f'import hashlib,pathlib; print(hashlib.sha256(pathlib.Path("/app/backend/scholar_graph/{name}").read_bytes()).hexdigest())')
    result['backend_sources_match'][name] = local == deployed
result['frontend_build_matches'] = (ROOT / 'frontend/.next/BUILD_ID').read_text().strip() == command(
    'docker', 'exec', 'scholar-graph-item04-frontend-1', 'cat', '/app/frontend/.next/BUILD_ID')
baseline = json.loads((OUT / 'baseline.json').read_text(encoding='utf-8-sig'))
result['preexisting_upload_edit_unchanged'] = baseline['upload_sha256'] == hashlib.sha256(
    (ROOT / 'frontend/components/UploadForm.tsx').read_bytes()).hexdigest()
dbfile = ROOT / 'data/item04-20261028/records/tracking/state.sqlite3'
with sqlite3.connect(dbfile.as_uri() + '?mode=ro', uri=True) as db:
    old = json.loads(db.execute('SELECT payload FROM runs WHERE id=?',
                     ('7dc11c77e40e45988738c5e642aac467',)).fetchone()[0])
    latest = json.loads(db.execute('SELECT payload FROM runs ORDER BY started DESC,id DESC LIMIT 1').fetchone()[0])
result['screenshot_original_run'] = summary(old)
result['latest_run_at_audit_time'] = summary(latest)
assert all(code == 200 for code in result['http'].values())
assert result['backend_health'] == 'healthy'
assert all(result['backend_sources_match'].values())
assert result['frontend_build_matches']
assert result['preexisting_upload_edit_unchanged']
(OUT / 'runtime.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
