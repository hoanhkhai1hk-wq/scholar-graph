# GROBID 容器联调与 MinerU 对照验收

日期：2026-10-26（Asia/Shanghai）。语料为 **官方 pdf/ 真文件**。

## 结论与验收边界

**GROBID 0.9.1-crf 容器服务已实连，完整 TEI 解析与逐字段对照证据已取得；现有可选生产转换未通过。** 两个结论分别记录，不把服务 HTTP 200 写成生产链路已接通。

- `/api/isalive`：HTTP 200，原文 `true`。
- `/api/version`：HTTP 200，原文 `{"version":"0.9.1","revision":"0.9.1"}`。
- 官方 Attention v7 的 `/api/processFulltextDocument`：HTTP 200，最新实测 2.089062 秒（已预热）。标题、作者、机构、摘要、章节、表格、公式、参考文献都有实际 TEI 产出；其中存在误识别，详见下表。
- 同一输入从两个全新目录跑 MinerU 和显式启用 GROBID 的现有 Pipeline。后者被第 1 条 ReferenceEntry 的空字符串 title/venue 拦截，状态 failed、VALIDATION_ERROR、进度 80、发布论文组 **0**。没有跳过校验，没有发布无效业务记录。
- 默认 HTTP 上传与 arXiv 抓取均没有注入 GROBID；本单未改生产实现、契约、前端、技术文档。未调用模型 API、未使用或保存 Key。

[实测 JSON](grobid-integration-live.json) 中 `service_evidence_passed=true`，`production_pipeline_passed=false`；原 `passed` 仍为 false，表示可选管线端到端未通过，未将失败改写成通过。[审计 JSON](grobid-integration-audit.json) 的审计成功也不替代业务成功。

## 基线与语料身份

首次开工 `git pull` 为 `Already up to date.`，主干 `523d07666767c0cafd9f54ed1a5980af3b26176d`；本次恢复后再次 pull 为 `Already up to date.`，主干 `c0e7e361e3b5032c2cb8300b76a59c4885acf4c3`，两次开工工作区均干净。

输入：`D:\AI_Workspace\Tasks\scholar-graph\pdf\1706.03762v7.pdf`，**2,215,244 字节、15 个 PDF 物理页**。SHA-256：

```text
bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697
```

最新完整探针：`2026-10-26T02:41:22.823825+00:00` 至 `2026-10-26T02:41:41.550095+00:00`（北京时间 10:41:22 至 10:41:41）。本地输出目录：`data/grobid-integration/20261026T024122Z-af7ce869/`。`mineru-only/` 和 `mineru-with-grobid/` 均为此次新建，没有复用旧解析记录。

完整 TEI 为该目录下 `attention.tei.xml`，121,852 字节，SHA-256：

```text
6512b0576b4b00b48677e6dc71c763fe265afa5c8542e2c27419764392c79d8a
```

PDF、完整 TEI、模型与业务记录仅保留在被忽略的 pdf/、data/。Git 只包含探针、少量样本、统计和回归证据；没有 COPY PDF 进镜像。

## 服务版本与复现

配置 `services/docker-compose.grobid.yml` 使用官方 **`grobid/grobid:0.9.1-crf`**，linux/amd64、CPU/CRF 模式；不是 full/DL 模式。Docker Desktop 4.96.3，Linux Engine 29.9.2。容器 `scholar-graph-grobid-grobid-1`，仅绑定 `127.0.0.1:8070`，6 GiB 内存上限、core dump 为 0，不传入密钥、环境文件或 PDF 挂载。

实际镜像 RepoDigest：

```text
grobid/grobid@sha256:223957791ac2bbe48609dcc58a689b16b60baeae13a8734ef440ae6bfb38f4cd
```

