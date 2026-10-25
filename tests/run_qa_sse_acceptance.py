"""Actual TCP SSE samples, keeping only bounded draft excerpts and validated final answers."""
import argparse
import hashlib
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import httpx
import uvicorn
from scholar_graph.api import create_app
from scholar_graph.api_repository import ApiRepository
from scholar_graph.qa import validate_answer
from scholar_graph.validation import ContractGate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['deepseek', 'fallback'], required=True)
    args = parser.parse_args()
    report = ROOT / f'tests/reports/qa-sse-{args.mode}-events.json'
    if args.mode == 'deepseek' and (not os.environ.get('DEEPSEEK_API_KEY') or not os.environ.get('DEEPSEEK_MODEL')):
        report.write_text(json.dumps({'mode': args.mode, 'status': 'skipped', 'reason': '模型环境未设置，未伪造实连。'}, ensure_ascii=False), encoding='utf-8')
        print('real_sse_status=skipped')
        return 0
    if args.mode == 'fallback':
        for name in list(os.environ):
            if any(part in name.upper() for part in ('API_KEY', 'TOKEN', 'SECRET', 'PASSWORD')):
                os.environ.pop(name)
        os.environ.pop('DEEPSEEK_MODEL', None)
    os.environ['SCHOLAR_GRAPH_QA_MODE'] = 'deepseek'  # Missing configuration exercises the actual fallback branch.
    gate = ContractGate()
    ids = json.loads((ROOT / 'data/real-model/sources.json').read_text(encoding='utf-8'))
    pid = ids['attention_id']
    source = ApiRepository(ROOT / 'data/real-model/records', gate).paper(pid)
    app = create_app(data_dir=ROOT / 'data/real-model/records')
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', log_level='critical', access_log=False))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
    thread.start()
    events, raw_tokens, token_count = [], [], 0
    result = {'mode': args.mode, 'scope': '官方Attention v7已落盘Chunk，临时真实TCP后端；非TestClient缓冲样本',
              'request': {'method': 'POST', 'path': f'/api/v1/papers/{pid}/qa/stream', 'question': 'Which optimizer?'},
              'environment': {n: '已设置' if os.environ.get(n) else '未设置' for n in
                              ('SCHOLAR_GRAPH_QA_MODE', 'DEEPSEEK_MODEL', 'DEEPSEEK_API_KEY')},
              'events': events, 'token_log_policy': '仅保留前8个真实增量原文；其余保留长度与散列，不存完整模型JSON或任何请求/思考正文。'}
    try:
        deadline = time.monotonic() + 15
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError('Temporary TCP server failed to start')
            time.sleep(.02)
        start = time.perf_counter()
        with httpx.Client(timeout=180, trust_env=False) as client:
            with client.stream('POST', f'http://127.0.0.1:{port}' + result['request']['path'],
                               json={'question': result['request']['question']}, headers={'Accept': 'text/event-stream'}) as response:
                result.update(http_status=response.status_code, content_type=response.headers.get('content-type'),
                              cache_control=response.headers.get('cache-control'), buffering=response.headers.get('x-accel-buffering'))
                fields = {}
                for line in response.iter_lines():
                    if not line:
                        if fields.get('event'):
                            data = json.loads(fields['data'])
                            row = {'id': int(fields['id']), 'event': fields['event'], 'data': data,
                                   'observed_seconds': round(time.perf_counter() - start, 6)}
                            if row['event'] == 'token':
                                token_count += 1
                                raw_tokens.append(data['delta'])
                                if token_count > 8:
                                    text = data.pop('delta')
                                    data.update(delta_omitted=True, delta_chars=len(text), delta_sha256=hashlib.sha256(text.encode()).hexdigest())
                            events.append(row)
                        fields = {}
                    elif not line.startswith(':') and ': ' in line:
                        name, value = line.split(': ', 1)
                        fields[name] = value
        result['elapsed_seconds'] = round(time.perf_counter() - start, 6)
        result['token_events'] = token_count
        result['draft_characters'] = sum(len(t) for t in raw_tokens)
        result['draft_sha256'] = hashlib.sha256(''.join(raw_tokens).encode()).hexdigest()
        finals = [e for e in events if e['event'] == 'final']
        errors = [e for e in events if e['event'] == 'error']
        result['status'] = 'failed'
        if finals:
            record = finals[0]['data']
            blocks = record['answer'].split('\n\n【证据 ')
            quotes = [blocks[0].split('\n', 1)[1]] + [b.split('\n', 1)[1] for b in blocks[1:]]
            evidence = [{'anchor': a, 'quote': q} for a,q in zip(record['anchors'], quotes, strict=True)]
            validate_answer(record, source, evidence, gate)
            tokens = [e for e in events if e['event'] == 'token']
            qa_end = next(e for e in events if e['event'] == 'node_end' and e['data']['node'] == 'qa')
            result['checks'] = {'http_sse': response.status_code == 200 and result['content_type'].startswith('text/event-stream'),
                'mode_first': events[0]['event'] == 'mode', 'done_last': events[-1]['event'] == 'done',
                'sequence': [e['id'] for e in events] == list(range(1, len(events)+1)),
                'answer_validated': not record['refused'] and bool(record['anchors']), 'no_error': not errors,
                'four_nodes': all(any(e['event']=='node_start' and e['data']['node']==n for e in events)
                                  for n in ('plan','retrieve','qa','validate')),
                'mode_correct': (bool(tokens) and tokens[0]['observed_seconds'] < qa_end['observed_seconds']) if args.mode == 'deepseek'
                                else not tokens and '回落模式、非 token 流式' in events[0]['data']['message']}
            result['status'] = 'passed' if all(result['checks'].values()) else 'failed'
            if tokens:
                result['first_token_seconds'] = tokens[0]['observed_seconds']
            result['qa_end_seconds'] = qa_end['observed_seconds']
            result['final_seconds'] = finals[0]['observed_seconds']
    except Exception as error:
        result.update(status='failed', probe_error={'type': type(error).__name__, 'message': 'SSE验收未完成；未记录异常原始正文。'})
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        listener.close()
    raw = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    key = os.environ.get('DEEPSEEK_API_KEY')
    if key and key in raw:
        raise RuntimeError('Credential safety check rejected report')
    report.write_text(raw + '\n', encoding='utf-8')
    print(json.dumps({'mode': args.mode, 'status': result['status'], 'events': len(events), 'token_events': token_count,
                      'seconds': result.get('elapsed_seconds'), 'checks': result.get('checks')}, ensure_ascii=False))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
