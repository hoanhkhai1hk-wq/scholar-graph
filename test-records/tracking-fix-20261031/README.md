# arXiv 追踪错误专项 · 2026-10-31

结论：**状态与错误展示修复后通过；部分外部题名查询仍超时，完整网络可用性未通过。** 本报告不替代官方第 1–6 项的整体验收。没有删除历史失败记录，没有使用虚构论文补齐结果。

## 1. 用户截图为什么报错

读取实际演示库的原始追踪日志，截图对应运行 `7dc11c77e40e45988738c5e642aac467`：

| 指标 | 真实记录 |
| --- | ---: |
| 状态 | partial |
| 执行查询 | 10 |
| 查询成功 / 失败 | 1 / 9 |
| 发现候选 / 新增入库 | 3 / 0 |
| 下载或解析失败 | 0 |
| 总耗时 | 859.554593 秒 |

这里的失败是请求 arXiv 公开接口失败，与 DeepSeek Key 无关。“下载或解析失败 0”并不代表查询成功。旧错误没有分类字段，不能倒推这 9 条全部属于同一种底层异常；重新实测一个题名查询确认出现 ReadTimeout。

页面还存在自己的问题：兼容面板只显示下载失败数、运行中错误显示“本次没有新增论文”、英文 running 状态、长错误被挤入键值网格的第一窄列、手动运行结果遮蔽后续状态、不会自动刷新；主面板把每条相同错误都展开为大红框。

## 2. 真实外部网络检查

| 路径 / 查询 | 结果 | 耗时 |
| --- | --- | ---: |
| 后端容器直连，arXiv id_list=1706.03762 | HTTP 200，Atom 格式真实返回 | 0.763 秒 |
| 后端容器直连，题名 A neural probabilistic language model | ReadTimeout，诊断探针 8 秒读取上限 | 8.25 秒 |
| 主机经现有系统代理，同题名 | ReadTimeout | 8.41 秒 |
| 后端容器经现有系统代理，同题名 | ReadTimeout | 8.32 秒 |
| 修改后真实 ArxivClient，同题名，2 次尝试 | UPSTREAM_TIMEOUT，单次读取上限 10 秒 | 20.74 秒 |
| 修改后真实 ArxivClient，all:"attention"，上限 3 篇 | 3 篇通过契约验证的真实结果 | 0.71 秒 |

最后一条返回 `2610.40653v1`、`2610.40647v1`、`2610.40586v1`。依据分别为 `container-network-before.log`、`system-proxy-probe.json`、`arxiv-client-live-after.log`、`attention-search-live.log`。

结论是部分查询能成功、部分题名查询超时，不能定性为全部无法访问，也不能宣称修复页面就恢复了所有外部查询。主机与容器经同一代理都超时，因此没有擅自把代理写进配置，也没有把“容器未继承系统代理”认定为已证实的唯一根因。当前证据不能进一步区分远端响应慢与中间网络链路问题。

## 3. 本轮修复与优化

- 后端把等待超时与连接失败分开，输出安全的原因码、异常类型、尝试次数和读取上限；不返回可能包含代理凭据的原始异常文本。
- 搜索请求读取上限从 30 秒调为 10 秒，保留原有一次额外尝试、公共接口限速和下载读取上限 30 秒。这是配置级等待约束，不是承诺整轮任务 10 秒结束，也不是同一批查询的速度提升实测。
- 持久化准备、查询、下载解析、结束阶段，查询总数和已发现数量随实际执行更新。
- 两个面板分别显示查询失败与下载解析失败，中文状态、候选与入库说明清楚区分。
- 相同错误合并显示次数，逐条原始结果留在折叠诊断中；两个相同错误合并为一个提示框已由浏览器状态模拟验证。
- 兼容面板按 5 秒周期顺序刷新、标签页隐藏时暂停轮询；主面板保留原有 10 秒刷新。运行时禁用重复触发。
- 仅当任务完整结束、没有查询或获取失败且新增为 0，才显示“本次没有新增论文”。
- 修复键值布局，不再让整段错误占据窄列；1440 与 390 宽度实测未出现水平溢出。

使用 Impeccable 的 harden 指引：采纳错误状态区分、用户操作说明、诊断折叠、中文化及小屏检查；保留用户已选的现有设计，没有展开全站重设计。其 context 提示 PRODUCT 与设计 sidecar 版本较旧，仅记录，不在本专项顺带更新。

