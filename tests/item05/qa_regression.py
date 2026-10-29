"""Recheck the prior nine questions and five guards against this fresh real corpus."""
import argparse,importlib.util,json
from common import ROOT,BASE,client,write,ready
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();out=BASE/a.run;out.mkdir(exist_ok=False)
    cases=module('original_item02_cases',ROOT/'tests/item02/run_cases.py').CASES
    ask=module('original_qa_common',ROOT/'tests/qa_usability/common.py').ask
    rows=[];sessions={}
    with client() as c:
        ready(c)
        for name,ids,q in cases:
            key=tuple(ids)
            if key not in sessions:sessions[key]=c.post('/api/v2/sessions',json={'paper_ids':ids}).json()['id']
            row=ask(c,ids,q,out/name,session=sessions[key]);row['case']=name;rows.append(row);write(out/'results.json',rows)
    print(json.dumps({'count':len(rows),'errors':sum(bool(r.get('error')) for r in rows)}))
