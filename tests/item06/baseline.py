"""Real writing, topology-format and chart probes before implementation changes."""
import json,time,base64,sys
from common import BASE,write,client,ready,wait_task
IDEA='以Transformer为基础，结合低秩适配和人类反馈，提出有限算力下科研问答系统的验证方案。分别引用三篇所选论文的真实贡献，明确区分已有结论与待验证设想，不能捏造实验结果。'
if __name__=='__main__':
    out=BASE/('baseline-charts' if '--charts-only' in sys.argv else 'baseline');out.mkdir(exist_ok=False);papers=json.loads((BASE/'selected-papers.json').read_text(encoding='utf8'));ids=[p['paper_id'] for p in papers]
    with client() as c:
        ready(c)
        if '--charts-only' not in sys.argv:
            start=time.monotonic();r=c.post('/api/v2/writing/tasks',json={'paper_ids':ids,'idea':IDEA,'kind':'outline'});r.raise_for_status();t=wait_task(c,r.json(),out/'outline-task.json');write(out/'outline-timing.json',{'seconds':round(time.monotonic()-start,3),'status':t['status']})
            print(json.dumps({'outline':t['status'],'references':(t.get('result') or {}).get('document',{}).get('references',[]),'error':t.get('error')},ensure_ascii=False),flush=True)
        raw=(BASE/'matrix-timings.csv').read_bytes()
        for kind in ['table','line','bar','radar3d']:
            start=time.monotonic();r=c.post('/api/v2/charts',files={'file':('actual-matrix-timings.csv',raw,'text/csv')},data={'kind':kind,'columns':json.dumps(['matmul_ms','add_ms','multiply_ms']),'label_column':'dimension'});r.raise_for_status();v=r.json();write(out/(kind+'.json'),v)
            if v['image']:(out/(kind+'.png')).write_bytes(base64.b64decode(v['image'].split(',')[1]))
            print(json.dumps({'kind':kind,'seconds':round(time.monotonic()-start,3),'captions':v['captions']},ensure_ascii=False),flush=True)
        attention=next(p for p in papers if p['filename']=='1706.03762v7.pdf')['paper_id'];r=c.post('/api/v1/topologies',json={'paper_ids':[attention],'formats':['matplotlib'],'logic':{'nodes':[{'id':'input','label':'Input','source_chunk_ids':[attention+'-p0001-c00010']}],'edges':[]}})
        write(out/'matplotlib-request.json',{'http_status':r.status_code,'response':r.json()});print('Matplotlib status',r.status_code,flush=True)
