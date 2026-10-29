"""Complete relevant suites plus all item-five regression; no provider skip hidden."""
import argparse,subprocess,sys,importlib.util
from common import ROOT,BASE,configured_environment
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    spec=importlib.util.spec_from_file_location('item05_related',ROOT/'tests/item05/run_related.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    files=list(dict.fromkeys(old.FILES+['test_topology.py','test_charts.py','test_charts_3d.py','test_translation.py','test_translation_en.py','test_workspace_formulas.py','test_workspace_layout.py','test_item03_navigation.py','test_item06_writing_artifacts.py']))
    env=configured_environment();env.update(PYTHONIOENCODING='utf8',SCHOLAR_GRAPH_GROBID_ENABLED='false',SCHOLAR_GRAPH_TRACKING_ENABLED='false')
    raise SystemExit(subprocess.run([sys.executable,'-m','pytest',*['tests/'+f for f in files],'-q','--run-real-model',
        '--basetemp',str(BASE/(a.run+'-temp')),'--junitxml',str(BASE/(a.run+'.xml'))],cwd=ROOT,env=env).returncode)
