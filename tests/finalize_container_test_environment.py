"""Re-run all component tests with isolated defaults; keep production hybrid and failed evidence."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from xml.etree import ElementTree as ET

from deployment_timer import finish_timer_observation

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/'tests/reports'


def main():
    build=json.loads((REPORTS/'final-deployment-build.json').read_text(encoding='utf-8'))
    result=json.loads((REPORTS/'final-deployment-container.json').read_text(encoding='utf-8'))
    assert all(c['passed'] for c in result['cases'].values()), 'Official HTTP cases must really pass first'
    old=ET.parse(REPORTS/'final-deployment-container-pytest.xml')
    failures={c.get('name') for c in old.iter('testcase') if c.find('failure') is not None}
    assert failures=={'test_search_real_anchors_order_pagination_cap_and_cors','test_empty_reason_and_missing_paper'}
    for source,target in [('final-deployment-container.json','final-deployment-container-before-test-isolation.json'),
        ('final-deployment-container-pytest.xml','final-deployment-container-before-test-isolation-pytest.xml'),
        ('final-deployment-build.json','final-deployment-build-before-test-isolation.json')]:
        assert not (REPORTS/target).exists()
        shutil.copyfile(REPORTS/source,REPORTS/target)
    env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ('API_KEY','TOKEN','SECRET','PASSWORD'))}
    env.pop('DEEPSEEK_MODEL',None)
    env.update(SCHOLAR_GRAPH_PDF_DIR=str(ROOT/'pdf'),SCHOLAR_GRAPH_REVISION=build['clone']['commit'])
    checkout=Path(build['clone']['path'])
    compose=['docker','compose','-p',build['project'],'-f','docker-compose.yml',
        '-f','services/docker-compose.acceptance.yml','-f','services/docker-compose.final-acceptance.yml']
    remote=result['output_root']+'/container-isolated-test-env.xml'
    assert re.fullmatch(r'/app/data/final-deployment/[a-f0-9]{32}/container-isolated-test-env.xml',remote)
    argv=compose+['exec','-T','-e','SCHOLAR_GRAPH_RETRIEVAL_MODE=lexical','backend','python',
        'tests/run_regression.py','full','--no-key','--corpus-dir','/corpus','--junit',remote]
    log=Path(build['run_root'])/'container-full-isolated-test-env.log'
    started=time.perf_counter()
    print(json.dumps({'stage':'container_full_isolated_test_environment','started':True}),flush=True)
    with log.open('wb') as handle:
        code=subprocess.run(argv,cwd=checkout,env=env,stdout=handle,stderr=subprocess.STDOUT,timeout=3600).returncode
    elapsed=round(time.perf_counter()-started,6)
    subprocess.run(compose+['cp','backend:'+remote,str(REPORTS/'final-deployment-container-pytest.xml')],
        cwd=checkout,env=env,capture_output=True,check=True)
    tree=ET.parse(REPORTS/'final-deployment-container-pytest.xml')
    suites=list(tree.iter('testsuite'))
    stats={k:sum(int(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
    stats.update(exit_code=code,elapsed_seconds=elapsed)
    actual_vector=next(c for c in tree.iter('testcase') if c.get('name')=='test_real_local_bge_m3_dense_sparse_chroma')
    assert actual_vector.find('failure') is None and actual_vector.find('skipped') is None
    assert actual_vector.find('properties') is not None, 'Actual BGE model metadata must still be recorded'
    result['regression_before_test_env_isolation']=result['regression']
    result['regression']=stats
    production=subprocess.check_output(compose+['exec','-T','backend','python','-c',
        "import os;print(os.environ['SCHOLAR_GRAPH_RETRIEVAL_MODE'])"],cwd=checkout,env=env,text=True).strip()
    assert production=='bge_m3_hybrid'
    result['component_test_environment']={'SCHOLAR_GRAPH_RETRIEVAL_MODE':'lexical',
        'production_backend_retrieval_mode':production,'real_vector_acceptance':'Actual local BGE-M3 dense+sparse test retained and passed'}
    finish_timer_observation(result,compose,checkout,env)
    build['steps'].append({'stage':'container-full-isolated-test-env','exit_code':code,
        'elapsed_seconds':elapsed,'argv':argv,'log':str(log),'log_bytes':log.stat().st_size,
        'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'last_lines':log.read_text(encoding='utf-8',errors='replace').splitlines()[-10:]})
    build['container']=result
    build['passed']=code==0 and result['passed'] and build['source_matches_clean_clone'] and build['clone']['clean_after_build_and_run']
    for name,value in [('final-deployment-container.json',result),('final-deployment-build.json',build)]:
        (REPORTS/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'stage':'container_full_isolated_test_environment',**stats,'passed':build['passed']}),flush=True)
    return int(not build['passed'])


if __name__=='__main__':
    raise SystemExit(main())
