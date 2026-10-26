# 缺口 E：图谱引用身份解析与真实连边验收

日期：2026-10-26（Asia/Shanghai）。输入均为 **官方 pdf/ 真文件**。

## 实测结论

四篇官方论文从空目录重新走本地 MinerU → 原有契约/锚点门禁 → 落盘 → `GET /api/v1/graph`：**HTTP 200，4 节点、9 条已核验引用位置、4 组去重后的论文关系**。要求的 BERT→Attention、GPT-1→Attention、FlashAttention→Attention 均已出现，另有 **FlashAttention→BERT**。

本次 261 条 ReferenceEntry 中，**4 条参考文献身份匹配到所选论文，257 条未匹配**；后者全部保留 `not_in_selection` 原因。该编码表示当前规则未在这 4 篇中找到候选，不表示已证实它们在全球不存在，也不等同于所有题录字段准确。没有声称 100% 解析。

四条已匹配文献的身份方法都是 `title`（正规化标题精确匹配）。BERT 正文采用作者年份引用，这是 CitationLink 的定位方式，不能与目标身份匹配方法混淆。arxiv、doi、author-year 三种身份方法有自制回归覆盖，本次四篇真实关系未使用这三种方法，不冒充其官方文件命中证据。

前端、全部 contracts/、docs/、prompts/、experiments/、test-records/ 零改动；不调用真实模型或外部身份 API，不需要 Key，官方文件仍被忽略。

## 基线与修复范围

开工 `git pull --ff-only` 输出 `Already up to date.`；工作区干净，分支 `main`，基线：

```text
e3df9a97865b748c5ac174c18a5690097014a40a
```

原实现的问题：

- 多数编号参考文献原文是“作者. 标题. 出处, 年份”，旧解析只识别“作者 (年份). 标题. 出处”，导致身份字段为空。
- BERT 为无编号作者年份式参考文献，旧解析产出 0 条 ReferenceEntry/CitationLink。
- 旧图谱标题匹配要求作者字符串数组与年份全部完全相同；本地 Attention 的 PaperMeta.title、authors、year 缺失，标题实际存在于首面 Chunk。

新增 `reference_identity.py`，在默认解析归一化与图谱构建中使用；同时让显式 GROBID 补充提取 TEI 的 arXiv idno/原文标识。GROBID 的默认接线位置未改，本次官方证据使用 MinerU 默认本地管线，不依赖 GROBID。

## 身份规则与拒绝条件

1. **arxiv**：提取 `arXiv:`、`arxiv.org/abs/`、`arxiv.org/pdf/`、`CoRR, abs/` 中的新旧格式标识；ReferenceEntry 保留版本，匹配时去掉版本后缀。多个已选版本无法唯一定位时不猜目标。
2. **doi**：提取并转为小写裸 DOI，移除 URL/doi 前缀与末尾标点，保留 DOI 内配对括号。DOI/arXiv 同时指向不同论文时记 `conflicting_identity`。
3. **title**：Unicode NFKC、casefold 小写，去掉标点与空白，只做整个标题精确比对，不用模糊分数或模型补标题。年份与作者姓氏有值时辅助排除冲突；缺失则在 `auxiliary_missing` 点名，未伪造年份或作者。
4. **author-year**：标题缺失时的严格末级辅助回退，要求年份及完整、非缩写作者姓名集合一致，而且唯一。只有姓氏、初始字母或同年同作者多篇都不能据此猜连；有非空但不同的标题时也不能用作者年份覆盖冲突。

强标识在目标元数据中缺失属于未知，可继续用精确标题；目标已有不同强标识时禁止用标题覆盖。未知、多候选、辅助字段冲突分别保留 `insufficient_identity`、`ambiguous_identity`、`conflicting_auxiliary` 等原因。

旧 PaperMeta.title 为 null 时，图谱只将摘要之前、首面、短小且无章节路径的**整块文本**作为精确比对候选，保留 `first_page_exact_chunk` 来源及该 Chunk 锚点；不修改 PaperMeta，不把正文某个子串猜成标题。本次 Attention 的依据为首面 `c00002` 的完整 `Attention Is All You Need`。其作者和年份仍缺失，记录明确指出这些辅助信息未知；`year_agrees=false` 在此表示未确认，不是报告了不同年份。

参考文献同时支持编号与无编号作者年份式，保留可识别的跨页小写续段。无编号文献按文末顺序赋号，符合既有 CONTRACTS.md 的口径。正文只在明确出现且唯一对应的作者/年份标记上建 CitationLink；同姓同年歧义、错误第二作者及年份后缀不确认的情形不猜链接。

## 官方输入、独立重跑与数量

