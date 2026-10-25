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


def export_reports(evidence, command, compose, checkout, root):
    """Export files only: pytest's Linux `*current` symlinks cannot be copied on Windows."""
    log = root / 'container-acceptance.log'
    messages = []
    for line in log.read_text(encoding='utf-8', errors='replace').splitlines():
        try:
            messages.append(json.loads(line))
        except ValueError:
            pass
    remote = next(row['report'] for row in reversed(messages) if 'report' in row)
    import re
    if not re.fullmatch(r'/app/data/docker-acceptance/[0-9a-f]{32}/container-results\.json', remote):
        raise RuntimeError('Unexpected container report path')
    parent = remote.rsplit('/', 1)[0]
    exported = root / ('reports-export-' + uuid.uuid4().hex[:8])
    exported.mkdir(exist_ok=False)
    for name in ('container-results.json', 'container-pytest.xml', 'dedup.json', 'ocr.json', 'longbook.json', 'pytest-console.txt'):
        code, _ = command('export-file-' + name.replace('.', '-'),
                          compose + ['cp', 'backend:' + parent + '/' + name, exported / name], cwd=checkout)
        if code:
            raise RuntimeError('Container report file export failed: ' + name)
    container = json.loads((exported / 'container-results.json').read_text(encoding='utf-8'))
    evidence['container_results'] = container
    evidence['exported_report'] = str(exported / 'container-results.json')
    evidence['export_method'] = 'Explicit JSON/XML/console files only; no pytest symlink tree or models exported'
    evidence['image_source_matches_clone'] = bool(container.get('source_sha256')) and all(
        hashlib.sha256((checkout / name).read_bytes()).hexdigest() == digest
        for name, digest in container['source_sha256'].items())
    for name in ('container-pytest.xml', 'dedup.json', 'ocr.json', 'longbook.json'):
        shutil.copyfile(exported / name, ROOT / 'tests/reports' / ('docker-' + name))


def verify_entrypoint(evidence, command, compose, checkout):
    if evidence.get('one_command_entrypoint', {}).get('exit_code') == 0:
        return True
    code, _ = command('one-command-up-build', compose + ['up', '--build', '-d', '--wait', '--wait-timeout', '300'],
                      cwd=checkout, timeout=420)
    evidence['one_command_entrypoint'] = {**evidence['steps'][-1],
        'scope': '同一干净克隆验证up --build入口；复用本轮无缓存构建层，不冒充第二次冷构建。'}
    return code == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf-dir', type=Path, required=True)
    parser.add_argument('--resume-export', type=Path, help='Recover report export from this existing run JSON; never reruns uploads.')
    args = parser.parse_args()
    corpus = args.pdf_dir.resolve(strict=True)
    require_files = ('1706.03762v7.pdf', '1706.03762v1.pdf', '1706.03762v1_img.pdf', 'UnderstandingDeepLearning_02_09_26_C.pdf')
    if not all((corpus / name).is_file() for name in require_files):
        raise SystemExit('All four official source files are required')
    env = dict(os.environ)
    for key in list(env):
        if any(part in key.upper() for part in ('API_KEY', 'TOKEN', 'SECRET', 'PASSWORD')):
            env.pop(key)
    env.pop('DEEPSEEK_MODEL', None)
    docker = docker_executable()
    env.update(PATH=str(docker.parent) + os.pathsep + env.get('PATH', ''),
               SCHOLAR_GRAPH_PDF_DIR=str(corpus), SCHOLAR_GRAPH_QA_MODE='extractive')
    output = ROOT / 'tests/reports/docker-reproduction-run.json'
    if args.resume_export:
        evidence = json.loads(args.resume_export.read_text(encoding='utf-8'))
        root = Path(evidence['run_root']).resolve(strict=True)
        if not root.is_relative_to((ROOT / 'data/docker-reproduction').resolve()):
            raise RuntimeError('Export recovery must stay inside this workspace reproduction directory')
        evidence['status'] = 'export-recovery-running'
        checkout = root / 'checkout'
    else:
        run_id = uuid.uuid4().hex
        root = ROOT / 'data/docker-reproduction' / run_id
        root.mkdir(parents=True, exist_ok=False)
        checkout = root / 'checkout'
        evidence = {'run_id': run_id, 'run_utc': datetime.now(timezone.utc).isoformat(), 'run_root': str(root),
                    'remote': REMOTE, 'branch': 'main', 'project': 'sg-clean-' + run_id[:10], 'steps': [],
                    'credentials_forwarded': False, 'host_parsed_records_used': False, 'status': 'running'}

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
        if args.resume_export:
            compose = [docker, 'compose', '-p', evidence['project'], '-f', 'docker-compose.yml',
                       '-f', 'services/docker-compose.acceptance.yml']
            export_reports(evidence, command, compose, checkout, root)
            entrypoint_ok = verify_entrypoint(evidence, command, compose, checkout)
            evidence['status'] = 'passed' if entrypoint_ok and evidence.get('image_source_matches_clone') and evidence['container_results']['passed'] else 'failed'
            evidence['export_recovered_without_rerunning_cases'] = True
            save(output, evidence)
            print(json.dumps({'status': evidence['status'], 'evidence': str(output)}, ensure_ascii=False), flush=True)
            return 0 if evidence['status'] == 'passed' else 1
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
        export_reports(evidence, command, compose, checkout, root)
        entrypoint_ok = verify_entrypoint(evidence, command, compose, checkout)
        _, status = command('clone-final-status', ['git', 'status', '--porcelain=v1'], cwd=checkout)
        evidence['clone']['clean_after_build_and_run'] = not status.strip()
        evidence['status'] = 'passed' if code == 0 and entrypoint_ok and evidence.get('image_source_matches_clone') and evidence.get('container_results', {}).get('passed') else 'failed'
    except Exception as error:
        evidence.update(status='failed', blocking_error={'type': type(error).__name__, 'message': str(error)[:1000]})
    save(output, evidence)
    print(json.dumps({'status': evidence['status'], 'evidence': str(output), 'run_root': str(root)}, ensure_ascii=False), flush=True)
    return 0 if evidence['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
