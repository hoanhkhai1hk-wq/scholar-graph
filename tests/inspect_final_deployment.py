"""Inspect built images without mounts, then restore the default daily deployment."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--daily', action='store_true')
    args = parser.parse_args()
    build = json.loads((ROOT/'tests/reports/final-deployment-build.json').read_text(encoding='utf-8'))
    checkout = Path(build['clone']['path'])
    env = {k:v for k,v in os.environ.items() if not any(p in k.upper() for p in ('API_KEY','TOKEN','SECRET','PASSWORD'))}
    env.pop('DEEPSEEK_MODEL',None)
    env['SCHOLAR_GRAPH_REVISION'] = build['clone']['commit']
    compose = ['docker','compose','-p',build['project'],'-f','docker-compose.yml']

    def run(argv):
        return subprocess.check_output(argv,cwd=checkout,env=env,text=True,encoding='utf-8',errors='replace')

    result = {'project':build['project'],'services':[]}
    if args.daily:
        started = time.perf_counter()
        result['daily_restore_output'] = run(compose+['up','-d','--wait','--wait-timeout','300'])
        result['daily_restore_seconds'] = round(time.perf_counter()-started,6)
        # Lifespan starts before health is declared; inspect its live state below.
    for name in ('backend','frontend'):
        cid = run(compose+['ps','-q',name]).strip()
        actual = json.loads(run(['docker','inspect',cid]))[0]
        image = json.loads(run(['docker','image','inspect',actual['Image']]))[0]
        if name=='backend':
            script = """import json,os,pathlib; p=pathlib.Path('/app'); private=['.env','.git','pdf','backend/.venv','data/records/papers']; bad=[k for k in os.environ if any(x in k.upper() for x in ('API_KEY','TOKEN','SECRET','PASSWORD'))]; pdf=list(p.rglob('*.pdf')); print(json.dumps({'pdf_count':len(pdf),'private_paths_present':[x for x in private if (p/x).exists()],'credential_names':bad,'passed':not pdf and not bad and not any((p/x).exists() for x in private)}))"""
            audit = json.loads(run(['docker','run','--rm','--network','none','--entrypoint','python',actual['Image'],'-c',script]))
        else:
            script = """const fs=require('fs'),path=require('path');let n=0;function walk(p){for(const e of fs.readdirSync(p,{withFileTypes:true})){const f=path.join(p,e.name);if(e.isDirectory())walk(f);else if(e.name.endsWith('.pdf'))n++;}}walk('/app');const bad=Object.keys(process.env).filter(k=>/API_KEY|TOKEN|SECRET|PASSWORD/i.test(k));const priv=['/app/.env','/app/.git','/app/pdf','/app/frontend/.env'].filter(p=>fs.existsSync(p));console.log(JSON.stringify({pdf_count:n,credential_names:bad,private_paths_present:priv,passed:n===0&&bad.length===0&&priv.length===0}));"""
            audit = json.loads(run(['docker','run','--rm','--network','none','--entrypoint','node',actual['Image'],'-e',script]))
        result['services'].append({'name':name,'container_id':cid,'image_id':actual['Image'],
            'healthy':actual['State'].get('Health',{}).get('Status')=='healthy',
            'revision':image['Config'].get('Labels',{}).get('org.opencontainers.image.revision'),
            'size_bytes':image['Size'],'ports':actual['NetworkSettings']['Ports'],
            'mounts':[{'type':m['Type'],'destination':m['Destination'],'read_write':m['RW']} for m in actual['Mounts']],
            'input_audit':audit})
    result['http_status'] = {label:httpx.get(url,timeout=30,trust_env=False).status_code for label,url in
        [('backend','http://127.0.0.1:8000/api/v1/papers?page_size=1'),('frontend','http://127.0.0.1:3000'),
         ('proxy','http://127.0.0.1:3000/api/backend/papers?page_size=1')]}
    result['scheduler'] = httpx.get('http://127.0.0.1:8000/api/v1/retrieval/tracking/status',timeout=30,trust_env=False).json()
    result['versions'] = {'python':run(compose+['exec','-T','backend','python','--version']).strip(),
        'node':run(compose+['exec','-T','frontend','node','--version']).strip(),
        'api':httpx.get('http://127.0.0.1:8000/openapi.json',trust_env=False).json()['info']['version']}
    model_code = """import pathlib,os,hashlib,json
p=pathlib.Path(os.environ['SCHOLAR_GRAPH_BGE_M3_PATH'])/'pytorch_model.bin'
h=hashlib.sha256()
with p.open('rb') as f:
 while b:=f.read(4*1024*1024): h.update(b)
print(json.dumps({'bytes':p.stat().st_size,'sha256':h.hexdigest(),'matches_fixed_revision_weights':h.hexdigest()=='b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38'}))
"""
    result['model_snapshot'] = json.loads(run(compose+['exec','-T','backend','python','-c',model_code]))
    (ROOT/'tests/reports/final-deployment-runtime.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    main()
