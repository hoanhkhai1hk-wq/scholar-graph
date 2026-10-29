"""Real configured model over exactly the twenty freshly uploaded papers."""
import argparse,json,time
from common import BASE,client,write,wait_task,ready
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--kind',choices=['review','future'],required=True);p.add_argument('--run',required=True);a=p.parse_args()
    out=BASE/a.run;out.mkdir(exist_ok=False)
    ids=[r['paper_id'] for r in json.loads((BASE/'upload-twenty/result.json').read_text(encoding='utf8'))['task']['result']['succeeded']]
    with client() as c:
        ready(c)
        start=time.monotonic();r=c.post('/api/v2/writing/tasks',json={'kind':a.kind,'paper_ids':ids,'idea':'结合这二十篇论文的真实引用网络，生成简短综述。所有论文和引文必须来自所选集合，区分有证据的贡献与尚待验证的设想。' if a.kind=='review' else '提取所选论文原文明确的未来工作，对照较新论文，排除已经尝试过的方向。'});r.raise_for_status();write(out/'submission.json',r.json())
        task=wait_task(c,r.json(),out/'result.json');write(out/'timing.json',{'seconds':round(time.monotonic()-start,3),'kind':a.kind,'status':task['status']})
        result=task.get('result') or {}
        print(json.dumps({'status':task['status'],'kind':a.kind,'sections':len((result.get('document') or {}).get('sections',[])),
            'directions':[{'topic':d['topic'],'decision':d['decision'],'year':d.get('source_year'),'matched_years':[m.get('year') for m in d['matches']]} for d in result.get('future',{}).get('directions',[])],
            'model_calls':len(result.get('metadata',{}).get('model_calls',[])),'error':task.get('error')},ensure_ascii=False))
