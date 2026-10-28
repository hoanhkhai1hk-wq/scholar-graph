"""Measure cold/warm real HTTP calls; verify cached base results are identical."""
import json
import time
from common import BASE,client,write
if __name__=='__main__':
    out=BASE/'recommendation-performance';out.mkdir(exist_ok=False)
    seed=json.loads((BASE/'seed-upload.json').read_text(encoding='utf-8'))['paper_id']
    timings=[];responses=[]
    with client() as c:
        for index in range(3):
            start=time.monotonic();r=c.get('/api/v2/recommendations',params={'paper_id':seed,'profile_id':'item04-performance'});r.raise_for_status()
            value=r.json();elapsed=round(time.monotonic()-start,6);responses.append(value)
            timings.append({'call':index+1,'elapsed_seconds':elapsed,'items':len(value['items']),'diagnostics':value['diagnostics']})
            write(out/f'{index+1}-response.json',value)
            print(json.dumps(timings[-1]),flush=True)
        assert responses[0]['items']==responses[1]['items']==responses[2]['items']
        assert timings[0]['diagnostics']['base_cache_hit'] is False
        assert all(t['diagnostics']['base_cache_hit'] for t in timings[1:])
        write(out/'result.json',{'timings':timings,'all_items_equal':True,'method':'Same service, same exact library signature, empty independent profile, genuine HTTP requests; cold includes full graph recomputation.'})
