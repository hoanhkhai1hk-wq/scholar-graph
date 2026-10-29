"""Read-only checks of deployed artifacts and preservation of source inputs."""
import json,re,subprocess,time
import httpx
from common import ROOT,BASE,digest,write

def docker(*args):return subprocess.check_output(['docker',*args],cwd=ROOT).decode().strip()
if __name__=='__main__':
    result={'services':{},'artifacts':[]}
    with httpx.Client(trust_env=False,timeout=30) as c:
        for key,bc,fc,api,web in [('main','scholar-graph-backend-1','scholar-graph-frontend-1',8030,3000),
            ('demo','scholar-graph-item04-backend-1','scholar-graph-item04-frontend-1',8100,3400)]:
            for _ in range(45):
                try:
                    r=c.get(f'http://127.0.0.1:{api}/api/v2/system');r.raise_for_status();break
                except httpx.HTTPError:time.sleep(1)
            s=r.json();assert s['model_configured'] is True
            n=c.get(f'http://127.0.0.1:{api}/api/v1/papers').json()['total']
            page=c.get(f'http://127.0.0.1:{web}/qa');assert page.status_code==200
            info={'system':s,'papers':n,'api_origin':f'http://127.0.0.1:{api}','web_origin':f'http://127.0.0.1:{web}',
                'web_status':page.status_code,'dns':docker('exec',fc,'getent','hosts','backend')}
            assert re.search(r'172\.\d+\.\d+\.\d+',info['dns'])
            for service,container in [('backend',bc),('frontend',fc)]:
                info[service+'_image']=docker('inspect',container,'--format','{{.Image}}')
                info[service+'_restart_policy']=docker('inspect',container,'--format','{{.HostConfig.RestartPolicy.Name}}')
                for _ in range(40):
                    health=docker('inspect',container,'--format','{{.State.Health.Status}}')
                    if health=='healthy':break
                    time.sleep(1)
                assert health=='healthy';info[service+'_health']=health
            for folder,container,names in [('backend/scholar_graph',bc,['workspace_research.py','workspace_query.py','workspace_overview.py']),
                ('frontend/components',fc,['ResearchChat.tsx','ReadingWorkbench.tsx'])]:
                for name in names:
                    relative=folder+'/'+name;sha=digest(ROOT/relative)
                    assert sha==docker('exec',container,'sha256sum','/app/'+relative).split()[0]
                    result['artifacts'].append({'service':key,'file':relative,'sha256':sha,'matched':True})
            info['build_id']=docker('exec',fc,'cat','/app/frontend/.next/BUILD_ID')
            assert info['build_id']==(ROOT/'frontend/.next/BUILD_ID').read_text().strip()
            result['services'][key]=info
    before=json.loads((BASE/'workspace-before.json').read_text(encoding='utf8'))
    allowed={'backend/scholar_graph/workspace_research.py','backend/scholar_graph/workspace_overview.py','frontend/components/ResearchChat.tsx','frontend/components/ReadingWorkbench.tsx'}
    unrelated={p:sha for p,sha in before['files'].items() if p not in allowed}
    assert all((ROOT/p).exists() and digest(ROOT/p)==sha for p,sha in unrelated.items())
    assert all(digest(ROOT/'pdf'/p)==sha for p,sha in before['pdfs'].items())
    result.update(official_pdfs_unchanged=len(before['pdfs']),preexisting_files_unchanged=len(unrelated),passed=True)
    write(BASE/'runtime-final.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='artifacts'},ensure_ascii=False))
