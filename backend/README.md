# ScholarGraph 模块一后端

本单实现本地 PDF 解析、状态机、去重与版本差异。Python 包为 `scholar_graph`。没有问答、图谱、检索、推荐或写作模块；没有 Web 服务端点实现。

## Windows 本地安装

在 `D:\AI_Workspace\Tasks\scholar-graph` 的 PowerShell 中执行。需要 Python 3.12；全部运行数据写入本目录下被 Git 忽略的 data/。

```powershell
py -V:Astral/CPython3.12.15 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -e 'backend[ocr,test]'
```

本机 Python 启动器的 3.12 标签为 Astral/CPython3.12.15，上面的命令已按该标签配置；其他机器先用 `py -0p` 查已有 Python 3.12 标签。已有 backend/.venv 时跳过创建步骤。仅解析文本 PDF 时可安装 `backend[test]`，扫描件需要额外的 ocr 依赖及首次模型下载。实际锁定的引擎为 MinerU 4.0.12、PaddleOCR 3.7.0、PaddlePaddle 3.3.1；使用 CPU OCR，不要求 CUDA 或 Docker。backend/pyproject.toml 固定直接依赖，完整本轮环境版本见 tests/reports/module-one-environment.json。不要把虚拟环境、模型、PDF、data/ 或 .env 提交到 Git。

## 第一步：解析一个 PDF

```powershell
backend/.venv/Scripts/python.exe -m scholar_graph parse data/input/paper-v1.pdf
```

文本页调用 MinerU 本地 SDK 的 `tier=flash, ocr_mode=txt`；没有模型推理的文本层模式也确实经过 MinerU。扫描页单独送 PaddleOCR，混合 PDF 保留各自的物理页索引；纯空白页不送 OCR、不创建伪正文。英文 OCR 为默认值，可加 `--ocr-language ch` 切换，中文样例本单未验证。

每个原始 PDF 按 SHA-256 得到稳定 paper id。成功后在 `data/module-one/papers/<paper-id>/` 得到：

- paper-meta.json：一个 PaperMeta；未知信息保留 null 或空列表，不推测机构、摘要或年份。
- chunks.json：Chunk 数组；坐标是可见整页的 0–1 归一化坐标，物理页码从 1 开始。
- reference-entries.json：ReferenceEntry 数组；未知参考文献信息保留 null，不编造条目。
- citation-links.json：CitationLink 数组；只链接已确认编号的文末条目，未知引用不生成链接。

命令 stdout 返回 PaperMeta；失败返回固定三字段统一错误对象并使用非零退出码。上传第二版时，如本地已有记录的裸 DOI、arXiv 基号或标题加作者完全一致，自动生成 DedupDecision 和 DiffSummary 到 comparisons/，无需另运行比较命令。显式冲突的 DOI 不会因为标题相同而自动配对；多个匹配版本按本地入库顺序选择最后一个，不作为发表日期或质量排序。中间状态在 `data/module-one/jobs/<job-id>/parse-status.json`，是已校验的 ParseStatus 快照数组，支持查看完整 queued → parsing → ocr（可选）→ indexing → completed / failed 过程。indexing 在本单仅指构建并验证记录关联，不是检索索引。依赖异常原文和凭据不会进入命令输出或状态记录。

每条记录先过冻结的 JSON Schema，随后检查外键、物理页码上限、章节路径、标题、bbox 顺序及引用唯一性。全部通过后才把四个文件作为一组原子发布；失败不发布半组文件。已有记录保持不可变，重复上传相同 PDF 返回相同记录；输出目录被修改或冲突时拒绝覆盖。

本地默认限制：50 MiB、200 页、每个引擎调用 300 秒；`--timeout` 可设为 1–3600 秒。MinerU 原始中间结构仅在子进程 stdout/内存中传递，不把未校验的第三方 JSON 当作项目记录保存。输入快照保存在 data/ 下临时目录，结束时清理。

