"""Retry actual failed references after fixes; preserve original batch and numbering."""
import argparse
import json
import time
from common import BASE,client,wait_task,write
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);args=p.parse_args()
    out=BASE/args.run;out.mkdir(exist_ok=False)
    seed=json.loads((BASE/'seed-upload.json').read_text(encoding='utf-8'))['paper_id']
    original=json.loads((BASE/'batch-all/task.json').read_text(encoding='utf-8'))['result']
    plan=json.loads((BASE/'reference-plan-before.json').read_text(encoding='utf-8'))
    failed_names={i['filename'] for i in original['failed']}
    nums=[i['reference']['number'] for i in plan if i['reference']['title'] in failed_names]
    with client() as c:
        start=time.monotonic();r=c.post(f'/api/v2/papers/{seed}/reference-tasks',json={'reference_numbers':nums});r.raise_for_status()
        task=wait_task(c,r.json()['id'],out/'task.json')
        result={'reference_numbers':nums,'elapsed_seconds':round(time.monotonic()-start,3),'status':task['status'],'result':task['result']}
        write(out/'result.json',result);print(json.dumps({k:v for k,v in result.items() if k!='result'}))
