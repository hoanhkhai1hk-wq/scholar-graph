# arXiv 定期追踪、引用去重与反馈验收

日期：2026-10-26，Asia/Shanghai。仓库：hoanhkhai1hk-wq/scholar-graph，分支main。开工git pull --ff-only后主干为`b42f3d21918bdb24c037c7845bd5129af6b1f9e3`，工作区干净，与origin/main一致。

本单已实现可触发的周期任务、手动追踪与状态端点、身份幂等抓取、持久化去重日志、引用精确清理和点赞/踩画像。最终限定2候选的真实两轮追踪通过；扩大候选范围的额外实测存在1篇解析失败，单独保留失败证据，不写成全部候选均能解析。全量回归最终481通过。前端及12份既有契约零改动。

## 端点与周期触发

路径均有`/api/v1`前缀，增加5条端点，业务端点总数由23变为28：

| 方法、路径 | 行为 |
| --- | --- |
| POST /retrieval/tracking/run | 同步执行一次真实公开Atom查询、候选关联及有上限的入库尝试；返回完整运行记录 |
| GET /retrieval/tracking/status | 读取落盘latest_run与唯一去重日志；未运行时latest_run=null |
| POST /retrieval/citations/cleanup | 清理相同位置的重复CitationLink，保留原件和前后散列 |
| POST /recommendations/feedback | 点赞/踩落盘，并返回排序前后、分数变化、主题词依据 |
| GET /recommendations/feedback | 读取画像的当前投票与事件历史 |

原GET /recommendations新增可选profile_id（默认local）；原POST /retrieval/fetch增加already_present与dedup字段。均为传输封装的向后兼容加法，不新增或修改业务schema。运维日志不是DedupDecision业务记录；新文件进入原比较流程时仍发布符合原schema的DedupDecision/DiffSummary。

周期任务采用用户允许的“可触发的定时任务”，不是常驻后台线程。Windows任务计划程序/cron可按日调用：

```powershell
backend/.venv/Scripts/python.exe -m scholar_graph.tracking_cli --data-dir data/module-one --due --interval-seconds 86400 --max-candidates 5 --max-imports 2
```

