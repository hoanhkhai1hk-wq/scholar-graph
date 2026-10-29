"""Verify served source/build identity, existing data, health and actual caps."""
import json
import subprocess
import time
import httpx
from common import ROOT, BASE, write, digest

def command(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, encoding='utf8').strip()

def run():
    report = {'deployments': []}
    backend = {str(p.relative_to(ROOT/'backend/scholar_graph')).replace('\\','/'):digest(p) for p in (ROOT/'backend/scholar_graph').rglob('*.py')}
    frontend = {str(p.relative_to(ROOT/'frontend')).replace('\\','/'):digest(p) for folder in ['app','components','lib'] for p in (ROOT/'frontend'/folder).rglob('*') if p.suffix in ['.css','.ts','.tsx']}
    frontend.update({name:digest(ROOT/'frontend'/name) for name in ['next.config.mjs','.next/BUILD_ID']})
    for project,api,web,count in [('scholar-graph',8030,3000,0),('scholar-graph-item04',8100,3400,37),('scholar-graph-item05',8120,3420,20),('scholar-graph-item06',8140,3440,21),('scholar-graph-code-order',8160,3460,2),('scholar-graph-ui',8180,3500,21)]:
        row={'project':project,'web_port':web,'api_port':api,'services':{}}
        for service,expected,folder in [('backend',backend,'/app/backend/scholar_graph/'),('frontend',frontend,'/app/frontend/')]:
            name=project+'-'+service+'-1'; value=json.loads(command('docker','inspect',name))[0]
            assert value['State']['Health']['Status']=='healthy' and not value['State']['OOMKilled']
            if service=='backend':
                code='import json,hashlib;from pathlib import Path;r=Path('+repr(folder)+');print(json.dumps({str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in r.rglob("*.py")}))'
                actual=json.loads(command('docker','exec',name,'python','-c',code))
            else:
                code='const f=require("fs"),c=require("crypto");let r={};for(const n of '+json.dumps(list(expected))+')r[n]=c.createHash("sha256").update(f.readFileSync('+json.dumps(folder)+'+n)).digest("hex");process.stdout.write(JSON.stringify(r));'
                actual=json.loads(command('docker','exec',name,'node','-e',code))
            assert actual==expected,(project,service,'source/build mismatch')
            row['services'][service]={'health':'healthy','oom_killed':False,'verified_source_files':len(actual),'image':value['Image'],'nano_cpus':value['HostConfig']['NanoCpus'],'memory_limit_bytes':value['HostConfig']['Memory'],'restart':value['HostConfig']['RestartPolicy']['Name']}
        dns=command('docker','exec',project+'-frontend-1','getent','hosts','backend');assert dns.startswith('172.')
        row['dns']=dns
        with httpx.Client(base_url=f'http://127.0.0.1:{api}',trust_env=False,timeout=60) as client:
            system=client.get('/api/v2/system').json();assert system['model_configured']
            total=client.get('/api/v2/papers?page_size=100').json()['total'];assert total==count
            row.update(model_configured=True,paper_count=total)
        report['deployments'].append(row)
    ui=report['deployments'][-1]['services'];assert sum(v['nano_cpus'] for v in ui.values())==2_000_000_000
    assert sum(v['memory_limit_bytes'] for v in ui.values())==4*1024**3
    report['container_limits_boundary']='Frontend+backend combined 2 CPU/4 GiB. Chrome and other project containers run on host; not whole-machine performance certification.'
    report['docker_stats_sample']=json.loads('['+','.join(command('docker','stats','--no-stream','--format','{{json .}}','scholar-graph-ui-backend-1','scholar-graph-ui-frontend-1').splitlines())+']')
    before=json.loads((BASE/'workspace-before.json').read_text(encoding='utf8'))
    allowed=['docs/ui-design-proposals.md']
    for group,values in before.items():
        if not isinstance(values,dict):continue
        # Only the selected proposal is an intentional edit among pre-existing
        # dirty/untracked files. UploadForm, README, env and PDFs remain exact.
        check={n:s for n,s in values.items() if n.replace('\\','/') not in allowed}
        changed=[n for n,s in check.items() if not (ROOT/n).exists() or digest(ROOT/n)!=s]
        assert not changed,(group,changed)
        report[group+'_unchanged']=len(check)
    copied=json.loads((BASE/'frozen-before.json').read_text(encoding='utf8'))
    # original-pdfs/index.json is a content-addressed lookup, not source bytes.
    copied={n:s for n,s in copied.items() if n!='original-pdfs/index.json'}
    assert all(digest(BASE/'records'/n)==s for n,s in copied.items())
    report['isolated_immutable_files_unchanged']=len(copied)
    with httpx.Client(base_url='http://127.0.0.1:3500',trust_env=False,timeout=60) as client:
        samples=[]
        for _ in range(5):
            t=time.perf_counter();r=client.get('/');r.raise_for_status();samples.append(round((time.perf_counter()-t)*1000,3))
        report['warm_home_http_ms_five_samples']=samples
        report['warm_home_http_html_bytes']=len(r.content)
    report['passed']=True
    write(BASE/'runtime-audit.json',report)
    print(json.dumps({'passed':True,'healthy_services':12,'paper_counts':[r['paper_count'] for r in report['deployments']],'warm_home_http_ms':samples,'unchanged':{k:v for k,v in report.items() if k.endswith('_unchanged')}}))

if __name__=='__main__':run()