## 4. 实测、模拟与构建分别记录

| 检查层 | 结果 | 边界 / 证据 |
| --- | --- | --- |
| 快速回归 | 200 passed，625 deselected，43.73 秒 | 无 Key 回归；不是重新验收所有 OCR / 模型功能。fast.log / fast.xml |
| arXiv、追踪、调度、导入、任务相关全量 | 72 passed，0 skipped，57.37 秒 | 包含 MockTransport 与合成文献，验证控制流及兼容；不算真实外网成功。related02.log / related02.xml |
| Next.js 生产构建 | 退出 0 | frontend-build02.log |
| Docker 镜像构建 | 前后端均成功 | backend-image.log / frontend-image02.log |
| 真实浏览器 | 7 个检查场景，0 页面脚本异常 | browser/report.json |
| 当前演示部署 | 后端 healthy；前端页面 HTTP 200；容器解析 backend 为 172.25.0.2 | runtime.json；该测试 Compose 的前端没有配置 Docker healthcheck，不能把它写成 Docker healthy |
| 版本及数据保护 | 容器后端两文件 SHA 与工作树一致；前端 BUILD_ID 一致；原有 UploadForm 修改 SHA 未变 | runtime.json；未提交该旧改动 |

浏览器的 7 个场景：2 个为实际 3400 网页、真实后端记录（1440 / 390）；4 个为明确标记的运行中、失败、部分完成、完成 UI 状态模拟；1 个为模拟状态由运行中转失败，验证自动刷新无需手动点击。后 5 个用于覆盖错误呈现，不能当成真实 arXiv 请求成功。所有场景均检查“没有新增论文”的显示条件，实际页面检查横向溢出，模拟重复错误检查主面板仅一个提示框。

执行入口（在项目根目录）：

```powershell
& backend/.venv/Scripts/python.exe tests/run_regression.py fast --no-key
& backend/.venv/Scripts/python.exe -m pytest tests/test_tracking_network_errors.py tests/test_arxiv_fetch.py tests/test_arxiv_api.py tests/test_tracking.py tests/test_tracking_import.py tests/test_tracking_scheduler.py tests/test_item04_discovery.py tests/test_workspace_tasks.py -q --basetemp data/tracking-related-recheck
& D:/下载/npm.cmd --prefix frontend run build
& D:/下载/node.exe tests/tracking_fix/browser.cjs after verified
& backend/.venv/Scripts/python.exe tests/tracking_fix/audit_runtime.py
```

首次相关测试因沙箱默认临时目录权限失败：16 passed、56 setup errors；改用工作区临时目录并正常授权执行后 72 全过。最初浏览器复查还曾因用户期间启动了新任务，断言固定的旧 partial 状态而失败；改为检查实时状态应满足的规则，未放宽错误计数、空状态或溢出要求。这些执行问题不隐藏为首跑即过。

## 5. 当前真实运行结果与残留

只读复核时间 `2026-10-31T04:06:47.921872+00:00`，最近一次真实运行 `720a10c3d76747aba8df61fc173f1deb`：2 条查询成功、0 条失败；发现 4 篇，按上限选出 3 篇；3 篇都为库内重复，新增 0；耗时 12.851523 秒。见 runtime.json 与 browser/main-1440.png。该批种子与截图旧批不同，不能把 859.55 秒到 12.85 秒描述为可比性能提升。

当前网站为 http://127.0.0.1:3400/retrieval ，后端 8100。启动此次版本：

```powershell
docker compose -p scholar-graph-item04 -f tests/item04/compose.yml -f tests/tracking_fix/release.yml up -d --no-build --wait
```

release.yml 引用本地已构建的追踪修复镜像，不含 Key；新的机器需按项目指南配置环境并构建镜像，不能直接假定本机镜像存在。Key 与模型配置仅验证 KEY_SET / MODEL_SET 为 true。

仍未通过：题名查询的端到端外网可用性。下一步需对同一失败题名查询在实际部署网络下复测，必要时排查出口链路或对接经过验证的公开检索备用源；备用结果也必须真实可追溯。本轮没有篡改种子、掩盖失败、批量删除数据，也没有为得到绿色结果绕开失败查询。

本轮提交只覆盖追踪相关修复、测试和证据。原有论文、历史记录、未跟踪的其他工作及旧的提交压缩包均保留；没有把本地 3400 写成公网体验地址。
