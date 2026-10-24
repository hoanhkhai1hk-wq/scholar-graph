# 模块四：检索、追踪与智能推荐交付报告

2026-10-24（Asia/Shanghai），D:\AI_Workspace\Tasks\scholar-graph，分支 main；在2026-10-30时间目标前完成。开工前工作区干净，git pull --ff-only 原文 `Already up to date.`，主干完整哈希 **5e3e0dce8dbc51b441bbebe7fa88c785e10ccb04**。

本单完成 POST /api/v1/retrieval/search、POST /api/v1/retrieval/fetch、GET /api/v1/recommendations。总业务端点由13增为16；/reviews、/frameworks、/charts/csv 仍未落地，后续单号待总指挥分配。未新增阅读器、写作、框架、图表接口。

十一类业务 Schema 与 example 共22份，逐份 Git blob 与开工基线完全一致；contracts/CONTRACTS.md 同样未改。没有新增推荐业务记录，只使用本单授权的传输封装。frontend/、prompts/、experiments/、test-records/、compose 和其他docs零改动。不读取.env、不使用真实API Key、不调用真实大语言模型，不直接联系 WorkBuddy 或 DeepSeek Harness。

## 实际检索：向量已实装

真实本地CPU编码和HTTP调用均跑通，不存在模型下载/运行阻塞。默认仍为词法模式，使用本地配置显式启用向量；默认值不等于本单未实现向量。部署者按backend README启动，工作流无真实Key。模块二 QA 本单仍沿用词法取证，不把新搜索接口说成已经替换QA检索。

| 组件 | 实际版本/配置 |
| --- | --- |
| Chroma | 1.5.9，PersistentClient，cosine索引 |
| BGE调用方 | FlagEmbedding 1.4.2，BGEM3FlagModel，CPU，float32 |
| 模型 | BAAI/bge-m3，固定快照5617a9f61b028005a4858fdac845db406aefb181 |
| torch / transformers | 2.14.1+cpu / 5.20.2 |
| 索引规模 | 4个自制论文Chunk，4条真实1024维dense向量和4组模型sparse权重 |
| 编码限制 | batch=1、2线程、512 tokens截断，不冒称完整8192-token覆盖 |
| 持久化复用 | 第二次仅选C论文，活动Chunk1、存储向量4、updated_chunks=0；未返回其他论文 |

独立隔离环境在 data/module-four-runtime/.venv，模型在 data/module-four-models/bge-m3，未污染原MinerU/PaddleOCR环境；两环境pip check均原文 `No broken requirements found.`。模型权重文件2271145830字节，SHA-256及稀疏头/分词器校验见 [audit JSON](module-four-audit.json)。模型与虚拟环境不进Git。

Chroma保存dense、文本和模型token sparse权重；dense按余弦，sparse按真实BGE权重点积排序，各自名次后等权融合：

```text
relevance = 0.5 * 61/(60 + dense_rank) + 0.5 * 61/(60 + sparse_rank)
```

名次从1起，sparse≤0贡献0，同分按chunk_id。每次只查询选定落盘Chunk的id，索引指纹包含完整Chunk、模型快照与截断配置，变更后重编码。每请求独立worker，240秒超时；模型缺失、依赖/worker异常、超时、损坏结果或非有限值均明确词法回退，响应头lexical/UNAVAILABLE。未启用为lexical/NOT_ENABLED，实际向量成功为bge_m3_hybrid/READY。worker不继承API_KEY/TOKEN/SECRET/PASSWORD类变量，运行期离线，不把远程API或随机数当模型。

本次混合HTTP耗时19.141秒，持久子集19.500秒。主要仍需每次加载模型；这是小语料功能验证，未验证生产吞吐、推荐质量、中文语义精度或长块尾部召回。词法模式使用本地token集合的IDF加权余弦，无需模型；模块四新增词法与稀疏模型编码分别命名，不混淆。

## 搜索实测

POST /api/v1/retrieval/search，请求 `{question:"cross-lingual transfer",page_size:999}`。响应200，page_size实际100，固定六字段分页壳，total=4；模式bge_m3_hybrid、READY。

| 排序 | Chunk | dense余弦 | 模型sparse点积 | relevance |
| ---: | --- | ---: | ---: | ---: |
| 1 | chunk-graph-b | 0.5804516077 | 0.1377510968 | 0.9919354839 |
| 2 | chunk-graph-c | 0.5793206096 | 0.1495761110 | 0.9919354839 |
| 3 | chunk-graph-a | 0.4832015038 | 0 | 0.4841269841 |
| 4 | chunk-graph-d | 0.3797173500 | 0 | 0.4765625000 |

首条anchor是 `{paper_id:"paper-graph-b",page_number:1,section:["Main"],chunk_id:"chunk-graph-b"}`，同时返回原样Chunk，输出前再次Schema和真实锚点校验。分数是融合排序值，不是答案可信度；向量可召回词面无交集的真实块，不以空词面交集断言语义无结果。

