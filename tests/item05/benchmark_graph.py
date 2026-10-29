"""Measure compact transport against actual full proof transport; preserve all graph facts."""
import argparse,json,time
from common import BASE,client,ready,write
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();out=BASE/a.run;out.mkdir(exist_ok=False)
    ids=[r['paper_id'] for r in json.loads((BASE/'upload-twenty/result.json').read_text(encoding='utf8'))['task']['result']['succeeded']]
    results=[]
    with client() as c:
        ready(c)
        for compact in [False,True,True,True]:
            start=time.monotonic();r=c.post('/api/v2/graph/rebuild',json={'paper_ids':ids,'compact':compact});r.raise_for_status()
            row={'compact':compact,'seconds':round(time.monotonic()-start,6),'response_bytes':len(r.content)};value=r.json()
            if not compact:full=value
            else:
                assert value['nodes']==full['nodes'] and value['edges']==full['edges'] and value['layers']==full['layers']
            results.append(row);write(out/'results.json',results)
        r=c.get('/api/v2/graph',params=[('paper_ids',pid) for pid in ids]);r.raise_for_status();assert r.json()==full
        write(out/'verification.json',{'full_evidence_unchanged_after_compact':True,'node_edge_rank_identity':True})
    print(json.dumps(results))
