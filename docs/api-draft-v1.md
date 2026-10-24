# API 契约草案 v1

日期：2026-10-24。端点前缀 `/api/v1`。数据结构的唯一依据为 [CONTRACTS.md](../contracts/CONTRACTS.md)：五类 1.0.0、四类 1.1.0、两类图谱 1.2.0。模块四保持十一份 Schema 和 example 全部不变，仅定义本单授权的检索/抓取/推荐传输封装。

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

核对结果：初版实际为 **17** 条业务端点，并非早期任务文字所称 16 条。模块一增加去重、差异两个 GET 后共 19 条；模块四完成后落地 16 条、未落地 3 条。OpenAPI/Swagger 基础设施不计入业务端点。以下“后续单号待总指挥分配”表示尚无正式单号，不代替威龙排单。

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
| POST | /papers/{paper_id}/qa | 路径 paper_id；JSON {question}，详见模块二定义 | 200 QAAnswer；无论文 404，坏请求 422 | 模块二已落地；默认词法兜底与原文摘录，真实模型未联调 |
| POST | /compare | JSON {paper_ids, question}，详见模块二定义 | 200 {evidence_table, per_paper, synthesis}，per_paper 每项是 QAAnswer | 模块二已落地；先证据表再综合，新增传输封装经本单授权 |
| GET | /graph | 重复查询参数 paper_ids，1–100 个不同 PaperMeta.id | 200 图谱视图：GraphNode[]、GraphEdge[]、分层、未来方向与诊断，详见模块五 | 模块五已落地，v1.2 图谱部分已定义；只读本地已落盘记录 |
| POST | /reviews | PaperMeta.id 列表、写作要求 | 带证据文字可引用 QAAnswer；综述结构不在本轮 v1.2 图谱部分 | 未落地：综述/写作留待后续单，单号待总指挥分配 |
| POST | /retrieval/search | JSON {question, paper_ids?, page?, page_size?, min_relevance?} | 200 分页 {chunk:Chunk, anchor, relevance, retrieval_method}；模式/空结果原因见响应头 | 模块四已落地：Chroma+BGE-M3 稠密/稀疏混合已实装；未启用或不可用时明确词法兜底 |
| POST | /retrieval/fetch | JSON {title} 或 {reference:ReferenceEntry}，二选一 | 200 单次抓取结果，含真实 PaperMeta、初始/最新 ParseStatus 与统一 error，详见模块四 | 模块四已落地：公开 arXiv Atom/PDF，同步复用模块一 Pipeline；不使用 Key |
| GET | /recommendations | paper_id 种子；as_of_year?；page、page_size | 200 分页 {paper:PaperMeta, score, signals, reasons, missing_signals, scoring_version, as_of_year} | 模块四已落地：复用模块五真实边与 PageRank，公式与来源见下文 |
| POST | /frameworks | PaperMeta.id 列表、目标文本 | 框架结构不在本轮 v1.2 图谱部分 | 未落地：写作辅助留待后续单，单号待总指挥分配 |
| POST | /charts/csv | multipart CSV、列名与绘图要求 | ChartOutput；不得塞进 QAAnswer.answer | 未落地：模块六，只有 v1.1 契约已定义；后续单号待总指挥分配 |
| GET | /papers/{paper_id}/dedup-decision | paper_id **就是 new_paper_id** | 200 DedupDecision；无记录 404 PAPER_NOT_FOUND | 本单已落地；人工裁决优先，保留原系统记录 |
| GET | /papers/{paper_id}/diff-summary | paper_id **就是 new_paper_id** | 200 DiffSummary；无记录 404 PAPER_NOT_FOUND | 本单已落地；与选中裁决取自同一比较记录组 |

## 已定义的传输裁定

### 模块五图谱：v1.2 已定义并落地

请求 `GET /api/v1/graph?paper_ids=paper-a&paper_ids=paper-b`，1–100 个不同 id；缺少参数、超过数量、重复 id 为 422 VALIDATION_ERROR，任一论文不存在为整包 404 PAPER_NOT_FOUND，不丢弃该 id。返回一个所选集合的派生图资源，不是论文列表分页；上限以显式参数校验为准，不截断节点/边。形状：

