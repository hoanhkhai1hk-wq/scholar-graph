# 打磨 C：阅读器升级验收

日期：2026-10-26 至 2026-10-27。执行人：WorkBuddy（前端）。工作目录 `D:\AI_Workspace\Tasks\scholar-graph`，分支 main。

开工前主干 `23173b893d851e3cde8325541a3f2c61bcce9724`，`git pull` 原文 `Already up to date.`，工作区干净。

只改 `frontend/` 与 `docs/`；**未改 backend/、contracts/ 与视觉 token**，未新增 Key，未做界面中文化（留给打磨 D）。

## 一、实测环境

| 项 | 值 |
| --- | --- |
| 后端 | 本机 `http://127.0.0.1:8010`，`SCHOLAR_GRAPH_DATA_DIR=data/translate-check`，当前源码 uvicorn |
| 前端 | `npm run start -- -p 3100`，`NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8010` |
| 语料 | 官方 `pdf/` 真文件，本单另外入库 3 篇（均 201）：长书 541 页（**256.440376 秒**）、扫描件 `1706.03762v1_img.pdf`（**628.004673 秒**，OCR）、FlashAttention（arXiv `2205.14135v2` 真实下载 **366.332761 秒**，34 页） |
| 库内论文 | 4 篇：Attention v7（15 页，有文本层）、FlashAttention（34 页）、长书（541 页）、扫描件（15 页，`has_text_layer=false`） |

## 二、任务 1：段落级定位（通过）

做法：标题树节点带上该章节首个 Chunk 的开头文字作候选串；点击时在目标页用 pdf.js `getTextContent()` 建文本层（含"归一化下标 → 原始下标"映射，避免空白折叠错位），搜到候选串后取命中区间的包围盒，换算到画布 CSS 坐标，滚动并画高亮框。搜不到就退回页首并写明。

官方 Attention v7 实测：

| 入口 | 树/栏标注 | 实测结果 |
| --- | --- | --- |
| 标题树 Abstract | p.1 | 第 1 页文本层命中，高亮 y=617 w=72 |
| 标题树 5 Training | p.7 | 第 7 页文本层命中，高亮 y=479 w=100 |
| 标题树 7 Conclusion | p.10 | 第 10 页文本层命中，高亮 y=584 w=121 |
| 参考文献 [1] | 引用在 p.3 | 第 3 页命中并高亮 |
| 参考文献 [6] | 引用在 p.7 | 第 7 页命中并高亮 |
| 参考文献 [8] | 引用在 p.10 | 第 10 页命中并高亮 |

6 处全部命中。页面同时显示「段落级定位：第 N 页文本层命中「…」，已滚动并高亮」，未命中时显示「段落级定位未命中…已退回页首（页级定位）」。

打开耗时（Attention v7）：PDF 载入 **225 ms**，首屏渲染 **330 ms**。

截图：[docs/images/15-paragraph-locate.png](../docs/images/15-paragraph-locate.png)——高亮框落在第 7 页的 "5 Training" 标题上。

**精度口径**：段落级，靠文本层匹配；**字符级坐标定位未实现**，也不声称能定位到某一行或某个字。

## 三、任务 2：长书与扫描件（通过，含边界）

### 3.1 长书 541 页

| 指标 | 实测 |
| --- | --- |
| 页面可交互 | 4955 ms（含 6859 个 Chunk 的分页取数） |
| 首张画布出现 | 5654 ms |
| PDF 载入 / 首屏渲染 | 377 ms / 739 ms |
| 跳转验证 | 点「Supervised learning p.31」→ 第 31 页文本层命中并高亮 |
| 已量高页数 | **4 / 541**（按需量取，未一次性量完） |

页高改为按需量取：进入视口附近才 `getPage()` 取真实比例，未量到的页按 A4 附近比例（1.32）占位，跳转后再补一次校正滚动。

截图：[docs/images/16-longbook-layout.png](../docs/images/16-longbook-layout.png)。

### 3.2 扫描件

