"""Final service, DNS, exact source hash and preserved-input checks."""
import json
import subprocess
import time
from common import ROOT,BASE,API,WEB,client,digest,write
import httpx

CORE=['arxiv_fetch.py','author_metadata.py','normalize.py','reference_identity.py','reference_importance.py','reference_acquisition.py','tracking.py','workspace_discovery.py','workspace_recommendations.py']
FRONT=['app/retrieval/page.tsx','app/globals.css','components/RetrievalWorkspace.tsx','components/AcquisitionPanel.tsx','components/RecommendationsPanel.tsx','components/RecommendationVote.tsx','components/DiscoveryStatus.tsx','components/TaskMonitor.tsx']
def docker(*args):return subprocess.check_output(['docker',*args],cwd=ROOT).decode().strip()
def source_hash(container,path):return docker('exec',container,'sha256sum',path).split()[0]

if __name__=='__main__':
    with client() as isolated, httpx.Client(trust_env=False,timeout=60) as c:
        for _ in range(60):
            try:
                if c.get('http://127.0.0.1:8000/api/v2/system').status_code==200:break
            except httpx.HTTPError:pass
            time.sleep(1)
        result={'services':{},'source_checks':[]}
        for project,backend,frontend,api,web in [('main','scholar-graph-backend-1','scholar-graph-frontend-1','http://127.0.0.1:8000','http://127.0.0.1:3000'),
           ('item04','scholar-graph-item04-backend-1','scholar-graph-item04-frontend-1',API,WEB)]:
            status=c.get(api+'/api/v2/system');status.raise_for_status()
            assert status.json()['model_configured'] is True
            r=c.get(web+'/retrieval');assert r.status_code==200
            count=c.get(api+'/api/v1/papers').json()['total']
            info={'system':status.json(),'web_http_status':r.status_code,'papers':count,
                  'backend_image':docker('inspect',backend,'--format','{{.Image}}'),'frontend_image':docker('inspect',frontend,'--format','{{.Image}}'),
                  'backend_health':docker('inspect',backend,'--format','{{.State.Health.Status}}'),
                  'dns':docker('exec',frontend,'getent','hosts','backend')}
            assert info['backend_health']=='healthy'
            if project=='main':
                info['frontend_health']=docker('inspect',frontend,'--format','{{.State.Health.Status}}')
                assert info['frontend_health']=='healthy'
                assert count==json.loads((BASE/'main-before-release.json').read_text(encoding='utf-8'))['main_papers_before']
            for name in CORE:
                host=ROOT/'backend/scholar_graph'/name;target='/app/backend/scholar_graph/'+name
                assert digest(host)==source_hash(backend,target),target
                result['source_checks'].append({'project':project,'file':'backend/scholar_graph/'+name,'sha256':digest(host),'matched':True})
            for name in FRONT:
                host=ROOT/'frontend'/name;target='/app/frontend/'+name
                assert digest(host)==source_hash(frontend,target),target
                result['source_checks'].append({'project':project,'file':'frontend/'+name,'sha256':digest(host),'matched':True})
            assert (ROOT/'frontend/.next/BUILD_ID').read_text().strip()==docker('exec',frontend,'cat','/app/frontend/.next/BUILD_ID')
            result['services'][project]=info
        originals=json.loads((BASE/'workspace-before.json').read_text(encoding='utf-8'))['official_pdfs']
        assert all(digest(ROOT/'pdf'/name)==sha for name,sha in originals.items())
        result.update(official_pdf_count=len(originals),official_pdfs_unchanged=True,source_files_matched=len(result['source_checks']),passed=True)
        write(BASE/'runtime-final.json',result)
        print(json.dumps({'passed':True,'source_files_matched':len(result['source_checks']),'official_pdfs_unchanged':len(originals),
               'services':{k:{p:v[p] for p in ['papers','web_http_status','backend_health','dns']} for k,v in result['services'].items()}},ensure_ascii=False))