同问词法模式total=2，C=0.4377912311、B=0.3345420558，明确标lexical。词法问zzzznonexistent返回空items、total=0、NO_MATCHING_CHUNKS；空库为EMPTY_CORPUS；有结果但page=999为空页且保留total，PAGE_OUT_OF_RANGE。浏览器可读取模式/状态/原因头，固定分页壳不偷偷添加原因字段；门禁拒绝假的Chunk id、越界相关度、NaN或错误索引。

## arXiv公开抓取与原管线复用

POST /api/v1/retrieval/fetch，JSON `{title}` 或 `{reference:完整ReferenceEntry}`二选一。真实Atom元数据只接受唯一精确标识/DOI/归一标题匹配；公开HTTPS固定arxiv.org/export.arxiv.org，3秒请求间隔，Atom1MiB/PDF50MiB上限，跨第三方重定向拒绝。未找到或请求失败不造元数据。

响应HTTP200是一次同步操作的传输封装 `{succeeded,metadata,paper,initial_parse_status,parse_status,error}`，不是论文列表。先将真实PaperMeta原子入catalog；PDF交给原Pipeline.parse，用原MinerU、可选PaddleOCR、ParseJob、门禁、原子发布与去重。新增metadata_enricher仅在发布前补实际API字段，禁止改id/版本契约号/file_hash/page_count/has_text_layer。metadata.id为arxiv标识，paper.id仍为实际PDF哈希，文件身份无伪造。

自制Atom+两页PDF得到 **1 PaperMeta /6 Chunk /1 ReferenceEntry /1 CitationLink**；初始ParseStatus确为queued/0、最新completed/100。它是自制样例、非官方pdf/用例，Atom用Mock，MinerU实际调用。注入HTTP503得到succeeded=false、metadata/paper/status=null，error原文为 `{"error_code":"UPSTREAM_ERROR","message":"arXiv 公共接口返回 HTTP 503，未取得所需记录或文件。","details":null}`。PDF下载失败可保留实际metadata但不伪建queued；PDF解析失败返回真实queued与failed，error用v1.1码表。

另有**真实公开接口探针**：ReferenceEntry中arxiv_id=1706.03762，实际API返回1706.03762v7《Attention Is All You Need》，published年2017（未把更新年当发表年），PDF15页。HTTP200 succeeded=true，queued→completed，耗时12.125秒，复用MinerU得到 **1 PaperMeta /175 Chunk /40 ReferenceEntry /69 CitationLink**，PDF SHA-256 bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697。它是一次真实公开连通验证，不是官方pdf/用例，也不宣称参考文献/块划分精度已达标。公开探针在向量四块样例之后运行，该175块不计入前述索引规模。

GROBID真实状态：**待验证**。本单未启动Docker、未联调GROBID，不改compose。OCR沿用已有PaddleOCR兜底，全量回归实际运行原自制扫描页测试；本次arXiv与搜索样例均无OCR页。不调用DeepSeek或其他真实生成模型。

## 推荐实测与含金量评分公式原文

```text
score = 100 * (0.40*G + 0.35*P + 0.15*T + 0.10*C); missing terms contribute 0, without reweighting
```

| 项 | 权重 | 定义与数据来源 |
| --- | ---: | --- |
| G | 0.40 | 候选和种子任一方向有verified图谱边为1；复用模块五CitationLink/ReferenceEntry/Chunk锚点。无verified边为0，不推断全网关系 |
| P | 0.35 | 候选PageRank/当前本地图最大PageRank；复用模块五相同0.85阻尼/悬挂回流/1e-12容差算法，集合是所有已解析论文，包含种子和孤立节点 |
| T | 0.15 | max(0,1-(as_of_year-PaperMeta.year)/10)，未知或晚于评分年为null并记缺失 |
| C | 0.10 | 真实PaperMeta.abstract/source存在精确https://github.com/owner/repo链接为1，否则null并记缺失；不以链接推断仓库内容或开源许可证 |

缺失按0贡献，不重分权重。as_of_year默认为当前UTC年，响应逐项回显；可显式指定以重现。没有引用次数项；局域PageRank不冒充全球引文数。权重是透明启发式，不是学习得到的科研质量分。

GET /api/v1/recommendations?paper_id=paper-graph-a&as_of_year=2026，图谱A→B→C，D孤立，HTTP200，total=3：

| 论文 | score | G | P | T | C |
| --- | ---: | ---: | ---: | ---: | --- |
| paper-graph-b | 71.1700680272 | 1 | 0.7191448008 | 0.4 | null |
| paper-graph-c | 38.0000000000 | 0 | 1 | 0.2 | null |
| paper-graph-d | 27.1054421769 | 0 | 0.3887269193 | 0.9 | null |

B理由保留A→B真实GraphEdge及Chunk锚点；每项给实际GraphNode、scope_size=4、最大PR=0.400544959128；时间理由附元数据年份与评分年。三篇均缺GitHub信号，明确missing_signals=[github_link]，不声称有开源代码。单种子库无候选为空列表/NO_CANDIDATES；不存在种子为404三字段PAPER_NOT_FOUND。额外测试使用明确标注为自制的GitHub链接验证元数据来源与得分一致，不把合成链接冒充真实仓库已访问。

## 最终全量回归

```text
241 passed in 125.34s (0:02:05)
```

