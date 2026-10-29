"""Publish bounded audit evidence; keep original PDFs/full parsed source records private."""
import json,re,shutil,hashlib
from collections import Counter
from common import ROOT,BASE,write,digest
OUT=ROOT/'test-records/item05-20261029'
def read(path):return json.loads((BASE/path).read_text(encoding='utf8'))
def qhash(text):return hashlib.sha256(text.encode()).hexdigest()
def compact(text):return ' '.join(text.split())
if __name__=='__main__':
    OUT.mkdir(exist_ok=True)
    graph=read('graph-delivery/graph-0.json');summary=read('graph-delivery/summary.json');sources=read('sources.json')
    ids={p['paper_id'] for p in summary['papers']};chunks={}
    for pid in ids:
        for c in json.loads((BASE/'records20/papers'/pid/'chunks.json').read_text(encoding='utf8')):chunks[c['chunk_id']]=c
    def anchored(anchor,quote=None):
        c=chunks[anchor['chunk_id']];assert c['paper_id']==anchor['paper_id'] and c['page_number']==anchor['page_number'] and c['section_path']==anchor['section']
        if quote:assert compact(quote) in compact(c['text'])
    proofs=[]
    for p in graph['diagnostics']['edge_evidence']:
        anchored(p['anchor'],p['body_quote'])
        bib=[]
        for r in p['references']:
            for b in r['bibliography']:
                anchored(b['anchor'],b['quote']);bib.append({'anchor':b['anchor'],'quote_sha256':qhash(b['quote'])})
        proofs.append({k:p[k] for k in ['edge_index','from_paper_id','to_paper_id','anchor','evidence_kind']}|{'body_quote_sha256':qhash(p['body_quote']) if p['body_quote'] else None,'bibliography':bib})
    assert len(proofs)==303 and len(ids)==20
    title_audit=read('graph-delivery/original-pdf-title-audit.json')
    title_pairs={(p['from_id'],p['to_id']) for p in title_audit}
    pairs={(e['from_paper_id'],e['to_paper_id']) for e in graph['edges'] if e['status']=='verified'}
    remaining=pairs-title_pairs;assert len(remaining)==1
    source_id,target_id=next(iter(remaining));source_paper=next(p for p in summary['papers'] if p['paper_id']==source_id);target=next(p for p in summary['papers'] if p['paper_id']==target_id)
    assert source_paper['filename']=='2101.03961v3.pdf' and target['filename']=='1910.02054v3.pdf'
    from pypdf import PdfReader
    found=[i for i,p in enumerate(PdfReader(ROOT/'pdf'/source_paper['filename']).pages,1) if '1910.02054' in (p.extract_text() or '')]
    assert found
    write(OUT/'identifier-pair-audit.json',{'from_paper_id':source_id,'to_paper_id':target_id,'original_source_file':source_paper['filename'],'target_file':target['filename'],'shared_arxiv_id':'1910.02054','original_pdf_physical_pages':found,'reason':'The bibliography and target titles differ in singular/plural form; arXiv identity agrees. This pair is outside the exact-full-title audit.'})
    core=[]
    for expectation in sources['qualitative_expectations_before_graph']:
        pid=next(r['paper_id'] for r in summary['papers'] if r['filename']==expectation['filename']);node=next(n for n in graph['nodes'] if n['paper_id']==pid)
        pairs={(e['from_paper_id'],e['to_paper_id']) for e in graph['edges'] if e['status']=='verified'}
        assert node['level']==expectation['expected']
        core.append({**expectation,**node,'incoming':sum(b==pid for a,b in pairs),'outgoing':sum(a==pid for a,b in pairs)})
    write(OUT/'core-source-audit.json',{'reviewer':'source-based qualitative review by coding assistant; not external human expert labeling','samples':core})
    write(OUT/'graph-summary.json',{**summary,'evidence_kind_counts':dict(Counter(p['evidence_kind'] for p in proofs)),'full_response_sha256':digest(BASE/'graph-delivery/graph-0.json')})
    write(OUT/'graph-evidence-manifest.json',proofs);write(OUT/'sources.json',sources)
    task=read('browser-accepted/review-task.json');d=task['result']['document'];assert all(r['paper_id'] in ids for r in d['references'])
    notes=[
      '范围声明，与20节点局部图谱一致。',
      '范围内确有Transformer、GPT-3、InstructGPT、DeepSeek-R1；本句为主题归纳。段落直接引文仅覆盖架构与扩展，对齐/推理须结合所选全文核对，属于引文覆盖可继续改善之处。',
      'Attention物理第1页摘要明确纯注意力、去循环/卷积、机器翻译与并行性。',
      'BERT物理第1页摘要明确双向表示及一个额外输出层。',
      '属于作者观点归纳；所选后续论文确实引用Transformer/BERT，不视为整个领域因果证明。',
      'Scaling Laws第1页摘要明确三项幂律；LoRA第1页原文明确冻结权重、可训练低秩矩阵和参数减少。未声称统一评测胜负。',
      '证据范围/局限说明，标为研究设想，不是已完成跨论文实验。',
      '条件性局限判断，不是实测结论。',
      '明确未来设想，没有宣称已完成统一对比实验。',
      '前文贡献的概括，类型为研究设想；不新增论文或定量结论。',
      '明确未来设想，没有宣称研究新颖性已证明。']
    sentences=[];i=0;citation_count=0
    for section in d['sections']:
        for p in section['paragraphs']:
            evidence=[]
            for c in p['citations']:
                assert c['anchor']['paper_id'] in ids;anchored(c['anchor'],c['quote']);citation_count+=1
                evidence.append({'anchor':c['anchor'],'quote_sha256':qhash(c['quote'])})
            for sentence in re.findall(r'[^。！？]+[。！？]?',p['text']):
                sentences.append({'sentence':sentence,'type':p['type'],'section':section['title'],'citation_evidence':evidence,'source_review_note':notes[i]});i+=1
    assert i==len(notes)
    write(OUT/'review-sentence-audit.json',{'task_id':task['id'],'task_status':task['status'],'sentences':sentences,'sentence_count':i,'citation_instances':citation_count,'reference_count':len(d['references']),'references':d['references'],'outside_selected_set':0,'model_calls':task['result']['metadata']['model_calls'],'reviewer':'coding assistant inspected actual source quotes; not an independent human expert'})
    runs=[read('future-primary/result.json')]
    examples=[(runs[0],runs[0]['result']['future']['directions'][i]) for i in [0,2]];checks=[]
    for future_task,direction in examples:
        anchored(direction['anchor'],direction['quote']);matches=[]
        for m in direction['matches']:
            candidate=next(p for p in direction['candidates'] if p['id']==m['candidate_id']);quote=m['quote']
            assert quote in (candidate.get('abstract') or '') or any(quote in p['quote'] for p in candidate.get('source_passages',[]))
            if direction['decision']=='exclude':assert candidate['year']>direction['source_year']
            matches.append({'candidate_id':m['candidate_id'],'title':candidate['title'],'year':m['year'],'source':candidate['source'],'quote_sha256':qhash(quote),'quote_excerpt':' '.join(quote.split()[:18])})
        checks.append({k:direction[k] for k in ['topic','decision','reason','source_year','source_year_basis','searched_at','anchor','date_check','searches']}|{'task_id':future_task['id'],'source_quote_sha256':qhash(direction['quote']),'matches':matches})
    assert sum(d['decision']=='exclude' for d in checks)>=2
    write(OUT/'future-time-audit.json',{'directions':checks,'runs':[{'task_id':t['id'],'status':t['status'],'model_calls':t['result']['metadata']['model_calls'],'source_evidence_counts':t['result']['metadata']['source_evidence_counts']} for t in runs]})
    primary=runs[0];directions=primary['result']['future']['directions']
    passages=[p for d in directions for c in d['candidates'] for p in c.get('source_passages',[])]
    assert all(not any(s.lower().startswith(('references','bibliography','参考文献')) for s in p['anchor']['section']) for p in passages)
    write(OUT/'future-primary-summary.json',{'task_id':primary['id'],'status':primary['status'],'timing':read('future-primary/timing.json'),
        'source_papers':len(primary['result']['metadata']['source_evidence_counts']),'model_calls':primary['result']['metadata']['model_calls'],
        'queries':sum(len(d['searches']) for d in directions),'search_errors':sum(len(d.get('search_errors',[])) for d in directions),
        'bibliography_passages':0,'decisions':[d['decision'] for d in directions]})
    old=read('future-before/result.json')
    write(OUT/'future-before-summary.json',{'task_id':old['id'],'directions':[{k:d.get(k) for k in ['topic','decision','reason']} for d in old['result']['future']['directions']]})
    failed=read('browser-accepted/future-task.json')
    write(OUT/'future-public-failure.json',{'task_id':failed['id'],'status':failed['status'],'created_at':failed['created_at'],'finished_at':failed['finished_at'],'failed_count':failed['result']['failed_count'],'failed':failed['result']['failed']})
    for name in ['baseline-fast.log','baseline-fast.xml','fast-acceptance.log','fast-acceptance.xml','related-acceptance.log','related-acceptance.xml','transport-check.log','upload-browser.log','upload-twenty.log','latest-tests.log','repair-tests.log','numbered-ui-build.log','index-build.log','index-build-retry.log','readable-front-image.log','release-front-image.log','release-runtime.log','final-front-release.log','runtime-audit.json','runtime-audit-delivery.log','release-commands.json','release-front-commands.json','qa-delivery.log','benchmark-final.log','browser-final.log','browser-accepted.log','future-resilient.log']:
        if (BASE/name).exists():shutil.copyfile(BASE/name,OUT/name)
    for name in ['fast-primary.log','fast-primary.xml','related-primary.log','related-primary.xml','primary-candidates.log','primary-candidates-fixed.log','primary-release.log','primary-item05-release.log','primary-back-image.log','future-primary.log','restart-release.log','restart-item05.log','runtime-audit-restarted.log','ui-after-restart.log']:
        shutil.copyfile(BASE/name,OUT/name)
    for name in ['graph-before/summary.json','graph-delivery/original-pdf-title-audit.json','benchmark-final/results.json','benchmark-final/verification.json','browser-final/result.json','browser-accepted/result.json','ui-readable/result.json','ui-final/result.json','future-resilient/timing.json','upload-twenty/result.json','primary-candidates.json']:
        write(OUT/name,read(name))
    qa=read('qa-delivery/results.json')
    write(OUT/'qa-regression-summary.json',[{'question':r['question'],'http_status':r['http_status'],'refused':r['answer'].get('refused'),'citations':sum(len(p.get('citations',[])) for p in r['answer'].get('paragraphs',[]))} for r in qa])
    for folder in ['ui-final','upload-twenty']:
        for path in (BASE/folder).glob('*.png'):
            target=OUT/folder/path.name;target.parent.mkdir(exist_ok=True);shutil.copyfile(path,target)
    resilient=read('future-resilient/result.json');assert resilient['status'] not in ('running','queued')
    write(OUT/'future-resilience.json',{'task_id':resilient['id'],'status':resilient['status'],'created_at':resilient['created_at'],'finished_at':resilient['finished_at'],'failed_count':resilient['result']['failed_count'],'source_evidence_counts':resilient['result']['metadata']['source_evidence_counts'],'model_calls':resilient['result']['metadata']['model_calls'],'directions':[{k:d.get(k) for k in ['topic','decision','source_year','date_check','searches','search_errors','error']}|{'candidate_count':len(d['candidates'])} for d in resilient['result']['future']['directions']]})
    write(OUT/'private-evidence-sha256.json',{name:digest(BASE/name) for name in ['upload-twenty/result.json','graph-delivery/graph-0.json','browser-accepted/review-task.json','browser-final/future-task.json','future-ready/result.json','browser-accepted/future-task.json','future-resilient/result.json','future-primary/result.json','browser-final/trace.zip']})
    print(json.dumps({'graph_proofs_checked':len(proofs),'review_sentences':i,'review_citations':citation_count,'references':len(task['result']['document']['references']),'dated_exclusions':sum(d['decision']=='exclude' for d in checks)}))
