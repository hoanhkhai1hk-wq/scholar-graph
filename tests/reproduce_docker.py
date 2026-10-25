"""Fresh remote-main clone -> no-cache build -> actual containers -> export evidence.

This host-side stdlib helper never copies a venv, model cache, node_modules or
parsed records. Normal application startup only requires Docker Compose.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMOTE = 'https://github.com/hoanhkhai1hk-wq/scholar-graph.git'


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def docker_executable():
    found = shutil.which('docker')
    if found:
        return Path(found)
    candidate = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/DockerDesktop/resources/bin/docker.exe'
    if candidate.is_file():
        return candidate
    raise RuntimeError('Docker executable not found')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf-dir', type=Path, required=True)
    args = parser.parse_args()
    corpus = args.pdf_dir.resolve(strict=True)
    require_files = ('1706.03762v7.pdf', '1706.03762v1.pdf', '1706.03762v1_img.pdf', 'UnderstandingDeepLearning_02_09_26_C.pdf')
    if not all((corpus / name).is_file() for name in require_files):
        raise SystemExit('All four official source files are required')
    run_id = uuid.uuid4().hex
    root = ROOT / 'data/docker-reproduction' / run_id
    root.mkdir(parents=True, exist_ok=False)
    checkout = root / 'checkout'
    env = dict(os.environ)
    for key in list(env):
        if any(part in key.upper() for part in ('API_KEY', 'TOKEN', 'SECRET', 'PASSWORD')):
            env.pop(key)
    env.pop('DEEPSEEK_MODEL', None)
    docker = docker_executable()
    env.update(PATH=str(docker.parent) + os.pathsep + env.get('PATH', ''),
               SCHOLAR_GRAPH_PDF_DIR=str(corpus), SCHOLAR_GRAPH_QA_MODE='extractive')
    evidence = {'run_id': run_id, 'run_utc': datetime.now(timezone.utc).isoformat(), 'run_root': str(root),
                'remote': REMOTE, 'branch': 'main', 'project': 'sg-clean-' + run_id[:10], 'steps': [],
                'credentials_forwarded': False, 'host_parsed_records_used': False, 'status': 'running'}
    output = ROOT / 'tests/reports/docker-reproduction-run.json'

    def command(label, argv, *, cwd=ROOT, timeout=3600):
        started = time.perf_counter()
        log = root / (label + '.log')
        print(json.dumps({'stage': label, 'started': True}, ensure_ascii=False), flush=True)
        with log.open('wb') as handle:
            try:
                run = subprocess.run([str(a) for a in argv], cwd=cwd, env=env,
                                     stdout=handle, stderr=subprocess.STDOUT, timeout=timeout)
                code = run.returncode
            except subprocess.TimeoutExpired:
                code = 124
        text = log.read_text(encoding='utf-8', errors='replace')
        lines = text.splitlines()
        row = {'stage': label, 'command': [str(a) for a in argv], 'exit_code': code,
               'elapsed_seconds': round(time.perf_counter() - started, 6), 'log': str(log),
               'log_bytes': log.stat().st_size, 'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
               'first_lines': lines[:12], 'last_lines': lines[-24:]}
        evidence['steps'].append(row)
        save(output, evidence)
        print(json.dumps({'stage': label, 'exit_code': code, 'seconds': row['elapsed_seconds']}, ensure_ascii=False), flush=True)
        return code, text

    try:
        code, _ = command('clone-main', ['git', 'clone', '--branch', 'main', '--single-branch', REMOTE, checkout], timeout=180)
        if code:
            raise RuntimeError('Fresh remote clone failed')
        _, head = command('clone-head', ['git', 'rev-parse', 'HEAD'], cwd=checkout)
        _, status = command('clone-status', ['git', 'status', '--porcelain=v1'], cwd=checkout)
        evidence['clone'] = {'path': str(checkout), 'commit': head.strip(), 'clean': not status.strip(),
                             'host_artifacts_absent': {name: not (checkout / name).exists() for name in
                                                       ('backend/.venv', 'frontend/node_modules', 'frontend/.next', '.env', 'pdf', 'data')}}
        if status.strip() or not all(evidence['clone']['host_artifacts_absent'].values()):
            raise RuntimeError('Clone contains reused host artifacts')
        compose = [docker, 'compose', '-p', evidence['project'], '-f', 'docker-compose.yml',
                   '-f', 'services/docker-compose.acceptance.yml']
        code, config = command('compose-config', compose + ['config', '--format', 'json'], cwd=checkout)
        if code:
            raise RuntimeError('Official Compose config validation failed')
        parsed = json.loads(config)
        evidence['compose_config'] = {'services': sorted(parsed['services']),
                                       'backend_volumes': parsed['services']['backend']['volumes']}
        command('docker-version', [docker, 'version'], cwd=checkout)
        code, _ = command('build-no-cache', compose + ['build', '--no-cache'], cwd=checkout, timeout=7200)
        if code:
            raise RuntimeError('No-cache image build failed; containers and cases not marked passed')
        code, _ = command('up-wait', compose + ['up', '-d', '--wait', '--wait-timeout', '300'], cwd=checkout, timeout=420)
        if code:
            raise RuntimeError('Container startup or healthcheck failed')
        _, state = command('container-state', compose + ['ps', '--format', 'json'], cwd=checkout)
        evidence['container_state'] = state
        code, _ = command('container-acceptance', compose + ['exec', '-T', 'backend', 'python', 'tests/run_docker_acceptance.py'],
                          cwd=checkout, timeout=7200)
        exported = root / 'container-output'
        copy_code, _ = command('export-container-results', compose + ['cp', 'backend:/app/data/docker-acceptance', exported], cwd=checkout)
        if not copy_code:
            reports = list(exported.rglob('container-results.json'))
            if len(reports) == 1:
                container = json.loads(reports[0].read_text(encoding='utf-8'))
                evidence['container_results'] = container
                evidence['exported_report'] = str(reports[0])
                evidence['image_source_matches_clone'] = all(
                    hashlib.sha256((checkout / name).read_bytes()).hexdigest() == digest
                    for name, digest in container.get('source_sha256', {}).items())
                for filename in ('container-pytest.xml', 'dedup.json', 'ocr.json', 'longbook.json'):
                    source = reports[0].parent / filename
                    if source.is_file():
                        shutil.copyfile(source, ROOT / 'tests/reports' / ('docker-' + filename))
        _, status = command('clone-final-status', ['git', 'status', '--porcelain=v1'], cwd=checkout)
        evidence['clone']['clean_after_build_and_run'] = not status.strip()
        evidence['status'] = 'passed' if code == 0 and evidence.get('image_source_matches_clone') and evidence.get('container_results', {}).get('passed') else 'failed'
    except Exception as error:
        evidence.update(status='failed', blocking_error={'type': type(error).__name__, 'message': str(error)[:1000]})
    save(output, evidence)
    print(json.dumps({'status': evidence['status'], 'evidence': str(output), 'run_root': str(root)}, ensure_ascii=False), flush=True)
    return 0 if evidence['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
