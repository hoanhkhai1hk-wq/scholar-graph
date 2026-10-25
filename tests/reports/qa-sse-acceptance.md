# 问答SSE流式端点验收

日期：2026-10-25。最终审计：**passed**。

开工main `99842ae6f8404e33701834bb5a247348a8a3e58a`；git pull --ff-only原文`Already up to date.`，工作区干净。本单只修改backend/与tests/，前端、契约、docs/与其他分工区域零改动。

新增`POST /api/v1/papers/{paper_id}/qa/stream`，JSON仍为`{question}`。原19条接口保持，新增后20条；传输事件定义在后端README，未增加业务Schema。SSE final.data就是原QAAnswer，不包一层新答案对象。

## 事件类型表

| event | 内容 |
| --- | --- |
| mode | 模式、是否token增量、回落原因；回落明确写“回落模式、非 token 流式” |
| node_start | node、attempt（从1开始）、elapsed_seconds=0、当前evidence_count |
| node_end | 每轮墙钟耗时、当前证据数、status；validate的validation与validation_error原文；失败节点reason |
| tool_start | 工具名、来源、调用id、轮次；尚未返回证据数0 |
| tool_end | 真实工具结果摘要、来源、返回证据数及耗时；没有原始查询正文 |
| token | qa节点上游content增量；verified=false、channel=model_json_draft，不发思考内容 |
| final | data直接为既有QAAnswer，验证后才发，无新答案记录格式 |
| error | 原三字段错误体error_code/message/details；无上游原始错误正文 |
| done | completed/refused/error与安全元数据；随后结束流 |

标准SSE的id/event/data与空行分帧，UTF-8 JSON单行编码。心跳是10秒静默后的`: keep-alive`注释，不计事件id；Cache-Control=no-cache,no-transform、X-Accel-Buffering=no，无Content-Length。队列32条形成背压，断开停止后续节点/队列等待并关闭已建立的上游流；尚未返回的同步规划请求仍受原60秒超时约束。

事件attempt从1开始；done.metadata.trace保持旧规划计数口径（首plan为0），接入时按SSE节点事件attempt分组。node_end.status=completed只表示执行结束，校验看validation，不能把驳回误读为通过。证据数是当前图状态的检索集合数量，不是最终锚点数。

## 两种模式真实TCP样本

输入为官方Attention v7已落盘的175个Chunk；本单不重新解析PDF。启动当前源码的临时Uvicorn TCP服务，用httpx流式读取真实网络连接，没有用TestClient结果冒充流到达时序。现有Docker旧容器未重建，不宣称旧镜像已具有新端点。

真实模型通过后端httpx调用官方DeepSeek /chat/completions：规划保留Function Calling；qa设置stream=true、include_usage=true，只转发content，thinking disabled，不发reasoning_content。最终仍经过原字面、锚点、数字与Schema门禁。

| 模式 | HTTP | 事件数 | token增量事件数 | 总耗时秒 | final |
| --- | ---: | ---: | ---: | ---: | --- |
| deepseek | 200 | 280 | 265 | 4.439896 | QAAnswer，锚点/数字校验通过 |
| fallback | 200 | 11 | 0 | 0.208275 | QAAnswer，锚点/数字校验通过 |

DeepSeek首增量在3.468373秒到达，qa节点4.427893秒完成，最终QAAnswer在4.438439秒到达。首增量早于完整回答，不是事后拆字。增量事件数265不等于服务商token计量。模型输出协议为证据选择JSON，token.delta是未校验JSON草稿，不能把它当作final.answer的拼接或已验证事实；final到达后以原QAAnswer为准。

以下日志来自真实事件，只展示首8条token原文及全部非token事件；其余token内容省略，JSON日志中保留字符长度/散列与原事件id。SSE样本中id间隔对应省略的token，不是造了额外事件。没有保存完整模型JSON、提示词、思考或Key。最终答案是任务要求的已批准QAAnswer。

### deepseek 实际事件日志样本

环境：`{"SCHOLAR_GRAPH_QA_MODE": "已设置", "DEEPSEEK_MODEL": "已设置", "DEEPSEEK_API_KEY": "已设置"}`。

