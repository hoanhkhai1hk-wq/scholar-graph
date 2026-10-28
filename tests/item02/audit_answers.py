"""Source-specific acceptance facts plus exact frozen-quote/page validation; no generated ground truth."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]; BASE=ROOT/'data/item02-20261028'; sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.validation import ContractGate
from scholar_graph.workspace_research import beta_settings,values,operand_number
from run_cases import A,B,G1,G2,G3
from audit_rules import context_transition_supported, unsupported_metric_refused, source_review_matches

def normal(s): return re.sub(r'\W+','',s.casefold())

def main():
    p=argparse.ArgumentParser(); p.add_argument('--run',required=True); p.add_argument('--output',default='audit.json'); p.add_argument('--review',type=Path); a=p.parse_args()
    report=json.loads((BASE/a.run/'results.json').read_text(encoding='utf-8')); repo=ApiRepository(BASE/'records',ContractGate())
    bundles={pid:repo.paper(pid) for pid in [A,B,G1,G2,G3]}
    source=json.loads((BASE/'independent-source-pages.json').read_text(encoding='utf-8'))
    source_map={A:'1706.03762v7.pdf',B:'N19-1423.pdf',G1:'language_understanding_paper.pdf',G2:'language_models_are_unsupervised_multitask_learners.pdf',G3:'2005.14165v4.pdf'}
    reviews={}
    reviewer='pending source review'
    if a.review:
        document=json.loads(a.review.read_text(encoding='utf-8'))
        reviewer=document['reviewer']; rows=document['cases']
        assert len(rows)==len({r['case'] for r in rows})==14
        assert {r['case'] for r in rows}=={r['case'] for r in report['cases']}
        reviews={r['case']:r for r in rows}
    result={'method':'fixed_source_checks_plus_result_hash_bound_semantic_review','semantic_reviewer':reviewer,'cases':[]}
    for row in report['cases']:
        name=row['case']; value=row.get('result',{}); text=' '.join(x['text'] for x in value.get('paragraphs',[])); normalized=normal(text)
        citations=[c for p in value.get('paragraphs',[]) for c in p['citations']]
        checks={'has_final':bool(value),'real_model_called':bool(value.get('metadata',{}).get('model_calls')),'no_stream_error':not row.get('error')}
        for c in citations:
            repo.gate.anchor(c['anchor'],list(bundles.values()),quote=c['quote'])
            pid=c['anchor']['paper_id']; page=c['anchor']['page_number']
            assert 1<=page<=len(source[source_map[pid]])
        locations={(c['anchor']['paper_id'],c['anchor']['page_number']) for c in citations}
        checks['exact_quotes_and_physical_page_bounds']=True
        if name.startswith('H'): checks['refused_unsupported_or_false_premise']=value.get('refused') is True
        else: checks['answered_with_citations']=value.get('refused') is False and bool(citations)
        if name=='S1': checks['source_fact']=all(normal(x) in normalized for x in ['Aidan N. Gomez','University of Toronto']) and (A,1) in locations
        if name=='S2': checks['source_fact']=beta_settings(text)=={'1':{Decimal('.9')},'2':{Decimal('.98')}} and (A,7) in locations
        if name in ('S3','P1','F1'): checks['source_fact']='P100' in text and bool(re.search(r'8|八',text)) and (A,7) in locations
        if name=='S4':
            checks['source_fact']='28.4' in text and '26.36' in text and (A,8) in locations
            calculations=value.get('calculations',[])
            checks['source_arithmetic']=any(c['operation']=='subtract' and c['result']=='2.04' and [operand_number(x['value']) for x in c['operands']]==[Decimal('28.4'),Decimal('26.36')] for c in calculations)
        if name=='S5': checks['source_fact']=all(normal(x) in normalized for x in ['Jimmy Lei Ba','Jamie Ryan Kiros','Geoffrey E Hinton','2016']) and (A,10) in locations
        if name=='M1': checks['source_fact']=all(x in text for x in ['编码器','解码器','双向']) and {(A,3),(B,3)}<=locations
        if name=='M2':
            parsed=values(text)
            checks['source_fact']=values('117M 175 billion')<=parsed and bool(values('1.5B 1542M')&parsed) and {(G2,4)}<=locations and any(pid==G3 for pid,page in locations)
            checks['earlier_value_attributed_to_later_paper']='GPT-2' in text and bool(re.search(r'GPT-1.{0,300}GPT-2',text))
        if name=='M3': checks['source_fact']='输入' in text and '额外' in text and '最后' in text and (G2,4) in locations
        if name=='M4':
            checks['source_fact']=all(x in text for x in ['512','1024','2048']) and context_transition_supported(citations,G2) and any(pid==G3 and page in [6,8,10,43] and '2048' in c['quote'] for c in citations for pid,page in [(c['anchor']['paper_id'],c['anchor']['page_number'])])
        if name=='H2': checks['corrected_source_values']=values('0.9 0.98')<=values(text) and (A,7) in locations
        if name=='H3': checks['refusal_without_answer_or_arithmetic']=unsupported_metric_refused(value)
        checks['semantic_source_review']=source_review_matches(value,reviews.get(name))
        for calculation in value.get('calculations',[]):
            left,right=[operand_number(x['value']) for x in calculation['operands']]
            expected=left-right if calculation['operation']=='subtract' else left/right if calculation['operation']=='ratio' else (left-right)/abs(right)*100
            assert abs(Decimal(calculation['result'])-expected)<Decimal('.000001')
        item={'case':name,'passed':all(checks.values()),'checks':checks,'seconds':row.get('seconds'),'answer':text,
              'citations':[{'anchor':c['anchor'],'quote_sha256':hashlib.sha256(c['quote'].encode()).hexdigest(),'quote_chars':len(c['quote'])} for c in citations],
              'model_calls':value.get('metadata',{}).get('model_calls'),'calculations':[{k:c[k] for k in ['label','operation','unit','result']} for c in value.get('calculations',[])]}
        item['semantic_review']=reviews.get(name)
        result['cases'].append(item)
    result['passed']=len(result['cases'])==14 and all(x['passed'] for x in result['cases'])
    with (BASE/a.run/a.output).open('x',encoding='utf-8') as f: json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'passed':result['passed'],'cases':[{k:r[k] for k in ['case','passed']} for r in result['cases']]},ensure_ascii=False))
    return 0 if result['passed'] else 1

if __name__=='__main__': raise SystemExit(main())
