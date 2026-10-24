# 模块二问答与跨篇对比交付报告

日期：2026-10-24（Asia/Shanghai），早于 2026-10-30 时间目标。工作目录 D:\AI_Workspace\Tasks\scholar-graph，分支 main。

开工前 `git pull --ff-only` 原文：`Already up to date.`。主干为 `3038ee9adb3373adf4c3e2f337c5048e77df1d24`，工作区干净。
最终独立实跑源码：`830dbf258c447b844ee377ef1ca4c2483f0561e6`。

**本单 57 项测试全部通过；最终全量回归 140 项中 139 通过、1 失败，不能称全绿。** 失败在未修改的模块一存储层目录重命名，详见下文与原始 JUnit。本单不修改模块一存储实现，需经用户转达威龙另单裁定。

所有输入均为**自制样例、非官方 pdf/ 用例**。没有运行官方三用例，没有使用真实 API Key，没有读取 .env，没有声称问答页面或真实模型已接通。

## 实施范围

新增 POST /api/v1/papers/{paper_id}/qa 与 POST /api/v1/compare。端点总数从 10 增到 12；19 条草案中的图谱、检索、框架、图表、推荐及写作等另外 7 条继续未落地。没有 501 伪端点。

单篇 JSON 为 {question}；question 去两端空白，必须是 1–2000 字符字符串，禁止额外字段。响应为完整冻结 QAAnswer，五个顶层字段原样；错误沿用三字段封装。不存在论文 404 PAPER_NOT_FOUND；无证据或错问为 200、refused=true；非法输入 422 VALIDATION_ERROR。

跨篇 JSON 为 {paper_ids, question}，2–10 个不同论文 id，保留请求顺序；任何论文不存在时整包 404，不发起部分模型请求或伪造部分成功。响应为 {evidence_table, per_paper, synthesis}：per_paper 每项是原样 QAAnswer；证据表行含 evidence_id、per_paper_index、四字段 anchor、quotes。该传输封装由本单明确授权并登记 API 草案，不新增业务记录或冻结 Schema。

## CORS 核实与同源代理

结论：**缺失已补**。基线 backend/scholar_graph/api.py 无 CORSMiddleware，本轮在 create_app 中补齐：

- 来源仅 http://localhost:3000、http://127.0.0.1:3000。
- 允许 GET、POST；OPTIONS 预检由中间件处理。
- 允许 Content-Type 及 CORS 标准安全请求头；暴露 Location、Link。
- allow_credentials=false，不配置任意来源或任意业务方法。
- 未知异常由外层 ServerErrorMiddleware 处理时，为允许的本地来源保留 CORS 头，同时保持 INTERNAL_ERROR 脱敏；未列出的来源不加放行头。

只读核对仓内原 frontend/lib/api.ts 与 frontend/app/api/backend/[...path]/route.ts：现有取数是 GET JSON、POST multipart；本轮增加 POST JSON。因此不需要把 Key 或 Authorization 暴露给浏览器。

tests/verify_proxy_compatibility.cjs 使用现有 Node/TypeScript，在内存编译执行**仓内未修改的原代理函数**，请求发往临时真实 uvicorn 后端：

| 原代理调用 | 上游及代理状态 | 实际核对 |
| --- | ---: | --- |
| GET /api/backend/papers?page_size=1 | 200 | 原查询参数、分页体、诊断头透传 |
| POST /api/backend/papers/{id}/qa，JSON | 200 | QAAnswer 与真实锚点透传 |
| POST /api/backend/papers，multipart 非 PDF | 415 | 原文件字段、Content-Type、UNSUPPORTED_FILE_TYPE 透传 |

代理不转发 Origin，服务端上游请求无 Origin 仍可用。两个开发来源的 OPTIONS 和实际 GET/404、500 错误响应另有测试。原代理源码 SHA-256 为 `e1e1f417a80c539ac4f7c709d1c68eedb6c4a7a6bb39d38d001e06a5bfc34eac`，见 JSON 证据。未安装/构建/修改前端，未验证浏览器问答页面，不把代理函数验证称为页面验收。

