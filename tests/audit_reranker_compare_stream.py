"""Deterministic acceptance audit; no model calls or credentials in output."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.qa import validate_answer
from scholar_graph.qa_compare import validate_comparison
from scholar_graph.validation import ContractGate
from run_reranker_compare_stream_acceptance import check_records

BASE='9f30f089548d4211445b132deab30ca1efc87a0b'


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True,encoding='utf-8').strip()


def audit():
    checks={}
    live=json.loads((ROOT/'tests/reports/reranker-compare-stream-live.json').read_text(encoding='utf-8'))
    bench=json.loads((ROOT/'tests/reports/reranker-top10-benchmark.json').read_text(encoding='utf-8'))
    ids=json.loads((ROOT/'data/real-model/sources.json').read_text(encoding='utf-8'))
    repo=ApiRepository(ROOT/'data/real-model/records',ContractGate())
    pids=[ids['attention_id'],ids['bert_id']]
    bundles=[repo.paper(pid) for pid in pids]
    for name,key in [('1706.03762v7.pdf','attention_id'),('N19-1423.pdf','bert_id')]:
        checks['official_file_'+key]=hashlib.sha256((ROOT/'pdf'/name).read_bytes()).hexdigest()==repo.paper(ids[key])['paper_meta']['file_hash']
    for path,digest in live['source_sha256_lf'].items():
        checks['source_'+path]=hashlib.sha256((ROOT/path).read_text(encoding='utf-8').encode()).hexdigest()==digest
    checks['benchmark_worker_source']=bench['worker_source_sha256_lf']==hashlib.sha256(
        (ROOT/'backend/scholar_graph/vector_worker.py').read_text(encoding='utf-8').encode()).hexdigest()
    reranks=[]
    checks['six_cases_present']=[row['case'] for row in live['cases']]==[1,2,3,4,5,6]
    for i,row in enumerate(live['cases']):
        value=row['result'];multi=i==5
        checks[f'qa_{i+1}']=row['http_status']==200 and all(check_records(value,multi,i,repo,pids).values())
        if not multi:
            parts=value['answer'].split('\n\n【证据 ')
            quotes=[parts[0].split('\n',1)[1]]+[b.split('\n',1)[1] for b in parts[1:]]
            evidence=[{'anchor':a,'quote':q} for a,q in zip(value['anchors'],quotes,strict=True)]
            validate_answer(value,bundles[0],evidence,repo.gate)
        meta=row['metadata']
        checks[f'qa_{i+1}_actual_hybrid']=meta.get('method')=='hybrid' and bool(meta.get('retrieval'))
        for n,info in enumerate(meta.get('retrieval',[])):
            rerank=info['rerank'];reranks.append(rerank)
            checks[f'qa_{i+1}_retrieval_{n}']=info['vector_status']=='READY' and info.get('ranking_method') in ('reranked','rrf')
            checks[f'qa_{i+1}_top_ten_{n}']=rerank.get('candidate_count',0)<=10
            if info['ranking_method']=='reranked':
                checks[f'qa_{i+1}_honest_{n}']=rerank['method']=='bge-reranker-large' and rerank['worker_seconds']<=5
            else:
                checks[f'qa_{i+1}_honest_{n}']=rerank['method']=='rrf' and bool(info['fallback_reason'])
    checks['two_complete_benchmarks']=len(bench['samples'])==2 and all(s['score_count']==10 and s['scores_valid'] for s in bench['samples'])
    checks['two_streams_present']=len(live['streams'])==2
    for row in live['streams']:
        events=row['events'];mode=row['mode']
        final=next(e['data'] for e in events if e['event']=='final')
        validate_comparison(final,bundles,repo.gate)
        checks['stream_'+mode]=row['passed'] and events[-1]['event']=='done' and events[-1]['data']['verified'] is True
        tokens=[e for e in events if e['event']=='token']
        checks['stream_draft_'+mode]=(bool(tokens) and all(e['data']['verified'] is False and 'delta' not in e['data'] for e in tokens)) if mode=='deepseek' else not tokens
        checks['stream_sequence_'+mode]=[e['id'] for e in events]==list(range(1,len(events)+1))
        metadata=events[-1]['data']['metadata']
        if mode=='deepseek':
            calls=metadata['model_calls']
            checks['stream_real_calls']=len(calls)>=2 and all(c['provider']=='deepseek' and c['status']=='succeeded' and c['total_tokens']>0 for c in calls)
            checks['stream_real_tools']=bool(metadata['tool_calls']) and all(c['origin']=='model_function_call' for c in metadata['tool_calls'])
        else:
            checks['stream_no_key_no_calls']=not metadata['model_calls'] and not metadata['tool_calls'] and events[-1]['data']['token_streaming'] is False
    suites={}
    for layer in ('fast','full'):
        root=ET.parse(ROOT/f'tests/reports/reranker-compare-stream-{layer}.xml').getroot()
        suite=root if root.tag=='testsuite' else root.find('testsuite')
        suites[layer]={k:int(suite.attrib[k]) for k in ('tests','failures','errors','skipped')}
        suites[layer]['passed']=suites[layer]['tests']-sum(suites[layer][k] for k in ('failures','errors','skipped'))
        checks['regression_'+layer]=suites[layer]['failures']==suites[layer]['errors']==0
        if layer=='full':
            for name in ('test_http_real_paddleocr_fallback','test_actual_paddleocr_scanned_pdf',
                         'test_real_local_bge_m3_dense_sparse_chroma','test_official_541_page_longbook_full_layer'):
                cases=[t for t in suite.iter('testcase') if t.attrib['name']==name]
                checks['full_actual_'+name]=len(cases)==1 and all(cases[0].find(t) is None for t in ('failure','error','skipped'))
    checks['five_no_key_skips_retained']=suites['full']['skipped']==5
    checks['full_count_complete']=suites['full']['tests']>=648
    checks['fast_count_complete']=suites['fast']['tests']>=187
    previous=ET.parse(ROOT/'tests/reports/reranker-compare-stream-before-route-count-fix-full.xml').getroot()
    failures=[t for t in previous.iter('testcase') if t.find('failure') is not None]
    checks['first_regression_failure_preserved']=len(failures)==1 and failures[0].attrib['name']=='test_nineteen_business_routes_including_module_six'
    prior=ROOT/live['initial_transport_probe']['path']
    # Git may convert CRLF on Windows checkout. Compare canonical UTF-8/LF text;
    # the initial Windows raw-byte digest remains separate forensic metadata.
    checks['first_transport_probe_preserved']=hashlib.sha256(prior.read_text(encoding='utf-8').encode('utf-8')).hexdigest()==live['initial_transport_probe']['sha256_lf']
    markdown=(ROOT/'tests/reports/reranker-compare-stream-acceptance.md').read_text(encoding='utf-8')
    checks['report_completed']='{{' not in markdown
    protected=git('diff',BASE,'--name-only','--','contracts/','frontend/','docs/','prompts/','experiments/','test-records/')
    checks['protected_paths_unchanged']=not protected
    checks['official_pdf_ignored']=git('check-ignore','pdf/1706.03762v7.pdf')=='pdf/1706.03762v7.pdf'
    changed=git('diff',BASE,'--name-only').splitlines()
    new=git('ls-files','--others','--exclude-standard').splitlines()
    checks['scope_only_backend_tests']=all(p.startswith(('backend/','tests/')) for p in changed+new)
    key=os.environ.get('DEEPSEEK_API_KEY')
    checks['credential_scan']='not-set' if not key else all(key.encode() not in (ROOT/p).read_bytes() for p in set(changed+new) if (ROOT/p).is_file())
    # A not-set credential scan is explicitly not counted as a successful opaque-key check.
    result={'checks':checks,'passed':all(v is True for v in checks.values()),'baseline':BASE,
        'head':git('rev-parse','HEAD'),'regression':suites,'official_cases_passed':sum(r['passed'] for r in live['cases']),
        'precision_accepted_calls':sum(r['method']=='bge-reranker-large' for r in reranks),
        'rrf_fallback_calls':sum(r['method']=='rrf' for r in reranks),
        'contract_schema_count':len(list((ROOT/'contracts').rglob('*.schema.json'))),
        'new_optional_transport_metadata':['ranking_method','fallback_reasons','retrieval[].ranking_method','retrieval[].fallback_reason','rerank.cold_start','rerank.startup','mode.draft_verified','mode.final_verified','done.verified','done.answer_format']}
    raw=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
    if key and key in raw:
        raise RuntimeError('Credential safety check rejected audit')
    (ROOT/'tests/reports/reranker-compare-stream-audit.json').write_text(raw+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    raise SystemExit(audit())
