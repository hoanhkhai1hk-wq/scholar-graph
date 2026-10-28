"""Real model translations of explicitly controlled source PDFs; no mock scores."""
import argparse,json,time
from pathlib import Path
import httpx

BASE=Path(__file__).resolve().parents[2]/'data/item03-20261028'
if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--run',required=True); args=parser.parse_args()
    out=BASE/args.run; out.mkdir(exist_ok=False); fixtures=json.loads((BASE/'protection-fixtures.json').read_text(encoding='utf-8')); report={'cases':[]}
    with httpx.Client(base_url='http://127.0.0.1:8080',trust_env=False,timeout=900) as client:
        for name,source,body in [('english_full',fixtures['english'],{'scope':'full','target':'zh'}),
                                 ('chinese_abstract',fixtures['chinese'],{'scope':'abstract','target':'en'}),
                                 ('chinese_full',fixtures['chinese'],{'scope':'full','target':'en'})]:
            started=time.monotonic(); response=client.post('/api/v1/papers/'+source['paper_id']+'/translate',json=body); value=response.json()
            (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
            row={'case':name,'http_status':response.status_code,'seconds':round(time.monotonic()-started,3)}
            if response.status_code==200:
                content=value.get('markdown') or '\n'.join(s['translated_text'] for s in value['segments'])
                row['checks']={'real_model':bool(value['metadata']['model_calls']),
                    'actual_pdf_pages':all(1<=s['page_number']<=2 for s in value['segments']),
                    'protected':{str(i):p in content for i,p in enumerate(source['expected_protected'])} if body['scope']=='full' else {},
                    'correct_direction':value['target']==body['target']}
                row['passed']=all(v for k,v in row['checks'].items() if k!='protected') and all(row['checks']['protected'].values())
            else: row.update(passed=False,error=value)
            report['cases'].append(row); (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(row,ensure_ascii=False),flush=True)
    report['passed']=all(x['passed'] for x in report['cases']); (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    raise SystemExit(0 if report['passed'] else 1)
