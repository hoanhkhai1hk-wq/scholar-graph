# 模块一 HTTP API 交付证据

日期：2026-10-24。工作目录 D:\AI_Workspace\Tasks\scholar-graph，分支 main。
开工前主干 `4ac3909b01fab904d3077b469ceca0e01d03aaa7`；`git pull --ff-only` 原文 `Already up to date.`；工作区干净。
独立实跑源码提交 `9f9b69fb41d99acde54d01042c9a7ed4bf39e975`。

所有输入均为**自制样例、非官方 pdf/ 用例**；没有运行官方三用例，没有验证前端已接通。未使用真实 API Key，未读取 .env。测试客户端不依赖 Docker 或真实 GROBID；文本与扫描上传实际调用本地 MinerU / PaddleOCR。

## 端点实施清单

开工草案实际 17 条端点，不是任务文字中的 16 条。保留全部原项，新增本单指定的去重、差异 GET，共 19 条；本单落地 10 条、未落地 9 条。均加 `/api/v1`，OpenAPI/Swagger 不计业务端点。

| 方法 | 已落地端点 | 响应 |
| --- | --- | --- |
| POST | /papers | 201 PaperMeta，Location 指向详情 |
| POST | /papers/batch | 200 四字段批量结果，逐文件同步 |
| GET | /papers | 六字段分页壳，items 为 PaperMeta |
| GET | /papers/{paper_id} | PaperMeta；Link 头提供下列三个子资源路径 |
| GET | /papers/{paper_id}/chunks | 分页 Chunk |
| GET | /papers/{paper_id}/references | 分页 ReferenceEntry |
| GET | /papers/{paper_id}/citation-links | 分页 CitationLink；可按 ref_id/chunk_id 筛选 |
| GET | /papers/{paper_id}/parse-status | 最新持久化 ParseStatus，失败未发布论文也可查其状态 |
| GET | /papers/{paper_id}/dedup-decision | DedupDecision；paper_id 为 new_paper_id |
| GET | /papers/{paper_id}/diff-summary | DiffSummary；paper_id 为 new_paper_id |

| 方法 | 未落地端点 | 原因与后续归属 |
| --- | --- | --- |
| POST | /papers/{paper_id}/qa | 模块二问答，不在本单；后续单号待总指挥分配 |
| POST | /compare | 跨篇问答/对比，不是版本差异，不在本单；后续单号待总指挥分配 |
| GET | /graph | 模块五不在本单，图谱结构留待 v1.2；后续单号待总指挥分配 |
| POST | /reviews | 综述/写作不在本单，结构留待 v1.2；后续单号待总指挥分配 |
| POST | /retrieval/search | 检索推荐不在本单；后续单号待总指挥分配 |
| POST | /retrieval/fetch | 检索抓取不在本单，抓取任务专用失败结构仍未裁定；后续单号待总指挥分配 |
| GET | /recommendations | 检索推荐不在本单；后续单号待总指挥分配 |
| POST | /frameworks | 写作辅助不在本单，框架结构留待 v1.2；后续单号待总指挥分配 |
| POST | /charts/csv | 模块六不在本单；ChartOutput 已定义不表示接口已实现；后续单号待总指挥分配 |

未落地端点没有伪实现或 501 占位。需经用户转达威龙分配正式后续单号，本轮不虚构调度编号。

## 本地 HTTP 最小验证

输入与完整输出证据：[module-one-api-smoke.json](module-one-api-smoke.json)。四类记录经 HTTP 读取，与上一单同格式的落盘记录逐项比较，并再次进行 Schema 和真实 Chunk 锚点校验。

| 上传输入 | 方式 | 物理页数 | PaperMeta | Chunk | ReferenceEntry | CitationLink |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| data/module-one-api-release/inputs/selfmade-v1.pdf | POST /papers | 2 | 1 | 6 | 1 | 1 |
| data/module-one-api-release/inputs/selfmade-v7.pdf | POST /papers/batch | 2 | 1 | 8 | 1 | 1 |
| data/module-one-api-release/inputs/selfmade-scan.pdf | POST /papers，真实 PaddleOCR | 1 | 1 | 3 | 0 | 0 |

