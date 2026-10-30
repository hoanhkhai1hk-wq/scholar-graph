"""Final fast/full regression includes actual-provider/OCR gates and new seams."""
import argparse
import importlib.util
import subprocess
import sys
from common import ROOT,BASE,configured_environment

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('layer',choices=['fast','related']);p.add_argument('--run',required=True);a=p.parse_args()
    env=configured_environment();env.update(PYTHONIOENCODING='utf8',SCHOLAR_GRAPH_GROBID_ENABLED='false',SCHOLAR_GRAPH_TRACKING_ENABLED='false')
    env.setdefault('SCHOLAR_GRAPH_OCR_CACHE_DIR',str(ROOT/'data/code-order-20261029/ocr-cache'))
    if a.layer=='fast':files=['tests'];options=['--layer','fast']
    else:
        spec=importlib.util.spec_from_file_location('item05_related',ROOT/'tests/item05/run_related.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        files=['tests/'+n for n in dict.fromkeys(m.FILES+['test_topology.py','test_charts.py','test_charts_3d.py','test_translation.py','test_translation_en.py','test_workspace_formulas.py','test_workspace_layout.py','test_item03_navigation.py','test_item06_writing_artifacts.py','test_parsing.py','test_page_batches.py','test_code_layout.py','test_reading_cache.py','test_resident_vector.py'])];options=['--run-real-model','--run-ocr']
    with (BASE/(a.run+'.log')).open('w',encoding='utf8') as out:
        r=subprocess.run([sys.executable,'-m','pytest',*files,'-q',*options,'--basetemp',str(BASE/(a.run+'-temp')),'--junitxml',str(BASE/(a.run+'.xml'))],cwd=ROOT,env=env,stdout=out,stderr=subprocess.STDOUT)
    print((BASE/(a.run+'.log')).read_text(encoding='utf8'));raise SystemExit(r.returncode)