```text
{
  nodes: GraphNode[],
  edges: GraphEdge[],
  layers: {cornerstone: paper_id[], derived: paper_id[], isolated: paper_id[]},
  future_work: {
    worth_exploring: [{direction_id, topic, source: QAAnswer, resolutions: QAAnswer[]}],
    excluded: [同形状条目],
    unverifiable: [同形状条目],
    checks: [{direction_id, candidate_paper_id, decision, reason}]
  },
  diagnostics: {
    unresolved_references: [{paper_id, ref_id, reason}],
    pagerank: {damping, tolerance, max_iterations, iterations, residual,
               verified_pair_count, uniform_baseline}
  }
}
```

业务记录仅新增 GraphNode/GraphEdge 两类，未来方向 source/resolutions 的事实证据复用原 QAAnswer；分组、诊断与处理状态是本端点传输约定，不新造综述或第三份图谱业务契约。nodes 按 paper_id 排序，分层列表按 PageRank 降序、id 升序；结果不依赖请求排列。

引用方向为“引用方 → 被引方”。ReferenceEntry 按裸 DOI、arXiv 去版本基号、最后才按标题+年份+作者的完整一致来唯一对应所选论文；已有 DOI 但不匹配时不回退标题猜边。目标不在所选集合、身份不足或多版本无法唯一对应均登记 unresolved_references。可对应目标却没有 CitationLink 的边为 anchor=null、status=unverified（不可验证）；有引用的 anchor 四字段须与真实 Chunk 及 CitationLink/ReferenceEntry 一致。多次引用保留不同 Chunk 锚点；PageRank 只对 verified 的去重论文对计单位边权。

PageRank 使用阻尼 0.85、均匀初值与跳转，悬挂节点质量均匀回流，L1 残差≤1e-12 为收敛，最多1000轮；未收敛返回 INDEXING_FAILED，不伪造分数。层级规则：无 verified 入/出边为 isolated；其余节点中有 verified 入边且分值>1/N+1e-12 为 cornerstone；其他为 derived。1/N 是所选图均匀基线，不是论文质量阈值；基石只表示本局域图的相对被引中心性。

未来方向为保守摘录：仅识别独立行 `Future work: 主题`、`Future direction: 主题`、`未来工作：主题`、`未来方向：主题`，每条原文≤600字符；同一论文相同主题去重。更晚论文必须有独立行 `Resolved future direction: 同主题`、`We resolved the previously open direction: 同主题` 或 `已解决的未来方向：同主题`，主题按大小写/空白/末尾句号归一后完全相同，年份严格更晚，且该解决声明所在 Chunk 必须有 verified 引用指向原论文，才能移入 excluded。source 与每个 resolution 都带真实 QAAnswer 锚点，checks 保留接受/拒绝原因。

未发现满足条件的证据时仅保留“在所选论文中尚未证实已解决”的 worth_exploring，不宣称全球未解决。原年份未知或匹配解决声明的时间无法比较时移入 unverifiable，不能当作已解决或确定未解决。同年/更早、计划、否定、仅部分词匹配、无锚点边、借用另一个 Chunk 的引用均不能排除。该规则是对作者明确声明及引用归属的本地核对，不是独立科学复现实验；普通叙述和语义改写会漏提取。未使用向量库、真实大模型或外部检索。

### 模块二问答与跨篇对比：已定义

单篇请求为 JSON `{"question":"本文样本量是多少？"}`，只允许 question 字段；去两端空白后长度 1–2000，必须是字符串。论文 id 引用 PaperMeta.id。响应直接为冻结 v1 QAAnswer，不套分页。保留 schema_version=1.0.0，refused 仍为布尔；错问纠错和无依据拒答都为 true，不引入实验报告建议的三态字段。

本单检索为词法兜底、向量检索待后续单。只读该论文已经落盘、通过校验的 Chunk；按中英文有限别名、关键词覆盖与长度归一得分排序，最多候选 8 句，最多返回 4 个不同 Chunk 的证据。每句为同一个 Chunk 中不超过 600 字符的连续原文；超长句跳过，不跨块拼接。该模式是保守摘录，不承诺任意问法或语义推理召回。非中性陈述、带数值前提、why/为什么、因果/颠倒式问题拒绝作肯定回答；有合适原文时附纠错依据。无法判断是否成立也拒答，不把检索未命中写成“全文未报告”。

