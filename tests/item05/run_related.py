"""Full related suites; actual-provider marker explicitly enabled, no silent model skip."""
import argparse,subprocess,sys
from common import ROOT,BASE,configured_environment
FILES=['test_citation_graph.py','test_graph_contracts.py','test_graph_api.py','test_graph_identity_evidence.py',
 'test_reference_identity.py','test_bibliography_formats.py','test_framework_contract.py','test_frameworks.py','test_reviews.py','test_future_work.py',
 'test_workspace.py','test_workspace_tasks.py','test_workspace_research.py','test_item01_parsing_quality.py','test_item05_graph_future.py',
 'test_grobid_evidence.py','test_grobid_default_path.py','test_grobid_conversion_fix.py','test_model_api.py','test_model_gateway.py','test_proxy_compatibility.py']
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();env=configured_environment()
    env.update(PYTHONIOENCODING='utf-8',SCHOLAR_GRAPH_GROBID_ENABLED='false',SCHOLAR_GRAPH_TRACKING_ENABLED='false')
    raise SystemExit(subprocess.run([sys.executable,'-m','pytest',*['tests/'+n for n in FILES],'-q','--run-real-model',
        '--basetemp',str(BASE/(a.run+'-temp')),'--junitxml',str(BASE/(a.run+'.xml'))],cwd=ROOT,env=env).returncode)
