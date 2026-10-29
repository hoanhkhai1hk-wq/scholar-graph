"""Actual deployed source/build, network, data isolation and frozen-input checks."""
import json,subprocess,hashlib,sqlite3
import httpx
from common import ROOT,BASE,write,digest
if __name__=='__main__':
    expected_back={str(p.relative_to(ROOT/'backend/scholar_graph')).replace('\\','/'):digest(p) for p in (ROOT/'backend/scholar_graph').rglob('*.py')}
    expected_front={str(p.relative_to(ROOT/'frontend')).replace('\\','/'):digest(p) for d in ['app','components','lib'] for p in (ROOT/'frontend'/d).rglob('*') if p.suffix in {'.ts','.tsx'}}
    expected_front.update({f:digest(ROOT/'frontend'/f) for f in ['next.config.mjs','.next/BUILD_ID']})
    report={'deployments':[]}
    for project,port,expected in [('scholar-graph',8030,0),('scholar-graph-item04',8100,37),('scholar-graph-item05',8120,20),('scholar-graph-item06',8140,21)]:
        row={'project':project,'backend_port':port,'services':{}}
        for service,files,folder in [('backend',expected_back,'/app/backend/scholar_graph/'),('frontend',expected_front,'/app/frontend/')]:
            name=project+'-'+service+'-1';v=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
            assert v['State']['Health']['Status']=='healthy' and not v['State']['OOMKilled']
            if service=='backend':
                code='import json,hashlib;from pathlib import Path;root=Path('+repr(folder)+');print(json.dumps({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*.py")}))'
                actual=json.loads(subprocess.check_output(['docker','exec',name,'python','-c',code]))
            else:
                code='const fs=require("fs"),c=require("crypto");let r={};for(const f of '+json.dumps(list(files))+')r[f]=c.createHash("sha256").update(fs.readFileSync('+json.dumps(folder)+'+f)).digest("hex");process.stdout.write(JSON.stringify(r));'
                actual=json.loads(subprocess.check_output(['docker','exec',name,'node','-e',code]))
            assert actual==files,(project,service,'deployed source differs')
            row['services'][service]={'health':v['State']['Health']['Status'],'oom_killed':False,'image_id':v['Image'],'restart':v['HostConfig']['RestartPolicy']['Name'],'source_files_checked':len(files)}
        dns=subprocess.check_output(['docker','exec',project+'-frontend-1','getent','hosts','backend']).decode().strip();assert dns.startswith('172.');row['backend_dns']=dns
        with httpx.Client(trust_env=False,timeout=180) as c:
            r=c.get(f'http://127.0.0.1:{port}/api/v1/papers',params={'page_size':100});r.raise_for_status();data=r.json();count=data.get('total',len(data.get('items',[])));assert count==expected,(project,count,expected)
            system=c.get(f'http://127.0.0.1:{port}/api/v2/system');system.raise_for_status();s=system.json();assert s['model_configured']
            row.update(paper_count=count,model_configured=True,workspace_release=s['workspace_release'])
        report['deployments'].append(row)
    before=json.loads((BASE/'workspace-before.json').read_text(encoding='utf8'));assert all(digest(ROOT/'pdf'/p)==sha for p,sha in before['pdfs'].items())
    frozen=json.loads((BASE/'frozen-before.json').read_text(encoding='utf8'))
    immutable={p:sha for p,sha in frozen.items() if p!='original-pdfs/index.sqlite3'}
    assert all(digest(BASE/'records'/p)==sha for p,sha in immutable.items())
    with sqlite3.connect(ROOT/'data/item05-20261029/records20/original-pdfs/index.sqlite3') as a,sqlite3.connect(BASE/'records/original-pdfs/index.sqlite3') as b:
        old={r[0]:r[1:] for r in a.execute('select paper_id,storage_name,sha256,byte_count from originals')}
        current={r[0]:r[1:] for r in b.execute('select paper_id,storage_name,sha256,byte_count from originals')}
        assert all(current.get(pid)==r for pid,r in old.items()) and len(current)==len(old)+1
        new_id=json.loads((BASE/'chinese-paper.json').read_text(encoding='utf8'))['paper_id']
        assert set(current)-set(old)=={new_id} and current[new_id][1]==digest(BASE/'chinese-acceptance.pdf')
        assert b.execute('pragma integrity_check').fetchone()[0]=='ok'
    report['original_index_check']={'previous_entries_unchanged':len(old),'new_authored_document_entries':1,'sqlite_integrity':'ok'}
    report.update(original_pdfs_unchanged=len(before['pdfs']),frozen_copied_source_files_unchanged=len(immutable),backend_source_sha256=expected_back,frontend_source_sha256=expected_front)
    report['memory_sample_not_peak']=[json.loads(s) for s in subprocess.check_output(['docker','stats','--no-stream','--format','{{json .}}','scholar-graph-item06-backend-1','scholar-graph-item06-frontend-1']).decode().splitlines()]
    write(BASE/'runtime-audit.json',report);print(json.dumps({'healthy_services':8,'paper_counts':[r['paper_count'] for r in report['deployments']],'pdfs_unchanged':len(before['pdfs']),'frozen_unchanged':len(immutable),'existing_original_index_entries_unchanged':len(old)}))
