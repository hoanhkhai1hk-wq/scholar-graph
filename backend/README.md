# ScholarGraph 模块一、二、四、五、六后端

## 最终 Docker 部署与回归分层

最终部署配置沿用根 Dockerfile/docker-compose.yml：后端 8000、前端 3000，只绑定本机，两个服务配置健康检查和 `restart: unless-stopped`。镜像增加独立 `/opt/vector-venv`（固定 CPU torch、Chroma、FlagEmbedding），不混用 PaddleOCR 的依赖；公开 BGE-M3 权重在运行时下载进持久卷，PDF 与 Key 不进镜像。默认无 Key 摘录式问答；模型权重未准备好时向量明确降级，不把镜像内已安装依赖说成模型已就绪。

```powershell
$env:SCHOLAR_GRAPH_REVISION=(git rev-parse HEAD)
docker compose build --no-cache
docker compose up -d --wait
docker compose exec -T backend python tests/run_regression.py fast --no-key
```

公开模型准备命令：`docker compose exec -T backend /opt/vector-venv/bin/python backend/download_bge_m3.py`，模型快照沿用既有固定版本；不需要 Key。只有准备后真实向量校验成功，才能宣称该运行环境向量已接通。

干净复现控制脚本将公开模型准备单独限时7200秒，再运行容器验收，避免下载占用测试探针的限时。本轮慢网络下的恢复入口为 `python tests/resume_final_deployment.py`：只允许论文库仍为空时恢复，保留已构建镜像及本轮容器下载片段，使用 `tests/prepare_bge_public.py` 对固定 Hugging Face 快照做有界 HTTP 范围续传（最多4路）；2,271,145,830字节和完整SHA-256都匹配才发布权重，再由原SDK确认。它只传入准备脚本，不复制宿主机模型、向量索引或解析记录。已有正式上传时拒绝用该恢复入口冒充从空库验收。

**自动追踪机制是后端生命周期内调度。** Compose 默认 `SCHOLAR_GRAPH_TRACKING_ENABLED=true`、间隔 86400 秒、启动延迟 15 秒；可选 `SCHOLAR_GRAPH_TRACKING_MAX_CANDIDATES`（默认3）、`MAX_IMPORTS`（默认1）、`PAPER_IDS`（逗号分隔，默认库内第一篇）。同一数据目录用操作系统锁选一个调度实例，单轮结束后等待下一个间隔，不补跑重叠任务；空库或指定论文尚未上传时只记等待事件。调度线程有界等待关闭；尚在返回的上游请求不会被谎报为已停止。非 Compose 本地启动默认关闭，需要同样环境变量显式开启。

`GET /api/v1/retrieval/tracking/status` 附加 `scheduler_details`（配置、active、进程号、运行数、最近事件），原手动端点保留。自动运行继续用原 TrackingService、公开 arXiv API、幂等与去重规则；记录候选和上游失败，不伪造成功。`tracking/scheduler-events.jsonl`、`scheduler-status.json` 与 `state.sqlite3` 位于持久数据目录，容器重建后日志保留。演示覆盖 `services/docker-compose.final-acceptance.yml` 使用同一调度机制，只将间隔设为60秒、固定官方 Attention 种子、max_imports=0（只追踪候选）；移除此覆盖即回到每日部署配置。

回归统一入口：

| 层 | 命令 | 范围与时机 |
| --- | --- | --- |
| 快速层 | `python tests/run_regression.py fast --no-key` | 每次提交；显式单元用例白名单，只测契约、状态、身份、图谱、传输、调度等；不调用模型/解析/OCR worker，不建大索引 |
| 全量层 | `python tests/run_regression.py full --no-key --corpus-dir pdf` | 单子验收及部署前；全部回归、真实 OCR、真实本地 BGE-M3/Chroma、官方541页长书解析与索引；本单不使用 Key |

全量层已有5项真实模型用例：无 Key 或模型名时跳过，跳过不计为通过；需要已授权真模型验收时，提供进程环境并去掉 `--no-key`，才会执行这些用例。显式全量层缺向量依赖/权重或长书则失败，不能靠跳过伪造覆盖。普通 `pytest` 保留按 opt-in 标记选择的行为；验收必须使用上述 full 入口。Linux 另有 Windows 专用锁测试跳过，报告逐项区分。

提交钩子：`git config --local core.hooksPath services/git-hooks`，本工作区已启用；钩子每次提交实际运行快速层。干净克隆后执行同一配置即可启用，Git 不会自动信任克隆仓库里的钩子。`.github/workflows/backend-fast.yml` 同时在 push/PR 执行快速层，未把全量 OCR/模型任务塞进每次提交。

官方容器验收：在全新 Compose 项目/空数据卷上，用 `services/docker-compose.acceptance.yml` 只读挂载现有官方 pdf/ 到 `/corpus`，再运行 `python tests/run_final_deployment_container.py`。此脚本在容器内下载公开模型、跑全量层、真实 HTTP 三用例、无 Key 问答和自动定时证据；不复用宿主机解析结果。干净远端克隆与无缓存构建入口为 `python tests/reproduce_final_deployment.py`。本轮真实结果与限制见 [最终部署验收报告](../tests/reports/final-deployment-acceptance.md)。

