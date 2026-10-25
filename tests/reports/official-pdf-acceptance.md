# 官方 pdf/ 真文件三项重跑总报告

本轮范围为**官方 pdf/ 真文件**，用户提供的四份文件直接从 `D:/AI_Workspace/Tasks/scholar-graph/pdf/` 只读上传，未下载替代文件、未重制扫描件、未抽页或拆书。业务失败如实保留；探针/审计通过与业务验收通过分开统计。本轮业务结论：去重失败、OCR 失败、长书失败。

开工 `git pull --ff-only` 原文：`Already up to date.`；工作区干净；main 起点 `17ed94939b01285ee96c7708cf177d669f48739b`。原有 `*.pdf` 已忽略文件，另新增 `/pdf/` 忽略整个目录并单独提交。Git 未跟踪语料。只新增 tests/ 与这一条忽略规则；后端、契约、前端及旧报告均零改动。

## 官方 pdf/ 真文件与上一单对照基线

| 项目 | 上一单对照基线 | 本轮官方 pdf/ 真文件 | 一致性判定 |
| --- | --- | --- | --- |
| 去重上传与 Chunk | v7/v1 均201，175/162条，无预警 | v7/v1 均201，175/162条，无预警；裁决/差异均404 | 一致：上传成功，去重业务仍失败 |
| Dice | 0.933224，出自带arXiv身份的另外一次抓取控制 | 0.933224，仅对实际上传Chunk离线计算，未写裁决 | 数值一致、计算场景不同；均不能证明本轮上传触发预警 |
| OCR | 默认300秒：304.962881秒（约304.96）；扩展900秒：904.776897秒（约904.78）；两次OCR_FAILED，0有效Chunk | 默认300秒：307.664604秒，HTTP422，OCR_FAILED，0有效Chunk；OCR worker在300.027257秒抛出TimeoutExpired | 失败行为一致；默认耗时不一致（多2.701723秒）；本轮未重跑900秒配置，不作同配置性能比较 |
| 长书页数/字节/拒绝 | 541页、22344992字节，200页上限拒绝，0Chunk，未索引 | 541页、22344992字节，HTTP422，200页上限拒绝，0Chunk，未索引 | 一致：长书业务失败 |
| 长书RSS采样峰值 | 154.45703125 MiB（约154.457031） | 143.453125 MiB（150421504字节） | 不一致：本轮低11.00390625 MiB；运行负载/采样差异，不能据此推断实现优化 |

本轮官方 v7/v1 与长书的 SHA-256 均与上一单对应文件一致；本轮官方扫描件 SHA-256 不同（4672118字节，上一单为5210401字节），因此只比较失败行为，不宣称扫描输入相同。三项 JSON 均包含运行前后原文件 SHA-256、完整接口响应及实际状态。审计再次校对当前文件哈希，证明探针未改写官方 pdf/ 真文件。

## 官方 pdf/ 真文件：去重

使用FastAPI TestClient调用真实管线，未替换解析引擎或补写元数据。真实调用 `POST /api/v1/papers`，先 `1706.03762v7.pdf`，再 `1706.03762v1.pdf`，未调用抓取端点补身份。v7耗时8.894384秒，201，PaperMeta/Chunk/ReferenceEntry/CitationLink为1/175/40/69；v1耗时8.017927秒，201，为1/162/36/64。两次最终状态均completed、100%。四类记录已经原有Schema与外键门禁，审计重新加载复核。

**预警原文：不存在（JSON null），没有触发预警。去重判定：未生成。差异摘要：未生成。** 两次上传响应为PaperMeta，原文均在 [去重JSON](official-pdf-dedup.json)。两篇的裁决GET原文均为：

```json
{"error_code":"PAPER_NOT_FOUND","message":"无该新版论文的去重记录。","details":null}
```

两篇的差异GET原文均为：

```json
{"error_code":"PAPER_NOT_FOUND","message":"无该新版论文的差异记录。","details":null}
```

只定位不修：`backend/scholar_graph/pipeline.py:139-147` 从PDF文档元数据取标题/作者，arxiv_id固定为空，版本只认独立的 `Version:` 行。本次两篇实际 title、doi、arxiv_id、version均null，authors均[]。`storage.py:83-111` 的 previous_version 仅按精确DOI/arXiv或完整标题作者查找，两次真实调用均返回None（探针旁观原方法并原样返回）。因此 `pipeline.py:96` 未找到prior，`:97` 跳过compare，`:100` 不写comparison；后续裁决/差异GET无记录。上传链路缺少在这些身份缺失时的全库语义候选查找，不能靠高词频Dice自动触发。现有compare也不做版本质量排序；不得声称已经建议保留v7。契约的new_paper_id指后上传记录，本次是v1，不等于版本号更新。

## 官方 pdf/ 真文件：扫描 OCR

