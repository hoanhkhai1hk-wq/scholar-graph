# 数据契约 v1.2（图谱部分）

契约集合版本：`1.2.0`（本轮仅图谱）。首次建立及本次更新日期：2026-10-24。仓库名为 `scholar-graph`，Python 包名为 `scholar_graph`。

本目录是模块间业务数据交换的唯一口径。原 v1/v1.1 九类记录及示例保持零改动。v1.2 本轮只新增 GraphNode（论文节点）、GraphEdge（引用边）；综述框架结构仍未定义，留待后续单。统一错误封装继续引用 ParseStatus 的 $defs；图谱响应集合与未来方向取证结果的 HTTP 组合见 API 草案，事实证据复用 QAAnswer，不新增第三类 v1.2 业务记录。

## 版本与通用约定

- 使用 JSON Schema Draft 2020-12；每类记录有独立 Schema 和一个合成示例。原五类 `.v1.` 保留 1.0.0，原四类 `.v1.1.` 保留 1.1.0，新图谱两类 `.v1.2.` 使用 1.2.0。集合升级不修改已发布记录。
- 每个对象的字段全部列入 `required`；可空字段仍须出现并使用 `null`。未知列表使用 `[]`，不得把未知年份写成 0、未知布尔值写成 false 或把未知文本写成空字符串。未知列表不代表已确认没有作者或机构。
- 所有对象禁止额外字段（`additionalProperties: false`）。字段增加、删除、重命名、类型、必填性、枚举或语义调整均必须升版本号并在本文变更记录登记，经总指挥验收后采用。不得由单个模块扩展字段或自行约定隐藏结构。
- 首版字段规则不是其他工具已接受的证明。协作中的变更需求由用户中转给总指挥（威龙）裁定；本仓库不直接联系其他工具。
- 标识符使用英文字符、数字及 `._:-`，以字母或数字开头；是无业务含义的稳定标识，不使用中文、文件路径或标题作为标识符。路径和文件名一律英文，字段值可以使用中文。
- 所有 `page_number` 都是 PDF 物理页码，从 1 开始，封面也计入；不使用论文印刷页码。`year` 为整数 1–9999 或 null。
- 作者为按原文顺序排列的姓名字符串数组；机构为去重字符串数组。v1 不表达作者与机构的对应关系，不自行把字符串换成对象。
- DOI 如已知，保存裸 DOI，不加 `https://doi.org/` 或 `doi:` 前缀。`arxiv_id` 不加 URL 或 `arXiv:` 前缀，可保留原文版本后缀（例如 v2）；未确认则为 null。
- 单记录按对应 Schema 校验。列表表示同一类记录的 JSON 数组，不新增记录类型。HTTP 查询参数、集合封装与错误封装属于传输约定；业务记录只使用本文登记的十一类。图谱节点/边本轮已定义，综述框架及未裁定异步任务仍不得自行新增。

## 文件与字段数

字段数按顶层 `properties` 统计，包含 `schema_version`，不重复计算嵌套字段。

| 契约 | Schema | 示例 | 顶层字段数 | 不含版本字段 |
| --- | --- | --- | ---: | ---: |
| PaperMeta | [paper-meta.v1.schema.json](paper-meta.v1.schema.json) | [paper-meta.v1.example.json](paper-meta.v1.example.json) | 14 | 13 |
| Chunk | [chunk.v1.schema.json](chunk.v1.schema.json) | [chunk.v1.example.json](chunk.v1.example.json) | 11 | 10 |
| ReferenceEntry | [reference-entry.v1.schema.json](reference-entry.v1.schema.json) | [reference-entry.v1.example.json](reference-entry.v1.example.json) | 10 | 9 |
| CitationLink | [citation-link.v1.schema.json](citation-link.v1.schema.json) | [citation-link.v1.example.json](citation-link.v1.example.json) | 6 | 5 |
| QAAnswer | [qa-answer.v1.schema.json](qa-answer.v1.schema.json) | [qa-answer.v1.example.json](qa-answer.v1.example.json) | 5 | 4 |
| DedupDecision | [dedup-decision.v1.1.schema.json](dedup-decision.v1.1.schema.json) | [dedup-decision.v1.1.example.json](dedup-decision.v1.1.example.json) | 7 | 6 |
| DiffSummary | [diff-summary.v1.1.schema.json](diff-summary.v1.1.schema.json) | [diff-summary.v1.1.example.json](diff-summary.v1.1.example.json) | 6 | 5 |
| ParseStatus | [parse-status.v1.1.schema.json](parse-status.v1.1.schema.json) | [parse-status.v1.1.example.json](parse-status.v1.1.example.json) | 7 | 6 |
| ChartOutput | [chart-output.v1.1.schema.json](chart-output.v1.1.schema.json) | [chart-output.v1.1.example.json](chart-output.v1.1.example.json) | 7 | 6 |

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

