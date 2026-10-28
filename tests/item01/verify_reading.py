"""Real all-page HTTP access and byte/time measurements, with no hidden retries."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import httpx

ROOT=Path(__file__).resolve().parents[2]
SAMPLES=[('v1','paper-0a9bff1be3575cf9fe26a4a3d3a9175bc791ecec90de8b9deba4cff75d2b9476'),
         ('scan','paper-64094fe169dd4ff454f579e9f197298df1c118c24b71b1f1ca8bb218c9e4801d'),
         ('book','paper-f8237d393163900fa8e43210e680a3f987b45ccac7750b372e156fae3df0bf32')]

def main():
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
    report={'at':datetime.now(timezone.utc).isoformat(),'passed':False,'hidden_retries':0,'samples':[]}
    def save(): a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if a.output.exists(): raise FileExistsError(a.output)
    save()
    try:
        with httpx.Client(base_url='http://127.0.0.1:8040/api/v2',trust_env=False,timeout=60) as c:
            for name,pid in SAMPLES:
                meta=c.get('/papers/'+pid); meta.raise_for_status(); pages=meta.json()['paper']['page_count']
                row={'sample':name,'physical_pages':pages,'pages':[]}; report['samples'].append(row)
                for page in range(1,pages+1):
                    started=time.monotonic(); r=c.get(f'/papers/{pid}/reading',params={'physical_page':page,'include_navigation':'false'}); r.raise_for_status()
                    value=r.json()
                    if value['page_number']!=page or any(x['page_number']!=page for x in value['chunks']): raise ValueError('Page locator mismatch')
                    row['pages'].append({'page':page,'chunks':len(value['chunks']),'bytes':len(r.content),'seconds':round(time.monotonic()-started,4)})
                    if page%50==0: save(); print(name,page,'/',pages,flush=True)
                row['verified_pages']=len(row['pages']); row['chunks']=sum(x['chunks'] for x in row['pages'])
                row['empty_pages']=[x['page'] for x in row['pages'] if not x['chunks']]; save()
            pid=SAMPLES[-1][1]; report['last_page_measurements']=[]
            for include in [True,False]*3:
                started=time.monotonic(); r=c.get(f'/papers/{pid}/reading',params={'physical_page':541,'include_navigation':str(include).lower()}); r.raise_for_status()
                value=r.json(); report['last_page_measurements'].append({'include_navigation':include,'status':r.status_code,
                    'bytes':len(r.content),'seconds':round(time.monotonic()-started,4),'chunks':len(value['chunks'])})
            report['passed']=True
    except Exception as e: report['error']={'type':type(e).__name__,'message':str(e)}
    finally: report['finished_at']=datetime.now(timezone.utc).isoformat(); save()
    print(json.dumps({k:v for k,v in report.items() if k!='samples'},ensure_ascii=False),flush=True)
    return 0 if report['passed'] else 1

if __name__=='__main__': raise SystemExit(main())