文本状态：queued:0 → parsing:5 → parsing:30 → indexing:80 → indexing:95 → completed:100。
扫描状态增加 ocr:40 → ocr:70。完整历史、paper_id、输入哈希见 JSON 证据。
v7 自动生成系统 DedupDecision 与 DiffSummary；相似度 0.850575，建议 manual_review。GET 按新版 id 返回两条裸记录。旧版 id 查裁决返回 404；没有比较的扫描论文查差异也为 404，不制造空记录。
另以脚本显式模拟人工 keep_both 意见，返回 human_override=true 的原记录；原系统记录与历史文件字节不变。这不是专家真实审核。单测还覆盖后续系统建议不能压掉更早的人工意见。

### 分页实测摘要

另一个隔离数据目录存入 101 份契约示例派生记录，避免将其冒充解析出的论文。page 默认 1、page_size 默认 20；超限按 100 计。实际响应固定六字段；下表为摘要，items 只显示条数。

| 请求（GET /api/v1/papers） | HTTP | items 条数 | page | page_size | total | total_pages | has_next |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| ?page=1&page_size=999 | 200 | 100 | 1 | 100 | 101 | 2 | true |
| ?page=2&page_size=999 | 200 | 1 | 2 | 100 | 101 | 2 | false |
| ?page=999&page_size=20 | 200 | 0 | 999 | 20 | 101 | 6 | false |
| ?title=Synthetic%20100 | 200 | 1 | 1 | 20 | 1 | 1 | false |

page/page_size 为 0、负数或非整数时，422 VALIDATION_ERROR，固定三字段错误体。空集合 total_pages=0、has_next=false；越界页不偷偷改成末页。total 按筛选后的总数计算。子资源列表使用同一分页函数；详情、状态、去重、差异不套壳。

### 批量部分失败实测摘要

请求 `POST /api/v1/papers/batch`，multipart 同名 files 字段，输入顺序：selfmade-v7.pdf、broken.pdf、wrong.txt、selfmade-v1.pdf。实际 HTTP **200**：

```json
{
  "succeeded": [
    {"paper_id": "新版完整 id 见 JSON 证据", "parse_status": "初始 ParseStatus，queued/0"},
    {"paper_id": "旧版完整 id 见 JSON 证据", "parse_status": "初始 ParseStatus，queued/0"}
  ],
  "failed": [
    {"filename": "broken.pdf", "error_code": "PARSE_FAILED", "error_message": "PDF 结构或文本层检查失败。"},
    {"filename": "wrong.txt", "error_code": "UNSUPPORTED_FILE_TYPE", "error_message": "上传文件必须为 PDF。"}
  ],
  "succeeded_count": 2,
  "failed_count": 2
}
```

以上为响应摘要，parse_status 实际是完整七字段记录，不是字符串；未经缩写的原始响应保存在 JSON 证据。四个文件恰好各进入一项结果，出错后仍处理最后一个文件；成功/失败数组各自保留相对输入顺序。返回时状态 GET 已为 completed/100；保留的 queued/0 是真实历史第一项。无异步队列，没有声称异步。

扩展名错误/超过 50 MiB 的文件在管线接收前拒绝，不伪造排队记录；合法扩展名但内容坏的 PDF 建立 queued 后进入 failed，可按其 SHA-256 id 查询状态，详情仍 404。大文件边界单测将门限临时调为 3 字节，不实际制造 50 MiB 文件。空批次返回 0/0；错误字段逐项记 VALIDATION_ERROR；multipart 解析失败返回请求级失败项，仍为 200。

无去重记录实际响应：

```json
{"error_code":"PAPER_NOT_FOUND","message":"无该新版论文的去重记录。","details":null}
```

无差异记录的 message 为“无该新版论文的差异记录。”。所有 API 错误遵循冻结 ParseStatus 的 #/$defs/api_error，无诊断 details=null；不返回业务记录，不回显异常堆栈、请求值或凭据。

## 测试结果与环境

最终完整 pytest 原文：

```text
83 passed in 94.09s (0:01:34)
```

JUnit：[module-one-api-pytest.xml](module-one-api-pytest.xml)，83 总数、83 通过、0 失败、0 错误、0 跳过。新增端点/分页 33 项，原有解析/去重等 50 项。

| 测试组 | 通过数 |
| --- | ---: |
| test_api_comparison | 4 |
| test_api_read | 14 |
| test_api_transport | 10 |
| test_api_uploads | 5 |
| test_cli_adapters | 3 |
| test_dedup | 14 |
| test_parsing | 14 |
| test_validation_status | 19 |