## 检索及模型真实方式

**本单检索为词法兜底、向量检索待后续单。** 开工环境没有 chromadb、sentence_transformers，本轮未安装/调用 Chroma，也未下载或运行 BGE-M3，不声称接通向量库或验证硬件不支持它们。

本地 Python 词法排序：有限中英文主题别名、查询关键词覆盖、命中数除以文本词项数平方根，确定性排序。候选最多 8 句；每句是同一 Chunk 的连续原文且不超过 600 字符，过长句跳过；最多返回 4 个不同 Chunk 的证据。只读当前论文已落盘记录，不检索外部来源。

**本轮应用实际没有调用语言模型，模型名为无，真实模型调用数 0。** 默认 SCHOLAR_GRAPH_QA_MODE=extractive，由本地 QuestionAnswerer 确定性摘录原文，不读取 Key、不联网。此模式适合可明确词法匹配的取证问题，不是通用语义推理；会拒答一些有依据但问法不同的正常问题，召回率没有真实论文评测。

可选接口的调用方为后端 httpx → DeepSeek HTTPS /chat/completions，必须显式配置 SCHOLAR_GRAPH_QA_MODE=deepseek、DEEPSEEK_MODEL、DEEPSEEK_API_KEY；base URL 可用 DEEPSEEK_BASE_URL 配置。Key 只从本地环境读取，不作为 HTTP 业务输入，不写入记录、提示词、报告或日志；模式不启用时连 Key 都不读取。仅有模型接口 Mock 测试，测试模型名 mock-evidence-selector 是桩，不是真实模型名，不证明 DeepSeek 已联调。

模型只能选择已校验候选的下标，不能生成答案新事实。无效下标、重复下标、错误类型不返回答案；上游失败返回脱敏 UPSTREAM_ERROR，不回显响应体、请求头、异常或凭据。调用元数据仅在选择器内存保留服务商、模型名、提示词版本、耗时和 usage token 数；本轮无真实模型用量。

