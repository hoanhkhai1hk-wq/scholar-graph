"""Explicit, reviewable reference-sidecar rebuilding through the real v2 operation."""
import argparse,json,time
from common import BASE,client,write,ready
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    out=BASE/a.run;out.mkdir(exist_ok=False)
    ids=[r['paper_id'] for r in json.loads((BASE/'upload-twenty/result.json').read_text(encoding='utf8'))['task']['result']['succeeded']]
    with client() as c:
        ready(c)
        start=time.monotonic();r=c.post('/api/v2/graph/rebuild',json={'paper_ids':ids});write(out/'response.json',r.json());r.raise_for_status()
        g=r.json();write(out/'summary.json',{'seconds':round(time.monotonic()-start,3),'nodes':len(g['nodes']),'edges':len(g['edges'])});print((out/'summary.json').read_text())
