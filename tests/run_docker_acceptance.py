"""Run inside the built backend container, against its actual HTTP server."""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from urllib.parse import unquote

import httpx
import psutil
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from scholar_graph.validation import ContractGate

FILES = {'dedup': ['1706.03762v7.pdf', '1706.03762v1.pdf'],
         'ocr': ['1706.03762v1_img.pdf'], 'longbook': ['UnderstandingDeepLearning_02_09_26_C.pdf']}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def cgroup_number(name):
    try:
        return int((Path('/sys/fs/cgroup') / name).read_text().strip())
    except (OSError, ValueError):
        return None


class Meter:
    def __enter__(self):
        self.start, self.done = time.perf_counter(), threading.Event()
        self.result = {'rss_sampled_peak_bytes': 0, 'cgroup_sampled_peak_bytes': None,
                       'cgroup_lifetime_peak_before_bytes': cgroup_number('memory.peak'),
                       'interval_seconds': .05, 'samples': 0}
        self.sample()
        self.thread = threading.Thread(target=self.poll, daemon=True)
        self.thread.start()
        return self

    def sample(self):
        rss = 0
        for process in psutil.process_iter():
            try:
                rss += process.memory_info().rss
            except psutil.Error:
                pass
        self.result['rss_sampled_peak_bytes'] = max(rss, self.result['rss_sampled_peak_bytes'])
        current = cgroup_number('memory.current')
        if current is not None:
            self.result['cgroup_sampled_peak_bytes'] = max(current, self.result['cgroup_sampled_peak_bytes'] or 0)
        self.result['samples'] += 1

    def poll(self):
        while not self.done.wait(.05):
            self.sample()

    def __exit__(self, *args):
        self.done.set()
        self.thread.join()
        self.sample()
        self.result.update(elapsed_seconds=round(time.perf_counter() - self.start, 6),
                           cgroup_lifetime_peak_after_bytes=cgroup_number('memory.peak'),
                           memory_scope='容器内可读进程RSS采样合计；cgroup采样含文件缓存；lifetime峰值非单次上传峰值。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite-only', action='store_true', help='No official corpus required; self-made HTTP QA smoke only.')
    args = parser.parse_args()
    require(sys.platform == 'linux' and Path('/.dockerenv').exists(), 'This probe requires an actual Linux Docker container')
    require(not os.environ.get('DEEPSEEK_API_KEY') and not os.environ.get('DEEPSEEK_MODEL'), 'No model credentials allowed')
    require(os.environ.get('SCHOLAR_GRAPH_QA_MODE') == 'extractive', 'Explicit extractive mode required')
    root = ROOT / 'data/docker-acceptance' / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=False)
    result = {'scope': '容器内官方 pdf/ 真文件' if not args.suite_only else '容器内全量回归及自制样例问答',
              'run_utc': datetime.now(timezone.utc).isoformat(), 'output_root': str(root),
              'platform': platform.platform(), 'hostname': platform.node(), 'python': sys.version,
              'real_model_calls': 0, 'credentials': '未设置', 'cases': {},
              'versions': {name: version(name) for name in ('mineru', 'paddleocr', 'paddlepaddle', 'langgraph', 'fastapi', 'psutil')}}
    report = root / 'container-results.json'
    try:
        with httpx.Client(base_url='http://127.0.0.1:8000', timeout=2100, trust_env=False) as client:
            health = client.get('/api/v1/papers?page_size=1')
            result['backend_health'] = {'http_status': health.status_code, 'body': health.json()}
            require(health.status_code == 200 and health.json()['total'] == 0,
                    'Acceptance requires an EMPTY backend volume; refusing to reuse parsed records')
            proxy = httpx.get('http://frontend:3000/api/backend/papers?page_size=1', timeout=30, trust_env=False)
            result['frontend_proxy_health'] = {'http_status': proxy.status_code, 'body': proxy.json()}
            require(proxy.status_code == 200, 'Actual frontend proxy health failed')
            result['empty_backend_before_tests'] = True
            # Source fingerprints prove which tracked inputs entered this image.
            names = ['Dockerfile', 'docker-compose.yml', '.dockerignore', 'backend/pyproject.toml',
                     'backend/scholar_graph/pipeline.py', 'frontend/package-lock.json',
                     'frontend/app/api/backend/[...path]/route.ts', 'tests/run_docker_acceptance.py']
            result['source_sha256'] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}
            junit = root / 'container-pytest.xml'
            started = time.perf_counter()
            suite = subprocess.run([sys.executable, '-m', 'pytest', 'tests', '-q', '--run-ocr', '--run-real-model',
                                    '--basetemp', str(root / 'pytest-temp'), '--junitxml', str(junit)],
                                   cwd=ROOT, capture_output=True, timeout=1800)
            # Only test output from this explicit no-key process is retained.
            (root / 'pytest-console.txt').write_bytes(suite.stdout + suite.stderr)
            stats = {'exit_code': suite.returncode, 'elapsed_seconds': round(time.perf_counter() - started, 6),
                     'junit': str(junit), 'tests': None, 'failures': None, 'errors': None, 'skipped': None}
            if junit.exists():
                suites = list(ET.parse(junit).getroot().iter('testsuite'))
                stats.update({key: sum(int(s.attrib[key]) for s in suites) for key in ('tests', 'failures', 'errors', 'skipped')})
                stats['skipped_cases'] = [{'name': c.attrib['name'], 'reason': c.find('skipped').attrib.get('message')}
                                          for c in ET.parse(junit).getroot().iter('testcase') if c.find('skipped') is not None]
            result['regression'] = stats
            save(report, result)
            print(json.dumps({'stage': 'container_regression', **stats}, ensure_ascii=False), flush=True)
            gate = ContractGate()
            if not args.suite_only:
                corpus = Path('/corpus')
                require(corpus.is_dir() and os.statvfs(corpus).f_flag & os.ST_RDONLY, 'Official corpus must be mounted read-only')
                result['corpus_read_only'] = True
                for case, filenames in FILES.items():
                    rows = []
                    for filename in filenames:
                        path = corpus / filename
                        digest = hashlib.sha256(path.read_bytes()).hexdigest()
                        with path.open('rb') as handle:
                            pages = len(PdfReader(handle).pages)
                        pid = 'paper-' + digest
                        initial = client.get(f'/api/v1/papers/{pid}/parse-status')
                        require(initial.status_code == 404, 'Source already parsed before this container upload')
                        with Meter() as meter:
                            with path.open('rb') as handle:
                                response = client.post('/api/v1/papers', files={'file': (filename, handle, 'application/pdf')})
                        status = client.get(f'/api/v1/papers/{pid}/parse-status')
                        chunk_page = client.get(f'/api/v1/papers/{pid}/chunks?page_size=3')
                        row = {'file': filename, 'sha256': digest, 'bytes': path.stat().st_size, 'pages': pages,
                               'http_status': response.status_code, 'response': response.json(), 'measurement': meter.result,
                               'status_http': status.status_code, 'status': status.json(),
                               'chunks_http': chunk_page.status_code, 'chunks': chunk_page.json().get('total', 0),
                               'text_samples': [c['text'][:160] for c in chunk_page.json().get('items', [])],
                               'warning': unquote(response.headers.get('X-ScholarGraph-Dedup-Warning', ''))}
                        require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'Official corpus changed')
                        if response.status_code == 201:
                            gate.record('PaperMeta', response.json())
                        if status.status_code == 200:
                            gate.record('ParseStatus', status.json())
                        row['passed'] = response.status_code == 201 and row['status'].get('status') == 'completed' and row['chunks'] > 0
                        if case == 'dedup':
                            for endpoint in ('dedup-decision', 'diff-summary'):
                                extra = client.get(f'/api/v1/papers/{pid}/{endpoint}')
                                row[endpoint] = {'http_status': extra.status_code, 'body': extra.json()}
                        if case == 'longbook':
                            page = max(1, (row['chunks'] + 99) // 100)
                            last = client.get(f'/api/v1/papers/{pid}/chunks?page={page}&page_size=100')
                            row['last_page'] = {'http_status': last.status_code, 'items': len(last.json().get('items', [])),
                                                'max_pdf_page': max((c['page_number'] for c in last.json().get('items', [])), default=None)}
                            row['overflow_items'] = len(client.get(f'/api/v1/papers/{pid}/chunks?page=999999').json().get('items', []))
                        progress = ROOT / 'data/records/partial' / pid / 'progress.json'
                        row['batch_metrics'] = json.loads(progress.read_text()) if progress.exists() else None
                        rows.append(row)
                        result['cases'][case] = {'uploads': rows}
                        save(root / f'{case}.json', result['cases'][case])
                        save(report, result)
                        print(json.dumps({'stage': case, 'file': filename, 'http': row['http_status'], 'chunks': row['chunks'],
                                          'seconds': meter.result['elapsed_seconds'], 'passed': row['passed']}, ensure_ascii=False), flush=True)
                    passed = all(row['passed'] for row in rows)
                    if case == 'dedup':
                        passed = passed and all(rows[-1][name]['http_status'] == 200 for name in ('dedup-decision', 'diff-summary'))
                        passed = passed and '建议保留库里较新版本（v7）' in rows[-1]['warning']
                    result['cases'][case]['passed'] = passed
                    save(root / f'{case}.json', result['cases'][case])
                qa_id = 'paper-' + result['cases']['dedup']['uploads'][0]['sha256']
                question = 'Which optimizer?'
            else:
                from sample_pdfs import make_pdf
                path = make_pdf(root / 'self-made.pdf')
                with path.open('rb') as handle:
                    uploaded = client.post('/api/v1/papers', files={'file': (path.name, handle, 'application/pdf')})
                require(uploaded.status_code == 201, 'Self-made HTTP upload failed')
                qa_id, question = uploaded.json()['id'], 'How many samples?'
            answer = client.post(f'/api/v1/papers/{qa_id}/qa', json={'question': question})
            qa = {'http_status': answer.status_code, 'question': question, 'body': answer.json()}
            qa['passed'] = answer.status_code == 200 and not qa['body'].get('refused', True) and bool(qa['body'].get('anchors'))
            if answer.status_code == 200:
                gate.record('QAAnswer', answer.json())
            result['no_key_qa'] = qa
            result['passed'] = suite.returncode == 0 and qa['passed'] and all(c['passed'] for c in result['cases'].values())
    except Exception as error:
        # Exceptions here are local probe errors; API errors are retained as normal data.
        result.update(passed=False, probe_error={'type': type(error).__name__, 'message': str(error)[:1000]})
    save(report, result)
    print(json.dumps({'passed': result['passed'], 'report': str(report)}, ensure_ascii=False), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