Docker inspect 返回镜像大小 1,717,306,087 字节。Registry manifest 的压缩层合计：CRF 509,986,678 字节/10 层，full 14,822,914,882 字节/21 层。原 full 下载因体积与本机 CPU 环境改选而停止，没有声称 full 拉取或解析通过；本轮全部字段证据来自 CRF。镜像与模式依据 [GROBID 官方 Docker 文档](https://grobid.readthedocs.io/en/latest/Grobid-docker/) 和 [0.9.1 官方 CRF Dockerfile](https://raw.githubusercontent.com/kermitt2/grobid/0.9.1/Dockerfile.crf)。

在仓库根目录运行：

```powershell
docker compose -f services/docker-compose.grobid.yml -p scholar-graph-grobid config
docker compose --progress quiet -f services/docker-compose.grobid.yml -p scholar-graph-grobid up -d
backend/.venv/Scripts/python.exe tests/run_grobid_acceptance.py
backend/.venv/Scripts/python.exe tests/audit_grobid_acceptance.py
```

`config` 和 `up -d` 均退出 0，容器 running。探针因可选管线失败退出 **1**，但会完整保留已成功的服务证据和失败状态。审计检查证据真实性与守门行为，业务结果另列。

服务 POST 使用 multipart 原始 PDF，全页、不设 start/end；consolidateHeader/Citations/Funders 全为 0，不靠 Crossref 或 Key 补数据。证据调用附 includeRawCitations、includeRawAffiliations、generateIDs 和 TEI 坐标；生产客户端调用仍使用原有参数。参数依据 [官方服务 API](https://grobid.readthedocs.io/en/latest/Grobid-service/)。首个冷请求服务日志为 `duration_ms=15198`；最新预热客户端实测 2.089062 秒，两者测量口径不同，不混作同一耗时。

## 同文件逐字段对照

MinerU **4.0.12**，项目既定本地 `tier=flash, ocr_mode=txt, image_analysis=False`，非视觉模型模式。最新全管线 **6.727363 秒**（引擎 5.594250 秒），completed/100，Schema 与锚点校验通过，发布 **1 PaperMeta /175 Chunk /40 ReferenceEntry /69 CitationLink**。175 Chunk 均有 bbox，类型为 text 166、figure 5、table 4、formula 0。

| 字段/计数口径 | MinerU 真实结果 | GROBID CRF 真实结果 | 强项与明确缺陷 |
| --- | --- | --- | --- |
| 标题 | 原生 doc_title 1，标题 Chunk 有原文；PaperMeta.title=null | titleStmt/title **1**，原文标题正确 | GROBID 已给出结构化题名；MinerU 原文有但本地上传元数据未补齐 |
| 作者 | 首面作者行保留在 Chunk；PaperMeta.authors **0** | header author/persName **10** | 论文实际 8 位作者；GROBID 把 Google Brain、Google Research 多识别为两个人，顺序也不宜当作原文作者次序 |
| 机构 | 原文有 Google Brain、Google Research、University of Toronto；PaperMeta.institutions **0** | affiliation 元素 **10**，去重 orgName **2** | 只有 University of Toronto 是正确的独立机构名；另一个把脚注和会议信息混成机构，Google 两机构落入作者列表；不能说机构字段准确 |
| 摘要 | 有摘要标题/正文 Chunk；PaperMeta.abstract=null | abstract **1** | GROBID 形成独立字段，但包含等贡献说明与工作机构脚注；MinerU 摘要正文 Chunk 更便于单独回溯 |
| 章节 | 原生 paragraph_title **27**；去重非空 section_path **29** | body 下 div/head **25** | GROBID 主体层次较清楚，但末尾有两个 Input-Input Layer5 图中文字误作章节；MinerU 也有邮箱、作者行、公式误作标题，计数不是正确章节数 |
| 表格 | table Chunk **4**，含表1–4的 HTML 行列和 bbox | table figure/table 元素均 **3**，仅表2–4；43行/274个cell | 本例 MinerU 覆盖更全；GROBID 表3部分单元格拆分也需复核。服务日志明确提示3张表格式不完整/异常，不能说三张均准确 |
| 公式 | 原生 equation **7**，7个内容均为空；发布 formula Chunk **0** | formula **13**，有表达式文本和物理页坐标 | GROBID 有公式文本产出；其 TEI 线性文本不是完整 LaTeX，也没有核定13条均为独立、准确公式 |
| 参考文献 | ReferenceEntry **40**；作者/年份/标题/出处/DOI 非空数均 **0**；编号锚点 CitationLink **69** | biblStruct **40**；标题/作者/年份/出处/原始条文非空数为 **39/39/40/39/40**；正文 bibr 标记 **58** | GROBID 结构化文献明显更丰富，但 ref1 的题名被放进 report_type 而非 title，且 venue 空；非空覆盖率不是准确率。58是原生引用标记数，69是拆分后的契约链接数，单位不同 |

GROBID 三张表的逐项统计：表2为11行/43 cell，表3为19行/193 cell，表4为13行/38 cell。这里计 XML row/cell 元素，不把 colspan 展开。正文/表格/公式只作为 TEI 对照证据，未冒充项目 Chunk 已增加相同能力。

## 字段原文样本（官方 pdf/ 真文件）

样本逐项对应 JSON；XML 仅按元素边界加空格便于阅读，未人工纠正 CRF 分类。

- 标题：GROBID `Attention Is All You Need`；MinerU 第1页 `c00002` 同为该原文。
- 作者：GROBID 的10个节点依次为 `Ashish Vaswani; Google Brain; Noam Shazeer; Niki Parmar; Google Research; Jakob Uszkoreit; Llion Jones; Aidan N Gomez; Łukasz Kaiser; Illia Polosukhin`。MinerU 第1页 `c00003` 原文：`Ashish Vaswani ∗ Google Brain avaswani@google.com  Llion Jones ∗  Google Research llion@google.com`，展示了机构为何不能直接当人名。
- 机构：GROBID 两个 orgName 原文为 `University of Toronto` 和 `Work performed while at Google Research. 31st Conference on Neural Information Processing Systems (NIPS 2017)`。MinerU 第1页 `c00004`：`Noam Shazeer ∗  Google Brain noam@google.com  Aidan N. Gomez ∗  † University of Toronto aidan@cs.toronto.edu`。
- 摘要：两者正文均含 `The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism.` GROBID abstract 后面还实际包含 `* Equal contribution. Listing order is random.` 等贡献说明及 `† Work performed while at Google Brain.`；没有将污染脚注剪掉后声称原始结果干净。MinerU 对应第1页 `c00010`。
- 章节：GROBID `Model Architecture; Scaled Dot-Product Attention; Optimizer`，也包含两个 `Input-Input Layer5`；MinerU 对应标题带编号 `3 Model Architecture; 3.2.1 Scaled Dot-Product Attention; 5.3 Optimizer`，其标题列表还混有 `illia.polosukhin@gmail.com`。
- 表格：GROBID 表2原文 `Transformer (big) 28.4 41.8 2.3 • 10 19`，其 XML 含 `<row><cell>Transformer (big)</cell><cell>28.4</cell><cell>41.8</cell><cell>2.3 • 10 19</cell></row>`。MinerU 第6页 `c00066` 为表1，含 `<tr><td>Self-Attention</td><td>O(n<sup>2</sup> · d)</td><td>O(1)</td><td>O(1)</td></tr>`；GROBID table 结构中没有表1。
- 公式：GROBID 首条原文 `Attention(Q, K, V ) = softmax( QK T √ d k )V (1)`，coords 为 `4,219.97,465.65,284.70,25.41`，首项4为物理页；上/下标和分式被线性化，未称其为 LaTeX。MinerU 原生样本 `{"type":"equation","index":6,"bbox":[0.358,0.587,0.825,0.62],"content":""}`，没有可引用的 formula Chunk 文本。
- 参考文献：GROBID ref1 原始条文为 `Jimmy Lei Ba, Jamie Ryan Kiros, and Geoffrey E Hinton. Layer normalization. arXiv preprint arXiv:1607.06450, 2016.`，作者3人、年份2016；但 `<monogr><title/></monogr>` 为空，`Layer normalization. arXiv preprint` 落在 report_type。ref2 题名为 `Neural machine translation by jointly learning to align and translate`，作者 `Dzmitry Bahdanau; Kyunghyun Cho; Yoshua Bengio`，年份2014。MinerU ref1/ref2 的 title/year/venue 为 null、authors=[]，没有拿 GROBID 样本反填到 MinerU 列。

## 可选生产转换失败：精确定位与守门证据

独立服务能解析 PDF，不代表现有项目转换正确。显式 `Pipeline(grobid=...)` 本次运行8.691425秒，实际 GROBID HTTP 调用1.904619秒，之后在发布前失败：

```json
{"status":"failed","progress":80,"error_code":"VALIDATION_ERROR","error_message":"ReferenceEntry 未通过 Schema 校验。"}
```

对客户端的实际转换结果在内存中逐条运行现有验证器，只有以下两项错误：

```json
[
  {"reference_number":1,"path":["title"],"validator":"anyOf","message":"'' is not valid under any of the given schemas"},
  {"reference_number":1,"path":["venue"],"validator":"anyOf","message":"'' is not valid under any of the given schemas"}
]
```

来源是 GROBID 的空 `<title/>`，现有 `grobid.py:text()` 将存在但无文本的节点转成 `""`；`_convert()` 直接用于 title/venue。冻结契约允许 null 或非空字符串，不允许空字符串。**本单只定位，不改转换、不放宽契约，也不把原始条文手工填成标题来制造通过。** 作者 persName 内 token 的现有拼接也有丢空格风险，尚不能将该转换宣称生产可用。

状态真实走到 queued → parsing → indexing → failed；未到 completed，未发布 PaperMeta/Chunk/ReferenceEntry/CitationLink 论文组（0组）。原始 TEI 只保留在 ignored data/，失败项在报告中是诊断信息，不是发布的无效业务记录。

## 生产分工与技术文档替换句

- `backend/scholar_graph/cli.py`：仅 `parse --grobid-url` 或 CLI 的 GROBID_URL 构造 GrobidClient；也支持调用方显式注入 Pipeline。
- `pipeline.py`：MinerU/必要时 OCR 之后，条件 `self.grobid is not None` 才调用 enrich，再过原有校验/发布；哈希已存在会提前复用，因此本探针使用全新记录目录。
- `grobid.py` 的设计职责：补 PaperMeta 标题、作者、机构、摘要、年份、DOI；生成 ReferenceEntry，并按 MinerU Chunk 中引用编号重建 CitationLink；不替换 Chunk、物理页、bbox，不把 GROBID 正文章节/表格/公式转成 Chunk。本次该可选转换实际失败，上述是设计职责，不是已经成功发布字段的承诺。
- `api_uploads.py:UploadService.__init__` 默认只构造 `Pipeline(root, gate=gate)`；`arxiv_fetch.py:ArxivFetcher._pipeline` 只注入元数据补充；两条默认 HTTP 路径都未启用 GROBID，设置 GROBID_URL 不会改变它们。

供用户转给文档补丁单的精确修正句（本单不改 docs/）：

> 默认 PDF 文本与版式解析使用本地 MinerU，扫描页由 PaddleOCR 兜底。GROBID 0.9.1-crf 已完成官方 Attention v7 的容器全文 TEI 解析与逐字段对照，但存在作者/机构误识别；它尚未接入默认 HTTP 上传及 arXiv 抓取，显式 CLI/Pipeline 补充路径也因 ReferenceEntry 空字符串校验失败而未发布记录。因此当前不能宣称经生产验证的“MinerU + GROBID 融合解析基座”。本轮未验证 DeepSeek-OCR。

## 前次失败与本次恢复记录

前次提交 c0e7e36 中 Docker Server 不可用，Desktop 启动因 `docker-secrets-engine/engine.sock` 无法访问失败，保留式重命名返回 Access denied；当时没有取得 GROBID 输出，失败结论保留在 Git 历史。本次用户打开 Docker 后，重新检查已能返回 Linux Server 信息；没有声称本单自动修好了 Docker 系统问题。

恢复后的首轮服务两次返回 HTTP 200，但探针整理 Docker ps 元数据时误用 Windows GBK 解码 UTF-8 省略号而失败。探针现已显式 UTF-8，增加阶段保存点和回归测试；以上主结果来自修正后再次创建空目录的完整重跑。没有把该次报告保存失败当作后端解析实现已修复。

## 回归与审计

新增探针测试现为9项：自制 TEI 的题录/参考作者分开计数、章节与表格 caption 区分、行列计数、缺失结构保持0、3种坏响应拒收、XXE拒收、转换保留Chunk身份、Windows UTF-8子进程输出、无效参考文献发布前拦截（计数含参数化，合计9）。自制样例测试不替代上面的官方 pdf/ 真文件容器证据。

最终全量回归命令：

```powershell
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --basetemp data/grobid-integration-regression-final --junitxml tests/reports/grobid-integration-pytest.xml
```

实际输出原文：

```text
532 passed, 5 skipped in 184.91s (0:03:04)
```

JUnit：537项，532通过、5跳过、0失败、0错误。未启用 --run-real-model，5项真实 DeepSeek测试按规则跳过，不将跳过计为通过；真实自制扫描件 PaddleOCR 测试启用。无 Docker/模型 API 依赖的常规回归不假装验证真实 GROBID。

审计 `tests/audit_grobid_acceptance.py` 重算本地 TEI 的哈希、数量、样本与表格计数，重验 MinerU 落盘四类记录与锚点，核实失败补充路径没有发布记录；另核对 PDF 身份及忽略、保护目录零改动、配置无密钥和 JUnit。审计结果与“生产转换是否通过”分开，不以审计通过掩盖生产失败。
