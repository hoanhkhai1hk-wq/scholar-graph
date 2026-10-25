# ScholarGraph 模块一、二、四、五、六后端

本后端实现本地 PDF 解析、状态机、去重与版本差异，模块二问答/对比、模块四检索/公开抓取/推荐，模块五局域引用图谱，以及模块六综述框架、摘录草稿与CSV图表，原19条 HTTP 端点保持，另增问答SSE与模块三英→中翻译端点，共21条。Python 包为 `scholar_graph`。自由成文、文档导出、异步队列仍未实现。

## Windows 本地安装

在 `D:\AI_Workspace\Tasks\scholar-graph` 的 PowerShell 中执行。需要 Python 3.12；全部运行数据写入本目录下被 Git 忽略的 data/。

```powershell
py -V:Astral/CPython3.12.15 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -e 'backend[ocr,test]'
```

本机 Python 启动器的 3.12 标签为 Astral/CPython3.12.15，上面的命令已按该标签配置；其他机器先用 `py -0p` 查已有 Python 3.12 标签。已有 backend/.venv 时跳过创建步骤。仅解析文本 PDF 时可安装 `backend[test]`，扫描件需要额外的 ocr 依赖及首次模型下载。实际锁定的引擎为 MinerU 4.0.12、PaddleOCR 3.7.0、PaddlePaddle 3.3.1；使用 CPU OCR，不要求 CUDA 或 Docker。backend/pyproject.toml 固定直接依赖，完整本轮环境版本见 tests/reports/module-one-environment.json。不要把虚拟环境、模型、PDF、data/ 或 .env 提交到 Git。

## 启动 HTTP API

本地开发 CORS 核实（模块二开工）：原后端缺少 CORSMiddleware，已在 scholar_graph/api.py 的 create_app 中补齐。仅允许 http://localhost:3000 与 http://127.0.0.1:3000；方法 GET/POST（中间件处理 OPTIONS 预检），允许 Content-Type 及 CORS 标准安全请求头，暴露 Location/Link，并在模块四增加 X-ScholarGraph-Search-Mode / Vector-Status / Search-Reason / Recommendation-Reason 四个响应头（均为完整 X-ScholarGraph- 前缀），不启用跨源凭据。前端同源代理仍按原格式透传到 /api/v1，不需要 Origin 的服务端请求不受 CORS 限制；本轮不修改前端。

```powershell
backend/.venv/Scripts/python.exe -m uvicorn scholar_graph.api:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

安装命令同上，新增直接依赖 FastAPI、python-multipart 和 uvicorn。默认数据目录沿用 `data/module-one`，可用 `SCHOLAR_GRAPH_DATA_DIR` 指定另一个本地目录；不需要 API Key。使用单 worker，上传写操作在进程内串行化，批量请求按文件顺序同步等待完成，不是异步任务队列。状态查询可以在另一个请求中读取已落盘快照。

OpenAPI 为 `http://127.0.0.1:8000/openapi.json`，Swagger 为 `/docs`。上传单文件字段为 file，批量为重复 files 字段；文献详情中的 Link 头给出 chunks、references、citation-links 的真实取数路径。详情/状态/去重/差异返回裸记录；列表统一分页，page_size 超过 100 按 100 计。去重、差异的路径参数为 **new_paper_id**，没有记录时 404，不返回空记录。

完整请求、响应及 19 条草案端点的实施清单见 [API 草案](../docs/api-draft-v1.md)；HTTP 实测及可复现命令见 [本轮报告](../tests/reports/module-one-api-report.md)。新增响应只是本轮获批的传输封装，九份业务 Schema 未改。HTTP 默认工厂不启用 GROBID，GROBID 真实联调仍为待验证。没有验证前端接通。

## 模块二：单篇问答与跨篇对比

POST /api/v1/papers/{paper_id}/qa 的 JSON 为 `{ "question": "本文样本量是多少？" }`，返回完整 QAAnswer。POST /api/v1/compare 的 JSON 为 `{ "paper_ids": ["paper-a", "paper-b"], "question": "样本量分别是多少？" }`，返回 evidence_table、逐篇 QAAnswer 数组 per_paper、综合文本 synthesis。用真实已入库 paper id 替换示例 id。比较不是版本差异，也不更改去重记录。

模块二默认摘录模式的检索为词法兜底；模块四已有独立 BGE-M3/Chroma 检索端点，但本轮问答与 Agent 的 search 工具仍采用词法排序，不冒充向量问答。默认摘录模式用有限中英文别名、关键词覆盖及长度归一得分选原文，候选最多 8 句，最多输出 4 个不同 Chunk 的证据。超过 600 字符的单句跳过；不做跨块拼句、语义改写或任意问法推理。关键词覆盖和保守问法规则会漏答正常问题，这不是通用模型问答质量验收。

默认 SCHOLAR_GRAPH_QA_MODE=extractive：本地确定性原文摘录，**没有真实模型调用或模型名**，不需要 Key，也不读取 .env。事实按“证据 A/B……”与 anchors 顺序对应；锚点四字段、原文子串、数字和 QAAnswer Schema 都通过后才返回。数字 passed 是原文回溯通过；不可回溯为 unverifiable，明确样本数矛盾为 failed。故意错前提、超纲、无依据都 refused=true，必要时附原文纠错，不凭检索未命中说全文没报告。

