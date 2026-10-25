# 模块三同步滚动前端接入验收报告

日期：2026-10-25。执行人：WorkBuddy（前端）。工作目录 `D:\AI_Workspace\Tasks\scholar-graph`，分支 main。

开工前主干 `04117a02ceafead2e61105390eae4a5ec8be0e09`，`git pull` 原文 `Already up to date.`，工作区干净。

本单只改 `frontend/` 与 `docs/`：**未改后端代码、未改 contracts/**。
端点结构与对齐口径依据 `backend/README.md`「模块三：英→中翻译与Chunk对齐」（第 266–293 行）。

## 一、真实环境

| 项 | 值 |
| --- | --- |
| 带 Key 后端 | `http://127.0.0.1:8010`，`SCHOLAR_GRAPH_DATA_DIR=data/translate-check`，继承进程环境的 `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL` |
| 无 Key 后端 | `http://127.0.0.1:8011`，同一数据目录，进程内**未设置**上述两个变量 |
| 论文 | 官方 `pdf/1706.03762v7.pdf` 上传入库，id `paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697`，175 个 Chunk |
| 前端 | `npm run start -- -p 3100`，通过现有同源代理取数 |

**与后端验收报告的一致性**：该论文 id 与
`tests/reports/translation-live-results.json` 中 manifest 的论文 id **完全相同**，
因此本报告中的段映射可直接与该报告的 manifest 逐条对应（见下节）。
Key 仅由后端从进程环境读取，未写入任何文件；本报告与代码均不含 Key。

## 二、四个入口状态（任务 2）

| 入口 | 请求体 | 真实结果（带 Key） | 无 Key 结果 | 页面位置 |
| --- | --- | --- | --- | --- |
| 摘要翻译 | `{"scope":"abstract","target":"zh"}` | HTTP 200，6 段（c00009–c00014），与报告 manifest 6 段一致 | 502 UPSTREAM_ERROR | 「翻译摘要」按钮 |
| 章节翻译 | `{"scope":"section","target":"zh","section_path":["1 Introduction"]}` | HTTP 200，5 段（c00015–c00019），与报告 manifest 5 段一致 | 502 UPSTREAM_ERROR | 章节下拉 +「翻译该章节」 |
| 选区翻译 | `{"scope":"selection","target":"zh","chunk_ids":[…]}` | HTTP 200，2 段（整 Chunk）／20 段（滚动验证时用） | 502 UPSTREAM_ERROR | Chunk 勾选 +「翻译选中 N 个整 Chunk」 |
| 全文翻译 | `{"scope":"full","target":"zh"}` | HTTP 200，175 段，markdown 39127 字符，175 个 `<a id>` 锚点 | 502 UPSTREAM_ERROR | 「翻译全文」按钮 |

真实耗时：abstract 3.46 s、section 2.98 s、selection（2 段）2.31 s、full 57.35 s。

**选区口径如实写明**：后端只接受该论文已有的 chunk_id、按原文顺序翻译整段 Chunk，
不支持 Chunk 内字符级选区，也不是逐词翻译。页面在选区入口用醒目提示原文写出这三点，
不假装支持逐词/字符选区。

**代码与公式保持原样**：MarkdownView 对代码块、行内代码一律原样渲染，不做翻译或改写；
后端侧本就不把 LaTeX/公式送模型。本次官方 Attention 的 markdown 含 3 个 HTML 表格、
0 个代码块、0 处 LaTeX（该源解析没有独立 formula 类型 Chunk），因此**代码块与 LaTeX
的保原样渲染在本论文上没有真实样本可验**，只在代码层实现。

## 三、双向滚动同步验证（任务 3）

### 3.1 对齐口径

按 `segments[i].source_chunk_id` 对应，两栏由同一份 segments 顺序渲染，
第 i 段互为对应段——**不依赖译文字符长度**（与后端 README 第 283、291 行一致）。
每段的 DOM 元素带 `data-chunk-id`，滚动/点击时取本栏视口顶部最近的一段，
把另一栏滚到同 id 的段，并用短暂锁避免两栏互相触发。

### 3.2 真实样本来源

后端 `tests/reports/translation-live-results.json` 最后一轮（`status: passed`）的
manifest：abstract 6 段、section 5 段、full 175 段，含每段 `source_chunk_id` 与 `page_number`。
本次入库论文的 id 与该 manifest 的论文 id 一致，实测段 id 与 manifest 逐条相同：

```
abstract（与 manifest 6 段一致）：-p0001-c00009 / c00010 / c00011 / c00012 / c00013 / c00014（均 p1）
section （与 manifest 5 段一致）：-p0002-c00015 / c00016 / c00017 / c00018 / c00019（均 p2）
```

### 3.3 浏览器实测（选区 20 个整 Chunk，真实译文）

先取 6 段摘要试跑，发现右栏可滚动范围仅 140 px（scrollHeight 758 / clientHeight 618），
末尾段**物理上无法顶到顶部**——这是容器高度限制，不是对齐错误。改用 20 段选区
（内容足够长）后重测：

```
两栏段数: {"left":20,"right":20}

=== 左 → 右 ===
左第 0  段 …p0001-c00001 → 右顶部 …p0001-c00001 | 一致
左第 5  段 …p0001-c00006 → 右顶部 …p0001-c00006 | 一致
左第 10 段 …p0001-c00011 → 右顶部 …p0001-c00011 | 一致
左第 15 段 …p0002-c00016 → 右顶部 …p0002-c00016 | 一致
左第 19 段 …p0002-c00020 → 右顶部 …p0002-c00016 | 触底钳制(scrollTop=1486/1486)

=== 右 → 左 ===
右第 0  段 …p0001-c00001 → 左顶部 …p0001-c00001 | 一致
右第 5  段 …p0001-c00006 → 左顶部 …p0001-c00006 | 一致
右第 10 段 …p0001-c00011 → 左顶部 …p0001-c00011 | 一致
右第 15 段 …p0002-c00016 → 左顶部 …p0002-c00016 | 一致
右第 19 段 …p0002-c00020 → 左顶部 …p0002-c00017 | 触底钳制(scrollTop=2038/2038)

左→右 精确一致 4/5；右→左 精确一致 4/5
```

结论：**双向都能按 source_chunk_id 定位**，抽查 5 个位置中 4 个精确顶格对齐；
最后一段两栏都滚到了各自极限（触底钳制），属容器可滚动范围的物理上限，
不是映射错配；该情况下对应段仍以高亮标出。

截图：[docs/images/11-bilingual-sync.png](../docs/images/11-bilingual-sync.png)
（画面：左英文原文、右中文译文，两栏同一 chunk id 标在同一行，
如 p0001-c00001「Provided proper attribution…」↔「在提供适当署名的情况下…」；
p0001-c00002「Attention Is All You Need」↔「注意力就是你需要的一切」）

## 四、无 Key 错误态（任务 2，必验）

无 Key 后端（进程内未设置 `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL`）直连结果：

```
abstract   {"error_code":"UPSTREAM_ERROR","message":"DeepSeek环境变量未设置，未调用模型。","details":null} [HTTP=502]
section    {"error_code":"UPSTREAM_ERROR","message":"DeepSeek环境变量未设置，未调用模型。","details":null} [HTTP=502]
selection  {"error_code":"UPSTREAM_ERROR","message":"DeepSeek环境变量未设置，未调用模型。","details":null} [HTTP=502]
full       {"error_code":"UPSTREAM_ERROR","message":"DeepSeek环境变量未设置，未调用模型。","details":null} [HTTP=502]
```

前端页面（经代理，四个入口各点一次）错误区文本一致：

```
翻译请求失败（abstract）· 未返回任何译文
接口地址 http://127.0.0.1:8011/api/v1/papers/paper-bdfaa68d…/translate
状态码 502
错误码 UPSTREAM_ERROR
原因 DeepSeek环境变量未设置，未调用模型。
后端未返回数据，页面不显示任何替代数据。请确认后端已启动且地址一致。
```

（section / selection / full 三个入口文本同上，仅 scope 名不同。）

页面同时写明：「缺配置时后端返回 502 / UPSTREAM_ERROR……后端不提供无 Key 的摘录假译文，
前端也不补」。**四个入口均无译文展示、无占位译文、无摘录兜底。**

截图：[docs/images/12-translate-no-key.png](../docs/images/12-translate-no-key.png)

## 五、npm run build 结果原文

```
BUILD_EXIT=0

> scholar-graph-frontend@0.1.0 build
> next build

   ▲ Next.js 15.5.28
   Creating an optimized production build ...
 ✓ Compiled successfully in 2.1s
   Linting and checking validity of types ...
   Collecting page data ...
   Generating static pages (0/3) ...
 ✓ Generating static pages (3/3)
   Finalizing page optimization ...
   Collecting build traces ...

Route (app)                                 Size  First Load JS
┌ ƒ /                                      162 B         106 kB
├ ○ /_not-found                            994 B         104 kB
├ ƒ /api/backend/[...path]                 123 B         103 kB
├ ƒ /graph                                139 kB         244 kB
├ ƒ /papers/[id]                         2.76 kB         109 kB
├ ƒ /qa                                  7.81 kB         117 kB
├ ƒ /read/[id]                           6.89 kB         113 kB
├ ƒ /retrieval                           3.17 kB         109 kB
├ ƒ /upload                               4.2 kB          110 kB
└ ƒ /writing                             2.79 kB         108 kB
+ First Load JS shared by all             103 kB

○  (Static)   prerendered as static content
ƒ  (Dynamic)  server-rendered on demand
```

9 条业务路由齐全（`/`、`/papers/[id]`、`/read/[id]`、`/qa`、`/graph`、`/retrieval`、
`/writing`、`/upload` 与同源代理路由）。`/read/[id]` 从 2.29 kB 增至 6.89 kB（双栏与翻译入口）。

（构建日志中夹杂本机 `system-ca-bundle.pem` 路径缺失的告警，与项目代码无关。）

## 六、安全自查

Key 仅由后端从进程环境读取；前端代码与本仓库任何文件均未出现 Key 字面量
（已用 `sk-[A-Za-z0-9]{10,}` 模式全仓扫描，命中项均为论文正文 "task-independent" 之类的
误匹配，且位于 gitignore 的 `data/` 内）。截图中的错误态只含接口地址，不含凭据。

## 七、本单未完成 / 如实说明

1. **末尾段的顶格对齐受容器可滚动范围限制**：最后 1–2 段无法顶到顶部（触底钳制），
   目前以高亮标出对应段。未做"到底后改为底部对齐"的补偿逻辑。
2. **代码块 / LaTeX 的保原样渲染无真实样本**：本次官方 Attention 的 markdown 没有代码块与
   LaTeX（0/0），只有 3 个 HTML 表格；渲染路径已实现但未在真实公式样本上验过。
3. **全文 Markdown 视图与逐段视图的混合同步**：full 的右栏可切 Markdown 版式（175 个锚点），
   此时左右栏高度差异更大，只验证了逐段模式下的双向同步，
   **Markdown 模式下的同步未做逐点抽查**。
4. 中→英全文翻译后端未实现，前端也没有该入口。