```text
id: 1
event: mode
data: {"mode": "deepseek", "token_streaming": true, "fallback_reason": null, "message": "真实上游token增量；增量为未校验JSON草稿，以final的QAAnswer为准。"}

id: 2
event: node_start
data: {"node": "plan", "attempt": 1, "evidence_count": 0, "elapsed_seconds": 0.0}

id: 3
event: node_end
data: {"node": "plan", "elapsed_seconds": 1.597727, "attempt": 1, "evidence_count": 0, "validation": null, "validation_error": null, "fallback_reason": null, "status": "completed"}

id: 4
event: node_start
data: {"node": "retrieve", "attempt": 1, "evidence_count": 0, "elapsed_seconds": 0.0}

id: 5
event: tool_start
data: {"tool_name": "search", "origin": "model_function_call", "tool_call_id": "call_00_wPYftC7vTCwOByoGmJef9794", "attempt": 1, "evidence_count": 0}

id: 6
event: tool_end
data: {"tool_name": "search", "tool_call_id": "call_00_wPYftC7vTCwOByoGmJef9794", "attempt": 1, "origin": "model_function_call", "arguments_summary": {"paper_ids": ["paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697"], "query_chars": 46, "limit": 12}, "return_summary": {"evidence_count": 12, "method": "lexical"}, "elapsed_seconds": 0.169973, "status": "succeeded", "evidence_count": 12}

id: 7
event: tool_start
data: {"tool_name": "search", "origin": "model_function_call", "tool_call_id": "call_01_gsQ4Gn9PAOjIhf2mTMId6205", "attempt": 1, "evidence_count": 0}

id: 8
event: tool_end
data: {"tool_name": "search", "tool_call_id": "call_01_gsQ4Gn9PAOjIhf2mTMId6205", "attempt": 1, "origin": "model_function_call", "arguments_summary": {"paper_ids": ["paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697"], "query_chars": 57, "limit": 12}, "return_summary": {"evidence_count": 9, "method": "lexical"}, "elapsed_seconds": 0.199521, "status": "succeeded", "evidence_count": 9}

id: 9
event: node_end
data: {"node": "retrieve", "elapsed_seconds": 0.374624, "attempt": 1, "evidence_count": 17, "validation": null, "validation_error": null, "fallback_reason": null, "status": "completed"}

id: 10
event: node_start
data: {"node": "qa", "attempt": 1, "evidence_count": 17, "elapsed_seconds": 0.0}

id: 11
event: token
data: {"node": "qa", "attempt": 1, "delta": "{", "verified": false, "channel": "model_json_draft"}

id: 12
event: token
data: {"node": "qa", "attempt": 1, "delta": "\"", "verified": false, "channel": "model_json_draft"}

id: 13
event: token
data: {"node": "qa", "attempt": 1, "delta": "answers", "verified": false, "channel": "model_json_draft"}

id: 14
event: token
data: {"node": "qa", "attempt": 1, "delta": "\":[", "verified": false, "channel": "model_json_draft"}

id: 15
event: token
data: {"node": "qa", "attempt": 1, "delta": "{\"", "verified": false, "channel": "model_json_draft"}

id: 16
event: token
data: {"node": "qa", "attempt": 1, "delta": "paper", "verified": false, "channel": "model_json_draft"}

id: 17
event: token
data: {"node": "qa", "attempt": 1, "delta": "_id", "verified": false, "channel": "model_json_draft"}

id: 18
event: token
data: {"node": "qa", "attempt": 1, "delta": "\":\"", "verified": false, "channel": "model_json_draft"}

id: 276
event: node_end
data: {"node": "qa", "elapsed_seconds": 2.288691, "attempt": 1, "evidence_count": 17, "validation": null, "validation_error": null, "fallback_reason": null, "status": "completed"}

id: 277
event: node_start
data: {"node": "validate", "attempt": 1, "evidence_count": 17, "elapsed_seconds": 0.0}

id: 278
event: node_end
data: {"node": "validate", "elapsed_seconds": 0.007016, "attempt": 1, "evidence_count": 17, "validation": true, "validation_error": null, "fallback_reason": null, "status": "completed"}

id: 279
event: final
data: {"schema_version": "1.0.0", "answer": "【证据 A】\nWe used the Adam optimizer [20] with β 1  = 0.9, β 2  = 0.98 and ϵ = 10 −9 . We varied the learning rate over the course of training, according to the formula:\n\n【证据 B】\nThis corresponds to increasing the learning rate linearly for the first warmup_steps training steps, and decreasing it thereafter proportionally to the inverse square root of the step number. We used warmup_steps = 4000.", "anchors": [{"paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697", "page_number": 7, "section": ["5 Training", "5.3 Optimizer"], "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0007-c00088"}, {"paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697", "page_number": 7, "section": ["5 Training", "5.3 Optimizer"], "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0007-c00089"}], "numeric_fact_check": {"status": "passed", "checks": [{"claim": "We used the Adam optimizer [20] with β 1  = 0.9, β 2  = 0.98 and ϵ = 10 −9 . We varied the learning rate over the course of training, according to the formula:", "status": "passed", "evidence": [{"paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697", "page_number": 7, "section": ["5 Training", "5.3 Optimizer"], "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0007-c00088"}], "reason": "数字与上下文逐字回溯同一真实Chunk；不证明实验结论本身。"}, {"claim": "This corresponds to increasing the learning rate linearly for the first warmup_steps training steps, and decreasing it thereafter proportionally to the inverse square root of the step number. We used warmup_steps = 4000.", "status": "passed", "evidence": [{"paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697", "page_number": 7, "section": ["5 Training", "5.3 Optimizer"], "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0007-c00089"}], "reason": "数字与上下文逐字回溯同一真实Chunk；不证明实验结论本身。"}]}, "refused": false}

id: 280
event: done
data: {"status": "completed", "metadata": {"engine": "langgraph", "attempts": 1, "max_attempts": 3, "fallback_reason": null, "trace": [{"node": "plan", "elapsed_seconds": 1.597727, "attempt": 0, "evidence_count": 0, "validation": null, "validation_error": null, "fallback_reason": null}, {"node": "retrieve", "elapsed_seconds": 0.374624, "attempt": 1, "evidence_count": 17, "validation": null, "validation_error": null, "fallback_reason": null}, {"node": "qa", "elapsed_seconds": 2.288691, "attempt": 1, "evidence_count": 17, "validation": null, "validation_error": null, "fallback_reason": null}, {"node": "validate", "elapsed_seconds": 0.007016, "attempt": 1, "evidence_count": 17, "validation": true, "validation_error": null, "fallback_reason": null}], "tool_calls": [{"tool_name": "search", "tool_call_id": "call_00_wPYftC7vTCwOByoGmJef9794", "attempt": 1, "origin": "model_function_call", "arguments_summary": {"paper_ids": ["paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697"], "query_chars": 46, "limit": 12}, "return_summary": {"evidence_count": 12, "method": "lexical"}, "elapsed_seconds": 0.169973, "status": "succeeded"}, {"tool_name": "search", "tool_call_id": "call_01_gsQ4Gn9PAOjIhf2mTMId6205", "attempt": 1, "origin": "model_function_call", "arguments_summary": {"paper_ids": ["paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697"], "query_chars": 57, "limit": 12}, "return_summary": {"evidence_count": 9, "method": "lexical"}, "elapsed_seconds": 0.199521, "status": "succeeded"}], "model_calls": [{"provider": "deepseek", "model": "deepseek-chat", "phase": "plan", "elapsed_seconds": 1.597382, "prompt_tokens": 798, "completion_tokens": 213, "total_tokens": 1011, "http_status": 200, "status": "succeeded"}, {"provider": "deepseek", "model": "deepseek-chat", "phase": "qa", "elapsed_seconds": 2.286765, "prompt_tokens": 11544, "completion_tokens": 264, "total_tokens": 11808, "http_status": 200, "status": "succeeded"}], "checkpointing": false, "external_tracing": false, "validated": true}, "token_streaming": true, "fallback_reason": null}

```

