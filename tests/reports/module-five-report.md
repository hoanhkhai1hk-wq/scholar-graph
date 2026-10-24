# 模块五引用图谱与第 0 项存储修复交付报告

日期：2026-10-24（Asia/Shanghai），在 2026-10-30 时间目标前执行。工作目录 D:\AI_Workspace\Tasks\scholar-graph，分支 main。
开工前主干 `de74511f9f579af910bd683820b409698a301020`，工作区干净；git pull --ff-only 原文 `Already up to date.`。

实施顺序：先重复旧失败测试 → 受控锁诊断及修复 → 第 0 项全量 148 通过 → 新增图谱契约与实现 → 独立 HTTP 验收 → 最终全量 **186 通过，0 失败、0 错误、0 跳过**。

所有图谱输入是**自制多篇落盘契约记录、非官方 pdf/ 用例**；没有运行官方三用例，没有以合成图谱冒充真实论文解析质量评测。图谱与未来方向过程均不使用真实大模型、向量库、API Key 或外部检索，未读取 .env。

## WinError 5 根因结论与缓解

**本轮未能自然复现历史 WinError 5，未定位实际占用者，不能宣称已确定是杀毒软件、外部进程或 ACL。** 修复前，旧四项去重端点测试加 101 条分页测试连续10轮，共50项全过。原 write_json 已用 with 关闭自身文件句柄并 flush/fsync，没有发现本程序句柄未关闭的证据。

受控 CreateFileW 实验：刻意打开目录且不共享删除/重命名权限，原始 rename 失败，实际为 **WinError 32**；0.12秒后释放句柄，退避重试后整组成功发布。它证明共享锁机制与等待缓解，不等于复现历史错误码5，也不证明历史占用进程。原始结果分别见 [修复前10轮](graph-storage-before.json)、[真实句柄实验](graph-storage-lock-probe.json)。

修法：新增 atomic_io.windows_retry，用于同盘目录原子 rename、状态快照 replace 及清理。只在 Windows 且 winerror=5/32/33 时有限重试，最多8次，等待0.025、0.05、0.1、0.2、0.4、0.8、1.6秒；每个操作最多累计等待3.175秒。临时占用者释放句柄后可继续原子操作；永久访问拒绝在最后一次原样抛出，非锁错误不重试。不复制半组目录、不覆盖既有记录、不修改权限或系统安全配置、不吞掉失败。

新增测试确定性验证三种暂态错误、永久失败仍抛出、非锁错误不重试以及真实 Windows 共享锁释放；永久模拟失败时不发布目标、不泄漏临时目录。修复后同样10轮50项全过，见 [修复后10轮](graph-storage-after.json)。第0项在图谱写入前的全量原文：

```text
148 passed in 95.78s (0:01:35)
```

[graph-storage-regression.xml](graph-storage-regression.xml) 保留原140项+8项新增测试结果。完整机制、边界与 Microsoft 共享模式文档见 [存储报告](graph-storage-report.md)。根因未知仍是诊断限制，修复不能保证永久锁或错误 ACL 永不失败。

## 契约 v1.2：仅新增图谱两类

| 记录 | Schema | example | 顶层字段数（含版本） |
| --- | --- | --- | ---: |
| GraphNode | contracts/graph-node.v1.2.schema.json | contracts/graph-node.v1.2.example.json | 6 |
| GraphEdge | contracts/graph-edge.v1.2.schema.json | contracts/graph-edge.v1.2.example.json | 5 |

GraphNode 为 schema_version、paper_id、title、year、pagerank、level；GraphEdge 为 schema_version、from_paper_id、to_paper_id、anchor、status。全字段必填、禁额外字段，锚点全四字段。无 CitationLink 的已知参考目标用 anchor=null、status=unverified 显式表达不可验证，不能伪造引用锚点。

原九份 Schema 与九份 example 的 Git blob 全部与开工基线一致，哈希清单见实跑 JSON；字段数仍是 PaperMeta14、Chunk11、ReferenceEntry10、CitationLink6、QAAnswer5、DedupDecision7、DiffSummary6、ParseStatus7、ChartOutput7。没有修改必填性、类型或旧字段。CONTRACTS.md 升级集合版本并登记两类新记录；综述框架不在本轮 v1.2 图谱部分，明确留待后续单。

ContractGate 接受完整原九类或完整十一类，图谱两份须成对存在。历史边界脚本明确继续只验证原 v1/v1.1，实际 **722/722 通过**；v1.2 由新增图谱契约及语义测试单独覆盖，没有把新例混入旧722数量。新增示例的标题/年份/源锚点也与原 PaperMeta/Chunk 示例对齐。

## 构图、PageRank 与分层规则

仅加载指定集合的已发布四类记录。引用目标按 DOI 精确匹配，其次 arXiv 去版本基号；无这两项才用标题+年份+作者完整匹配。已有 DOI 不匹配不能回退标题猜边。多版本身份歧义、集合外引用、身份信息不足登记 unresolved_references，不新造节点。