本后端实现本地 PDF 解析、状态机、去重与版本差异，模块二问答/对比、模块四检索/公开抓取/推荐，模块五局域引用图谱，以及模块六综述框架、摘录草稿与CSV图表，原19条 HTTP 端点保持，另增问答SSE、双向翻译、拓扑脚本与三维CSV图表端点，共23条。Python 包为 `scholar_graph`。自由成文、文档导出、异步队列仍未实现。

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

完整请求、响应及 19 条草案端点的实施清单见 [API 草案](../docs/api-draft-v1.md)；HTTP 实测及可复现命令见 [本轮报告](../tests/reports/module-one-api-report.md)。新增响应只是本轮获批的传输封装，九份业务 Schema 未改。HTTP 默认工厂不启用 GROBID；独立容器联调的当前状态见 tests/reports/grobid-integration-acceptance.md。没有验证前端接通。

## 原文 PDF 文件端点

`GET /api/v1/papers/{paper_id}/file` 返回入库 PDF 原件，`Content-Type: application/pdf`，`Content-Disposition: inline; filename="paper.pdf"`。论文详情的 Link 头新增 `rel="file"`。支持 `Range: bytes=...`（206、Accept-Ranges、Content-Range、ETag），本地开发 CORS 放行 Range/If-Range 并暴露阅读器所需响应头。非法/越界范围返回400/416及既有三字段错误封装。前端可将此 URL 交给 pdf.js；本单没有修改或验收前端阅读器。

成功的单个/批量上传和新的 arXiv PDF 下载入库都会在临时文件清理前保留原件。原件位于当前数据目录的 `original-pdfs/`，SQLite 索引以论文 id 查询服务器生成的随机文件名；不采用用户上传文件名或把请求 id 拼成文件路径。存储前对照 PaperMeta.file_hash，每次 GET 再以64 KiB块校验 SHA-256，然后由 FileResponse 按块发送；GET不加载全部 PDF或整篇Chunk。原件归档、完整性预检与发送均有界内存，原有解析器的 POST/抓取内存方式未因本端点改变。

未知 id、未保留原件的历史记录、映射文件缺失均为404/PAPER_NOT_FOUND，正文明确说明缺原件；损坏或不安全的存储映射返回422/VALIDATION_ERROR。旧版本会删除上传/抓取临时 PDF，因此历史记录不会自动出现原件。可重新上传与已入库 file_hash 完全一致的 PDF补齐映射；不会根据用户路径、arXiv当前最新版或相近标题猜测原件。已有 arXiv身份的幂等抓取仍按原逻辑复用，不自动替旧版本补下另一个文件。CLI直接解析/手工导入旧记录不在本次 HTTP 原件保留入口内。

原件及数据库放在忽略的 data/ 下，官方语料 pdf/ 仍不进Git。实测、哈希对照、穿越拒绝与 arXiv 元数据429限制见 [文件端点验收报告](../tests/reports/pdf-file-endpoint-acceptance.md)。

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

缺口 E 已补引用身份解析：参考文献提取裸 DOI、带版本 arXiv 号，支持编号条目及作者年份式条目；无编号条目按文末顺序赋号，只在正文作者年份唯一对应时建立 CitationLink。图谱按 arxiv / doi / title / author-year 记录匹配方法与依据；标题使用 Unicode 归一、小写、去标点空白后的精确匹配，作者及年份辅助排除冲突。强标识冲突或多版本歧义不猜；目标标识缺失时可用精确标题，不能覆盖已知不同标识。旧 PaperMeta.title 为 null 时仅用摘要前短小首面 Chunk 的完整文本作标题比对，保留该目标 Chunk 锚点，不改 PaperMeta；缺失作者/年份明确登记为缺失。

原 GraphEdge 五字段与全部契约保持不变。新增的是可选传输诊断字段：`diagnostics.reference_resolutions`（每条参考文献的方法、目标、依据、文末锚点或未解析原因），`diagnostics.edge_evidence`（用 edge_index 对应 edges，含 ref_id、文献序号、正文原文与锚点），以及 reference_count / resolved_reference_count / unresolved_reference_count。正文锚点与文末参考条目锚点分别提供，不能互换；没有正文 CitationLink 的边仍为 unverified。前端可忽略这些附加诊断，本单未改前端与 docs/。

官方 pdf/ 真文件四篇重跑、真实连边及未解析数见 [引用身份验收报告](../tests/reports/graph-identity-acceptance.md)。解析行为应用于新解析；哈希命中会复用旧记录，本单未自动改写既有论文组。旧记录中的已有 ReferenceEntry 可在构图时利用其文末 Chunk 补充身份依据，但旧 BERT 若完全没有 ReferenceEntry/CitationLink，须从原件解析到新的数据目录，不能凭空补出已落盘记录。

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

POST /api/v1/retrieval/fetch 接收 `{title}` 或 `{reference:完整ReferenceEntry}`。通过公开 arXiv API 唯一匹配标题/标识/裸DOI，先保存真实元数据，再下载PDF并复用模块一Pipeline、ParseJob和所有校验/发布/去重逻辑。固定HTTP200操作封装 `{succeeded,metadata,paper,initial_parse_status,parse_status,error}`；失败保留真实原因，下载前未拿到PDF不伪建queued。metadata的arxiv-id与paper的PDF哈希id明确分开，catalog里的未解析元数据不混入/papers。请求非法仍为422三字段统一错误。无真实Key、无另起解析管线；该 HTTP 抓取路径不启用 GROBID。

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

