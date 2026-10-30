"""Independent all-page OCR rerun; distinguish content mapping from API roundtrip."""
from collections import defaultdict
import json
import os
import re
import sys
import time
from common import ROOT,BASE,write
sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.adapters import LocalEngines
from scholar_graph.pdf_files import PdfFiles

def shingles(text):
    text=re.sub('[^a-z0-9]','',text.casefold())
    return {text[n:n+3] for n in range(max(0,len(text)-2))}

if __name__=='__main__':
    pid=next(x['id'] for x in json.loads((BASE/'samples.json').read_text(encoding='utf8')) if not x['has_text_layer'])
    chunks=json.loads((BASE/'records/papers'/pid/'chunks.json').read_text(encoding='utf8'));by_page=defaultdict(str)
    for chunk in chunks:by_page[chunk['page_number']]+=chunk['text']+'\n'
    original={p:shingles(t) for p,t in by_page.items()}
    os.environ['SCHOLAR_GRAPH_OCR_CACHE_DIR']=str(ROOT/'data/code-order-20261029/ocr-cache')
    engines=LocalEngines(cache_dir=BASE/'ocr-cache',timeout=900)
    started=time.perf_counter();raw=engines.ocr(PdfFiles(BASE/'records').locate(pid),list(range(15)))
    (BASE/'ocr-rerun.private.json').write_text(json.dumps(raw,ensure_ascii=False),encoding='utf8')
    report={'paper_id':pid,'method':'Independent PaddleOCR all15 physical pages. Match normalized character3-gram Dice scores to every frozen OCR page; not merely compare API page labels.','pages':[]}
    for page in raw['pages']:
        text=' '.join(part['content'] for block in page['blocks'] for part in block['content'])
        actual=shingles(text);scores={p:2*len(actual&s)/max(1,len(actual)+len(s)) for p,s in original.items()}
        ranked=sorted(scores,key=lambda p:(-scores[p],p));winner=ranked[0];physical=page['page_idx']+1
        row={'physical_page':physical,'matched_frozen_page':winner,'score':round(scores[winner],6),'runner_up_score':round(scores[ranked[1]],6),'ocr_blocks':len(page['blocks'])}
        row['passed']=winner==physical and scores[winner]>=.6 and scores[winner]-scores[ranked[1]]>=.1
        report['pages'].append(row)
    report.update(seconds=round(time.perf_counter()-started,6),passed=len(report['pages'])==15 and all(p['passed'] for p in report['pages']),mismatched_pages=sum(not p['passed'] for p in report['pages']))
    write(BASE/'ocr-independent.json',report);print(json.dumps({k:report[k] for k in ['seconds','passed','mismatched_pages']}));raise SystemExit(0 if report['passed'] else 1)