## 第二步：比较两版

先分别解析 v1 与 v7，再将两次得到的 paper id 代入：

```powershell
backend/.venv/Scripts/python.exe -m scholar_graph compare data/module-one/papers/<old-paper-id> data/module-one/papers/<new-paper-id>
```

在 `data/module-one/comparisons/comparison-<id>/` 生成 dedup-decisions.json（DedupDecision 数组）与 diff-summary.json（DiffSummary）。相似度是词频重叠的 Dice 系数，不是科研质量或结论可信度。正文一致时建议 keep_old；发现变化时保守建议 manual_review，不凭版本号或样本数变大自动建议 keep_new。手动比较命令用于没有精确元数据对应或需要明确指定两版的情况。本单只有本地精确身份对应，不做语义检索、推荐或跨源候选召回。

差异按真实 Chunk.section_path 分组；无章节分块的变化标作 Unsectioned。关键句是对应 Chunk 的最多 600 字符原文前缀，verified 必须同时通过四字段锚点匹配与原文子串检查；无锚点的外部关键句只能标 unverified。章节未变化时明确输出“未检出章节级差异”。删除章节引用旧版原文，不把删除推断为论文结论错误。

人工意见需显式提供选择与依据：

```powershell
backend/.venv/Scripts/python.exe -m scholar_graph compare data/module-one/papers/<old-paper-id> data/module-one/papers/<new-paper-id> --human-choice keep_both --human-reason '已核对两版内容，保留两版用于比较'
```

系统记录原样保留为数组第一项，人工意见是另一项且 human_override=true。程序不删除 PDF，不覆盖原系统 recommendation，也不自动执行淘汰。人工依据本身是人工意见，不冒充程序验证的科研质量结论。

## 可选 GROBID

配置 `GROBID_URL` 或 `--grobid-url http://127.0.0.1:8070` 后，通过 multipart 调用 `/api/processFulltextDocument`，将 TEI 中可靠的元数据和参考文献归一化为现有契约。默认关闭，不影响 MinerU 本地直跑。配置后调用失败即输出 UPSTREAM_ERROR，不静默声称已经用到 GROBID。禁用服务端 Crossref consolidation，避免隐式联网补元数据。

本机没有 Docker Desktop / Docker CLI，GROBID 实际联调与 `docker compose config` 均待验证。Mock HTTP/TEI 测试仅证明客户端转换逻辑，不证明真实服务已接通。Compose 的镜像标签有官方文档依据，尚未拉取或启动；详见 services/README.md。

## 验证与范围

```powershell
backend/.venv/Scripts/python.exe tests/verify_contract_boundaries.py
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --basetemp data/test-temp
backend/.venv/Scripts/python.exe tests/run_module_one_smoke.py --output-root data/module-one-smoke --report tests/reports/module-one-smoke.json
```

722 个边界用例证据见 tests/reports/contract-boundaries.md 和 JSON 逐项结果。解析/去重实跑报告见 tests/reports/module-one-report.md。所有 PDF 都是脚本自制，非官方 pdf/ 用例，不声称官方三用例通过。

当前细粒度能力的边界：本地文本模式按 MinerU 返回块分割；参考文献回退只确认编号条目，支持明确的作者（年份）标题格式和数字引用；未覆盖作者年份正文引用、复杂跨栏引用、表格/公式识别质量或全类型论文。真实论文质量尚需独立评测。GROBID 可补充结构化元数据，但本轮未实连。扫描 OCR 只验证一份干净英文自制样例，不代表中文或复杂版面的精度。

实现参考：[MinerU 本地 SDK](https://opendatalab.github.io/MinerU/usage/sdk_api/)、[MinerU 中间格式](https://opendatalab.github.io/MinerU/reference/output_files/)、[PaddleOCR Python 接入](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html)、[GROBID 服务 API](https://grobid.readthedocs.io/en/latest/Grobid-service/)。