[JUnit](module-four-pytest.xml)：241总数、241通过、0失败、0错误、0跳过；含原186项与本单新增55项。运行命令：

```powershell
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --basetemp data/module-four-final-test-temp --junitxml tests/reports/module-four-pytest.xml
```

| 新增组 | 数量 |
| --- | ---: |
| 词法/融合/锚点门禁 | 8 |
| 推荐信号/缺失/元数据链接 | 6 |
| arXiv客户端与既有Pipeline | 10 |
| 向量worker协议与故障 | 8 |
| 搜索端点 | 9 |
| 抓取端点 | 7 |
| 推荐端点 | 7 |

默认pytest不联网、不依赖Docker/GROBID、不下载BGE模型；worker协议测试含Mock，**不拿Mock证明真实向量接通**。真正本地BGE/Chroma与公开arXiv分别由独立HTTP实跑脚本补证，详见 [完整9组请求响应/native_evidence](module-four-smoke.json)。真实MinerU/PaddleOCR、同源代理、CORS、模块二/五回归亦执行。输入是自制样例、非官方pdf/用例；未运行官方三用例、未验收前端页面。

复现：按backend README准备可选隔离环境/模型，然后选择新的data输出目录：

```powershell
backend/.venv/Scripts/python.exe tests/run_module_four_smoke.py --output-root data/module-four-reproduce --report data/module-four-reproduce.json --vector-python data/module-four-runtime/.venv/Scripts/python.exe --model-path data/module-four-models/bge-m3 --live-arxiv
```

## 提交与协作交付

实现提交完整哈希、中文事项、逐提交文件清单在 [audit JSON的implementation_commits](module-four-audit.json)。下面附同一清单，路径均相对本报告开头的D盘仓库；证据报告自身的最终提交完整哈希及git push原文由最终交付回报给出，避免自引用哈希。

交由用户转达WorkBuddy：按docs/api-draft-v1.md的新搜索Chunk证据形状、抓取操作封装及推荐列表对接；浏览器可读模式/空结果头，默认词法、配置后本地向量可用。未修改前端，不把前端静态壳称为已接通。模型下载/运行均实际成功，无向量阻塞；默认词法与每请求加载耗时是明确的部署取舍。

| 完整提交哈希 | 事项 | 对应文件 |
| --- | --- | --- |
| eae274e4007ab4256055d2881bc82b9d0f54e048 | 实现真实Chunk词法取证与混合排序门禁及空结果说明 | backend/scholar_graph/retrieval.py<br>tests/test_retrieval.py |
| a4bcea7f5626086d56220bd4ca5ef95aa944acdf | 复用模块五信号实现可追溯推荐与公开评分公式 | backend/scholar_graph/recommendations.py<br>tests/test_recommendations.py |
| f7c408fabeeb45c5e09421439df253342aaf0473 | 复用既有解析管线接入公开arXiv抓取与真实元数据入库 | backend/scholar_graph/arxiv_fetch.py<br>backend/scholar_graph/pipeline.py<br>tests/test_arxiv_fetch.py |
| c2de5a1176f66a9be39d1f9db7fef9d4ac017997 | 增加隔离CPU的BGE-M3稠密稀疏编码与Chroma持久索引适配 | backend/requirements-retrieval.txt<br>backend/scholar_graph/vector_search.py<br>backend/scholar_graph/vector_worker.py<br>tests/test_vector_adapter.py |
| 6de8ca8edb35507edfc3af6e258f744aaf2ca3fd | 落地检索端点与真实锚点分页及可见检索模式 | backend/scholar_graph/api.py<br>backend/scholar_graph/retrieval_routes.py<br>tests/test_retrieval_api.py |
| 6d08759695b062865ca91716cf71dca8355f7c7a | 落地arXiv抓取端点并返回既有解析状态与逐次失败原因 | backend/scholar_graph/api.py<br>backend/scholar_graph/retrieval_routes.py<br>tests/test_arxiv_api.py |
| 571553295cf7257c662344609262272e9518c8df | 落地推荐端点并用真实图谱时间及元数据链接解释评分 | backend/scholar_graph/api.py<br>backend/scholar_graph/retrieval_routes.py<br>tests/test_api_comparison.py<br>tests/test_recommendations_api.py |
| c5d9e7a90db51d93dd3a433a278a628ccde9c725 | 增加模块四HTTP真实向量与公开抓取可复现验收脚本 | tests/run_module_four_smoke.py<br>tests/run_module_one_api_smoke.py |
| c0a879fb76b0da0cb238a00040c11858690251b7 | 拒绝损坏或非有限向量结果并清除过期运行证据 | backend/scholar_graph/vector_search.py<br>tests/test_vector_adapter.py |
| b596d57d6215a983ce473af26a64976747eb0a45 | 同步模块四传输裁定评分公式及实际向量运行复现指南 | backend/README.md<br>backend/download_bge_m3.py<br>docs/api-draft-v1.md |
| f4a33c0b2a959fedbd69f47d3d32de48581a7718 | 清除抓取推荐遗留待裁定文字并明确列表排序差异 | backend/README.md<br>docs/api-draft-v1.md |
