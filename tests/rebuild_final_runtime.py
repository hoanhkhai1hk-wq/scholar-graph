"""Rebuild a clean remote main after runtime diagnosis, preserving first-run evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT/'tests/reports'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--activate', action='store_true')
    parser.add_argument('--retry-build', action='store_true')
    args = parser.parse_args()
    output = REPORTS/'final-deployment-runtime-rebuild.json'
    old = json.loads((REPORTS/'final-deployment-build.json').read_text(encoding='utf-8'))
    env = {k:v for k,v in os.environ.items() if not any(p in k.upper() for p in ('API_KEY','TOKEN','SECRET','PASSWORD'))}
    env.pop('DEEPSEEK_MODEL',None)
    env['SCHOLAR_GRAPH_PDF_DIR'] = str(ROOT/'pdf')
    if args.activate or args.retry_build:
        evidence = json.loads(output.read_text(encoding='utf-8'))
    else:
        if output.exists():
            previous=json.loads(output.read_text(encoding='utf-8'))
            label='final-deployment-runtime-rebuild-interrupted.json'
            if (REPORTS/label).exists():
                label='final-deployment-runtime-rebuild-network-failure.json'
            if (REPORTS/label).exists():
                label='final-deployment-runtime-rebuild-prior-'+previous['clone']['commit'][:8]+'-'+uuid4().hex[:8]+'.json'
            shutil.copyfile(output,REPORTS/label)
        run = ROOT/'data/final-deployment-build'/uuid4().hex
        run.mkdir(parents=True)
        evidence = {'project':old['project'],'remote':old['remote'],'run_root':str(run),
            'steps':[],'credentials_forwarded':False,'passed':False,
            'reason':'Linux symlink-resolved worker used system Python without vector dependencies'}
    run = Path(evidence['run_root'])
    checkout = run/'checkout'

    def save():
        output.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    def command(stage,argv,cwd=checkout,timeout=10800):
        started = time.perf_counter()
        log = run/(stage+'.log')
        print(json.dumps({'stage':stage,'started':True}),flush=True)
        with log.open('wb') as handle:
            result = subprocess.run([str(a) for a in argv],cwd=cwd,env=env,stdout=handle,
                stderr=subprocess.STDOUT,timeout=timeout)
        text = log.read_text(encoding='utf-8',errors='replace')
        row = {'stage':stage,'argv':[str(a) for a in argv],'exit_code':result.returncode,
            'elapsed_seconds':round(time.perf_counter()-started,6),'log':str(log),
            'log_bytes':log.stat().st_size,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),
            'last_lines':text.splitlines()[-20:]}
        evidence['steps'].append(row)
        save()
        print(json.dumps({k:row[k] for k in ('stage','exit_code','elapsed_seconds')}),flush=True)
        if result.returncode:
            raise RuntimeError(stage+' failed; inspect preserved log')
        return text

    if not args.activate and not args.retry_build:
        command('clone-main',['git','clone','--branch','main','--single-branch',old['remote'],checkout],ROOT,180)
        head = command('clone-head',['git','rev-parse','HEAD']).strip()
        clean = not command('clone-clean',['git','status','--porcelain']).strip()
        evidence['clone'] = {'commit':head,'clean':clean,'path':str(checkout),
            'host_artifacts_absent':{p:not (checkout/p).exists() for p in
                ('backend/.venv','frontend/node_modules','frontend/.next','.env','pdf','data')}}
        assert clean and all(evidence['clone']['host_artifacts_absent'].values())
    env['SCHOLAR_GRAPH_REVISION'] = evidence['clone']['commit']
    compose = ['docker','compose','-p',evidence['project'],'-f','docker-compose.yml',
        '-f','services/docker-compose.acceptance.yml','-f','services/docker-compose.final-acceptance.yml']
    if args.retry_build:
        assert not subprocess.check_output(['git','status','--porcelain'],cwd=checkout).strip()
        for step in evidence['steps']:
            if step['stage']=='build-no-cache' and step['exit_code']:
                step['stage']='build-no-cache-network-failure'
        command('build-no-cache-network-retry',compose+['build','--no-cache'])
        evidence['steps'][-1]['stage']='build-no-cache'
        evidence['build_completed']=True
        save()
        return 0
    if not args.activate:
        command('compose-config',compose+['config'])
        command('build-no-cache',compose+['build','--no-cache'])
        evidence['build_completed'] = True
        save()
        return 0

    assert evidence['build_completed'] and 'container' in old, 'First formal run must finish and be preserved'
    for source,target in [('final-deployment-build.json','final-deployment-build-before-runtime-fix.json'),
        ('final-deployment-container.json','final-deployment-container-before-runtime-fix.json'),
        ('final-deployment-container-pytest.xml','final-deployment-container-before-runtime-fix-pytest.xml')]:
        assert not (REPORTS/target).exists()
        shutil.copyfile(REPORTS/source,REPORTS/target)
    cid = command('previous-backend-id',compose+['ps','-q','backend']).strip()
    mount = json.loads(command('previous-data-mount',['docker','inspect',cid]))[0]['Mounts']
    volume = next(m['Name'] for m in mount if m['Destination']=='/app/data' and m['Type']=='volume')
    command('stop-previous-backend',compose+['stop','backend'])
    # Preserve failed-run records on the same container volume. No host model or
    # parsed records are imported, and the new HTTP library starts empty again.
    archived = 'records-before-runtime-fix-'+uuid4().hex
    code = ("from pathlib import Path; import json,shutil; root=Path('/app/data').resolve(); "
        "p=root/'records'; assert p.resolve().parent==root and p.is_dir(); "
        f"p.rename(root/{archived!r}); "
        f"src=root/{archived!r}/'models/paddlex'; dst=root/'paddle-models'; "
        "assert not list(src.rglob('*.pdf')); "
        "shutil.copytree(src,dst,dirs_exist_ok=True) if src.is_dir() else None; "
        f"print(json.dumps({{'archived':{archived!r},'new_http_library_absent':not p.exists(),'retained_public_ocr_weight_files':len(list(dst.rglob('*.pdiparams')))}}))")
    evidence['data_archive'] = json.loads(command('archive-first-run-records',[
        'docker','run','--rm','--network','none','--user','1000','--mount',f'type=volume,source={volume},target=/app/data',
        '--entrypoint','python',evidence['project']+'-backend','-c',code]))
    command('up-healthy',compose+['up','-d','--wait','--wait-timeout','300'],timeout=420)
    evidence['previous_runtime_source_commit'] = old['clone']['commit']
    evidence['public_model_provenance'] = 'Same fresh container volume; anonymous public download verified before rebuild; no host cache'
    evidence['previous_preparation_steps'] = [s for s in old['steps'] if s['stage'].startswith(('prepare-','confirm-'))]
    save()
    (REPORTS/'final-deployment-build.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
