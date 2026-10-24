# 数据契约 v1

版本：`1.0.0`。首次建立日期：2026-10-24。仓库名为 `scholar-graph`，后续 Python 包名为 `scholar_graph`。

本目录是模块间业务数据交换的唯一口径。五类记录为 PaperMeta（论文元数据）、Chunk（分块）、ReferenceEntry（参考文献条目）、CitationLink（正文引用对应）和 QAAnswer（问答输出）。本单只定义结构，不包含生产、解析、校验服务或页面实现。

## 版本与通用约定

- 使用 JSON Schema Draft 2020-12；每类记录有独立 Schema 和一个合成示例。`.v1.` 表示主版本，每个记录的 `schema_version` 必须为 `1.0.0`；Schema 的 `$id` 也携带完整版本。
- 每个对象的字段全部列入 `required`；可空字段仍须出现并使用 `null`。未知列表使用 `[]`，不得把未知年份写成 0、未知布尔值写成 false 或把未知文本写成空字符串。未知列表不代表已确认没有作者或机构。
- 所有对象禁止额外字段（`additionalProperties: false`）。字段增加、删除、重命名、类型、必填性、枚举或语义调整均必须升版本号并在本文变更记录登记，经总指挥验收后采用。不得由单个模块扩展字段或自行约定隐藏结构。
- 首版字段规则不是其他工具已接受的证明。协作中的变更需求由用户中转给总指挥（威龙）裁定；本仓库不直接联系其他工具。
- 标识符使用英文字符、数字及 `._:-`，以字母或数字开头；是无业务含义的稳定标识，不使用中文、文件路径或标题作为标识符。路径和文件名一律英文，字段值可以使用中文。
- 所有 `page_number` 都是 PDF 物理页码，从 1 开始，封面也计入；不使用论文印刷页码。`year` 为整数 1–9999 或 null。
- 作者为按原文顺序排列的姓名字符串数组；机构为去重字符串数组。v1 不表达作者与机构的对应关系，不自行把字符串换成对象。
- DOI 如已知，保存裸 DOI，不加 `https://doi.org/` 或 `doi:` 前缀。`arxiv_id` 不加 URL 或 `arXiv:` 前缀，可保留原文版本后缀（例如 v2）；未确认则为 null。
- 单记录按对应 Schema 校验。列表表示同一类记录的 JSON 数组，不构成第六份契约。HTTP 查询参数、文件上传、内容类型属于传输约定；业务内容仍只能使用这五类记录。未被覆盖的任务状态、图结构、错误结构和图表结构不得自行新增数据对象。

## 文件与字段数

字段数按顶层 `properties` 统计，包含 `schema_version`，不重复计算嵌套字段。

| 契约 | Schema | 示例 | 顶层字段数 | 不含版本字段 |
| --- | --- | --- | ---: | ---: |
| PaperMeta | [paper-meta.v1.schema.json](paper-meta.v1.schema.json) | [paper-meta.v1.example.json](paper-meta.v1.example.json) | 14 | 13 |
| Chunk | [chunk.v1.schema.json](chunk.v1.schema.json) | [chunk.v1.example.json](chunk.v1.example.json) | 11 | 10 |
| ReferenceEntry | [reference-entry.v1.schema.json](reference-entry.v1.schema.json) | [reference-entry.v1.example.json](reference-entry.v1.example.json) | 10 | 9 |
| CitationLink | [citation-link.v1.schema.json](citation-link.v1.schema.json) | [citation-link.v1.example.json](citation-link.v1.example.json) | 6 | 5 |
| QAAnswer | [qa-answer.v1.schema.json](qa-answer.v1.schema.json) | [qa-answer.v1.example.json](qa-answer.v1.example.json) | 5 | 4 |

## PaperMeta：论文元数据

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| schema_version | string | 固定为 1.0.0，数据契约版本 |
| id | string | 论文记录标识；其他契约通过 paper_id 引用 |
| title | string / null | 论文标题，未提取时为 null |
| authors | string[] | 作者姓名，保留原文顺序 |
| institutions | string[] | 去重机构名称 |
| abstract | string / null | 摘要原文 |
| year | integer / null | 发表年份，不用上传年份替代 |
| source | string / null | 可核实的来源描述或地址，不猜填 |
| arxiv_id | string / null | arXiv 标识 |
| doi | string / null | 裸 DOI |
| version | string / null | 论文或文件的来源版本号，与 schema_version 区分；没有证据则为 null |
| file_hash | string / null | 原始 PDF 字节的 SHA-256，小写 64 位十六进制；尚未取得 PDF 时为 null |
| page_count | integer / null | 已知时为正整数 |
| has_text_layer | boolean / null | 是否存在可提取文本层；未检查为 null；不代表文本质量已通过 |

未取得 PDF 的检索元数据允许 file_hash、page_count、has_text_layer 为 null。取得文件后可补齐未知值；已绑定原始文件字节发生变化时必须使用新的 id，不覆盖旧记录绑定。论文同名、DOI 相同与 PDF 字节相同是不同概念，v1 不定义去重业务规则。

## Chunk：分块

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| schema_version | string | 固定为 1.0.0 |
| chunk_id | string | 全局唯一分块标识 |
| paper_id | string | 对应 PaperMeta.id |
| page_number | integer | 物理页码，从 1 开始 |
| section_path | string[] | 由外到内的完整章节标题路径；未知为 [] |
| heading_1 | string / null | 一级标题的原文，含原文编号 |
| heading_2 | string / null | 二级标题的原文 |
| heading_3 | string / null | 三级标题的原文 |
| text | string | 非空正文；表格、图片、公式使用有来源的文本表示，不能伪造识别结果 |
| bbox | number[4] / null | `[x0, y0, x1, y1]`，无可靠坐标时为 null |
| type | string | 固定枚举 text / table / figure / formula |

