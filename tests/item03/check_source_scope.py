"""A full English request must never silently translate only a prior abstract."""
import argparse,json,time
from pathlib import Path
import httpx
BASE=Path(__file__).resolve().parents[2]/'data/item03-20261028'
PID='paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697'
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);args=parser.parse_args();out=BASE/args.run;out.mkdir(exist_ok=False)
    with httpx.Client(base_url='http://127.0.0.1:8080',trust_env=False,timeout=900) as c:
        def wait(tid):
            while True:
                task=c.get('/api/v2/tasks/'+tid).json()
                if task['status'] not in ['queued','running','cancelling']:return task
                time.sleep(.5)
        response=c.post('/api/v2/papers/'+PID+'/translation-tasks',json={'scope':'abstract','target':'zh'});response.raise_for_status();abstract=wait(response.json()['id'])
        assert abstract['status']=='completed'
        (out/'abstract-task.json').write_text(json.dumps(abstract,ensure_ascii=False,indent=2),encoding='utf-8')
        response=c.post('/api/v2/papers/'+PID+'/translation-tasks',json={'scope':'full','target':'en','chinese_task_id':abstract['id']})
        value=response.json(); report={'abstract_segments':len(abstract['result']['translation']['segments']),'full_request_http_status':response.status_code}
        if response.status_code==202:
            full=wait(value['id']);(out/'wrong-scope-full-task.json').write_text(json.dumps(full,ensure_ascii=False,indent=2),encoding='utf-8')
            report.update(full_task_status=full['status'],claimed_full_segments=len((full.get('result') or {}).get('translation',{}).get('segments',[])))
        else:report['error']=value
        report['passed']=response.status_code==422
        (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
        raise SystemExit(0 if report['passed'] else 1)
