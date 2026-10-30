"""Actual task runners: invalid translation payload and refused TCP arXiv proxy."""
import argparse
import time
import httpx
from common import BASE,write
PID='paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697'

def wait(client,identity):
    started=time.perf_counter()
    while time.perf_counter()-started<120:
        r=client.get('/api/v2/tasks/'+identity);r.raise_for_status();j=r.json()
        if j['status'] not in ['queued','running','cancelling']:return j
        time.sleep(.2)
    raise RuntimeError('Task did not finish within the actual test budget')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();out=BASE/a.run;out.mkdir(exist_ok=False)
    report={'faults':{'translation':'Test-only httpx transport returns empty translations; dummy key, no actual model invocation',
                      'arxiv':'Actual outbound TCP connection refused at local proxy127.0.0.1:9; no candidate response mocked'},'tasks':{}}
    with httpx.Client(base_url='http://127.0.0.1:8210',trust_env=False,timeout=60) as c:
        for name,path,body in [('translation','/api/v2/papers/'+PID+'/translation-tasks',{'scope':'abstract','target':'zh'}),
                               ('tracking','/api/v2/tracking/tasks',{'paper_ids':[PID],'max_candidates':3,'max_imports':1}),
                               ('fetch','/api/v2/acquisition/tasks',{'title':'Rethinking the Inception Architecture for Computer Vision'})]:
            started=time.perf_counter();r=c.post(path,json=body);r.raise_for_status();task=wait(c,r.json()['id']);report['tasks'][name]=task
            assert task['status']=='failed',(name,task)
            print(name,task['status'],round(time.perf_counter()-started,3),flush=True);write(out/'report.json',report)
    report['passed']=True;write(out/'report.json',report)
