# 模块一解析、去重与状态机实跑报告

日期：2026-10-24（Asia/Shanghai）。所有输入为自制样例、非官方 pdf/ 用例；未运行官方三用例。

开工前拉取主干：`0a285b2686e9e0638d8545e5ad44fe4be7e447c9`；git pull --ff-only 返回 Already up to date.。
独立实跑对应源码提交：`cd892b4b5bb746fd6b3df87cb15acde8cbb360b6`。十八份契约 Schema/example 的 Git 文件哈希与开工基线一致，未更改任何字段。

## 先完成的前置项

1. tests/verify_contract_boundaries.py 与依赖单独提交。
2. 实际执行 722 个唯一边界用例，722 通过、0 失败，报告单独提交；分类与逐项结果见 contract-boundaries.md/json。
3. docs/api-draft-v1.md 仅修改 parse-status 端点表一行，改为“v1.1 已定义，返回 ParseStatus”，单独提交。

## 本地最小验证

| 输入 | 页数 | PaperMeta | Chunk | ReferenceEntry | CitationLink |
| --- | ---: | ---: | ---: | ---: | ---: |
| data/module-one-release/inputs/selfmade-v1.pdf | 2 | 1 | 6 | 1 | 1 |
| data/module-one-release/inputs/selfmade-v7.pdf | 2 | 1 | 8 | 1 | 1 |
| data/module-one-release/inputs/selfmade-scan.pdf | 1 | 1 | 3 | 0 | 0 |

v1 和 v7 的 SHA-256、输出目录、每个 JSON 的 SHA-256、完整 ParseStatus 历史见 module-one-smoke.json。四类记录落盘后重新加载并经过 Schema 与外键校验。

v7 上传时已自动生成 1 条系统 DedupDecision 和 1 条 DiffSummary；依据已有裸 DOI 的精确匹配，无需额外比较命令。扫描样例使用独立标题与作者，没有误配到这两版。另行验证人工覆盖路径，生成 1 条系统 DedupDecision、1 条模拟人工 DedupDecision、1 条 DiffSummary。词频 Dice 相似度为 0.850575，系统建议 manual_review。
系统建议原样保留；模拟人工意见另存为 human_override=true / keep_both。模拟意见由测试脚本显式指定，不是用户或专家实际审核。
去重证据分别指向含 12 samples 与 18 samples 的真实正文 Chunk；差异摘要引用新版协议正文。全部关键句四字段锚点匹配，verified 文本是目标 Chunk 的原文子串。

## 状态与校验

文本路径：queued:0 → parsing:5 → parsing:30 → indexing:80 → indexing:95 → completed:100。
扫描路径在 parsing:30 后进入 ocr:40 → ocr:70，再进入 indexing 和 completed。失败分支保留最后进度，必须有统一编码与非空错误说明，不使用 100。
所有项目记录在落盘前过冻结 Schema；Chunk 归属、物理页码、section_path、heading、bbox 顺序、参考条目及引用键再做语义检查。去重与差异锚点还要匹配真实 Chunk，关键句长度上限 600 字符并检查原文子串。
每组论文 JSON 先完整校验再写临时目录，同文件系统重命名发布；不合规数据或写盘故障不发布半组结果。重复输入相同 PDF 不覆盖旧记录。

## 测试结果

最终 pytest：50 通过、0 失败、0 错误、0 跳过，包含真实 MinerU 与真实 PaddleOCR。JUnit 明细见 module-one-pytest.xml。

| 测试文件分类 | 实际数量 |
| --- | ---: |
| tests.test_cli_adapters | 3 |
| tests.test_dedup | 14 |
| tests.test_parsing | 14 |
| tests.test_validation_status | 19 |

