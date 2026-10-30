"""Verify delivered code, runtime identity and preservation without dumping env."""
import hashlib
import json
import subprocess
from pathlib import Path
import httpx
from common import ROOT, BASE, write

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()

if __name__ == '__main__':
    before=json.loads((BASE/'workspace-before.json').read_text(encoding='utf8'))
    report={'preservation':{},'runtime':[]}
    for group in ['pdfs','source_records','files']:
        changed=[p for p,h in before[group].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
        # README includes the new item08 instructions. Other pre-existing changes
        # must remain byte-for-byte identical until the separately authorized audit.
        expected=['README.md'] if group=='files' else []
        report['preservation'][group]={'count':len(before[group]),'changed':changed,'expected_changed':expected}
        assert set(changed)==set(expected),(group,changed)
    report['preservation']['readme_prefix_preserved']=(ROOT/'README.md').read_bytes().startswith((BASE/'README-before.md').read_bytes())
    assert report['preservation']['readme_prefix_preserved']
    sources=['workspace.py','qa_retrieval.py','rerank_worker.py','vector_worker.py','vector_search.py']
    for project,port,expected in [('scholar-graph',8030,0),('scholar-graph-item08',8200,23)]:
        row={'project':project,'services':{}}
        for service in ['backend','frontend']:
            name=project+'-'+service+'-1';j=json.loads(docker('inspect',name))[0]
            s={'health':j['State']['Health']['Status'],'image':j['Image'],'oom_killed':j['State']['OOMKilled'],
               'memory_limit':j['HostConfig']['Memory'],'nano_cpus':j['HostConfig']['NanoCpus']}
            assert s['health']=='healthy' and not s['oom_killed']
            if service=='backend':
                s['source_hashes']={}
                for file in sources:
                    actual=docker('exec',name,'sha256sum','/app/backend/scholar_graph/'+file).split()[0]
                    assert actual==sha(ROOT/'backend/scholar_graph'/file),file
                    s['source_hashes'][file]=actual
                s['model_configuration']=docker('exec',name,'python','-c',"import os;print('KEY_SET' if os.getenv('DEEPSEEK_API_KEY') else 'KEY_MISSING');print('MODEL_SET' if os.getenv('DEEPSEEK_MODEL') else 'MODEL_MISSING')").splitlines()
                assert s['model_configuration']==['KEY_SET','MODEL_SET']
            else:
                s['build_id']=docker('exec',name,'cat','/app/frontend/.next/BUILD_ID')
                assert s['build_id']==(ROOT/'frontend/.next/BUILD_ID').read_text().strip()
                s['dns']=docker('exec',name,'getent','hosts','backend')
                assert s['dns']
                if project=='scholar-graph':assert s['dns'].startswith('172.')
            row['services'][service]=s
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False) as c:
            r=c.get('/api/v2/papers');r.raise_for_status();row['paper_count']=r.json()['total'];assert row['paper_count']==expected
        report['runtime'].append(row)
    report['passed']=True;write(BASE/'release-audit.json',report)
    print(json.dumps({'passed':True,'pdfs_unchanged':len(before['pdfs']),'frozen_files_unchanged':len(before['source_records']),'runtime':len(report['runtime'])}))
