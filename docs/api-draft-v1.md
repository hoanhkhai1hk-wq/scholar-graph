# API 契约草案 v1

日期：2026-10-24。端点前缀 `/api/v1`。数据结构的唯一依据为 [CONTRACTS.md](../contracts/CONTRACTS.md)：原五类记录使用 `schema_version=1.0.0`，新增四类记录使用 `1.1.0`。本文件记录 HTTP 传输封装与真实实现范围，不修改九份业务 Schema。

## 五份契约引用

| 名称 | JSON Schema |
| --- | --- |
| PaperMeta（论文元数据） | [paper-meta.v1.schema.json](../contracts/paper-meta.v1.schema.json) |
| Chunk（分块） | [chunk.v1.schema.json](../contracts/chunk.v1.schema.json) |
| ReferenceEntry（参考文献条目） | [reference-entry.v1.schema.json](../contracts/reference-entry.v1.schema.json) |
| CitationLink（正文引用对应） | [citation-link.v1.schema.json](../contracts/citation-link.v1.schema.json) |
| QAAnswer（带证据问答） | [qa-answer.v1.schema.json](../contracts/qa-answer.v1.schema.json) |

`契约[]` 表示该契约记录的数组。文件字节、路径参数、查询词、分页与批量结果属于传输层，不新增业务记录。未裁定结构仍须经用户转达总指挥处理，禁止自行添加业务字段。

## 端点清单

核对结果：开工基线实际为 **17** 条业务端点，并非任务文字所称 16 条。本单保留全部原端点，增加明确授权的去重、差异两个 GET，共 19 条；其中落地 10 条、未落地 9 条。OpenAPI/Swagger 基础设施不计入业务端点。以下“后续单号待总指挥分配”表示尚无正式单号，不代替威龙排单。

| 方法 | 端点（均加 /api/v1） | 请求 | 响应契约与 HTTP | 实施状态、原因及后续归属 |
| --- | --- | --- | --- | --- |
| POST | /papers | multipart 字段 file：一个 PDF；本轮不接收附加元数据 | 201 PaperMeta；Location 指向详情 | 本单已落地；同步 MinerU / PaddleOCR |
| POST | /papers/batch | multipart 字段 files：多个 PDF | 200 批量结果，见下文 | 本单已落地；按文件顺序同步处理 |
| GET | /papers | page、page_size；title 忽略大小写包含匹配，year/source 精确筛选 | 200 分页 PaperMeta | 本单已落地 |
| GET | /papers/{paper_id} | paper_id 引用 PaperMeta.id | 200 PaperMeta；Link 头指向 chunks/references/citation-links | 本单已落地；不向 PaperMeta 添加子集合字段 |
| GET | /papers/{paper_id}/parse-status | paper_id 引用 PaperMeta.id | v1.1 已定义，返回 ParseStatus，200 最新持久化快照 | 本单已落地 |
| GET | /papers/{paper_id}/chunks | paper_id；page、page_size | 200 分页 Chunk | 本单已落地 |
| GET | /papers/{paper_id}/references | paper_id；page、page_size | 200 分页 ReferenceEntry | 本单已落地 |
| GET | /papers/{paper_id}/citation-links | paper_id；page、page_size；可按 ref_id、chunk_id 精确筛选 | 200 分页 CitationLink | 本单已落地 |
| POST | /papers/{paper_id}/qa | paper_id、问题文本；证据引用既有契约 | QAAnswer | 未落地：超出模块一；模块二，后续单号待总指挥分配 |
| POST | /compare | PaperMeta.id 列表、问题文本 | QAAnswer，anchors 可跨论文 | 未落地：跨篇问答，不是版本差异；模块二/跨篇对比，后续单号待总指挥分配 |
| GET | /graph | PaperMeta.id 列表 | 基础数据引用 PaperMeta、ReferenceEntry、CitationLink；图谱结构留待 v1.2 | 未落地：模块五，依赖 v1.2 裁定；后续单号待总指挥分配 |
| POST | /reviews | PaperMeta.id 列表、写作要求 | 带证据文字可引用 QAAnswer；综述结构留待 v1.2 | 未落地：综述/写作，依赖 v1.2；后续单号待总指挥分配 |
| POST | /retrieval/search | 查询词 | 分页 PaperMeta；无 PDF 时可空文件信息 | 未落地：检索推荐，不在模块一；后续单号待总指挥分配 |
| POST | /retrieval/fetch | PaperMeta[] | 列表结果使用统一分页；抓取任务与失败结构仍待裁定 | 未落地：检索抓取，不在模块一；后续单号待总指挥分配 |
| GET | /recommendations | PaperMeta.id 列表、查询词 | 分页 PaperMeta；分数与理由未定义 | 未落地：检索推荐，不在模块一；后续单号待总指挥分配 |
| POST | /frameworks | PaperMeta.id 列表、目标文本 | 框架结构留待 v1.2 | 未落地：写作辅助，依赖 v1.2；后续单号待总指挥分配 |
| POST | /charts/csv | multipart CSV、列名与绘图要求 | ChartOutput；不得塞进 QAAnswer.answer | 未落地：模块六，只有 v1.1 契约已定义；后续单号待总指挥分配 |
| GET | /papers/{paper_id}/dedup-decision | paper_id **就是 new_paper_id** | 200 DedupDecision；无记录 404 PAPER_NOT_FOUND | 本单已落地；人工裁决优先，保留原系统记录 |
| GET | /papers/{paper_id}/diff-summary | paper_id **就是 new_paper_id** | 200 DiffSummary；无记录 404 PAPER_NOT_FOUND | 本单已落地；与选中裁决取自同一比较记录组 |

