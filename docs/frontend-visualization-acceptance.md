# 前端可视化验收报告（图谱画布 / 思考过程时间线 / 预警与元数据）

日期：2026-10-25。执行人：WorkBuddy（前端）。工作目录 `D:\AI_Workspace\Tasks\scholar-graph`，分支 main。

开工前主干 `63a56a003d4569465ee09173e71f712d69a09a17`，`git pull` 原文 `Already up to date.`，工作区干净。

本单只改 `frontend/` 与 `docs/`：**未改后端、未改契约**。所有响应头名称与解码方式以
`backend/README.md` 为准（第 188 行、第 219 行）。

## 一、环境

| 项 | 值 |
| --- | --- |
| 后端 | `http://127.0.0.1:8000`（本机已运行的实例，库内为官方 pdf/ 真文件） |
| 前端 | `npm run start -- -p 3100`（3000 已被 Docker 实例占用，故用 3100） |
| 取数路径 | 浏览器侧经现有同源代理 `/api/backend/*` → `/api/v1/*`，服务端组件直连 |
| 新增依赖 | cytoscape 3.34.4（仅前端，不进后端与契约） |

切换端口不影响取数：前端所有浏览器侧调用都走同源代理，服务端发起到 8000，不经过 CORS。

## 二、响应头依据（backend/README.md 原文摘录）

```
单篇上传预警在 X-ScholarGraph-Dedup-Warning 响应头中，以 UTF-8 百分号编码返回，
编码标记为 X-ScholarGraph-Dedup-Warning-Encoding: percent-encoded-utf-8；先解码再展示。
```

```
调用元数据在 X-ScholarGraph-QA-Meta / X-ScholarGraph-Agent-Meta 响应头，UTF-8百分号编码JSON；
前者为模型调用统计，后者另含节点耗时、证据数量、校验状态、回落原因与工具参数/结果摘要。
```

两个元数据头只在特定条件下返回（读 `backend/scholar_graph/qa_routes.py` 确认）：

- `X-ScholarGraph-Agent-Meta`：请求带 `?agent=true` 时返回，**不需要 Key**。
- `X-ScholarGraph-QA-Meta`：仅当 `SCHOLAR_GRAPH_QA_MODE=deepseek` 且进程内配置了 Key 时返回。

本次环境未配置 `SCHOLAR_GRAPH_QA_MODE` / `DEEPSEEK_MODEL` / `DEEPSEEK_API_KEY`
（已确认三个变量均未设置），因此 **QA-Meta 不会被返回**，前端如实显示“后端未返回”，不编造服务商、模型名与耗时。

## 三、任务 1：图谱 Cytoscape 可视化

新文件 `frontend/components/GraphCanvas.tsx`，接入 `GraphWorkspace`，原表格保留为“节点与分层（附表）”。

画布规则（三条硬规则均已实现）：

1. 只对 `edge.status === "verified"` 建边，`unverified` 边不画，也不画成已核验样式；
2. 孤立节点照常入图，不因无边隐藏；
3. `cornerstone` 节点用深松绿 `#14544B` 且尺寸更大，`derived` / `isolated` 分别用 `#3C6E8F` / `#8A877E`。

支持滚轮缩放、拖拽平移、点节点跳转 `/papers/{id}`，外加放大/缩小/适应窗口三个按钮。

### 真实冒烟（7 篇全部勾选）

```
nodes: 7
edges: 0
layers: cornerstone 0 / derived 0 / isolated 7
diagnostics: unresolved_references 112（reason 全部为 insufficient_identity）
pagerank: verified_pair_count 0, uniform_baseline 0.25, iterations 1
```

图谱诊断显示 112 条参考文献全部 `insufficient_identity`、verified 边对为 0，
因此画布**真实结果就是 0 条边、7 个孤立节点**——这是数据现状，不是前端漏画边。
截图下方说明文字同步显示“只画 0 条已核验边……孤立节点 7 个照常显示”。

截图：[docs/images/06-graph-canvas.png](../docs/images/06-graph-canvas.png)
（画面：7 个灰色孤立节点、无连线、含四色图例与上述说明文字）

## 四、任务 2：思考过程时间线

新文件 `frontend/components/TraceTimeline.tsx`，接在 `/qa` 页的问答结果与综合结果下方，
并新增“使用 LangGraph 编排（?agent=true）”开关。

