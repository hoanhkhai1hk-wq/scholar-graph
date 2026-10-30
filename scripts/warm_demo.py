"""Warm selected real papers and validate an actual comparison before a demo.

This calls the configured backend, never accepts or prints a provider API key.
Token deltas are explicitly drafts; only validated final/done count as ready.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import httpx


def run(base_url,paper_ids,question,timeout=900,output=None,require_vector=False):
    report={'base_url':base_url,'paper_ids':paper_ids,'question':question,
            'events':[],'ready':False,'first_event_seconds':None,'first_delta_seconds':None}
    def save():
        if output:
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    with httpx.Client(base_url=base_url,trust_env=False,timeout=httpx.Timeout(30,read=60)) as client:
        system=client.get('/api/v2/system');system.raise_for_status()
        configured=system.json().get('model_configured',False)
        report['key_status']='KEY_SET' if configured else 'CONFIG_INCOMPLETE'
        if not configured:raise RuntimeError('模型配置未就绪；请配置本地.env和override后重建backend。')
        report['reading']=[]
        for pid in paper_ids:
            started=time.perf_counter();r=client.get('/api/v2/papers/'+pid+'/reading');r.raise_for_status()
            report['reading'].append({'paper_id':pid,'seconds':round(time.perf_counter()-started,6),'chunks':r.json()['total_chunks']})
        started=time.perf_counter();name=None;final=None;done=None
        with client.stream('POST','/api/v1/compare/stream',json={'paper_ids':paper_ids,'question':question}) as response:
            response.raise_for_status();report['http_status']=response.status_code
            for line in response.iter_lines():
                elapsed=time.perf_counter()-started
                if elapsed>timeout:raise RuntimeError('预热超过指定时限；未标记就绪。')
                if line.startswith('event: '):name=line[7:]
                elif line.startswith('data: '):
                    value=json.loads(line[6:]);row={'event':name,'seconds':round(elapsed,6)}
                    if report['first_event_seconds'] is None:report['first_event_seconds']=row['seconds']
                    if name=='token':
                        delta=value.get('delta','');row.update(chars=len(delta),sha256=hashlib.sha256(delta.encode()).hexdigest())
                        if delta and report['first_delta_seconds'] is None:report['first_delta_seconds']=row['seconds']
                    elif name=='final':final=value;row.update(refused=[x['refused'] for x in value.get('per_paper',[])],anchor_count=sum(len(x['anchors']) for x in value.get('per_paper',[])))
                    elif name=='done':done=value;row.update(verified=value.get('verified'),status=value.get('status'));report['metadata']=value.get('metadata')
                    elif name=='error':report['error']=value
                    else:row['data']=value
                    report['events'].append(row);save()
        report['seconds']=round(time.perf_counter()-started,6)
        report['retrieval_method']=(report.get('metadata') or {}).get('method')
        report['ranking_method']=(report.get('metadata') or {}).get('ranking_method')
        report['ready']=bool(final and done and done.get('verified') and done.get('status')=='completed'
                             and final.get('per_paper') and all(not r['refused'] and r['anchors'] for r in final['per_paper'])
                             and report['first_delta_seconds'] is not None and 'error' not in report)
        if require_vector and report['retrieval_method'] not in ('hybrid','vector'):
            report['ready']=False
        report['final']=final;save()
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-url',default='http://127.0.0.1:8000')
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--paper-ids',nargs='+')
    group.add_argument('--paper-titles',nargs='+')
    p.add_argument('--require-vector',action='store_true',help='向量不可用时不报告hybrid预热就绪。')
    p.add_argument('--question',required=True)
    p.add_argument('--timeout-seconds',type=float,default=900)
    p.add_argument('--output',type=Path,default=Path('data/demo-warmup.json'))
    a=p.parse_args()
    try:
        if a.paper_titles:
            a.paper_ids=[]
            with httpx.Client(base_url=a.base_url,trust_env=False,timeout=30) as client:
                for title in a.paper_titles:
                    r=client.get('/api/v2/papers',params={'title':title,'page_size':100});r.raise_for_status()
                    matches=[v['paper']['id'] for v in r.json()['items'] if (v['paper']['title'] or '').strip().casefold()==title.strip().casefold()]
                    if len(matches)!=1:raise RuntimeError('标题没有唯一匹配，请先导入对应论文或使用--paper-ids：'+title)
                    a.paper_ids.append(matches[0])
        if not 2<=len(set(a.paper_ids))==len(a.paper_ids)<=10:p.error('请选择2–10篇不同的真实论文。')
        result=run(a.base_url.rstrip('/'),a.paper_ids,a.question,a.timeout_seconds,a.output,a.require_vector)
        print(json.dumps({k:result[k] for k in ['key_status','ready','retrieval_method','ranking_method','first_event_seconds','first_delta_seconds','seconds']},ensure_ascii=False))
        raise SystemExit(0 if result['ready'] else 1)
    except (RuntimeError,httpx.HTTPError) as error:
        print('预热失败：'+str(error),file=sys.stderr);raise SystemExit(1)
