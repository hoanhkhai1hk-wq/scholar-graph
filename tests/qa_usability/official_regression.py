"""Clone only the official parsed corpus; run real model cases through a local app.

No historical test sessions or records are mutated. Original bundles stay private.
"""
import argparse,importlib.util,json,os,shutil,sqlite3,sys
from pathlib import Path
from common import ROOT,BASE,ask,write
sys.path.insert(0,str(ROOT/'backend'));sys.path.insert(0,str(ROOT/'tests/item02'))
from local_environment import configured_environment

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',default='official-regression');a=p.parse_args()
    out=BASE/a.run;out.mkdir(exist_ok=False)
    source=ROOT/'data/item02-20261028/records';target=out/'records';target.mkdir()
    for folder in ['papers','original-pdfs']:shutil.copytree(source/folder,target/folder)
    with sqlite3.connect(source/'workspace.sqlite3') as src,sqlite3.connect(target/'workspace.sqlite3') as dst:src.backup(dst)
    env=configured_environment();os.environ.update({k:env[k] for k in ['DEEPSEEK_API_KEY','DEEPSEEK_MODEL']})
    os.environ.update(SCHOLAR_GRAPH_DATA_DIR=str(target),SCHOLAR_GRAPH_QA_MODE='deepseek',SCHOLAR_GRAPH_WORKSPACE_RETRIEVAL='lexical',
        SCHOLAR_GRAPH_TRACKING_ENABLED='false',SCHOLAR_GRAPH_GROBID_ENABLED='false',SCHOLAR_GRAPH_QA_RETRIEVAL_MODE='lexical')
    spec=importlib.util.spec_from_file_location('official_cases',ROOT/'tests/item02/run_cases.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    from starlette.testclient import TestClient
    from scholar_graph.api import create_app
    results=[];sessions={}
    with TestClient(create_app()) as c:
        for name,ids,q in m.CASES:
            key=tuple(ids)
            if key not in sessions:sessions[key]=c.post('/api/v2/sessions',json={'paper_ids':ids}).json()['id']
            row=ask(c,ids,q,out/name,session=sessions[key]);row['case']=name;results.append(row);write(out/'results.json',results)
