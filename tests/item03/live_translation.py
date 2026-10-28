"""Real service/model probes. Complete translated documents stay local only."""
import argparse,json,hashlib,time,sys
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[2]; BASE=ROOT/'data/item03-20261028'; sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.validation import ContractGate
from scholar_graph.translation import select_chunks,protect,check_numbers
PID='paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697'


def save(path,value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def verify(value,bundle,scope,section=None,ids=None,chinese=None):
    expected=select_chunks(bundle,scope,section,ids); sources={c['chunk_id']:c for c in expected}
    checks={'coverage':[s['source_chunk_id'] for s in value['segments']]==[c['chunk_id'] for c in expected],
            'anchors':True,'protected_spans':True,'numbers':True,'nonempty':True}
    prior={s['source_chunk_id']:s['translated_text'] for s in chinese['segments']} if chinese else {}
    for s in value['segments']:
        c=sources[s['source_chunk_id']]
        assert all(s[k]==c[k] for k in ['paper_id','page_number','section_path','type'])
        source=prior.get(c['chunk_id'],c['text']); assert s['source_text']==source
        assert s['translated_text'].strip()
        _,spans=protect(source,formula=c['type']=='formula',numbers=False)
        assert all(text in s['translated_text'] for text in spans.values())
        check_numbers(source,s['translated_text'],c['chunk_id'])
    checks['markdown_coverage']=all(f'<a id="{s["source_chunk_id"]}"></a>' in value['markdown'] for s in value['segments']) if scope=='full' else value['markdown'] is None
    calls=value['metadata'].get('model_calls',[])
    checks['real_model']=bool(calls) and all(x['provider']=='deepseek' and x['http_status']==200 and x['status']=='succeeded' for x in calls)
    return checks


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--run',required=True); parser.add_argument('--direct-full',action='store_true'); args=parser.parse_args()
    out=BASE/args.run; out.mkdir(exist_ok=False); report={'cases':[]}
    repo=ApiRepository(BASE/'records',ContractGate()); bundle=repo.paper(PID)
    full_id=json.loads((BASE/'full-task-browser.json').read_text())['taskId']
    with httpx.Client(base_url='http://127.0.0.1:8080',trust_env=False,timeout=1000) as c:
        task=c.get('/api/v2/tasks/'+full_id).json(); assert task['status']=='completed' and not task['result']['failed_count']
        full=task['result']['translation']; save(out/'full-zh-response.json',full); save(out/'full-zh-task.json',task)
        full_started=time.monotonic()
        if args.direct_full:
            direct=c.post('/api/v1/papers/'+PID+'/translate',json={'scope':'full','target':'zh'}); direct.raise_for_status(); full=direct.json(); save(out/'full-zh-response.json',full)
        report['cases'].append({'case':'full_zh','via':'real_direct_v1' if args.direct_full else 'real_browser_v2_task','task_id':None if args.direct_full else full_id,
                               'seconds':round(time.monotonic()-full_started,3) if args.direct_full else None,'checks':verify(full,bundle,'full'),'segments':len(full['segments'])})
        save(out/'results.json',report); print(json.dumps(report['cases'][-1],ensure_ascii=False),flush=True)
        selection=next(x for x in bundle['chunks'] if x['text'].startswith('Instead of performing'))
        for name,body in [('abstract_zh',{'scope':'abstract','target':'zh'}),
                          ('section_zh',{'scope':'section','target':'zh','section_path':['3 Model Architecture','3.2 Attention','3.2.2 Multi-Head Attention']}),
                          ('selection_zh',{'scope':'selection','target':'zh','chunk_ids':[selection['chunk_id']]}),
                          ('abstract_en',{'scope':'abstract','target':'en','source_translation':full})]:
            started=time.monotonic(); response=c.post('/api/v1/papers/'+PID+'/translate',json=body); value=response.json()
            row={'case':name,'status':response.status_code,'seconds':round(time.monotonic()-started,3)}
            if response.status_code==200:
                save(out/(name+'-response.json'),value)
                row.update(segments=len(value['segments']),checks=verify(value,bundle,body['scope'],body.get('section_path'),body.get('chunk_ids'),full if body['target']=='en' else None))
            else: row['error']=value
            report['cases'].append(row); save(out/'results.json',report); print(json.dumps(row,ensure_ascii=False),flush=True)
        if args.direct_full:
            started=time.monotonic(); response=c.post('/api/v1/papers/'+PID+'/translate',json={'scope':'full','target':'en','source_translation':full}); response.raise_for_status(); value=response.json(); save(out/'full-en-response.json',value)
            row={'case':'full_en','via':'real_direct_v1','http_status':response.status_code,'seconds':round(time.monotonic()-started,3),'segments':len(value['segments']),'checks':verify(value,bundle,'full',chinese=full)}
            report['cases'].append(row); report['passed']=len(report['cases'])==6 and all(bool(r.get('checks')) and all(r['checks'].values()) for r in report['cases']); save(out/'results.json',report); print(json.dumps(row,ensure_ascii=False),flush=True)
            return 0 if report['passed'] else 1
        response=c.post('/api/v2/papers/'+PID+'/translation-tasks',json={'scope':'full','target':'en','chinese_task_id':full_id}); response.raise_for_status()
        tid=response.json()['id']; save(out/'full-en-task-id.json',{'id':tid}); started=time.monotonic()
        previous=None
        while True:
            task=c.get('/api/v2/tasks/'+tid).json(); state=[task['status'],task['progress']['completed_units']]
            if state!=previous: print(json.dumps({'full_en_status':state,'progress':task['progress']},ensure_ascii=False),flush=True); previous=state
            if task['status'] not in ['queued','running','cancelling']: break
            time.sleep(2)
        save(out/'full-en-task.json',task)
        row={'case':'full_en','task_status':task['status'],'seconds':round(time.monotonic()-started,3),'failed':task.get('result',{}).get('failed_count')}
        if task['status']=='completed':
            value=task['result']['translation']; save(out/'full-en-response.json',value); row.update(segments=len(value['segments']),checks=verify(value,bundle,'full',chinese=full))
        report['cases'].append(row); save(out/'results.json',report); print(json.dumps(row,ensure_ascii=False),flush=True)
    report['passed']=len(report['cases'])==6 and all(all(r.get('checks',{}).values()) and bool(r.get('checks')) for r in report['cases']); save(out/'results.json',report)
    return 0 if report['passed'] else 1


if __name__=='__main__': raise SystemExit(main())
