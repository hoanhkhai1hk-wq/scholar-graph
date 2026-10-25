"""官方 pdf/ 真文件修复验收：真实上传、运行中取数、默认后端配置。"""
import argparse
import json
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote

from official_pdf_support import ROOT, prepare, header, save, file_info, Measure, parsed_details, read
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from scholar_graph.api import create_app

BASELINE = 'fb98c8fddadfebdcc58e325f7bdd53b4d42ba71f'
FILES = {'dedup': ['1706.03762v7.pdf', '1706.03762v1.pdf'],
         'ocr': ['1706.03762v1_img.pdf'], 'longbook': ['UnderstandingDeepLearning_02_09_26_C.pdf']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case', choices=FILES)
    parser.add_argument('--run-root', type=Path)
    args = parser.parse_args()
    root = prepare(args.run_root or ROOT / 'data/official-repair' / args.case)
    records = root / 'records'
    if args.case == 'ocr':
        source = ROOT / 'data/repair-ocr-model-smoke/models/paddlex'
        if source.is_dir():
            shutil.copytree(source, records / 'models/paddlex', ignore=shutil.ignore_patterns('*.lock'))
    result = header('repair-' + args.case)
    result.update(baseline=BASELINE, default_api_configuration=True, uploads=[])
    report = ROOT / f'tests/reports/official-pdf-repair-{args.case}.json'
    app = create_app(data_dir=records)
    with TestClient(app) as client:
        for filename in FILES[args.case]:
            path = ROOT / 'pdf' / filename
            before = file_info(path)
            pid = 'paper-' + before['sha256']
            observations = []

            def post():
                with Measure() as meter:
                    with path.open('rb') as handle:
                        response = client.post('/api/v1/papers', files={'file': (filename, handle, 'application/pdf')})
                return {'http_status': response.status_code, 'response': response.json(), 'measurement': meter.result,
                        'warning_header': response.headers.get('X-ScholarGraph-Dedup-Warning'),
                        'warning_text': unquote(response.headers.get('X-ScholarGraph-Dedup-Warning', '')) or None}

            start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(post)
                while not future.done():
                    status = read(client, f'/api/v1/papers/{pid}/parse-status')
                    if status['http_status'] == 200:
                        chunks = read(client, f'/api/v1/papers/{pid}/chunks?page=1&page_size=1')
                        observation = {'elapsed_seconds': round(time.perf_counter() - start, 3),
                                       'status': status['response'], 'chunks_http': chunks['http_status'],
                                       'published_chunks': chunks['response'].get('total', 0)}
                        if not observations or observation['status'] != observations[-1]['status']:
                            observations.append(observation)
                            save(root / 'live.json', observation)
                    time.sleep(2)
                value = future.result()
            value.update(source=before, source_after=file_info(path), observations=observations)
            value['parsed'] = parsed_details(client, records, value)
            value['status'] = read(client, f'/api/v1/papers/{pid}/parse-status')
            value['chunks_first'] = read(client, f'/api/v1/papers/{pid}/chunks?page=1&page_size=5')
            if args.case == 'dedup':
                value['decision'] = read(client, f'/api/v1/papers/{pid}/dedup-decision')
                value['diff'] = read(client, f'/api/v1/papers/{pid}/diff-summary')
            else:
                progress = records / 'partial' / pid / 'progress.json'
                value['batch_metrics'] = json.loads(progress.read_text(encoding='utf-8')) if progress.exists() else None
                total = value['chunks_first']['response'].get('total', 0)
                value['chunks_last'] = read(client, f'/api/v1/papers/{pid}/chunks?page={max(1, (total + 99) // 100)}&page_size=100')
                value['chunks_overflow'] = read(client, f'/api/v1/papers/{pid}/chunks?page=999999&page_size=100')
            result['uploads'].append(value)
            save(report, result)
    result['passed'] = all(v['http_status'] == 201 and v['status']['response']['status'] == 'completed'
                           and v['chunks_first']['response'].get('total', 0) > 0 for v in result['uploads'])
    if args.case == 'dedup':
        last = result['uploads'][-1]
        result['passed'] = result['passed'] and last['decision']['http_status'] == last['diff']['http_status'] == 200 and '建议保留库里较新版本（v7）' in (last['warning_text'] or '')
    save(report, result)
    print(json.dumps({'case': args.case, 'scope': result['scope'], 'passed': result['passed'],
                      'uploads': [{'http': v['http_status'], 'seconds': v['measurement']['elapsed_seconds'],
                                   'chunks': v['chunks_first']['response'].get('total'), 'warning': v['warning_text']} for v in result['uploads']]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
