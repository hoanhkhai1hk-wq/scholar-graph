"""Recheck every OCR anchor's physical page against the actual scan PDF."""
from collections import Counter
import json
import sys
import time
import httpx
from common import ROOT,BASE,API,write
sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.pdf_files import PdfFiles,file_digest
from pypdf import PdfReader

if __name__=='__main__':
    started=time.perf_counter()
    scan=next(j for j in json.loads((BASE/'samples.json').read_text(encoding='utf8')) if not j['has_text_layer'])
    pid=scan['id'];paper=BASE/'records/papers'/pid
    chunks=json.loads((paper/'chunks.json').read_text(encoding='utf8'))
    path=PdfFiles(BASE/'records').locate(pid)
    reader=PdfReader(path);assert len(reader.pages)==scan['page_count']==15
    chars=[len((p.extract_text() or '').strip()) for p in reader.pages]
    assert not any(chars),'The scan must not acquire a fabricated PDF text layer'
    histogram=Counter(c['page_number'] for c in chunks)
    assert all(1<=n<=15 for n in histogram)
    report={'paper_id':pid,'source_file_sha256':file_digest(path)[0],'pdf_pages':15,'source_text_chars_per_page':chars,
            'ocr_chunks':len(chunks),'ocr_pages':sorted(histogram),'chunks_per_page':dict(histogram),'pages':[]}
    with httpx.Client(base_url=API,trust_env=False,timeout=60) as client:
        for number in range(1,16):
            r=client.get(f'/api/v2/papers/{pid}/reading',params={'physical_page':number,'include_navigation':'false'});r.raise_for_status();got=r.json()['chunks']
            expected=[c for c in chunks if c['page_number']==number]
            assert [(c['chunk_id'],c['page_number'],c['text']) for c in got]==[(c['chunk_id'],c['page_number'],c['text']) for c in expected]
            report['pages'].append({'physical_page':number,'chunks':len(got),'source_equal':True,'chunk_ids':[c['chunk_id'] for c in got]})
    report.update(mismapped_anchors=0,seconds=round(time.perf_counter()-started,6),passed=True,
                  precision='Page-only for scan: the original PDF contains no selectable text coordinates; OCR text is not a PDF text layer.')
    write(BASE/'scan-mapping.json',report);print(json.dumps({k:report[k] for k in ['pdf_pages','ocr_chunks','mismapped_anchors','passed','seconds']}))