answer 的每个事实块固定为 `【证据 A】\n原文`，按顺序一一对应 anchors 中的四字段对象；不得把 chunk_id 字符串冒充锚点。锚点必须属于本次检索集合，paper_id、物理 page_number、section 对应 section_path、chunk_id 必须与真实记录匹配。返回前校验 QAAnswer Schema、原文子串、锚点与数字。numeric_fact_check 的 passed 只说明该数字连同上下文逐字回溯到证据，不证明实验真实性、计算结论或不同指标可比性；每项 passed 有 evidence，且它们属于顶层 anchors。缺失所需数值为 unverifiable，明确同项样本数冲突为 failed；没有数字事实为 not_applicable。无依据时 HTTP 200、refused=true；无论文仍为 404 PAPER_NOT_FOUND。

跨篇请求为 JSON `{"paper_ids":["paper-a","paper-b"],"question":"样本量分别是多少？"}`，只允许这两个字段。paper_ids 为 2–10 个不同 PaperMeta.id，保留请求顺序。任何论文不存在则整个请求 404，不返回部分结果；重复、数量越界、空问题或额外字段为 422 VALIDATION_ERROR。

旧草案只写 QAAnswer，没有 per_paper/综合的可执行封装。本单按用户明确授权定义以下 HTTP 传输结构，未新增业务记录或修改九份 Schema：

```text
{
  evidence_table: [
    {evidence_id: "E1", per_paper_index: 0,
     anchor: {paper_id, page_number, section, chunk_id}, quotes: ["连续原文"]}
  ],
  per_paper: [QAAnswer, QAAnswer],
  synthesis: "原文并列：连续原文 [E1]\n不可验证：……"
}
```

evidence_table 一行一个 Chunk，当前每行 quotes 恰好一个原文摘录；evidence_id 按行连续 E1、E2……，per_paper_index 为从 0 开始的请求顺序。per_paper 每篇恰好一个完整 QAAnswer，无额外包装或新增字段；即使拒答也保留该位置。每行 anchor 必须出现在该 per_paper 的 anchors 中，quote 必须出现在对应 answer，拒答原因保留在原记录中。

执行顺序为：逐篇生成并校验 → 构建去重证据表 → 综合 → 再次校验整包。综合中的论文事实仅并列复制已校验 quote，每条末尾 `[E编号]` 回指证据表及 per_paper 锚点，不生成跨指标优劣或因果推断。缺少证据/部分拒答时，综合明确标“不可验证”；不以缺席证据断言论文没做某事。最终键顺序也为 evidence_table、per_paper、synthesis，但程序顺序及引用校验才是证据先行的保证。

模型实际方式：默认 extractive 为本地确定性摘录，无模型名、无外部调用。显式配置环境变量 SCHOLAR_GRAPH_QA_MODE=deepseek、DEEPSEEK_MODEL、DEEPSEEK_API_KEY 时，httpx 调 DeepSeek /chat/completions，仅选已校验候选下标，不采信自由生成事实；坏下标/输出未过门禁不返回答案。真实模型调用尚未验证，Mock 只证明协议及门禁。Key 仅来自本地环境变量，不进入请求参数、业务记录、测试证据或日志；不得提交 .env。

### 模块四检索、公开抓取与推荐：已定义并落地

本单对草案原来未裁定的三项传输形状作如下明确裁定，不新增业务记录、不改十一份契约。`/retrieval/search` 返回真实 Chunk 证据，替代旧草案的 PaperMeta 搜索占位；`/retrieval/fetch` 是一次抓取操作，不是论文列表；推荐是 PaperMeta 加可复核理由的分页传输封装。模块二问答当前仍保留其原词法取证方式，本单没有改变其检索器或调用真实大模型。

**搜索请求与空结果。** question 为去首尾空白后 1–2000 字符；paper_ids 可省略（全部已解析落盘论文），指定时为 1–100 个不同 id；缺失论文整包 404 PAPER_NOT_FOUND。page 默认1、page_size 默认20且上限100，放在 JSON 中；min_relevance 默认0，范围0–1。成功返回固定六字段分页壳，每项 `{chunk: Chunk, anchor: {paper_id, page_number, section, chunk_id}, relevance, retrieval_method}`，relevance 是排序分值，不是正确性概率。锚点 section 为 Chunk.section_path，四字段必须与落盘 Chunk 一致。返回前再次过 Schema/锚点门禁。

