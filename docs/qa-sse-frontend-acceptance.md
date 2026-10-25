# 问答 SSE 前端接入验收报告

日期：2026-10-25。执行人：WorkBuddy（前端）。工作目录 `D:\AI_Workspace\Tasks\scholar-graph`，分支 main。

开工前主干 `0674f9574c41afb99e847db91e4abad284c9aafe`，`git pull` 原文 `Already up to date.`，工作区干净。

本单只改 `frontend/` 与 `docs/`：**未改后端代码、未改 contracts/**。
事件协议依据 `backend/README.md`「问答SSE流式端点」（第 231–263 行）与
`backend/scholar_graph/qa_sse.py`、`orchestration.py` 的实际发射字段。

## 一、代理改动说明（任务 1）

文件：`frontend/app/api/backend/[...path]/route.ts`

改动前：代理统一 `const body = await upstream.text()` 再回传。SSE 会被一次性缓冲到
流结束才吐出，页面拿不到任何增量——这正是后端 README 第 261 行点名的问题
（「当前前端同源代理先调用 upstream.text()，会缓冲SSE」）。

改动后：按上游 `content-type` 分流。

| 上游类型 | 代理行为 |
| --- | --- |
| `text/event-stream` | 直接 `new Response(upstream.body, …)`，不缓冲、不解析、不拼装事件；保留后端 `Cache-Control: no-cache, no-transform` 与 `X-Accel-Buffering: no`，另设 `content-encoding: none` 防止中间层压缩把增量攒到结束 |
| 其他（含错误体） | 维持原样回传正文，保证后端三字段错误体原封不动到达前端 |
| 上游不可达 | 仍返回 502 + `{error_code:"NETWORK_ERROR", message, details:null}` |

代理层同时保留原有能力：`x-sg-upstream-url`、`x-sg-upstream-status` 两个诊断头，
以及原样带回上游所有 `X-ScholarGraph-*` 头。POST 时额外转发客户端的 `Accept`
（SSE 请求必须带 `Accept: text/event-stream`）。

**代理不改事件内容的验证**：同一请求分别直连后端（8010）与经代理（3100）抓取，
各 11 个事件块；把 `elapsed_seconds` 归一化后逐块比对，**差异块索引为空**
（字节数 3303 vs 3301 的差值只来自两次运行的耗时数字长度不同）。

## 二、事件处理对照表（任务 2）

文件：`frontend/lib/sse.ts`（解析与取数）、`frontend/components/StreamTimeline.tsx`（渲染）

| event | 前端处理 | 页面呈现 |
| --- | --- | --- |
| `mode` | 存 mode / token_streaming / fallback_reason / message | 顶部模式条：`fallback_reason` 非空或 `token_streaming=false` 显示「回落模式、非 token 流式」黄色标签，否则显示「真实上游 token 增量」；下方原样显示后端 message |
| `node_start` | 追加一行，状态「执行中」 | 节点时间线新增行（节点名、轮次、耗时显示"进行中"、证据数） |
| `node_end` | 回填同一 node+attempt 且未完成的最后一行 | 填耗时、证据数、status；`validation=false` 时**原样展示 `validation_error` 原文**；`status=failed` 展示 `reason` |
| `tool_start` | 追加一行，状态「执行中」 | 工具调用表新增行（工具名、origin、tool_call_id、轮次） |
| `tool_end` | 按 `tool_call_id` 回填 | 填返回证据数、耗时、status |
| `token` | 追加到草稿字符串，计数 +1 | **增量区固定标注「草稿（未校验）」**，并写明 `channel=model_json_draft`、`verified=false`、不是 final.answer 的逐字拼接、事件条数不等于服务商 token 数 |
| `final` | 校验形状后存入 answer | 「最终答案（仅 final 事件到达后展示）」区，用 QaAnswerView 展示答案、四字段锚点、数字事实校验 |
| `error` | 存错误原文并结束 | 显示「流式问答出错（已结束，不编造答案）」+ error_code/message + 原始 envelope |
| `done` | 标记流结束 | 结束条显示 `done.status`、token_streaming、fallback_reason、attempts/上限 |
| `: keep-alive` | 忽略（不计数、不渲染） | 无 |
| 断流/客户端异常 | 捕获后写入错误区 | 同 error，不补答案 |

解析细节：按 `\n\n` 切块，残留部分留在 buffer 等下一个分块；`data` 多行用 `\n` 合并；
单块 JSON 解析失败不中断整条流。

三条纪律的实现位置：

1. **事件到一条画一条**：`handleEvent` 每次 setState 即重渲染，无节流、无攒批。
2. **草稿不得冒充最终答案**：草稿与 `answer` 是两个独立状态；
   未收到 `final` 时最终答案区固定显示「尚未收到 final 事件……草稿不得冒充最终答案」。
3. **错误即停**：`error` 事件到达即展示原文；`done` 到达标记结束；
   AbortError（用户点停止）不写入任何结果。

## 三、回落模式冒烟（无 Key，必验项）

环境：本地真实 TCP 后端 `http://127.0.0.1:8010`（`SCHOLAR_GRAPH_DATA_DIR=data/module-one`，
库内 3 篇自制样例），前端 `npm run start -- -p 3100` 且
`NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8010`。
未设置 `SCHOLAR_GRAPH_QA_MODE` / `DEEPSEEK_MODEL` / `DEEPSEEK_API_KEY`。

### 3.1 代理时序（证明不缓冲）

用一个**临时假上游**（仅按 SSE 帧格式每 1.5 秒发一个事件，用于验证透传时序，
不是业务数据、不进仓库）指向前端，逐分块记录到达时刻：

```
HTTP 200
content-type: text/event-stream; charset=utf-8
content-length: (未设置)
cache-control: no-cache, no-transform
x-accel-buffering: no
---
分块 1 @ 1.55s | id: 1 event: mode ...
分块 2 @ 3.03s | id: 2 event: node_start ...
分块 3 @ 4.54s | id: 3 event: node_end ...
分块 4 @ 6.05s | id: 4 event: token ...
分块 5 @ 7.56s | id: 5 event: token ...
分块 6 @ 9.06s | id: 6 event: final ...
分块 7 @ 10.57s | id: 7 event: done ...
结束 @ 12.08s，共 7 个分块
```

分块按 ~1.5 s 间隔依次到达，说明代理是流式透传而非攒到最后。

### 3.2 真实后端事件流（直连与经代理）

```
事件序列：mode node_start node_end node_start node_end node_start node_end node_start node_end final done
事件数：11（直连与经代理一致）；keep-alive：0（本轮很快，未触发 10 秒心跳）
```

`mode` 事件原文：`{"mode":"extractive","token_streaming":false,"fallback_reason":"EXTRACTIVE_MODE","message":"回落模式、非 token 流式"}`

`done` 事件原文（节选）：`{"status":"completed","token_streaming":false,"fallback_reason":"EXTRACTIVE_MODE","metadata":{"engine":"langgraph","attempts":1,"max_attempts":3,...,"validated":true}}`

### 3.3 页面实际渲染（Chrome 无头，真实点击）

```
已收事件 11 条 · 节点 4 · 工具 0
回落模式、非 token 流式
mode extractive / token_streaming false / fallback_reason EXTRACTIVE_MODE

节点时间线（随流实时推进）
规划 plan      轮次1  11.1 ms  证据0  completed  —
检索 retrieve  轮次1   1.6 ms  证据1  completed  —
问答 qa        轮次1   8.7 ms  证据1  completed  —
校验 validate  轮次1   3.1 ms  证据1  completed  通过

工具调用：尚无工具调用事件（回落模式不构造模型客户端，不会虚构模型工具调用）
增量区[草稿（未校验）]：本次没有 token 增量（回落模式不发 token，最终答案整段到达）
最终答案：refused=false、【证据 A】The synthetic study uses 18 samples and cites [1].
         锚点 p.1 · …-p0001-c00004 · 1 Introduction；数字事实校验 passed
流已结束：done.status completed / token_streaming false / fallback_reason EXTRACTIVE_MODE / attempts 1 / 3
```

截图：[docs/images/09-qa-sse-stream.png](../docs/images/09-qa-sse-stream.png)

### 3.4 错误分支

（a）SSE 开始前的 HTTP 错误（经代理）：

```
不存在论文 → HTTP 404 {"error_code":"PAPER_NOT_FOUND","message":"无该论文已发布的页面批次。","details":null}
空问题     → HTTP 422 {"error_code":"VALIDATION_ERROR","message":"请求参数不合法。","details":null}
```

（b）连接中断（页面加载后停掉后端，再点「开始流式问答」）：

```
已收事件 0 条 · 节点 0 · 工具 0
流式问答出错（已结束，不编造答案）
NETWORK_ERROR（HTTP 502）无法连接后端 http://127.0.0.1:8010/api/v1：fetch failed
最终答案区：尚未收到 final 事件。未收到 final 时不展示任何答案，草稿不得冒充最终答案。
```

截图：[docs/images/10-qa-sse-error.png](../docs/images/10-qa-sse-error.png)

## 四、deepseek 模式：**未验**（无 Key，如实标记）

按后端 README 第 257 行，deepseek 模式才会发 `token` 事件与真实 Function Calling 的
`tool_start/tool_end`；本环境未配置 `SCHOLAR_GRAPH_QA_MODE` / `DEEPSEEK_MODEL` /
`DEEPSEEK_API_KEY`（已确认三个变量均未设置），因此：

- **`token` 增量（草稿）未在真实数据下呈现过**——只有回落模式下的「0 增量」状态。
- **`tool_start` / `tool_end` 未在真实数据下呈现过**——回落模式必然为空。
- **流内 `error` 事件未验**——需要 deepseek 模式下上游连接/协议失败才会触发。
- **`X-ScholarGraph-QA-Meta` 的服务商/模型名/耗时仍无真实值**（该头与 SSE 无关，为上一单遗留）。

以上四项前端均已实现并按“无数据/未返回”如实显示，**没有填任何值、没有伪造事件**。
要补齐验证，需要把可用的 DeepSeek Key 注入后端进程（只用环境变量，不写文件、不进 Git），
重跑后补事件日志。

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
├ ƒ /papers/[id]                         2.68 kB         109 kB
├ ƒ /qa                                  7.81 kB         117 kB
├ ƒ /read/[id]                           2.29 kB         108 kB
├ ƒ /retrieval                           3.17 kB         109 kB
├ ƒ /upload                              4.12 kB         110 kB
└ ƒ /writing                             2.79 kB         108 kB
+ First Load JS shared by all             103 kB

○  (Static)   prerendered as static content
ƒ  (Dynamic)  server-rendered on demand
```

9 条业务路由齐全（`/`、`/papers/[id]`、`/read/[id]`、`/qa`、`/graph`、`/retrieval`、
`/writing`、`/upload` 与同源代理路由）。`/qa` 从 4.78 kB 增至 7.81 kB（流式组件）。

（构建日志中夹杂本机 `system-ca-bundle.pem` 路径缺失的告警，与项目代码无关。）

## 六、样式约束自查

沿用已确认 token（纸感暖白 `#F7F6F3`、深松绿 `#14544B`、赭石 `#B4551D`）；
新增只有模式条/结束条的 1px 边框与浅底，未加渐变、未加圆角阴影卡片、未用 emoji 图标。

## 七、本单未完成事项汇总

1. deepseek 模式的 token 草稿、模型工具调用、流内 error 事件**均未实时验到**（需 Key）。
2. 跨篇对比仍走同步端点，未接流式（后端流式端点目前只有单篇）。
3. 假上游仅用于透传时序验证，不进入仓库，也不作为任何业务数据来源。