当前 deepseek 模式由 scholar_graph/deepseek_client.py 与 grounded_model.py 调用真实 DeepSeek /chat/completions，让模型从实际 Chunk 中选择连续原文；旧 qa_model.py 选择器保留兼容。请求模型名来自 DEEPSEEK_MODEL，仅允许官方 HTTPS api.deepseek.com，DEEPSEEK_API_KEY 只从已注入进程环境读取，不加载 .env、不将 Key 写入任何文件。本轮已完成真实联调，详见文末新验收节。默认 extractive 不因 Key 存在而联网；默认 deepseek 上游异常明确返回502 UPSTREAM_ERROR，不伪造答案。

对比先校验各篇 QAAnswer，再建一行一个 Chunk 的证据表，最后综合。每条综合事实为原文并列，并带 E 行引用，行内锚点必须回指 per_paper；不作跨指标大小排名或因果判断。不支持的综合论断标“不可验证”。完整传输形状、请求边界和限制见 API 草案，不改冻结 Schema。

同源代理兼容性测试实际在内存编译执行仓内原 route.ts，转发 GET 列表、POST 问答 JSON 和 POST multipart 到临时真实 uvicorn 后端；分别验证 200、200、415 及原错误码。既没有修改/构建前端，也没有声称浏览器页面已接问答。开发 CORS 预检另有 TestClient 验证。

模块二独立实跑及测试证据见 [module-two-report.md](../tests/reports/module-two-report.md)。所有输入为自制样例、非官方 pdf/ 用例，不使用真实 Key。运行：

```powershell
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --basetemp data/module-two-tests
backend/.venv/Scripts/python.exe tests/run_module_two_smoke.py --output-root data/module-two-reproduce --report data/module-two-reproduce.json
```

## 模块五：局域引用图谱

GET `/api/v1/graph?paper_ids=paper-a&paper_ids=paper-b` 用 1–100 个不同已入库 id 生成视图；先按真实 CitationLink/ReferenceEntry/Chunk 关联，再运行显式 PageRank，返回 nodes、edges、layers、future_work 和 diagnostics。GraphNode/GraphEdge 使用 v1.2，原九份记录和示例不变。没有锚点的边为 unverified，不参与排名或未来方向排除；身份无法唯一匹配不猜边。接口形状与全部规则见 API 草案。

PageRank 阻尼 0.85、悬挂质量均匀回流、L1 容差1e-12；基石是有入边且高于所选图 1/N 均匀基线的节点，孤立节点保留。分层不是论文质量评价。未来方向仅按明确标记行摘录；主题完全一致、严格更晚、解决声明所在 Chunk 有真实引用时才排除，并保留两侧 QAAnswer 证据与核验原因。未满足条件只表示所选语料尚未证明已解决；不推断全球科研状态。模块五自身不调用向量检索或真实大模型，也未对接前端图谱页面。

本轮先处理上一单 WinError 5：修复前10轮未能自然复现，未定位历史占用者；受控真实共享锁出现 WinError 32，释放句柄后退避成功。原子发布/清理只对 Windows 5/32/33 有限重试，永久错误仍抛出；保留校验后原子发布，不复制半成品、不改权限。诊断与第0项148项全量通过证据见 [存储报告](../tests/reports/graph-storage-report.md)，本轮最终图谱实跑和完整回归见 [模块五报告](../tests/reports/module-five-report.md)。

```powershell
backend/.venv/Scripts/python.exe tests/run_module_five_smoke.py --output-root data/module-five-reproduce --report data/module-five-reproduce.json
```

该脚本以自制落盘契约记录构造引用链及孤立节点，不是官方 pdf/ 用例，也不伪称真实论文解析质量评测。运行数据仍位于被忽略的 data/，不需要任何 Key。

## 模块四：检索、公开抓取与推荐

POST /api/v1/retrieval/search 接收 `{question,paper_ids?,page?,page_size?,min_relevance?}`，返回固定六字段分页壳，每项含原样 Chunk、真实四字段 anchor、relevance 和 retrieval_method。默认词法 IDF 加权余弦；模式/向量状态/空结果原因在 X-ScholarGraph-* 响应头。页大小超过100按100计，越界页保持 total 且空 items。模块二 QA 仍是原词法取证，本次没有替换 QA 的检索器或联调真实生成模型。

**向量已实装并本地跑通。** Chroma 1.5.9、FlagEmbedding 1.4.2、torch 2.14.1+cpu、transformers 5.20.2；模型 BAAI/bge-m3 快照5617a9f61b028005a4858fdac845db406aefb181。实际验证4个自制 Chunk 的1024维 dense和模型 sparse权重，持久索引后子集检索复用已有向量。稠密余弦与稀疏权重点积各排序，再按等权RRF（k=60）融合，具体公式见 API 草案。CPU float32、batch1、2线程、512token截断；每次请求独立worker加载模型，实测约15–20秒，不作吞吐量或真实语料精度承诺。索引增量按原文/元数据/模型快照指纹更新，输出仅来自本次指定的真实 Chunk 集合。

