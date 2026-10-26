"""Observe real timer runs after uploads release ingestion; never trigger a POST."""
import json
import subprocess


def finish_timer_observation(result,compose,checkout,env):
    result['probe_snapshot_before_timer_wait']={k:result.get(k) for k in ('passed','automatic_timer_triggered')}
    otherwise_passed=(result['regression']['exit_code']==0 and result['model_download']['exit_code']==0
        and all(c['passed'] for c in result['cases'].values())
        and result['no_key_qa']['http_status']==200 and not result['no_key_qa']['body'].get('refused',True))
    if not otherwise_passed:
        return
    code="""import json,pathlib,sqlite3,time,httpx
root=pathlib.Path('/app/data/records/tracking'); start=time.monotonic(); runs=[]
while time.monotonic()-start<600:
 events=[json.loads(x) for x in (root/'scheduler-events.jsonl').read_text().splitlines()]
 automatic={e.get('run_id') for e in events if e['event']=='run_finished'}
 with sqlite3.connect(root/'state.sqlite3') as db:
  all_runs=[json.loads(r[0]) for r in db.execute('SELECT payload FROM runs ORDER BY started')]
 runs=[r for r in all_runs if r['run_id'] in automatic and r.get('queries') and r.get('finished_at')]
 if len(runs)>=2: break
 time.sleep(5)
status=httpx.get('http://127.0.0.1:8000/api/v1/retrieval/tracking/status',timeout=30,trust_env=False).json()
print(json.dumps({'automatic_public_runs':runs,'scheduler_events':events,'scheduler':status,
 'timer_observation_seconds':round(time.monotonic()-start,6)}))
"""
    text=subprocess.check_output(compose+['exec','-T','backend','python','-c',code],
        cwd=checkout,env=env,text=True,encoding='utf-8',timeout=660)
    result.update(json.loads(text))
    result['automatic_timer_triggered']=len(result['automatic_public_runs'])>=2
    result['passed']=otherwise_passed and result['automatic_timer_triggered']
