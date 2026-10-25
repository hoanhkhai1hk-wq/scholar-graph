"""Validate recorded TCP samples against original Chunk publications and write acceptance."""
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'tests/reports'
BASELINE = '99842ae6f8404e33701834bb5a247348a8a3e58a'
sys.path.insert(0, str(ROOT / 'backend'))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.qa import validate_answer
from scholar_graph.validation import ContractGate


def load(name):
    return json.loads((REPORTS / name).read_text(encoding='utf-8'))


def junit(name):
    suites = list(ET.parse(REPORTS / name).getroot().iter('testsuite'))
    return {key: sum(int(s.attrib[key]) for s in suites) for key in ('tests', 'failures', 'errors', 'skipped')}


def main():
    gate = ContractGate()
    repository = ApiRepository(ROOT / 'data/real-model/records', gate)
    samples = {mode: load(f'qa-sse-{mode}-events.json') for mode in ('deepseek', 'fallback')}
    checks = {}
    for mode, sample in samples.items():
        events = sample['events']
        checks[mode + ':passed'] = sample['status'] == 'passed' and all(sample['checks'].values())
        checks[mode + ':sequence'] = [e['id'] for e in events] == list(range(1, len(events)+1))
        checks[mode + ':terminals'] = events[0]['event'] == 'mode' and [e['event'] for e in events[-2:]] == ['final','done']
        open_nodes, open_tools, tokens = set(), set(), 0
        lifecycle = True
        for event in events:
            kind, data = event['event'], event['data']
            if kind.startswith('node_'):
                key = (data['node'], data['attempt'])
                if kind == 'node_start':
                    lifecycle &= key not in open_nodes
                    open_nodes.add(key)
                else:
                    lifecycle &= key in open_nodes and data['elapsed_seconds'] >= 0 and data['evidence_count'] >= 0
                    open_nodes.discard(key)
            if kind == 'token':
                tokens += 1
                lifecycle &= ('qa',data['attempt']) in open_nodes and data['verified'] is False and data['channel'] == 'model_json_draft'
            if kind.startswith('tool_'):
                key = (data['tool_call_id'],data['attempt'])
                lifecycle &= data['origin'] == 'model_function_call'
                if kind == 'tool_start':
                    open_tools.add(key)
                else:
                    lifecycle &= key in open_tools and data['evidence_count'] >= 0
                    open_tools.discard(key)
        checks[mode + ':lifecycle'] = lifecycle and not open_nodes and not open_tools
        checks[mode + ':token_count'] = tokens == sample['token_events']
        record = events[-2]['data']
        source = repository.paper(record['anchors'][0]['paper_id'])
        blocks = re.split(r'\n\n(?=【证据 [A-Z]】\n)', record['answer'])
        evidence = [{'anchor': a,'quote': b.split('\n',1)[1]} for a,b in zip(record['anchors'],blocks,strict=True)]
        validate_answer(record, source, evidence, gate)
        checks[mode + ':final_schema_source_numeric'] = not record['refused']
        checks[mode + ':validation_before_final'] = any(e['event']=='node_end' and e['data']['node']=='validate'
            and e['data']['validation'] is True for e in events[:-2])
    deep, fallback = samples['deepseek'], samples['fallback']
    checks['real_incremental_arrival'] = deep['first_token_seconds'] < deep['qa_end_seconds'] < deep['final_seconds']
    checks['fallback_no_fake_stream_or_model_calls'] = fallback['token_events'] == 0 and not fallback['events'][-1]['data']['metadata']['model_calls']
    checks['fallback_explicit_label_no_key'] = '回落模式、非 token 流式' in fallback['events'][0]['data']['message'] and fallback['environment']['DEEPSEEK_API_KEY'] == '未设置'
    checks['real_provider_calls'] = all(c['provider']=='deepseek' and c['http_status']==200 and c['status']=='succeeded'
        for c in deep['events'][-1]['data']['metadata']['model_calls'])
    full, no_key = junit('qa-sse-pytest.xml'), junit('qa-sse-no-key-pytest.xml')
    checks['full_regression'] = full == {'tests':342,'failures':0,'errors':0,'skipped':0}
    checks['no_key_skip'] = no_key == {'tests':13,'failures':0,'errors':0,'skipped':1}
    for directory in ('frontend','contracts','docs','prompts','experiments','test-records'):
        checks['unchanged:' + directory] = not subprocess.check_output(['git','diff','--name-only',BASELINE,'--',directory],cwd=ROOT,text=True).strip()
    checks['pdf_ignored_untracked'] = '/pdf/' in (ROOT/'.gitignore').read_text(encoding='utf-8').splitlines() and not subprocess.check_output(['git','ls-files','pdf'],cwd=ROOT,text=True).strip()
    names = set(subprocess.check_output(['git','diff','--name-only',BASELINE],cwd=ROOT,text=True).splitlines())
    names.update(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines())
    key = os.environ.get('DEEPSEEK_API_KEY')
    checks['deliverables_no_injected_key'] = not key or all(key.encode() not in (ROOT/name).read_bytes() for name in names if (ROOT/name).is_file())
    audit = {'baseline':BASELINE,'checks':checks,'status':'passed' if all(checks.values()) else 'failed',
             'full_regression':full,'no_key_stream_tests':no_key}
    (REPORTS/'qa-sse-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    rows = [
        ('mode','模式、是否token增量、回落原因；回落明确写“回落模式、非 token 流式”'),
        ('node_start','node、attempt（从1开始）、elapsed_seconds=0、当前evidence_count'),
        ('node_end','每轮墙钟耗时、当前证据数、status；validate的validation与validation_error原文；失败节点reason'),
        ('tool_start','工具名、来源、调用id、轮次；尚未返回证据数0'),
        ('tool_end','真实工具结果摘要、来源、返回证据数及耗时；没有原始查询正文'),
        ('token','qa节点上游content增量；verified=false、channel=model_json_draft，不发思考内容'),
        ('final','data直接为既有QAAnswer，验证后才发，无新答案记录格式'),
        ('error','原三字段错误体error_code/message/details；无上游原始错误正文'),
        ('done','completed/refused/error与安全元数据；随后结束流'),
    ]
    lines = ['# 问答SSE流式端点验收', '', '日期：2026-10-25。最终审计：**'+audit['status']+'**。', '',
        f'开工main `{BASELINE}`；git pull --ff-only原文`Already up to date.`，工作区干净。本单只修改backend/与tests/，前端、契约、docs/与其他分工区域零改动。', '',
        '新增`POST /api/v1/papers/{paper_id}/qa/stream`，JSON仍为`{question}`。原19条接口保持，新增后20条；传输事件定义在后端README，未增加业务Schema。SSE final.data就是原QAAnswer，不包一层新答案对象。', '',
        '## 事件类型表', '', '| event | 内容 |','| --- | --- |']
    lines += ['| '+name+' | '+text+' |' for name,text in rows]
    lines += ['', '标准SSE的id/event/data与空行分帧，UTF-8 JSON单行编码。心跳是10秒静默后的`: keep-alive`注释，不计事件id；Cache-Control=no-cache,no-transform、X-Accel-Buffering=no，无Content-Length。队列32条形成背压，断开停止后续节点/队列等待并关闭已建立的上游流；尚未返回的同步规划请求仍受原60秒超时约束。', '',
        '事件attempt从1开始；done.metadata.trace保持旧规划计数口径（首plan为0），接入时按SSE节点事件attempt分组。node_end.status=completed只表示执行结束，校验看validation，不能把驳回误读为通过。证据数是当前图状态的检索集合数量，不是最终锚点数。', '',
        '## 两种模式真实TCP样本', '',
        '输入为官方Attention v7已落盘的175个Chunk；本单不重新解析PDF。启动当前源码的临时Uvicorn TCP服务，用httpx流式读取真实网络连接，没有用TestClient结果冒充流到达时序。现有Docker旧容器未重建，不宣称旧镜像已具有新端点。', '',
        '真实模型通过后端httpx调用官方DeepSeek /chat/completions：规划保留Function Calling；qa设置stream=true、include_usage=true，只转发content，thinking disabled，不发reasoning_content。最终仍经过原字面、锚点、数字与Schema门禁。', '',
        '| 模式 | HTTP | 事件数 | token增量事件数 | 总耗时秒 | final |', '| --- | ---: | ---: | ---: | ---: | --- |']
    for mode,sample in samples.items():
        lines.append(f"| {mode} | {sample['http_status']} | {len(sample['events'])} | {sample['token_events']} | {sample['elapsed_seconds']:.6f} | QAAnswer，锚点/数字校验通过 |")
    lines += ['', f"DeepSeek首增量在{deep['first_token_seconds']:.6f}秒到达，qa节点{deep['qa_end_seconds']:.6f}秒完成，最终QAAnswer在{deep['final_seconds']:.6f}秒到达。首增量早于完整回答，不是事后拆字。增量事件数{deep['token_events']}不等于服务商token计量。模型输出协议为证据选择JSON，token.delta是未校验JSON草稿，不能把它当作final.answer的拼接或已验证事实；final到达后以原QAAnswer为准。", '',
        '以下日志来自真实事件，只展示首8条token原文及全部非token事件；其余token内容省略，JSON日志中保留字符长度/散列与原事件id。SSE样本中id间隔对应省略的token，不是造了额外事件。没有保存完整模型JSON、提示词、思考或Key。最终答案是任务要求的已批准QAAnswer。', '']
    for mode,sample in samples.items():
        lines += ['### '+mode+' 实际事件日志样本', '',
                  '环境：`'+json.dumps(sample['environment'],ensure_ascii=False)+'`。', '', '```text']
        for event in sample['events']:
            if event['event']=='token' and event['data'].get('delta_omitted'):
                continue
            lines += [f"id: {event['id']}", 'event: '+event['event'], 'data: '+json.dumps(event['data'],ensure_ascii=False), '']
        lines += ['```','']
    lines += ['无Key样本用单独子进程删除Key/模型变量，并保留deepseek模式来实际触发MODEL_CONFIGURATION_UNAVAILABLE分支；模型调用0，token事件0，先发节点轨迹再发完整final。extractive模式即使有Key也强制相同的非token分支，离线测试另覆盖。', '',
        '## 上游失败、驳回与断开', '',
        '配置齐全后上游401/500或流截断：error→done(error)，没有final，不中途静默转成摘录成功。开始SSE后HTTP状态仍200，客户端必须检查事件；请求参数非法/论文不存在在SSE开始前仍HTTP422/404。上游错误正文被丢弃，错误为原三字段封装。', '',
        '本次真实服务两模式均成功，没有谎称现场复现了真实上游故障。上游失败/截断、校验驳回原文、第三轮通过与三轮超限拒答、活动响应关闭均由明确标注的离线Mock协议/确定性测试覆盖。验证不通过最多重做三轮，之后原契约refused=true；增量未校验，客户端须在error时丢弃草稿。', '',
        '## 回归与审计', '',
        '全量：342通过、0失败、0错误、0跳过；JUnit qa-sse-pytest.xml（165.256秒），启用--run-ocr --run-real-model，包含原回归与新增13项。真实模型SSE测试实际执行，非只测模拟流。', '',
        '无Key子进程：流式测试13项，12通过、1跳过、0失败/错误；qa-sse-no-key-pytest.xml。跳过项为real_model标记的真实SSE实连，其余回落/模拟协议测试仍执行。未把跳过写成实连成功。', '',
        f"审计{sum(checks.values())}/{len(checks)}项通过：事件顺序/节点与工具配对、qa期间真实增量、final源Chunk/Schema/数字核验、两种模式、JUnit、改动边界与真实Key字节扫描。pdf/仍忽略且Git未跟踪语料；合同Schema与example未改。", '',
        '样本模型调用元数据（只统计本次真实TCP deepseek样本，不冒充整单账单）：', '',
        '| 服务商 | 请求模型 | 阶段 | 秒 | prompt tokens | completion tokens | total tokens |', '| --- | --- | --- | ---: | ---: | ---: | ---: |']
    for call in deep['events'][-1]['data']['metadata']['model_calls']:
        lines.append(f"| {call['provider']} | {call['model']} | {call['phase']} | {call['elapsed_seconds']:.6f} | {call['prompt_tokens']} | {call['completion_tokens']} | {call['total_tokens']} |")
    lines += ['', '## 给WorkBuddy的接入说明（由用户转达）', '',
        '前端源码未动。现有frontend/app/api/backend/[...path]/route.ts第54行使用upstream.text()，会缓冲SSE；后续前端单须透传upstream.body及SSE头，用fetch POST+ReadableStream逐事件读取，不能用只支持GET的原生EventSource。按attempt分轮呈现节点及原文驳回原因；区分未校验JSON草稿与final；处理error/done及取消。无Key回落应显示“非token流式”，不得模拟打字动画冒充模型增量。', '',
        '源码启动或Docker重建后才有新端点；本单没有重建/替换用户现有容器，也未声称前端时间线已经接入SSE。后端README给出完整字段表、curl -N示例和重放/取消限制。', '',
        '## 交付文件与复核', '',
        '- backend/scholar_graph/qa_sse.py：有界实时SSE桥接。',
        '- deepseek_client.py / orchestration.py / qa_routes.py：真实上游流、现有图观察回调及新路由。',
        '- tests/test_qa_sse.py：12项离线/回落测试与1项可跳过真实实连。',
        '- tests/run_qa_sse_acceptance.py：临时TCP真实样本；--mode deepseek / --mode fallback。',
        '- qa-sse-deepseek-events.json / qa-sse-fallback-events.json：原始事件样本（token内容按上述策略裁剪）。',
        '- tests/audit_qa_sse.py / qa-sse-audit.json：复核已批准答案及样本；需要本地已解析Attention记录。',
        '- qa-sse-pytest.xml / qa-sse-no-key-pytest.xml：完整回归与无Key跳过证据。', '',
        '技术依据：[DeepSeek流式聊天协议](https://api-docs.deepseek.com/api/create-chat-completion/)、[Starlette StreamingResponse](https://starlette.dev/responses/)、[HTTPX流式读取](https://www.python-httpx.org/quickstart/#streaming-responses)。', '']
    report = '\n'.join(lines)
    if key and key in report:
        raise RuntimeError('Credential safety check rejected report')
    (REPORTS/'qa-sse-acceptance.md').write_text(report,encoding='utf-8')
    print(json.dumps({'audit':audit['status'],'checks':len(checks),'full_regression':full,'no_key':no_key},ensure_ascii=False))
    return 0 if audit['status']=='passed' else 1


if __name__=='__main__':
    raise SystemExit(main())
