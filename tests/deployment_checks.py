"""Same official upload checks for host and container; measurements stay separate."""
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote

from pypdf import PdfReader

FILES = {'dedup': ['1706.03762v7.pdf', '1706.03762v1.pdf'], 'ocr': ['1706.03762v1_img.pdf'],
         'longbook': ['UnderstandingDeepLearning_02_09_26_C.pdf']}


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def official_cases(client, corpus, records, output, meter_class):
    cases = {}
    for case, names in FILES.items():
        rows = []
        for name in names:
            source = corpus/name
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            pid = 'paper-'+digest
            row = {'file': name, 'sha256': digest, 'bytes': source.stat().st_size, 'scope': '官方 pdf/ 真文件'}
            rows.append(row)
            try:
                with source.open('rb') as stream:
                    row['pages'] = len(PdfReader(stream).pages)
                row['initial_status_http'] = client.get(f'/api/v1/papers/{pid}/parse-status').status_code
                assert row['initial_status_http'] == 404, 'Refuse to reuse a previously parsed source'
                with meter_class() as meter:
                    with source.open('rb') as stream:
                        response = client.post('/api/v1/papers', files={'file': (name, stream, 'application/pdf')})
                page = client.get(f'/api/v1/papers/{pid}/chunks?page_size=3')
                status = client.get(f'/api/v1/papers/{pid}/parse-status')
                row.update(http_status=response.status_code, response=response.json(), measurement=meter.result,
                    parse_status=status.json(), chunks=page.json().get('total', 0),
                    text_samples=[c['text'][:160] for c in page.json().get('items', [])],
                    warning=unquote(response.headers.get('X-ScholarGraph-Dedup-Warning', '')),
                    dedup_metadata=unquote(response.headers.get('X-ScholarGraph-Dedup-Meta', '')))
                row['passed'] = response.status_code == 201 and row['chunks'] > 0 and row['parse_status']['status'] == 'completed'
                assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
                if case == 'dedup':
                    for endpoint in ('dedup-decision', 'diff-summary'):
                        result = client.get(f'/api/v1/papers/{pid}/{endpoint}')
                        row[endpoint] = {'http_status': result.status_code, 'body': result.json()}
                else:
                    progress = records/'partial'/pid/'progress.json'
                    row['batch_metrics'] = json.loads(progress.read_text()) if progress.exists() else None
                    last = client.get(f'/api/v1/papers/{pid}/chunks?page={max(1,(row["chunks"]+99)//100)}&page_size=100')
                    row['last_page'] = {'http_status': last.status_code, 'items': len(last.json().get('items', [])),
                        'max_pdf_page': max((c['page_number'] for c in last.json().get('items', [])), default=None)}
                    row['overflow_items'] = len(client.get(f'/api/v1/papers/{pid}/chunks?page=999999').json().get('items', []))
                    if case == 'longbook':
                        row['passed'] &= row['pages'] == 541 and row['last_page']['max_pdf_page'] == 541 and row['overflow_items'] == 0
                    else:
                        row['passed'] &= any(len(s) >= 10 and any(c.isalpha() for c in s) for s in row['text_samples'])
            except Exception as error:
                row.update(passed=False, probe_error={'type': type(error).__name__, 'message': str(error)[:500]})
            print(json.dumps({'stage': case, 'file': name, 'passed': row['passed'], 'chunks': row.get('chunks'),
                'seconds': row.get('measurement', {}).get('elapsed_seconds')}, ensure_ascii=False), flush=True)
            save(output/(case+'.json'), {'uploads': rows})
        passed = all(r['passed'] for r in rows)
        if case == 'dedup':
            last = rows[-1]
            passed &= ('建议保留库里较新版本（v7）' in last.get('warning', '') and
                last.get('dedup-decision', {}).get('http_status') == last.get('diff-summary', {}).get('http_status') == 200 and
                last['dedup-decision']['body']['recommendation'] == 'keep_old')
        cases[case] = {'passed': passed, 'uploads': rows}
        save(output/(case+'.json'), cases[case])
    return cases
