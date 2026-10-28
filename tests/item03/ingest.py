"""One official PDF in a fresh item-3 library; no mutation of prior libraries."""
import hashlib,json,time
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[2]; BASE=ROOT/'data/item03-20261028'
if __name__=='__main__':
    source=ROOT/'pdf/1706.03762v7.pdf'; digest=hashlib.sha256(source.read_bytes()).hexdigest()
    with httpx.Client(base_url='http://127.0.0.1:8080',trust_env=False,timeout=90) as client:
        assert client.get('/api/v1/papers').json()['total']==0
        started=time.monotonic()
        with source.open('rb') as file:
            response=client.post('/api/v2/uploads',files=[('files',(source.name,file,'application/pdf'))]); response.raise_for_status()
        identity=response.json()['id']
        while True:
            task=client.get('/api/v2/tasks/'+identity).json()
            if task['status'] not in ['queued','running']: break
            time.sleep(1)
        assert task['status']=='completed',task
        pid=task['result']['succeeded'][0]['paper_id']
        reading=client.get('/api/v2/papers/'+pid+'/reading').json()
        report={'source':source.name,'sha256':digest,'unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==digest,
                'paper_id':pid,'seconds':round(time.monotonic()-started,3),'pages':reading['paper']['page_count'],
                'chunks':reading['total_chunks'],'task':task}
        (BASE/'ingestion.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k!='task'},ensure_ascii=False))