协议依据：[DeepSeek Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)、[DeepSeek JSON 输出](https://api-docs.deepseek.com/guides/json_mode/)。文档依据不等于实连证据。

## 锚点、数字、错问与证据先行

每条事实仅为原文摘录，按 answer 中“证据 A/B……”与 anchors 顺序一一对应。返回前必须通过冻结 QAAnswer Schema、检索集合归属、四字段锚点与真实 Chunk 匹配、原文子串及长度校验。伪页码、伪章节、错论文、假 Chunk、新增无锚点事实、extra 字段、passed 无 evidence 均被测试拒绝。

数字 checks 的 passed 限于同一条原文及其上下文逐字可回溯，evidence 非空且包含在顶层 anchors 中；不把数字碰巧出现在别的 Chunk 当依据。数字缺失为 unverifiable；明确同项样本数冲突为 failed；没有数字事实为 not_applicable。汇总按 failed > unverifiable > passed，否则 not_applicable。保留百分比、科学计数及中文数量表达的原文，不做单位换算或跨指标排名，passed 不证明实验真实性或算术正确。

本地问法规则保守拒绝数值前提、why/为什么、因果结论、替代/放弃、否定式前提及指令注入等输入；无依据、中性问句未命中也拒答。不把“没有检索到”变成“论文没报告”。错问纠错仍 refused=true，不向冻结布尔字段塞三态。

沿用单三错问模式的测试包括：缺失 F1、颠倒跨语言结论、把 2020 ACE/12000 样本安到别篇、把未来主动学习说成已经替代原方法、把别篇 MRR 数字当成本篇结果、把跨语言未来工作说成只建议单语；另加单字否定词被分词漏掉的反例。测试结果不代表识别所有语言和所有隐含前提。

跨篇执行顺序：逐篇回答并通过门禁 → 按 Chunk 去重证据表 → 并列原文综合 → 整包再校验。每条综合事实携带 [E编号]，必须回指表内行、对应 per_paper 的 anchor 和原文；每篇仍输出一个 QAAnswer。生成新结论、错引、缺引用、错 quote、重复证据行和跨篇错绑都被拒绝。综合未支持部分明确写“不可验证”，不推断因果或指标优劣。另有测试证明第二篇门禁失败时不会执行综合。

## 本地实测示例

完整请求/响应、四字段锚点、真实输入哈希与运行版本：[module-two-smoke.json](module-two-smoke.json)。输入由 sample_pdfs.py 在 data/module-two-final-release/inputs 下生成，真实走原模块一 MinerU 本地上传。

| 输入 | PaperMeta | Chunk | ReferenceEntry | CitationLink |
| --- | ---: | ---: | ---: | ---: |
| selfmade-v1.pdf | 1 | 6 | 1 | 1 |
| selfmade-v7.pdf | 1 | 8 | 1 | 1 |

问答请求均为 POST /api/v1/papers/{真实 id}/qa、JSON {question}，下表为实际响应摘要：

| question | answer 摘要 | refused | numeric_fact_check.status |
| --- | --- | --- | --- |
| 本文样本量是多少？ | The synthetic study uses 12 samples and cites [1]. | false | passed，附真实 evidence |
| Did the study use 12000 samples? | 拒绝按题设作肯定回答，附上述 12 samples 原文核对 | true | failed，题设与明确样本数冲突 |
| 作者报告的 F1 具体是多少？ | 拒答：未检索到足以回答的原文或所需数值 | true | unverifiable |
| What is the capital of France? | 拒答：本文本无相关证据 | true | not_applicable |

正常回答的真实锚点：

```json
{
  "paper_id": "paper-cb43a78f6a004b6e2d2e44a52823f59c180d97b1ef7c418d6e22d1840d3c3c20",
  "page_number": 1,
  "section": ["1 Introduction"],
  "chunk_id": "paper-cb43a78f6a004b6e2d2e44a52823f59c180d97b1ef7c418d6e22d1840d3c3c20-p0001-c00004"
}
```

对比请求为 POST /api/v1/compare，paper_ids=[上述 v1 id, JSON 中的 v7 id]，question="How many samples?"。实际 200，先返回 E1/E2 两行真实证据，再 per_paper 两个 QAAnswer，最后 synthesis：

```text
原文并列：The synthetic study uses 12 samples and cites [1]. [E1]
原文并列：The synthetic study uses 18 samples and cites [1]. [E2]
不可验证：这些摘录不证明跨篇因果关系，也不支持不同指标之间的优劣排名。
```

## 测试结果及未全绿事项

本单定向测试原文：

```text
57 passed in 8.18s
```

[module-two-targeted-pytest.xml](module-two-targeted-pytest.xml)：57 总数、57 通过、0 失败、0 错误、0 跳过。

| 分类 | 数量 |
| --- | ---: |
| test_qa | 36 |
| test_qa_compare | 16 |
| test_cors | 4 |
| test_proxy_compatibility | 1 |

最终全量回归原文摘要：

```text
FAILED tests/test_api_read.py::test_http_pagination_across_101_contract_examples
1 failed, 139 passed in 98.92s (0:01:38)
```

[module-two-pytest.xml](module-two-pytest.xml)：140 总数、139 通过、1 失败、0 错误、0 跳过。全部本单测试通过，原有解析/OCR等也执行；未声称全量通过。

失败发生在旧 101 条分页测试准备数据阶段，调用未修改的 backend/scholar_graph/storage.py 的 paper()，staging.rename(target) 抛 PermissionError: [WinError 5] 拒绝访问。此前另一轮全量在同一未修改文件的 comparison() 目录重命名也出现 WinError 5，原始证据保存在 [module-two-windows-rename-failure.xml](module-two-windows-rename-failure.xml)（139 总数、138 通过、1 失败）。相关旧四项测试单独复测通过，但不能据此说已修复。原因未确认，不归因于杀毒软件、权限配置或 CORS；没有加隐藏重试、禁用测试或覆盖成绿报告，也没有继续反复重跑全量碰运气。

**转达威龙事项：另单裁定排查模块一原子目录重命名的 Windows WinError 5。** 本单未改 storage.py、未修改全局权限或系统安全配置，完整保留失败证据。这是当前全量回归未全绿的明确限制。

`pip check` 原文 `No broken requirements found.`。环境版本：FastAPI 0.162.0、Starlette 1.9.0、httpx 0.28.1、Pydantic 2.14.1、MinerU 4.0.12。真实模型和向量库无运行版本，因为本轮未运行它们。

## 契约及边界核对

18 份冻结 Schema/example 与开工基线的 Git blob 全部一致，逐项哈希见 JSON；contracts/CONTRACTS.md 也未改。没有修改 frontend/、prompts/、experiments/、test-records/、docker-compose.yml 或其他 docs。前端仅为本单 CORS/代理核实而只读，不修改其源文件、配置、缓存或构建产物。没有定义图谱或综述框架结构。

原有模块一落盘格式、状态机和存储实现未改。问答和比较不落业务输出文件，不覆盖原始 Chunk、裁决或原系统建议。只有测试输入/模型缓存等运行数据在被忽略的 data/ 下。可选 DeepSeek 未真实联调，GROBID 状态仍沿用待验证。

## 复现

在 D:\AI_Workspace\Tasks\scholar-graph 的 PowerShell，使用新的英文输出目录：

```powershell
backend/.venv/Scripts/python.exe -m pytest tests/test_qa.py tests/test_qa_compare.py tests/test_cors.py tests/test_proxy_compatibility.py -q --basetemp data/module-two-targeted-reproduce --junitxml data/module-two-targeted-reproduce.xml
backend/.venv/Scripts/python.exe tests/run_module_two_smoke.py --output-root data/module-two-reproduce --report data/module-two-reproduce.json
```

原代理实际函数测试需要已有 Node 与 frontend/node_modules/typescript；本机二者均有并实际运行，不安装/构建前端。缺依赖的机器该测试会明确跳过，不能沿用本机通过结论。实跑脚本的代理环节则要求该依赖，缺失会失败，不假装通过。全量回归命令及 WinError 5 限制如上，不保证其他机器无该环境现象。

## 提交与文件

| 完整提交哈希 | 对应文件 |
| --- | --- |
| adfe5a2d694294c6ba8d6f1e0f290aef7a2d0721 | backend/README.md；backend/scholar_graph/api.py；tests/test_cors.py |
| 1950307ba8db2f2abf45e036305b5248f618d98e | backend/scholar_graph/api.py；qa.py；qa_evidence.py；qa_model.py；qa_routes.py（后四者同目录）；tests/test_qa.py |
| 4d7e8b737f30c5c16ac7fba00c52fe2452fffec8 | backend/scholar_graph/qa.py；qa_compare.py；qa_routes.py（后两者同目录）；tests/test_qa_compare.py |
| 396e4bdc35462b198cd4176244a59cf84ef8b88e | tests/run_module_one_api_smoke.py；tests/test_api_comparison.py；tests/test_proxy_compatibility.py；tests/verify_proxy_compatibility.cjs |
| 750d38f6fe7b6d9e800f5af5ae0e73bb83b3af29 | backend/README.md；docs/api-draft-v1.md |
| 70ee5b671534a0b0e436a3145953d1c80d8211ed | tests/run_module_two_smoke.py |
| de83ffacd8125419386159485947a4a4e0b90850 | backend/scholar_graph/api.py；tests/test_cors.py |
| 830dbf258c447b844ee377ef1ca4c2483f0561e6 | backend/scholar_graph/qa_evidence.py；tests/test_qa.py |

最后证据提交包含本报告、smoke JSON、本单定向 JUnit、全量 JUnit、较早 WinError 5 JUnit；完整哈希与 git push 原文在推送后最终回报列出，不预写成功结果。
