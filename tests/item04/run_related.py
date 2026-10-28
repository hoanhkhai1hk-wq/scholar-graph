"""Full deterministic discovery, ingestion, identity, metadata and workspace regressions."""
import argparse
import os
import subprocess
import sys
from common import ROOT,BASE

FILES=['test_arxiv_fetch.py','test_tracking.py','test_tracking_import.py','test_tracking_scheduler.py',
 'test_recommendations.py','test_recommendations_api.py','test_recommendation_feedback.py','test_citation_cleanup.py',
 'test_reference_identity.py','test_graph_identity_evidence.py','test_grobid_default_path.py',
 'test_workspace.py','test_workspace_tasks.py','test_item04_discovery.py','test_proxy_compatibility.py']
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    env=dict(os.environ);env.update(PYTHONIOENCODING='utf-8',SCHOLAR_GRAPH_TRACKING_ENABLED='false',SCHOLAR_GRAPH_GROBID_ENABLED='false')
    raise SystemExit(subprocess.run([sys.executable,'-m','pytest',*['tests/'+f for f in FILES],'-q',
       '--basetemp',str(BASE/(a.run+'-temp')),'--junitxml',str(BASE/(a.run+'.xml'))],cwd=ROOT,env=env).returncode)