### fallback 实际事件日志样本

环境：`{"SCHOLAR_GRAPH_QA_MODE": "已设置", "DEEPSEEK_MODEL": "未设置", "DEEPSEEK_API_KEY": "未设置"}`。

```text
id: 1
event: mode
data: {"mode": "extractive", "token_streaming": false, "fallback_reason": "MODEL_CONFIGURATION_UNAVAILABLE", "message": "回落模式、非 token 流式"}

id: 2
event: node_start
data: {"node": "plan", "attempt": 1, "evidence_count": 0, "elapsed_seconds": 0.0}

id: 3
event: node_end
data: {"node": "plan", "elapsed_seconds": 0.000431, "attempt": 1, "evidence_count": 0, "validation": null, "validation_error": null, "fallback_reason": "MODEL_CONFIGURATION_UNAVAILABLE", "status": "completed"}

id: 4
event: node_start
data: {"node": "retrieve", "attempt": 1, "evidence_count": 0, "elapsed_seconds": 0.0}

id: 5
event: node_end
data: {"node": "retrieve", "elapsed_seconds": 0.006725, "attempt": 1, "evidence_count": 2, "validation": null, "validation_error": null, "fallback_reason": "MODEL_CONFIGURATION_UNAVAILABLE", "status": "completed"}

id: 6
event: node_start
data: {"node": "qa", "attempt": 1, "evidence_count": 2, "elapsed_seconds": 0.0}

id: 7
event: node_end
data: {"node": "qa", "elapsed_seconds": 0.03143, "attempt": 1, "evidence_count": 2, "validation": null, "validation_error": null, "fallback_reason": "MODEL_CONFIGURATION_UNAVAILABLE", "status": "completed"}

id: 8
event: node_start
data: {"node": "validate", "attempt": 1, "evidence_count": 2, "elapsed_seconds": 0.0}

id: 9
event: node_end
data: {"node": "validate", "elapsed_seconds": 0.001757, "attempt": 1, "evidence_count": 2, "validation": true, "validation_error": null, "fallback_reason": "MODEL_CONFIGURATION_UNAVAILABLE", "status": "completed"}

id: 10
event: final
data: {"schema_version": "1.0.0", "answer": "【证据 A】\n5.3 Optimizer\n\n【证据 B】\nWe used the Adam optimizer [20] with β 1  = 0.9, β 2  = 0.98 and ϵ = 10 −9 .", "anchors": [{"paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697", "page_number": 7, "section": ["5 Training", "5.3 Optimizer"], "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0007-c00087"}, {"paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697", "page_number": 7, "section": ["5 Training", "5.3 Optimizer"], "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0007-c00088"}], "numeric_fact_check": {"status": "passed", "checks": [{"claim": "5.3 Optimizer", "status": "passed", "evidence": [{"paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697", "page_number": 7, "section": ["5 Training", "5.3 Optimizer"], "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0007-c00087"}], "reason": "数字及其上下文逐字来自该 Chunk；仅核验原文回溯，不证明实验真实性或跨指标可比性。"}, {"claim": "We used the Adam optimizer [20] with β 1  = 0.9, β 2  = 0.98 and ϵ = 10 −9 .", "status": "passed", "evidence": [{"paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697", "page_number": 7, "section": ["5 Training", "5.3 Optimizer"], "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0007-c00088"}], "reason": "数字及其上下文逐字来自该 Chunk；仅核验原文回溯，不证明实验真实性或跨指标可比性。"}]}, "refused": false}

id: 11
event: done
data: {"status": "completed", "metadata": {"engine": "langgraph", "attempts": 1, "max_attempts": 3, "fallback_reason": "MODEL_CONFIGURATION_UNAVAILABLE", "trace": [{"node": "plan", "elapsed_seconds": 0.000431, "attempt": 0, "evidence_count": 0, "validation": null, "validation_error": null, "fallback_reason": "MODEL_CONFIGURATION_UNAVAILABLE"}, {"node": "retrieve", "elapsed_seconds": 0.006725, "attempt": 1, "evidence_count": 2, "validation": null, "validation_error": null, "fallback_reason": "MODEL_CONFIGURATION_UNAVAILABLE"}, {"node": "qa", "elapsed_seconds": 0.03143, "attempt": 1, "evidence_count": 2, "validation": null, "validation_error": null, "fallback_reason": "MODEL_CONFIGURATION_UNAVAILABLE"}, {"node": "validate", "elapsed_seconds": 0.001757, "attempt": 1, "evidence_count": 2, "validation": true, "validation_error": null, "fallback_reason": "MODEL_CONFIGURATION_UNAVAILABLE"}], "tool_calls": [], "model_calls": [], "checkpointing": false, "external_tracing": false, "validated": true}, "token_streaming": false, "fallback_reason": "MODEL_CONFIGURATION_UNAVAILABLE"}

```

