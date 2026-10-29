"""Real-corpus audit of evidence selection; this is not a new model generation."""
import json,sys
from common import ROOT,BASE,write
sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.api import create_app
from scholar_graph.future_evidence import local_candidates
if __name__=='__main__':
    task=json.loads((BASE/'future-resilient/result.json').read_text(encoding='utf8'))
    ids=[r['paper_id'] for r in json.loads((BASE/'upload-twenty/result.json').read_text(encoding='utf8'))['task']['result']['succeeded']]
    app=create_app(data_dir=BASE/'records20');bundles=[app.state.workspace.bundle(pid) for pid in ids];rows=[]
    for d in task['result']['future']['directions']:
        candidates=local_candidates(bundles,d['anchor']['paper_id'],d['source_year'],[d['query'],d.get('alternative_query',d['query'])])
        passages=[p for c in candidates for p in c['source_passages']]
        assert all(not any(s.lower().startswith(('references','bibliography','参考文献')) for s in p['anchor']['section']) for p in passages)
        old=[m for m in d['matches'] if m['candidate_id'].startswith('paper-')]
        retained=[m for m in old if any(m['quote'] in (c.get('abstract') or '') or any(m['quote'] in p['quote'] for p in c['source_passages']) for c in candidates if c['id']==m['candidate_id'])]
        rows.append({'topic':d['topic'],'candidate_count':len(candidates),'bibliography_passages':0,'retained_real_match_count':len(retained),'retained_match_papers':[m['candidate_id'] for m in retained]})
    assert rows[0]['retained_real_match_count']>=1 and rows[2]['retained_real_match_count']>=2
    write(BASE/'primary-candidates.json',rows);print(json.dumps(rows,ensure_ascii=False))
