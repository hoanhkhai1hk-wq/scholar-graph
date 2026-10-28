"""Post-restart checks; secret configuration is recorded only as booleans elsewhere."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import httpx

ROOT=Path(__file__).resolve().parents[2]; BASE=ROOT/'data/item01-20261028'
V1='paper-0a9bff1be3575cf9fe26a4a3d3a9175bc791ecec90de8b9deba4cff75d2b9476'
V7='paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697'
BOOK='paper-f8237d393163900fa8e43210e680a3f987b45ccac7750b372e156fae3df0bf32'

def main():
    result={'at':datetime.now(timezone.utc).isoformat(),'passed':False,'checks':{}}
    expected=runpy.run_path(str(ROOT/'tests/item01/check_formulas.py'),run_name='fixture')['EXPECTED']
    with httpx.Client(trust_env=False,timeout=60) as c:
        def get(base,path):
            r=c.get(base+path); r.raise_for_status(); return r.json()
        iso='http://127.0.0.1:8040/api/v2'; main='http://127.0.0.1:8000/api/v2'
        papers=get(iso,'/papers'); ids={x['paper']['id'] for x in papers['items']}
        result['isolated_visible_papers']=papers['total']; result['checks']['six_test_papers_persisted']=papers['total']==6
        result['checks']['both_versions_persisted']={V1,V7}<=ids
        versions=get(iso,f'/papers/{V1}/versions'); result['version_history_count']=len(versions[0]['history'])
        result['checks']['version_choice_and_history_persisted']=versions[0]['selection']['choice']=='keep_both' and len(versions[0]['history'])>=3
        formulas=get(iso,f'/papers/{V1}/formulas')['items']
        result['checks']['six_source_corrections_persisted']=len(formulas)==6 and all(
            x['status']=='corrected_from_source' and x['latex']==expected[x['region_id']][1] and x.get('recognized_latex') for x in formulas)
        reading=get(iso,f'/papers/{BOOK}/reading?physical_page=541&include_navigation=false')
        result['checks']['last_page_after_restart']=reading['page_number']==541 and len(reading['chunks'])==27 and reading['total_chunks']==6859
        result['main_visible_papers']=get(main,'/papers')['total']
        result['checks']['main_library_still_empty']=result['main_visible_papers']==0
        result['checks']['site_icon_http_200']=c.get('http://127.0.0.1:3000/icon.svg').status_code==200
    result['images']={name:subprocess.check_output(['docker','image','inspect',name,'--format','{{.Id}}'],text=True).strip()
                      for name in ['scholar-graph-backend:item01-20261028','scholar-graph-frontend:item01-20261028']}
    cache=ROOT/'data/repair-ocr-model-smoke/models/paddlex'
    files={name:cache/'official_models'/name/'inference.pdiparams' for name in
           ['en_PP-OCRv5_mobile_rec','PP-OCRv5_mobile_det','PP-LCNet_x0_25_textline_ori','PP-DocLayout-S']}
    files['PP-FormulaNet-S']=cache/'item01-formula/PP-FormulaNet-S_infer/inference.pdiparams'
    local={k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in files.items()}
    code="from pathlib import Path; import json,hashlib; p=Path('/app/data/paddle-models/official_models'); print(json.dumps({d.name:hashlib.sha256((d/'inference.pdiparams').read_bytes()).hexdigest() for d in p.iterdir()}))"
    deployed=json.loads(subprocess.check_output(['docker','compose','exec','-T','backend','python','-c',code],cwd=ROOT,text=True))
    result['checks']['five_public_model_weights_match']=all(deployed.get(k)==v for k,v in local.items())
    result['public_model_sha256']=local
    result['passed']=all(result['checks'].values())
    with (BASE/'delivery-check-final.json').open('x',encoding='utf-8') as f: json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__': raise SystemExit(main())