无Key样本用单独子进程删除Key/模型变量，并保留deepseek模式来实际触发MODEL_CONFIGURATION_UNAVAILABLE分支；模型调用0，token事件0，先发节点轨迹再发完整final。extractive模式即使有Key也强制相同的非token分支，离线测试另覆盖。

## 上游失败、驳回与断开

配置齐全后上游401/500或流截断：error→done(error)，没有final，不中途静默转成摘录成功。开始SSE后HTTP状态仍200，客户端必须检查事件；请求参数非法/论文不存在在SSE开始前仍HTTP422/404。上游错误正文被丢弃，错误为原三字段封装。

本次真实服务两模式均成功，没有谎称现场复现了真实上游故障。上游失败/截断、校验驳回原文、第三轮通过与三轮超限拒答、活动响应关闭均由明确标注的离线Mock协议/确定性测试覆盖。验证不通过最多重做三轮，之后原契约refused=true；增量未校验，客户端须在error时丢弃草稿。

## 回归与审计

全量：342通过、0失败、0错误、0跳过；JUnit qa-sse-pytest.xml（165.256秒），启用--run-ocr --run-real-model，包含原回归与新增13项。真实模型SSE测试实际执行，非只测模拟流。

无Key子进程：流式测试13项，12通过、1跳过、0失败/错误；qa-sse-no-key-pytest.xml。跳过项为real_model标记的真实SSE实连，其余回落/模拟协议测试仍执行。未把跳过写成实连成功。

