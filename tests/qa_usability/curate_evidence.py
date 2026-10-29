"""Publish result metadata and quote hashes; original corpora and SSE stay local."""
import hashlib,json,shutil
from common import ROOT,BASE,digest,write

OUT=ROOT/'test-records/qa-usability-20261028'
def checked(row,records):
    answer=row['answer'];assert not row.get('error') and row['done'].get('verified') is True
    assert all(c['status']=='succeeded' for c in answer['metadata']['model_calls'])
    selected=set(row['paper_ids']);citations=[]
    for p in answer['paragraphs']:
        assert p['kind']!='answer' or p['citations']
        for citation in p['citations']:citations.append(citation)
    for calculation in answer['calculations']:citations.extend(calculation['operands'])
    for citation in citations:
        a=citation['anchor'];assert a['paper_id'] in selected
        chunks=json.loads((records/'papers'/a['paper_id']/'chunks.json').read_text(encoding='utf8'))
        chunk=next(c for c in chunks if c['chunk_id']==a['chunk_id'])
        assert citation['quote'] in chunk['text'] and chunk['page_number']==a['page_number']
    return {'case':row.get('case',row['question']),'question':row['question'],'seconds':row['elapsed_seconds'],
        'refused':answer['refused'],'text':[p['text'] for p in answer['paragraphs']],
        'citations':[{'anchor':c['anchor'],'quote_sha256':hashlib.sha256(c['quote'].encode()).hexdigest()} for c in citations],
        'calculations':[{'label':x['label'],'result':x['result'],'unit':x['unit']} for x in answer['calculations']],
        'retrieval':answer['metadata']['retrieval'],'model_calls':answer['metadata']['model_calls'],'verified_done':True}

if __name__=='__main__':
    OUT.mkdir(exist_ok=True);report={}
    assert not (OUT/'manifest.json').exists(),'Published evidence must not be overwritten'
    for run,records,refused in [('final-service',ROOT/'data/item04-20261028/records',{'论文中火星基地的建造预算是多少？','论文是不是说Adam的β1=0.98、β2=0.9？'}),
        ('official-final-code',BASE/'official-final-code/records',{'H1','H2','H3'})]:
        rows=json.loads((BASE/run/'results.json').read_text(encoding='utf8'));values=[]
        for r in rows:
            assert r['answer']['refused']==(r.get('case',r['question']) in refused)
            values.append(checked(r,records))
        write(OUT/(run+'.json'),values);report[run]={'count':len(values),'refused_as_expected':len(refused),'errors':0,'source_checks':'verbatim chunk + physical page + selected paper'}
    browser=json.loads((BASE/'browser-final-visible/result.json').read_text(encoding='utf8'));assert browser['passed'] and browser['highlighted_page']==1
    # Keep UI actions/results, omit duplicate full answer/source excerpts.
    compact={k:v for k,v in browser.items() if k!='cases'}
    compact['cases']=[{k:v for k,v in row.items() if k!='result'} for row in browser['cases']]
    write(OUT/'browser.json',compact)
    (OUT/'screenshots').mkdir(exist_ok=True)
    for name in ['qa-answer.png','qa-1440.png','qa-390.png','reader-answer.png','reader-source.png']:
        shutil.copyfile(BASE/'browser-final-visible'/name,OUT/'screenshots'/name)
    for name in ['baseline-fast.log','fast-final-code.log','fast-final-code.xml','related-first.log','related-final-code.log','related-final-code.xml',
        'frontend-build-final.log','final-service.log','official-final-code.log','browser-final-visible.log','deploy-health.log','runtime-final.json']:
        shutil.copyfile(BASE/name,OUT/name)
    before=json.loads((BASE/'before/results.json').read_text(encoding='utf8'));write(OUT/'before.json',[
        {'question':r['question'],'seconds':r['elapsed_seconds'],'refused':r['answer']['refused'],
         'retrieval':r['answer']['metadata']['retrieval']} for r in before])
    failures={}
    for folder in ['after-final','after-scope-final','deployed-final','final-acceptance-ready','release-verified']:
        path=BASE/folder/'results.json'
        if path.exists():failures[folder]=[{'question':r['question'],'seconds':r['elapsed_seconds'],'error':r['error']} for r in json.loads(path.read_text(encoding='utf8')) if r.get('error')]
    write(OUT/'retained-failures.json',failures);write(OUT/'summary.json',report)
    print(json.dumps(report,ensure_ascii=False))
