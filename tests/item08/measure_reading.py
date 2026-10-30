"""Measure actual legacy pagination and current v2 cold/warm page reads."""
import argparse
import time
import httpx
from common import BASE,API,write

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--legacy',action='store_true');a=p.parse_args()
    samples=__import__('json').loads((BASE/'samples.json').read_text(encoding='utf8'))
    book=next(p for p in samples if p['page_count']==541);pid=book['id'];out=BASE/a.run;out.mkdir(exist_ok=False)
    report={'paper_id':pid,'page_count':541,'samples':[]}
    with httpx.Client(base_url=API,trust_env=False,timeout=600) as c:
        if a.legacy:
            started=time.perf_counter();page=1;chunks=[];calls=0;size=0
            while True:
                r=c.get(f'/api/v1/papers/{pid}/chunks',params={'page':page,'page_size':100});r.raise_for_status();j=r.json();chunks+=j['items'];calls+=1;size+=len(r.content)
                if not j['has_next']:break
                page+=1
            report['legacy']={'requests':calls,'chunks':len(chunks),'bytes':size,'elapsed_ms':round((time.perf_counter()-started)*1000,3)}
            write(out/'report.json',report)
        for name,number,navigation in [('cold_navigation',1,True),('warm_navigation',1,True),('jump_300',300,False),('jump_541',541,False),('repeat_300',300,False)]:
            started=time.perf_counter();r=c.get(f'/api/v2/papers/{pid}/reading',params={'physical_page':number,'include_navigation':str(navigation).lower()});r.raise_for_status();j=r.json()
            assert j['paper']['page_count']==541 and all(ch['page_number']==number for ch in j['chunks'])
            row={'name':name,'physical_page':number,'navigation':navigation,'ms':round((time.perf_counter()-started)*1000,3),'bytes':len(r.content),'chunks':len(j['chunks']),'outline':len(j['outline']),'total_chunks':j['total_chunks']}
            report['samples'].append(row);write(out/'report.json',report);print(row,flush=True)
