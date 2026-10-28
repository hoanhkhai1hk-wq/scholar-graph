"""Reproduce the historical five-real-paper corpus in a new isolated directory."""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from common import ROOT,BASE,write,digest
sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.api import create_app

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);args=p.parse_args()
    out=BASE/args.run;out.mkdir(exist_ok=False)
    historical=json.loads((ROOT/'tests/reports/tracking-live-results.json').read_text(encoding='utf-8'))
    source=ROOT/'data/tracking-acceptance-final-v4/records/papers'
    rows=historical['feedback']['before']['items'];seed=historical['seed_ids'][0]
    ids=[seed]+[r['paper']['id'] for r in rows]
    records=out/'records';hashes={}
    for pid in ids:
        shutil.copytree(source/pid,records/'papers'/pid)
        hashes[pid]={p.name:digest(p) for p in (source/pid).glob('*.json')}
    os.environ.update(SCHOLAR_GRAPH_TRACKING_ENABLED='false',SCHOLAR_GRAPH_DEDUP_MODE='off')
    target=next(r['paper']['id'] for r in rows if r['paper']['title'].startswith('BERT:'))
    proof={'source':'Previously genuinely downloaded five-paper corpus; copied unmodified, no synthetic scores or papers', 'source_hashes':hashes,'seed':seed,'target':target,'interfaces':{}}
    with TestClient(create_app(data_dir=records)) as c:
        for v,params in [('v1',{'paper_id':seed,'as_of_year':2026,'page_size':100}),('v2',{'paper_id':seed,'profile_id':'item04-v2'})]:
            before=c.get(f'/api/{v}/recommendations',params=params);before.raise_for_status()
            profile='local' if v=='v1' else 'item04-v2'
            event=c.post(f'/api/{v}/recommendations/feedback',json={'paper_id':target,'seed_paper_id':seed,'vote':'like','profile_id':profile,'as_of_year':2026});event.raise_for_status()
            liked=c.get(f'/api/{v}/recommendations',params=params).json()
            dislike=c.post(f'/api/{v}/recommendations/feedback',json={'paper_id':target,'seed_paper_id':seed,'vote':'dislike','profile_id':profile,'as_of_year':2026});dislike.raise_for_status()
            disliked=c.get(f'/api/{v}/recommendations',params=params).json()
            rank=lambda d:next(i for i,r in enumerate(d['items'],1) if r['paper']['id']==target)
            proof['interfaces'][v]={'before':before.json(),'like_event':event.json(),'after_like':liked,'dislike_event':dislike.json(),'after_dislike':disliked,
                'ranks':{'before':rank(before.json()),'liked':rank(liked),'disliked':rank(disliked)}}
            write(out/'result.json',proof)
            assert rank(liked)<rank(before.json()) and rank(disliked)>rank(liked)
        # The primary v2 content score reproduces 4 -> 1. The legacy graph-heavy
        # score is reported as measured, never retuned to force an old rank.
        assert proof['interfaces']['v2']['ranks']['before']==4 and proof['interfaces']['v2']['ranks']['liked']==1
    with TestClient(create_app(data_dir=records)) as c:
        proof['after_restart']=c.get('/api/v2/recommendations',params={'paper_id':seed,'profile_id':'item04-v2'}).json()
        assert proof['after_restart']['votes']==proof['interfaces']['v2']['after_dislike']['votes']
    write(out/'result.json',proof);print(json.dumps({'passed':True,'ranks':{v:p['ranks'] for v,p in proof['interfaces'].items()}},ensure_ascii=False))