边方向为引用方→被引方，verified 必须对应真实 CitationLink/ReferenceEntry/Chunk。正文多次引用可保留不同 Chunk 的边，但算法仅使用去重后的 verified 论文对，每对单位边权。unverified 边展示但不贡献排名或未来方向解决证据。节点 title/year 原样来自 PaperMeta。

显式 PageRank 幂迭代，d=0.85，初值1/N，悬挂节点质量均匀回流：

```text
PR_next(v) = (1-d)/N
             + d * sum(PR(u)/outdegree(u), 对所有 u→v)
             + d * sum(PR(u), 对所有悬挂节点u)/N
```

L1残差≤1e-12 时收敛，最多1000轮；不收敛抛 INDEXING_FAILED，不返回伪造分数。算法约定参考 [PageRank 官方技术说明](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.link_analysis.pagerank_alg.pagerank.html)，实际实现为本地显式 Python 迭代。

分层阈值：没有 verified 入/出边为 isolated；其余中有 verified 入边且 PR>1/N+1e-12 为 cornerstone；其他为 derived。1/N 是所选图均匀基线，阈值和排名随选择集合变化，不是全球影响力或论文质量结论。孤立指已核验图，不把不可靠边当确定连接。列表按排名降序、id升序展示。

测试对A→B→C加孤立D的已知图使用独立解析解：令d=0.85，a=1/(4+2d+d²)，则PR(A)=PR(D)=a、PR(B)=(1+d)a、PR(C)=(1+d+d²)a。另验证均匀循环、单个孤立节点、重复引用不加权、非收敛报错。

## Future Work 时间过滤

沿用 QAAnswer 原文摘录/四字段锚点/数字校验门禁。仅提取独立行明确标记 Future work / Future direction / 未来工作 / 未来方向 后的主题，单句≤600字符；同篇相同主题去重，不跨块拼接。

排除同时要求：候选论文有明确肯定的“Resolved future direction: 同主题”等白名单声明；主题仅做大小写、空白及末尾句号归一后完全相同；PaperMeta.year 已知且严格晚于来源；解决声明所在 Chunk 有 verified 引用指向来源论文。source 与 resolution 都是完整 QAAnswer，checks 保存接受/拒绝及原因。年份不明不能作时间结论；同年也不算更晚。

计划、否定、部分词相似、无引用锚点、借用其他 Chunk 的引用都不排除。原年份未知或匹配解决声明的时间不明进入 unverifiable。worth_exploring 仅表示在所选论文中尚未证明已解决，不宣称全球未解决；excluded 是作者明确解决声明与时间/引用核验成立，不等于独立科学复现。普通叙述、语义改写及未匹配的主题会漏召回，该精度/召回没有真实论文评测。

## HTTP 独立实测

端点 `GET /api/v1/graph?paper_ids=paper-graph-a&paper_ids=paper-graph-b&paper_ids=paper-graph-c&paper_ids=paper-graph-d`，响应200。
输出固定 nodes、edges、layers、future_work、diagnostics；节点/边使用新契约，未来事实证据使用原 QAAnswer。它是所选集合派生的图资源，不套论文列表分页壳。1–100个不同id；非法选择422，任何论文不存在整包404，错误体仍为三字段。

实跑脚本源码提交 `e4f1174554967137e9323e11ef29d561246cdae0`，其后仅校正新契约示例与文档、增加示例一致性测试，运行算法未变。输入在 data/module-five-release/ 下，是手工合成并真实落盘的四类契约 JSON，不调用 PDF 解析器。完整请求、响应、输入文件SHA-256与18份旧契约Git哈希见 [module-five-smoke.json](module-five-smoke.json)。两组查询前后均核对输入文件字节不变。

主样例 **4节点、2边、2条 verified**，A→B→C，D孤立：

| 节点 | 年份 | PageRank | 层级 |
| --- | ---: | ---: | --- |
| paper-graph-a | 2024 | 0.155702608019 | derived |
| paper-graph-b | 2020 | 0.288049824835 | cornerstone |
| paper-graph-c | 2018 | 0.400544959128 | cornerstone |
| paper-graph-d | 2025 | 0.155702608019 | isolated |

均匀基线0.25，基石按排名为C、B。33轮收敛，残差8.182898802999716e-13。未来方向 **3→2**，排除1：C(2018)的cross-lingual transfer有B(2020)明确解决原文及B→C真实引用。证据锚点分别是C的chunk-graph-c / page1 / Future Work和B的chunk-graph-b / page1 / Main；完整四字段在JSON。document-level extraction因B明确否定解决而保留，robust noisy labels无合格后续解决证据而保留。

