"""Authored PDFs + explicitly manual source segments, never official parser evidence."""
import copy,hashlib,json,sys,textwrap
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.pagesizes import A4
import pypdfium2 as pdfium

ROOT=Path(__file__).resolve().parents[2]; BASE=ROOT/'data/item03-20261028'; sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.validation import ContractGate
from scholar_graph.pdf_files import PdfFiles

FENCE='```python\ndef forward(x):\n    # Keep this English comment unchanged.\n    return x + 1\n```'
LATEX=r'\begin{aligned} f(x) &= \frac{x^2+1}{2} \\ g(x) &= \beta_1 + 0.98 \end{aligned}'
HTML='<pre><code>print("Keep English text unchanged")\n# Do not translate this comment</code></pre>'
INLINE='`return x + 1`'
MATH=r'$x_1 + x_2$'


def create(language):
    chinese=language=='zh'; name=f'controlled-protection-{language}.pdf'; path=BASE/name
    if path.exists(): raise FileExistsError(path)
    title='人工自编翻译保护样本（非官方论文）' if chinese else 'Authored translation protection fixture (not an official paper)'
    abstract='本样本用于核对真实翻译服务中的代码、公式和原文位置。它是一份人工构造的测试文档，不代表科研成果。' if chinese else 'This authored fixture checks the real translation service, protected code and equations, and source page alignment. It is a controlled test document, not a scientific finding.'
    prose=('请翻译此段说明，保留以下行内代码和公式：' if chinese else 'Translate the surrounding explanation, keeping this inline code and equation unchanged: ')+INLINE+' '+MATH
    specs=[(1,['摘要' if chinese else 'Abstract'],'text',abstract),
           (1,['1 方法' if chinese else '1 Method'],'text',prose),
           (2,['2 保护片段' if chinese else '2 Protected spans'],'text',('下面是源代码：\n' if chinese else 'The following is source code:\n')+FENCE),
           (2,['2 保护片段' if chinese else '2 Protected spans'],'formula',LATEX),
           (2,['2 保护片段' if chinese else '2 Protected spans'],'text',('以下为HTML代码块：\n' if chinese else 'The following is an HTML code block:\n')+HTML)]
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light')); document=canvas.Canvas(str(path),pagesize=A4)
    document.setTitle(title); font='STSong-Light' if chinese else 'Courier'
    for page in [1,2]:
        y=805; document.setFont(font,10)
        document.drawString(35,y,title); y-=30
        for number,section,kind,text in specs:
            if number!=page: continue
            document.drawString(35,y,section[-1]); y-=20
            for line in text.splitlines():
                for part in textwrap.wrap(line,width=48 if chinese else 85,replace_whitespace=False,drop_whitespace=False) or ['']:
                    document.drawString(35,y,part); y-=17
            y-=20
        document.showPage()
    document.save()
    digest=hashlib.sha256(path.read_bytes()).hexdigest(); pid='paper-'+digest
    with pdfium.PdfDocument(str(path)) as pdf:
        texts=[page.get_textpage().get_text_range() for page in pdf]
    normalized=lambda text:''.join(text.split())
    assert all(normalized(text) in normalized(texts[page-1]) for page,_,_,text in specs)
    meta=json.loads((ROOT/'contracts/paper-meta.v1.example.json').read_text(encoding='utf-8'))
    meta.update(id=pid,title=title,authors=['Authored acceptance fixture'],institutions=[],abstract=abstract,
                source='controlled-test-fixture-manual-segmentation',file_hash=digest,page_count=2)
    prototype=json.loads((ROOT/'contracts/chunk.v1.example.json').read_text(encoding='utf-8'))
    chunks=[]
    for index,(page,section,kind,text) in enumerate(specs,1):
        item=copy.deepcopy(prototype); item.update(chunk_id=f'{pid}-p{page:04d}-c{index:05d}',paper_id=pid,page_number=page,
                section_path=section,heading_1=section[0],heading_2=None,heading_3=None,text=text,type=kind,bbox=None); chunks.append(item)
    bundle={'paper_meta':meta,'chunks':chunks,'reference_entries':[],'citation_links':[]}
    repository=ApiRepository(BASE/'records',ContractGate()); repository.store.paper(bundle); PdfFiles(BASE/'records').retain(path,meta)
    return {'paper_id':pid,'file':name,'sha256':digest,'pages':2,'chunks':5,'source_method':'author-defined source segments verified against actual PDF text, not automatic parsing','expected_protected':[FENCE,LATEX,HTML,INLINE,MATH]}


if __name__=='__main__':
    report={'english':create('en'),'chinese':create('zh')}
    (BASE/'protection-fixtures.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:{a:b for a,b in v.items() if a!='expected_protected'} for k,v in report.items()},ensure_ascii=False))
