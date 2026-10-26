"""Real default HTTP factories, official PDF, and real unreachable TCP fallback."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import unquote
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
import httpx
from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.validation import ContractGate


def main():
    for key in list(os.environ):
        if any(s in key.upper() for s in ('API_KEY','TOKEN','SECRET','PASSWORD')):os.environ.pop(key)
    os.environ.pop('DEEPSEEK_MODEL',None)
    os.environ.update(SCHOLAR_GRAPH_TRACKING_ENABLED='false',SCHOLAR_GRAPH_DEDUP_MODE='off',
        SCHOLAR_GRAPH_RETRIEVAL_MODE='lexical',SCHOLAR_GRAPH_QA_MODE='extractive',
        SCHOLAR_GRAPH_GROBID_ENABLED='true')
    source=ROOT/'pdf/1706.03762v7.pdf'
    raw=source.read_bytes();digest=hashlib.sha256(raw).hexdigest();pid='paper-'+digest
    run=ROOT/'data/grobid-default-live'/uuid4().hex;run.mkdir(parents=True)
    report={'input_kind':'官方 pdf/ 真文件','file':source.name,'bytes':len(raw),'sha256':digest,
        'run_root':str(run),'credentials':'未设置','groups':{}}
    report['source_revision']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    files=['pipeline.py','grobid.py','grobid_enrichment.py','parse_provenance.py','api.py','api_uploads.py','arxiv_fetch.py']
    report['source_sha256']={name:hashlib.sha256((ROOT/'backend/scholar_graph'/name).read_bytes()).hexdigest() for name in files}
    output=ROOT/'tests/reports/grobid-default-path-live.json'
    report['passed']=False
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    service='http://127.0.0.1:8070'
    with httpx.Client(trust_env=False,timeout=10) as client:
        report['service']={'alive':client.get(service+'/api/isalive').text,
            'version':client.get(service+'/api/version').json()}
    bundles={}
    # A bound, non-listening real TCP socket guarantees no other service steals
    # the failure endpoint. This is a real connection refusal, not a mock HTTP.
    with socket.socket() as unavailable:
        unavailable.bind(('127.0.0.1',0))
        endpoints={'enabled':service,'unreachable':'http://127.0.0.1:'+str(unavailable.getsockname()[1])}
        for group,url in endpoints.items():
            os.environ['GROBID_URL']=url
            root=run/group
            app=create_app(data_dir=root)
            assert not (root/'papers').exists()
            with TestClient(app) as client:
                assert client.get('/api/v1/papers/'+pid+'/parse-status').status_code==404
                started=time.perf_counter()
                response=client.post('/api/v1/papers',files={'file':(source.name,raw,'application/pdf')})
                elapsed=round(time.perf_counter()-started,6)
                trace=json.loads(unquote(response.headers.get('X-ScholarGraph-Parse-Meta','{}')))
                bundle=app.state.repository.paper(pid) if response.status_code==201 else None
                if bundle:ContractGate().bundle(bundle)
                status=client.get('/api/v1/papers/'+pid+'/parse-status')
                detail=client.get('/api/v1/papers/'+pid)
                file=client.get('/api/v1/papers/'+pid+'/file')
                full_trace=json.loads((root/'jobs'/trace['job_id']/'parse-metadata.json').read_text(encoding='utf-8')) if trace else None
                expected='mineru+grobid' if group=='enabled' else 'mineru-fallback'
                checks={'http_201':response.status_code==201,'parse_completed':status.json().get('status')=='completed',
                    'real_chunks':bool(bundle and bundle['chunks']),'schema_and_anchor_gate':bundle is not None,
                    'expected_method':trace.get('method')==expected,'actually_attempted':trace.get('grobid_attempted') is True,
                    'detail_method_persisted':detail.status_code==200 and json.loads(unquote(detail.headers.get('X-ScholarGraph-Parse-Meta','{}'))).get('method')==expected,
                    'original_pdf_hash':file.status_code==200 and hashlib.sha256(file.content).hexdigest()==digest}
                if group=='enabled':checks['enhanced_fields']=bool(trace.get('paper_fields') or trace.get('references_enriched'))
                else:checks['unavailable_reason']=trace.get('grobid_error',{}).get('details',{}).get('failure_kind')=='unavailable'
                report['groups'][group]={'http_status':response.status_code,'elapsed_seconds':elapsed,
                    'paper_meta':response.json(),'parse_metadata':trace,'full_parse_metadata':full_trace,
                    'parse_status':status.json(),'checks':checks,'passed':all(checks.values()),
                    'counts':{key:len(bundle[key]) for key in ('chunks','reference_entries','citation_links')} if bundle else {},
                    'reference_samples':bundle['reference_entries'][:3] if bundle else []}
                bundles[group]=bundle
                output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({'group':group,'passed':report['groups'][group]['passed'],'seconds':elapsed,
                'method':trace.get('method'),'counts':report['groups'][group]['counts']},ensure_ascii=False),flush=True)
    report['mineru_chunks_identical']=bundles['enabled']['chunks']==bundles['unreachable']['chunks']
    report['reference_changes']=[{'ref_id':a['ref_id'],'fields':[k for k in a if a[k]!=b[k]]}
        for a,b in zip(bundles['enabled']['reference_entries'],bundles['unreachable']['reference_entries'],strict=True) if a!=b]
    report['passed']=all(g['passed'] for g in report['groups'].values()) and report['mineru_chunks_identical']
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'report':str(output)},ensure_ascii=False),flush=True)
    return int(not report['passed'])


if __name__=='__main__':
    raise SystemExit(main())