覆盖空列表、101 条记录、分页上限/越界/过滤计数、详情子资源取数、真实单篇与混合批次、逐文件原因与续跑、体积门限、失败状态、最新快照、三字段错误、未知异常脱敏、无记录 404、新版关联键、人工优先与系统历史不可变、未实现端点未暴露，以及真实 HTTP 扫描 OCR。

FastAPI 0.162.0、Starlette 1.9.0、httpx 0.28.1、python-multipart 0.0.32、uvicorn 0.54.0。`pip check` 原文 `No broken requirements found.`。完整引擎版本另见 JSON。

| 组件 | 真实状态 | 证据与限制 |
| --- | --- | --- |
| MinerU | 已接通 | 真实本地 SDK 文本解析，HTTP 上传产生上述四类记录 |
| PaddleOCR | 已接通 | 真实 CPU OCR，经 HTTP 上传自制英文扫描页产生 3 条 Chunk；不代表中文或复杂版面质量 |
| GROBID | **待验证** | 沿用上一单客户端与 Mock 测试，未调用真实服务；HTTP 默认工厂不启用 GROBID |

未找到 Docker CLI，默认位置也没有 Docker Desktop 可执行文件。本轮不改 Compose，不将 Mock 计作联调，真实 GROBID 与 Compose 真验证仍待验证。

## 契约与范围核对

与开工基线对比：contracts/ 下 9 份 Schema + 9 份 example 的 Git blob 全部一致；逐文件哈希见 JSON 的 frozen_contracts。contracts/CONTRACTS.md 亦未改。九份记录顶层字段数保持为 PaperMeta 14、Chunk 11、ReferenceEntry 10、CitationLink 6、QAAnswer 5、DedupDecision 7、DiffSummary 6、ParseStatus 7、ChartOutput 7。

只修改 backend/、tests/、本单获批的 docs/api-draft-v1.md。frontend/、prompts/、experiments/、test-records/、docker-compose.yml 及其他 docs 零改动。未定义图谱节点/边或综述框架结构，未实现问答、检索、写作和 CSV 图表。

本地文件存储沿用上一单格式。上传进程内串行化，启动文档指定单 worker；未实现跨进程锁、任务队列或正式部署。部分失败批次不回滚已成功文件。业务输出继续先校验再原子发布；不把未通过校验的解析记录落盘。精度边界沿用上一单，不把自制样例当真实论文质量结论。

## 复现

```powershell
backend/.venv/Scripts/python.exe -m pip install -e 'backend[ocr,test]'
backend/.venv/Scripts/python.exe -m uvicorn scholar_graph.api:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

另一 PowerShell 运行测试；实跑输出目录必须使用新的英文目录，脚本拒绝覆盖已有证据：

```powershell
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --basetemp data/http-api-reproduce --junitxml data/http-api-reproduce.xml
backend/.venv/Scripts/python.exe tests/run_module_one_api_smoke.py --output-root data/module-one-api-reproduce --report data/module-one-api-reproduce.json
```

测试客户端不要求先启动 uvicorn。运行数据、PDF、模型都在被忽略的 data/ 内，不提交。首次 OCR 可能下载模型，不需要 DeepSeek Key。

## 本轮提交与文件

以下为证据提交前的六个细粒度提交；本报告及 JSON/JUnit 的最后证据提交完整哈希在最终回报列出，避免自引用。推送原文也在最终回报给出，不在推送前预写成功结果。

| 完整提交哈希 | 对应文件 |
| --- | --- |
| 94c3bc0235f0a462e03c78fe74a246cd03acf1cc | backend/scholar_graph/api_transport.py；tests/test_api_transport.py |
| 408ccd59f7291dca268ca0ed09c4ea3fbf8acf96 | backend/pyproject.toml；backend/scholar_graph/api.py；backend/scholar_graph/api_repository.py；tests/test_api_read.py |
| 2adb415022b6e3e30ff16f2c3ec4761a67895ded | backend/scholar_graph/api.py；backend/scholar_graph/api_uploads.py；tests/test_api_uploads.py |
| 88af4c8eef5eead09a6b20216f89c91dc3001bc0 | backend/scholar_graph/api.py；backend/scholar_graph/api_repository.py；tests/test_api_comparison.py |
| 91b12b8dfa1b27349109043e5efde6cf28a1c509 | backend/README.md；docs/api-draft-v1.md |
| 9f9b69fb41d99acde54d01042c9a7ed4bf39e975 | tests/test_api_read.py；tests/test_api_uploads.py；tests/run_module_one_api_smoke.py |
