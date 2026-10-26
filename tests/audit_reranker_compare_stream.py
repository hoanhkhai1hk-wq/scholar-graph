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
    suites={}
    for layer in ('fast','full'):
        root=ET.parse(ROOT/f'tests/reports/reranker-compare-stream-{layer}.xml').getroot()
        suite=root if root.tag=='testsuite' else root.find('testsuite')
        suites[layer]={k:int(suite.attrib[k]) for k in ('tests','failures','errors','skipped')}
        suites[layer]['passed']=suites[layer]['tests']-sum(suites[layer][k] for k in ('failures','errors','skipped'))
        checks['regression_'+layer]=suites[layer]['failures']==suites[layer]['errors']==0
    checks['five_no_key_skips_retained']=suites['full']['skipped']==5
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