覆盖真实文本 PDF、空白封面的物理页码、真实扫描 OCR、v1/v7 差异、重复上传、异常 PDF、加密 PDF、OCR 故障、截断/重复页、无锚点及错页/错章节、伪造关键句、写盘故障和人工意见保留。
开发首轮发现空白封面被误送 OCR；修复后又发现 MinerU 的空白页省略 blocks 字段。两项均已修复并由最终测试覆盖。报告复核还发现证据指向标题过弱，已改为优先引用实际变化正文，重新跑完整测试及独立验证。

## 外部组件真实状态

| 组件 | 状态 | 实际证据 |
| --- | --- | --- |
| MinerU | 已接通 | 4.0.12，本地 flash/txt SDK，实际解析自制文本 PDF，不依赖 Docker |
| OCR | 已接通 | PaddleOCR 3.7.0 + PaddlePaddle 3.3.1，CPU/PP-OCRv5；自制英文扫描页识别 3 条 Chunk |
| GROBID | 待验证 | 可配置 HTTP/TEI 客户端已写且 Mock 测试通过；未调用真实 GROBID，无 Docker Desktop/CLI |

GROBID 官方快速开始明确列出 grobid/grobid:0.9.1-full 标签，Compose 沿用该版本；未拉取镜像，镜像摘要、资源配置与运行联调仍为 TODO。
来源：[GROBID 官方快速开始](https://grobid.readthedocs.io/en/latest/getting_started/)。文档可确认镜像名不等于运行验证。

`docker compose --profile grobid config` 原始输出：

```text
'docker' is not recognized as an internal or external command,
operable program or batch file.
```

退出码 1。Docker Compose 真校验：待验证。只完成 PyYAML 的语法和 GROBID 占位结构自查，未将其计作 Compose 校验通过。
pip check 输出 No broken requirements found.；完整依赖版本见 module-one-environment.json。

## 复现

在 D:\AI_Workspace\Tasks\scholar-graph 的 PowerShell：

```powershell
backend/.venv/Scripts/python.exe tests/verify_contract_boundaries.py
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --basetemp data/test-temp-reproduce
backend/.venv/Scripts/python.exe tests/run_module_one_smoke.py --output-root data/module-one-smoke-reproduce --report tests/reports/module-one-smoke-reproduce.json
```

smoke 命令拒绝覆盖已存在的输出根目录，重现时使用新的英文目录。首次 OCR 可能下载模型。安装与单篇解析、比较命令详见 backend/README.md。

## 范围与限制

没有实现问答、图谱、检索推荐、写作辅助或 Web API；没有修改 frontend、prompts、experiments、test-records、提纲或其他 docs 内容。未读取或配置真实 API Key，没有调用 DeepSeek。
Guardrails 本单落实结构校验、锚点真实归属、关键句原文子串及长度上限；没有把实验报告建议的 QA 三态等内容写入冻结契约。
本地参考文献回退仅支持编号条目与可确认的简单格式；作者年份引用、复杂表格/公式、跨栏、中文 OCR 和真实论文精度未验证。自动版本对应仅使用本地裸 DOI、arXiv 基号或标题加作者完全相同；显式 DOI 冲突不自动配对。没有语义检索或推荐；无精确对应时可手动指定两条记录。相同文件重传不重复生成版本裁决。
截图仅用于检查自制 PDF 的可读性，没有将其当真实论文或前端验收。输出路径在被忽略的 data/ 中；原始 PDF、模型和虚拟环境没有入 Git。

## 已执行提交与对应文件

下表为最终证据提交之前的全部实施提交（含前一轮证据及后续补强）；本报告最新提交哈希由最终回报另列，避免自引用。

| 完整哈希 | 内容 | 对应文件 |
| --- | --- | --- |
| `de356d567c6b7b358843a9882d65e77a65cf4c7f` | 补入可复现的契约边界验证脚本与依赖 | `tests/requirements.txt`；`tests/verify_contract_boundaries.py` |
| `3b6db0bf018ba1a06d913a29c0487d9c90a4120b` | 记录契约边界用例实际运行数量分类与逐项结果 | `tests/reports/contract-boundaries.json`；`tests/reports/contract-boundaries.md` |
| `e98dd914812685cc9406bed7947de65cb362c201` | 修正解析状态端点行以返回v1.1 ParseStatus | `docs/api-draft-v1.md` |
| `dff23636388c579067ffb303cbf19cae872efef9` | 实现契约及锚点校验门禁与解析状态机并验证边界 | `backend/pyproject.toml`；`backend/scholar_graph/__init__.py`；`backend/scholar_graph/errors.py`；`backend/scholar_graph/status.py`；`backend/scholar_graph/validation.py`；`tests/conftest.py`；`tests/test_validation_status.py` |
| `544c545a14721baff400d7a82a587e39818ba7e0` | 实现MinerU本地解析和PaddleOCR兜底及校验后原子落盘 | `backend/pyproject.toml`；`backend/scholar_graph/_engine_worker.py`；`backend/scholar_graph/adapters.py`；`backend/scholar_graph/grobid.py`；`backend/scholar_graph/normalize.py`；`backend/scholar_graph/pipeline.py`；`backend/scholar_graph/storage.py`；`backend/scholar_graph/validation.py`；`tests/conftest.py`；`tests/sample_pdfs.py`；`tests/test_parsing.py` |
| `c3cbd2f7309f3a091f62f033279ae7e95df88fa5` | 实现保守去重与版本差异及保留系统意见的人工裁决 | `backend/scholar_graph/dedup.py`；`tests/test_dedup.py` |
| `d9181e30d3d0d623e4e7ce65d55061b3f0b67655` | 添加本地命令行入口复现步骤及实跑证据生成脚本 | `backend/.gitignore`；`backend/README.md`；`backend/scholar_graph/__main__.py`；`backend/scholar_graph/cli.py`；`backend/scholar_graph/validation.py`；`tests/run_module_one_smoke.py`；`tests/test_cli_adapters.py`；`tests/test_validation_status.py` |
| `8df8bdebf4228ef0ec58fe9358413a48f46143a7` | 配置可选GROBID本机服务并明确Docker联调待验证 | `docker-compose.yml`；`services/README.md` |
| `09f6c3bfafcd90f84e62ed0f99aa09c8b58d5670` | 补强解析完整页检查与失败清理范围防止截断结果被发布 | `backend/scholar_graph/dedup.py`；`backend/scholar_graph/pipeline.py`；`backend/scholar_graph/storage.py`；`tests/test_parsing.py` |
| `2d12139ed1c16650deec0b569cb92f83945ee10a` | 按实际环境检测Docker可用性避免复现报告写死结论 | `tests/run_module_one_smoke.py` |
| `57a4812b68987e117ae80e8c00d1795d10e74ce3` | 使去重证据与差异关键句优先指向实际变化正文 | `backend/scholar_graph/dedup.py`；`tests/test_dedup.py` |
| `cef1fa7a1a19fa777d31b438e4c31da068c19a13` | 保存模块一自制PDF实跑与49项测试及契约冻结审计报告 | `tests/reports/module-one-audit.json`；`tests/reports/module-one-environment.json`；`tests/reports/module-one-pytest.xml`；`tests/reports/module-one-report.md`；`tests/reports/module-one-smoke.json` |
| `546ae4a66fe0f035738a8c4a27388f2923b6edc5` | 在第二版上传后按精确元数据自动生成去重与差异记录 | `backend/README.md`；`backend/scholar_graph/pipeline.py`；`backend/scholar_graph/storage.py`；`tests/run_module_one_smoke.py`；`tests/test_dedup.py` |
| `cd892b4b5bb746fd6b3df87cb15acde8cbb360b6` | 避免相同文件重传重复生成版本裁决并区分独立OCR样例 | `backend/scholar_graph/pipeline.py`；`tests/sample_pdfs.py`；`tests/test_dedup.py` |
