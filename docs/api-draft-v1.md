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

1. 解析状态、异步任务、批量部分失败、错误与分页封装尚未被五份记录覆盖。
2. 图谱接口可以引用既有论文、条目和引用记录，但多集合传输封装与专用节点/边格式没有定义；不能直接返回某个图形库的数据对象作为新口径。
3. QAAnswer 能表示带论文证据的综述或框架文字，不能保证结构化章节、独立框架或导出附件；独立无证据创作也不符合非拒答必须带锚点的 v1 约束。
4. CSV 图表的输入文件属于传输层，其结构化输出不在五份契约内。不得将图表 JSON、Markdown 数据块或下载地址塞进 answer 字段规避版本管理。

以上为本单明确报告的接口缺口，不代表已获契约扩展授权。WorkBuddy 的前端、文档和跑测、DeepSeek Harness 的 Prompt 实验由总指挥另行拆单；本单不要求它们采用未验收的响应结构。