- 图片页正常渲染：画布 856×1109，页面可交互 798 ms、首张画布 944 ms。
- **段落级定位未命中**：扫描件 PDF 没有文本层，点「1 Introduction」时界面写明
  「段落级定位未命中：第 1 页文本层没找到「1 Introduction」，已退回页首（页级定位）。」
- **OCR 页码映射有效**：点一条 OCR 解析出的引用（侧栏标注 p.7）→ 实际落到**第 7 页**。
  即页级定位可用，段落级不可用，两者都在界面上如实区分。

截图：[docs/images/17-scanned-layout.png](../docs/images/17-scanned-layout.png)。

**边界（不让演示翻车）**：扫描件的段落级定位**做不到**，只能到页；长书只验证了 1 个跳转点，未做全书遍历；长书首屏 5 秒左右，主要耗时在 Chunk 取数而非 PDF 渲染。

## 四、任务 3：公式样本（部分未验到，如实）

换用 FlashAttention（arXiv 2205.14135v2，34 页，真实下载入库）：

- **版式原文的公式渲染已验**：第 4 页原件排版呈现 Algorithm 1 的算法行、行内数学
  （Q, K, V ∈ ℝᴺˣᵈ）与独立公式（m(x) := maxᵢ xᵢ、f(x)、ℓ(x)、softmax(x) := f(x)/ℓ(x)）。
  点标题树「3 FlashAttention: Algorithm, Analysis, and Extensions」→ 第 4 页文本层命中并高亮。
  截图：[docs/images/18-flashattention-formula.png](../docs/images/18-flashattention-formula.png)。
- **代码块与 LaTeX 保原样渲染未验到**，两个原因都如实记录：
  1. 该论文 571 个已落盘 Chunk 中，含 `$` 的 **0** 个、含 `\begin{` 的 **0** 个、含 ``` 的 **0** 个；
     公式以纯文本数学形式存在（8 个 Chunk，如 p.4「compute S = QK…」）。源解析没有产出 LaTeX 标记，
     因此翻译链路"不送模型、原位置拼回"的保护没有真实样本可验。
  2. 全文翻译（`scope=full`）**两次均未通过后端校验**，返回
     `502 / UPSTREAM_ERROR`「翻译结果校验失败，未返回不完整译文。」
     第一次 details：`段落缺失、重复、重排或为空`；第二次：`译文出现新增或改写的数字；单元u399；原数字{'2': 1}；译数字{'2': 3}`。
     后端按设计未返回部分译文，前端也就没有 markdown 可渲染。

  结论：**Markdown 视图的代码块/LaTeX 分支本次没有真实样本验过**；只验了表格、标题与段落锚点（见任务 4）。

## 五、任务 4：版式同步抽查与触底补偿（通过）

### 5.1 Markdown 版式模式同步抽查

用 Attention v7 全文翻译（175 段）开启「Markdown 版式视图」，右栏为 MarkdownView 渲染、
175 个 `<a id>` 锚点都带 `data-chunk-id`。左 → 右逐点抽查：

| 左栏点第 N 段 | 右栏顶部锚点 | 结果 |
| --- | --- | --- |
| 0（p0001-c00001） | p0001-c00001 | 一致 |
| 43（p0004-c00044） | p0004-c00044 | 一致 |
| 87（p0007-c00088） | p0007-c00088 | 一致 |
| 131（p0011-c00132） | p0011-c00132 | 一致 |

**4/4 精确一致**。

### 5.2 末尾触底补偿

点最后一段（p0015-c00175）：两栏滚动状态 左 21660/21660、右 10879/10879，**两栏都到底**，
并显示提示「该段已到栏底，无法顶到顶部；两栏改为按底部对齐（触底补偿），对应段仍以高亮标出。」

> 修过一个真 bug：第一版补偿提示点了不出来——后续滚动回调把状态又清掉了
> （补偿把两栏都带到底后，`sync` 再次执行时发现目标已在底部，于是把"底部对齐"标记清成 false）。
> 改成"只要目标栏停在底部就保持该状态"后正常。

截图：[docs/images/19-markdown-sync-bottom.png](../docs/images/19-markdown-sync-bottom.png)。

## 六、任务 5：追踪状态前端展示（通过，失败分支未验）

检索页新增「arXiv 定期追踪」区（`GET /retrieval/tracking/status`、`POST /retrieval/tracking/run`），
通过界面点「立即运行一次追踪」真实触发（真实公开 arXiv Atom 查询）：

```
调度：backend_interval · 启用 false · 活动 false · 间隔 86400 秒 · 已自动运行 0 次
去重日志 0 条 · 默认间隔 86400 秒
最近一次运行 completed
run_id dec718ce · 耗时 22.219 秒 · 候选 3 · 新增 0 · 重复 0 · 失败 0
2026-10-26T16:59:45 → 2026-10-26T17:00:07
查询 7 条（真实公开 arXiv Atom 查询）
```

运行状态、新增数、失败数、调度信息均在页面可见；失败原因按后端三字段原文渲染（`error_code：message`），不改写。

截图：[docs/images/20-tracking-status.png](../docs/images/20-tracking-status.png)。

- 修过一个真问题：状态取数最初走服务端地址（默认 8000），与实际后端 8010 不一致导致
  「追踪状态取数失败 / NETWORK_ERROR」；改为与页面其他取数一致的浏览器侧同源代理后正常。
- **失败原因展示分支未在真实失败上跑通**：本单所有追踪运行均成功（无失败原因可显示）。
  调试期间曾记录到一次后端真实失败原文 `VALIDATION_ERROR：同一数据目录的操作正在执行，请稍后重试。`
  （上传占锁时触发），但该场景未能在界面上复现，故该分支标记为**未验**。

## 七、文本 pane 回归与构建

文本 pane（默认「原文阅读」）回归：

```
{"chunks":175,"navItems":70,"citeButtons":116}
视图模式: ["原文阅读","中英双语对照","版式原文（pdf.js）"]
```

三个视图切换都在，文本 pane 的 175 个 Chunk、70 个导航项、116 个引用按钮均正常。

构建结果原文：

```
EXIT=0
✓ Compiled successfully in 1634ms
Generating static pages (0/3) ...
✓ Generating static pages (3/3)

