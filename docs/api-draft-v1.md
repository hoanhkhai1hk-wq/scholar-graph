# API 契约草案 v1

日期：2026-10-24。此文件仅登记端点与输入输出引用，不包含路由、请求模型、业务流程或服务实现。端点前缀暂定 `/api/v1`。数据结构的唯一依据为 [CONTRACTS.md](../contracts/CONTRACTS.md)，所有记录携带 `schema_version=1.0.0`。

## 五份契约引用

| 名称 | JSON Schema |
| --- | --- |
| PaperMeta（论文元数据） | [paper-meta.v1.schema.json](../contracts/paper-meta.v1.schema.json) |
| Chunk（分块） | [chunk.v1.schema.json](../contracts/chunk.v1.schema.json) |
| ReferenceEntry（参考文献条目） | [reference-entry.v1.schema.json](../contracts/reference-entry.v1.schema.json) |
| CitationLink（正文引用对应） | [citation-link.v1.schema.json](../contracts/citation-link.v1.schema.json) |
| QAAnswer（带证据问答） | [qa-answer.v1.schema.json](../contracts/qa-answer.v1.schema.json) |

`契约[]` 仅表示该契约记录的数组。文件字节、路径参数、查询词、问题文本和论文 id 列表为传输输入，不定义第六类业务记录。下表中的“待裁定”表示现有五份结构不能完整覆盖，禁止消费者自行添加字段或响应封装；必须由用户转达总指挥确定后再升版本并记入契约变更记录。

## 端点清单

| 方法 | 端点（均加 /api/v1） | 用途 | 请求及契约引用 | 响应及契约引用 |
| --- | --- | --- | --- | --- |
| POST | /papers | 单篇上传 | multipart PDF 文件；如附元数据只接受 PaperMeta，文件字节不是契约记录 | PaperMeta；若需异步任务描述则待裁定 |
| POST | /papers/batch | 批量上传 | multipart PDF 文件列表；如附元数据只接受 PaperMeta[] | PaperMeta[]；部分失败及任务状态封装待裁定 |
| GET | /papers | 文献列表 | 无请求体；筛选参数仅引用 PaperMeta 已有字段 | PaperMeta[]；分页封装待裁定 |
| GET | /papers/{paper_id} | 文献详情 | paper_id 引用 PaperMeta.id | PaperMeta |
| GET | /papers/{paper_id}/parse-status | 解析状态 | paper_id 引用 PaperMeta.id | 待裁定：五份契约均无解析阶段、进度或错误字段；不得通过 null 元数据猜状态 |
| GET | /papers/{paper_id}/chunks | 分块列表 | paper_id 引用 PaperMeta.id | Chunk[] |
| GET | /papers/{paper_id}/references | 参考文献条目 | paper_id 引用 PaperMeta.id | ReferenceEntry[] |
| GET | /papers/{paper_id}/citation-links | 正文与参考文献跳转数据 | paper_id 引用 PaperMeta.id；可按 CitationLink.ref_id 或 chunk_id 筛选 | CitationLink[]；以 ref_id 与 chunk_id 关联前两项列表 |
| POST | /papers/{paper_id}/qa | 单篇问答 | paper_id 引用 PaperMeta.id；问题为传输文本，证据输入只接受 Chunk[]、ReferenceEntry[]、CitationLink[] | QAAnswer |
| POST | /compare | 跨篇对比 | 论文 id 列表引用 PaperMeta.id；问题为传输文本，证据记录只使用五份既有契约 | QAAnswer，anchors 可跨多篇论文 |
| GET | /graph | 图谱数据 | 论文 id 列表引用 PaperMeta.id | 原始数据引用 PaperMeta[]、ReferenceEntry[]、CitationLink[]；三类集合封装、节点与边的专用结构待裁定 |
| POST | /reviews | 综述生成 | 论文 id 列表引用 PaperMeta.id；写作要求为传输文本 | 草案引用 QAAnswer 表达带证据文字；综述专用结构、章节层级与导出格式待裁定 |
| POST | /retrieval/search | 检索 | 查询词为传输文本 | PaperMeta[]，未取得 PDF 时允许 file_hash、page_count、has_text_layer 为 null |
| POST | /retrieval/fetch | 抓取文献 | PaperMeta[]，来源引用已有 source、doi、arxiv_id 字段 | PaperMeta[]；抓取任务及失败结构待裁定 |
| GET | /recommendations | 推荐列表 | 论文 id 列表引用 PaperMeta.id；查询词为传输文本 | PaperMeta[]；分数、理由等字段不在 v1 内，禁止添加 |
| POST | /frameworks | 框架生成 | 论文 id 列表引用 PaperMeta.id；目标为传输文本 | 草案引用 QAAnswer 表达带证据文字；结构化框架格式待裁定 |
| POST | /charts/csv | CSV 图表 | multipart CSV 文件；列名与绘图要求为传输参数 | 待裁定：五份契约没有图表规范、系列数据、图片或下载地址结构；QAAnswer 仅可表达有论文锚点的文字解读，不能替代 CSV 图表输出 |

## 交给总指挥的契约缺口

本栏登记截至 v1.1 的更新，覆盖上方保留的 v1 历史缺口描述；本单只修改本栏，不重写端点表和原有五份契约引用。v1 五份记录继续使用 schema_version=1.0.0，四类新增记录使用 schema_version=1.1.0。定义完成不表示端点已实现。

| 缺口 | 状态 | 契约引用与边界 |
| --- | --- | --- |
| A：去重裁决 | v1.1 已定义 | [DedupDecision](../contracts/dedup-decision.v1.1.schema.json)；人工意见另存记录，原系统建议原样保留 |
| B：版本差异摘要 | v1.1 已定义 | [DiffSummary](../contracts/diff-summary.v1.1.schema.json)；无锚点关键句必须标 unverified，空变化章节须写“未检出章节级差异” |
| C：解析状态与统一错误封装 | v1.1 已定义 | [ParseStatus](../contracts/parse-status.v1.1.schema.json)；`/papers/{id}/parse-status` 返回 ParseStatus，其中 id 即端点表中的 paper_id，引用 PaperMeta.id；全 API 错误响应引用同文件 `#/$defs/api_error`，错误码与 ParseStatus 共用编码表 |
| CSV 图表输出 | v1.1 已定义 | [ChartOutput](../contracts/chart-output.v1.1.schema.json)；`/charts/csv` 的图表业务响应引用 ChartOutput，严禁塞进 QAAnswer.answer，图注数字必须通过 CSV 回溯检查 |
| 图谱结构 | 不在 v1.1，留待 v1.2 | 本单不定义多集合封装、节点或边结构，不返回某个图形库的专用对象作为契约 |
| 综述框架结构 | 不在 v1.1，留待 v1.2 | 本单不定义结构化综述章节、独立框架或导出结构；QAAnswer 的带证据文字不替代这些结构 |

异步任务标识、批量部分成功封装、分页封装、推荐分数与理由等仍未定义，不因 ParseStatus 或统一错误定义完成而自动获得新字段。其后续范围由总指挥另行拆单。

本栏仅登记本单授权新增的四类记录与附属错误封装。WorkBuddy 的前端、文档和跑测、DeepSeek Harness 的 Prompt 实验由总指挥另行拆单，协作与变更请求通过用户中转，不直接联系其他工具。
