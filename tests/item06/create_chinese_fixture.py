"""Authored acceptance document containing the actual matrix timing experiment."""
import json,sys
from common import BASE,write,digest
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Preformatted,Table,TableStyle
from reportlab.lib import colors
import pypdfium2 as pdfium
if __name__=='__main__':
    path=BASE/'chinese-acceptance.pdf';assert not path.exists();experiment=json.loads((BASE/'matrix-experiment.json').read_text(encoding='utf8'))
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    body=ParagraphStyle('body',fontName='STSong-Light',fontSize=11,leading=19,wordWrap='CJK',spaceAfter=11)
    heading=ParagraphStyle('heading',parent=body,fontSize=15,leading=23,spaceBefore=10)
    title=ParagraphStyle('title',parent=body,fontSize=19,leading=29)
    story=[]
    def p(text,style=body):story.append(Paragraph(text,style))
    p('矩阵运算计时与科研文稿溯源测试',title);p('人工编写的验收文稿；不是已发表论文或模型精度报告。')
    p('摘要',heading)
    p('本文记录一次本机矩阵运算计时实验，用于验证科研文稿的中译英、术语一致性与数字回溯。矩阵维度为64、128、256、512、1024，每项操作重复7次，取耗时中位数，单位为毫秒。')
    p('实验配置请求1个计算线程，实际线程数未独立测量，随机种子为20261029。本文同时使用编码器、解码器、注意力机制与低秩适配等术语作为翻译检查内容，不宣称运行了这些模型。')
    p('1 引言',heading)
    p('科学翻译需要保留原文位置、术语和数字。注意力机制可以连接编码器与解码器；低秩适配和人类反馈是本次写作测试使用的领域词汇，本计时实验不评价其性能。')
    p('研究结论与系统验收必须分开。本稿只证明这一输入的翻译和绘图处理情况，不能代替独立研究评估。')
    story.append(PageBreak());p('2 方法',heading)
    p('计时使用实际运行的NumPy运算，包括矩阵乘法、矩阵加法和逐元素乘法。每个维度先预热，再重复7次。输入由固定种子产生；报告保留每次原始计时和汇总中位数。')
    p('以下公式与代码用于检查翻译保护规则，必须保留原样：')
    story.append(Preformatted('$f(x) = x^2 + 1$',ParagraphStyle('mono',fontName='Courier',fontSize=11,leading=17)))
    story.append(Preformatted('```python\ndef forward(x):\n    # Keep this English comment.\n    return x + 1\n```',ParagraphStyle('code',fontName='Courier',fontSize=10,leading=16)))
    p('3 结果',heading)
    p('下表来自本项真实本机计时，数值是毫秒。行序表示矩阵维度递增，不等于时间序列，不据此推断因果。')
    rows=[['dimension','matmul_ms','add_ms','multiply_ms']]+[[str(r[k]) for k in ['dimension','matmul_ms','add_ms','multiply_ms']] for r in experiment['rows']]
    table=Table(rows,colWidths=[95,105,105,105]);table.setStyle(TableStyle([('FONT',(0,0),(-1,-1),'Courier',9),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#c9d5ce')),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7efeb')),('BOTTOMPADDING',(0,0),(-1,-1),8)]));story.append(table)
    p('4 局限与结论',heading)
    p('处理器、内存、调度和计时误差都可能影响结果。本稿没有把耗时当作模型准确率，也没有依据图形外观预测未来结果。翻译后应逐段核对全部数字、术语、公式和代码。')
    SimpleDocTemplate(str(path),pagesize=(595.28,841.89),rightMargin=50,leftMargin=50,topMargin=45,bottomMargin=45,title='矩阵运算计时与科研文稿溯源测试').build(story)
    doc=pdfium.PdfDocument(str(path));images=[]
    for i,page in enumerate(doc):
        target=BASE/f'chinese-source-page-{i+1}.png';page.render(scale=1.4).to_pil().save(target);images.append(target.name)
    write(BASE/'chinese-fixture.json',{'file':path.name,'sha256':digest(path),'pages':len(doc),'origin':'authored acceptance document using actual local matrix timing data; not a published paper','page_images':images});print('Created and rendered',len(doc),'pages')