Route (app)                                 Size  First Load JS
┌ ƒ /                                      162 B         106 kB
├ ○ /_not-found                            994 B         104 kB
├ ƒ /api/backend/[...path]                 123 B         103 kB
├ ƒ /graph                                139 kB         244 kB
├ ƒ /papers/[id]                          2.8 kB         109 kB
├ ƒ /qa                                  7.81 kB         117 kB
├ ƒ /read/[id]                           10.6 kB         117 kB
├ ƒ /retrieval                            4.2 kB         110 kB
├ ƒ /upload                              4.24 kB        111 kB
└ ƒ /writing                             2.79 kB         108 kB
+ First Load JS shared by all             103 kB

○  (Static)   prerendered as static content
ƒ  (Dynamic)  server-rendered on demand
```

9 条业务路由齐全。`/read/[id]` 由 9.19 kB 增至 10.6 kB，`/retrieval` 由 3.17 kB 增至 4.2 kB。

## 八、本单未完成 / 如实说明

1. **Markdown 视图的代码块与 LaTeX 分支未验到**：两篇官方论文的落盘 Chunk 都没有 LaTeX/代码标记，
   FlashAttention 全文翻译两次未通过校验。需要带 LaTeX 标记的输入才能真正验到。
2. **扫描件段落级定位做不到**：只能页级，已在界面写明。
3. **追踪失败原因展示分支未验**：没有真实失败运行可显示。
4. 长书只验了 1 个跳转点，未做全书遍历；长书首屏约 5 秒，瓶颈在 Chunk 分页取数（69 次请求），未优化。
5. 界面中文化按约定留到打磨 D，本单未做；视觉 token 未动。
6. 提交钩子执行后在 `tests/` 下出现未跟踪文件 `audit_web_runtime.py`，不属于本单改动，未提交。
