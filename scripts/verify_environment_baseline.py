"""Probe the actual Compose deployment without recording environment secrets."""
import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import subprocess

import httpx

ROOT = Path(__file__).resolve().parents[1]


def command(*args):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=60)
    if result.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(args[:4]))
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'data') or output.exists():
        raise ValueError('Choose a new evidence file under data.')
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'passed': False, 'checks': {}}
    try:
        raw = command('docker', 'compose', 'ps', '--all', '--format', 'json')
        services = json.loads(raw) if raw.startswith('[') else [json.loads(line) for line in raw.splitlines()]
        report['services'] = [{k: row.get(k) for k in ('Service', 'State', 'Health', 'Image')} for row in services]
        report['checks']['both_services_healthy'] = {r['Service'] for r in services} == {'backend', 'frontend'} and all(
            r.get('State') == 'running' and r.get('Health') == 'healthy' for r in services)
        dns = command('docker', 'compose', 'exec', '-T', 'frontend', 'getent', 'hosts', 'backend')
        report['dns'] = dns
        report['checks']['backend_dns_172_private'] = any(
            ipaddress.ip_address(line.split()[0]) in ipaddress.ip_network('172.16.0.0/12') for line in dns.splitlines())
        configured = json.loads(command('docker', 'compose', 'exec', '-T', 'backend', 'python', '-c',
            "import os,json; print(json.dumps({n:bool(os.getenv(n,'').strip()) for n in ('DEEPSEEK_API_KEY','DEEPSEEK_MODEL')}))"))
        report['model_configuration_nonempty'] = configured
        report['checks']['model_configuration_nonempty'] = all(configured.values())
        with httpx.Client(trust_env=False, timeout=20) as client:
            for name, url in [('backend_system', 'http://127.0.0.1:8000/api/v2/system'),
                              ('frontend_workspace_proxy', 'http://127.0.0.1:3000/api/workspace/system'),
                              ('frontend_legacy_proxy', 'http://127.0.0.1:3000/api/backend/papers?page_size=1')]:
                response = client.get(url)
                report[name] = {'http_status': response.status_code}
                report['checks'][name] = response.status_code == 200
                if response.status_code == 200 and name != 'frontend_legacy_proxy':
                    body = response.json()
                    required = ('paper_management', 'version_choice', 'reading_pages', 'author_mapping',
                                'layout_regions', 'tracking_read_only', 'csv_provenance', 'translation_snapshots')
                    report[name].update(workspace_release=body.get('workspace_release'), qa_mode=body.get('qa_mode'),
                                        model_configured=body.get('model_configured'))
                    report['checks'][name + '_release_and_capabilities'] = body.get('workspace_release') == '20261027-workbench-r2' and all(
                        body.get('capabilities', {}).get(key) for key in required)
        report['source_hashes'] = []
        for service, relative, remote in [('backend', 'backend/scholar_graph/api.py', '/app/backend/scholar_graph/api.py'),
                ('backend', 'backend/scholar_graph/workspace.py', '/app/backend/scholar_graph/workspace.py'),
                ('frontend', 'frontend/components/ResearchChat.tsx', '/app/frontend/components/ResearchChat.tsx')]:
            digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            actual = command('docker', 'compose', 'exec', '-T', service, 'sha256sum', remote).split()[0]
            report['source_hashes'].append({'file': relative, 'workspace_sha256': digest, 'container_sha256': actual})
        report['checks']['sampled_runtime_source_matches_workspace'] = all(
            row['workspace_sha256'] == row['container_sha256'] for row in report['source_hashes'])
        report['passed'] = all(report['checks'].values())
    except Exception as error:
        report['error_type'] = type(error).__name__
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'checks': report['checks'], 'error_type': report.get('error_type')}, ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