## v1.1 新增定义

### v1.1 新增：DedupDecision（缺口 A）

顶层七项全部必填：schema_version（固定 1.1.0）、old_paper_id、new_paper_id、similarity、evidence、recommendation、human_override。两个论文 id 均引用 PaperMeta.id，必须不同。similarity 为 0–1 的数值，不等于裁决置信度或论文质量评分。recommendation 枚举为 keep_new / keep_old / keep_both / manual_review。

evidence 至少一项，每项有且只有 anchor 与 reason 两个必填字段。anchor 原样复用 v1 QAAnswer 的四字段 Chunk 锚点：paper_id、page_number、section、chunk_id；reason 为非空依据文本。锚点必须引用被比较两篇论文之一的真实 Chunk，页码使用 PDF 物理页码、section 对应 Chunk.section_path。keep_new 时必须至少有新版锚点，reason 明确说明相对于旧版的优势，不能仅以“版本较新”或相似度高作为依据。

human_override 为必填布尔字段，Schema 的 default=false 只是默认值注释，不会补齐缺失字段；生产者必须显式写入。为了在不新增字段的前提下保留系统建议，系统记录使用 human_override=false 并保持原样；人工裁决作为相同 old_paper_id/new_paper_id 的另一条记录，human_override=true，recommendation 写人工意见。两条记录必须共同保留，禁止原地替换系统 recommendation。本单不定义存储、历史排序或裁决执行代码。

规则原文：recommendation 为 keep_new 时必须在 evidence 里说明新版优于旧版的依据；human_override 为 true 时 recommendation 以人工意见为准，系统建议原样保留不许覆盖。

### v1.1 新增：DiffSummary（缺口 B）

顶层六项全部必填：schema_version（固定 1.1.0）、old_paper_id、new_paper_id、changed_sections、summary_text、key_sentences。论文 id 均引用 PaperMeta.id，必须不同。changed_sections 为去重的非空章节名称/路径字符串列表，允许空列表。summary_text 必须非空；changed_sections 为空时 Schema 要求 summary_text 包含原文“未检出章节级差异”。

每项 key_sentences 有且只有 text、anchor、status 三个必填字段。anchor 使用同一四字段 Chunk 锚点；定位失败也不能省略 anchor 字段，必须显式为 null，同时 status 必须为 unverified。status 仅允许 verified / unverified；有锚点不等于已验证，仍可为 unverified。verified 还要求关键句确实由目标 Chunk 支持，不能只凭字段存在认定。锚点只能属于被比较的两篇论文，使用 PDF 物理页码。

规则原文：关键句无锚点的，一律标 unverified，不许写成已验证；changed_sections 为空时 summary_text 必须写明「未检出章节级差异」，不许留空。

### v1.1 新增：ParseStatus（缺口 C）

顶层七项全部必填：schema_version（固定 1.1.0）、paper_id、status、progress、current_stage、error_code、error_message。paper_id 引用 PaperMeta.id。status 枚举为 queued / parsing / ocr / indexing / completed / failed；current_stage 为非空当前阶段文本。

progress 是 0–100 的整数：queued 固定为 0；parsing / ocr / indexing 使用 0–99；completed 固定为 100；failed 使用 0–99，保留失败前最后合法进度。除进入 completed 时设为 100 外，只有 parsing / ocr / indexing 可推进进度。failed 为终止状态，不能继续递增；本 Schema 校验单条快照，不证明跨快照进度推进是否合法，也不定义重试和状态迁移服务。

所有非 failed 状态的 error_code 与 error_message 均显式为 null；failed 时 error_code 必须来自下表，error_message 为非空文本，不能使用 null、空字符串或纯空白。Schema 对以上静态条件施加约束。