审计28/28项通过：事件顺序/节点与工具配对、qa期间真实增量、final源Chunk/Schema/数字核验、两种模式、JUnit、改动边界与真实Key字节扫描。pdf/仍忽略且Git未跟踪语料；合同Schema与example未改。

样本模型调用元数据（只统计本次真实TCP deepseek样本，不冒充整单账单）：

| 服务商 | 请求模型 | 阶段 | 秒 | prompt tokens | completion tokens | total tokens |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| deepseek | deepseek-chat | plan | 1.597382 | 798 | 213 | 1011 |
| deepseek | deepseek-chat | qa | 2.286765 | 11544 | 264 | 11808 |

## 给WorkBuddy的接入说明（由用户转达）

前端源码未动。现有frontend/app/api/backend/[...path]/route.ts第54行使用upstream.text()，会缓冲SSE；后续前端单须透传upstream.body及SSE头，用fetch POST+ReadableStream逐事件读取，不能用只支持GET的原生EventSource。按attempt分轮呈现节点及原文驳回原因；区分未校验JSON草稿与final；处理error/done及取消。无Key回落应显示“非token流式”，不得模拟打字动画冒充模型增量。

源码启动或Docker重建后才有新端点；本单没有重建/替换用户现有容器，也未声称前端时间线已经接入SSE。后端README给出完整字段表、curl -N示例和重放/取消限制。

## 交付文件与复核

- backend/scholar_graph/qa_sse.py：有界实时SSE桥接。
- deepseek_client.py / orchestration.py / qa_routes.py：真实上游流、现有图观察回调及新路由。
- tests/test_qa_sse.py：12项离线/回落测试与1项可跳过真实实连。
- tests/run_qa_sse_acceptance.py：临时TCP真实样本；--mode deepseek / --mode fallback。
- qa-sse-deepseek-events.json / qa-sse-fallback-events.json：原始事件样本（token内容按上述策略裁剪）。
- tests/audit_qa_sse.py / qa-sse-audit.json：复核已批准答案及样本；需要本地已解析Attention记录。
- qa-sse-pytest.xml / qa-sse-no-key-pytest.xml：完整回归与无Key跳过证据。

技术依据：[DeepSeek流式聊天协议](https://api-docs.deepseek.com/api/create-chat-completion/)、[Starlette StreamingResponse](https://starlette.dev/responses/)、[HTTPX流式读取](https://www.python-httpx.org/quickstart/#streaming-responses)。
