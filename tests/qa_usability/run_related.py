"""Full question/retrieval/SSE/numeric and translation regressions; no silent skip claim."""
import argparse
import subprocess
import sys
from common import ROOT,BASE
sys.path.insert(0,str(ROOT/'tests/item02'))
from local_environment import configured_environment
FILES=['test_qa.py','test_qa_compare.py','test_qa_sse.py','test_compare_sse.py','test_qa_hybrid_retrieval.py','test_qa_two_stage.py',
 'test_model_api.py','test_model_gateway.py','test_agent_orchestration.py','test_workspace.py','test_workspace_tasks.py',
 'test_workspace_research.py','test_item02_research.py','test_qa_usability.py','test_proxy_compatibility.py']
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    import os
    env=configured_environment();env.update(PYTHONIOENCODING='utf-8',SCHOLAR_GRAPH_GROBID_ENABLED='false',SCHOLAR_GRAPH_TRACKING_ENABLED='false')
    raise SystemExit(subprocess.run([sys.executable,'-m','pytest',*['tests/'+f for f in FILES],'-q','--run-real-model','--basetemp',str(BASE/(a.run+'-temp')),
        '--junitxml',str(BASE/(a.run+'.xml'))],cwd=ROOT,env=env).returncode)