响应头 `X-ScholarGraph-Search-Mode` 为 lexical 或 bge_m3_hybrid；`X-ScholarGraph-Vector-Status` 为 NOT_ENABLED、READY 或 UNAVAILABLE；`X-ScholarGraph-Search-Reason` 为 OK、EMPTY_CORPUS、NO_MATCHING_CHUNKS 或 PAGE_OUT_OF_RANGE。空结果返回空 items 与实际 total，不编造证据；后者为分页越界的空页。上述头允许两个本地开发 Origin 的浏览器读取，不改变同源代理。

**实际检索方式。** Chroma 1.5.9 + FlagEmbedding 1.4.2 + torch 2.14.1+cpu + transformers 5.20.2，BAAI/bge-m3 固定快照 `5617a9f61b028005a4858fdac845db406aefb181`。本地 CPU 实际编码/索引已实装并验证，不使用远程 Embedding API。Chroma 保存 1024 维 dense、文本、来源 id、指纹和模型 lexical_weights；稀疏分数为 BGE-M3 真实 token 权重的点积，不把词法或 BM25 冒充模型稀疏编码。稠密分数为余弦相似度，分别降序取名次后融合：

```text
relevance = 0.5 * 61/(60 + dense_rank) + 0.5 * 61/(60 + sparse_rank)
```

名次从1开始，稀疏点积≤0时该项贡献0；同分按 chunk_id 升序。仅查询本次实际论文集合的 id，过期索引行不能返回。实测4个自制 Chunk、1024维；第二次子集检索复用既存向量。编码 batch=1、float32、CPU2线程、最多512 tokens，长块尾部会截断；此限制明确存在，不声称覆盖8192 tokens或完成真实语料质量评测。每请求独立 worker、240秒上限，索引按指纹增量更新。默认 lexical，显式设置 SCHOLAR_GRAPH_RETRIEVAL_MODE=bge_m3_hybrid 及本地 Python/模型路径启用；依赖、模型、超时或 worker 失败明确标 UNAVAILABLE 并词法回退。词法使用本地 token 集合的 IDF 加权余弦，不调用向量库。语义检索即使词面无交集也可能返回真实 Chunk，需 min_relevance 过滤；分值不能替代回答所需的事实核验。

**arXiv 抓取。** POST JSON `{title}` 或 `{reference: ReferenceEntry}` 严格二选一；reference 必须是完整冻结记录。优先按参考文献 arxiv_id 精确查公开 Atom API；其次裸 DOI；否则标题归一后完全匹配，只接受唯一结果，拒绝用相似标题冒充。只允许 HTTPS arxiv.org/export.arxiv.org，跨域重定向拒绝；连续请求至少间隔3秒，不使用 Key。Atom 上限1MiB，PDF 上限50MiB；年份用 published，未提供的信息保持 null/空列表。

一次操作固定 HTTP200 `{succeeded, metadata, paper, initial_parse_status, parse_status, error}`。metadata 是公开接口真实 PaperMeta，id 为 arxiv-基号及版本，文件信息尚未取得时为 null，先原子保存到本地 catalog/；paper 为成功通过模块一 Pipeline 的 PaperMeta，id 为实际 PDF SHA-256 派生 id，不把两个身份混淆。已解析论文通过既有 /papers 与子资源端点读取；catalog 元数据不冒充已解析论文列表。抓取和解析同步等待，初始状态确为既有 ParseJob 的 queued/0，随后使用同一 MinerU/PaddleOCR、状态机、门禁、原子发布和去重路径，成功保留真实文件身份与页数。相同字节已有不可变记录且元数据冲突时会明确失败，不覆盖旧记录。

无匹配、公开接口失败、PDF 下载失败或解析失败时 succeeded=false，error 为 `{error_code,message,details}`（编码沿用 v1.1），paper=null；metadata 仅在真实获取后保留。未拿到 PDF 字节时 initial_parse_status/parse_status 为 null，不虚构排队；解析已启动失败则返回实际 queued 与 failed 快照。error 内不塞业务记录，metadata/paper 在外层。请求本身非法使用HTTP422三字段统一错误。GROBID 仍待验证，本单不声称已联调。

