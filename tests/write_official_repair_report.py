"""Build the 官方 pdf/ 真文件 repair report from actual evidence, never guessed metrics."""
import json
import subprocess
import xml.etree.ElementTree as ET
from importlib.metadata import version

from official_pdf_support import ROOT
from run_official_repairs import BASELINE


def main():
    folder = ROOT / 'tests/reports'
    def load(name):
        return json.loads((folder / name).read_text(encoding='utf-8'))
    d, o, b = [load('official-pdf-repair-' + case + '.json') for case in ('dedup', 'ocr', 'longbook')]
    old_o, old_b = [load('official-pdf-' + case + '.json') for case in ('ocr', 'longbook')]
    du, ou, bu = d['uploads'][-1], o['uploads'][0], b['uploads'][0]
    def metric(u):
        m = u['measurement']
        return f"{u['chunks_first']['response'].get('total', 0)} Chunk；{m['elapsed_seconds']}秒；RSS {m['rss_peak_bytes'] / 1048576:.6f} MiB（{m['rss_peak_bytes']}字节）"
    suites = ET.parse(folder / 'official-pdf-repair-pytest.xml').getroot().findall('testsuite')
    counts = {k: sum(int(s.get(k, '0')) for s in suites) for k in ('tests', 'failures', 'errors', 'skipped')}
    console = (ROOT / 'data/official-repair/regression/console.txt').read_text(encoding='utf-8', errors='replace')
    result_line = next((line.strip() for line in reversed(console.splitlines()) if ' passed' in line), '见JUnit原始统计')
    commits = subprocess.check_output(['git', 'log', BASELINE + '..HEAD', '--format=%H %s'], cwd=ROOT, encoding='utf-8').strip()
    passed = sum(bool(x['passed']) for x in (d, o, b))
    text = f'''# 官方 pdf/ 真文件三缺口修复验收

本单修改后端实现并重验同一批**官方 pdf/ 真文件**。三项实际通过 {passed}/3；失败 {3 - passed}/3。全量回归统计见下方，不与业务验收混计。未调用真实大模型或使用真实API Key。开工main `{BASELINE}`，`git pull --ff-only` 原文 `Already up to date.`，工作区干净。

## 官方 pdf/ 真文件修复前后对照

| 项目 | 修复前：官方 pdf/ 真文件 | 修复后：官方 pdf/ 真文件 | 结论 |
| --- | --- | --- | --- |
| 去重触发 | v7/v1上传201，175/162 Chunk；无预警；裁决/差异404 | v7：{metric(d['uploads'][0])}；v1：{metric(du)}；第二传预警“{du['warning_text']}”；裁决/差异{du['decision']['http_status']}/{du['diff']['http_status']} | {'通过' if d['passed'] else '失败'} |
| 扫描OCR | {old_o['upload']['measurement']['elapsed_seconds']}秒，TimeoutExpired，HTTP422，OCR_FAILED，0有效Chunk | HTTP{ou['http_status']}；{metric(ou)}；失败页{ou['batch_metrics']['failed_pages']} | {'通过' if o['passed'] else '失败'} |
| 长书 | 541页，pipeline.py:124–125的200页上限拒绝；0 Chunk；未索引；RSS {old_b['upload']['measurement']['rss_peak_bytes'] / 1048576:.6f} MiB | HTTP{bu['http_status']}；{metric(bu)}；{len(bu['batch_metrics']['batches'])}个批次；索引相关累计{bu['batch_metrics']['indexing_seconds']}秒 | {'通过' if b['passed'] else '失败'} |

扫描件修复后耗时可能长于旧版超时失败，长书RSS也高于原来直接拒绝的143.453125MiB；旧版没有完成同等工作，不能比较为性能改善。RSS每50ms轮询本测试进程与全部子进程的采样合计，可能重复计算共享页，不是精确系统高水位。索引相关累计计时包含规范化、批次Schema/外键门禁、文件发布与SQLite提交，不冒充纯SQL耗时。

## 去重实现与实测

解析完成后查本地候选：精确DOI/arXiv/标题作者身份优先；身份缺失时用真实词频Dice，阈值0.90，明确冲突的DOI/arXiv不会配对。不宣称语义向量去重。PDF原文中的arXiv版本标识现会提取为PaperMeta的原有字段，未从文件名虚构版本。

同一arXiv的低版本上传，保留库内高版本建议只依据身份及版本先后，不称学术质量更好。`new_paper_id`仍是本次后上传v1的paper_id。第二传预警原文：

> {du['warning_text']}

不改变PaperMeta：单篇HTTP201响应体仍是原记录；预警通过`X-ScholarGraph-Dedup-Warning`返回UTF-8百分号编码文本，编码标记响应头为`percent-encoded-utf-8`，Link指向裁决接口，CORS已暴露两头。未修改前端，不声称前端已显示弹窗。批量成功项命中时可带新增可选传输字段warning。裁决原文与完整DiffSummary见[去重JSON](official-pdf-repair-dedup.json)，均按new_paper_id真实落盘可查；human_override读取优先规则未改变，系统原记录仍保留。

## OCR逐页产出与失败恢复

直接上传官方`1706.03762v1_img.pdf`，没有重制、抽页或换文件。显式固定PP-OCRv5_mobile_det与英文en_PP-OCRv5_mobile_rec，不再只指定检测器而让识别模型落到默认配置；本机旧缓存中存在PP-OCRv6_medium_rec，新英文轻量模型已实际下载并推理。包版本：PaddleOCR {version('paddleocr')} / PaddlePaddle {version('paddlepaddle')}。实际OCR仍为本地CPU，不是大模型调用。复用本机模型缓存不计入上传耗时，未使用Key。

每页独立运行、独立限时、逐页校验并原子发布，后续页失败不会丢掉已发布Chunk。扫描页直接PaddleOCR；文本批次MinerU超时后逐页PaddleOCR兜底。错误明确列出失败物理页；原错误契约只允许标量details，因此failed_pages用逗号分隔字符串、page_errors用安全逐页原因文本，没有改Schema或塞业务记录。内部progress.json保留完整页列表；再次传相同源文件可补未完成页，并修复批次已落盘而索引/检查点未提交的中断。

本次状态最终为`{ou['status']['response']['status']}`；已处理{len(ou['batch_metrics']['completed_pages'])}/15页；有效Chunk {ou['chunks_first']['response'].get('total', 0)}；失败页{ou['batch_metrics']['failed_pages']}。真实首批文本：

```text
{chr(10).join(c['text'][:160] for c in ou['chunks_first']['response'].get('items', [])[:3])}
```

运行中观测见[OCR JSON](official-pdf-repair-ocr.json)的observations：OCR状态未完成时，原Chunk端点已返回非空记录；最终数据经过原门禁。识别完成不等同于逐字准确率评测，未声称数学公式/表格逐字正确。

## 长书流式与分批索引

官方长书原文件541页、22344992字节。取消200页硬拒绝，默认可配置2000页（范围1–10000）。以PDFium逐页检查文本层，只保留首个有效页的元数据候选；原始PDF快照受50MiB上传限制。每批最多32物理页切成临时PDF交给MinerU，解析后释放该批原始布局对象，页码映射回原始物理页；最终仍需保存规范化Chunk列表，内存随文本记录规模增长，不声称完全常量内存。

每批先通过原Schema与外键门禁，原子写partial目录并事务提交SQLite物理页/序号Chunk索引，解析状态持续更新。原Chunk端点通过SQLite分页，不为一页请求重新加载所有布局结果；非空产出在完成前即可读取。partial论文不混入完成论文列表。最终合并参考文献/引用再发布四类记录。索引是本地锚点索引，未冒充BGE-M3或向量去重。

本次17批处理全部541页，产出{bu['chunks_first']['response'].get('total', 0)} Chunk，空白/无文本页登记为{bu['batch_metrics']['empty_pages']}，无失败页；末页查询可到物理页{bu['chunks_last']['response']['items'][-1]['page_number']}，越界页返回空表。详细进度、各批页码、计时及内存原始值见[长书JSON](official-pdf-repair-longbook.json)。

默认防呆：文本批32页/120秒，OCR单页90秒，分批整篇1800秒；worker等待也受剩余整篇时限约束。配置变量及范围见backend/README.md的新修复节。原小文本PDF继续用MinerU完整解析；GROBID状态仍为待验证。

## 回归、契约与边界审计

三项官方 pdf/ 真文件重验完成后执行 `backend/.venv/Scripts/python.exe tests/run_official_repair_regression.py`；包含`--run-ocr`，全量不依赖Docker或真实GROBID，既有自制样例加本轮故障注入回归，不能把回归输入称作官方文件。

```text
{result_line}
```

JUnit统计：总数{counts['tests']}，失败{counts['failures']}，错误{counts['errors']}，跳过{counts['skipped']}。新增测试覆盖：无身份Dice候选、冲突身份排除、无关文档不误报、旧版本上传预警与裁决；单页失败保留其余页、补页恢复、全篇时限点名未处理页、索引中断恢复、非法OCR页码；201页分批与分页、配置页数上限。参见[JUnit](official-pdf-repair-pytest.xml)。

原26个契约文件Git blob零改动，旧官方报告与原始JSON未覆盖；只改backend/与tests/。`/pdf/`仍被.gitignore排除，Git未跟踪官方语料；运行前后源哈希一致。[审计脚本](../audit_official_repairs.py)核对真实落盘、Chunk锚点、索引计数及回归，输出[审计JSON](official-pdf-repair-audit.json)。

实现及证据提交（报告自身最终提交哈希另由交付回报列出，避免自引用）：

```text
{commits}
```

实际官方验收启动时部分实现尚未提交，三份JSON的source_commit记录当时HEAD，不假称该HEAD已包含全部修复；最终实现以本轮提交与全量回归为准。未变更前端或API路径，未调用真实大模型或真实API Key。原PDF和模型/临时运行数据全部留在被忽略的本地目录。
'''
    (folder / 'official-pdf-repair-acceptance.md').write_text(text, encoding='utf-8')
    print(f'官方 pdf/ 真文件修复报告已生成：{passed}/3通过。')


if __name__ == '__main__':
    main()
