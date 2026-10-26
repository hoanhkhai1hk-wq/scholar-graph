# GROBID 转换容错修复验收（C-补）

日期：2026-10-26（Asia/Shanghai）。输入为 **官方 pdf/ 真文件**，不是自制 PDF 或公开替代件。

## 结论

**显式 GROBID 补充路径已修通并发布成功；默认 HTTP 上传及 arXiv 抓取仍未启用 GROBID。** 没有放宽契约，没有绕过发布前校验。

使用真实 `grobid/grobid:0.9.1-crf` 服务，对官方 Attention v7 全文重新解析、转换、校验及落盘：发布 **1 组论文记录**，包含 **1 PaperMeta、175 Chunk、40 ReferenceEntry、69 CitationLink**。状态为 `completed/100`，四类记录 Schema、外键及 Chunk 锚点校验通过，重新加载与内存输出相同。

第 1 条参考文献的标题和出处各有 **1 项**从空字符串归一为 `null`，涉及同一条文献。`persName` 姓名分量间距也已修复。CRF 原有作者/机构实体误识别仍存在，不把“转换可发布”解释成“所有题录均准确”。

全量回归：**564 项，559 通过、5 跳过、0 失败、0 错误**。5 项真实模型测试未启用，跳过不计为通过。未调用模型 API，未使用、保存或打印 Key。

## 开工基线与改动

开工 `git pull --ff-only` 原文为 `Already up to date.`；工作区干净，分支为 `main`。基线完整哈希：

```text
a3725bfed43fedf13be9fb7597749e72f9a7a9f7
```

转换修复提交：`c307fa92fbafd1d973c04ed687fcb8dbaa224341`。实测在该修复工作树上运行，实测 JSON 的 `revision` 记录的是提交前 HEAD 基线，不把它误写成已包含修复的提交。

- `backend/scholar_graph/grobid.py:text()`：不存在、空白、空元素和无文本的嵌套节点统一返回 `None`，序列化后为 JSON `null`。非空文本仍按原规则折叠空白；通用行内文本不插入额外空格，例如 `Ti<hi>k</hi>Z` 仍为 `TikZ`。
- 新增 `person_name()`，只在姓名直接子分量之间加入间隔，同时保留直接文本、尾随文本和分量内部的行内标记，修复相邻 `<forename>/<surname>` 的连写。空姓名不加入作者数组。
- 保持原有回退行为：参考文献 analytic 标题为空时仍可取 monograph 标题；GROBID header 缺少题名时保留本地 PaperMeta 原值。不从 `report_type` 或原始条文猜补标题。
- 增补空节点、姓名、中间名、连字符/Unicode、混合内容、行内文本、标题回退和真实发布门禁测试；原测试中“空 title 必须导致失败”的预期改为合法 `null` 后可发布。直接给冻结契约传 `""` 的拒收测试仍保留。
- **contracts/ 全目录与前端等保护目录相对开工基线零改动**。旧 GROBID 失败报告和 JSON 保留，未覆盖。

## 官方真文件与服务身份

输入：`D:\AI_Workspace\Tasks\scholar-graph\pdf\1706.03762v7.pdf`，**2,215,244 字节、15 个 PDF 物理页**。

SHA-256：

```text
bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697
```

服务为 Docker Linux Engine **29.9.2** 上的 `scholar-graph-grobid-grobid-1`，镜像 **`grobid/grobid:0.9.1-crf`**，不是 full/DL 模式。实际 RepoDigest：

```text
grobid/grobid@sha256:223957791ac2bbe48609dcc58a689b16b60baeae13a8734ef440ae6bfb38f4cd
```

服务实测返回：

```text
GET /api/isalive  -> 200 true
GET /api/version  -> 200 {"version":"0.9.1","revision":"0.9.1"}
POST /api/processFulltextDocument -> 200
```

全文请求由生产 `GrobidClient.enrich()` 发出，multipart 原始 PDF，不设 start/end，不使用演示站点；客户端关闭 Header/Citations consolidation，不调用 Crossref 补全。探针的传输封装只观察真实请求与响应，没有替换 TEI。

