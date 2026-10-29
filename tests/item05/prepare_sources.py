"""Freeze original source selection and qualitative expectations before graph scores."""
from common import ROOT,BASE,write,digest
SOURCES=['1706.03762v7.pdf','N19-1423.pdf','language_understanding_paper.pdf',
 'language_models_are_unsupervised_multitask_learners.pdf','2005.14165v4.pdf','1910.10683v4.pdf',
 '2001.08361v1.pdf','1910.02054v3.pdf','2101.03961v3.pdf','2106.09685v2.pdf','2107.03374v2.pdf',
 '2201.11903v6.pdf','2203.02155v1.pdf','2205.14135v2.pdf','2210.02414v2.pdf',
 '333078981_693988129081760_4712707815225756708_n.pdf','2305.18290v3.pdf','2307.09288v2.pdf',
 '2412.19437v1.pdf','2501.12948v2.pdf']
if __name__=='__main__':
    assert not (BASE/'sources.json').exists()
    from pypdf import PdfReader
    rows=[{'filename':name,'sha256':digest(ROOT/'pdf'/name),'bytes':(ROOT/'pdf'/name).stat().st_size,
        'physical_pages':len(PdfReader(ROOT/'pdf'/name).pages)} for name in SOURCES]
    assert len(rows)==20 and len({r['sha256'] for r in rows})==20
    write(BASE/'sources.json',{'theme':'Transformer与大语言模型的架构、扩展和对齐','inputs':rows,
        'qualitative_expectations_before_graph':[
            {'filename':SOURCES[0],'expected':'cornerstone','basis':'Transformer架构基础；所选后续编码器、生成式预训练及大模型文献明确依赖此架构。预期为局域核心之一，不预设必为第一名。'},
            {'filename':SOURCES[-1],'expected':'derived','basis':'集合中时间较晚的推理对齐研究，预期引用前序工作、尚无本集合更晚论文引用；局域边缘不等于质量低。'},
            {'filename':SOURCES[-2],'expected':'derived','basis':'较新的MoE基础模型技术报告，预期入引较少；R1可能引用该基础模型，仍预期低于局域核心。'}]})
    print('Frozen 20 distinct PDFs:',sum(r['physical_pages'] for r in rows),'pages,',sum(r['bytes'] for r in rows),'bytes')