安装到 D盘被忽略的隔离环境，不影响解析/OCR依赖；约2.2GB模型下载不需要Key。先安装backend，再执行：

```powershell
backend/.venv/Scripts/python.exe -m venv data/module-four-runtime/.venv
data/module-four-runtime/.venv/Scripts/python.exe -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.1+cpu
data/module-four-runtime/.venv/Scripts/python.exe -m pip install -r backend/requirements-retrieval.txt
data/module-four-runtime/.venv/Scripts/python.exe backend/download_bge_m3.py
$env:SCHOLAR_GRAPH_RETRIEVAL_MODE='bge_m3_hybrid'
$env:SCHOLAR_GRAPH_VECTOR_PYTHON='D:\AI_Workspace\Tasks\scholar-graph\data\module-four-runtime\.venv\Scripts\python.exe'
$env:SCHOLAR_GRAPH_BGE_M3_PATH='D:\AI_Workspace\Tasks\scholar-graph\data\module-four-models\bge-m3'
backend/.venv/Scripts/python.exe -m uvicorn scholar_graph.api:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

运行期模型完全离线，不隐式下载或使用远程Embedding接口；worker不继承API_KEY/TOKEN/SECRET/PASSWORD类环境变量。未启用为lexical/NOT_ENABLED；模型缺失、依赖错误、worker失败或240秒超时为lexical/UNAVAILABLE，不伪报向量成功。Chroma持久数据位于当前 SCHOLAR_GRAPH_DATA_DIR/chroma-bge-m3；启动使用单worker，单实例向量操作串行，上传和抓取复用同一写锁。本实现面向本机开发，不声称分布式索引或异步队列。

POST /api/v1/retrieval/fetch 接收 `{title}` 或 `{reference:完整ReferenceEntry}`。通过公开 arXiv API 唯一匹配标题/标识/裸DOI，先保存真实元数据，再下载PDF并复用模块一Pipeline、ParseJob和所有校验/发布/去重逻辑。固定HTTP200操作封装 `{succeeded,metadata,paper,initial_parse_status,parse_status,error}`；失败保留真实原因，下载前未拿到PDF不伪建queued。metadata的arxiv-id与paper的PDF哈希id明确分开，catalog里的未解析元数据不混入/papers。请求非法仍为422三字段统一错误。无真实Key、无另起解析管线，GROBID仍待验证。

真实公开探针已获取1706.03762v7《Attention Is All You Need》，复用MinerU解析15页，得到1 PaperMeta /175 Chunk /40 ReferenceEntry /69 CitationLink。它是一次公开论文连通性验证，不能替代真实论文解析质量评测或官方比赛用例。自制Atom+PDF测试另得到1/6/1/1。

GET /api/v1/recommendations?paper_id=种子id&as_of_year=2026 使用本地已解析集合，返回分页PaperMeta+理由，不新定义业务记录。评分原文：

```text
score = 100 * (0.40*G + 0.35*P + 0.15*T + 0.10*C); missing terms contribute 0, without reweighting
```

G=与种子任一方向有模块五verified边；P=模块五PR/本地图最大PR；T=max(0,1-(as_of_year-year)/10)；C=真实PaperMeta.abstract/source带精确GitHub仓库链接。缺年份、未来年份或未发现链接标missing_signals并贡献0，不重分权重。无GitHub信号不写有代码；有链接只说明元数据含仓库链接，未核许可证，不断言开源。PR不是全网引文数，公式没有虚构引用数；理由给原边/锚点、节点与PR来源、年份或原始链接。默认as_of_year为当前UTC年并回显。完整权重/来源和传输字段见 [API草案](../docs/api-draft-v1.md)。

复现本轮HTTP验收（选择尚不存在的output-root）：

```powershell
backend/.venv/Scripts/python.exe tests/run_module_four_smoke.py --output-root data/module-four-reproduce --report data/module-four-reproduce.json --vector-python data/module-four-runtime/.venv/Scripts/python.exe --model-path data/module-four-models/bge-m3 --live-arxiv
```

默认测试无网络、无Docker、无真实Key。该脚本显式参数才运行本地真实BGE/Chroma与公开arXiv探针，结果保留 native_evidence 和失败原因；实际交付证据见 [模块四报告](../tests/reports/module-four-report.md)。输入是自制样例、非官方 pdf/ 用例；未运行官方三用例，未验收前端接入。

## 模块六：框架、摘录草稿与CSV图表

新增FrameworkOutline v1.2，原十一份Schema/example零改动。POST /api/v1/frameworks 接收 `{paper_ids}`，返回图谱分层和已过滤未来方向组成的有证据大纲。基石分别成章，衍生沿verified边归入最近基石，距离相同时复用模块四所选集合内的推荐分数；孤立/无基石可达的论文单独归位。每章带真实论文id、四字段Chunk锚点及最多600字符的原文待写材料；无未来方向证据不造章。

POST /api/v1/reviews 接收 `{paper_ids,framework,requirements?}`，framework须为当前集合生成且未被无依据篡改的FrameworkOutline；返回章节标题、逐字摘录、锚点与数字核验。额外requirements在本章已有摘录中词法取证，无结果用unverifiable+空anchors明确占位，不补写结论。只说明有限材料未找到，不能断言全文缺失。没有真实模型调用或Key，mode=extractive，不把摘录式草稿称为大模型生成，成文由用户完成。

POST /api/v1/charts/csv 接收multipart file、value_columns（JSON列名数组字符串）、chart_type（默认bar）、可选x_column和caption，直接返回原样七字段ChartOutput。支持line/bar/scatter/histogram；返回实际Matplotlib 3.11.2/Agg PNG的数据URI，不给不存在图片路径，也不新增下载端点。逐所选源单元格生成numeric_checks，行号按逻辑CSV记录计（表头=1）。图注默认 `CSV values: 12, 18.`，自定义也仅接受同样数值枚举格式；每个数字必须能回溯到原CSV，拒绝自由叙述及百分比等单位换算以免漏验。

CSV须UTF-8/BOM、≤1MiB、1–1000行数据、1–20列、唯一非空表头、整齐记录；所选列为有限且可无损float表示的纯数字。line/bar可选1–10数值列；scatter须一个独立数值x列+一个y列，histogram只一列；不支持分类x轴。CSV非法422 CSV_INVALID，配置/图注/Schema/PNG失败422 CHART_VALIDATION_FAILED，均是既有v1.1三字段错误；不把图表塞QAAnswer。

自制四篇样例：框架4章、5处锚点引用（4个唯一锚点），未来章只保留2条过滤后方向；草稿默认6条摘录、0处unverifiable，额外无证据要求产生4处占位。两行CSV samples=12/18分别回溯到第2/3行，PNG已实际生成和检查。测试为自制样例、非官方pdf/用例，不声称官方三用例通过或前端接通。完整字段/限制见[API草案](../docs/api-draft-v1.md)，原始证据与回归见[模块六报告](../tests/reports/module-six-report.md)。

```powershell
backend/.venv/Scripts/python.exe tests/run_module_six_smoke.py --output-root data/module-six-reproduce --report data/module-six-reproduce.json
```

选择尚不存在的输出目录；全部输入/PNG留在被忽略的data/，脚本无网络、无Docker、无模型和Key依赖。Matplotlib已列入backend/pyproject.toml直接依赖，安装backend后无需另启服务。CORS与同源代理沿用已有配置，前端零改动。

## 第一步：解析一个 PDF

```powershell
backend/.venv/Scripts/python.exe -m scholar_graph parse data/input/paper-v1.pdf
```

文本页调用 MinerU 本地 SDK 的 `tier=flash, ocr_mode=txt`；没有模型推理的文本层模式也确实经过 MinerU。扫描页单独送 PaddleOCR，混合 PDF 保留各自的物理页索引；纯空白页不送 OCR、不创建伪正文。英文 OCR 为默认值，可加 `--ocr-language ch` 切换，中文样例本单未验证。

每个原始 PDF 按 SHA-256 得到稳定 paper id。成功后在 `data/module-one/papers/<paper-id>/` 得到：

- paper-meta.json：一个 PaperMeta；未知信息保留 null 或空列表，不推测机构、摘要或年份。
- chunks.json：Chunk 数组；坐标是可见整页的 0–1 归一化坐标，物理页码从 1 开始。
- reference-entries.json：ReferenceEntry 数组；未知参考文献信息保留 null，不编造条目。
- citation-links.json：CitationLink 数组；只链接已确认编号的文末条目，未知引用不生成链接。

命令 stdout 返回 PaperMeta；失败返回固定三字段统一错误对象并使用非零退出码。上传第二版时，如本地已有记录的裸 DOI、arXiv 基号或标题加作者完全一致，自动生成 DedupDecision 和 DiffSummary 到 comparisons/，无需另运行比较命令。显式冲突的 DOI 不会因为标题相同而自动配对；多个匹配版本按本地入库顺序选择最后一个，不作为发表日期或质量排序。中间状态在 `data/module-one/jobs/<job-id>/parse-status.json`，是已校验的 ParseStatus 快照数组，支持查看完整 queued → parsing → ocr（可选）→ indexing → completed / failed 过程。indexing 在本单仅指构建并验证记录关联，不是检索索引。依赖异常原文和凭据不会进入命令输出或状态记录。

每条记录先过冻结的 JSON Schema，随后检查外键、物理页码上限、章节路径、标题、bbox 顺序及引用唯一性。最终四类记录全部通过后作为一组原子发布；页面批次也必须先通过同一门禁，再单独原子发布。后续页失败不会删除已校验批次，部分产出不进入已完成论文列表。已有记录保持不可变，重复上传相同 PDF 返回相同记录；输出目录被修改或冲突时拒绝覆盖。

本地默认限制：50 MiB、可配置2000页。分批路径为32页文本批次、单批120秒、单页OCR90秒、整篇1800秒；小型文本PDF的单次引擎上限300秒。`--timeout` 可设为1–3600秒，但分批路径同时受各批及剩余整篇时限约束。MinerU 原始中间结构仅在子进程 stdout/内存中传递，不把未校验的第三方 JSON 当作项目记录保存。输入快照保存在 data/ 下临时目录，结束时清理。

## 第二步：比较两版

先分别解析 v1 与 v7，再将两次得到的 paper id 代入：

```powershell
backend/.venv/Scripts/python.exe -m scholar_graph compare data/module-one/papers/<old-paper-id> data/module-one/papers/<new-paper-id>
```

在 `data/module-one/comparisons/comparison-<id>/` 生成 dedup-decisions.json（DedupDecision 数组）与 diff-summary.json（DiffSummary）。相似度是词频重叠的 Dice 系数，不是科研质量或结论可信度。正文一致时建议 keep_old；发现变化时保守建议 manual_review，不凭版本号或样本数变大自动建议 keep_new。手动比较命令用于没有精确元数据对应或需要明确指定两版的情况。上传候选现支持精确身份与缺失身份时的词频Dice兜底；同一arXiv低版本上传时建议keep_old以避免版本降级，未增加语义向量去重或跨源召回。

差异按真实 Chunk.section_path 分组；无章节分块的变化标作 Unsectioned。关键句是对应 Chunk 的最多 600 字符原文前缀，verified 必须同时通过四字段锚点匹配与原文子串检查；无锚点的外部关键句只能标 unverified。章节未变化时明确输出“未检出章节级差异”。删除章节引用旧版原文，不把删除推断为论文结论错误。

人工意见需显式提供选择与依据：

```powershell
backend/.venv/Scripts/python.exe -m scholar_graph compare data/module-one/papers/<old-paper-id> data/module-one/papers/<new-paper-id> --human-choice keep_both --human-reason '已核对两版内容，保留两版用于比较'
```

系统记录原样保留为数组第一项，人工意见是另一项且 human_override=true。程序不删除 PDF，不覆盖原系统 recommendation，也不自动执行淘汰。人工依据本身是人工意见，不冒充程序验证的科研质量结论。

## 可选 GROBID

配置 `GROBID_URL` 或 `--grobid-url http://127.0.0.1:8070` 后，通过 multipart 调用 `/api/processFulltextDocument`，将 TEI 中可靠的元数据和参考文献归一化为现有契约。默认关闭，不影响 MinerU 本地直跑。配置后调用失败即输出 UPSTREAM_ERROR，不静默声称已经用到 GROBID。禁用服务端 Crossref consolidation，避免隐式联网补元数据。