## 全文重跑与发布结果

本次新建两个空输出目录，分别跑 MinerU 基线与显式注入 GROBID 的 Pipeline，没有复用既有业务记录：

```text
data/grobid-conversion-fix/8dc9ac2680d645469a26c5dc6eb4b0c9/mineru-only/
data/grobid-conversion-fix/8dc9ac2680d645469a26c5dc6eb4b0c9/with-grobid/
```

MinerU-only 是对照组，**不把它另算作 GROBID 发布论文组**。以下发布数只统计 `with-grobid/papers/`。

| 指标 | 修复前历史结果 | 本次修复后官方真文件结果 |
| --- | --- | --- |
| 论文组 | 0 | **1** |
| 解析状态 | failed，进度 80，VALIDATION_ERROR | **completed，进度 100，错误字段均 null** |
| PaperMeta / Chunk / ReferenceEntry / CitationLink | 未发布 | **1 / 175 / 40 / 69** |
| ReferenceEntry #1 title / venue | `""` / `""`，契约拒收 | **null / null，原契约接受** |
| 完整 Pipeline 耗时 | 历史失败 8.691425 秒 | **9.680789 秒**，含解析、服务请求、校验与重新加载 |
| GROBID HTTP 请求耗时 | 历史失败轮次 1.904619 秒 | **2.454602 秒**，已运行的服务，非冷启动耗时 |

本次独立 MinerU-only 基线耗时 **6.952990 秒**。这些时间来自不同运行，不能简单相减当作 GROBID 净开销。

175 个 Chunk 与本次 MinerU 基线**逐条完全相同**：text 166、figure 5、table 4、formula 0；175 条有 bbox，非空章节路径去重 29 个。GROBID 没有替换 Chunk、物理页或 bbox。ReferenceEntry 40 条中标题/作者/年份/出处/DOI 非空覆盖数为 **39/39/40/39/0**；非空覆盖率不等于准确率。

保留的完整原始响应为本地 `grobid-response.tei.xml`，**80,698 字节**，SHA-256：

```text
55dc0a7a1a927d20af2b97a0b9b3e537023da6194909d44b5d862b282c4a0b1d
```

本次响应使用生产客户端参数，先前字段对照探针另加了 raw/坐标等参数，响应大小不同；未把两份 TEI 当作同一响应。完整 TEI、四类业务记录仍在 ignored data/，PDF 仍在 ignored pdf/，均未进 Git。

## 空值与作者间距核查

对本次 TEI 用旧 `text()` 行为与修复后的实际发布记录逐条比较：

| 归一项 | 条目数 | 对应文献 |
| --- | --- | --- |
| title 空字符串 → null | **1** | ReferenceEntry #1 |
| venue 空字符串 → null | **1** | ReferenceEntry #1 |
| 至少一个上述字段变化的文献 | **1** | 同一条，不重复计算 |

该条实际发布数据节选：

```json
{
  "number": 1,
  "authors": ["Jimmy Lei Ba", "Jamie Ryan Kiros", "Geoffrey E Hinton"],
  "year": 2016,
  "title": null,
  "venue": null,
  "doi": null,
  "arxiv_id": null
}
```

这里只展示字段节选；真实落盘记录保留全部必填字段，并通过冻结 ReferenceEntry Schema。GROBID 将该题名放在 report_type，不能因为原始条文可读就伪称 title 已恢复。

全 TEI 核查 **165 个非空 author/persName 出现位置，其中 159 个字符串因分量间距而变化**。这是出现位置数，包含重复姓名与被 CRF 误分类的机构，不是 165 位独立作者，也不是 159 处实体识别修正。

| 旧拼接 | 修复后实际值 |
| --- | --- |
| AshishVaswani | Ashish Vaswani |
| AidanNGomez | Aidan N Gomez |
| ŁukaszKaiser | Łukasz Kaiser |
| JimmyLei Ba | Jimmy Lei Ba |
| JamieRyan Kiros | Jamie Ryan Kiros |
| GeoffreyEHinton | Geoffrey E Hinton |