配置 `GROBID_URL` 或 `--grobid-url http://127.0.0.1:8070` 后，通过 multipart 调用 `/api/processFulltextDocument`，尝试将 TEI 元数据和参考文献归一化为现有契约。默认关闭，不影响 MinerU 本地直跑。配置后调用失败即输出 UPSTREAM_ERROR，不静默声称已经用到 GROBID。禁用服务端 Crossref consolidation，避免隐式联网补元数据。

当前独立服务配置为 services/docker-compose.grobid.yml，使用 grobid/grobid:0.9.1-crf，启动命令见 services/README.md。配置语法通过不等于容器解析通过；Mock HTTP/TEI 不算联调证据。只有显式 CLI 参数/环境变量或 Pipeline(grobid=...) 启用补充，默认 HTTP 上传与 arXiv 抓取不读取 GROBID_URL。GROBID 补 PaperMeta 与 ReferenceEntry，并重建 CitationLink；Chunk、物理页与 bbox 仍由 MinerU 负责，GROBID 正文结构不会替换 Chunk。

2026-10-26 官方 Attention v7 容器全文解析已实测。早期联调曾因第 1 条参考文献 title/venue 空字符串被拒收；C-补将空节点归一为 null，并修复 persName 分量间距后，显式补充路径已通过原契约，成功发布 1 组论文、40 条参考文献。最新证据见 tests/reports/grobid-conversion-fix-acceptance.md；tests/reports/grobid-integration-acceptance.md 保留历史失败。默认 HTTP 上传与 arXiv 路径仍未启用 GROBID；CRF 作者/机构误识别仍存在，空值与间距修复不能解决该实体识别问题。

## 验证与范围

```powershell
backend/.venv/Scripts/python.exe tests/verify_contract_boundaries.py
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --basetemp data/test-temp
backend/.venv/Scripts/python.exe tests/run_module_one_smoke.py --output-root data/module-one-smoke --report tests/reports/module-one-smoke.json
```

722 个边界用例证据见 tests/reports/contract-boundaries.md 和 JSON 逐项结果。解析/去重实跑报告见 tests/reports/module-one-report.md。所有 PDF 都是脚本自制，非官方 pdf/ 用例，不声称官方三用例通过。

当前细粒度能力的边界：本地文本模式按 MinerU 返回块分割；参考文献回退只确认编号条目，支持明确的作者（年份）标题格式和数字引用；未覆盖作者年份正文引用、复杂跨栏引用、表格/公式识别质量或全类型论文。真实论文质量尚需独立评测。GROBID 可补充结构化元数据；当前容器联调证据另见 grobid-integration-acceptance.md，不将早期 mock 写成真实接通。早期OCR证据为干净英文自制样例；本轮官方 pdf/ 真文件的产出、失败页与耗时另见修复验收报告，不将识别完成等同于逐字准确率评测。

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

`POST /api/v1/papers/{paper_id}/translate` 接受JSON，返回传输封装，不新增或修改contracts业务记录。英→中仍支持四种scope；本轮另增target=en的摘要与全文，输入及溯源说明见下方“模块六补齐”。前端同步滚动未由后端实现。当前共23条端点。

四种请求：

```json
{"scope":"abstract","target":"zh"}
{"scope":"section","target":"zh","section_path":["1 Introduction"]}
{"scope":"selection","target":"zh","chunk_ids":["<stored_chunk_id>"]}
{"scope":"full","target":"zh"}
```

section_path是落盘Chunk的完整章节路径前缀，包含子章节；selection只接受该论文已有chunk_id，按原文顺序返回，不接受任意未锚定字符串，也不支持Chunk内字符选区。section/selection分别必须提供section_path/chunk_ids，其余scope不接受这两项；重复或未知chunk_id、未知范围及额外字段均422；target=en另有下述中文输入约束。

响应：`{paper_id,scope,target,segments,markdown,metadata}`。segments每项固定包含source_chunk_id、source_text、translated_text、paper_id、page_number（PDF物理页）、section_path、type。一条源Chunk对应一条译文；Chunk过长时仅内部拆分再拼回，不新增Chunk或伪造id。摘要按Abstract/摘要章节识别；无该章节时只接受与PaperMeta.abstract完全对应的真实Chunk，不用元数据生成虚拟锚点。当前官方Attention源解析把脚注等也归入Abstract，该scope沿用已落盘边界，报告如实列数。

full的markdown为整篇Markdown字符串，其他scope为null。Markdown保持原Chunk顺序，按section_path层级生成标题，为每段加入`<a id="source_chunk_id"></a>`，因此段级滚动使用segments中的source_chunk_id即可双向对应。表格保留原HTML/Markdown行列标记，公式块、代码块与行内代码、美元符/括号LaTeX均不发送给模型，由代码按原位置拼回；链接及结构标记也由代码保留；数字保留并核对源值，支持4.5 million与450万等确定性的单位换算，以及英文月份/计数的阿拉伯数字表示。这里只保留原解析已有的结构和表格/公式位置，不重新识别PDF版面，也不补造Chunk中没有的图片或数学语义；原解析误分的标题、公式仍会继承。