**推荐输入与评分。** GET paper_id 为种子且必须已落盘；as_of_year 可设1–9999，默认当前UTC年份，并逐项回显用于重现；page/page_size 与统一分页一致。候选仅为本地已解析且非种子的论文，不冒充全网推荐。每项固定含 paper、score、signals、reasons（每项 signal/text/evidence）、missing_signals、scoring_version=module-four-v1、as_of_year；不新增业务 Schema。无候选返回空表，响应头 `X-ScholarGraph-Recommendation-Reason=NO_CANDIDATES`；其他为 OK/PAGE_OUT_OF_RANGE。

含金量评分公式原文：

```text
score = 100 * (0.40*G + 0.35*P + 0.15*T + 0.10*C); missing terms contribute 0, without reweighting
```

| 项 | 权重 | 定义与真实数据来源 | 缺失口径 |
| --- | ---: | --- | --- |
| G / graph_neighbor | 0.40 | 候选与种子在本地已解析集合中存在任一方向 verified 引用边为1，否则0；复用模块五 CitationLink/ReferenceEntry 匹配，理由保留 GraphEdge 与真实 Chunk 锚点 | 无 verified 邻接为已知本地图无此信号，不推断全球无关系；unverified 边不计分 |
| P / pagerank_normalized | 0.35 | 复用模块五同一算法/参数，所有本地已解析论文构图（含种子与孤立节点），候选PR/该图最大PR；理由给节点、scope_size、max_pagerank | 已解析节点均参与，孤立节点仍有真实PR；不是全球引文数 |
| T / recency | 0.15 | max(0,1-(as_of_year-PaperMeta.year)/10)；发表时间取真实 PaperMeta.year | 年份未知或晚于as_of_year为null并记 missing_signals，不给虚构时间分 |
| C / github_link | 0.10 | PaperMeta.abstract/source 中真实出现的 https://github.com/owner/repo 链接为1；理由附元数据字段与原链接 | 未发现为null并记缺失；仅确认元数据带代码仓链接，未核仓可访问性或开源许可证，不能断言开源 |

缺失项按0贡献，不重新分配权重。按score降序、paper_id升序。所有证据来自当前落盘快照；arXiv不提供引用计数，公式完全没有引用计数。权重是本单显式可复核的启发式排序，未以用户数据训练或完成推荐质量评估。

