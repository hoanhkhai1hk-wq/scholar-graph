"""Real endpoint/model acceptance using the already parsed official Attention PDF.

Only bounded paired samples, hashes and allowlisted call metadata enter Git.
Complete endpoint responses stay under ignored data/. Credentials stay in env.
"""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.translation import protect, used_terms


def persist(path, value):
    raw = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    key = os.environ.get('DEEPSEEK_API_KEY')
    if key and key in raw:
        raise RuntimeError('Credential safety check rejected report')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full', action='store_true', help='Also translate all 175 stored Chunks.')
    args = parser.parse_args()
    path = ROOT / 'tests/reports/translation-live-results.json'
    result = {'source': '官方 pdf/ 真文件 1706.03762v7.pdf，复用已解析Chunk，不重新解析PDF',
              'baseline': '349369388b31033dc624ace815b9189a0569b4e4',
              'environment': {n: '已设置' if os.environ.get(n) else '未设置'
                              for n in ('DEEPSEEK_API_KEY', 'DEEPSEEK_MODEL')}, 'runs': []}
    if path.is_file():
        result['runs'] = json.loads(path.read_text(encoding='utf-8')).get('runs', [])
    if not os.environ.get('DEEPSEEK_API_KEY') or not os.environ.get('DEEPSEEK_MODEL'):
        result['runs'].append({'status': 'skipped', 'reason': '模型环境未设置，未生成译文。'})
        persist(path, result)
        print('translation_live=skipped')
        return 0
    app = create_app(data_dir=ROOT / 'data/real-model/records')
    pid = json.loads((ROOT / 'data/real-model/sources.json').read_text(encoding='utf-8'))['attention_id']
    bundle = app.state.repository.paper(pid)
    pdf = ROOT / 'pdf/1706.03762v7.pdf'
    with pdf.open('rb') as file:
        digest = hashlib.file_digest(file, 'sha256').hexdigest()
    if digest != bundle['paper_meta']['file_hash']:
        raise RuntimeError('Official PDF does not match parsed source')
    result.update(paper_id=pid, pdf_sha256=digest, source_chunks=len(bundle['chunks']))
    requests = [{'scope': 'abstract', 'target': 'zh'},
                {'scope': 'section', 'target': 'zh', 'section_path': ['1 Introduction']}]
    if args.full:
        requests.append({'scope': 'full', 'target': 'zh'})
    for previous in result['runs']:
        if len(previous.get('cases', [])) < 3 and previous.get('status') == 'failed':
            previous['incomplete_note'] = '会话中断，未记录完整三项；不计为通过。'
    run = {'status': 'running', 'cases': [], 'implementation_sha256': {
        p: hashlib.sha256((ROOT / p).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in (
            'backend/scholar_graph/translation.py', 'backend/scholar_graph/translation_routes.py',
            'backend/scholar_graph/deepseek_client.py')}}
    result['runs'].append(run)
    with TestClient(app) as client:
        for body in requests:
            case = {'request': body, 'status': 'running'}
            run['cases'].append(case)
            persist(path, result)
            start = time.perf_counter()
            response = client.post(f'/api/v1/papers/{pid}/translate', json=body)
            case.update(http_status=response.status_code,
                        elapsed_seconds=round(time.perf_counter() - start, 6), status='failed')
            value = response.json()
            if response.status_code == 200:
                persist(ROOT / f'data/translation-acceptance/{body["scope"]}-response.json', value)
                sources = {c['chunk_id']: c for c in bundle['chunks']}
                segments = value['segments']
                ids = [s['source_chunk_id'] for s in segments]
                checks = {'one_to_one': len(ids) == len(set(ids)), 'real_source_anchors': all(
                    s['source_chunk_id'] in sources and s['source_text'] == sources[s['source_chunk_id']]['text']
                    and all(s[k] == sources[s['source_chunk_id']][k] for k in ('paper_id','page_number','section_path','type'))
                    for s in segments), 'nonempty': bool(segments) and all(s['translated_text'].strip() for s in segments),
                    'full_coverage': ids == [c['chunk_id'] for c in bundle['chunks']] if body['scope']=='full' else True,
                    'markdown_alignment': all(f'<a id="{cid}"></a>' in value['markdown'] for cid in ids) if body['scope']=='full' else value['markdown'] is None,
                    'terminology': all(all(target.casefold() in s['translated_text'].casefold()
                        for target in used_terms(protect(s['source_text'], formula=s['type']=='formula')[0],
                                                 value['metadata']['terminology']).values()) for s in segments),
                    'actual_model': bool(value['metadata']['model_calls']) and all(
                        c['provider']=='deepseek' and c['status']=='succeeded' for c in value['metadata']['model_calls'])}
                # Exactly one paragraph from the abstract/introduction, not complete raw protocol bodies.
                sample = next((s for s in segments if s['type']=='text' and len(s['source_text']) > 250), segments[0])
                case.update(status='passed' if all(checks.values()) else 'failed', checks=checks,
                    segments=len(segments), metadata=value['metadata'],
                    sample=sample if body['scope']!='full' else None,
                    markdown_characters=len(value['markdown'] or ''),
                    manifest=[{'source_chunk_id': s['source_chunk_id'], 'page_number': s['page_number'],
                               'source_sha256': hashlib.sha256(s['source_text'].encode()).hexdigest(),
                               'translation_sha256': hashlib.sha256(s['translated_text'].encode()).hexdigest()}
                              for s in segments])
            else:
                case['error'] = value
            persist(path, result)
            print(json.dumps({k: case.get(k) for k in ('request','status','http_status','segments','elapsed_seconds','error')}, ensure_ascii=False))
    run['status'] = 'passed' if all(c['status']=='passed' for c in run['cases']) else 'failed'
    persist(path, result)
    return 0 if run['status']=='passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
