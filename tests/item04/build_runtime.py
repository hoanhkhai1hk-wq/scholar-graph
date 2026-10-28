"""Reuse verified item-three dependencies; copy only source/build artifacts, no keys/PDFs."""
import argparse
import json
import shutil
import subprocess
import time
from common import ROOT,BASE,write,digest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('service',choices=['frontend','backend']);p.add_argument('--run',required=True);a=p.parse_args()
    context=BASE/a.run;context.mkdir(exist_ok=False)
    if a.service=='frontend':
        assert (ROOT/'frontend/.next/BUILD_ID').is_file(),'Run npm --prefix frontend run build first'
        shutil.copytree(ROOT/'frontend/.next',context/'.next',ignore=shutil.ignore_patterns('cache'))
        for folder in ['app','components','lib','public']:
            shutil.copytree(ROOT/'frontend'/folder,context/folder)
        copies='\n'.join(f'COPY --chown=node:node {folder}/ ./{folder}/' for folder in ['.next','app','components','lib','public'])
        dockerfile='FROM scholar-graph-frontend:item03-20261028\nWORKDIR /app/frontend\n'+copies+'\n'
    else:
        shutil.copytree(ROOT/'backend/scholar_graph',context/'backend/scholar_graph',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        shutil.copytree(ROOT/'contracts',context/'contracts')
        dockerfile='FROM scholar-graph-backend:item03-20261028\nCOPY --chown=scholar:scholar backend/scholar_graph/ /app/backend/scholar_graph/\nCOPY --chown=scholar:scholar contracts/ /app/contracts/\n'
    (context/'Dockerfile').write_text(dockerfile,encoding='utf-8')
    tag='scholar-graph-'+a.service+':item04-20261028'
    start=time.monotonic()
    result=subprocess.run(['docker','build','-t',tag,str(context)],cwd=ROOT)
    proof={'service':a.service,'tag':tag,'dependency_base':'scholar-graph-'+a.service+':item03-20261028',
        'elapsed_seconds':round(time.monotonic()-start,3),'exit_code':result.returncode,
        'files':{str(x.relative_to(context)).replace('\\','/'):digest(x) for x in context.rglob('*') if x.is_file()}}
    if result.returncode==0:proof['image_id']=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}']).decode().strip()
    write(BASE/(a.run+'-result.json'),proof)
    print(json.dumps({k:v for k,v in proof.items() if k!='files'}))
    raise SystemExit(result.returncode)