剩余影响：PaperMeta 仍有 **10 个作者值**，其中 Google Brain、Google Research 是 CRF 误识别的机构；**2 个机构值**之一混有工作说明/会议信息；摘要仍混有脚注。这些是上游实体与版面识别问题，空值及间距修复不能解决，本单没有按论文常识人工改写数据。标题 `Attention Is All You Need` 已按实际 TEI 发布。

## 最终接线位置与文档修正句

最终位置为 **显式补充路径**，不是默认 HTTP/arXiv 融合解析：

1. `backend/scholar_graph/cli.py` 的 `parse --grobid-url` 或 CLI 读取 `GROBID_URL` 后构造客户端；也可由调用方显式注入 `Pipeline(grobid=...)`。
2. `pipeline.py` 在 MinerU/必要时 OCR 之后，仅当 `self.grobid is not None` 时执行补充，再走相同 Schema、锚点和发布门禁。
3. GROBID 实际补充 PaperMeta 的题名、作者、机构、摘要、年份、DOI（有值才覆盖）及 ReferenceEntry，随后按保留的 Chunk 引用编号重建 CitationLink。正文/表格/公式 TEI 不替代 MinerU Chunk。
4. `api_uploads.py` 默认工厂没有注入 GROBID；`arxiv_fetch.py` 默认只注入元数据补充，也没有 GROBID。审计实际设置 GROBID_URL 后实例化两种工厂，二者 `.grobid` 都为 `None`；仅设置该变量不会让这两条默认 HTTP 路径启用 GROBID。

后端和 services README 已同步当前结论，docs/ 未改。供文档补丁单使用的修正句：

> 默认 PDF 文本与版式解析使用本地 MinerU，扫描页由 PaddleOCR 兜底。GROBID 0.9.1-crf 作为显式 CLI/Pipeline 题录与参考文献补充，已通过官方 Attention v7 的原有契约校验并发布 1 组论文记录；默认 HTTP 上传及 arXiv 抓取仍未启用。其作者/机构实体识别仍有误差，Chunk、物理页与 bbox 锚点仍由 MinerU 负责；本单未验证 DeepSeek-OCR。

## 回归、审计与复现

本单新增 12 项参数化回归用例，另修正 1 项旧发布测试的预期。定向测试输出：`34 passed, 1 skipped in 8.91s`（该轮未启用 OCR）。回归输入是自制 TEI/PDF，不冒充官方文件实测；上面的官方真文件全文证据另列。

```powershell
docker compose -f services/docker-compose.grobid.yml -p scholar-graph-grobid up -d
backend/.venv/Scripts/python.exe tests/run_grobid_conversion_fix.py
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --basetemp data/grobid-conversion-fix-regression --junitxml tests/reports/grobid-conversion-fix-pytest.xml
backend/.venv/Scripts/python.exe tests/audit_grobid_conversion_fix.py
```

全量回归输出原文：

```text
559 passed, 5 skipped in 189.67s (0:03:09)
```

JUnit 共 **564 项、559 通过、5 跳过、0 失败、0 错误**。启用了真实自制扫描件 PaddleOCR 回归；未传 `--run-real-model`，5 项 DeepSeek 实连测试按规则跳过，未调用真实大模型。

审计重新从本地原始 TEI 转换并与整组实际落盘记录比较，重算 PDF/TEI 哈希、空值与姓名计数，重验冻结 Schema、外键、锚点、Chunk 保留、论文组数、两条默认工厂、保护目录零差异、pdf/ 忽略及 JUnit。审计通过不替代业务发布通过，二者均独立保留证据。

交付证据：

- [真实服务与发布 JSON](grobid-conversion-fix-live.json)
- [全量回归 JUnit](grobid-conversion-fix-pytest.xml)
- [审计 JSON](grobid-conversion-fix-audit.json)
- [新全文重跑探针](../run_grobid_conversion_fix.py)
- [新审计脚本](../audit_grobid_conversion_fix.py)

旧 `grobid-integration-*` 报告与 JSON 原样保留，历史失败没有被重写成成功。契约、前端、docs/、prompts/、experiments/、test-records/ 均未修改。