规则原文：status 为 failed 时 error_code 与 error_message 两项都必填；progress 只在 parsing / ocr / indexing 阶段推进，completed 必须为 100，failed 不许写 100。

### v1.1 统一错误封装与稳定编码表

规则原文：统一错误封装（全 API 通用）：错误响应体固定为 {error_code, message, details} 三项，error_code 用稳定的字符串编码（与 ParseStatus.error_code 共用同一编码表，编码表写进 CONTRACTS.md），details 为可选对象，不许在错误体里塞业务记录。

Schema 引用为 [parse-status.v1.1.schema.json#/$defs/api_error](parse-status.v1.1.schema.json#/$defs/api_error)。这只是 ParseStatus 文件中可独立引用的 HTTP 错误定义，不是第五个新增记录，也不能当 ParseStatus 成功响应返回。错误对象只有 error_code、message、details 三个键，无 schema_version 或业务字段，禁止额外键。

为保持全字段必填和固定三键的口径，“details 可选”表示内容可以没有：键仍必填，无详情时填 null。存在详情时是诊断对象，键使用英文小写字母开头的下划线命名，值只允许字符串、数值、布尔值或 null；禁止数组及嵌套对象，因此不能放入 PaperMeta、Chunk、ChartOutput 等业务记录。禁止用字符串序列化业务记录规避该规则。message 为非空文本，error_code 与 ParseStatus 共同引用 `#/$defs/error_code` 的同一枚举定义。

| error_code | 固定含义 |
| --- | --- |
| VALIDATION_ERROR | 请求或契约结构不合法 |
| PAPER_NOT_FOUND | 指定论文记录不存在 |
| UNSUPPORTED_FILE_TYPE | 文件类型不支持 |
| FILE_TOO_LARGE | 文件超过允许大小 |
| PARSE_FAILED | 文档解析失败 |
| OCR_FAILED | OCR 识别失败 |
| INDEXING_FAILED | 索引建立失败 |
| CSV_INVALID | CSV 无法读取或不满足输入要求 |
| CHART_VALIDATION_FAILED | 图表数值或图注校验失败 |
| UPSTREAM_ERROR | 外部依赖服务失败 |
| INTERNAL_ERROR | 未分类的内部失败 |

编码不使用可变自然语言，不与不同含义重复绑定；增改编码也要升版本并登记。非失败 ParseStatus 的 null 不属于错误编码。合成错误响应示例：

```json
{
  "error_code": "OCR_FAILED",
  "message": "合成示例：OCR 未提取到可用文本。",
  "details": null
}
```

### v1.1 新增：ChartOutput（CSV 图表输出）

顶层七项全部必填：schema_version（固定 1.1.0）、chart_id、chart_type、series、image_ref、caption、numeric_checks。chart_type 枚举为 line / bar / scatter / histogram；ChartOutput 是独立记录，不能嵌入或序列化进 QAAnswer.answer。

series 为非空列表，每项有且只有 name（非空系列名）、values（非空数值列表）两个必填字段。image_ref 是非空图表资源引用，不是内嵌图片字节；本单不定义资源服务或导出实现。caption 为非空图注文本。

numeric_checks 为非空校验项列表，每项有且只有 value（数值）、csv_anchor（源 CSV 单元格锚点）、verified（布尔）三个必填字段。csv_anchor 有且只有 csv_ref（非空 CSV 引用）、row_number（整数，表头为第 1 行，数据行从 2 开始）、column_name（非空表头列名）三个必填字段。verified=true 表示已经回溯到对应源 CSV 单元格，false 表示尚未通过回溯，不能依靠模型猜测写 true。

series 每项数值均应有对应检查；caption 中每个数值出现也必须有相同数值、对应源单元格且 verified=true 的检查。相同数值的不同来源须分别留检查。数字包含整数、小数、负数、科学计数法、百分比、中文数词以及文字中的数量表达；百分比必须核对 CSV 原始单位，不能将 0.12 与 12 混作相同数值。false 项可以保留其未验证结果，但对应数字不得写入 caption；不得将未验证数字改写成中文数量规避校验。

Schema 校验字段、枚举、布尔类型及源单元格结构，不能完成自然语言中所有数字的抽取、动态数值对照或读取源 CSV；这些属于后续消费者必须执行的语义检查，本单不实现。全无数字的 caption 不增加额外图注检查项，但 series 中的数值仍须有检查，不能借此省略系列检查。

规则原文：caption 里的每个数字必须在 numeric_checks 里有对应校验项，校验不通过的数字不许写进 caption；ChartOutput 是独立记录，严禁塞进 QAAnswer 的 answer 字段。

### v1.1 示例与验证边界

新增四份示例仅表示合成契约数据，不代表真实去重、解析、图表生成或事实校验已经执行。paper-demo-002 及 chunk-demo-002-p1-001 是测试中构造的新版 PaperMeta/Chunk 标识；沿用 v1 的结构，假定其分块写有 18 个样本及协议修正，不能把这些引用当作仓库已经拥有真实论文。

ChartOutput 示例的 CSV 与图像引用同样是假定资源，未在 fixtures 或其他目录创建文件。verified=true 仅演示字段表达，源数值一致性可用内存合成单元格检查；不构成真实 CSV 回溯成果。Schema 也不能独立证明新版优于旧版、跨快照进度合法或人工裁决历史未被覆盖；必须结合实际来源和保留的历史记录核验。

## v1.2 图谱记录

| 契约 | Schema / example | 顶层字段数（含版本） |
| --- | --- | ---: |
| GraphNode | graph-node.v1.2.schema.json / graph-node.v1.2.example.json | 6 |
| GraphEdge | graph-edge.v1.2.schema.json / graph-edge.v1.2.example.json | 5 |

GraphNode 六项全必填：schema_version=1.2.0、paper_id（引用 PaperMeta.id）、title、year、pagerank、level。title/year 必须与对应 PaperMeta 原值一致，未知仍 null；pagerank 是 [0,1] 数值；level 为 cornerstone / derived / isolated。PageRank 和层级仅对本次所选局域图成立，不表示论文质量或全球影响力。

GraphEdge 五项全必填：schema_version=1.2.0、from_paper_id（引用方）、to_paper_id（被引方）、anchor、status。两端都引用所选 PaperMeta。anchor 复用原 QAAnswer 四字段 Chunk 锚点。status=verified 时必须有非空合法 anchor，且 paper_id 必须为 from_paper_id，必须与该论文真实 CitationLink、ReferenceEntry、Chunk 及目标身份一致；没有正文 CitationLink、但参考文献可唯一对应目标时，anchor=null、status=unverified，不可伪造锚点。这种不可验证边仍展示，但不参与 PageRank、分层或未来方向解决证据。

每个对象全字段必填、additionalProperties=false；嵌套锚点同口径。多次正文引用可以形成多个带不同 anchor 的 GraphEdge；排名只使用去重后的 verified 论文对，不按引用标记次数加权。相同 DOI 多版本或同名目标无法唯一对应时，登记 unresolved_references，不猜连边。原九类记录字段数仍为 14/11/10/6/5/7/6/7/7，必填、类型与 Schema/example 字节均不改变。

两个 example 为合成记录，不是声称已经落盘；GraphNode 示例分值只表达字段，不能单独证明一组 PageRank 总和为一。图谱生成者须结合整组记录检查节点归属、边锚点、概率归一和算法收敛。

## 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| 1.2.0 | 2026-10-24 | 本轮只新增 GraphNode、GraphEdge 的 Schema/example；原九类记录与示例零改动。锚点复用 v1，GraphEdge 用 status/可空 anchor 显式表达不可验证边。综述框架未定义，留待后续单。 |
| 1.1.0 | 2026-10-24 | 只新增 DedupDecision、DiffSummary、ParseStatus、ChartOutput 四类记录及各自示例；v1 五份记录的字段数、必填、类型、Schema 与示例全部零改动。统一错误封装与稳定编码表附在 ParseStatus 的 $defs 内，不新增业务记录。图谱节点/边与综述框架结构不在 v1.1，留待 v1.2。 |
| 1.0.0 | 2026-10-24 | 首次建立五份契约及合成示例；明确物理页码、归一化坐标、引用双向定位、问答证据与数字校验口径。未增加解析状态、图谱节点边、综述、推荐、框架或 CSV 图表的专用结构；这些结构需求在 API 草案登记并由用户转达总指挥。 |
