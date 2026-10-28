"""Read-only release checks. Deliberately never inspect container environments."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import httpx

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'data/item02-20261028'


def command(*args):
    return subprocess.check_output(list(args),cwd=ROOT,text=True,encoding='utf-8').strip()


def main():
    report={'at':datetime.now(timezone.utc).isoformat(),'systems':{},'containers':{},'source_hashes':{},'input_hashes':[]}
    with httpx.Client(trust_env=False,timeout=40) as client:
        for name,port,expected in [('main',8000,0),('item02',8060,5)]:
            system=client.get(f'http://127.0.0.1:{port}/api/v2/system'); system.raise_for_status()
            papers=client.get(f'http://127.0.0.1:{port}/api/v1/papers'); papers.raise_for_status()
            value=system.json(); count=papers.json()['total']
            report['systems'][name]={k:value[k] for k in ['api_version','model_configured','qa_mode','research_retrieval','data_class']}
            report['systems'][name]['papers']=count
            assert value['model_configured'] and value['qa_mode']=='deepseek' and count==expected
        for name,port in [('main',3000),('item02',3360)]:
            response=client.get(f'http://127.0.0.1:{port}/qa'); response.raise_for_status()
            report['systems'][name]['frontend_qa_status']=response.status_code
    for name in ['scholar-graph-backend-1','scholar-graph-frontend-1','scholar-graph-item02-backend-1','scholar-graph-item02-frontend-1']:
        state=json.loads(command('docker','inspect','--format','{{json .State}}',name))
        image=command('docker','inspect','--format','{{.Image}}',name)
        health=state.get('Health',{}).get('Status','not_configured')
        report['containers'][name]={'running':state['Running'],'health':health,'image_config_id':image}
        assert state['Running'] and (health=='healthy' or name=='scholar-graph-item02-frontend-1' and health=='not_configured')
    for project in ['scholar-graph','scholar-graph-item02']:
        dns=command('docker','exec',project+'-frontend-1','getent','hosts','backend')
        report['systems']['main' if project=='scholar-graph' else 'item02']['backend_dns']=dns
        assert dns.startswith('172.')
    paths=['backend/scholar_graph/qa_sse.py','backend/scholar_graph/vector_worker.py','backend/scholar_graph/workspace_research.py',
           'frontend/app/qa/page.tsx','frontend/components/LayoutViewer.tsx']
    for path in paths:
        service='backend' if path.startswith('backend/') else 'frontend'
        local=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
        for project in ['scholar-graph','scholar-graph-item02']:
            actual=command('docker','exec',project+'-'+service+'-1','sha256sum','/app/'+path).split()[0]
            assert actual==local,(project,path)
        report['source_hashes'][path]=local
    ingestion=json.loads((BASE/'ingestion.json').read_text(encoding='utf-8'))
    for item in ingestion['files']:
        actual=hashlib.sha256((ROOT/'pdf'/item['filename']).read_bytes()).hexdigest()
        assert actual==item['source_sha256']
        report['input_hashes'].append({'filename':item['filename'],'sha256':actual,'unchanged':True})
    report['passed']=True
    (BASE/'runtime-final.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':True,'systems':report['systems'],'source_files_matched_in_both_deployments':len(paths)},ensure_ascii=False))


if __name__=='__main__': main()
