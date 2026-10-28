"""Real official-file HTTP acceptance. New evidence directories never overwrite old runs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import httpx

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=('versions', 'scan', 'book'), required=True)
    parser.add_argument('--run', required=True)
    parser.add_argument('--base', default='http://127.0.0.1:8040')
    args = parser.parse_args()
    out = (ROOT / 'data/item01-20261028' / args.run).resolve()
    if not out.is_relative_to(ROOT / 'data/item01-20261028'):
        raise ValueError('Evidence directory escapes task root')
    out.mkdir(parents=True, exist_ok=False)
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'phase': args.phase,
              'mode': 'real_official_pdf_real_http_pipeline', 'passed': False, 'uploads': []}
    def save():
        (out / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    def request(client, method, url, **kw):
        response = client.request(method, url, **kw)
        response.raise_for_status()
        return response.json()
    save()
    try:
        with httpx.Client(base_url=args.base, timeout=60, trust_env=False) as client:
            listing = request(client, 'GET', '/api/v2/papers')
            report['initial_visible_papers'] = len(listing['items'])
            if args.phase == 'versions' and listing['items']:
                raise RuntimeError('Version-order test requires an initially empty library')
            names = {'versions': ['1706.03762v7.pdf', '1706.03762v1.pdf'],
                     'scan': ['1706.03762v1_img.pdf'], 'book': ['UnderstandingDeepLearning_02_09_26_C.pdf']}[args.phase]
            for name in names:
                source = ROOT / 'pdf' / name
                started = time.monotonic()
                row = {'filename': name, 'input_bytes': source.stat().st_size,
                       'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'progress': []}
                report['uploads'].append(row); save()
                with source.open('rb') as stream:
                    task = request(client, 'POST', '/api/v2/uploads', files={'files': (name, stream, 'application/pdf')})
                row['task_id'] = task['id']; save()
                print(json.dumps({'event': 'upload_submitted', 'filename': name, 'id': task['id']}), flush=True)
                previous = None
                while task['status'] in ('queued', 'running', 'cancelling'):
                    if time.monotonic() - started > 2700:
                        raise TimeoutError('Task exceeds 2700-second acceptance budget; no pass recorded')
                    time.sleep(1)
                    task = request(client, 'GET', '/api/v2/tasks/' + task['id'])
                    progress = task.get('progress')
                    if progress != previous:
                        entry = {'elapsed_seconds': round(time.monotonic()-started, 3), 'status': task['status'], 'progress': progress}
                        row['progress'].append(entry); previous = progress; save()
                        print(json.dumps({'filename': name, **entry}, ensure_ascii=False), flush=True)
                (out / (name + '.task.json')).write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding='utf-8')
                row.update(status=task['status'], elapsed_seconds=round(time.monotonic()-started, 3), error=task.get('error'))
                if task['status'] != 'completed' or not task.get('result', {}).get('succeeded'):
                    save(); raise RuntimeError('Upload did not complete; inspect preserved task result')
                pid = task['result']['succeeded'][0]['paper_id']
                view = request(client, 'GET', '/api/v2/papers/' + pid)
                row.update(paper_id=pid, physical_pages=view['paper']['page_count'])
                chunks, empty = [], []
                for page in range(1, row['physical_pages']+1):
                    reading = request(client, 'GET', f'/api/v2/papers/{pid}/reading?physical_page={page}')
                    page_chunks = reading['chunks']
                    if not page_chunks: empty.append(page)
                    if any(c['page_number'] != page for c in page_chunks):
                        raise RuntimeError('Physical page locator returned chunks from another page')
                    chunks.extend(page_chunks)
                (out / (name + '.view.json')).write_text(json.dumps(view, ensure_ascii=False, indent=2), encoding='utf-8')
                row.update(chunk_count=len(chunks), empty_physical_pages=empty,
                           all_physical_page_endpoints_accessible=True, input_sha256_unchanged=hashlib.sha256(source.read_bytes()).hexdigest() == row['sha256'])
                versions = request(client, 'GET', f'/api/v2/papers/{pid}/versions')
                (out / (name + '.versions.json')).write_text(json.dumps(versions, ensure_ascii=False, indent=2), encoding='utf-8')
                if args.phase == 'versions':
                    row['dedup_comparisons'] = len(versions)
                    if name.endswith('v7.pdf') and versions:
                        raise RuntimeError('First v7 upload was not recognized as new')
                    if name.endswith('v1.pdf'):
                        decision = versions[0]['decision']
                        row.update(recommendation=decision['recommendation'], similarity=decision['similarity'])
                        if decision['recommendation'] != 'keep_old':
                            raise RuntimeError('The older v1 upload was not advised to keep existing v7')
                save()
                print(json.dumps({'event': 'upload_verified', **{k:v for k,v in row.items() if k != 'progress'}}, ensure_ascii=False), flush=True)
            report['passed'] = all(r['status'] == 'completed' and r['input_sha256_unchanged'] for r in report['uploads'])
    except Exception as error:
        report['error'] = {'type': type(error).__name__, 'message': str(error)}
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat(); save()
    print(json.dumps({'passed': report['passed'], 'phase': args.phase, 'error': report.get('error')}, ensure_ascii=False), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
