"""Observe a scheduler-started real cycle; never invoke the tracking run endpoint."""
import argparse
import json
import time
from common import BASE,client,write
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    out=BASE/a.run;out.mkdir(exist_ok=False)
    with client() as c:
        start=time.monotonic();last=None
        for _ in range(240):
            r=c.get('/api/v2/tracking/status');r.raise_for_status();status=r.json()
            write(out/'status.json',status)
            state=(status['scheduler_details']['run_count'],status['scheduler_details']['last_event'],(status['latest_run'] or {}).get('status'))
            if state!=last:
                print(json.dumps({'elapsed_seconds':round(time.monotonic()-start,3),'scheduler':state[0],'event':state[1],'tracking_status':state[2]},ensure_ascii=False),flush=True);last=state
            event=status['scheduler_details']['last_event'] or {}
            if event.get('event')=='run_finished' and event.get('status')!='skipped':
                write(out/'result.json',{'elapsed_seconds':round(time.monotonic()-start,3),'status':status})
                assert event['status'] in ['completed','partial'],event
                assert status['latest_run']['queries'],status
                break
            time.sleep(2)
        else:raise TimeoutError('No genuine scheduler-completed cycle; latest evidence retained')
