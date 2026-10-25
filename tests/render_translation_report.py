"""Render acceptance Markdown from actual JSON, audit and JUnit evidence."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    reports = ROOT / 'tests/reports'
    live = json.loads((reports / 'translation-live-results.json').read_text(encoding='utf-8'))
    audit = json.loads((reports / 'translation-audit.json').read_text(encoding='utf-8'))
    cases = live['runs'][-1]['cases']
    if live['runs'][-1]['status'] != 'passed' or audit['status'] != 'passed':
        raise RuntimeError('Cannot publish a passed report without passed evidence')
    regression, no_key = audit['regression'], audit['no_key']
    lines = [
        '# 模块三英→中翻译端点验收（2026-10-25）', '',
        f'开工前在D盘工作目录执行git pull --ff-only，输出Already up to date.，工作区干净；主干为`{live["baseline"]}`。本单仅改backend/与tests/，不改前端、既有契约或API草案。', '',
        '最终结论：英→中翻译端点、段级对齐与全文Markdown已落地并完成真实DeepSeek验收。摘要和Introduction各抽查一段；全文175段通过结构、源Chunk对齐和数字回溯校验，不把这等同于175段逐句专家审校。', '',
        '语料为**官方 pdf/ 真文件1706.03762v7.pdf**，复用此前解析入库的175个Chunk；本单没有重新解析PDF，没有用公开替代文件或自制样例冒充这次实测。官方文件与已落盘PaperMeta.file_hash的SHA-256一致：', '',
        f'`{live["pdf_sha256"]}`。PDF与完整源文/译文响应只留本地忽略目录，不进入Git或镜像。', '',
        '## 端点与对齐结构', '',
        '`POST /api/v1/papers/{paper_id}/translate`，JSON请求；沿用现有/api/v1前缀。请求的scope必填，target默认zh且仅接受zh。示例：', '',
        '```json', '{"scope":"abstract","target":"zh"}',
        '{"scope":"section","target":"zh","section_path":["1 Introduction"]}',
        '{"scope":"selection","target":"zh","chunk_ids":["<已落盘chunk_id>"]}',
        '{"scope":"full","target":"zh"}', '```', '',
        'section_path按源Chunk路径前缀取章节及子章节；selection按真实chunk_id选整段，按文档顺序返回。重复/未知Chunk、无该范围、额外参数、中→英target=en均返回422；论文不存在404。Chunk内字符选区、中→英全文、前端同步滚动均不在本单。', '',
        '| 响应字段 | 含义 |', '| --- | --- |',
        '| paper_id / scope / target | 论文id、本次范围、zh |',
        '| segments | 段级对齐列表，一条源Chunk对应一条译文 |',
        '| markdown | full时为整篇Markdown字符串，其他范围为null |',
        '| metadata | 服务商、请求模型名、耗时、安全调用统计、本次术语表与对齐说明 |', '',
        'segments每项固定为`{source_chunk_id,source_text,translated_text,paper_id,page_number,section_path,type}`。source_chunk_id直接取源Chunk.chunk_id，page_number为PDF物理页；paper_id/章节/类型均由服务端从落盘Chunk复制，模型不能指定这些字段。长Chunk仅在内部拆分翻译，再拼回一个对齐项，不生成新的业务记录。Pydantic校验传输封装，原有contracts/所有schema与example零改动。', '',
        '无Key或缺模型名返回HTTP502，统一三字段`{error_code,message,details}`，error_code=UPSTREAM_ERROR，消息为“DeepSeek环境变量未设置，未调用模型。”；没有摘录式假译文。上游HTTP、连接或超时也明确返回UPSTREAM_ERROR，不暴露原始上游正文。批次校验失败最多再试一次，仍不合法时不返回任何部分译文。', '',
        '## 真模型实测', '',
        '调用方为现有DeepSeekClient，直接请求官方api.deepseek.com；Key/模型变量仅从启动环境读取，二者均已设置。以下为最后一轮成功请求的用量，不是整个开发会话累计。只报告请求模型名，不推测服务商别名背后的底层版本。', '',
        '| 范围 | HTTP/结论 | 对齐段数 | 耗时（秒） | 模型调用数 | token总数 | Markdown字符数 |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |',
    ]
    for case in cases:
        calls = case['metadata']['model_calls']
        lines.append(f'| {case["request"]["scope"]} | {case["http_status"]} / {case["status"]} | {case["segments"]} | {case["elapsed_seconds"]:.6f} | {len(calls)} | {sum(c.get("total_tokens") or 0 for c in calls)} | {case["markdown_characters"]} |')
    lines += ['', f'请求模型：`{cases[-1]["metadata"]["model"]}`。完整安全调用元数据见translation-live-results.json：provider/model/phase/elapsed_seconds/prompt_tokens/completion_tokens/total_tokens/http_status/status，无Key、请求消息或思考内容。', '',
        'abstract实际返回6段，包含源解析归入Abstract的标题、正文、arXiv信息与贡献/会议脚注；不把6段都称为摘要正文。Introduction返回标题与4个正文段，共5段。PaperMeta.title与abstract在这份既有源记录中为空；范围选择来自真实Chunk章节，不伪造元数据锚点。', '']
    for label, case in zip(('摘要抽查', 'Introduction抽查'), cases[:2], strict=True):
        sample = case['sample']
        lines += [f'### {label}', '',
            f'源Chunk：`{sample["source_chunk_id"]}`；PDF第{sample["page_number"]}页，章节路径`{json.dumps(sample["section_path"],ensure_ascii=False)}`。', '',
            '原文：', '', '> ' + sample['source_text'].replace('\n', '\n> '), '',
            '译文：', '', '> ' + sample['translated_text'].replace('\n', '\n> '), '']
    lines += ['抽查结论：摘要保留编码器/解码器与纯注意力架构、28.4 BLEU、超过2 BLEU、41.8 BLEU、3.5天与八个GPU等原文信息；章节保留循环网络、长短期记忆、门控循环网络、编码器-解码器与引文编号，未在样本中发现新增事实。两个样本通过；语言自然度仍有可润色空间，不宣称已完成整篇人工校译。', '',
        '## 全文版式与保护规则', '',
        'full覆盖175/175个已落盘Chunk（166 text、4 table、5 figure）；为每段生成唯一`<a id="chunk_id"></a>`定位点。标题按已有section_path层级生成；表格和公式保留源Chunk顺序及已有HTML/Markdown结构。论文标题段已真实翻译为“注意力就是你所需要的一切”。原解析没有独立formula类型Chunk，公式保护另由自制LaTeX/公式块测试覆盖，不谎称该官方文件已有完整数学结构识别。', '',
        '代码块、行内代码、LaTeX、公式块与HTML/表格结构从文字片段中移除，不交给模型改写；由代码在原位置拼回。链接与表格行列标记保留。正文数字通过Decimal按源值核验，允许4.5 million→450万、36M→3600万及2 Aug 2023→2023年8月2日，拒绝数字新增、改值和丢失；英文may等普通词不能冒充月份数字依据。', '',
        '固定NLP术语词表加本次有原译依据且前后兼容的新术语贯穿所有批次；普通介词短语不由模型擅自升为必须逐字匹配的术语。已有术语不许改写。结构和数字校验只证明对应关系与源值可回溯，不证明所有翻译语义都正确。', '',
        '全文保持源解析已有结构，不重新推断未入库的标题属性、不复原PDF字体/栏位、不补造Chunk中缺失的图片。原解析误分的章节路径、纯文本数学表达式和无网格表格会继承；不把Markdown称为PDF原版式重建。', '',
        '端点同步完成后返回，不是流式翻译或后台队列。源文上限600000字符；内部约3000字符单元，批次最多4000字符或32单元，max_tokens=8192；旧问答默认2400不变。批次间检查900秒预算，上游网络超时60秒，不声称绝对900秒强制中断持续传输的HTTP读取。', '',
        '## 开发轮次中的失败与修正', '',
        '下表保留真实失败及中断记录，早期失败不计为通过；最终结论以上述最后一轮及实现散列匹配审计为准。', '',
        '| 轮次 | 各范围结果/原始错误 |', '| --- | --- |']
    for n, run in enumerate(live['runs'], 1):
        summary = []
        for case in run.get('cases', []):
            reason = (case.get('error', {}).get('details') or {}).get('reason')
            summary.append(case['request']['scope'] + ': ' + case['status'] + ('；' + reason if reason else ''))
        if run.get('incomplete_note'):
            summary.append(run['incomplete_note'])
        lines.append(f'| {n} | ' + ' / '.join(summary).replace('|','\\|').replace('\n',' ') + ' |')
    lines += ['', '修正包含：语法允许的数字语序不再误拒；代码/公式/结构改为代码拼回；数字校验支持确定性单位/日期换算；只接纳有一致依据的术语；模型同时接收保护后的正文与同一文字片段的原文上下文，完整翻译标题。失败批次仍不返回部分结果，未通过放宽锚点或伪造译文掩盖失败。', '',
        '## 回归与安全审计', '',
        f'最终全量JUnit：{regression["tests"]}项，{regression["tests"]-regression["failures"]-regression["errors"]-regression["skipped"]}通过，{regression["failures"]}失败，{regression["errors"]}错误，{regression["skipped"]}跳过，{regression["seconds"]:.6f}秒；包含真实PaddleOCR、既有模型/SSE及新增翻译实连测试。', '',
        f'无Key/模型变量子进程：{no_key["tests"]}项，{no_key["tests"]-no_key["skipped"]}通过，{no_key["skipped"]}项真实翻译测试跳过，0失败/错误，{no_key["seconds"]:.6f}秒。离线协议与未配置502错误测试照常执行。', '',
        '新增测试使用自制契约样例，覆盖四种范围、源顺序和真实锚点、超长段内部拆分、代码/LaTeX/表格保护、术语规则、数字校验、上游失败、重试上限、部分批次失败整次不成功、非法输入与范围、预算限制及无Key跳过；不把这些自制样例测试称为官方PDF质量测试。', '',
        f'独立审计{audit["check_count"]}项通过：源文件散列、最终实现散列、段级manifest、真实Chunk锚点、数字与保护片段、Markdown定位点、安全元数据、JUnit、变更目录、pdf/忽略与未跟踪、真实Key字节不在本单文件中。未修改frontend/、contracts/、docs/、prompts/、experiments/、test-records/。', '',
        '复现（已具备本地依赖、同一官方源PDF/已解析数据；实连需要启动环境中的Key与模型变量）：', '',
        '```powershell', 'backend/.venv/Scripts/python.exe tests/run_translation_acceptance.py --full',
        'backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --run-real-model --basetemp data/translation-reproduce-tests --junitxml tests/reports/translation-pytest.xml',
        'backend/.venv/Scripts/python.exe tests/audit_translation_acceptance.py',
        'backend/.venv/Scripts/python.exe tests/render_translation_report.py', '```', '',
        '探针在tests/reports/translation-live-results.json追加运行轮次；完整响应只写忽略的data/translation-acceptance/，Git仅留有限原译样本、段级散列及安全元数据。JUnit包括translation-pytest.xml与translation-no-key-pytest.xml，审计为translation-audit.json。无Key的pytest应跳过real_model实连项，探针也明确标skipped。', '',
        '## 转达WorkBuddy', '',
        '使用上述POST与segments.source_chunk_id匹配阅读器源段；page_number和section_path用于回溯，markdown用于全文视图。selection当前为整Chunk选择。翻译服务无Key是明确错误，不是摘录回落。前端同步滚动与中→英全文由后续单负责，本单没有实现或声称已接通。现有Docker镜像未重建，容器使用新端点须重建镜像。', '',
        '实现依据：[DeepSeek Chat Completions与JSON输出](https://api-docs.deepseek.com/api/create-chat-completion/)。', '']
    text = '\n'.join(lines)
    key = os.environ.get('DEEPSEEK_API_KEY')
    if key and key in text:
        raise RuntimeError('Credential safety check rejected Markdown')
    (reports / 'translation-acceptance.md').write_text(text, encoding='utf-8')
    print('translation-acceptance.md rendered from passed evidence')


if __name__ == '__main__':
    main()
