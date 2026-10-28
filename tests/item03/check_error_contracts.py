"""Real HTTP direction restrictions and isolated no-key application behavior."""
import json,os,sys
from pathlib import Path
import httpx
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'data/item03-20261028';sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.api import create_app
from scholar_graph.api_repository import ApiRepository
from scholar_graph.validation import ContractGate
PID='paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697'
if __name__=='__main__':
    cases=[]
    with httpx.Client(base_url='http://127.0.0.1:8080',trust_env=False,timeout=40) as client:
        for version in ['v1','v2']:
            endpoint='/api/'+version+'/papers/'+PID+('/translate' if version=='v1' else '/translation-tasks')
            response=client.post(endpoint,json={'scope':'section','target':'en','section_path':['1 Introduction']})
            assert response.status_code==422;cases.append({'case':version+'_en_section_rejected','http_status':response.status_code,'error':response.json()})
    os.environ.pop('DEEPSEEK_API_KEY',None);os.environ.pop('DEEPSEEK_MODEL',None)
    fixtures=json.loads((BASE/'protection-fixtures.json').read_text(encoding='utf-8'));pid=fixtures['english']['paper_id']
    bundle=ApiRepository(BASE/'records',ContractGate()).paper(pid)
    folder=BASE/'no-key-check';folder.mkdir(exist_ok=False)
    app=create_app(data_dir=folder);app.state.repository.store.paper(bundle)
    with TestClient(app) as client:
        response=client.post('/api/v1/papers/'+pid+'/translate',json={'scope':'abstract','target':'zh'})
        assert response.status_code==502 and 'segments' not in response.json()
        cases.append({'case':'isolated_no_key_no_fabricated_translation','http_status':502,'error':response.json()})
    (BASE/'error-contracts.json').write_text(json.dumps({'passed':True,'cases':cases},ensure_ascii=False,indent=2),encoding='utf-8');print('3 error-contract probes passed')
