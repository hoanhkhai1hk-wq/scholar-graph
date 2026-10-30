"""Cold, explicit warmup, then independent real-model comparison samples."""
import argparse
import importlib.util
import time
import httpx
from common import ROOT,BASE,API,write

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--phase',choices=['cold','warm','warmup'],required=True);a=p.parse_args()
    spec=importlib.util.spec_from_file_location('warm_demo',ROOT/'scripts/warm_demo.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with httpx.Client(base_url=API,trust_env=False,timeout=30) as c:
        papers=c.get('/api/v2/papers?page_size=100').json()['items']
    transformer=next(v['paper']['id'] for v in papers if v['paper']['title']=='Attention Is All You Need')
    bert=next(v['paper']['id'] for v in papers if (v['paper']['title'] or '').startswith('BERT:'))
    questions={'cold':'BERT与Transformer Encoder是什么承袭关系？BERT保留和丢弃了哪些部分？',
               'warmup':'请根据两篇原文解释BERT与Transformer的Encoder结构关系以及未采用的部分。',
               'warm':'原始Transformer和BERT的Encoder结构有哪些联系，BERT没有沿用哪些部分？'}
    out=BASE/a.run;out.mkdir(exist_ok=False)
    result=module.run(API,[transformer,bert],questions[a.phase],output=out/'report.json')
    write(out/'summary.json',{k:result[k] for k in ['key_status','ready','first_event_seconds','first_delta_seconds','seconds']})
    print({k:result[k] for k in ['ready','first_event_seconds','first_delta_seconds','seconds']},flush=True)
    raise SystemExit(0 if result['ready'] else 1)
