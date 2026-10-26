"""Clean remote main, no-cache images, actual containers and per-file evidence export."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
REMOTE = 'https://github.com/hoanhkhai1hk-wq/scholar-graph.git'


def main():
    run_id = uuid4().hex
    root = ROOT/'data/final-deployment-build'/run_id
    root.mkdir(parents=True)
    checkout = root/'checkout'
    evidence = {'project':'sg-final-'+run_id[:10], 'run_root':str(root), 'remote':REMOTE,
                'steps':[], 'credentials_forwarded':False, 'passed':False}
    output = ROOT/'tests/reports/final-deployment-build.json'
    env = {k:v for k,v in os.environ.items() if not any(p in k.upper() for p in ('API_KEY','TOKEN','SECRET','PASSWORD'))}
    env.pop('DEEPSEEK_MODEL',None)
    env['SCHOLAR_GRAPH_PDF_DIR'] = str(ROOT/'pdf')

    def save():
        output.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    def command(label, argv, *, cwd=ROOT, timeout=7200):
        print(json.dumps({'stage':label,'started':True}),flush=True)
        log = root/(label+'.log')
        started = time.perf_counter()
        with log.open('wb') as handle:
            try:
                code = subprocess.run([str(a) for a in argv],cwd=cwd,env=env,stdout=handle,
                                      stderr=subprocess.STDOUT,timeout=timeout).returncode
            except subprocess.TimeoutExpired:
                code = 124
        text = log.read_text(encoding='utf-8',errors='replace')
        row = {'stage':label,'exit_code':code,'elapsed_seconds':round(time.perf_counter()-started,6),
               'argv':[str(a) for a in argv], 'log':str(log),'log_bytes':log.stat().st_size,
               'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'last_lines':text.splitlines()[-20:]}
        evidence['steps'].append(row)
        save()
        print(json.dumps({'stage':label,'exit_code':code,'seconds':row['elapsed_seconds']}),flush=True)
        return code,text

    def require(code,label):
        if code:
            raise RuntimeError(label+' failed; see stage log')

    try:
        code,_ = command('clone-main',['git','clone','--branch','main','--single-branch',REMOTE,checkout],timeout=180)
        require(code,'clean clone')
        _,head = command('clone-head',['git','rev-parse','HEAD'],cwd=checkout)
        _,status = command('clone-clean',['git','status','--porcelain'],cwd=checkout)
        evidence['clone'] = {'commit':head.strip(),'clean':not status.strip(),'path':str(checkout),
            'host_artifacts_absent':{name:not (checkout/name).exists() for name in
                ('backend/.venv','frontend/node_modules','frontend/.next','.env','pdf','data')}}
        assert evidence['clone']['clean'] and all(evidence['clone']['host_artifacts_absent'].values())
        env['SCHOLAR_GRAPH_REVISION'] = head.strip()
        compose = ['docker','compose','-p',evidence['project'],'-f','docker-compose.yml',
            '-f','services/docker-compose.acceptance.yml','-f','services/docker-compose.final-acceptance.yml']
        code,_ = command('compose-config',compose+['config'],cwd=checkout)
        require(code,'compose config')
        command('docker-version',['docker','version'],cwd=checkout)
        code,_ = command('build-no-cache',compose+['build','--no-cache'],cwd=checkout,timeout=10800)
        require(code,'no-cache build')
        code,_ = command('up-healthy',compose+['up','-d','--wait','--wait-timeout','300'],cwd=checkout,timeout=420)
        require(code,'container health')
        _,state = command('container-state',compose+['ps','--format','json'],cwd=checkout)
        evidence['container_state'] = state
        # Network preparation has its own bound; it must not consume the
        # validation probe's 40-minute subprocess budget on slower links.
        code,_ = command('prepare-public-vector-model',compose+['exec','-T','backend',
            '/opt/vector-venv/bin/python','backend/download_bge_m3.py'],cwd=checkout,timeout=7200)
        require(code,'public model preparation')
        code,log = command('container-acceptance',compose+['exec','-T','backend','python',
            'tests/run_final_deployment_container.py'],cwd=checkout,timeout=10800)
        rows = []
        for line in log.splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
        remote = next(row['report'] for row in reversed(rows) if 'report' in row)
        assert re.fullmatch(r'/app/data/final-deployment/[a-f0-9]{32}/container.json',remote)
        parent = remote.rsplit('/',1)[0]
        exported = root/'exported'
        exported.mkdir()
        for name in ('container.json','container-pytest.xml','pytest-console.txt','model-download.log',
                     'dedup.json','ocr.json','longbook.json'):
            copied,_ = command('export-'+name.replace('.','-'),compose+['cp','backend:'+parent+'/'+name,exported/name],cwd=checkout)
            require(copied,'export '+name)
        result = json.loads((exported/'container.json').read_text(encoding='utf-8'))
        evidence['container'] = result
        evidence['source_matches_clean_clone'] = all(hashlib.sha256((checkout/name).read_bytes()).hexdigest()==digest
            for name,digest in result['source_sha256'].items())
        import shutil
        for name,target in [('container.json','final-deployment-container.json'),('container-pytest.xml','final-deployment-container-pytest.xml')]:
            shutil.copyfile(exported/name,ROOT/'tests/reports'/target)
        _,status = command('clone-final-clean',['git','status','--porcelain'],cwd=checkout)
        evidence['clone']['clean_after_build_and_run'] = not status.strip()
        evidence['passed'] = code == 0 and result['passed'] and evidence['source_matches_clean_clone'] and not status.strip()
    except Exception as error:
        evidence['error'] = {'type':type(error).__name__,'message':str(error)[:500]}
    save()
    print(json.dumps({'passed':evidence['passed'],'report':str(output),'run_root':str(root)}),flush=True)
    return int(not evidence['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
