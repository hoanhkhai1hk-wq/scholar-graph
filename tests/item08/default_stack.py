"""Exercise the documented default Compose in a separate empty volume/project."""
import json
import subprocess
import sys
import time
import httpx
import ipaddress
from common import ROOT,BASE,configured_environment,write

def task(client,identity,where):
    started=time.perf_counter()
    while time.perf_counter()-started<900:
        r=client.get('/api/v2/tasks/'+identity);r.raise_for_status();value=r.json();write(where,value)
        if value['status'] not in ['queued','running','cancelling']:return value
        time.sleep(.5)
    raise RuntimeError('Real task did not finish within test budget')

if __name__=='__main__':
    env=configured_environment();env.update(COMPOSE_PROJECT_NAME='scholar-graph-item08-default',SCHOLAR_GRAPH_BACKEND_PORT='8220',SCHOLAR_GRAPH_FRONTEND_PORT='3540',SCHOLAR_GRAPH_TRACKING_ENABLED='false')
    with (BASE/'fresh-default-up.log').open('w',encoding='utf8') as out:
        subprocess.run(['docker','compose','up','-d','--no-build','--wait'],cwd=ROOT,env=env,stdout=out,stderr=subprocess.STDOUT,check=True)
    report={'project':env['COMPOSE_PROJECT_NAME'],'separate_original_volume':True,'model_tests':[]}
    for service in ['backend','frontend']:
        name=env['COMPOSE_PROJECT_NAME']+'-'+service+'-1';j=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
        report[service]={'health':j['State']['Health']['Status'],'oom_killed':j['State']['OOMKilled']}
        assert report[service]['health']=='healthy'
    dns=subprocess.check_output(['docker','exec',env['COMPOSE_PROJECT_NAME']+'-frontend-1','getent','hosts','backend'],text=True).strip();assert ipaddress.ip_address(dns.split()[0]).is_private;report['dns']=dns
    raw=subprocess.check_output(['docker','exec',env['COMPOSE_PROJECT_NAME']+'-backend-1','python','-c',"import os;print('KEY_SET' if os.environ.get('DEEPSEEK_API_KEY') else 'KEY_MISSING')"],text=True).strip();assert raw=='KEY_SET';report['key_status']=raw
    with httpx.Client(base_url='http://127.0.0.1:8220',trust_env=False,timeout=120) as c:
        before=c.get('/api/v2/papers').json()['total'];assert before==0;report['initial_papers']=before
        # Copying frozen records via the project-owned volume keeps this test
        # focused on deployment/translation, not a repeat of parsing acceptance.
        source=ROOT/'data/item06-20261029/records/papers';pid='paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697'
        name=env['COMPOSE_PROJECT_NAME']+'-backend-1'
        subprocess.run(['docker','exec',name,'mkdir','-p','/app/data/records/papers'],check=True,stdout=subprocess.DEVNULL)
        subprocess.run(['docker','cp',str(source/pid),name+':/app/data/records/papers/'+pid],check=True,stdout=subprocess.DEVNULL)
        for scope in ['abstract','full']:
            started=time.perf_counter();r=c.post('/api/v2/papers/'+pid+'/translation-tasks',json={'scope':scope,'target':'zh'});r.raise_for_status();value=task(c,r.json()['id'],BASE/('fresh-'+scope+'-task.private.json'))
            tr=(value.get('result') or {}).get('translation',{});m=tr.get('metadata',{})
            row={'scope':scope,'status':value['status'],'seconds':round(time.perf_counter()-started,6),'expected_segments':m.get('expected_segments'),'translated_segments':m.get('translated_segments'),'cache_hits':m.get('cache_hits'),'complete':m.get('complete'),'model_calls':m.get('model_calls'),'provider':m.get('provider')}
            report['model_tests'].append(row);write(BASE/'default-stack.json',report)
            assert value['status']=='completed' and m.get('complete') is True and m['translated_segments']==m['expected_segments']
            assert tr['segments'] and m.get('provider')=='deepseek'
    report['passed']=True;write(BASE/'default-stack.json',report);print(json.dumps({'passed':True,'key_status':raw,'dns':dns,'translations':[{k:r[k] for k in ['scope','status','seconds','expected_segments','translated_segments','cache_hits']} for r in report['model_tests']]}))
