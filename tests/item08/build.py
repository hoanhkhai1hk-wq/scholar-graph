"""Overlay verified local dependencies; no credential/data layers in images."""
import argparse
import shutil
import subprocess
from common import ROOT,BASE,write
import time

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();folder=BASE/a.run;folder.mkdir(exist_ok=False);started=time.perf_counter()
    shutil.copytree(ROOT/'backend/scholar_graph',folder/'backend/scholar_graph',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(ROOT/'frontend/.next',folder/'frontend/.next',ignore=shutil.ignore_patterns('cache'))
    for n in ['app','components','lib','public']:shutil.copytree(ROOT/'frontend'/n,folder/'frontend'/n)
    shutil.copyfile(ROOT/'frontend/next.config.mjs',folder/'frontend/next.config.mjs')
    (folder/'scripts').mkdir();shutil.copyfile(ROOT/'scripts/warm_demo.py',folder/'scripts/warm_demo.py')
    for name in ['README.md','Dockerfile','docker-compose.yml']:shutil.copyfile(ROOT/name,folder/name)
    spec='FROM scholar-graph-backend:code-order-20261029 AS backend\nCOPY --chown=scholar:scholar backend/scholar_graph/ /app/backend/scholar_graph/\n'
    spec+='COPY --chown=scholar:scholar scripts/ /app/scripts/\nCOPY --chown=scholar:scholar README.md Dockerfile docker-compose.yml /app/\n'
    spec+='FROM scholar-graph-frontend:celadon-20261029 AS frontend\nCOPY --chown=node:node frontend/ /app/frontend/\n'
    (folder/'Dockerfile').write_text(spec,encoding='utf8')
    for service in ['backend','frontend']:
        with (BASE/(a.run+'-'+service+'.log')).open('w',encoding='utf8') as log:
            subprocess.run(['docker','build','--target',service,'-t',f'scholar-graph-{service}:item08-20261030',str(folder)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    write(BASE/(a.run+'-result.json'),{'passed':True,'seconds':time.perf_counter()-started})
