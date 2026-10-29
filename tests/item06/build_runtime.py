"""Overlay tested source on the prior working image; no dependency reinstall."""
import argparse,shutil,subprocess,time
from common import ROOT,BASE,write
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('service',choices=['frontend','backend']);p.add_argument('--run',required=True);a=p.parse_args()
    out=BASE/a.run;out.mkdir(exist_ok=False)
    if a.service=='backend':
        shutil.copytree(ROOT/'backend/scholar_graph',out/'backend/scholar_graph',ignore=shutil.ignore_patterns('__pycache__','*.pyc'));shutil.copytree(ROOT/'contracts',out/'contracts')
        spec='COPY --chown=scholar:scholar backend/scholar_graph/ /app/backend/scholar_graph/\nCOPY --chown=scholar:scholar contracts/ /app/contracts/\n'
    else:
        shutil.copytree(ROOT/'frontend/.next',out/'.next',ignore=shutil.ignore_patterns('cache'))
        for f in ['app','components','lib','public']:shutil.copytree(ROOT/'frontend'/f,out/f)
        shutil.copyfile(ROOT/'frontend/next.config.mjs',out/'next.config.mjs')
        spec='WORKDIR /app/frontend\n'+''.join('COPY --chown=node:node '+f+'/ ./'+f+'/\n' for f in ['.next','app','components','lib','public'])+'COPY --chown=node:node next.config.mjs ./next.config.mjs\n'
    (out/'Dockerfile').write_text('FROM scholar-graph-'+a.service+':item05-20261029\n'+spec,encoding='utf8')
    start=time.monotonic();tag='scholar-graph-'+a.service+':item06-20261029'
    r=subprocess.run(['docker','build','-t',tag,str(out)],cwd=ROOT)
    write(BASE/(a.run+'-result.json'),{'tag':tag,'seconds':round(time.monotonic()-start,3),'exit_code':r.returncode});raise SystemExit(r.returncode)