本机没有 Docker Desktop / Docker CLI，GROBID 实际联调与 `docker compose config` 均待验证。Mock HTTP/TEI 测试仅证明客户端转换逻辑，不证明真实服务已接通。Compose 的镜像标签有官方文档依据，尚未拉取或启动；详见 services/README.md。

## 验证与范围

```powershell
backend/.venv/Scripts/python.exe tests/verify_contract_boundaries.py
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --basetemp data/test-temp
backend/.venv/Scripts/python.exe tests/run_module_one_smoke.py --output-root data/module-one-smoke --report tests/reports/module-one-smoke.json
```

722 个边界用例证据见 tests/reports/contract-boundaries.md 和 JSON 逐项结果。解析/去重实跑报告见 tests/reports/module-one-report.md。所有 PDF 都是脚本自制，非官方 pdf/ 用例，不声称官方三用例通过。

当前细粒度能力的边界：本地文本模式按 MinerU 返回块分割；参考文献回退只确认编号条目，支持明确的作者（年份）标题格式和数字引用；未覆盖作者年份正文引用、复杂跨栏引用、表格/公式识别质量或全类型论文。真实论文质量尚需独立评测。GROBID 可补充结构化元数据，但本轮未实连。早期OCR证据为干净英文自制样例；本轮官方 pdf/ 真文件的产出、失败页与耗时另见修复验收报告，不将识别完成等同于逐字准确率评测。

