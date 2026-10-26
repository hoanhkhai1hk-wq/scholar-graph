"""Resume network preparation only; require the official HTTP library still be empty."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import httpx
from deployment_timer import finish_timer_observation

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT/'tests/reports/final-deployment-build.json'
    original = ROOT/'tests/reports/final-deployment-build-initial-preparation.json'
    if not original.exists():
        shutil.copyfile(output,original)
    evidence = json.loads(output.read_text(encoding='utf-8'))
    root, checkout = Path(evidence['run_root']), Path(evidence['clone']['path'])
    assert httpx.get('http://127.0.0.1:8000/api/v1/papers',trust_env=False).json()['total']==0
    env = {k:v for k,v in os.environ.items() if not any(p in k.upper() for p in ('API_KEY','TOKEN','SECRET','PASSWORD'))}
    env.pop('DEEPSEEK_MODEL',None)
    env.update(SCHOLAR_GRAPH_PDF_DIR=str(ROOT/'pdf'),SCHOLAR_GRAPH_REVISION=evidence['clone']['commit'])
    compose = ['docker','compose','-p',evidence['project'],'-f','docker-compose.yml',
               '-f','services/docker-compose.acceptance.yml','-f','services/docker-compose.final-acceptance.yml']
    evidence['initial_preparation_interrupted_before_regression_or_uploads'] = True
    evidence['error_before_network_recovery'] = evidence.pop('error',None)

    def save():
        output.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    def command(label,args,timeout=10800):
        log = root/(label+'.log')
        started=time.perf_counter()
        print(json.dumps({'stage':label,'started':True}),flush=True)
        with log.open('wb') as handle:
            try:
                code=subprocess.run(compose+args,cwd=checkout,env=env,stdout=handle,stderr=subprocess.STDOUT,timeout=timeout).returncode
            except subprocess.TimeoutExpired:
                code=124
        text=log.read_text(encoding='utf-8',errors='replace')
        evidence['steps'].append({'stage':label,'exit_code':code,'elapsed_seconds':round(time.perf_counter()-started,6),
            'argv':compose+args,'log':str(log),'log_bytes':log.stat().st_size,
            'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),
            'last_lines':[re.sub(r'https?://\S+','<public-url>',line) for line in text.splitlines()[-20:]]})
        save()
        print(json.dumps({'stage':label,'exit_code':code,'seconds':evidence['steps'][-1]['elapsed_seconds']}),flush=True)
        return code,text

    copied,_=command('copy-public-range-parallel-script',['cp',str(ROOT/'tests/prepare_bge_public.py'),
                                                          'backend:/app/data/prepare_bge_public.py'])
    assert copied==0
    code,_=command('prepare-public-vector-model-range-parallel',['exec','-T','backend','python','/app/data/prepare_bge_public.py'],7200)
    if code:
        evidence.update(passed=False,error={'message':'Independent public model preparation failed; no container pass claimed'})
        save()
        return 1
    code,_=command('confirm-public-vector-model',['exec','-T','backend','/opt/vector-venv/bin/python','backend/download_bge_m3.py'],7200)
    if code:
        evidence.update(passed=False,error={'message':'Public SDK model confirmation failed'})
        save()
        return 1
    code,text=command('container-acceptance-after-model-preparation',['exec','-T','backend','python','tests/run_final_deployment_container.py'])
    rows=[]
    for line in text.splitlines():
        try: rows.append(json.loads(line))
        except ValueError: pass
    remote=next(r['report'] for r in reversed(rows) if 'report' in r)
    assert re.fullmatch(r'/app/data/final-deployment/[a-f0-9]{32}/container.json',remote)
    parent=remote.rsplit('/',1)[0]
    exported=root/'exported-after-model-preparation'
    exported.mkdir(exist_ok=False)
    for name in ('container.json','container-pytest.xml','pytest-console.txt','model-download.log','dedup.json','ocr.json','longbook.json'):
        copied,_=command('export-final-'+name.replace('.','-'),['cp','backend:'+parent+'/'+name,str(exported/name)])
        assert copied==0
    result=json.loads((exported/'container.json').read_text(encoding='utf-8'))
    result['original_probe_exit_code']=code
    finish_timer_observation(result,compose,checkout,env)
    (exported/'container-after-timer-observation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    evidence['container']=result
    evidence['source_matches_clean_clone']=all(hashlib.sha256((checkout/name).read_bytes()).hexdigest()==digest
        for name,digest in result['source_sha256'].items())
    evidence['clone']['clean_after_build_and_run']=not subprocess.check_output(['git','status','--porcelain'],cwd=checkout).strip()
    for name,target in [('container.json','final-deployment-container.json'),('container-pytest.xml','final-deployment-container-pytest.xml')]:
        shutil.copyfile(exported/name,ROOT/'tests/reports'/target)
    (ROOT/'tests/reports/final-deployment-container.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    evidence['passed']=result['passed'] and evidence['source_matches_clean_clone'] and evidence['clone']['clean_after_build_and_run']
    save()
    print(json.dumps({'passed':evidence['passed'],'report':str(output)}),flush=True)
    return int(not evidence['passed'])


if __name__=='__main__':
    raise SystemExit(main())