## 已定义的传输裁定

### 分页封装：已定义

所有列表类端点统一响应 `{items, page, page_size, total, total_pages, has_next}`。items 内保留业务记录原形。page 默认 1，page_size 默认 20；两者必须为正整数，否则 422 VALIDATION_ERROR。page_size 超过 100 按 100 计，响应回显实际值；total 是筛选后的总条数，total_pages = ceil(total / page_size)，has_next = page < total_pages。空集合 total_pages 为 0；越界页返回空 items，保留请求 page。列表按 paper_id 稳定排序，子资源保留落盘顺序。详情、状态、裁决和摘要直接返回记录，不套分页壳。未来未落地列表亦须遵循此封装，未声称其已实现。

### 批量上传部分失败：已定义

`POST /papers/batch` 响应一律 HTTP 200，固定 `{succeeded, failed, succeeded_count, failed_count}`。succeeded 每项为 `{paper_id, parse_status}`，parse_status 是真实初始 ParseStatus（queued/0），不是查询时的最新状态。failed 每项为 `{filename, error_code, error_message}`；error_code 使用 v1.1 的 11 码之一。每个文件恰好进入一个结果集合，各集合保持输入中的相对顺序；失败后继续处理后续文件，不静默丢弃。

本轮按文件顺序同步等待本地解析完成，没有异步队列。返回后 GET parse-status 可已为 completed；失败的 PDF 如已经建立状态，也可按其文件 SHA-256 对应 paper_id 查询 failed。扩展名错误或过大文件在管线接收前拒绝，不虚构其排队记录。空列表返回两个空集合及 0/0；无法解析 multipart 时用 filename=`(request)` 的 VALIDATION_ERROR 记录请求级失败；非 files 字段逐项记 VALIDATION_ERROR，无文件名用 `(unnamed)`。批量结果是传输封装，不是统一错误体。

### 单资源、关联键与错误

去重、差异路径中的 id 一律为新版 PaperMeta.id，不接受旧版键冒充新版。无记录返回 404，统一错误体固定 `{error_code, message, details}`，error_code=PAPER_NOT_FOUND，message 明确“无该新版论文的去重记录。”或“无该新版论文的差异记录。”；不返回空记录。存在 human_override=true 时原样返回人工记录，保留系统建议；后续系统记录不会压掉人工意见。

全 API 错误引用 ParseStatus 的 `#/$defs/api_error`；无诊断时 details=null，不塞业务记录。单上传不合法请求 422、非 PDF 415、超过 50 MiB 413、解析/OCR 失败 422、上游错误 502、未知内部错误 500。未知端点 404 也用三字段体。管线状态机、物理页码、裸 DOI、输出 Schema 与锚点门禁沿用上一单。GROBID 状态为**待验证**，HTTP 默认管线只走本地 MinerU 与 PaddleOCR；现有可配置 GROBID 客户端仅有 Mock 证据，不是实际联调。

## 交给总指挥的契约缺口

本栏登记截至 v1.1 的业务契约及本轮获批的传输裁定。九份 Schema 零修改；契约定义完成不表示对应端点已实现，实现状态以上表为准。

| 缺口 | 状态 | 契约引用与边界 |
| --- | --- | --- |
| A：去重裁决 | v1.1 已定义 | [DedupDecision](../contracts/dedup-decision.v1.1.schema.json)；人工意见另存记录，原系统建议原样保留 |
| B：版本差异摘要 | v1.1 已定义 | [DiffSummary](../contracts/diff-summary.v1.1.schema.json)；无锚点关键句必须标 unverified，空变化章节须写“未检出章节级差异” |
| C：解析状态与统一错误封装 | v1.1 已定义 | [ParseStatus](../contracts/parse-status.v1.1.schema.json)；`/papers/{id}/parse-status` 返回 ParseStatus，其中 id 即端点表中的 paper_id，引用 PaperMeta.id；全 API 错误响应引用同文件 `#/$defs/api_error`，错误码与 ParseStatus 共用编码表 |
| CSV 图表输出 | v1.1 已定义 | [ChartOutput](../contracts/chart-output.v1.1.schema.json)；`/charts/csv` 的图表业务响应引用 ChartOutput，严禁塞进 QAAnswer.answer，图注数字必须通过 CSV 回溯检查 |
| 分页封装 | 已定义 | 本轮授权固定六字段传输壳，见“已定义的传输裁定”；不增加业务字段 |
| 批量上传部分失败 | 已定义 | 本轮授权固定四字段传输壳，逐文件记录成功或失败；同步处理，见上文 |
| 图谱结构 | 不在 v1.1，留待 v1.2 | 本单不定义多集合封装、节点或边结构，不返回某个图形库的专用对象作为契约 |
| 综述框架结构 | 不在 v1.1，留待 v1.2 | 本单不定义结构化综述章节、独立框架或导出结构；QAAnswer 的带证据文字不替代这些结构 |

异步任务队列与标识、推荐分数与理由、抓取任务专用失败结构仍未定义；后续范围由总指挥另行拆单。分页和 PDF 批量部分失败已由本轮明确授权定义，不据此扩展到未裁定业务字段。

WorkBuddy 的前端、其他文档和跑测、DeepSeek Harness 的 Prompt 实验由总指挥另行拆单，协作与变更请求通过用户中转，不直接联系其他工具。本轮没有验证前端与这些 API 的对接。