实现参考：[MinerU 本地 SDK](https://opendatalab.github.io/MinerU/usage/sdk_api/)、[MinerU 中间格式](https://opendatalab.github.io/MinerU/reference/output_files/)、[PaddleOCR Python 接入](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html)、[GROBID 服务 API](https://grobid.readthedocs.io/en/latest/Grobid-service/)。
# 官方 PDF 修复：页面批次与去重预警

上传仍同步返回原 PaperMeta，未改任何业务 Schema。发现相同 DOI/arXiv 身份后比较；缺少身份时，对已完成论文使用词频 Dice（阈值 0.90）找候选，冲突 DOI/arXiv 身份排除。这不是语义向量去重。同一 arXiv 的低版本再次上传时建议保留库内高版本，`new_paper_id` 仍指本次上传。

单篇上传预警在 `X-ScholarGraph-Dedup-Warning` 响应头中，以 UTF-8 百分号编码返回，编码标记为 `X-ScholarGraph-Dedup-Warning-Encoding: percent-encoded-utf-8`；先解码再展示。`Link` 指向原去重接口，裁决与差异仍按本次 paper_id 读取。两个预警头均已加入本地开发 CORS expose_headers；未修改前端。批量成功项只在命中时增加可选传输字段 `warning`，不改 PaperMeta。

扫描件逐页运行 PaddleOCR，明确使用 PP-OCRv5_mobile_det 与英文 en_PP-OCRv5_mobile_rec（其他语言使用通用 PP-OCRv5_mobile_rec），每页独立限时。大于32页的文本PDF使用 PDFium 生成最多32页的临时批次，再交给 MinerU；中间页码映射回原始 PDF 物理页。MinerU 批次失败后逐页 PaddleOCR 兜底。空白页计入完成页，另外登记 empty_pages，不生成空白 Chunk。

每个成功批次先过原 Schema/外键门禁，原子发布到 `data/.../partial/{paper_id}/batch-*`，再提交 SQLite Chunk 锚点索引事务。解析期间已有 Chunk 可通过原 `/api/v1/papers/{id}/chunks` 分页读取；论文列表只列最终完成的论文。分批索引为 SQLite 的物理页/序号索引，不冒充 BGE-M3 向量索引。最终四类记录与引用关系再次验证后发布到原 papers 目录。索引连接、PDF/图片句柄明确关闭。

单页失败继续处理其他页；最终状态为 failed，错误消息列出失败的物理页，已发布 Chunk 保留可查。统一错误体仍为三个字段；details 按原契约只用标量，`failed_pages` 是逗号分隔页码，`page_errors` 为逐页安全原因文本。完整逐页运行信息保存在内部 progress.json。再次上传同一原文件可复用已校验批次，只补未完成页；批次落盘后、索引提交前发生中断时会重建索引。

可配置环境变量（不读取 .env 文件；由启动环境传入；不涉及 Key）：

| 变量 | 默认值 | 含义/允许范围 |
| --- | --- | --- |
| SCHOLAR_GRAPH_MAX_PAGES | 2000 | PDF物理页数上限，1–10000；默认覆盖541页 |
| SCHOLAR_GRAPH_TEXT_BATCH_PAGES | 32 | 每个MinerU批次页数，1–128 |
| SCHOLAR_GRAPH_PAGE_TIMEOUT | 90 | 单页OCR最长秒数，1–600 |
| SCHOLAR_GRAPH_BATCH_TIMEOUT | 120 | MinerU单批最长秒数，1–600 |
| SCHOLAR_GRAPH_TOTAL_TIMEOUT | 1800 | 分批处理整篇最长秒数，1–7200；每次worker等待同时受剩余总时限约束 |

修复验收使用本地官方 pdf/ 真文件；结果在 tests/reports/official-pdf-repair-acceptance.md。GROBID接通状态未因本次修复改变，仍待验证；本次没有调用真实大模型或真实API Key。


## 真模型、LangGraph 与 Function Calling（2026-10-25）

已使用官方 pdf/ 真文件 Attention v7（175 Chunk）和 BERT N19-1423（277 Chunk）完成 DeepSeek 实连，请求模型名 deepseek-chat；不推测服务商别名背后的模型版本。六道命题例题及故意错问的结果、失败轮次、真实工具轨迹和调用元数据见 [本轮验收报告](../tests/reports/real-model-orchestration-acceptance.md)。本节更新问答现状，不改变先前解析/写作报告的历史结论。

启动进程须已设置 SCHOLAR_GRAPH_QA_MODE、DEEPSEEK_MODEL、DEEPSEEK_API_KEY；环境只报告“已设置/未设置”。本轮不创建或读取任何 Key 文件。现有启动方式和19个端点保留。deepseek 单篇请求仍返回原 QAAnswer；跨篇仍按证据表、逐篇 QAAnswer、综合文本顺序返回三个字段。模型负责证据选择，输出只能是同一真实 Chunk 内≤600字符的连续原文；代码验证字面一致、四字段锚点与数字回溯后构造答案。数字通过只证明源文本可回溯，BLEU 的2.04差值是报告中的代码派生计算，未伪装成原文。作者顺序辅助只处理有坐标/联系信息的版面，不承诺任意论文作者网格都能恢复。

LangGraph 1.2.17 编排为 plan（规划）→ retrieve（检索）→ qa（问答）→ validate（代码校验）。deepseek 的 /compare 默认使用联合规划；两条问答端点都可显式加 ?agent=true 启用有回落的图。状态只在内存保留论文集合、证据与锚点；校验失败返回检索，最多三轮，超限拒答。显式 Agent 在模型未配置/上游不可用时调用已有摘录器，元数据 fallback_reason 明确原因；默认 deepseek 调用失败仍返回上游错误。未启用检查点，强制关闭 LangSmith 追踪，不保存原始消息、思考内容或协议正文。

已定义 search（本地词法证据检索）、graph_query（复用真实局域图谱）和 arxiv_fetch（复用原抓取与解析服务）三个工具，参数禁止额外字段、检索/图谱只访问用户指定论文。arxiv_fetch 还要求显式 allow_fetch=True 与传入现有 fetcher；当前 HTTP 比较任务不授权增补论文，故该工具在该场景返回明确错误。本轮真实 Function Calling 演示的是模型发出 search 调用，执行后以匹配的 tool_call_id 回传结果再问答；图谱/抓取分派只做模拟服务测试，不声称本轮三种工具都已真实调用。

调用元数据在 X-ScholarGraph-QA-Meta / X-ScholarGraph-Agent-Meta 响应头，UTF-8百分号编码JSON；前者为模型调用统计，后者另含节点耗时、证据数量、校验状态、回落原因与工具参数/结果摘要。两个头已加入现有 CORS expose_headers。QAAnswer 与比较体形状不变，所有现有契约零改动；前端没有修改，需由用户转达前端读取元数据的方式，未声称前端已接通。

```powershell
backend/.venv/Scripts/python.exe tests/run_real_model_acceptance.py
backend/.venv/Scripts/python.exe tests/run_real_model_acceptance.py --author-guard-only
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --run-real-model --basetemp data/real-model/reproduce-tests --junitxml data/real-model/reproduce-junit.xml
backend/.venv/Scripts/python.exe tests/audit_real_model_acceptance.py
```

实连测试须 --run-real-model 且有 Key 和模型变量，无 Key 标记跳过；普通测试自动将模式设为 extractive，模拟协议测试不计为实连。验收脚本会覆盖本轮结果JSON，重现实验应先自行保存已验收记录。本轮检索仍是词法，未把模块四向量实验自动接入 Agent。协议依据：[DeepSeek工具调用](https://api-docs.deepseek.com/guides/tool_calls/)、[聊天API](https://api-docs.deepseek.com/api/create-chat-completion/)、[LangGraph图API](https://docs.langchain.com/oss/python/langgraph/graph-api)。


## 问答SSE流式端点

新增 `POST /api/v1/papers/{paper_id}/qa/stream`，JSON请求仍为 `{ "question": "Which optimizer?" }`，响应 `text/event-stream; charset=utf-8`。无需另造答案记录：`final`事件的data**直接是原QAAnswer**，仍经过原Schema、真实Chunk四字段锚点、字面原文与数字回溯门禁。原同步问答/比较端点保持。该SSE端点始终使用已有Agent编排，最多三轮校验；新的传输事件不写入contracts/。

用支持POST流读取的客户端：

```bash
curl -N -H "Content-Type: application/json" -H "Accept: text/event-stream" -d '{"question":"Which optimizer?"}' http://127.0.0.1:8000/api/v1/papers/<paper_id>/qa/stream
```

将paper_id替换为真实已入库id。浏览器原生EventSource只发GET，本端点应使用fetch POST及ReadableStream读取。每个事件都有递增id，JSON data单行编码，空行结束；10秒无业务事件发一条`: keep-alive`注释。当前不支持断线重放，重新POST会重新执行，不把Last-Event-ID当作续跑凭据。

| event | data形状与含义 |
| --- | --- |
| mode | mode、token_streaming、fallback_reason、message；无Key/模型变量或extractive模式明确写“回落模式、非 token 流式” |
| node_start | node(plan/retrieve/qa/validate，超限另有refuse)、attempt、elapsed_seconds=0、evidence_count |
| node_end | node、attempt、elapsed_seconds、evidence_count、status；validate另含validation和validation_error原文；失败节点另有reason |
| tool_start | tool_name、origin=model_function_call、tool_call_id、attempt、evidence_count=0（尚未返回） |
| tool_end | 同一工具ID、真实来源、参数/返回摘要、elapsed_seconds、status、实际返回evidence_count；不发原始参数正文 |
| token | node=qa、attempt、delta、verified=false、channel=model_json_draft；只转发上游content增量，不发reasoning_content |
| final | 原QAAnswer本身，没有额外包装；只有验证通过后才发 |
| error | 既有三字段错误体{error_code,message,details}；不包含上游原始正文/Key |
| done | status(completed/refused/error)、安全调用/trace元数据及是否token流式；流结束 |

SSE事件attempt从1开始分轮；done.metadata.trace保留既有规划节点执行前的计数口径（第一轮plan为0），前端按SSE节点事件的attempt分组即可。证据数为当前图状态中的检索数量，不等于最终锚点数或节点新增数量。node_end.status=completed表示节点执行完，校验是否通过须看validation，不以completed冒充通过。校验驳回原因是既有代码门禁原文；重试会重新规划、检索和问答，第三轮仍不通过则返回原契约拒答记录。

deepseek模式的qa节点设置上游stream=true，读取真实分块后即发token，不等完整答案再拆字。当前模型输出协议是证据选择JSON，因此delta是**未校验JSON草稿片段**，不是final.answer的逐字拼接；事件条数也不是服务商token数。客户端不得把草稿当作已核验事实，应以最终QAAnswer替换。无Key、缺模型变量或extractive模式不构造模型客户端，不发任何token或虚构模型工具调用，只发真实本地节点轨迹与最终整段记录。模式不合法、坏请求或论文不存在，在SSE开始前保留正常HTTP422/404错误；配置齐全后上游连接/协议失败则发error→done(error)，没有final，不中途静默回落。HTTP头已发出后状态仍200，调用方须读error/done判断结果。

响应设置Cache-Control:no-cache,no-transform及X-Accel-Buffering:no，不设置Content-Length。队列最多32条，慢消费者施加背压；断开后停止后续节点、取消队列等待并关闭活动的上游流。规划阶段的同步HTTP等待仍受现有60秒超时约束，不承诺瞬间中断尚未返回的规划请求。无检查点，不写完整模型请求/响应、思考内容或Key。启动环境的Key仅用于后端到官方DeepSeek的Authorization头，不进入SSE元数据。

转达WorkBuddy：当前前端同源代理先调用upstream.text()，会缓冲SSE；前端单需专门透传upstream.body、保留SSE头，fetch POST逐事件读取，处理草稿、final、error、done和断开。现有CORS已允许本地3000的POST/Content-Type，本单无前端源码或契约改动。现有Docker容器不会自动加载新源码；使用容器时须重建镜像后才有本端点，本轮验收使用临时真实TCP后端，不冒充已部署进旧容器。

新增离线协议/回落测试不需要Key，真实模型SSE测试标记real_model，仅--run-real-model且Key/模型变量可用才执行，无Key跳过。真实TCP的deepseek与无Key回落日志、全量回归及事件接入约定见[本轮报告](../tests/reports/qa-sse-acceptance.md)。参考：[DeepSeek流式聊天协议](https://api-docs.deepseek.com/api/create-chat-completion/)、[Starlette StreamingResponse](https://starlette.dev/responses/)、[HTTPX流式读取](https://www.python-httpx.org/quickstart/#streaming-responses)。


## 模块三：英→中翻译与Chunk对齐

`POST /api/v1/papers/{paper_id}/translate` 接受JSON，返回传输封装，不新增或修改contracts业务记录。本单只支持target=zh；中→英全文翻译与前端同步滚动均未实现。当前已有端点加本端点合计21条。

四种请求：

```json
{"scope":"abstract","target":"zh"}
{"scope":"section","target":"zh","section_path":["1 Introduction"]}
{"scope":"selection","target":"zh","chunk_ids":["<stored_chunk_id>"]}
{"scope":"full","target":"zh"}
```

section_path是落盘Chunk的完整章节路径前缀，包含子章节；selection只接受该论文已有chunk_id，按原文顺序返回，不接受任意未锚定字符串，也不支持Chunk内字符选区。section/selection分别必须提供section_path/chunk_ids，其余scope不接受这两项；重复或未知chunk_id、未知范围、target=en及额外字段均422。

响应：`{paper_id,scope,target,segments,markdown,metadata}`。segments每项固定包含source_chunk_id、source_text、translated_text、paper_id、page_number（PDF物理页）、section_path、type。一条源Chunk对应一条译文；Chunk过长时仅内部拆分再拼回，不新增Chunk或伪造id。摘要按Abstract/摘要章节识别；无该章节时只接受与PaperMeta.abstract完全对应的真实Chunk，不用元数据生成虚拟锚点。当前官方Attention源解析把脚注等也归入Abstract，该scope沿用已落盘边界，报告如实列数。

full的markdown为整篇Markdown字符串，其他scope为null。Markdown保持原Chunk顺序，按section_path层级生成标题，为每段加入`<a id="source_chunk_id"></a>`，因此段级滚动使用segments中的source_chunk_id即可双向对应。表格保留原HTML/Markdown行列标记，公式块、代码块与行内代码、美元符/括号LaTeX均不发送给模型，由代码按原位置拼回；链接及结构标记也由代码保留；数字保留并核对源值，支持4.5 million与450万等确定性的单位换算，以及英文月份/计数的阿拉伯数字表示。这里只保留原解析已有的结构和表格/公式位置，不重新识别PDF版面，也不补造Chunk中没有的图片或数学语义；原解析误分的标题、公式仍会继承。

每次请求的术语表从固定NLP词表开始，已知术语先由代码统一替换为本次中文词表用语，模型提出的新术语须有源文和译文依据，且与已完成段落兼容后才能加入；后续批次复用同一词表。metadata.terminology列出本次词表，不持久化全局词表。术语、结构、中文正文和数字增改校验失败时最多重试一次，仍失败返回原三字段UPSTREAM_ERROR，绝不返回部分成功译文。语义质量仍需抽查，结构校验不等于全部翻译逐句无误。

翻译始终使用DeepSeek，独立于SCHOLAR_GRAPH_QA_MODE；只从进程环境读取DEEPSEEK_API_KEY与DEEPSEEK_MODEL，不读写Key文件，不提供无Key摘录假译文。缺配置返回502/UPSTREAM_ERROR及“环境变量未设置，未调用模型”；上游HTTP/连接/超时失败也返回明确统一错误，不包含上游原始正文。metadata仅含服务商、模型名、耗时、token用量、词表与对齐说明，不含Key、请求消息或思考内容。非持久化同步端点，无后台队列或翻译缓存。

原文上限600000字符，超过时422并要求按章节/选区调用；内部每个单元约3000字符、批次最多4000字符或32单元，翻译调用max_tokens=8192，旧问答默认2400不变。批次间检查900秒总预算，单次上游调用沿用60秒网络超时；不承诺HTTP读取持续有数据时绝对900秒中断。

前端协作（由用户转达WorkBuddy）：通过原同源代理POST本端点，按segments的source_chunk_id匹配阅读器已落盘Chunk，page_number与section_path用于定位校验；full.markdown用于整篇版式视图，原文/译文段级滚动不依赖译文字符长度。本单没有改前端，没有声称同步滚动已接通；现有Docker镜像需要重建才含本端点。

实连测试标记real_model，需`--run-real-model`与模型/Key变量，无Key跳过；离线协议和未配置错误测试仍执行。官方Attention的摘要、章节和全文实测、对照样本及回归证据见[翻译验收报告](../tests/reports/translation-acceptance.md)。调用依据：[DeepSeek聊天与JSON输出协议](https://api-docs.deepseek.com/api/create-chat-completion/)。
