"""Validate the published empty-key template without touching personal .env."""
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    env={k:v for k,v in os.environ.items() if not k.startswith(('DEEPSEEK_','SCHOLAR_GRAPH_','SG_','COMPOSE_'))}
    args=['docker','compose','--env-file','.env.example','-f','docker-compose.yml','-f','deploy/compose.provider.example.yml','config','--format','json']
    r=subprocess.run(args,cwd=ROOT,env=env,capture_output=True,check=True)
    value=json.loads(r.stdout);provider=value['services']['backend']['environment']
    assert provider['DEEPSEEK_API_KEY']==''
    assert provider['DEEPSEEK_MODEL']=='deepseek-chat'
    assert provider['SCHOLAR_GRAPH_QA_MODE']=='deepseek'
    assert provider['SCHOLAR_GRAPH_QA_RERANKER']=='rrf'
    assert provider['SCHOLAR_GRAPH_WORKSPACE_RETRIEVAL']=='lexical'
    assert value['services']['backend']['ports'][0]['published']=='8000'
    assert value['services']['frontend']['ports'][0]['published']=='3000'
    assert 'COPY scripts/warm_demo.py ./scripts/warm_demo.py' in (ROOT/'Dockerfile').read_text()
    report={'passed':True,'published_template_config_valid':True,'empty_key_allowed_to_start':True,
            'key_missing':True,'model_set':True,'ranking':'rrf','workspace_retrieval':'lexical',
            'host_ports':[3000,8000],'warm_script_in_dockerfile':True,
            'note':'Compose configuration check, not a clean network rebuild or model success. Missing-key HTTP behavior separately covered by API tests.'}
    path=ROOT/'data/submission-20261030/config-check.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report))
