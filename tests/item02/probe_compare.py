"""Same selected papers and questions across real single/compare/SSE paths."""
import argparse
import json
from pathlib import Path
import time
import httpx
from run_cases import A,B,CASES,BASE

def main():
    p=argparse.ArgumentParser(); p.add_argument('--run',required=True); a=p.parse_args(); out=BASE/a.run; out.mkdir(exist_ok=False)
    rows=[]
    with httpx.Client(base_url='http://127.0.0.1:8060',trust_env=False,timeout=900) as c:
        for name,url,body in [
            ('single-a','/api/v1/papers/'+A+'/qa',{'question':'原始Transformer的Encoder和Decoder分别是什么结构？'}),
            ('single-b','/api/v1/papers/'+B+'/qa',{'question':'BERT使用了什么Transformer结构？'}),
            ('compare-stream','/api/v1/compare/stream',{'paper_ids':[A,B],'question':CASES[5][2]})]:
            started=time.monotonic(); row={'path':name}; rows.append(row)
            if name!='compare-stream':
                r=c.post(url,json=body); row.update(status=r.status_code,result=r.json())
            else:
                raw=[]; event=None
                with c.stream('POST',url,json=body) as r:
                    row['status']=r.status_code
                    for line in r.iter_lines():
                        raw.append(line)
                        if line.startswith('event: '): event=line[7:]
                        elif line.startswith('data: '):
                            value=json.loads(line[6:])
                            if event in ('mode','final','done','error'): row[event]=value
                (out/'compare.sse').write_text('\n'.join(raw),encoding='utf-8')
            row['seconds']=round(time.monotonic()-started,3)
            (out/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
            print(name,row['seconds'],row.get('result',{}).get('refused'),[r['refused'] for r in row.get('final',{}).get('per_paper',[])],flush=True)

if __name__=='__main__': main()