直接上传用户 `1706.03762v1_img.pdf`：15物理页，4672118字节，所有页文本层字符数0，未光栅化、未修复。PaddleOCR3.7.0/PaddlePaddle3.3.1，默认API与默认300秒worker时限。复用本机既有PaddleX缓存28文件，仅复制缓存至本次隔离data目录，不改模型、阈值、线程或时限。本轮没有另外执行900秒配置。

实际耗时 **307.664604秒**，HTTP422，有效Chunk **0**。真实MinerU worker成功返回（7.504464秒），OCR worker在 **300.027257秒** 抛出 **TimeoutExpired**。状态 queued0 → parsing5 → parsing30 → ocr40 → failed40，未进入indexing。错误原文：

```json
{"error_code":"OCR_FAILED","message":"本地 OCR 未完成，请检查依赖、模型与运行时限。","details":null}
```

本轮确定失败在真实OCR子进程等待超时（非依赖失败的推测）；尚不能判断是某页特别慢或累计全页耗时导致。完整进程观察、状态历史、内存采样与源哈希见 [OCR JSON](official-pdf-ocr.json)。

只定位不修：`pipeline.py:74` 调用LocalEngines.ocr，`adapters.py:33-34` 执行真实worker，`:41-43` 将超时/进程异常/非法输出统一为OCR_FAILED；本轮具体观察见 engine_calls。`_engine_worker.py:27-49` 按页处理，直到全部页完成后才向父进程返回JSON，因此没有可发布的部分Chunk。旁观器只记录模式、时限、耗时、返回码或异常类型，原始调用参数不变，返回/异常透传；没有伪造引擎、吞异常或记录模型日志/环境值。无法据此判断超时时究竟处理到第几页，不编造更细根因。

## 官方 pdf/ 真文件：长书

完整 `UnderstandingDeepLearning_02_09_26_C.pdf`，541页、22344992字节。HTTP422，上传测量0.345713秒；错误原文：

```json
{"error_code":"PARSE_FAILED","message":"PDF 页数必须在 1 到 200 之间。","details":null}
```

状态queued0 → parsing5 → failed5。`backend/scholar_graph/pipeline.py:124-125`：`if count < 1 or count > 200:` 后抛出该错误；发生在页数检查阶段，早于MinerU、切块和索引。本次已发布Chunk为0，索引未进入，耗时记null而非0秒。论文列表total0，该论文Chunk分页GET404，不能写成长书分页已通过。RSS采样峰值150421504字节/143.453125MiB，private峰值135442432字节；每50ms采样测试进程及全部子进程合计，非系统级精确高水位，可能重复计算共享页。原始JSON含采样次数/起始值。

## 官方 pdf/ 真文件验证后的全量回归与审计

执行 `backend/.venv/Scripts/python.exe tests/run_official_regression.py`，实际pytest参数为 `-m pytest tests -q --run-ocr --basetemp data/official-pdf/regression/temp --junitxml tests/reports/official-pdf-pytest.xml`。控制台原文：

```text
296 passed in 193.85s (0:03:13)
```

JUnit：总数296，通过296，失败0，错误0，跳过0。真实OCR自制单页烟测包含在回归中，不能替代本次官方15页扫描件失败。

回归保留既有自制样例；并非296个官方语料业务用例。JUnit仅补充验证范围与回归输入属性，不改统计、耗时或测试结果。三项官方验证全部结束后才运行回归。OCR开始后的短时间内并行运行另两项独立上传，采样分别覆盖各自进程树；本单耗时不作为严格性能基准。

复现（D盘仓库，需本地原语料、既有虚拟环境与Paddle缓存；每项要求新建data目录，已存在则拒绝覆盖）：

```powershell
backend/.venv/Scripts/python.exe tests/run_official_dedup.py
backend/.venv/Scripts/python.exe tests/run_official_ocr.py
backend/.venv/Scripts/python.exe tests/run_official_longbook.py
backend/.venv/Scripts/python.exe tests/run_official_regression.py
backend/.venv/Scripts/python.exe tests/audit_official_pdfs.py
```

探针移除子进程环境中凭据变量，不读取.env，问答配置为extractive、检索为lexical，不调用真实大模型或使用真实API Key。审计核对三项JSON与落盘数据、原文件运行前后哈希、契约Git blob冻结、只增tests/范围与忽略规则、常见密钥格式及完整JUnit。本次审计81项检查通过，26个既有契约文件Git blob与开工基线一致。审计通过仅证明证据一致；**官方 pdf/ 真文件三项业务未通过，未修实现。**

文件：[去重JSON](official-pdf-dedup.json)、[OCR JSON](official-pdf-ocr.json)、[长书JSON](official-pdf-longbook.json)、[审计JSON](official-pdf-audit.json)、[JUnit](official-pdf-pytest.xml)。提交完整哈希与推送原文在最终交付回报，避免报告自引用提交哈希。