展示内容：

- 元数据：`engine` / `attempts`（含上限）/ 轨迹节点数 / 轨迹总耗时 / `validated` / `fallback_reason` / `checkpointing` 与 `external_tracing`
- 节点时间线：按轨迹原始顺序逐条展示 `plan → retrieve → qa → validate`，每条带轮次、耗时（ms）、证据数、校验结果；**校验驳回时原样展示 `validation_error` 原文**
- 分轮小结：把 10 条轨迹按 attempt 归组，展示每轮节点序列、耗时、证据数与结论
- 工具调用：`tool_name` / `origin`（`model_function_call` 高亮）/ 轮次 / `tool_call_id` / 入参摘要 / 返回摘要（含证据数）/ 耗时 / 状态
- 两个模型调用表：Agent-Meta 的 `model_calls` 与 QA-Meta 的 `model_calls`

### 真实冒烟（`?agent=true`）

```
HTTP 200
x-scholargraph-agent-meta: {"engine":"langgraph","attempts":1,"max_attempts":3,
 "fallback_reason":"MODEL_CONFIGURATION_UNAVAILABLE","trace":[
   {"node":"plan","elapsed_seconds":2e-06,"attempt":0,"evidence_count":0,"validation":null,...},
   {"node":"retrieve","elapsed_seconds":2e-06,"attempt":1,"evidence_count":0,...},
   {"node":"qa","elapsed_seconds":0.074124,"attempt":1,"evidence_count":0,...},
   {"node":"validate","elapsed_seconds":0.009111,"attempt":1,"evidence_count":0,"validation":true,...}],
 "tool_calls":[],"model_calls":[],"checkpointing":false,"external_tracing":false,"validated":true}
```

页面渲染结果（与截图一致）：

- 编排引擎 langgraph、轮次 1/3、轨迹节点 4、总耗时 31.0 ms、最终校验通过
- `fallback_reason = MODEL_CONFIGURATION_UNAVAILABLE`，页面用醒目提示写明“本次走回落路径……下面展示的是真实发生的节点轨迹与耗时，不是模型推理过程”
- 时间线四行：plan 0.0ms（第0轮）→ retrieve 0.0ms → qa 29.8ms → validate 1.2ms（校验通过）
- 工具调用：**本次无工具调用**，页面写明原因（回落路径下没有模型参与，不会产出 tool_calls），不补造记录
- QA-Meta：**后端未返回**，页面写明仅 deepseek 模式且配置 Key 时返回，不编造服务商/模型名/耗时

截图：[docs/images/07-qa-trace-timeline.png](../docs/images/07-qa-trace-timeline.png)

### 多轮重试渲染：未能用实时请求验证（如实说明）

实时请求只有 1 轮（无 Key → 走回落，不会触发“校验失败重新检索”）。
为验证多轮渲染逻辑，用后端验收报告
`tests/reports/real-model-orchestration-results.json` 中**一次真实三轮轨迹**
（非本次实时请求、非手写）跑同一套分轮逻辑，输出如下：

```
轨迹节点数: 10 | 分轮数: 4

轮次 | 节点序列                        | 耗时(ms) | 证据 | 校验结果
0    | plan                           |   1670.7 |    0 | 未进入校验
1    | retrieve → qa → validate       |   6708.4 |   24 | 驳回：同一Chunk的摘录跨度超出600字符。
2    | retrieve → qa → validate       |   6638.9 |   20 | 驳回：同一Chunk的摘录跨度超出600字符。
3    | retrieve → qa → validate       |   6382.0 |   20 | 通过
```

逐节点明细（含驳回原因原文）：

```
  plan      第0轮   1670.7ms 证据  0 —
  retrieve  第1轮    111.1ms 证据 24 —
  qa        第1轮   6595.0ms 证据 24 —
  validate  第1轮      2.3ms 证据 24 驳回 → 同一Chunk的摘录跨度超出600字符。
  retrieve  第2轮   1742.9ms 证据 20 —
  qa        第2轮   4893.0ms 证据 20 —
  validate  第2轮      3.0ms 证据 20 驳回 → 同一Chunk的摘录跨度超出600字符。
  retrieve  第3轮   1867.0ms 证据 20 —
  qa        第3轮   4505.0ms 证据 20 —
  validate  第3轮      9.9ms 证据 20 通过
```

