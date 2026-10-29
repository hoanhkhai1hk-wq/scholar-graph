"""Real twenty-paper graph, original-PDF title audit and independent linear PageRank."""
import argparse,json,re,time,unicodedata
from common import ROOT,BASE,write,client,ready

def key(s):return ''.join(c for c in unicodedata.normalize('NFKC',s).lower() if c.isalnum())
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();out=BASE/a.run;out.mkdir(exist_ok=False)
    upload=json.loads((BASE/'upload-twenty/result.json').read_text(encoding='utf8'));assert upload['passed']
    mapping={r['filename']:r['paper_id'] for r in upload['task']['result']['succeeded']};assert len(mapping)==20
    ids=list(mapping.values());report={'papers':[],'http_seconds':[]}
    with client() as c:
        ready(c)
        for name,pid in mapping.items():
            r=c.get('/api/v2/papers/'+pid+'/reading',params={'physical_page':1,'include_navigation':'false'});r.raise_for_status();row=r.json()
            report['papers'].append({'filename':name,'paper_id':pid,'title':row['paper']['title'],'year':row['paper']['year'],'pages':row['paper']['page_count'],'chunks':row['total_chunks']})
        for i in range(3):
            start=time.monotonic();r=c.get('/api/v2/graph',params=[('paper_ids',pid) for pid in ids]);r.raise_for_status();g=r.json();report['http_seconds'].append(round(time.monotonic()-start,6));write(out/f'graph-{i}.json',g)
    pairs={(e['from_paper_id'],e['to_paper_id']) for e in g['edges'] if e['status']=='verified'}
    report.update(nodes=len(g['nodes']),verified_edges=sum(e['status']=='verified' for e in g['edges']),unique_verified_pairs=len(pairs),unverified_edges=sum(e['status']!='verified' for e in g['edges']),
        isolated=len(g['layers']['isolated']),ranked=sorted(g['nodes'],key=lambda n:-n['pagerank']))
    import numpy as np
    n=len(ids);P=np.zeros((n,n))
    for i,pid in enumerate(ids):
        targets=[b for aa,b in pairs if aa==pid]
        if targets:
            for target in targets:P[i,ids.index(target)]=1/len(targets)
        else:P[i,:]=1/n
    solved=np.linalg.solve(np.eye(n)-.85*P.T,np.ones(n)*(.15/n));reported={r['paper_id']:r['pagerank'] for r in g['nodes']}
    report['independent_linear_solution_max_error']=float(max(abs(solved[i]-reported[pid]) for i,pid in enumerate(ids)))
    assert report['independent_linear_solution_max_error']<1e-10
    from pypdf import PdfReader
    bibliography_audit=[]
    for paper in report['papers']:
        pages=[p.extract_text() for p in PdfReader(ROOT/'pdf'/paper['filename']).pages];full='\n'.join(pages)
        headings=list(re.finditer(r'(?im)^\s*(?:references|bibliography)\s*$',full))
        if not headings:continue
        bib=full[headings[0].end():];normalized=key(bib)
        for target in report['papers']:
            title=key(target['title'] or '')
            if paper['paper_id']==target['paper_id'] or len(title)<20 or title not in normalized:continue
            bibliography_audit.append({'source_file':paper['filename'],'target_file':target['filename'],'from_id':paper['paper_id'],'to_id':target['paper_id'],
                'target_title':target['title'],'verified_pair_found':(paper['paper_id'],target['paper_id']) in pairs})
    write(out/'original-pdf-title-audit.json',bibliography_audit)
    report['original_pdf_title_audit']={'eligible_pairs':len(bibliography_audit),'verified_found':sum(r['verified_pair_found'] for r in bibliography_audit),'missing':[r for r in bibliography_audit if not r['verified_pair_found']]}
    write(out/'summary.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ['ranked','papers']},ensure_ascii=False));
    print(json.dumps(report['ranked'],ensure_ascii=False))
