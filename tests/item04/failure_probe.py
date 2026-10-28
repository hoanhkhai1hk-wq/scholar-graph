"""Actual connection-refused proxy fault, never a mocked response or fake candidate."""
import argparse
import json
import time
import httpx
from common import BASE, wait_task, write

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--expect',required=True,choices=['before','after']);a=p.parse_args()
    out=BASE/a.run;out.mkdir(exist_ok=False)
    pid=json.loads((BASE/'seed-upload.json').read_text(encoding='utf-8'))['paper_id']
    with httpx.Client(base_url='http://127.0.0.1:8110',trust_env=False,timeout=60) as c:
        start=time.monotonic();r=c.post('/api/v2/tracking/tasks',json={'paper_ids':[pid],'max_candidates':3,'max_imports':1});r.raise_for_status()
        task=wait_task(c,r.json()['id'],out/'task.json')
        status=c.get('/api/v2/tracking/status').json();write(out/'status.json',status)
        value={'fault':'Actual httpx outbound TCP connection to closed proxy 127.0.0.1:9; no response mocking','task_id':task['id'],
            'outer_status':task['status'],'tracking_status':task['result']['tracking']['status'],
            'query_count':len(task['result']['tracking']['queries']),'errors':task['result']['tracking']['errors'],
            'elapsed_seconds':round(time.monotonic()-start,3)}
        value['passed']=(task['status']=='failed' and value['tracking_status']=='failed' and len(value['errors'])>0)
        write(out/'result.json',value);print(json.dumps(value,ensure_ascii=False))
        if a.expect=='after':assert value['passed'],value