缺锚点对照样例同为4节点2边，其中1条unverified/null anchor；排名只用另一条verified边，基石仅B。即使B写有解决声明，也不能借缺失引用排除方向，**3→3，排除0**。这证明没有把无锚点边或单纯主题/年份匹配当解决证据。

## 最终全量回归

```text
186 passed in 99.42s (0:01:39)
```

[module-five-pytest.xml](module-five-pytest.xml)：186总数、186通过、0失败、0错误、0跳过，包含原140项和新增46项，真实MinerU/PaddleOCR及原同源代理测试均执行。

| 本轮新增测试组 | 数量 |
| --- | ---: |
| Windows原子发布 | 8 |
| 图谱契约/示例 | 4 |
| 引用构图与PageRank | 10 |
| 未来方向/时间/锚点门禁 | 16 |
| 图谱API | 8 |

测试覆盖身份冲突与歧义、孤立节点、重复引用、真实Chunk关联、无锚点边、错误页码/论文/引用、假分数/假节点/假原文、同年及更早论文、未知年份、否定与计划、部分匹配、错误Chunk引用、选择范围及错误体。pip check 原文 `No broken requirements found.`。

## 范围、协作与复现

仅更改 backend/、contracts/、tests/ 和授权 docs/api-draft-v1.md；frontend/、prompts/、experiments/、test-records/、docker-compose.yml 及其他docs零改动。没有新增检索、框架、图表、推荐或综述接口。原 QA/比较功能和九类记录保持兼容；旧实跑脚本明确排除新增图谱路由/记录以维持原证据范围，不修改旧报告或减少原测试。

交给用户转达 WorkBuddy：按本轮 GraphNode/GraphEdge v1.2 与 API 草案的 /graph 形状对接前端；本轮没有进行图谱页面接入或验收，不直接联系其他工具。综述框架仍交总指挥另单。

```powershell
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --basetemp data/module-five-reproduce-tests --junitxml data/module-five-reproduce-tests.xml
backend/.venv/Scripts/python.exe tests/run_module_five_smoke.py --output-root data/module-five-reproduce --report data/module-five-reproduce.json
backend/.venv/Scripts/python.exe tests/verify_contract_boundaries.py --report-dir data/module-five-legacy-boundaries
```

输出根目录须用新的英文目录，smoke拒绝覆盖。Windows真实句柄测试只在Windows执行；本机为Windows，未跳过。原同源代理测试依赖现有Node/TypeScript，本机依赖存在并执行。数据/PDF/缓存/.env不进Git。

## 提交与对应文件

| 完整提交哈希 | 对应文件 |
| --- | --- |
| 9a20186ca95f7f565a4decb9ecb192f326ab1580 | tests/reproduce_storage_rename.py；tests/reports/graph-storage-before.json |
| 81e342835c1345822b3ecec6f56195f957826095 | backend/scholar_graph/atomic_io.py；storage.py（同目录）；tests/storage_lock_probe.py；tests/test_atomic_io.py；tests/reports/graph-storage-lock-probe.json |
| 2c7186e08f631d9db780e2a8fa68512007c6a14e | tests/reports/graph-storage-after.json；graph-storage-regression.xml；graph-storage-report.md（同目录） |
| 63b217f1ef11f589865fa5784b87fd2e61642844 | contracts/graph-node.v1.2.schema.json；graph-node.v1.2.example.json；graph-edge.v1.2.schema.json；graph-edge.v1.2.example.json；CONTRACTS.md（后四者同目录）；backend/scholar_graph/validation.py；tests/test_graph_contracts.py |
| 42a4ff8f1914295a168b3df2c6a66b14438f0436 | backend/scholar_graph/citation_graph.py；tests/graph_samples.py；tests/test_citation_graph.py |
| 665b595ba9eebbfa141acc90d95fa1426db9debd | backend/scholar_graph/future_work.py；graph_service.py（同目录）；tests/test_future_work.py |
| ef107195ef1897ead9a87aa9697898606083f83d | backend/scholar_graph/api.py；graph_routes.py（同目录）；tests/test_graph_api.py；tests/test_api_comparison.py；tests/verify_contract_boundaries.py；tests/run_module_one_api_smoke.py；tests/run_module_two_smoke.py |
| 5c9705abb166589c20d45fbb8c93578f49d617ac | backend/README.md；docs/api-draft-v1.md |
| e4f1174554967137e9323e11ef29d561246cdae0 | backend/scholar_graph/api.py；tests/run_module_five_smoke.py |
| eb1703429b3d426df5cdd681ace9a033f1593bba | contracts/graph-node.v1.2.example.json；contracts/graph-edge.v1.2.example.json；tests/test_graph_contracts.py |
| ea1cc437f67cbe82d7afc60343e6ff5ea997d5f9 | docs/api-draft-v1.md |

最后证据提交为本报告、module-five-smoke.json、module-five-pytest.xml；完整哈希及原始git push输出在推送后最终回报给出，避免自引用及预写成功。
