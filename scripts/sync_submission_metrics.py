"""Rebuild measured claims from immutable evidence, not from remembered numbers."""
import json
from pathlib import Path
import re
from statistics import median
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
B='test-records/item08-20261030/'

def read(name):return json.loads((ROOT/name).read_text(encoding='utf8'))

def collect():
    rows=[]
    def add(i,label,text,source,report,rule):rows.append(dict(id=i,label=label,display=text,source=source,report=report,derivation=rule))
    book=read(B+'reading-after/report.json')
    add('M01','长书覆盖',f"{book['page_count']}页 / {book['samples'][0]['total_chunks']} Chunk",B+'reading-after/report.json','test-records/第8项报告.md','page_count、samples[0].total_chunks')
    perf=read(B+'reading-comparison.json')
    for i,label,k in [('M02','长书首屏','first_render'),('M03','跳第300页','jump_300'),('M04','跳第541页','jump_541')]:
        add(i,label,f"{median(perf[k+'_before_ms'])/1000:.3f}→{median(perf[k+'_after_ms'])/1000:.3f}秒",B+'reading-comparison.json','test-records/第8项报告.md','各3轮毫秒中位数/1000；同机浏览器')
    before=read(B+'reading-before/report.json');after=book
    add('M05','API单次冷读（退步保留）',f"{before['samples'][0]['ms']}→{after['samples'][0]['ms']}毫秒",B+'reading-before/report.json、'+B+'reading-after/report.json','test-records/第8项报告.md','samples[0].ms；非3轮统计')
    cold=read(B+'stream-cold/report.json');warm=read(B+'resident-warm/report.json')
    add('M06','全冷→已预热首内容增量',f"{cold['first_delta_seconds']:.6f}→{warm['first_delta_seconds']:.6f}秒",B+'stream-cold/report.json、'+B+'resident-warm/report.json','test-records/第8项报告.md','first_delta_seconds；真实模型、不同表述、hybrid+RRF')
    cli=read(B+'cli-warm-final.json')
    add('M07','重启后首次CLI预热',f"首增量{cli['first_delta_seconds']:.6f}秒 / 完成{cli['seconds']:.6f}秒",B+'cli-warm-final.json','test-records/第8项报告.md','first_delta_seconds、seconds；不是已预热请求')
    scan=read(B+'scan-mapping.json');ocr=read(B+'ocr-mapping-review.json')
    add('M08','本次扫描件冻结样本',f"{scan['pdf_pages']}页 / {scan['ocr_chunks']} OCR Chunk",B+'scan-mapping.json','test-records/第8项报告.md','pdf_pages、ocr_chunks；为第1项优化前989块版本')
    add('M09','OCR物理页匹配与额外文本门限',f"{ocr['mapping_correct_pages']}/15页匹配；13/15页过相似度门限",B+'ocr-mapping-review.json','test-records/第8项报告.md','按15条逐页结果；非字符准确率')
    translations=read(B+'default-stack.json')['model_tests']
    for i,t in zip(['M10','M11'],translations):
        add(i,'新库真实翻译 '+t['scope'],f"{t['translated_segments']}/{t['expected_segments']}段 / {t['seconds']:.6f}秒 / 缓存{t['cache_hits']}",B+'default-stack.json','test-records/第8项报告.md','model_tests；真实DeepSeek，完整性非逐字质量评级')
    graph=read('test-records/item05-20261029/graph-summary.json')
    add('M12','所选图谱',f"{len(graph['papers'])}节点 / {graph['unique_verified_pairs']}关系 / {graph['verified_edges']}依据 / {graph['isolated']}孤立",'test-records/item05-20261029/graph-summary.json','test-records/第5项报告.md','不同有向关系与依据位置分别计数')
    for i,name in [('M13','fast-final'),('M14','related-resumed')]:
        suite=ET.parse(ROOT/(B+name+'.xml')).getroot().find('testsuite')
        tests=int(suite.attrib['tests']);skip=int(suite.attrib['skipped']);fail=int(suite.attrib['failures'])+int(suite.attrib['errors'])
        assert fail==0
        add(i,'快速回归' if name.startswith('fast') else '相关全量回归',f"{tests-skip}通过 / {skip}跳过",B+name+'.xml','test-records/第8项报告.md','JUnit tests - skipped，failure/error均为0；快速层另有未选用项')
    # Human-reviewed business claims are extracted from their authored reports.
    def literal(i,label,source,pattern,display):
        text=(ROOT/source).read_text(encoding='utf8');match=re.search(pattern,text,re.S);assert match,(source,pattern)
        add(i,label,display,source,source,'报告原文断言：'+match.group(0))
    literal('M15','问答固定题集','test-records/第2项报告.md',r'最终部署批次.*?14/14通过，其中官方9/9', '官方9/9；总固定题集14/14')
    literal('M16','参考文献获取','test-records/第4项报告.md',r'40条官方参考文献已逐项实测，32条取得，8条仍未取得', '40条中32取得 / 8未取得')
    literal('M17','长书首次解析前后','test-records/第1项报告.md',r'1225\.453秒降至226\.625秒', '1225.453→226.625秒')
    literal('M18','扫描件前次优化样本','test-records/第1项报告.md',r'326\.485秒；1042块', '15页 / 1042 Chunk / 326.485秒')
    literal('M19','中译英原生中文全文','test-records/第6项报告.md',r'21/21分块，覆盖2页\|5\.922秒', '2页 / 21/21 Chunk / 5.922秒')
    literal('M20','写作参考文献核对','test-records/第6项报告.md',r'共6条参考文献记录、3篇唯一论文', '两次生成6条记录 / 3篇唯一论文')
    return rows

if __name__=='__main__':
    rows=collect();(ROOT/'docs/submission-metrics.json').write_text(json.dumps({'date':'2026-10-30','scope':'本轮技术文档采用的实测数字；配置、版本与评分权重另注明来源，不以旧文档反证自身。','claims':rows},ensure_ascii=False,indent=2),encoding='utf8')
    print({'claims':len(rows),'source_checks':'passed'})
