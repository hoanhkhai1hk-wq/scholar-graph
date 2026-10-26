# GROBID 联调验收记录（当前未通过）

日期：2026-10-26。语料：**官方 pdf/ 真文件**。本单没有改后端业务实现、契约、前端或技术文档，没有调用模型 API、没有使用或保存 Key。

## 结论

**GROBID 容器联调未通过，逐字段双解析器对照尚未完成。** 本机装有 Docker Desktop/CLI，但本次 Docker Desktop 启动失败，Linux Server 不可连接；不能将 CLI 已安装、Compose 语法有效或自制 TEI 测试通过说成 GROBID 已接通。GROBID 没有返回 TEI，各字段数量是“未取得”，不是 0。已向用户报告这个需要在本机恢复引擎的阻塞，恢复后可用本报告命令重跑。

独立配置、真实探针、7 项新增单元测试和本机回归已经完成。官方真文件 MinerU 从空目录实跑完成，保留了题录为空、公式无文本等实际边界。未伪造 GROBID 数量、样本、镜像摘要、服务版本或比较结论。

## 开工基线与输入

- `git pull`：`Already up to date.`；开工主干 `523d07666767c0cafd9f54ed1a5980af3b26176d`，工作区干净。
- 本地文件 `D:\AI_Workspace\Tasks\scholar-graph\pdf\1706.03762v7.pdf`，2,215,244 字节、15 个 PDF 物理页。
- SHA-256：`bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697`。
- `.gitignore` 仍含 `/pdf/` 和 `*.pdf`；本单 PDF、模型和完整解析结果不进 Git。
- 最新一次探针开始于 `2026-10-26T01:27:41.411059+00:00`，输出空目录 `data/grobid-integration/20261026T012741Z-9ae086c5/`，没有复用宿主机已解析记录。
- 结构化实测：[grobid-integration-live.json](grobid-integration-live.json)。报告样本是官方真文件实际 MinerU 输出，非手写替代。

## 服务版本、启动与失败证据

