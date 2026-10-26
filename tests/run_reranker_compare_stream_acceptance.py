"""Official six questions + real TCP comparison SSE, with credential-free local reranking."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
from urllib.parse import unquote
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
import httpx
import uvicorn
from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.api_repository import ApiRepository
from scholar_graph.qa_compare import validate_comparison
from scholar_graph.qa_retrieval import qa_retriever
from scholar_graph.rerank_worker import resident_worker, close_workers
from scholar_graph.validation import ContractGate
from run_real_model_acceptance import QUESTIONS

REPORT = ROOT/'tests/reports/reranker-compare-stream-live.json'


def persist(result):
    raw = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    key = os.environ.get('DEEPSEEK_API_KEY')
    if key and key in raw:
        raise RuntimeError('Credential safety check rejected report')
    REPORT.write_text(raw+'\n', encoding='utf-8')


def check_records(value, multi, question_index, repo, ids):
    records = value['per_paper'] if multi else [value]
    bundles = [repo.paper(pid) for pid in ids]
    if multi:
        validate_comparison(value, bundles, repo.gate)
    for record in records:
        repo.gate.record('QAAnswer', record)
        for anchor in record['anchors']:
            repo.gate.anchor(anchor, bundles)
    text = ' '.join(r['answer'] for r in records).casefold()
    needles = [('aidan','toronto'), ('0.9','0.98'), ('8','p100'), ('28.4','26.36'), ('ba','kiros','hinton','2016')]
    checks = {word: word in text for word in needles[question_index]} if not multi else {
        'encoder': 'encoder' in text, 'bidirectional': 'bidirectional' in text,
        'decoder_or_encoder_stack': 'decoder' in text or 'encoder stack' in text, 'vaswani': 'vaswani' in text}
    checks['anchors_and_answer'] = all(r['anchors'] and not r['refused'] for r in records)
    if question_index in (1,2,3):
        checks['numeric'] = all(r['numeric_fact_check']['status'] == 'passed' and
            all(c['evidence'] for c in r['numeric_fact_check']['checks'] if c['status'] == 'passed') for r in records)
    return checks


def stream_sample(app, ids, mode):
    # Only metadata, hashes of unverified deltas and validated public-paper answers survive.
    listener = socket.socket(); listener.bind(('127.0.0.1',0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', log_level='critical', access_log=False))
    thread = threading.Thread(target=server.run, kwargs={'sockets':[listener]}, daemon=True)
    thread.start()
    row = {'mode': mode, 'request': {'path':'/api/v1/compare/stream', 'paper_ids':ids,
        'question': QUESTIONS[5] if mode == 'deepseek' else 'Which optimizer?'}, 'events': [], 'passed':False}
    try:
        deadline = time.monotonic()+15
        while not server.started:
            if not thread.is_alive() or time.monotonic()>deadline:
                raise RuntimeError('Temporary TCP server did not start')
            time.sleep(.02)
        started = time.perf_counter()
        with httpx.Client(timeout=600, trust_env=False) as client:
            with client.stream('POST', f'http://127.0.0.1:{port}/api/v1/compare/stream',
                    json={'paper_ids':ids,'question':row['request']['question']}) as response:
                row.update(http_status=response.status_code, content_type=response.headers.get('content-type'))
                fields = {}
                for line in response.iter_lines():
                    if not line:
                        if fields.get('event'):
                            data = json.loads(fields['data'])
                            if fields['event']=='token':
                                text = data.pop('delta')
                                data.update(delta_chars=len(text),delta_sha256=hashlib.sha256(text.encode()).hexdigest())
                            row['events'].append({'id':int(fields['id']),'event':fields['event'],'data':data,
                                'observed_seconds':round(time.perf_counter()-started,6)})
                        fields = {}
                    elif not line.startswith(':') and ': ' in line:
                        key, value = line.split(': ',1); fields[key]=value
        row['elapsed_seconds'] = round(time.perf_counter()-started,6)
        events = row['events']
        finals = [e for e in events if e['event']=='final']
        tokens = [e for e in events if e['event']=='token']
        errors = [e for e in events if e['event']=='error']
        checks = {'http_sse':row['http_status']==200 and row['content_type'].startswith('text/event-stream'),
            'final_exists':len(finals)==1, 'no_error':not errors,
            'done_last':bool(events) and events[-1]['event']=='done',
            'sequence':[e['id'] for e in events]==list(range(1,len(events)+1))}
        if finals:
            validate_comparison(finals[0]['data'], [app.state.repository.paper(pid) for pid in ids], app.state.repository.gate)
            checks['validated_final'] = events[-1]['data'].get('verified') is True
            checks['answers_not_refused'] = all(not r['refused'] and r['anchors'] for r in finals[0]['data']['per_paper'])
        if mode=='deepseek':
            checks['unverified_drafts'] = bool(tokens) and all(e['data']['verified'] is False for e in tokens)
            ends = [e for e in events if e['event']=='node_start' and e['data']['node']=='validate']
            checks['delta_before_validation'] = bool(tokens and ends) and tokens[0]['id']<ends[0]['id']
        else:
            modes = [e['data'] for e in events if e['event']=='mode']
            checks['no_fake_tokens'] = not tokens and modes[-1]['token_streaming'] is False
            checks['fallback_label'] = '回落模式、非 token 流式' in modes[-1]['message']
        row.update(checks=checks,passed=all(checks.values()),token_events=len(tokens))
    except Exception as error:
        row['probe_error'] = {'type':type(error).__name__, 'message':'探针失败，未保存异常正文。'}
    finally:
        server.should_exit=True; thread.join(timeout=15); listener.close()
    return row


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--without-model',action='store_true')
    args=parser.parse_args()
    result={'baseline':'9f30f089548d4211445b132deab30ca1efc87a0b',
        'scope':'官方 pdf/ 真文件已落盘Attention v7与BERT；真实本地模型/真实DeepSeek，未重新解析PDF。',
        'environment':{k:'已设置' if os.environ.get(k) else '未设置' for k in
            ('DEEPSEEK_API_KEY','DEEPSEEK_MODEL','SCHOLAR_GRAPH_QA_MODE')}, 'cases':[], 'streams':[]}
    os.environ.update(SCHOLAR_GRAPH_QA_MODE='deepseek',SCHOLAR_GRAPH_QA_RETRIEVAL_MODE='hybrid',
        SCHOLAR_GRAPH_QA_RERANKER='auto',SCHOLAR_GRAPH_TRACKING_ENABLED='false', SCHOLAR_GRAPH_GROBID_ENABLED='false')
    folder=ROOT/'data/reranker-compare-stream'/uuid4().hex
    folder.mkdir(parents=True)
    result['isolated_data_dir']=str(folder.relative_to(ROOT)).replace('\\','/')
    source_ids=json.loads((ROOT/'data/real-model/sources.json').read_text(encoding='utf-8'))
    ids=[source_ids['attention_id'],source_ids['bert_id']]
    source=ApiRepository(ROOT/'data/real-model/records',ContractGate())
    app=create_app(data_dir=folder/'records')
    for pid in ids:
        app.state.repository.store.paper(source.paper(pid))
    retriever=qa_retriever(app.state.repository)
    reranker=retriever.reranker
    # The first real request includes cold initialization in its five-second budget.
    chunks=source.paper(ids[0])['chunks'][:10]
    order,meta=reranker.order('Which optimizer?',chunks)
    result['cold_rerank']={'accepted':order is not None,'metadata':meta}
    started=time.perf_counter()
    result['explicit_prewarm']=resident_worker(reranker.python,reranker.path).prepare(timeout=90)
    result['explicit_prewarm']['wait_seconds']=time.perf_counter()-started
    order,meta=reranker.order('Which optimizer?',chunks)
    result['warm_benchmark']={'accepted':order is not None,'metadata':meta}
    persist(result)
    print(json.dumps({'phase':'benchmark','cold':result['cold_rerank']['metadata'],'warm':meta}),flush=True)
    configured=bool(os.environ.get('DEEPSEEK_API_KEY') and os.environ.get('DEEPSEEK_MODEL')) and not args.without_model
    result['real_model_status']='executed' if configured else 'skipped: environment unavailable or --without-model'
    if configured:
        client=TestClient(app,raise_server_exceptions=False)
        for n,question in enumerate(QUESTIONS):
            multi=n==5; started=time.perf_counter()
            response=client.post('/api/v1/compare' if multi else f'/api/v1/papers/{ids[0]}/qa',
                json={'question':question,**({'paper_ids':ids} if multi else {})})
            meta=json.loads(unquote(response.headers.get('X-ScholarGraph-QA-Meta','%7B%7D')))
            agent=json.loads(unquote(response.headers.get('X-ScholarGraph-Agent-Meta','%7B%7D')))
            value=response.json()
            row={'case':n+1,'question':question,'http_status':response.status_code,
                'elapsed_seconds':round(time.perf_counter()-started,6),'metadata':meta,'agent':agent,'result':value,'passed':False}
            if response.status_code==200:
                checks=check_records(value,multi,n,app.state.repository,ids)
                checks['actual_hybrid']=meta.get('method')=='hybrid' and bool(meta.get('retrieval')) and all(r['vector_status']=='READY' for r in meta['retrieval'])
                checks['top_ten_bounded']=all(r['rerank'].get('candidate_count',0)<=10 for r in meta.get('retrieval',[]))
                row.update(checks=checks,passed=all(checks.values()))
            result['cases'].append(row);persist(result)
            print(json.dumps({'case':n+1,'passed':row['passed'],'http_status':response.status_code,
                'method':meta.get('method'),'ranking_method':meta.get('ranking_method'),'seconds':row['elapsed_seconds']}),flush=True)
        result['streams'].append(stream_sample(app,ids,'deepseek'));persist(result)
        print(json.dumps({'phase':'deepseek_stream','passed':result['streams'][-1]['passed'],
            'seconds':result['streams'][-1].get('elapsed_seconds'),'token_events':result['streams'][-1].get('token_events')}),flush=True)
    # Genuine no-key/no-vector transport smoke; no secrets are written or restored to disk.
    saved={k:os.environ.pop(k,None) for k in ('DEEPSEEK_API_KEY','DEEPSEEK_MODEL')}
    os.environ['SCHOLAR_GRAPH_QA_RETRIEVAL_MODE']='lexical'
    result['streams'].append(stream_sample(app,ids,'no-key-no-vector'))
    for k,v in saved.items():
        if v is not None:
            os.environ[k]=v
    result['source_sha256_lf']={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_text(encoding='utf-8').encode()).hexdigest()
        for p in [ROOT/'backend/scholar_graph'/name for name in
            ('qa_retrieval.py','rerank_worker.py','vector_worker.py','qa_sse.py','qa_routes.py','orchestration.py')]}
    persist(result);close_workers()
    summary={'six_passed':sum(r['passed'] for r in result['cases']),
        'streams_passed':sum(r['passed'] for r in result['streams'])}
    print(json.dumps(summary),flush=True)
    return int((configured and summary['six_passed']!=6) or not all(r['passed'] for r in result['streams']))


if __name__=='__main__':
    raise SystemExit(main())