每次请求的术语表从固定NLP词表开始，已知术语先由代码统一替换为本次中文词表用语，模型提出的新术语须有源文和译文依据，且与已完成段落兼容后才能加入；后续批次复用同一词表。metadata.terminology列出本次词表，不持久化全局词表。术语、结构、中文正文和数字增改校验失败时最多重试一次，仍失败返回原三字段UPSTREAM_ERROR，绝不返回部分成功译文。语义质量仍需抽查，结构校验不等于全部翻译逐句无误。

翻译始终使用DeepSeek，独立于SCHOLAR_GRAPH_QA_MODE；只从进程环境读取DEEPSEEK_API_KEY与DEEPSEEK_MODEL，不读写Key文件，不提供无Key摘录假译文。缺配置返回502/UPSTREAM_ERROR及“环境变量未设置，未调用模型”；上游HTTP/连接/超时失败也返回明确统一错误，不包含上游原始正文。metadata仅含服务商、模型名、耗时、token用量、词表与对齐说明，不含Key、请求消息或思考内容。非持久化同步端点，无后台队列或翻译缓存。

原文上限600000字符，超过时422并要求按章节/选区调用；内部每个单元约3000字符、批次最多4000字符或32单元，翻译调用max_tokens=8192，旧问答默认2400不变。批次间检查900秒总预算，单次上游调用沿用60秒网络超时；不承诺HTTP读取持续有数据时绝对900秒中断。

前端协作（由用户转达WorkBuddy）：通过原同源代理POST本端点，按segments的source_chunk_id匹配阅读器已落盘Chunk，page_number与section_path用于定位校验；full.markdown用于整篇版式视图，原文/译文段级滚动不依赖译文字符长度。本单没有改前端，没有声称同步滚动已接通；现有Docker镜像需要重建才含本端点。

