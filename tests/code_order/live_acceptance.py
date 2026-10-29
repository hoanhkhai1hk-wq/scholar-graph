"""Original failing PDF, fresh parse, official prose, and real DeepSeek tasks."""
import ast
import argparse
import json
import re
import sys
import time

import httpx
from pypdf import PdfReader
from common import ROOT, BASE, PID, API, write, digest

sys.path.insert(0, str(ROOT / 'backend'))
from scholar_graph.code_layout import fenced_regions, code_ranges, join_code
from scholar_graph.translation import check_numbers, render_markdown


def poll(client, task, path):
    start = time.monotonic()
    while True:
        write(path, task)
        if task['status'] not in ['queued', 'running', 'cancelling']:
            return task
        assert time.monotonic() - start < 1200, 'Task exceeded measured 1200s acceptance limit'
        time.sleep(1)
        response = client.get('/api/v2/tasks/' + task['id'])
        response.raise_for_status()
        task = response.json()


def original_code():
    page = PdfReader(ROOT / 'data/item06-20261029/chinese-acceptance.pdf').pages[1]
    return next(fenced_regions(page.extract_text(extraction_mode='layout')))[2]


def verify_code(markdown):
    region = next(fenced_regions(markdown))[2]
    assert region == original_code(), 'Code differs from physical PDF source'
    body = re.search(r'```python\n(.*?)\n```', region, re.S)[1]
    assert '<a ' not in body
    ast.parse(body)
    namespace = {}
    # Known, authored acceptance fixture only, never arbitrary uploaded content.
    exec(compile(body, '<authored-pdf-code>', 'exec'), namespace)
    assert namespace['forward'](2) == 3
    return {'exact_source_match': True, 'python_ast_valid': True, 'forward_2': 3,
            'four_space_indent': '\n    return x + 1' in body, 'html_inside_code': False,
            'code_sha256': __import__('hashlib').sha256(region.encode()).hexdigest()}


def reading(client, pid, count):
    chunks = []
    for number in range(1, count + 1):
        response = client.get(f'/api/v2/papers/{pid}/reading', params={'physical_page': number})
        response.raise_for_status()
        chunks.extend(response.json()['chunks'])
    return chunks


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume', action='store_true', help='Verify already captured genuine tasks without repeating model calls')
    args = parser.parse_args()
    output = BASE / 'live01'
    output.mkdir(exist_ok=args.resume)
    report = json.loads((output / 'result.json').read_text(encoding='utf8')) if args.resume else {'source': 'same unchanged authored acceptance PDF; not a published paper', 'cases': []}
    if args.resume:
        report['cases'] = [r for r in report['cases'] if r['case'].startswith('fresh_upload_')]
    with httpx.Client(base_url=API, trust_env=False, timeout=300) as client:
        for file in ([] if args.resume else [ROOT / 'data/item06-20261029/chinese-acceptance.pdf', ROOT / 'pdf/1706.03762v1.pdf']):
            started = time.monotonic()
            with file.open('rb') as stream:
                response = client.post('/api/v2/uploads', files={'files': (file.name, stream, 'application/pdf')}, data={'file_count': '1'})
            response.raise_for_status()
            task = poll(client, response.json(), output / (file.stem + '-upload.json'))
            assert task['status'] == 'completed', task.get('error')
            pid = task['result']['succeeded'][0]['paper_id']
            folder = BASE / 'records/papers' / pid
            meta = json.loads((folder / 'paper-meta.json').read_text(encoding='utf8'))
            raw = json.loads((folder / 'chunks.json').read_text(encoding='utf8'))
            visible = reading(client, pid, meta['page_count'])
            assert raw == visible
            row = {'case': 'fresh_upload_' + file.stem, 'source_sha256': digest(file), 'seconds': round(time.monotonic() - started, 3),
                   'paper_id': pid, 'pages': meta['page_count'], 'chunks': len(raw), 'all_pages_readable': len({c['page_number'] for c in visible}) == meta['page_count']}
            if pid == PID:
                spans = code_ranges(raw)
                code = join_code([c['text'] for c in raw if c['chunk_id'] in spans])
                row['source_code_checks'] = verify_code(code)
                bundle = {'paper_meta': meta, 'chunks': raw}
                write(output / 'fresh-source-chunks.json', raw)
            else:
                assert any('Multi-Head Attention' in c['text'] for c in raw)
                refs = json.loads((folder / 'reference-entries.json').read_text(encoding='utf8'))
                row['multicolumn_order_changed_by_code_fix'] = False
                assert all('```' not in c['text'] and '~~~' not in c['text'] for c in raw)
                row['reference_count'] = len(refs)
            report['cases'].append(row)
            write(output / 'result.json', report)
        if args.resume:
            folder = BASE / 'records/papers' / PID
            bundle = {'paper_meta': json.loads((folder / 'paper-meta.json').read_text(encoding='utf8')),
                      'chunks': json.loads((folder / 'chunks.json').read_text(encoding='utf8'))}
        chinese_task, chinese_translation = None, None
        for label, target, from_prior in [('native-en', 'en', False), ('native-zh', 'zh', False), ('prior-zh-to-en', 'en', True)]:
            body = {'scope': 'full', 'target': target}
            if from_prior:
                body['chinese_task_id'] = chinese_task
            start = time.monotonic()
            if args.resume:
                task = json.loads((output / (label + '-task.json')).read_text(encoding='utf8'))
            else:
                response = client.post(f'/api/v2/papers/{PID}/translation-tasks', json=body)
                response.raise_for_status()
                task = poll(client, response.json(), output / (label + '-task.json'))
            assert task['status'] == 'completed', task.get('error') or task.get('result')
            value = task['result']['translation']
            assert value['metadata']['complete'] and value['metadata']['model_calls'], 'Must be a genuine new model run'
            assert value['metadata']['cache_hits'] == 0
            sources = {c['chunk_id']: c for c in bundle['chunks']}
            prior_texts = {s['source_chunk_id']: s['translated_text'] for s in chinese_translation['segments']} if from_prior else {}
            assert [s['source_chunk_id'] for s in value['segments']] == [c['chunk_id'] for c in bundle['chunks']]
            for segment in value['segments']:
                original = sources[segment['source_chunk_id']]
                assert all(segment[k] == original[k] for k in ['paper_id', 'page_number', 'section_path', 'type'])
                assert segment['source_text'] == prior_texts.get(segment['source_chunk_id'], original['text'])
                check_numbers(segment['source_text'], segment['translated_text'], segment['source_chunk_id'])
            checks = verify_code(value['markdown'])
            (output / (label + '.md')).write_text(value['markdown'], encoding='utf8')
            elapsed = sum(c['elapsed_seconds'] for c in value['metadata']['model_calls']) if args.resume else time.monotonic() - start
            report['cases'].append({'case': label, 'task_id': task['id'], 'seconds': round(elapsed, 3),
                'timing_basis': 'sum_actual_provider_call_seconds' if args.resume else 'task_wall_seconds',
                'segments': len(value['segments']), 'model_calls': len(value['metadata']['model_calls']),
                'cache_hits': 0, 'all_anchor_and_number_checks': True, 'code': checks})
            if target == 'zh':
                chinese_task = task['id']
                chinese_translation = value
            write(output / 'result.json', report)
    report['passed'] = True
    write(output / 'result.json', report)
    print(json.dumps(report, ensure_ascii=False))
