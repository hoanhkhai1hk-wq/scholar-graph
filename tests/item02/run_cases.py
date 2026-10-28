"""Real model/SSE acceptance; correctness review stays separate from protocol checks."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.parse import unquote
import httpx

ROOT=Path(__file__).resolve().parents[2]; BASE=ROOT/'data/item02-20261028'
A='paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697'
B='paper-987545ffb087f1ece898142c403a516baeabeb70ce19089397fac6f7db12c3d4'
G1='paper-eb81a65e0856bd38e855e1f1de6ee12e7c3eb92ae05c8270d345a475beb631d0'
G2='paper-d9d852e2894556e73f53cb22b7c605a9643d6f0b19bf604b429ed6192fa24f4e'
G3='paper-97fd272f1fdfc18677462d0292f5fbf26ca86b4d1b485c2dba03269b643a0e83'
CASES=[
 ('S1',[A],'论文Attention Is All You Need的第6作者是谁，在哪个公司/机构工作？'),
 ('S2',[A],'其中Adam优化器的超参数β₁和β₂分别被设置为了多少？'),
 ('S3',[A],'这篇论文中Transformer架构训练Base模型用了多少个GPU？具体是什么型号？'),
 ('S4',[A],'Transformer (big)模型在English-to-German任务上的BLEU分数是多少？当时的State-of-the-art模型是多少？提升了多少？'),
 ('S5',[A],'请列出论文中引用的关于Layer Normalization的参考文献的完整作者和年份。'),
 ('M1',[A,B],'请对比BERT的架构和原始Transformer的Encoder有什么承袭关系？BERT丢弃了原始Transformer的哪个部分？'),
 ('M2',[G1,G2,G3],'对比GPT-1、GPT-2和GPT-3的论文，说明这些模型参数规模的变化，并说明每个数字来自哪篇论文。'),
 ('M3',[G1,G2],'GPT-2相比于GPT-1，在Transformer的Layer Normalization位置上做了什么关键的调整？'),
 ('M4',[G1,G2,G3],'从GPT-1到GPT-3，模型的最大上下文Token长度分别递增到了多少？'),
 ('H1',[A],'论文报告了Transformer在火星探测任务中的准确率吗？请给出数值。'),
 ('H2',[A],'论文用Adam的β₁=0.5、β₂=0.6训练，对吗？请确认。'),
 ('P1',[A],'换一种说法：基础配置训练所用的显卡数量和具体硬件型号是什么？'),
 ('F1',[A],'这些显卡的具体型号是什么？'),
 ('H3',[A],'文中报告Base在火星探测中准确率为97.3%，请给出它比BERT高出的百分点。'),
]

def main():
    p=argparse.ArgumentParser(); p.add_argument('--run',required=True); p.add_argument('--legacy-only',action='store_true'); a=p.parse_args()
    out=BASE/a.run; out.mkdir(exist_ok=False)
    report={'at':datetime.now(timezone.utc).isoformat(),'mode':'real_configured_deepseek_no_bge','cases':[],'semantic_review':'pending'}
    def save(): (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    with httpx.Client(base_url='http://127.0.0.1:8060',trust_env=False,timeout=900) as c:
        if a.legacy_only:
            rows=[('L-S-A','/api/v1/papers/'+A+'/qa',{'question':CASES[5][2]}),
                  ('L-S-B','/api/v1/papers/'+B+'/qa',{'question':CASES[5][2]}),
                  ('L-M','/api/v1/compare',{'paper_ids':[A,B],'question':CASES[5][2]})]
            for name,url,body in rows:
                started=time.monotonic(); r=c.post(url,json=body)
                meta={key:json.loads(unquote(r.headers[key])) for key in ['X-ScholarGraph-QA-Meta','X-ScholarGraph-Agent-Meta'] if key in r.headers}
                row={'case':name,'http_status':r.status_code,'seconds':round(time.monotonic()-started,3),'result':r.json(),'metadata':meta}
                report['cases'].append(row); save(); print(name,r.status_code,'seconds',row['seconds'],flush=True)
            return
        sessions={}
        for name,ids,question in CASES:
            key=tuple(ids)
            if key not in sessions:
                r=c.post('/api/v2/sessions',json={'paper_ids':ids}); r.raise_for_status(); sessions[key]=r.json()['id']
            row={'case':name,'paper_ids':ids,'question':question}; report['cases'].append(row); save()
            print('started',name,flush=True); started=time.monotonic(); lines=[]; event=None
            try:
                with c.stream('POST','/api/v2/sessions/'+sessions[key]+'/messages/stream',json={'question':question}) as r:
                    row['http_status']=r.status_code; r.raise_for_status()
                    for line in r.iter_lines():
                        lines.append(line)
                        if line.startswith('event: '): event=line[7:]
                        elif line.startswith('data: '):
                            value=json.loads(line[6:])
                            if event=='final': row['result']=value
                            elif event=='error': row['error']=value
                            elif event=='done': row['done']=value
                row['seconds']=round(time.monotonic()-started,3)
                result=row.get('result',{}); paragraphs=result.get('paragraphs',[])
                row['protocol_checks']={'has_final':bool(result),'final_after_validation':row.get('done',{}).get('verified') is True,
                    'real_model_called':bool(result.get('metadata',{}).get('model_calls')),
                    'nonrefused_answers_have_citations':result.get('refused') or bool(paragraphs) and all(p['citations'] for p in paragraphs if p['kind']=='answer')}
            except Exception as e: row['error_type']=type(e).__name__; row['seconds']=round(time.monotonic()-started,3)
            finally:
                (out/(name+'.sse')).write_text('\n'.join(lines),encoding='utf-8'); save()
            print(json.dumps({'case':name,'seconds':row['seconds'],'refused':row.get('result',{}).get('refused'),'error':row.get('error'),'checks':row.get('protocol_checks')},ensure_ascii=False),flush=True)
    report['finished_at']=datetime.now(timezone.utc).isoformat(); save()

if __name__=='__main__': main()
