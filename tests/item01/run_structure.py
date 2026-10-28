"""Actual local layout and formula tasks on the official v1 paper."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import httpx

ROOT=Path(__file__).resolve().parents[2]
PID='paper-0a9bff1be3575cf9fe26a4a3d3a9175bc791ecec90de8b9deba4cff75d2b9476'

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--run',required=True)
    args=parser.parse_args(); out=(ROOT/'data/item01-20261028'/args.run).resolve()
    if not out.is_relative_to(ROOT/'data/item01-20261028'): raise ValueError('Invalid evidence path')
    out.mkdir(parents=True,exist_ok=False)
    report={'started_at':datetime.now(timezone.utc).isoformat(),'passed_execution':False,'tasks':[]}
    def save(): (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        with httpx.Client(base_url='http://127.0.0.1:8040/api/v2',trust_env=False,timeout=60) as c:
            def req(method,path):
                r=c.request(method,path); r.raise_for_status(); return r.json()
            for mode in ('layout','formula'):
                started=time.monotonic(); task=req('POST',f'/papers/{PID}/{mode}-tasks')
                row={'kind':mode,'id':task['id']}; report['tasks'].append(row); save()
                previous=None
                while task['status'] in ('queued','running','cancelling'):
                    if time.monotonic()-started>1800: raise TimeoutError('Task timed out')
                    time.sleep(1); task=req('GET','/tasks/'+task['id'])
                    if task.get('progress')!=previous:
                        previous=task.get('progress'); print(mode,task['status'],previous,flush=True)
                (out/(mode+'-task.json')).write_text(json.dumps(task,ensure_ascii=False,indent=2),encoding='utf-8')
                row.update(status=task['status'],elapsed_seconds=round(time.monotonic()-started,3),error=task.get('error')); save()
                if task['status']!='completed': raise RuntimeError(mode+' did not fully complete')
            for name,path in [('structure',f'/papers/{PID}/structure'),('formulas',f'/papers/{PID}/formulas'),
                              ('metadata',f'/papers/{PID}')]:
                (out/(name+'.json')).write_text(json.dumps(req('GET',path),ensure_ascii=False,indent=2),encoding='utf-8')
            report['passed_execution']=True
    except Exception as e: report['error']={'type':type(e).__name__,'message':str(e)}
    finally: report['finished_at']=datetime.now(timezone.utc).isoformat(); save()
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return 0 if report['passed_execution'] else 1

if __name__=='__main__': raise SystemExit(main())
