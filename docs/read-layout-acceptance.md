# 缺口单 D 第二段：pdf.js 版式原文阅读器验收

日期：2026-10-26。执行人：WorkBuddy（前端）。工作目录 `D:\AI_Workspace\Tasks\scholar-graph`，分支 main。

开工前主干 `5a8d0ed8b5e4139ba8a924b5306202f8b60f6d62`，`git pull` 原文 `Already up to date.`，工作区干净。

本单只改 `frontend/`、`docs/` 与 `.gitignore` 一条生成物规则；**未改 backend/ 与 contracts/**，未新增 Key。

## 一、实测环境

| 项 | 值 |
| --- | --- |
| 后端 | 本机 `http://127.0.0.1:8010`，`SCHOLAR_GRAPH_DATA_DIR=data/translate-check`，当前源码 uvicorn |
| 前端 | `npm run start -- -p 3100`，`NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8010` |
| 论文 | 官方 `pdf/1706.03762v7.pdf`（Attention Is All You Need v7），15 页，175 Chunk，40 条参考文献，69 条引用对应 |
| 新增依赖 | `pdfjs-dist` 4.10.38（Apache-2.0，登记见 `docs/open-source-register.md`） |

**原件准备**：该论文是上一单上传的，上传当时后端尚未保留原件，`GET /file` 返回 404。
按后端 README「可重新上传与已入库 file_hash 完全一致的 PDF 补齐映射」重传同一文件后补齐；
重传返回 201，并带去重预警（解码后）：「同一文件内容已入库；换名重传触发重复判定，保留已有论文，不重复入库。」

## 二、文件端点与代理透传（先决条件）

### 2.1 后端直连

```
HTTP=200 字节=2215244
content-type: application/pdf
content-disposition: inline; filename="paper.pdf"
accept-ranges: bytes
etag: "bdfb15c61c09a5ff2ef6082bcb181ecc"
下载件 SHA-256 与官方源件 pdf/1706.03762v7.pdf 一致：True
```

### 2.2 代理改动（本单必须修的一处）

原代理对非 SSE 响应执行 `await upstream.text()`，有两个后果：SSE 被缓冲；
**二进制响应被按 UTF-8 解码而损坏**——原文 PDF 经代理后必然打不开。

改为统一 `return new Response(upstream.body, …)`，并额外透传文件端点需要的
`content-disposition`、`accept-ranges`、`etag`、`content-range`。

经代理实测（证明未损坏）：

```
HTTP=200 字节=2215244
accept-ranges / content-disposition / content-type / etag 均带回
经代理下载 SHA-256: bdfaa68d8984f0dc02beaca527b76f207d99b666…
官方源件   SHA-256: bdfaa68d8984f0dc02beaca527b76f207d99b666…
经代理后仍与源件逐字节一致: True
```

## 三、任务 1：版式原文渲染

`/read/{id}` 新增第三个视图「版式原文（pdf.js）」，与「原文阅读」「中英双语对照」并存，
三个视图互不改动（文本 pane 与双语同步滚动保持原样）。

实现：`LayoutViewer` 通过同源代理取 `/papers/{id}/file` 的 `arrayBuffer`，交给 pdf.js 逐页画到 canvas；
页容器按 `data-page` 标记并带 `id="pdf-page-N"`，供跳转定位。渲染对象**是 PDF 原件**，
不是解析后的 Markdown，也不重新排版。

浏览器实测（Chrome 无头，真实点击切换）：

```
页数栏: 共 15 页 · 当前第 1 页 | 页容器数: 15 | 首张画布: 856x1108
首画布非白像素数: 2900   ← 画布真的画出了内容，不是空白占位
```

画面为论文第 1 页原排版：Google 授权声明、标题「Attention Is All You Need」、
八位作者与单位、arXiv 侧栏 `arXiv:1706.03762v7 [cs.CL] 2 Aug 2023`、摘要起始段。

截图：[docs/images/13-layout-original.png](../docs/images/13-layout-original.png)

## 四、任务 2：标题树与 3 处跳转页码对照

标题树由已落盘 Chunk 的 `section_path` 生成（多级缩进），节点页码取该路径下 Chunk 的
**最早物理页**，与后端 `GET /chunks` 的 `page_number` 同源。

### 4.1 后端基准（脚本复刻前端口径，从 `GET /chunks` 全量计算）

```
Chunk 总数: 175
Abstract → p.1        1 Introduction → p.2      2 Background → p.2
3 Model Architecture → p.2    5 Training → p.7   6 Results → p.8
7 Conclusion → p.10    References → p.10   3.2.2 Multi-Head Attention → p.4
```

### 4.2 浏览器实测（点击标题树项 → 读取视口顶部实际页码）

修复前：

```
Abstract     标注 p.1  → 落到第 1 页 : 一致
5 Training   标注 p.7  → 落到第 6 页 : 不一致
7 Conclusion 标注 p.10 → 落到第 8 页 : 不一致
```

**失败原因（真实 bug，非测量误差）**：懒渲染时未渲染的页高度为 0，
跳到第 N 页后上方页面陆续渲染变高，把目标页推下去。
修复：加载后按序量出每页高度占位；跳转时先把目标页**及之前所有页**量完再滚动，
并补一次校正滚动。

修复后：

```
Abstract     标注 p.1  → 落到第 1 页 : 一致
5 Training   标注 p.7  → 落到第 7 页 : 一致
7 Conclusion 标注 p.10 → 落到第 10 页 : 一致
```

三处全部一致。截图：[docs/images/14-layout-nav-jump.png](../docs/images/14-layout-nav-jump.png)
（侧栏显示标题树与页码，含命题示例中的「3.2.2 Multi-Head Attention → p.4」）

**如实说明**：源解析把部分公式与正文片段误分为一级标题，标题树会照实继承这些条目
（如 "4 To illustrate why the dot products get…" → p.4、"MultiHead(Q, K, V ) = Concat…" → p.5、
邮箱行 → p.1）。这是已落盘 `section_path` 的真实内容，前端未做过滤，也未假装它们是正确章节。

## 五、任务 3：参考文献双向跳转

映射口径：`CitationLink.ref_id ↔ ReferenceEntry.ref_id`，
`CitationLink.page_number` 即该条文献在正文被引用处的 PDF 物理页。

后端基准（40/40 条文献都有引用页，共 69 条引用对应）：

```
[1] p.3    [2] p.2、p.4、p.5    [3] p.4、p.7    [6] p.7    [8] p.10    [9] p.2、p.5、p.6、p.8、p.9
```

### 5.1 文献 → PDF 页（点击侧栏条目）

```
[1] 侧栏「正文中引用出现在 p.3」  → 实际落到第 3 页
[6] 侧栏「正文中引用出现在 p.7」  → 实际落到第 7 页
[8] 侧栏「正文中引用出现在 p.10」 → 实际落到第 10 页
```

三处全部正确。若某条没有解析出引用位置，侧栏写「正文引用位置未解析出，无法跳转」，
不猜页码、不跳到近似位置。

### 5.2 PDF 页 → 回到该条文献（反向）

顶部条实时显示当前页出现的引用编号；点击即滚回侧栏对应条目并高亮：

```
点击本页引用 [8] → 高亮的文献条目：[8]（标题未提取）
```

反向可用。参考文献条目的标题在本论文中未被解析出来（显示「标题未提取」），
这是源 `ReferenceEntry` 的真实内容，前端未编造标题。

### 5.3 精度口径（如实写明）

- 标题树与参考文献跳转均为**页级精度**：只能定位到该页顶部，做不到字符级定位，
  也不定位到某一行或某个引用标记的具体坐标。
- 页内滚动位置不做二次定位，因此"跳到第 7 页"是第 7 页的页首，不是该章节标题的精确位置。
- 双栏 PDF 不做分栏定位：只按物理页定位，不声称能定位到左栏/右栏。

## 六、前端构建结果原文

```
EXIT=0
> scholar-graph-frontend@0.1.0 build
> npm run sync-pdf-worker && next build
[pdf.worker] 已复制 -> public/pdf.worker.min.mjs
   ▲ Next.js 15.5.28
 ✓ Compiled successfully in 2.2s
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
├ ƒ /read/[id]                           9.19 kB         115 kB
├ ƒ /retrieval                           3.17 kB         109 kB
├ ƒ /upload                               4.2 kB          110 kB
└ ƒ /writing                             2.79 kB         108 kB
+ First Load JS shared by all             103 kB

○  (Static)   prerendered as static content
ƒ  (Dynamic)   server-rendered on demand
```

9 条业务路由齐全。`/read/[id]` 由 6.89 kB 增至 9.19 kB（pdf.js 与版式视图）。

**worker 处理**：pdf.js 的 worker 由 `scripts/copy-pdf-worker.mjs` 在 build/dev 前从
`node_modules` 复制到 `public/`，已在 `.gitignore` 排除——不把第三方构建产物提交进仓库；
pdf.js 协议 Apache-2.0 已在 `docs/open-source-register.md` 登记。

## 七、回归与相邻视图

切换视图后原文本 pane 复测（未改动其逻辑）：

```
原文阅读 pane: {"chunks":175,"navItems":70,"citeButtons":116,
                "translateNote":true,"pdfNote":true}
视图模式: ["原文阅读","中英双语对照","版式原文（pdf.js）"]
```

文本 pane 仍为 175 Chunk、70 个导航项、116 个正文引用按钮；双语同步滚动逻辑未触碰。
文本 pane 里那句「版式原文渲染待后端文件端点」已过时（文件端点已落地、版式视图已上线），
改为「本视图是文本 pane，不是版式原文……请切到顶部的『版式原文（pdf.js）』视图」。

## 八、本单未完成 / 如实说明

1. **只验了官方 Attention v7 一篇**（15 页）。长书（541 页）与扫描件未在本单试跑：
   页高按序量取，541 页会有可感知等待，未做性能测量，不声称长书可用。
2. **未做字符级定位**：标题树与文献跳转都是页级（见 5.3），未尝试坐标级定位，也不假称做到。
3. **未验 Range 分片请求**：后端支持 `Range: bytes=...`（206/Accept-Ranges/Content-Range），
   代理已透传相关头，但 pdf.js 本单走的是整文件 `arrayBuffer` 读取，
   **没有实测分片请求路径**。
4. 参考文献标题在本论文中未解析出，侧栏显示「标题未提取」，未编造标题。
5. 双栏版面只做到按页渲染与按页定位，未做分栏定位。
