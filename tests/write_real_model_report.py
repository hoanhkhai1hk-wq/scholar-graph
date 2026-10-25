"""Render accepted answers and allowlisted statistics; never render raw protocol bodies."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'tests/reports'


def load(name):
    return json.loads((REPORTS / name).read_text(encoding='utf-8'))


def main():
    final = load('real-model-orchestration-results.json')
    audit = load('real-model-orchestration-audit.json')
    interpretations = [
        '第6作者为 Aidan N. Gomez，首页列出的机构为 University of Toronto。作者块按行/列坐标辅助恢复顺序，未把同块另一位作者误当第6位。',
        'Adam：β₁=0.9，β₂=0.98。',
        'Base训练使用8个GPU，型号为 NVIDIA P100。',
        'English-to-German：Transformer (big) 为28.4 BLEU；当时表中的最佳既往结果为26.36（Deep-Att + PosUnk Ensemble）。代码计算28.4−26.36=2.04 BLEU；论文正文的措辞是超过2.0，并非逐字写2.04。',
        'Jimmy Lei Ba、Jamie Ryan Kiros、Geoffrey E. Hinton，2016年。',
        'BERT承袭Vaswani等人的Transformer编码器实现，采用多层双向Transformer encoder。原始Transformer包含encoder和decoder；BERT保留编码器、没有原始序列到序列decoder部分。这是两篇架构原文的对照归纳，不是新增跨篇因果主张。',
    ]
    lines = [
        '# 真模型联调、LangGraph编排与Function Calling验收', '',
        '日期：2026-10-25。输入为**官方 pdf/ 真文件**，Attention v7与BERT N19-1423；语料仅保留在本地 pdf/，未进入Git。', '',
        '开工前 main：`' + audit['baseline_main'] + '`；`git pull --ff-only` 原文为 `Already up to date.`，开工工作区干净。', '',
        '本轮最终六题6/6通过，错前提示例拒答，真实多篇Agent在第3轮通过代码校验。全量回归326通过、0失败、0错误、0跳过；另以无Key子进程验证实连测试1项跳过。历史未通过轮次单列，未改写为通过。', '',
        '## 环境、模型与检索实际方式', '',
        '| 环境变量 | 状态 |', '| --- | --- |',
    ]
    lines += [f'| {name} | {value} |' for name, value in audit['environment'].items()]
    lines += ['',
        '服务商deepseek；请求模型名deepseek-chat（来自DEEPSEEK_MODEL），后端httpx 0.28.1调用官方HTTPS /chat/completions。只报告接口请求模型名，不推测服务商内部别名版本。规划和问答节点均为真实调用；校验节点为代码。thinking设为disabled，以使用required工具选择。', '',
        '本轮QA及Agent search均为**词法检索**：读取已有Chunk，扩展有限中英文检索词，选择最多24个连续证据窗口，单段≤600字符；未接入模块四BGE-M3/Chroma作为QA检索器。既有向量服务及其历史验收未改动。本轮模型负责选择真实原文，最终回答是有锚点的原文摘录，并非开放式生成文章。', '',
        'Key只从进程环境读取，未写入文件、代码或日志。不保留原始请求/响应、思考内容、工具原始查询正文或论文全文；下列答案是任务要求的已批准QAAnswer内容。LangGraph关闭检查点和外部追踪，状态只在内存。状态含paper_ids、bundles、evidence、anchors；不含Key或客户端对象。', '',
        '## 官方语料与已落盘记录', '',
        '| 本地文件 | PDF物理页数 | Chunk数 | paper_id |', '| --- | ---: | ---: | --- |',
    ]
    for source in audit['sources']:
        lines.append(f"| {source['file']} | {source['pages']} | {source['chunks']} | `{source['paper_id']}` |")
    lines += ['', 'Attention沿用已校验的解析结果；BERT通过已有模块一管线入库。审计重新核对PDF SHA-256、全部记录与锚点，不重造论文元数据。源摘要散列见审计JSON。', '',
              '## 六道命题例题逐题结果', '',
              '题面来自本地命题PDF，仅规范空格与β下标。所有页码为PDF物理页，锚点四项使用原契约。数字passed只说明与同一源Chunk字面回溯通过，不评价科学结论真实性。', '']
    for row, explanation in zip(final['cases'], interpretations, strict=True):
        lines += [f"### 第{row['case']}题：{'通过' if row['passed'] else '未通过'}", '', row['question'], '',
                  '**核对结论：**' + explanation, '', f"HTTP {row['http_status']}；程序检查：`{json.dumps(row['verification'], ensure_ascii=False)}`。", '']
        records = row['result']['per_paper'] if row['case'] == 6 else [row['result']]
        for n, record in enumerate(records, 1):
            lines += ([f'逐篇{n}：', ''] if len(records) > 1 else [])
            lines += ['已批准答案原文：', '', '```text', record['answer'], '```', '',
                      f"数字回溯：`{record['numeric_fact_check']['status']}`；拒答：`{str(record['refused']).lower()}`；锚点：", '',
                      '```json', json.dumps(record['anchors'], ensure_ascii=False, indent=2), '```', '']
        if 'derived_numeric_check' in row:
            lines += ['差值由Decimal代码计算：`28.4 - 26.36 = 2.04 BLEU`，两个源数字均已通过锚点检查；派生说明与源锚点保存在结果JSON中，不把派生值塞回原文摘录。', '']
        calls = row['metadata']['model_calls']
        lines += [f"真实模型调用{len(calls)}次；累计调用耗时{sum(c['elapsed_seconds'] for c in calls):.6f}秒；token合计{sum(c['total_tokens'] for c in calls)}。", '']
    lines += ['多篇响应仍先返回evidence_table，再返回逐篇QAAnswer与引用该表的synthesis；综合只并列已核验摘录，并明确跨篇因果不可验证。完整表与数字检查逐项证据在结果JSON，无额外业务Schema。', '',
              '## 故意错前提拒答', '', final['refusal']['question'], '', '```text', final['refusal']['result']['answer'], '```', '',
              f"HTTP {final['refusal']['http_status']}，refused=true；数字状态为`{final['refusal']['result']['numeric_fact_check']['status']}`。本次模型拒绝提供支持错误前提的摘录，未把β₁=0.5、β₂=0.6标为通过；此例没有输出纠正数字，不能冒充已给出纠错证据。第2题另有0.9/0.98的真实锚点答案。", '',
              '独立回归还覆盖模型给出原文纠错证据时，代码将具名β参数冲突标failed并附锚点；该项为模拟协议测试，不冒充第二次真实纠错调用。', '',
              '## 完整真实走图记录', '',
              'LangGraph 1.2.17：plan→retrieve→qa→validate；校验不通过回retrieve，最多3轮；超限进入refuse。以下来自单独一次真实多篇任务，而非手写轨迹。默认deepseek /compare本身也使用联合图。', '',
              '| 节点 | 轮次 | 耗时秒 | 证据数 | 校验 | 原因 |', '| --- | ---: | ---: | ---: | --- | --- |']
    meta = final['orchestration']['metadata']
    for row in meta['trace']:
        state = '通过' if row['validation'] is True else '未通过' if row['validation'] is False else '未执行校验'
        lines.append(f"| {row['node']} | {row['attempt']} | {row['elapsed_seconds']:.6f} | {row['evidence_count']} | {state} | {row.get('validation_error') or ''} |")
    lines += ['',
        '真实两次驳回原因：同一Chunk所选两处原文跨度超过600字符；重新检索并重新问答，第三次获得合法连续原文。未返回前两轮未校验草稿。最终fallback_reason=null、validated=true；没有把回落或超限拒答写成本次业务成功。', '',
        '## Function Calling实际调用轨迹', '',
        '模型规划响应包含实际tool_calls，后端执行工具，将同一tool_call_id的role=tool结果回传后再调用问答模型。下表只保留参数摘要和返回摘要，查询正文不落盘。', '',
        '| 轮次 | 工具 | 模型调用ID | 参数摘要 | 返回摘要 | 工具耗时秒 |', '| ---: | --- | --- | --- | --- | ---: |',
    ]
    mapping = {s['paper_id']: 'Attention' if n == 0 else 'BERT' for n, s in enumerate(audit['sources'])}
    for tool in meta['tool_calls']:
        args = tool['arguments_summary']
        label = ','.join(mapping[pid] for pid in args['paper_ids'])
        lines.append(f"| {tool['attempt']} | {tool['tool_name']} | `{tool['tool_call_id']}` | {label}；query_chars={args['query_chars']}；limit={args['limit']} | {tool['return_summary']['evidence_count']}条；lexical；{tool['status']} | {tool['elapsed_seconds']:.6f} |")
    lines += ['',
        '三个工具均定义了严格参数Schema（全字段必填、禁止额外字段）：search复用真实Chunk词法取证；graph_query复用既有构图；arxiv_fetch按名复用现有抓取服务和模块一解析，需要显式allow_fetch及fetcher。本轮对比不授权新增论文，HTTP Agent中的arxiv_fetch会明确拒绝。真实演示为search；graph_query/arxiv_fetch仅验证实际分派及模拟抓取失败，未宣称三工具都完成线上调用。', '',
        '## 上游错误、回落与兼容性', '',
        '默认deepseek上游失败返回HTTP502及原统一三字段UPSTREAM_ERROR，无原始上游正文；模拟覆盖HTTP401/429/500/302的脱敏错误返回。显式?agent=true允许模型不可用时回落原QuestionAnswerer，元数据记录MODEL_CONFIGURATION_UNAVAILABLE或UPSTREAM_ERROR；模拟覆盖规划/问答失联。没有人为中断本轮真实服务来冒充失联实测。', '',
        '单篇QAAnswer与跨篇三字段响应不变，全部已有契约零改动，端点仍19条。仅新增可选agent查询参数及UTF-8百分号编码的X-ScholarGraph-QA-Meta / X-ScholarGraph-Agent-Meta响应头；已在原CORS中暴露，保留既有同源代理。前端零修改，未验证前端展示；需用户转达WorkBuddy：如展示元数据，先解码这两个头。', '',
        '## 保留的历史未通过结果', '',
        '| 轮次 | 六题通过 | 拒答示例 | Agent | 当轮缺陷及处理 |', '| --- | --- | --- | --- | --- |',
    ]
    causes = [
        '作者题拒答；多篇证据不足；故意错问未拒答；Agent三轮未过门禁。后续加入题设具名参数检查、逐篇贡献规则。',
        '作者列块顺序误判；多篇HTTP422（同Chunk多段处理）。后续加入版面行序提示与连续原文合并。',
        '单窗口检索试验丢失SOTA表格证据，多篇一侧拒答。恢复双窗口并改联合规划。',
        'BLEU缺前SOTA表格分数，其他五题通过。增加表格覆盖校验及反馈，再取得最终六题通过结果。',
    ]
    for row, cause in zip(audit['historical_attempts'], causes, strict=True):
        lines.append(f"| {row['file']} | {row['passed']}/{row['total']} | {'通过' if row['refusal_passed'] else '未通过'} | {'通过' if row['agent_passed'] else '未通过'} | {cause} |")
    lines += ['',
        '最终作者序号门禁增加后单独重跑作者题，仍通过，证据保存在real-model-final-author-check.json；未覆盖此前整组六题结果。校验脚本重新核对该结果与其余答案。作者版面辅助不是通用完整作者抽取器，本篇只验收第6作者，不宣称所有作者/任意版面已正确恢复。', '',
        '## 调用元数据汇总', '',
        '| 范围 | 次数 | 调用耗时累计秒 | prompt tokens | completion tokens | total tokens |', '| --- | ---: | ---: | ---: | ---: | ---: |',
    ]
    for name, key in (('最终六题、拒答、单独Agent、作者补验、全量实连测试', 'current_retained_calls'),
                      ('四轮历史报告内保留的调用', 'historical_retained_calls')):
        stats = audit[key]
        lines.append(f"| {name} | {stats['calls']} | {stats['elapsed_seconds_sum']:.6f} | {stats['prompt_tokens']} | {stats['completion_tokens']} | {stats['total_tokens']} |")
    lines += ['',
        '上述服务商均deepseek，请求模型名均deepseek-chat。累计耗时是各次请求耗时之和，不是整单墙钟时间。初次连通额外1次：1.217860秒、37 prompt + 5 completion = 42 token；此前仅输出安全元数据未存原始正文，另记不重复计表。早期HTTP422丢失响应头的调用没有完整元数据，未计入汇总；不把已留存统计冒充完整账单。', '',
        '## 回归与审计', '',
        '全量命令：', '', '```powershell',
        'backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --run-real-model --basetemp data/real-model/full-regression-final --junitxml tests/reports/real-model-orchestration-pytest.xml',
        '```', '',
        '结果：326通过、0失败、0错误、0跳过，JUnit总耗时120.626秒。旧306项加新增20项（19项模拟/确定性、1项真实模型连通）。真实OCR也已启用；新模型协议测试使用自制数据，与本轮官方真文件实测分开登记。pip check：`No broken requirements found.`。', '',
        '另以删除三个变量的子进程运行test_deepseek_live.py --run-real-model：1项跳过，0失败/错误，退出码0；证据real-model-no-key-pytest.xml。无Key不是实连通过。', '',
        f"审计重新校验{audit['validated_qa_records']}份QAAnswer、{audit['validated_anchor_occurrences']}处锚点出现及比较表；核对六题、错误前提拒答、[false,false,true]的真实校验序列和{audit['actual_model_tool_calls']}次实际search工具调用。contracts/frontend/prompts/experiments/test-records相对基线无改动；pdf/忽略且Git未跟踪语料；全部本单文件完成真实Key字节扫描，未检出。", '',
        '## 复现与交付文件', '',
        '- tests/run_real_model_acceptance.py：使用现有官方落盘记录运行真实六题、拒答和Agent；--author-guard-only为最终作者补验。需要进程已有变量，不读取或写入Key文件。',
        '- tests/reports/real-model-orchestration-results.json：最终批准答案、完整锚点/数字检查、安全元数据与真实走图。',
        '- tests/reports/real-model-orchestration-attempt-1.json 至 attempt-4.json：保留历史失败。',
        '- tests/reports/real-model-final-author-check.json：最终作者门禁补验。',
        '- tests/audit_real_model_acceptance.py 与 real-model-orchestration-audit.json：无模型调用的本地源数据复核；重跑需要本地原文件/记录。',
        '- tests/write_real_model_report.py：仅渲染批准答案与安全元数据。',
        '- tests/reports/real-model-orchestration-pytest.xml 与 real-model-no-key-pytest.xml：全量与无Key跳过证据。', '',
        '技术依据：[DeepSeek工具调用协议](https://api-docs.deepseek.com/guides/tool_calls/)、[DeepSeek聊天API](https://api-docs.deepseek.com/api/create-chat-completion/)、[LangGraph图API](https://docs.langchain.com/oss/python/langgraph/graph-api)。', '',
    ]
    raw = '\n'.join(lines)
    key = os.environ.get('DEEPSEEK_API_KEY')
    if key and key in raw:
        raise RuntimeError('Refused to persist credential-containing report')
    path = REPORTS / 'real-model-orchestration-acceptance.md'
    path.write_text(raw, encoding='utf-8')
    print(json.dumps({'written': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size}))


if __name__ == '__main__':
    main()
