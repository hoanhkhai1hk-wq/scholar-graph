"""Independent per-page token coverage screen. This is not OCR semantic accuracy."""
from collections import Counter, defaultdict
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import unicodedata
import pypdfium2 as pdfium

ROOT=Path(__file__).resolve().parents[2]
SAMPLES=[('v1','1706.03762v1.pdf','paper-0a9bff1be3575cf9fe26a4a3d3a9175bc791ecec90de8b9deba4cff75d2b9476'),
         ('scan','1706.03762v1.pdf','paper-64094fe169dd4ff454f579e9f197298df1c118c24b71b1f1ca8bb218c9e4801d'),
         ('book','UnderstandingDeepLearning_02_09_26_C.pdf','paper-f8237d393163900fa8e43210e680a3f987b45ccac7750b372e156fae3df0bf32')]

def tokens(value):
    return Counter(re.findall(r'[a-z]{2,}|\d+(?:\.\d+)?|[\u3400-\u9fff]',unicodedata.normalize('NFKC',value).casefold()))

def main():
    p=argparse.ArgumentParser(); p.add_argument('--records',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); report={'at':datetime.now(timezone.utc).isoformat(),'method':'multiset_token_recall_against_independent_pdf_text',
        'limitations':'Token recall screens missing text only. It is not OCR character accuracy, mathematical correctness or semantic fidelity.','samples':[]}
    for name,filename,pid in SAMPLES:
        raw=json.loads((a.records/'papers'/pid/'chunks.json').read_text(encoding='utf-8'))
        pages=defaultdict(list)
        for c in raw: pages[c['page_number']].append(c['text'])
        d=pdfium.PdfDocument(str(ROOT/'pdf'/filename)); rows=[]
        try:
            for i in range(len(d)):
                page=d[i]; tp=page.get_textpage()
                try: expected=tokens(tp.get_text_range())
                finally: tp.close()
                actual=tokens(' '.join(pages[i+1])); total=sum(expected.values()); found=sum((actual&expected).values())
                blank=False
                if not total and not pages[i+1]:
                    bitmap=page.render(scale=.4); image=bitmap.to_pil().convert('L')
                    # The book has printer crop marks outside its content area.
                    content=image.crop((round(image.width*.06),round(image.height*.06),round(image.width*.94),round(image.height*.94)))
                    try: blank=sum(x<220 for x in content.getdata())/ (content.width*content.height)<.00005
                    finally: content.close()
                    image.close(); bitmap.close()
                page.close()
                rows.append({'page':i+1,'reference_tokens':total,'parsed_tokens':sum(actual.values()),'matched_tokens':found,
                             'recall':round(found/total,4) if total else None,'chunks':len(pages[i+1]),'visually_blank':blank})
        finally: d.close()
        total=sum(r['reference_tokens'] for r in rows); found=sum(r['matched_tokens'] for r in rows)
        row={'sample':name,'physical_pages':len(rows),'chunks':len(raw),'weighted_token_recall':round(found/total,4),
             'empty_pages':[r['page'] for r in rows if not r['chunks']], 'visually_blank_pages':[r['page'] for r in rows if r['visually_blank']],
             'missing_text_pages':[r['page'] for r in rows if r['reference_tokens']>=20 and not r['parsed_tokens']],
             'low_recall_pages':[r for r in rows if r['reference_tokens']>=20 and r['recall']<.55],'pages':rows}
        report['samples'].append(row); print(json.dumps({k:v for k,v in row.items() if k not in ('pages','low_recall_pages')},ensure_ascii=False),flush=True)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f: json.dump(report,f,ensure_ascii=False,indent=2)

if __name__=='__main__': main()
