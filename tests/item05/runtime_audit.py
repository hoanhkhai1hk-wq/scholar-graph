"""Read-only deployed-source, health, DNS, data-isolation and input-integrity audit."""
import json,subprocess,hashlib
import httpx
from common import ROOT,BASE,write,digest
BACK=['citation_graph.py','front_matter.py','graph_service.py','normalize.py','reference_identity.py','workspace.py','workspace_future.py','workspace_routes.py','workspace_task_routes.py','workspace_writing.py','future_evidence.py','graph_preparation.py','graph_bibliography.py']
FRONT=['app/api/workspace/[...path]/route.ts','app/globals.css','app/graph/page.tsx','components/GraphCanvas.tsx','components/GraphWorkspace.tsx','components/UploadWorkspace.tsx','components/PaperPicker.tsx','components/GraphResearch.tsx','components/GraphDiagnostics.tsx','components/FutureDirections.tsx','lib/server-transport.ts','next.config.mjs','.next/BUILD_ID']
if __name__=='__main__':
    report={'deployments':[]}
    for prefix,port,expected in [('scholar-graph',8030,0),('scholar-graph-item04',8100,37),('scholar-graph-item05',8120,20)]:
        row={'project':prefix,'backend_port':port,'expected_papers':expected,'services':{}}
        for service,files in [('backend',BACK),('frontend',FRONT)]:
            name=prefix+'-'+service+'-1';v=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
            assert v['State']['Health']['Status']=='healthy' and not v['State']['OOMKilled']
            hashes={}
            for f in files:
                remote=('/app/backend/scholar_graph/' if service=='backend' else '/app/frontend/')+f
                local=ROOT/('backend/scholar_graph' if service=='backend' else 'frontend')/f
                h=subprocess.check_output(['docker','exec',name,'sha256sum',remote]).decode().split()[0];assert h==digest(local),(name,f)
                hashes[f]=h
            row['services'][service]={'health':v['State']['Health']['Status'],'oom_killed':v['State']['OOMKilled'],'image_id':v['Image'],'restart':v['HostConfig']['RestartPolicy']['Name'],'source_sha256':hashes}
        dns=subprocess.check_output(['docker','exec',prefix+'-frontend-1','getent','hosts','backend']).decode().strip();assert dns.startswith('172.')
        row['backend_dns']=dns
        with httpx.Client(trust_env=False,timeout=120) as c:
            r=c.get(f'http://127.0.0.1:{port}/api/v1/papers',params={'page_size':100});r.raise_for_status();d=r.json()
            count=d.get('total',len(d.get('papers',d.get('items',[]))));assert count==expected,(prefix,d)
            row['paper_count']=count
            system=c.get(f'http://127.0.0.1:{port}/api/v2/system');system.raise_for_status();row['system_http_status']=system.status_code
        report['deployments'].append(row)
    before=json.loads((BASE/'workspace-before.json').read_text(encoding='utf8'))
    assert all(digest(ROOT/'pdf'/name)==sha for name,sha in before['pdfs'].items())
    frozen=json.loads((BASE/'frozen-before-delivery.json').read_text(encoding='utf8'))
    assert all(digest(BASE/'records20'/name)==sha for name,sha in frozen.items())
    report['original_pdfs_unchanged']=len(before['pdfs']);report['frozen_records_and_retained_pdfs_unchanged']=len(frozen)
    stats=subprocess.check_output(['docker','stats','--no-stream','--format','{{json .}}','scholar-graph-item05-backend-1','scholar-graph-item05-frontend-1']).decode()
    report['memory_sample_not_peak']=[json.loads(line) for line in stats.splitlines()]
    write(BASE/'runtime-audit.json',report);print(json.dumps({'healthy_services':6,'paper_counts':[r['paper_count'] for r in report['deployments']],'pdfs_unchanged':len(before['pdfs']),'frozen_files_unchanged':len(frozen)}))