本地语料目录：`D:\AI_Workspace\Tasks\scholar-graph\pdf\`。GPT-1 对应真实文件 `language_understanding_paper.pdf`，首面原文标题是 `Improving Language Understanding by Generative Pre-Training`，未用别的论文代替。

| 论文 | 官方文件 | 字节 | 物理页 | Chunk | ReferenceEntry | CitationLink | 解析/发布秒 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Attention | 1706.03762v7.pdf | 2215244 | 15 | 175 | 40 | 69 | 7.367418 |
| BERT | N19-1423.pdf | 786279 | 16 | 277 | 56 | 72 | 7.946834 |
| GPT-1 | language_understanding_paper.pdf | 541036 | 12 | 153 | 71 | 110 | 6.016754 |
| FlashAttention | 2205.14135v2.pdf | 2630825 | 34 | 571 | 94 | 177 | 14.121641 |

四篇状态均为 completed/100，并重新加载逐条通过冻结 Schema/外键/页码/锚点门禁。本地引擎版本：**MinerU 4.0.12、pypdf 6.21.2、FastAPI 0.162.0**。没有使用宿主机既有解析结果或模型 API 补数据。

完整 paper_id 是 `paper-` 加下列 SHA-256；后续表格用论文名引用它：

| 论文 | 原文件 SHA-256 |
| --- | --- |
| Attention | bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697 |
| BERT | 987545ffb087f1ece898142c403a516baeabeb70ce19089397fac6f7db12c3d4 |
| GPT-1 | eb81a65e0856bd38e855e1f1de6ee12e7c3eb92ae05c8270d345a475beb631d0 |
| FlashAttention | ca7f9fda10b90fc05dd291a3accc85e9c1a4a860b99b31928dab03ed3fcb14e4 |

输出目录：`data/graph-identity/1479db32c07f4a7491f1a33566eae440/`，探针创建前不存在。四篇从官方 PDF 依次完整解析，图谱从其真实落盘记录取数；请求与整理响应实测 **0.725033 秒**。完整原文记录及本地接口响应在忽略的 data/，JSON 验收证据另存 tests/reports/。

### 同一批 Chunk 的基线对照

审计从 Git 基线读取旧 normalize/citation_graph 函数，在**本次相同 Chunk 和 PaperMeta** 上重算旧结果，仅作内存投影，不覆写历史记录：

| 项目 | 旧函数投影 | 本次真实重跑 |
| --- | ---: | ---: |
| 节点 | 4 | 4 |
| ReferenceEntry | 205 | 261 |
| 已核验边/引用位置 | 0 | 9 |
| 未匹配原因 | insufficient_identity 204；not_in_selection 1 | not_in_selection 257 |

条目增加 56 来自 BERT，不是为了凑边编造条目。背景中的“7 节点、112 条 insufficient_identity”是另一论文集合，本单不把 4 篇的 261 条与 112 条作解析率降幅比较。

## 真实边清单与引用证据

下表 chunk 后缀拼到**来源论文 paper_id** 后即为完整 chunk_id，例如 BERT 的 `-p0001-c00014`。引用位置均为 PDF 物理页。完整四字段锚点（含原始 section 数组）、逐字正文及文末原文均在 [接口实测 JSON](graph-identity-live.json) 的 `graph.diagnostics.edge_evidence`；未手工美化解析器的章节路径。

| edge_index | 来源 → 目标 | 方法 | 文末参考序号 | 正文物理页 / Chunk 后缀 | 文末物理页 / Chunk 后缀 |
| ---: | --- | --- | ---: | --- | --- |
| 0 | BERT → Attention | title | 46（顺序赋号） | 1 / -p0001-c00014 | 11 / -p0011-c00181 |
| 1 | BERT → Attention | title | 46（顺序赋号） | 3 / -p0003-c00040 | 11 / -p0011-c00181 |
| 2 | BERT → Attention | title | 46（顺序赋号） | 8 / -p0008-c00119 | 11 / -p0011-c00181 |
| 3 | FlashAttention → BERT | title | 22 | 7 / -p0007-c00092 | 12 / -p0012-c00193 |
| 4 | FlashAttention → BERT | title | 22 | 17 / -p0017-c00275 | 12 / -p0012-c00193 |
| 5 | FlashAttention → Attention | title | 82 | 1 / -p0001-c00009 | 15 / -p0015-c00256 |
| 6 | GPT-1 → Attention | title | 62 | 2 / -p0002-c00014 | 11 / -p0011-c00142 |
| 7 | GPT-1 → Attention | title | 62 | 3 / -p0003-c00029 | 11 / -p0011-c00142 |
| 8 | GPT-1 → Attention | title | 62 | 5 / -p0005-c00050 | 11 / -p0011-c00142 |

本次 9 条边全部 verified，未核验边 0。PageRank 仍只按 **4 组不同论文对**计数，不能把 9 处正文位置说成 9 组不同论文关系。

可核对的正文与文末样本（均来自官方 pdf/ 真文件，未由模型撰写）：

- **BERT，物理页 3**：`BERT’s model architecture is a multi-layer bidirectional Transformer encoder based on the original implementation described in Vaswani et al. (2017)`；文末第 46 条含 `2017. Attention is all you need.`。正文的作者年份标记唯一指向该文末条目，再由正规化标题连到 Attention 首面题名。
- **GPT-1，物理页 3**：`In our experiments, we use a multi-layer Transformer decoder [34] for the language model, which is a variant of the transformer [62].`；文末 [62] 题名为 `Attention is all you need`。
- **FlashAttention，物理页 1**：`Transformer models [82] have emerged as the most widely used architecture in applications such as natural language processing and image classification.`；文末 [82] 题名为 `Attention is all you need`。
- **额外关系 FlashAttention→BERT，物理页 7**：`We train a BERT-large [22] model with FlashAttention on Wikipedia.`；文末 [22] 为 Devlin 等作者的 BERT 题名；作者姓氏 chang/devlin/lee/toutanova 也与 BERT 元数据相符，发表年份未知未补造。

## 未解析总数与限制

| 来源 | 参考条目 | 匹配到所选论文 | 未匹配 | arXiv 非空提取 | DOI 非空提取 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Attention | 40 | 0 | 40 | 22 | 0 |
| BERT | 56 | 1 | 55 | 8 | 0 |
| GPT-1 | 71 | 1 | 70 | 16 | 0 |
| FlashAttention | 94 | 2 | 92 | 22 | 1 |
| 合计 | **261** | **4** | **257** | **68** | **1** |

提取到标识不代表其目标论文已入库；没有把 arXiv/DOI 的非空数量当作已核验边数。未匹配条目逐项保留 ref_id、身份字段、尝试方法、文末锚点和原因。解析仍是确定性格式规则，不覆盖所有参考文献体例；标点切句、异常姓名、复杂续段可能不完整，非空字段数量不是准确率。

现有记录不会被自动批量覆写：哈希命中会复用旧论文组。构图可从旧条目对应的真实文末 Chunk 补身份依据，但旧 BERT 若没有 ReferenceEntry/CitationLink，不能凭空获得正文边。本单已在上述新目录完成四篇实际重解析并发布；不把未迁移的其他历史论文组写成已更新。

## 接口附加诊断：契约零改动

路径保持 `GET /api/v1/graph?paper_ids=...`。GraphEdge 仍只有原五字段：schema_version、from_paper_id、to_paper_id、anchor、status，照旧通过 `additionalProperties:false`；未给冻结记录塞额外字段。

新增的是**可选传输诊断**，本接口当前返回，旧调用方可忽略：

- `diagnostics.reference_resolutions`：每条已落盘 ReferenceEntry 一项，含 paper_id/ref_id/reference_number、status、target_paper_id、method（arxiv/doi/title/author-year，未解析为 null）、attempted_methods、identity、evidence、bibliography 和 reason。
- `diagnostics.edge_evidence`：每条 edges 一项，用 `edge_index` 关联；含两端论文 id、正文 anchor、body_quote、citation_number、references（对应上述解析结果）。多条参考文献落到同一正文边时合并其证据，不静默丢失。
- `diagnostics.reference_count`、`resolved_reference_count`、`unresolved_reference_count`：条目总数及已匹配/未匹配数；原 unresolved_references 和 pagerank 保持。

正文锚点必须对应真实 CitationLink、ReferenceEntry 和 Chunk；文末锚点是独立证据，不能冒充正文出现位置。没有正文链接的边仍 anchor=null/status=unverified，不参加排名。最终响应重新计算并核对整组图谱，伪造方法、参考序号、文末证据或锚点均被拒收。

backend/README.md 已同步方法、附加字段和历史数据边界。供用户转达 WorkBuddy：读取每条边的方法/参考来源时，以 `diagnostics.edge_evidence[].edge_index` 关联 `edges`；不要向 GraphEdge 添加字段，也不要把 bibliography 锚点当作正文 anchor。本单没有修改或验收前端。

## 回归、审计与复现

新增 **35 项**参数化测试，覆盖 DOI/arXiv 正规化、编号与作者年份条目、姓名初始字母、标题去标点空白、跨页续段、标识冲突/多版本歧义、作者年份歧义、目标字段缺失、无匹配、真实正文/文末锚点以及篡改图谱附加诊断拒收。单元测试为自制样例，官方真文件证据另列于上表。

```powershell
backend/.venv/Scripts/python.exe tests/run_graph_identity_acceptance.py
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --basetemp data/graph-identity-regression-final --junitxml tests/reports/graph-identity-pytest.xml
backend/.venv/Scripts/python.exe tests/audit_graph_identity_acceptance.py
```

最终全量回归输出原文：

```text
594 passed, 5 skipped in 213.59s (0:03:33)
```

JUnit **599 项，594 通过、5 跳过、0 失败、0 错误**。启用了真实自制扫描件 PaddleOCR 回归；未传 `--run-real-model`，5 项真实 DeepSeek 测试按规则跳过，不计为通过。本单未调用真实模型，不将自制回归冒充官方文件验收。

审计从落盘记录重构接口输出，逐边检查实际 CitationLink、ReferenceEntry、正文与文末 Chunk、目标题名，并核对官方 PDF 哈希、未匹配总数、保护目录差异与忽略规则。审计结果另存 JSON，不能代替真实业务连边成功。

证据：[官方实测 JSON](graph-identity-live.json)、[JUnit](graph-identity-pytest.xml)、[审计 JSON](graph-identity-audit.json)、[重跑脚本](../run_graph_identity_acceptance.py)、[审计脚本](../audit_graph_identity_acceptance.py)。PDF 与完整落盘论文仍在忽略目录，未进 Git、镜像或契约示例。