一个分块只属于一页；跨页内容拆为多条。坐标使用按 PDF 页面旋转后的可见整页归一化坐标，原点左上，x 向右、y 向下，范围 0–1；要求 x0 < x1 且 y0 < y1。不得把像素坐标、PDF 原始点坐标混入。section_path 可以超过三级，heading_1/2/3 应分别等于路径前三项，不存在的层级为 null。没有章节标题时路径为空且三项标题均为 null。

## ReferenceEntry：参考文献条目

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| schema_version | string | 固定为 1.0.0 |
| ref_id | string | 全局唯一参考文献条目标识 |
| paper_id | string | 包含这条参考文献的论文，而非被引论文的内部 id |
| number | integer | 该论文参考文献序号，从 1 开始 |
| authors | string[] | 参考文献作者姓名 |
| year | integer / null | 参考文献年份 |
| title | string / null | 参考文献标题 |
| venue | string / null | 出处，例如期刊、会议或预印本平台 |
| doi | string / null | 被引文献的裸 DOI |
| arxiv_id | string / null | 被引文献的 arXiv 标识 |

同一 paper_id 下 number 唯一。没有显式编号的参考文献按文末条目顺序从 1 编号，正文作者年份引用只能在对应条目被确认后使用这一序号。没有确认匹配的引用不得猜造条目。v1 不增加原始引用字符串或被引论文内部 id。

## CitationLink：正文引用对应

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| schema_version | string | 固定为 1.0.0 |
| paper_id | string | 出现正文引用的论文 id |
| citation_number | integer | 引用标记解析后的参考文献序号，必须等于目标条目的 number |
| page_number | integer | 引用出现的物理页码 |
| chunk_id | string | 引用出现的具体分块 id |
| ref_id | string | 指向的 ReferenceEntry.ref_id，不能省略 |

这是双向跳转的基础记录。正文 `[1, 3]` 建两条，`[2–4]` 建三条，分别链接确定的目标条目；同一参考文献在不同页或分块出现须保留多条。v1 的定位粒度为分块：同一分块内相同引用标记多次出现合为一条，唯一键为 `(paper_id, citation_number, page_number, chunk_id, ref_id)`。它不是字符位置级跳转契约。

正向：由 paper_id、page_number、chunk_id 定位正文，再用 ref_id 找文末条目。反向：用 ref_id 查询全部引用记录，再回到各正文分块。paper_id 必须同时匹配 Chunk.paper_id 与 ReferenceEntry.paper_id，page_number 必须等于 Chunk.page_number；不接受悬空引用或跨论文误连。尚未确认匹配的引用不输出 CitationLink，不以 null 或虚构 ref_id 代替。

## QAAnswer：问答输出

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| schema_version | string | 固定为 1.0.0 |
| answer | string | 非空回答；拒答时写明拒答原因 |
| anchors | object[] | 回答证据锚点，结构见下文 |
| numeric_fact_check | object | 数字事实校验结果，结构见下文 |
| refused | boolean | true 为拒答；false 的回答至少有一个锚点 |

每个锚点有且只有四个必填字段：paper_id（论文 id）、page_number（物理页码）、section（完整章节路径 string[]）、chunk_id（分块 id）。section 对应 Chunk.section_path，页码与论文必须匹配目标分块。跨篇回答可以在一个 anchors 数组内引用多篇论文。

numeric_fact_check 有且只有两个必填字段：status（汇总状态）与 checks（逐项记录数组）。每项 checks 有且只有 claim（待核数字陈述）、status（单项状态）、evidence（相同四字段锚点数组）、reason（非空校验理由）。evidence 的锚点也须包含在顶层 anchors 中。

- 单项 status：passed（已由证据支持）、failed（与证据矛盾）、unverifiable（证据不足）。passed 至少提供一个 evidence；其他状态也须提供 reason，不把无证据当成通过。
- 汇总 status：存在 failed 则为 failed；否则存在 unverifiable 则为 unverifiable；全部为 passed 且非空时为 passed。回答没有可校验数字事实时为 not_applicable，checks 必须为空。
- Schema 对状态枚举、非空证据及汇总组合施加结构约束，但不证明数字真实性、单位一致、计算正确或锚点有效。当前示例中的“通过”仅为合成数据示意，没有执行真实论文或模型评估。
- refused=true 时 anchors 可为空，也可携带拒答依据；不修改任何字段以隐藏拒答。拒答也必须填写 numeric_fact_check，没有数字事实时使用 not_applicable。

## 跨记录约束与示例边界

JSON Schema 只能检查单条记录结构，不能完成外键、文件哈希实值、bbox 大小关系、章节路径一致、页码上限、数字真实性或唯一性校验。后续生产者与消费者必须依上文口径校验这些约束；本单不实现校验业务。

同一文件记录内 Chunk.page_number 和锚点页码不得超过已知 PaperMeta.page_count。每个 Chunk.paper_id 必须存在；ReferenceEntry.paper_id 必须存在；CitationLink 和所有问答锚点必须指向存在且一致的记录。集合内 id、chunk_id、ref_id 全局唯一，ReferenceEntry 的论文内序号唯一。

五份示例为互相关联的合成数据，零值 SHA-256 是格式占位，不对应真实 PDF；示例标题、机构、作者、12 个样本等均不构成项目实验或真实科研事实。示例仅用于验证格式与关联口径。

## 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| 1.0.0 | 2026-10-24 | 首次建立五份契约及合成示例；明确物理页码、归一化坐标、引用双向定位、问答证据与数字校验口径。未增加解析状态、图谱节点边、综述、推荐、框架或 CSV 图表的专用结构；这些结构需求在 API 草案登记并由用户转达总指挥。 |