独立配置：`services/docker-compose.grobid.yml`，镜像标签 **`grobid/grobid:0.9.1-full`**，`linux/amd64`、CPU 路径，仅开放 `127.0.0.1:8070`，容器内存上限 6 GiB、core dump 为 0，不注入环境变量、密钥或 PDF 卷。标签来自 [GROBID 官方 Docker 文档](https://grobid.readthedocs.io/en/latest/Grobid-docker/)（2026-10-26 查阅）。这只是配置版本；实际 `/api/version`、容器运行状态和镜像 digest 均未取得。

CLI 实际版本为 Docker 29.9.2，Desktop 启动日志标示 4.96.3。开始时 `docker version` 的 Server 为 null。尝试 `docker desktop start` 后，Docker 自身启动失败原文（仅 HOME 脱敏）：

```text
starting services: initializing Secrets Engine: listening on unix://<HOME>/AppData/Local/docker-secrets-engine/engine.sock: rename <HOME>/AppData/Local/docker-secrets-engine/engine.sock <HOME>/AppData/Local/docker-secrets-engine/engine.sock.stale: The file cannot be accessed by the system. (listener: The file cannot be accessed by the system.)
```

核实该目录只含 `engine.sock`（0 字节、Archive/ReparsePoint）。对本次启动后已崩溃的 Docker 进程进行停止后，尝试完整保留该 socket 目录并重命名；PowerShell 与 .NET 的目录移动均返回：

```text
Access to the path 'C:\Users\1234\AppData\Local\docker-secrets-engine' is denied.
```

没有删除目录、没有工厂重置、没有修改 Docker 设置或清理镜像/数据卷，也没有尝试提权。该故障模式与 [Docker 官方问题仓库 #15064](https://github.com/docker/for-win/issues/15064) 相似；本机重命名也失败，不能声称该 workaround 已修复本机。

真实执行启动命令：

```powershell
docker compose -f services/docker-compose.grobid.yml -p scholar-graph-grobid up -d
```

退出码 1，输出原文：

```text
failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine; check if the path is correct and if the daemon is running: open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
```

本机 HTTP 探针实际失败原文：

```text
ConnectError: [WinError 10061] 由于目标计算机积极拒绝，无法连接。
```

因此没有服务端解析耗时、GROBID TEI 或可选 Pipeline 实连耗时；没有把 MinerU 耗时当成容器耗时。

配置语法校验确实成功（退出码 0），输出原文：

```yaml
name: scholar-graph-grobid
services:
  grobid:
    restart: 'no'
    image: grobid/grobid:0.9.1-full
    init: true
    mem_limit: "6442450944"
    networks:
      default: null
    platform: linux/amd64
    ulimits:
      core:
        soft: 0
        hard: 0
    ports:
      - mode: ingress
        host_ip: 127.0.0.1
        target: 8070
        published: "8070"
        protocol: tcp
networks:
  default:
    name: scholar-graph-grobid_default
```

## 同一官方真文件逐字段对照（GROBID 列仍待真实服务）

MinerU 4.0.12，使用项目既定本地 SDK `tier=flash, ocr_mode=txt, image_analysis=False`。这不是 MinerU 的视觉模型/OCR 模式。全管线 6.754470 秒，其中引擎 5.505349 秒；最终 completed/100，四类记录与锚点校验通过。

| 字段 | MinerU 原始/归一化实测 | GROBID 容器实测 | 可据实判断的差异 |
| --- | --- | --- | --- |
| 标题 | 原生 `doc_title` 1；Chunk 中 1 个明确标题；PaperMeta.title 为空 | 未取得 | 文本存在，但本地上传题录未补齐；不能声称两者题录一致 |
| 作者 | 作者原文位于首面多个 Chunk；PaperMeta.authors 为 0 | 未取得 | 正文能回溯作者行，但不是结构化作者列表 |
| 机构 | 首面原文含 Google Brain、Google Research、University of Toronto；PaperMeta.institutions 为 0 | 未取得 | 有原文不代表字段已归一化，不能以手工计数冒充字段产出 |
| 摘要 | 摘要标题/正文 Chunk 有文本；PaperMeta.abstract 为空 | 未取得 | 摘要可作为证据检索，但没有进入题录字段 |
| 章节 | 原生 paragraph_title 27；归一化非空 section_path 去重 29 | 未取得 | 单位不同；27 中包括作者、邮箱、公式误判，不能说是 27 个准确章节 |
| 表格 | 原生 table 4；最终 table Chunk 4，带 HTML 行列与物理页 bbox | 未取得 | 本例真实优势是表格内容、位置均有产出；没有测得 GROBID 表格质量 |
| 公式 | 原生 equation 7，但内容均为空的情况须单独核对；已抽样的前 2 个 content=""；最终 formula Chunk 0 | 未取得 | 当前文本层配置没有产出可用公式文本，不能说 MinerU 已识别出 7 个公式原文 |
| 参考文献 | ReferenceEntry 40；40 条的作者、年份、标题、出处、DOI 均为空，仅编号身份有效；CitationLink 69 | 未取得 | 编号锚点可用；结构化文献字段有明确缺口，尚无 GROBID 实测补齐证据 |

最终 Chunk 为 **175**：text 166、figure 5、table 4、formula 0；175 个都有 bbox。原生中间结果包括 text 121、doc_title 1、paragraph_title 27、aside_text 1、page_number 14、image 5、equation 7、page_footnote 2、table 4。不能把原生块数与有文本的发布 Chunk 数直接等同。

GROBID 的原定优势是题录与结构化参考文献；这是服务设计及现有适配器的职责，不是本轮已测得结论。**本轮无法完成“两者各自强项”的实验性判断**，没有把官方文档、旧 mock 或 MinerU 输出放进 GROBID 列充数。

## MinerU 原文样本（官方 pdf/ 真文件）

以下均来自本次新发布的 Chunk；完整 chunk_id 在 JSON 中。`p0001` 等为 PDF 物理页，不是印刷页码。

- 标题：第 1 页 `c00002`：`Attention Is All You Need`。
- 作者/机构：第 1 页 `c00003`：`Ashish Vaswani ∗ Google Brain avaswani@google.com  Llion Jones ∗  Google Research llion@google.com`。第 1 页 `c00004`：`Noam Shazeer ∗  Google Brain noam@google.com  Aidan N. Gomez ∗  † University of Toronto aidan@cs.toronto.edu`。这是原文行，未假装成已归一化作者/机构字段。
- 摘要：第 1 页 `c00010`：`The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism.`
- 章节：原生标题样本 `3 Model Architecture`、`3.2.1 Scaled Dot-Product Attention`、`5.3 Optimizer`。同一列表还包含 `illia.polosukhin@gmail.com`，故不将其总数当准确章节数。
- 表格：第 6 页 `c00066`：`Table 1: Maximum path lengths, per-layer complexity and minimum number of sequential operations for different layer types.` HTML 原文片段：`<tr><td>Self-Attention</td><td>O(n<sup>2</sup> · d)</td><td>O(1)</td><td>O(1)</td></tr>`。
- 公式：没有可引用的 formula Chunk。原生样本：`{"type":"equation","index":6,"bbox":[0.358,0.587,0.825,0.62],"content":""}`。空字符串没有被补写成公式原文。
- 参考文献：ReferenceEntry number=1 的 `authors=[]; year=null; title=null; venue=null; doi=null`，number=2 同样为空。原文引用编号能解析，但不能把空记录说成完整文献解析结果。
- GROBID 上述八类字段：**均无返回样本**；未借用 MinerU 或手工填写。

## 生产链路真实分工与文档修正句

静态核查的具体位置：

1. `backend/scholar_graph/cli.py` 的 `parse --grobid-url`（默认读取 GROBID_URL）构造 GrobidClient，传给 Pipeline。
2. `backend/scholar_graph/pipeline.py`：MinerU/必要时 OCR 完成后，仅当 `self.grobid is not None` 才调用 `enrich`；随后仍走契约/锚点校验与发布。同文件哈希已存在会提前复用结果，因此真实探针分别使用两个全新目录，不能复用旧记录冒充本次调用。
3. `backend/scholar_graph/grobid.py`：补 PaperMeta 的标题、作者、机构、摘要、年份、DOI；生成 ReferenceEntry，并按既有 Chunk 引用标记重建 CitationLink。保留 Chunk，不将 GROBID 正文、章节、表格、公式映射到 Chunk。当前 XML 人名的 token 连接方式也尚缺真实 TEI 验证，不能保证所有姓名格式正确。
4. `backend/scholar_graph/api_uploads.py:UploadService.__init__` 的默认工厂只有 `Pipeline(root, gate=gate)`，**没有注入 GROBID**。
5. `backend/scholar_graph/arxiv_fetch.py:ArxivFetcher._pipeline` 的默认工厂只加元数据补充，没有注入 GROBID。根 Compose 也没有替 HTTP 工厂启用它。

结论：**源码有可选补充接入点，默认 HTTP 生产路径未启用；本轮连可选分支的真实容器调用也尚未跑通。** 不是“已验证的 MinerU + GROBID 默认融合基座”。没有为补证据擅自改变默认生产实现。

供用户转给文档补丁单的精确替换句（本单不改 docs/）：

> PDF 文本与版式解析基座为本地 MinerU；扫描页由 PaddleOCR 兜底。GROBID 仅保留显式启用的 CLI/Pipeline 题录及参考文献补充接入点，默认 HTTP 上传和 arXiv 抓取未启用；本轮受 Docker Desktop 启动故障阻塞，尚未取得 GROBID 容器联调证据，不宣称已形成经实测的 MinerU + GROBID 融合解析基座。本轮未验证 DeepSeek-OCR。

## 探针与回归

探针 `tests/run_grobid_acceptance.py` 的设计顺序：空目录 MinerU → `/api/isalive` 与 `/api/version` → multipart `/api/processFulltextDocument`（全页、不设 start/end，consolidation 全为 0，附原始 affiliation/citation 与坐标）→ 第二个空目录启用现有 GrobidClient 的真实 Pipeline。无 mock 网络、无自造业务答案。失败设置 `passed=false` 并返回退出码 1；后续步骤未执行就不写成成功。API 参数依据 [GROBID 官方服务文档](https://grobid.readthedocs.io/en/latest/Grobid-service/)。

7 项新增测试使用**自制 TEI，非官方 PDF、非容器联调证据**：题录/文献作者分开计数、章节与表格 caption 分开计数、缺失字段保持 0、3 种坏响应拒收、XXE 拒收、可选转换不更改 Chunk 与文件身份。单测 7/7 通过。

本机全量回归命令与输出原文：

```powershell
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --basetemp data/grobid-integration-regression --junitxml tests/reports/grobid-integration-pytest.xml
```

```text
530 passed, 5 skipped in 164.02s (0:02:44)
```

JUnit：535 项、530 通过、5 跳过、0 失败、0 错误。包含真实自制扫描件 PaddleOCR 测试。本单不启用 `--run-real-model`，5 项真实 DeepSeek 测试按既有规则跳过：连通性、SSE、英中翻译、中英翻译、3D 图注。**没有把跳过计为通过，也没有声称 GROBID 容器测试通过。**

证据审计命令：`backend/.venv/Scripts/python.exe tests/audit_grobid_acceptance.py`。审计将仓库范围、语料身份、忽略规则、配置无密钥与回归检查，同“GROBID 业务验收是否通过”分别标记，见 [审计 JSON](grobid-integration-audit.json)。

## 重跑入口

Docker Server 恢复后，在 D 盘工作目录依次执行：

```powershell
docker compose -f services/docker-compose.grobid.yml -p scholar-graph-grobid up -d
backend/.venv/Scripts/python.exe tests/run_grobid_acceptance.py
backend/.venv/Scripts/python.exe tests/audit_grobid_acceptance.py
```

只有真实容器返回完整 TEI、完成可选 Pipeline、取得逐字段数量和样本后，才能将本报告的“未取得”改为结果并改验收结论。目前三项任务中服务解析与双解析器实测对照仍未完成；分工口径核查已完成。