参考：[BGE-M3 官方模型](https://huggingface.co/BAAI/bge-m3)、[Chroma 官方客户端](https://docs.trychroma.com/reference/python/client)、[arXiv 公共 API](https://info.arxiv.org/help/api/user-manual.html)。

### 分页封装：已定义

所有列表类端点统一响应 `{items, page, page_size, total, total_pages, has_next}`。items 内的业务记录字段保持原形，搜索/推荐项仅在外层增加本单授权的传输信息。page 默认 1，page_size 默认 20；两者必须为正整数，否则 422 VALIDATION_ERROR。page_size 超过 100 按 100 计，响应回显实际值；total 是筛选后的总条数，total_pages = ceil(total / page_size)，has_next = page < total_pages。空集合 total_pages 为 0；越界页返回空 items，保留请求 page。论文列表按 paper_id 稳定排序，子资源保留落盘顺序；搜索按相关度降序/chunk_id升序，推荐按分数降序/paper_id升序。详情、状态、裁决和摘要直接返回记录，不套分页壳。未来未落地列表亦须遵循此封装，未声称其已实现。

### 批量上传部分失败：已定义

`POST /papers/batch` 响应一律 HTTP 200，固定 `{succeeded, failed, succeeded_count, failed_count}`。succeeded 每项为 `{paper_id, parse_status}`，parse_status 是真实初始 ParseStatus（queued/0），不是查询时的最新状态。failed 每项为 `{filename, error_code, error_message}`；error_code 使用 v1.1 的 11 码之一。每个文件恰好进入一个结果集合，各集合保持输入中的相对顺序；失败后继续处理后续文件，不静默丢弃。

本轮按文件顺序同步等待本地解析完成，没有异步队列。返回后 GET parse-status 可已为 completed；失败的 PDF 如已经建立状态，也可按其文件 SHA-256 对应 paper_id 查询 failed。扩展名错误或过大文件在管线接收前拒绝，不虚构其排队记录。空列表返回两个空集合及 0/0；无法解析 multipart 时用 filename=`(request)` 的 VALIDATION_ERROR 记录请求级失败；非 files 字段逐项记 VALIDATION_ERROR，无文件名用 `(unnamed)`。批量结果是传输封装，不是统一错误体。

### 单资源、关联键与错误

去重、差异路径中的 id 一律为新版 PaperMeta.id，不接受旧版键冒充新版。无记录返回 404，统一错误体固定 `{error_code, message, details}`，error_code=PAPER_NOT_FOUND，message 明确“无该新版论文的去重记录。”或“无该新版论文的差异记录。”；不返回空记录。存在 human_override=true 时原样返回人工记录，保留系统建议；后续系统记录不会压掉人工意见。

全 API 错误引用 ParseStatus 的 `#/$defs/api_error`；无诊断时 details=null，不塞业务记录。单上传不合法请求 422、非 PDF 415、超过 50 MiB 413、解析/OCR 失败 422、上游错误 502、未知内部错误 500。未知端点 404 也用三字段体。管线状态机、物理页码、裸 DOI、输出 Schema 与锚点门禁沿用上一单。GROBID 状态为**待验证**，HTTP 默认管线只走本地 MinerU 与 PaddleOCR；现有可配置 GROBID 客户端仅有 Mock 证据，不是实际联调。

## 交给总指挥的契约缺口

本栏登记截至 v1.2 图谱部分的契约及已授权传输裁定。模块四保持全部十一份 Schema 零修改；/retrieval/search、/retrieval/fetch、/recommendations 传输封装已定义并落地；其余实现状态以上表为准。未落地仅 /reviews（综述/写作）、/frameworks（写作框架）、/charts/csv（模块六），后续单号均待总指挥分配。

| 缺口 | 状态 | 契约引用与边界 |
| --- | --- | --- |
| A：去重裁决 | v1.1 已定义 | [DedupDecision](../contracts/dedup-decision.v1.1.schema.json)；人工意见另存记录，原系统建议原样保留 |
| B：版本差异摘要 | v1.1 已定义 | [DiffSummary](../contracts/diff-summary.v1.1.schema.json)；无锚点关键句必须标 unverified，空变化章节须写“未检出章节级差异” |
| C：解析状态与统一错误封装 | v1.1 已定义 | [ParseStatus](../contracts/parse-status.v1.1.schema.json)；`/papers/{id}/parse-status` 返回 ParseStatus，其中 id 即端点表中的 paper_id，引用 PaperMeta.id；全 API 错误响应引用同文件 `#/$defs/api_error`，错误码与 ParseStatus 共用编码表 |
| CSV 图表输出 | v1.1 已定义 | [ChartOutput](../contracts/chart-output.v1.1.schema.json)；`/charts/csv` 的图表业务响应引用 ChartOutput，严禁塞进 QAAnswer.answer，图注数字必须通过 CSV 回溯检查 |
| 分页封装 | 已定义 | 本轮授权固定六字段传输壳，见“已定义的传输裁定”；不增加业务字段 |
| 批量上传部分失败 | 已定义 | 本轮授权固定四字段传输壳，逐文件记录成功或失败；同步处理，见上文 |
| 图谱结构 | v1.2 已定义，/graph 已落地 | GraphNode、GraphEdge；节点/边均对应落盘记录，未知锚点显式 unverified；形状见模块五，不返回图形库专用对象 |
| 综述框架结构 | 不在本轮 v1.2 图谱部分，留待后续单 | 本单不定义结构化综述章节、独立框架或导出结构；QAAnswer 的带证据文字不替代这些结构 |

异步任务队列与标识仍未定义；后续范围由总指挥另行拆单。推荐分数与理由、同步抓取操作及失败结构已由模块四授权定义，见上文；它们不代表异步任务契约。分页和 PDF 批量部分失败继续沿用已定义封装，不据此扩展未裁定业务字段。

WorkBuddy 的前端、其他文档和跑测、DeepSeek Harness 的 Prompt 实验由总指挥另行拆单，协作与变更请求通过用户中转，不直接联系其他工具。本轮没有验证前端与这些 API 的对接。
