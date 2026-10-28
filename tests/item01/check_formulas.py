"""Source-reviewed fixture/corrections for this exact official v1, never production output."""
import hashlib
import json
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[2]
PID='paper-0a9bff1be3575cf9fe26a4a3d3a9175bc791ecec90de8b9deba4cff75d2b9476'
# Transcribed after viewing the exact source PDF pages 3,4,5,7. V1 multi-head
# equation has no W^O factor; do not substitute a remembered later edition.
EXPECTED={
 'p0003-r0008':(3,r'\operatorname{Attention}(Q,K,V)=\operatorname{softmax}\left(\frac{QK^{T}}{\sqrt{d_k}}\right)V','核对第3页公式(1)，规范函数名与分式，保留d_k。'),
 'p0004-r0012':(4,r'\begin{aligned}\operatorname{MultiHead}(Q,K,V)&=\operatorname{Concat}(\mathrm{head}_1,\ldots,\mathrm{head}_h)\\\text{where}\quad\mathrm{head}_i&=\operatorname{Attention}(QW_i^Q,KW_i^K,VW_i^V)\end{aligned}','核对第4页原式，修正第二行括号；v1原式没有W^O，不增补后续版本内容。'),
 'p0005-r0014':(5,r'\begin{aligned}PE_{(pos,2i)}&=\sin(pos/10000^{2i/d_{\mathrm{model}}})\\PE_{(pos,2i+1)}&=\cos(pos/10000^{2i/d_{\mathrm{model}}})\end{aligned}','核对第5页两行位置编码，保留2i、2i+1与10000的指数。'),
 'p0005-r0015':(5,r'\operatorname{FFN}(x)=\max(0,xW_1+b_1)W_2+b_2','核对第5页公式(2)，扩展裁切已恢复末尾b_2，本次保存规范数学代码。'),
 'p0007-r0015':(7,r'\operatorname{Attention}(Q,K,V)=\operatorname{dropout}\left(\operatorname{softmax}\left(\frac{QK^T}{\sqrt{d}}\right)\right)V','核对第7页Attention Dropout原式，分母原文是sqrt(d)，不改成d_k。'),
 'p0007-r0016':(7,r'\mathrm{lrate}=d_{\mathrm{model}}^{-0.5}\cdot\min\left(\mathrm{step\_num}^{-0.5},\mathrm{step\_num}\cdot\mathrm{warmup\_steps}^{-1.5}\right)','已通过真实浏览器保存的第7页公式(3)核对结果。'),
}

def main():
    source=ROOT/'pdf/1706.03762v1.pdf'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==PID.removeprefix('paper-')
    out=ROOT/'data/item01-20261028/formula-source-reviewed'; out.mkdir(exist_ok=False)
    records=ROOT/'data/item01-20261028/after/records'
    def frozen(): return {str(p.relative_to(records)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (records/'papers').rglob('*.json')}
    before=frozen()
    with httpx.Client(base_url='http://127.0.0.1:8040/api/v2',trust_env=False,timeout=60) as c:
        response=c.get(f'/papers/{PID}/formulas'); response.raise_for_status(); candidates=response.json()
        (out/'candidates-before-correction.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2),encoding='utf-8')
        for identity,(page,latex,note) in EXPECTED.items():
            if identity=='p0007-r0016': continue  # This correction was actually made in the browser.
            response=c.patch(f'/papers/{PID}/formulas/{identity}',json={'latex':latex,'note':'第1项原图核对：'+note}); response.raise_for_status()
        response=c.get(f'/papers/{PID}/formulas'); response.raise_for_status(); result=response.json()
        (out/'source-reviewed.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        assert len(result['items'])==6
        assert all(x['latex']==EXPECTED[x['region_id']][1] and x['status']=='corrected_from_source' and x.get('recognized_latex') for x in result['items'])
    report={'source_sha256':PID.removeprefix('paper-'),'reviewer':'Codex source-image review; not an independent human evaluation',
        'source_pages':[3,4,5,7],'regions':6,'source_reviewed_corrections':6,
        'automatic_semantic_acceptance_passed':False,
        'observed_machine_errors':['p0004-r0012: missing or malformed closing expression','p0007-r0016: model subscript misrecognized'],
        'corrections_exercised_in_browser':1,'corrections_saved_via_real_api':5,
        'frozen_json_files':len(before),'frozen_json_unchanged':before==frozen()}
    (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__': main()
