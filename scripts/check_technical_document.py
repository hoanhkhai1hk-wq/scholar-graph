"""Verify source-backed claims, required disclosures, PDF pages and page bounds."""
import hashlib
import json
from pathlib import Path
import sys
from pypdf import PdfReader
import pypdfium2 as pdfium
from PIL import Image, ImageDraw
from sync_submission_metrics import collect

ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    base=ROOT/'data/submission-20261030';out=base/'technical-pages';out.mkdir(exist_ok=True)
    md=(ROOT/'docs/technical-document.md').read_text(encoding='utf8');claims=collect()
    registry=json.loads((ROOT/'docs/submission-metrics.json').read_text(encoding='utf8'))['claims']
    assert claims==registry,'Measured values changed: update the registry and document in a small patch'
    pdf=ROOT/'docs/technical-document.pdf';r=PdfReader(pdf);assert 1<=len(r.pages)<=30
    text='\n'.join(p.extract_text() or '' for p in r.pages)
    compact=''.join(text.split());checks=[]
    for row in claims:
        assert row['display'] in md,row['id']
        assert ''.join(row['display'].split()) in compact,('PDF missing metric',row['id'])
        checks.append({'id':row['id'],'source_matches':True,'markdown_matches':True,'pdf_matches':True})
    required=['黄伟浩','广州商学院','B 组个人赛','每一句回答，都能点回原文的那一页','扫描','页级','RRF','reranker未上线','FlagEmbedding','待核','预热','在线演示地址','待实际部署填写','35%','15%','30%','10%','不超过30页','a–f']
    for word in required:assert ''.join(word.split()) in compact,word
    for banned in ['划词／悬停翻译未实现','三维雷达图未实现','命题全部通过','稳拿']:
        assert banned not in md,banned
    pages=[];renders=pdfium.PdfDocument(str(pdf))
    for i,p in enumerate(renders):
        p.render(scale=1.25).to_pil().save(out/f'page-{i+1:02}.png')
        textpage=p.get_textpage();count=textpage.count_chars();bounds=[]
        for n in range(count):
            box=textpage.get_charbox(n)
            # Whitespace and combining glyphs can have empty/infinite boxes.
            if box[2]>box[0] and box[3]>box[1] and (box[0]<0 or box[1]<0 or box[2]>p.get_width()+1 or box[3]>p.get_height()+1):bounds.append(n)
        assert not bounds,('Text outside physical page',i+1,len(bounds))
        pages.append({'page':i+1,'chars':count,'out_of_page_characters':0})
    w,h=360,510;cols=3;rows=(len(pages)+cols-1)//cols;sheet=Image.new('RGB',(cols*w,rows*(h+25)),'#dce5e1');draw=ImageDraw.Draw(sheet)
    for i in range(len(pages)):
        im=Image.open(out/f'page-{i+1:02}.png').convert('RGB');im.thumbnail((w-10,h));x=(i%cols)*w+5;y=(i//cols)*(h+25)+22;sheet.paste(im,(x,y));draw.text((x,y-18),str(i+1),fill='black')
    sheet.save(base/'technical-contact-sheet.png')
    report={'passed':True,'pages':len(r.pages),'limit':30,'pdf_bytes':pdf.stat().st_size,'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'claims':checks,'physical_bounds':pages,'visual_review':'pending','note':'Bounds and text checks supplement, not replace, visual review of rendered pages.'}
    (base/'document-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:report[k] for k in ['passed','pages','pdf_bytes','pdf_sha256']}))