实连测试标记real_model，需`--run-real-model`与模型/Key变量，无Key跳过；离线协议和未配置错误测试仍执行。官方Attention的摘要、章节和全文实测、对照样本及回归证据见[翻译验收报告](../tests/reports/translation-acceptance.md)。调用依据：[DeepSeek聊天与JSON输出协议](https://api-docs.deepseek.com/api/create-chat-completion/)。


## 模块六补齐：拓扑脚本、三维图注与中→英（2026-10-26）

新增`POST /api/v1/topologies`与`POST /api/v1/charts/csv/3d`，扩展原翻译端点target=en；共23条端点。前端、docs/API草案与contracts/所有既有schema/example均未修改。本节描述新增传输封装，不增业务记录；原/frameworks、/reviews和二维/charts/csv行为保持。

### 拓扑脚本

JSON输入paper_ids与logic/framework二选一，formats默认[tikz,dot,mermaid]。logic.nodes每项为{id,label,source_chunk_ids,column?,row?}；edges每项为{from_id,to_id,label,source_chunk_ids}。column/row为TikZ网格，缺省纵向排列；最多100节点、200边。每个依据必须属于所选论文的真实Chunk，后端返回原四字段锚点。framework直接接受既有FrameworkOutline，校验Schema、论文集合与要点锚点后按章节顺序连边，明确是章节顺序而非因果/引用推断。

返回nodes、edges、scripts[{format,script,validation}]与metadata。三种脚本均为确定性渲染器根据输入逻辑真实生成，不调用模型、不返回占位代码。格式自检先检查括号/引号，再按生成器支持的严格语法子集解析关键字、节点、边，最后与输入图逐项对照；失败422/VALIDATION_ERROR，不发布无法解析的脚本。节点id映射为n0等，标签按各语言转义，防止标签被当成命令。

运行时自检不是通用TeX/DOT/Mermaid编译器。TikZ为完整ctexart+tikz文档，未安装TeX引擎、未声称已编译PDF；本轮另用Graphviz WASM真实渲染DOT、Mermaid官方包真实解析流程图。外部解析器仅是测试依赖，装在忽略的data/module6-tools/，后端API运行不需要Node包。逻辑来自调用方/框架；锚点存在不等于系统自动证明任意调用方的边语义。

### 三维柱图与趋势图注

`POST /api/v1/charts/csv/3d`接收multipart file、value_columns（JSON数值列数组）、可选x_column。CSV校验复用二维模块；至少两行，最多8个系列、1000根柱。横轴可为严格递增数值列；未指定时按CSV记录顺序，不假称时间。三维坐标为横轴、系列、测量值，Matplotlib真实bar3d渲染800×600 PNG，负值柱向零基线以下延伸。

响应为{chart,projection,data_table,conclusions,series_aliases,metadata}。chart严格符合既有ChartOutput v1.1，chart_type仍为bar；外层projection=3d说明投影，绝不把未批准的bar3d塞进枚举。image_ref为真实PNG数据URI。data_table含所选列、数值、CSV散列与逻辑行号（表头=1）。原二维/charts/csv仍返回原七字段记录，无需Key，受限枚举图注不变。

趋势先由Fraction精确计算单调/波动、变速加快/放缓等事实，再让真DeepSeek读取所选数据行与事实，在已核验的解释性候选中选择图注。返回的图注确实来自模型响应，metadata.caption_method=deepseek_grounded_selection，如实表示受限选择；不是开放式因果推断或未来预测，也不是只枚举数字。代码核对每个系列、趋势、变化率形态、完整数据行集合与结论文本，失败最多重试一次，仍错422/CHART_VALIDATION_FAILED。CSV非法用CSV_INVALID；无模型/Key或上游失败502/UPSTREAM_ERROR，不生成假图注或部分成功图表。

conclusions逐项含series_name、trend、shape、text、row_numbers和csv_anchors，回溯全部涉及的记录；逐单元格numeric_checks仍在chart中。为避免列名中的数字被误当图注事实，含数字的列名在定性图注中改用系列甲/乙等别名，series_aliases给出映射；图与数据表保留源列名。三维雷达图本轮未实现，不计入已交付类型。

### 中→英摘要与全文

原`POST /api/v1/papers/{paper_id}/translate`增加target=en，仅支持scope=abstract/full。已入库原生中文Chunk可直接翻译；英文论文的回译须在请求中增加source_translation，值为该论文上一轮target=zh的完整响应（可覆盖更大范围）。例如先取此前中文摘要响应，再POST {scope:abstract,target:en,source_translation:此前响应}。不从英文源文直接拷贝一遍冒充中文回译。

后端核对source_translation.paper_id/target、唯一Chunk标识、英文source_text与已落盘原文、物理页/章节/类型、中文译文覆盖范围及保留的代码/公式标记。模型只接收实际中文文字片段及术语上下文，不接收上一轮英文source_text作答案。当前source_text表示本次实际中文输入，source_chunk_id仍回指原论文Chunk；这是原论文→中文→英文的对齐链，不声称中文是英文PDF原文的字面引用。

metadata新增source_language、source_translation_sha256和source_input；前者为zh，散列锁定所选中文输入。source_input区分stored_chinese_chunks与客户端提供的前次中文响应。锚点一致性可验证，客户端任意响应的模型来源不是签名认证；本轮验收额外逐段对照第④单已提交的译文manifest，证明使用原真实派生中文文件，未手写样本。

请求参数的source_translation为可选向后兼容加法，传输响应target扩展到en，原有字段保留；既有业务契约未动。中文技术词表反向复用，支持attention/attend和perplexity/perplexities等语法词形，不把漏译术语当正确。代码、公式与结构仍由代码原位保留，数字校验支持日期、中文计数与单位的双向回溯。scope=full仍输出Markdown与逐Chunk对齐。无Key明确502，不回落为假译文。

### 测试与前端协作

真实图注/中→英测试标记real_model，只有--run-real-model及Key/模型变量均已设置才执行，无Key标记跳过；普通离线验证与不需要模型的拓扑测试仍执行。独立解析器可用无敏感变量子进程安装/运行：npm --cache data/module6-tools/npm-cache install --ignore-scripts --no-audit --no-fund --prefix data/module6-tools @viz-js/viz@3.31.0 mermaid@12.2.0 jsdom@30.1.3，然后node tests/validate_topology_scripts.mjs。安装缓存也可指定D盘data/module6-tools/npm-cache，不修改全局npm配置。

用户转达WorkBuddy：拓扑用scripts[*].format/script与validation；三维图用chart.image_ref、data_table和带row_numbers的conclusions，注意外层projection；英文回译用已有中文响应作为source_translation，按同一source_chunk_id衔接定位。前端展示本单未接，旧Docker镜像未重建。真实脚本、PNG、趋势图注、中英样本与回归证据见[模块六补齐验收](../tests/reports/module6-completion-acceptance.md)。

语法/绘图依据：[DOT语法](https://graphviz.org/doc/info/lang.html)、[Mermaid流程图](https://mermaid.js.org/syntax/flowchart.html)、[TikZ节点与边](https://tikz.dev/tikz-shapes)、[Matplotlib三维柱图](https://matplotlib.org/stable/gallery/mplot3d/3d_bars.html)。

## arXiv 定期追踪、引用去重与反馈（2026-10-26）

新增以下传输端点，全部使用现有 `/api/v1` 前缀；当前共28条业务端点。既有12份业务契约、前端和docs/API草案均未修改。

| 方法与路径 | 输入和输出 |
| --- | --- |
| POST /retrieval/tracking/run | JSON：paper_ids（可选，1–5个库内id）、max_candidates（默认5，1–20）、max_imports（默认2，0–5）、interval_seconds（默认86400，60–2592000）、force（默认true）；同步返回本次完整运行记录 |
| GET /retrieval/tracking/status | latest_run、dedup_records、scheduler与default_interval_seconds；尚未运行时latest_run=null |
| POST /retrieval/citations/cleanup | 无请求体；返回扫描论文数、链接前后数量、删除数与每次清理的审计引用 |
| POST /recommendations/feedback | JSON：paper_id（被推荐论文）、seed_paper_id、vote=like/dislike、profile_id（默认local）、as_of_year（可选）；返回落盘事件号、排序前后、评分和主题词证据 |
| GET /recommendations/feedback | 查询profile_id（默认local）；返回当前有效投票与完整反馈事件记录 |

原GET /recommendations增加可选profile_id，默认local；空画像保持原排序。profile_id只是本地画像标识，不是账号认证或跨用户权限隔离。点赞/踩每个画像、每篇论文只保留一个有效值，后一次替换前一次，不因重复提交叠加权重；事件历史保留。拒绝给种子自身投票。反馈只由推荐API显式启用，框架与综述复用的纯推荐函数不读写画像目录。

### 周期任务与种子来源

提供可由Windows任务计划程序或cron定期触发的命令，无需API Key。使用与后端相同的数据目录；已安装backend包时，可在仓库根目录执行：

```powershell
backend/.venv/Scripts/python.exe -m scholar_graph.tracking_cli --data-dir data/module-one --due --interval-seconds 86400 --max-candidates 5 --max-imports 2
```

CLI 保留手动运维入口：`--due` 在距最近一次运行开始不足间隔时返回 `skipped=true,reason=NOT_DUE`，不发网络请求；手动端点 force=true 可立即运行。命令对 partial/failed 返回退出码 1，正常或未到期返回 0。最终部署已改用下述后端生命周期内调度，不依赖宿主机任务计划程序或 cron。

默认从库内按id排序的前5篇取种子，可显式指定paper_ids或重复`--paper-id`。每篇最多两条查询：标题主题词查询，以及由真实CitationLink关联的首个可用ReferenceEntry标题查询。旧导入的PaperMeta.title或参考标题为空时，可从真实首屏短文本候选和可识别的参考文献原文摘取，并附对应锚点；短文本选择是启发式，不保证总是论文题名，不回填或修改业务记录。找不到任何可用种子明确失败。主题为英文词法启发式：去停用词、拆连字符、长词尾s归一化，取排序前4词；不是语义向量检索。中文标题无可识别英文主题且无可用引用时会明确失败。

调用公开Atom API，查询按submittedDate倒序，每条查询最多max_candidates条，默认请求间隔3秒；合并相同基础arXiv ID后按查询顺序最多保留max_candidates个全局候选。相关理由包含库内paper_id、实际重合词、来源类型与可用引用锚点，不声称已证实学术承袭关系。候选是对当前库的新发现，不保证都是近期发表；引用种子可能找到历史文献。未达到导入预算的条目标deferred，未抓到、未解析成功不冒充入库。默认每次最多两次导入尝试（失败和重复也占预算），下一次重新查询，不是持久化候选队列。status为completed/partial/failed/running/interrupted，是运维运行状态，不扩展ParseStatus枚举。

### 幂等与引用维护

抓取前在跨进程入库锁内检查已发布PaperMeta：基础arXiv ID去掉vN后相同，或裸DOI大小写无关相同，则返回`already_present=true`，复用现有paper、不下载、不新建queued状态，initial_parse_status=null。旧记录无job历史时parse_status可为null，绝不伪造完成状态；已存在版本不会被轮询降级覆盖，也不会自动追新版本。真正新论文仍调用原Pipeline，queued→parsing→indexing/completed或failed，保留原DOI精确、身份冲突排除和词频Dice≥0.90机制。Dice只作疑似重复预警：按既有行为保留不同文件记录供人工复核，不把词频高相似武断等同身份，也不改成人工否决。

`retrieval/fetch`响应为原有字段加already_present和dedup（向后兼容传输加法），不改任何schema。`tracking/state.sqlite3`保存运行、去重日志、投票及反馈事件。去重日志以基础arXiv ID唯一，每次重复只更新occurrences与last_seen，不增加第二行；它是抓取运维日志，绝不冒充新业务契约DedupDecision。若新文件确实走到原Pipeline的比较流程，原DedupDecision/DiffSummary照常校验发布，本日志记录其旧论文与真实Dice分值。

每轮追踪先清理已发布论文引用链接，也可手动调用清理端点。只按(paper_id,citation_number,page_number,chunk_id,ref_id)完全一致去重，保留不同页/Chunk中的合法多次引用；校验所有原链接schema与清理后整组外键，非法锚点仍报错。替换前将原链接、前后SHA与操作意图写入tracking/citation-cleanups，之后原子替换citation-links.json并写完成凭据；不改论文元数据、正文、索引、参考条目。失败不吞异常，原件可审计；中途退出可按intent与实际文件SHA核对。上传、抓取、引用清理共享操作系统文件锁；锁随进程退出释放，锁等待超限返回明确错误，不靠删除锁文件解锁。

### 可复核的反馈评分

基础评分仍为`100*(0.40*G+0.35*P+0.15*T+0.10*C)`（局域图邻居、归一化PageRank、十年线性时效、元数据真实GitHub链接；缺失按0，不编引用次数）。新增：

```text
score = clamp(base_score + 50 * mean(vote * Jaccard(title_topics(candidate), title_topics(voted_paper))), 0, 100); empty profile adds 0
```

vote点赞为1、踩为-1；Jaccard=主题词交集数/并集数，空并集为0。标题取已发布元数据，主题归一化与追踪一致；不读伪造画像或使用向量。权重50为透明启发式，每条推荐返回base_score、feedback_adjustment和实际共同词、分母词集、投票依据；没有反馈时原响应字段和得分保持。反馈事件在同一SQLite事务写投票与排序前后，进程重启后仍可查询。无模型调用、无Key要求，沿用原三字段错误体和错误码。

两轮真实公开arXiv追踪、额外解析失败原文、引用清理数量、反馈效果与全量回归见[追踪验收报告](../tests/reports/tracking-acceptance.md)。用户转达WorkBuddy：本单只交后端端点与传输封装，前端未接入；docs草案本单未授权修改。已有Docker镜像需重建才包含这些代码，不能把旧容器视为已更新。

协议依据：[arXiv API查询、Atom与排序](https://info.arxiv.org/help/api/user-manual.html)、[arXiv API使用条款](https://info.arxiv.org/help/api/tou.html)。

## 上传语义向量去重（2026-10-26）

上传解析完成、Schema校验通过后，Pipeline接入本地BGE-M3论文向量余弦比较；既有裸DOI精确快速通道保留，向量不可用时保留身份/词频Dice与人工核对兜底，并明确返回状态，不把兜底结果称为向量结果。前端、API路径和12份业务契约均未修改。

默认SCHOLAR_GRAPH_DEDUP_MODE=auto，独立于检索模式；本机复用data/module-four-runtime/.venv/Scripts/python.exe与data/module-four-models/bge-m3。其他部署须通过SCHOLAR_GRAPH_VECTOR_PYTHON、SCHOLAR_GRAPH_BGE_M3_PATH指定已安装隔离依赖的Python与本地固定模型目录，Linux需指定实际Python路径。SCHOLAR_GRAPH_DEDUP_MODE=off显式禁用向量。模型/环境均不进镜像或Git，运行时离线，不自动下载，不需要Key；子进程移除API_KEY/TOKEN/SECRET/PASSWORD类变量。

模型沿用BAAI/bge-m3快照5617a9f61b028005a4858fdac845db406aefb181，CPU/float32，FlagEmbedding 1.4.2、torch 2.14.1+cpu、transformers 5.20.2。每篇优先取摘要、引言、结论中的真实正文Chunk，再按原文位置补足最多8个；每段最多2000字符，再按512 token截断。过滤明确标识的References/Bibliography/参考文献节，缺正文时回退真实text块，不生成虚构段落。8个dense向量取均值再归一化，得到1024维论文代表向量，论文之间计算余弦；不把检索的dense/sparse融合名次当成语义余弦。

SQLite缓存保存模型快照、文本指纹和向量，命中时复用；不缓存外部Key或把输入正文写进日志。每次隔离worker有240秒时限，异常、无效/非有限向量、校准配置不匹配均明确降级。代表性采样不等于完整论文的逐段语义覆盖，大规模库性能尚未验证。

分档来自独立4篇官方pdf/论文的实测校准，非手填常数。正样本为同论文每5个Chunk删除1个的明确人工扰动4对，负样本为4篇不同论文两两组合6对；不使用Attention v7/v1或BERT验收输入来定阈值。负样本最高0.8098823029271678、正样本最低0.9137429008639619，取观测间隔的1/3、2/3：

| 余弦范围 | 分档与行为 |
| --- | --- |
| ≥0.8791227015516972 | duplicate；同论文且版本号可核验时建议保留较新版本；身份冲突强制人工核对，未知版本不据余弦虚构质量结论 |
| ≥0.8445025022394325且低于重复阈值 | manual_review；只预警人工核对，不宣称已确认重复 |
| <0.8445025022394325 | new_paper；不发重复预警；若另有明确身份依据冲突则保留人工核对 |

另外每7块删除1块的4对保留扰动均超过重复阈值。校准只是小规模同文缺块鲁棒性，不是任意改写、中文、跨学科大样本性能证明；分布变化需重新校准。配置semantic_thresholds.json作为包数据随安装交付，绑定模型快照和采样版本。来源、完整分数与算法在tests/reports/semantic-dedup-calibration.json。

单篇上传仍返回原PaperMeta；新增响应头X-ScholarGraph-Dedup-Meta（百分号编码UTF-8 JSON）回显status、method、score、band、reason及可用推荐/回退原因；已有预警头继续使用。浏览器CORS已暴露新头。批量成功项增加dedup_metadata，属于向后兼容传输加法。完整逐候选分数、阈值和真实代表Chunk id仅落盘到semantic-dedup/assessments/{paper_id}/latest.json；向量库为同目录vectors.sqlite3。无候选时score=null，表示无可比论文；DOI快速通道score=null，明确未编码；不可用时不会返回编造分数。

不同文件的DedupDecision.similarity在status=ready时使用语义余弦；原契约下限为0，若因身份依据而比较负余弦，则该字段截为0，原始负值仍保留在元数据和reason。三组实测均为正值，无截断。证据reason明确算法、分档，DiffSummary仍是原文差异。旧的离线/禁用比较继续为Dice，二者由元数据与证据文字区分。人工human_override仍由原查询优先返回，系统不覆盖人工记录；高语义相似仅给建议，不自动删论文。keep_new只在同一arXiv身份、更高版本号可核验时给出，并带新版本Chunk依据；版本较新不等于学术质量更高。

同文件改名上传按SHA-256复用原论文，仍返回预警及缓存向量自余弦，避免重复解析/入库。由于原契约要求DedupDecision指向两个不同PaperMeta，**不伪造自比较业务记录**；这类判定放在上传响应头和本地运维记录，不返回指向不存在自比较记录的Link。正式跨版本裁决/差异端点保持原路径。

测试默认禁用本地大模型，由显式假向量验证边界、降级、DOI通道、人工裁决与协议；官方三组验收脚本另在无Key子进程真实加载本地BGE-M3。实际分数、官方输入散列、判定原文和最终回归见[语义去重验收报告](../tests/reports/semantic-dedup-acceptance.md)。旧Docker镜像需重建并另挂本地模型才能启用向量，未声称本单已完成容器向量联调。算法调用依据：[BGE-M3官方模型说明](https://huggingface.co/BAAI/bge-m3)。

## QA 混合检索（2026-10-26）

单篇问答、跨篇比较、Agent Function Calling的search工具和SSE retrieve节点现统一使用QAHybridRetriever。现有QAAnswer等12份业务契约、前端、端点路径及响应业务记录均未修改。默认SCHOLAR_GRAPH_QA_RETRIEVAL_MODE=hybrid；lexical显式回退，不依赖检索页的SCHOLAR_GRAPH_RETRIEVAL_MODE开关。

本地环境沿用SCHOLAR_GRAPH_VECTOR_PYTHON、SCHOLAR_GRAPH_BGE_M3_PATH（D盘默认路径同前节）；其他部署尤其Linux须指定实际Python和模型目录。QA片段索引单独位于数据目录chroma-qa-bge-m3，复用Chroma 1.5.9和固定快照BGE-M3，CPU、512 token、batch=1、2线程；每个worker仍独立加载模型，600秒上限包含首次建索引。向量子进程不继承API_KEY/TOKEN/SECRET/PASSWORD，离线运行；需要Key的是deepseek回答/规划，向量检索及无Key摘录模式不需要Key。

每篇论文双路召回：BGE-M3 dense余弦取前24个真实Chunk，词法路复用原IDF排序、领域别名扩展及首页作者布局覆盖，取前24个不同Chunk。并集最多48块，使用等权RRF排序：各路第r名贡献`0.5*61/(60+r)`，未召回的路贡献0。原检索页仍使用自己的BGE dense/sparse融合；QA不把BGE sparse当作这次词法路，元数据明确bge_sparse_scores_used=false。全部结果受用户论文集合约束，不把其他索引旧行返回作证据。

优先尝试本地bge-reranker-large，固定快照55611d7bca2a7133960a6d3b71e083071bbfc312。可用`data/module-four-runtime/.venv/Scripts/python.exe backend/download_bge_reranker.py`公开下载一次；运行时只读本地模型，不自动联网。SCHOLAR_GRAPH_RERANKER_PATH覆盖本地目录，SCHOLAR_GRAPH_QA_RERANKER=auto（默认）/cross_encoder（强制使用）/rrf（明确指定融合）。CPU auto设额外每请求重排预算5秒，包含本架构每次冷加载；首次实际打分并校验所有返回id后，超过预算则本次使用RRF，将实测原因和计时原子保存到qa-retrieval/reranker-policy.json，该目录后续auto复用。它是当前数据目录/当前部署的性能选择，不是通用跨硬件结论；更换硬件可重测或强制cross_encoder。模型缺失、重排失败或超时也明确用RRF，不冒充cross-encoder成功。

本机首次36个候选实测：reranker模型构造5.3434365秒、逐对推理12.4232497秒、含Python导入/进程启动的worker总耗时27.5579491秒，超过5秒预算，因此最终选RRF。没有假称reranker未安装或仅凭估计判慢。首次Attention建索引实测51.0089652秒，冷请求还包括上述重排基准；后续索引指纹命中不重复编码。报告同时列BGE模型构造时间、worker启动到模型可用时间、索引/查询时间、整段worker时间；构造时间不包含重型库导入，不能拿它与旧15–20秒端到端worker数据直接混比。

单篇/普通比较通过原X-ScholarGraph-QA-Meta返回method与retrieval列表；显式agent=true通过原X-ScholarGraph-Agent-Meta，deepseek比较同时提供两头；SSE在retrieve节点完成与done.metadata中给相同信息。头仍为百分号编码UTF-8 JSON，现有CORS已暴露。method只取hybrid（双路）、vector（词法无结果但实际向量成功）、lexical-fallback（禁用/未配置/失败）；混合多篇中任何一次回落，全局保守标lexical-fallback，每篇实际方法仍逐项保留。vector_status、reason、候选数、重排选择、真实阶段计时和版本可查；模型回答回落与向量回退是两种独立原因。

证据仍是≤600字符的连续真实Chunk窗口，答案仍过原锚点与数字门禁。单篇直接模型保留双窗口以覆盖SOTA表格；Agent工具每轮每Chunk只提供一段，并在多工具结果合并时按Chunk去重，避免模型选择同块远距离片段后跨度超过600字符。未放宽契约、未拼造省略号摘录；确无依据仍拒答。无Key摘录模式也执行真实可用的混合retrieve，只发原SSE轨迹和最终整段，不伪造token增量。

普通回归默认使用词法或显式假向量保证确定性，真实本地向量和官方六题另跑独立探针。完整六题方法、候选/返回证据数、同义改写对照、初次跨篇拒答及修复、加载与重排耗时、回归证据见[QA混合检索验收](../tests/reports/hybrid-retrieval-acceptance.md)。用户转达WorkBuddy：仅元数据增加可选字段，前端未改；冷索引请求可能较长，不能把整请求耗时当成模型加载时间。旧Docker镜像及未挂载模型的部署不会凭空启用向量，本单未重建容器。

模型依据：[BGE-M3官方模型说明](https://huggingface.co/BAAI/bge-m3)、[bge-reranker-large官方模型说明](https://huggingface.co/BAAI/bge-reranker-large)。
