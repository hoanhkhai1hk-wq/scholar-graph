"""Actual follow-up polling to verify new-paper budget and known-paper dedup."""
import argparse
import json
import time
from common import BASE,client,write
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    out=BASE/a.run;out.mkdir(exist_ok=False)
    seed=json.loads((BASE/'seed-upload.json').read_text(encoding='utf-8'))['paper_id']
    with client() as c:
        before=c.get('/api/v1/papers',params={'page_size':100}).json()
        started=time.monotonic();r=c.post('/api/v2/tracking/run',json={'paper_ids':[seed],'force':True,'max_candidates':3,'max_imports':1});r.raise_for_status()
        value=r.json();write(out/'run.json',value)
        after=c.get('/api/v1/papers',params={'page_size':100}).json()
        proof={'seconds':round(time.monotonic()-started,3),'before_papers':before['total'],'after_papers':after['total'],
            'query_count':len(value['queries']),'query_return_counts':[q['returned_count'] for q in value['queries']],
            **{k:value[k] for k in ['status','candidate_count','imported_count','duplicate_count','failed_count','query_failed_count','discovered_count']}}
        assert after['total']-before['total']==value['imported_count']
        assert value['imported_count']<=1
        write(out/'result.json',proof);print(json.dumps(proof))
