# 前端模块三阅读器与新页面接线冒烟记录

日期：2026-10-25。执行人：WorkBuddy（前端主力）。工作目录 `D:\AI_Workspace\Tasks\scholar-graph`，分支 main。

开工前主干 `02ddb853b870160029042ed911e4f25a574b7787`，`git pull` 原文 `Already up to date.`，工作区干净。

本记录只记录**实际发生的请求与页面渲染结果**，不代表任何能力已通过验收；
官方三用例未运行，输入全部为自制样例 PDF，不是真实论文。

## 环境

| 项 | 值 |
| --- | --- |
| 后端启动 | `backend/.venv/Scripts/python.exe -m uvicorn scholar_graph.api:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log` |
| 取数基地址 | `http://127.0.0.1:8000/api/v1` |
| 前端构建 | `npm run build`（Next.js 15.5.28），EXIT_CODE=0 |
| 前端服务 | `npm run start`，`http://localhost:3000` |
| 浏览器侧调用路径 | 同源代理 `/api/backend/*` → `/api/v1/*`；服务端组件直连 |
| 库中论文 | 3 篇（v1、v7、扫描件各 1） |

## 页面 HTTP 状态

```
/            200
/qa          200
/graph       200
/retrieval   200
/writing     200
/upload      200
/read/{id}   200
```

## 逐条真实请求结果

以下请求全部经前端同源代理发出，与各页面客户端组件走同一条路径。

### 1　POST /api/v1/papers/{id}/qa（正常提问）

```
refused = False
answer  = 【证据 A】
          The synthetic study uses 12 samples and cites [1].
anchors = 1  paper-cb43a78f…3c20-p0001-c00004
numeric = passed
```

### 2　POST /api/v1/papers/{id}/qa（错误前提，应拒答）

```
refused = True
answer  = 拒答：本文本无相关证据，未检索到足以回答该问题的原文或所需数值；不能据此断言全文未报告。
```

页面按 refused=true 原样展示拒答原因，未把它渲染成答案。

### 3　POST /api/v1/compare

```
evidence_table = 2 行
per_paper      = 2 篇
synthesis      = 原文并列：The synthetic study uses 12 samples and cites [1]. [E1] | 原文并列：The synthetic …
```

### 4　GET /api/v1/graph（v1 + v7）

```
nodes = 2  ['isolated', 'isolated']
edges = 0  []
layers = cornerstone 0 / derived 0 / isolated 2
future_work = worth 0 / excluded 0 / unverifiable 0 / checks 0
diagnostics = unresolved_references 2 / pagerank iterations 1
```

本次样例两篇论文互不引用，故为 2 个孤立节点、0 条边，并把 2 条无法对应的引用登记进
`unresolved_references`。页面按此原样展示，未画成已核验边。

### 5　POST /api/v1/retrieval/search

响应头（由同源代理原样带回）：

```
x-scholargraph-search-mode: lexical
x-scholargraph-search-reason: OK
x-scholargraph-vector-status: NOT_ENABLED
```

```
items = 3 / total = 3
  relevance 0.6148722459609013 | method lexical | p.1 | The synthetic study uses 12 samples.
  relevance 0.507150695750987  | method lexical | p.1 | The synthetic study uses 12 samples and cites [1].
  relevance 0.4836358532401687 | method lexical | p.1 | The synthetic study uses 18 samples and cites [1].
```

页面把 mode 显示为「词法兜底 lexical」，不把词法说成向量。

### 6　GET /api/v1/recommendations（种子 = v1）

响应头 `x-scholargraph-recommendation-reason: OK`

```
items = 2 / total = 2
  score 50.0 | signals {graph_neighbor 0, pagerank_normalized 1.0, recency 1.0, github_link null}
             | missing ['github_link'] | reasons 2
  score 35.0 | signals {graph_neighbor 0, pagerank_normalized 1.0, recency null, github_link null}
             | missing ['publication_year', 'github_link'] | reasons 1
```

### 7　POST /api/v1/frameworks（v1 + v7）

```
schema 1.2.0 | chapters 2
  isolated | 独立论文：Synthetic ScholarGraph Study | writing_points 1 | anchors 1
  isolated | 独立论文：Synthetic ScholarGraph Study | writing_points 1 | anchors 1
```

### 8　POST /api/v1/reviews（使用上一步框架 + 1 条额外要求）

```
mode = extractive | unverifiable_count = 2 | chapters = 2
  独立论文：… | points 2
     - verified      | Synthetic ScholarGraph Study                    | req: None
     - unverifiable  | 未在本章摘录材料中检出所需要点；不可验证，未补写结论。 | req: 补充实验设置
  独立论文：… | points 2（同上结构）
```

### 9　POST /api/v1/charts/csv（自制 CSV：samples/epochs 三行）

```
chart_id   = chart-28f389487c8a2ea61db3b8808e215b4cbd092775750978a18871cc65483b14b1
chart_type = bar
series     = [('samples', [12.0, 18.0, 20.0])]
caption    = CSV values: 12, 18, 20.
image_ref  = data:image/png;base64,…（18658 字节的真实 PNG 数据 URI）

numeric_checks:
  value 12.0 | row 2 | col samples | verified True | csv_ref csv-984b1350bdc9…
  value 18.0 | row 3 | col samples | verified True | csv_ref csv-984b1350bdc9…
  value 20.0 | row 4 | col samples | verified True | csv_ref csv-984b1350bdc9…
```

图注三个数字与 CSV 三个源单元格逐一对应，页面以表格展示该回溯关系。

## 阅读器页渲染

对 v7 请求 `/read/{id}`，页面渲染结果：

```
章节导航           有
文末条目           有
版式原文渲染待后端文件端点  有
引用对应关系        有
翻译功能待后端模型接入     有
划词              有

章节条目数 : 5（1 个标题 + 4 个章节）
引用按钮数 : 2
导航区片段 : 章节导航 4 个章节 · 8 个分块 (未分章节) p.1 · 2 块 / 1 Introduction p.1 · 2 块 / 2 Protocol p.1 · 2 …
```

8 个分块与后端 v7 的分块数一致。阅读材料为 Chunk 正文，未渲染 PDF 版式原文。

## 断后端验证（禁止静默回落）

停掉 uvicorn 后请求页面，结果为：

列表页：

```
论文列表取数失败
接口地址 http://127.0.0.1:8000/api/v1/papers?page=1&page_size=20
状态码   无响应
错误码   NETWORK_ERROR
原因     无法连接后端：fetch failed
后端未返回数据，页面不显示任何替代数据。请确认后端已启动且地址一致。

是否残留论文条目: False
```

阅读器页：

```
取数失败 · 未取得该论文
接口地址 http://127.0.0.1:8000/api/v1/papers/paper-5d99397e9a37ee758723e7e845f5630ac8c5c88d9b60888946340fa4fa93a7d2
状态码   无响应
错误码   NETWORK_ERROR
原因     无法连接后端：fetch failed
```

两处都显示了真实接口地址与状态码，且没有回落到任何替代数据。

## 本单未做的事（如实列出）

- 未运行官方三用例；所有输入为自制样例，不代表真实论文质量。
- 未联调真实翻译端点：后端没有翻译端点，划词只展示原文与锚点。
- 未渲染 PDF 版式原文：后端没有原文件下载端点，前端不构造该端点。
- 未调用真实大模型：问答与草稿均为本地确定性摘录，与后端口径一致。
- 阅读器子资源取全量时单次上限为 20 页、每页 100 条，超出会标记「材料可能不完整」；
  本次 3 篇论文均未触发。
