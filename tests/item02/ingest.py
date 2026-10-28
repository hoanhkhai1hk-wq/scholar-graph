"""Real official files, fresh isolated HTTP ingestion, no provider credentials in output."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import httpx

ROOT=Path(__file__).resolve().parents[2]; BASE=ROOT/'data/item02-20261028'
FILES=['1706.03762v7.pdf','N19-1423.pdf','language_understanding_paper.pdf',
       'language_models_are_unsupervised_multitask_learners.pdf','2005.14165v4.pdf']

def main():
    output=BASE/'ingestion.json'
    if output.exists(): raise FileExistsError(output)
    report={'at':datetime.now(timezone.utc).isoformat(),'passed':False,'files':[]}
    def save(): output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    with httpx.Client(base_url='http://127.0.0.1:8060/api/v2',timeout=60,trust_env=False) as c:
        def req(method,path,**kw):
            r=c.request(method,path,**kw); r.raise_for_status(); return r.json()
        assert req('GET','/papers')['total']==0
        for filename in FILES:
            source=ROOT/'pdf'/filename; started=time.monotonic(); digest=hashlib.sha256(source.read_bytes()).hexdigest()
            with source.open('rb') as f: task=req('POST','/uploads',files={'files':(filename,f,'application/pdf')})
            print('submitted',filename,task['id'],flush=True)
            while task['status'] in ('queued','running','cancelling'):
                if time.monotonic()-started>1200: raise TimeoutError(filename)
                time.sleep(1); task=req('GET','/tasks/'+task['id'])
            row={'filename':filename,'source_sha256':digest,'task_id':task['id'],'status':task['status'],'seconds':round(time.monotonic()-started,3)}
            report['files'].append(row); save()
            if task['status']!='completed': raise RuntimeError('Parsing failed; see real task result')
            pid=task['result']['succeeded'][0]['paper_id']; meta=req('GET','/papers/'+pid)
            row.update(paper_id=pid,pages=meta['paper']['page_count'],title=meta['paper']['title'],input_unchanged=hashlib.sha256(source.read_bytes()).hexdigest()==digest)
            save(); print(json.dumps(row,ensure_ascii=False),flush=True)
    report['passed']=all(r['status']=='completed' and r['input_unchanged'] for r in report['files']); save()

if __name__=='__main__': main()
