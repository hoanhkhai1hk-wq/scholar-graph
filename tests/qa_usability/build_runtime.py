"""Build a source-only runtime overlay on the verified dependency images."""
import argparse,json,shutil,subprocess,time
from common import ROOT,BASE,write,digest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('service',choices=['frontend','backend']);p.add_argument('--run',required=True);a=p.parse_args()
    context=BASE/a.run;context.mkdir(exist_ok=False)
    base='scholar-graph-'+a.service+':item04-20261028'
    if a.service=='frontend':
        shutil.copytree(ROOT/'frontend/.next',context/'.next',ignore=shutil.ignore_patterns('cache'))
        for folder in ['app','components','lib','public']:shutil.copytree(ROOT/'frontend'/folder,context/folder)
        copies='\n'.join('COPY --chown=node:node '+x+'/ ./'+x+'/' for x in ['.next','app','components','lib','public'])
        dockerfile='FROM '+base+'\nWORKDIR /app/frontend\n'+copies+'\n'
    else:
        shutil.copytree(ROOT/'backend/scholar_graph',context/'backend/scholar_graph',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        shutil.copytree(ROOT/'contracts',context/'contracts')
        dockerfile='FROM '+base+'\nCOPY --chown=scholar:scholar backend/scholar_graph/ /app/backend/scholar_graph/\nCOPY --chown=scholar:scholar contracts/ /app/contracts/\n'
    (context/'Dockerfile').write_text(dockerfile,encoding='utf8')
    tag='scholar-graph-'+a.service+':qa-usability-20261029';start=time.monotonic()
    r=subprocess.run(['docker','build','-t',tag,str(context)],cwd=ROOT)
    result={'tag':tag,'dependency_base':base,'exit_code':r.returncode,'seconds':round(time.monotonic()-start,3)}
    if r.returncode==0:result['image_id']=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}']).decode().strip()
    write(BASE/(a.run+'-result.json'),result);print(json.dumps(result));raise SystemExit(r.returncode)
