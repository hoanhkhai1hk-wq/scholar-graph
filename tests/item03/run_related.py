"""Related regressions, explicit workspace temp dirs, real provider tests enabled."""
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/item02'))
from local_environment import configured_environment

FILES=['test_translation.py','test_translation_en.py','test_workspace.py','test_workspace_tasks.py','test_item03_navigation.py',
       'test_qa.py','test_qa_compare.py','test_qa_sse.py','test_compare_sse.py','test_qa_hybrid_retrieval.py','test_qa_two_stage.py',
       'test_model_api.py','test_model_gateway.py','test_agent_orchestration.py','test_workspace_research.py','test_item02_research.py','test_proxy_compatibility.py']
if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--run',required=True); args=parser.parse_args()
    env=configured_environment(); env.update(PYTHONIOENCODING='utf-8',SCHOLAR_GRAPH_TRACKING_ENABLED='false',SCHOLAR_GRAPH_GROBID_ENABLED='false')
    raise SystemExit(subprocess.run([sys.executable,'-m','pytest',*['tests/'+f for f in FILES],'-q','--run-real-model',
        '--basetemp','data/item03-20261028/'+args.run+'-temp','--junitxml','data/item03-20261028/'+args.run+'.xml'],cwd=ROOT,env=env).returncode)