结论：分轮归组与驳回原因展示逻辑正确（第 1、2 轮驳回、第 3 轮通过）。
但**该多轮过程未在页面上实时跑出**，实时验证需要配置真实模型与 Key，本次环境不具备。

## 五、任务 3：预警与元数据展示

### 3.1 去重预警横幅

`uploadSingle` 改为读取 `X-ScholarGraph-Dedup-Warning`，用 `decodeURIComponent`
做百分号解码后展示；`uploadBatch` 读取成功项上的可选 `warning` 字段并在成功项下方展示。

真实触发过程：库内已有 `1706.03762v7`（15 页）。用 pypdf 删去末页生成自制样例
（不同字节、正文高度相似，与项目其他测试输入同为自制样例），经前端代理上传：

```
HTTP=201
x-scholargraph-dedup-warning: %E5%B7%B2%E6%A3%80%E5%87%BA...（百分号编码）
x-scholargraph-dedup-warning-encoding: percent-encoded-utf-8
```

解码后原文：

```
已检出文本变化，但文本相似度和版本序号不能证明新版质量更高；需人工核对差异。
```

页面横幅显示：标题「版本重复预警」+ 上述原文 + 「建议保留库里较新版本」建议 +
说明该原文来自响应头 UTF-8 百分号编码、前端解码后展示。

截图：[docs/images/08-upload-dedup-warning.png](../docs/images/08-upload-dedup-warning.png)

### 3.2 两个元数据响应头

`readMetaHeaders` 统一读取 `X-ScholarGraph-QA-Meta` 与 `X-ScholarGraph-Agent-Meta`，
同样做百分号解码后 `JSON.parse`，交给时间线上方的元数据区与两个模型调用表。
本次 Agent-Meta 有值、QA-Meta 未返回，页面如实区分（见第四节）。

## 六、npm run build 结果原文

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
├ ƒ /papers/[id]                         2.72 kB         109 kB
├ ƒ /qa                                  4.78 kB         114 kB
├ ƒ /read/[id]                           2.29 kB         108 kB
├ ƒ /retrieval                           3.17 kB         109 kB
├ ƒ /upload                              4.17 kB         110 kB
└ ƒ /writing                             2.79 kB         108 kB
+ First Load JS shared by all             103 kB

○  (Static)   prerendered as static content
ƒ  (Dynamic)  server-rendered on demand
```

9 条业务路由齐全（`/`、`/papers/[id]`、`/read/[id]`、`/qa`、`/graph`、`/retrieval`、
`/writing`、`/upload` 与同源代理路由，另含 `_not-found`）。`/graph` 因引入 Cytoscape
从 2.54 kB 增至 139 kB，为已知代价。

（构建输出中夹杂 `Warning: Ignoring extra certs ... system-ca-bundle.pem` 若干条，
为本机证书包路径缺失的告警，与本项目代码无关，构建结果仍为 EXIT 0。）

## 七、本单未完成 / 受限于环境的事项（如实列出）

1. **图谱真边为 0**：当前库内 7 篇论文的 112 条参考文献全部 `insufficient_identity`，
   verified 边对为 0，画布只能显示孤立节点。已核验边的绘制效果（连线、箭头、基石高亮的对比）
   **未在真实数据下呈现过**。
2. **多轮重试未实时跑出**：需要 `SCHOLAR_GRAPH_QA_MODE=deepseek` 与 Key，本环境未配置，
   仅用后端记录的真实三轮轨迹核对了分轮逻辑。
3. **工具调用列表为空**：同上，Function Calling 由真实模型发起，回落路径下必然为空，
   页面已写明原因而非留空表格。
4. **QA-Meta 的服务商/模型名/耗时三个字段未展示出真实值**：后端未返回该头，
   前端按“未返回”处理，未填充任何值。
5. 截图采用区块裁剪（非整页）：图谱页整页高达 18884 px，整页图不可用，
   故按区块截图，画面为该区块的真实渲染。

## 八、样式约束自查

沿用已确认 token：纸感暖白 `#F7F6F3`、深松绿 `#14544B`、赭石 `#B4551D`；
新增样式只用 1px 边框与留白分层，未新增渐变、未新增圆角阴影卡片、未使用 emoji 作图标
（图例为纯 CSS 色块，按钮为文字按钮）。