`--due`检查距最近一次运行开始的时间，未到期不发请求；手动端点force=true可立即执行。命令completed或NOT_DUE退出0，partial/failed退出1。实际执行过CLI，返回`skipped=true,reason=NOT_DUE`、退出0，证据见JSON的scheduled_task_not_due。本单未向用户宿主机注册系统计划；部署须配置触发器。完整参数、计划程序字段及限制在[backend README第336行起](../../backend/README.md#arxiv-定期追踪引用去重与反馈2026-10-26)。

种子来自已发布论文标题主题词及真实CitationLink→ReferenceEntry关系，每篇最多两条查询。旧Attention的PaperMeta.title与ReferenceEntry.title均为空，首次准备发现不能直接取到种子；最终从真实页1短文本“Attention Is All You Need”和真实参考文献Chunk摘取主题/题名，同时返回锚点。空元数据不回填到契约。首屏短文本选择是可追溯的启发式，不保证对所有论文都能识别题名；无任何可用种子明确失败。

实测的两条查询为`all:"attention"`、`ti:"Empirical evaluation of gated recurrent neural networks on sequence modeling"`。后者从实际正文引用关系定位，未伪造参考条目标题。候选相关理由给库内paper_id、类型、共同词与可用锚点；主题规则为英文停用词、连字符拆分与尾s归一化，是词法关联，不冒充向量或语义模型。按submittedDate倒序取公开搜索结果；历史引用查询可得到旧文献，“新”表示当前库的新发现，不承诺每篇刚发表。

## 两轮真实 arXiv 验收

探针：[run_tracking_acceptance.py](../run_tracking_acceptance.py)。完整结果：[tracking-live-results.json](tracking-live-results.json)。新候选由本轮公开arXiv接口查询、实际下载PDF并调用原MinerU本地解析Pipeline；未用宿主机已有候选解析结果替代。本轮无模型Key、无模型调用，探针要求子进程不含DEEPSEEK_API_KEY。

种子库复制此前真实已解析的官方pdf/ Attention v7（175 Chunk）和公开BERT（277 Chunk），复制范围只用于初始化库内种子；新增候选的实际ParseStatus为queued→completed。独立数据目录为忽略的`data/tracking-acceptance-final-v4/records`，初始2篇，第一轮后4篇，第二轮后仍4篇。

实际时间为2026-10-26 01:08:58–01:09:51 +08:00，包括后续额外抓取和反馈。请求：

```json
{"paper_ids":["paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697"],"max_candidates":2,"max_imports":2}
```

| 轮次 | HTTP/运行状态 | 候选 | 新增论文 | 跳过重复 | 失败 | 论文总数 | HTTP总耗时/服务内耗时（秒） |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 200/completed | 2 | 2 | 0 | 0 | 4 | 33.750 / 33.515 |
| 2 | 200/completed | 2 | 0 | 2 | 0 | 4 | 4.266 / 4.062 |

运行id分别为`39f0e43ea4f64461ae15deea66786d55`、`bb051baacb5a40a1b3acda73f85aaf27`。

| arXiv ID | 真实标题 | 本轮实际Chunk | 第二轮结果 |
| --- | --- | ---: | --- |
| 2610.31639v1 | Causal Chain of Thought: Mitigating Attention Leakage via Context Isolation | 409 | 复用同一个paper_id；不重复下载/解析 |
| 2610.31633v1 | BeNice! Closing Looping's Inference-Memory Gap via KV-Sharing | 350 | 复用同一个paper_id；不重复下载/解析 |

两条候选都关联真实Attention种子，理由原文为“与库内论文主题词重合：attention”，附页1真实Chunk锚点。引用查询的结果与主题查询一并记录，但最终全局候选上限为2，按查询顺序截取；不冒充已将所有查询结果入库。每次入库尝试预算同时计失败和重复，超出预算的候选标deferred；无后台队列。

重跑命令（为保留已完成证据，另指定未使用的data目录；需已有种子解析数据）：

```powershell
@'
import os, subprocess
env = {k:v for k,v in os.environ.items() if not any(w in k.upper() for w in ('API_KEY','TOKEN','SECRET','PASSWORD'))}
raise SystemExit(subprocess.run(['backend/.venv/Scripts/python.exe','tests/run_tracking_acceptance.py','--data-dir','data/tracking-reproduction-new'],env=env).returncode)
'@ | backend/.venv/Scripts/python.exe -
```

公开结果会随时间变化；探针输出锁定实测源码SHA、实际arXiv ID、完整状态及持久化排序。探针默认保护已使用的数据目录，避免拿旧结果充当新解析。

## 身份去重与引用清理数量

基础arXiv ID剥离vN后相同，或裸DOI大小写无关相同，在入库锁内直接复用已发布论文。不重新建queued，initial_parse_status=null；有真实job才返回parse_status，没有job就null。不同版本不会自动覆盖原库记录，也不会自动下载最新版。这是身份幂等，不是语义向量去重。

真正新文件沿用原Pipeline的DOI/身份判断与词频Dice≥0.90疑似重复机制。显式冲突身份不因高词频强配对。Dice高相似的新文件保留原比较裁决，供人工复核，不擅自删除可能不同的论文。新增回归证明未知身份的本地论文能触发真实Dice比较，重复抓取不新增第二份比较文件。

| 计数项 | 本次实际值 |
| --- | ---: |
| 第一轮唯一新增身份 | 2 |
| 第二轮跳过重复入库 | 2 |
| 持久化去重日志总行数 | 2（每个基础arXiv ID一行） |
| 两行日志occurrences总和 | 2 |
| 第二轮新增比较业务文件 | 0 |
| 正常库第一轮/第二轮清理重复引用 | 0 / 0 |
| 明确故障注入副本的清理 | 71→69条，删除2条 |
| 同一注入副本再次清理 | 69→69条，删除0条 |

正常库没有检测到重复引用，不能把0写成已清理真实语料缺陷。另复制真实Attention的69条已落盘CitationLink，在独立cleanup-fixture上故意追加同一链接两遍：这是明确标识的故障注入，不冒充论文原生重复。清理只比较(paper_id,citation_number,page_number,chunk_id,ref_id)全等；不同Chunk/物理页的合法引用保留。非法锚点报错，不能顺手删掉以凑成功。

清理前验证schema，清理后验证整组外键；保存before.json、intent.json、completed.json和前后SHA，原子替换citation-links.json。不改源元数据、Chunk、ReferenceEntry或索引。操作系统文件锁覆盖HTTP上传、抓取及清理，跨进程释放由内核负责；SQLite事务保存唯一去重日志、运行和反馈。

## 点赞/踩的真实效果与持久化

为了验证画像影响另一篇同类论文，在两轮追踪完成之后**另行**公开抓取`Reformer: The Efficient Transformer`：真实arXiv `2001.04451v2`，12页、197 Chunk，实际下载解析成功，11.062秒。该额外入库不计入上表两轮新增数量。

基础评分原文不变：

```text
base_score = 100*(0.40*G + 0.35*P + 0.15*T + 0.10*C)
```

G为已核验局域图邻居，P为本地PageRank归一化值，T为元数据年份的十年线性时效，C为元数据实际GitHub链接。缺失按0贡献，不编造全球引用数。新增反馈公式原文：

```text
score = clamp(base_score + 50 * mean(vote * Jaccard(title_topics(candidate), title_topics(voted_paper))), 0, 100); empty profile adds 0
```

vote为点赞1、踩-1。标题主题词取真实PaperMeta，停用词过滤、连字符拆词、长度>4且非ss结尾的词裁剪末尾s，不作词性判断；Jaccard=交集数/并集数。空并集贡献0，权重50是透明启发式。响应返回共同词、双方词集、实际投票、调整量。没有向量库、模型画像或虚构开源信号。

实测请求POST /api/v1/recommendations/feedback：

```json
{"paper_id":"paper-987545ffb087f1ece898142c403a516baeabeb70ce19089397fac6f7db12c3d4","seed_paper_id":"paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697","vote":"like","as_of_year":2026}
```

HTTP200、event_id=1，画像local：

| 论文 | 点赞前排名/得分 | 点赞后排名/得分 | 加分及依据 |
| --- | --- | --- | --- |
| BERT | 4 / 35 | 1 / 85 | +50，自身标题主题词一致 |
| BeNice! | 1 / 50 | 2 / 50 | 0，与本次投票无共同标题词 |
| Causal Chain of Thought | 2 / 50 | 3 / 50 | 0，与本次投票无共同标题词 |
| Reformer | 3 / 41 | 4 / 46 | +5，共同词transformer，Jaccard=0.1 |

同类Reformer得到真实主题加分，但BERT被提升到首位后Reformer的**绝对名次为第4，未上升**，不能把加分误写为它排名上升。完整排序前后留在反馈事件中，可由GET反馈端点查回。创建新app模拟进程重启后，当前投票、事件与推荐响应完全相同，确认不是只放内存。自制回归另外验证同类论文排序、踩的负分、更换投票不叠加、不同画像隔离、404与非法参数。

profile_id是本地画像标识，没有新增账号认证。框架/综述的内存视图调用保持纯排序，不读取个人画像；仅推荐API显式加载画像。

## 失败、修复与实际边界

1. 首次全量回归为479项、464通过、15失败、0错误/跳过，耗时165.04秒，保留[首次JUnit](tracking-initial-pytest.xml)。原因是新增反馈默认让纯推荐函数读取repository.root，而旧框架/综述的SelectedPapers是内存视图，没有root。修复为纯函数默认不启用画像，由HTTP推荐端点显式传profile_id；新增隔离回归后重跑全量，最终481项通过。没有修改框架、综述实现绕过失败。
2. [扩大候选范围的两轮原始结果](tracking-candidate-failure-results.json)：max_candidates=3、max_imports=3，每轮均为partial；第一轮2新增、1失败，第二轮0新增、2跳过重复、1失败。额外候选`2610.31608v1`（Humanoid Mobility via Attention-based Contacts）两轮均因`PARSE_FAILED`拒绝，原文：“参考文献编号重复，不能确认正文引用目标。”定位在现有`backend/scholar_graph/normalize.py:37`。这是原解析器发现参考编号歧义，未发布非法论文；没有为本单放宽锚点或schema，也没有把失败写成通过。该两轮耗时62.313秒、32.937秒。最终上表为**另一个明确限定2候选的完整批次**，不掩盖扩大范围时的失败。
3. 可触发任务不等于已经在宿主机注册每日计划。当前不启用常驻循环、不自动追版本、不提供持久化候选待导入队列。公开接口、PDF不可用或不支持的版式仍会明确失败；结果不是全网覆盖或语义新颖性判断。
4. 前端未改、未声称接入。docs/API草案本单未授权修改；端点、结构、评分和转达WorkBuddy说明已放backend README。旧Docker镜像本单未重建，不冒充容器已含新实现。

## 最终全量回归与审计

```powershell
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --run-real-model --basetemp data/tracking-final-regression --junitxml tests/reports/tracking-pytest.xml
```

原文：

```text
481 passed in 153.61s (0:02:33)
```

[最终JUnit](tracking-pytest.xml)：总数481，通过481，失败0，错误0，跳过0；JUnit时间153.582秒，包含原448项及本单33项新增回归。自制Atom/PDF测试与真实网络探针明确分开，单测不冒充真实arXiv。既有可选OCR和真模型回归本轮也执行；本单追踪与反馈探针始终在移除Key的子进程运行，不调用模型。

新增覆盖：arXiv同身份/不同版本、DOI命中、同实例并发、文件锁释放、Dice比较、无job历史；引用审计幂等、真实多锚点保留、非法锚点拒绝；主题与引用种子、空种子/上游失败/解析失败、候选预算、运行互斥/中断恢复、未到期CLI；点赞/踩、同类词证据、重启持久化、画像隔离、旧框架纯排序兼容。schema/example均未修改。

审计脚本：[audit_tracking_acceptance.py](../audit_tracking_acceptance.py)。结果：[tracking-audit.json](tracking-audit.json)：**36项通过，0失败**，核对真实库、两轮论文id集合、ParseStatus、Chunk和种子锚点、唯一日志、清理SHA、重启画像、源码SHA、最终/首次JUnit、额外失败原文、28条路由及Git边界。实际Key逐文件扫描未命中；pdf/仍被.gitignore忽略，pdf/、data/、.env没有被跟踪或提交。语料和运行SQLite只在本地忽略目录。

## 提交与文件

| 完整提交哈希 | 对应文件/事项 |
| --- | --- |
| c97d59263a4fa85db38175cafc51d31df684329f | backend/scholar_graph/{api_uploads,arxiv_fetch,tracking_state}.py；tests/test_tracking_import.py |
| 3b955cd23b5aaef03a3f5d541b1fcb16288c9bf4 | backend/scholar_graph/citation_cleanup.py；tests/test_citation_cleanup.py |
| 8e5f6a9ce57e59b17e172c274f99c2b1509f2c6b | backend/scholar_graph/{tracking,tracking_cli}.py；tests/test_tracking.py |
| bf875c90cf8190a31e762ed43dda9964116e8d51 | backend/scholar_graph/{recommendation_feedback,recommendations}.py；tests/test_recommendation_feedback.py |
| 08e6d10d4a4dfb164ac99b1745c04561dfad2e39 | backend/scholar_graph/tracking.py；tests/test_tracking.py，统一主题匹配 |
| 570f7bd63d628e93f0538fbe30f41773e11025e1 | backend/scholar_graph/{api,retrieval_routes,tracking_routes}.py；tests/test_api_comparison.py |
| abb94e0bf4e12709c817e694187f679723a0c2c4 | backend/README.md，周期任务、端点和公式 |
| 4ac2fba34b4eff7dc43e885290a1420e57cfb949 | backend/README.md，旧元数据启发式边界 |
| 99fe878088d48ad69eff133919649edabf0e78b1 | tests/run_tracking_acceptance.py、tests/audit_tracking_acceptance.py；tests/reports/tracking-{live-results,candidate-failure-results,audit}.json、tracking-pytest.xml、tracking-initial-pytest.xml |

本文件单独提交；其完整哈希及实际git push原文随最终交付回报给出。

公共协议依据：[arXiv API手册](https://info.arxiv.org/help/api/user-manual.html)、[arXiv API使用条款](https://info.arxiv.org/help/api/tou.html)。本次结果来自实际公开HTTP数据，不把文档说明代替网络实测。
