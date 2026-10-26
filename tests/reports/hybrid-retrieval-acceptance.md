# 缺口单 B：QA 混合检索验收

2026-10-26，Asia/Shanghai。D:\AI_Workspace\Tasks\scholar-graph，main分支。开工`git pull --ff-only`原文`Already up to date.`；主干`1dc443e6fb80840d4b0b49a5187ccce88129ce58`，工作区干净。

已将真实本地Chroma/BGE-M3双路召回接入单篇QA、跨篇比较、Agent retrieve/search及SSE链路。最终官方六题 **6/6通过，逐题均hybrid**，锚点与数字门禁保留。真实同义改写对照观察到向量优势；本机实测bge-reranker-large过慢，最终采用RRF。全量528通过，审计82通过。前端与12份业务契约零改动。

## 接线与实际重排选择

调用QAHybridRetriever：

- 单篇POST /api/v1/papers/{paper_id}/qa，包括deepseek和摘录模式。
- POST /api/v1/compare，及显式agent=true。
- LangGraph retrieve节点和模型Function Calling的search工具。
- 原POST /api/v1/papers/{paper_id}/qa/stream的retrieve阶段及done元数据。

每篇在用户选择的真实已落盘Chunk集合中召回：本地BGE-M3 dense余弦前24块，词法路前24个不同Chunk；词法仍复用原IDF排序、领域别名扩展、首页作者布局覆盖。并集最多48块。QA不使用BGE sparse分值冒充本次词法路；检索页原dense/sparse方式保留不改。Chroma活动id严格限定当前论文，不把其他论文旧索引行作为证据。

等权RRF按实际名次打分，第r名的单路贡献：

```text
RRF(chunk) = 0.5*61/(60+dense_rank) + 0.5*61/(60+lexical_rank)
```

名次从1开始，未召回的路贡献0，同分按chunk_id。不是将两个模型的原始分值假定为同尺度概率。词法无结果而真实向量有结果时标vector；两路都有时标hybrid；禁用、缺模型或失败标lexical-fallback并写reason/vector_status。多篇中任一调用回落，全局保守标lexical-fallback，各次实际方法仍逐项列出，不假装全程向量成功。

优先下载并实际跑了BAAI/bge-reranker-large，固定快照`55611d7bca2a7133960a6d3b71e083071bbfc312`，CPU、512 token、batch=1。本地权重model.safetensors为2239618772字节；SHA与公开固定快照缓存元数据一致，见审计JSON。

| 首次真实重排测量 | 实际值 |
| --- | ---: |
| 并集候选 | 36块 |
| 模型构造/加载 | 5.343437秒 |
| 实际逐对推理 | 12.423250秒 |
| 含Python导入、进程启动的worker总耗时 | 27.557949秒 |
| 预设每请求额外重排预算 | 5秒 |

auto预算在实测之前已设定，包含当前架构每请求的冷加载。实际打分和id/有限数校验完成后，因27.557949>5秒，采用RRF，并把实测原因MEASURED_CPU_BUDGET_EXCEEDED及全部计时写入数据目录qa-retrieval/reranker-policy.json；该数据目录后续auto复用，不每题重复跑慢重排。不是只因没安装就宣称太慢，也不把RRF称为cross-encoder已参与最终排序。若持久模型或更快硬件能降低延迟可另测；本次仅证明这台CPU和当前逐请求worker部署的选择。

配置SCHOLAR_GRAPH_QA_RETRIEVAL_MODE默认hybrid，lexical显式关闭向量；本地Python/模型沿用SCHOLAR_GRAPH_VECTOR_PYTHON、SCHOLAR_GRAPH_BGE_M3_PATH。SCHOLAR_GRAPH_RERANKER_PATH指定本地重排目录；SCHOLAR_GRAPH_QA_RERANKER=auto/cross_encoder/rrf。默认D盘现有隔离环境，其他平台须指定实际路径。缺模型不自动联网推理，明确回退。

## 本地索引与加载耗时

实际依赖：Chroma1.5.9、FlagEmbedding1.4.2、torch2.14.1+cpu、transformers5.20.2；BGE-M3快照`5617a9f61b028005a4858fdac845db406aefb181`。CPU float32、2线程、512 token截断，batch=1。模型运行均本地、离线；worker不继承API_KEY/TOKEN/SECRET/PASSWORD，不需要Key。规划/回答另走已授权的deepseek-chat，不能把其Key要求混写为向量需要Key。

独立测试数据目录data/hybrid-retrieval-acceptance/records，复制此前已解析的官方Attention和BERT作为库内记录，原论文记录不改。实际重新建立QA专用chroma-qa-bge-m3索引：Attention175向量＋BERT277向量=**452条**。首次冷运行分别实际编码175、277块，索引阶段51.008965秒、86.905440秒；不是把空索引或此前检索页4条自制向量冒充452条。

首次作者题冷请求101.231908秒，包含冷索引、真实重排基准及回答；首次跨篇194.581999秒，还包含BERT冷索引和3次失败重试。它们保存在首次运行证据，不能拿来当最终热索引每题时延。

最终六题共9次实际向量调用（跨篇模型调用了4次search），复用索引，updated_chunks均0，但每个worker仍重新加载模型。计时口径：

| 最终六题计时范围 | 最小–最大 |
| --- | --- |
| model_load_seconds：库导入后，BGE模型构造/读权重 | 1.891185–2.026878秒 |
| startup_to_model_ready_seconds：worker开始至模型可用，包含重型库导入 | **12.069429–13.873853秒** |
| worker_seconds：含模型、索引检查、查询、进程退出 | 14.342757–16.168348秒 |
| 热索引检查 | 0.106211–0.141376秒 |
| 查询编码、Chroma查询与稀疏兼容计算 | 0.500323–0.592488秒 |

旧“约15–20秒”更接近端到端worker口径；不能用排除Python/torch/FlagEmbedding导入后的约2秒宣称整个模型启动降到2秒。首轮首题实际worker72.216104秒中包含51.008965秒冷索引。当前没有实现常驻BGE进程或生产级吞吐优化，仍存在每次加载成本。

## 官方六题逐题结果

探针：[run_hybrid_retrieval_acceptance.py](../run_hybrid_retrieval_acceptance.py)。最终原始批准响应、完整四字段锚点、数字校验、工具轨迹及调用元数据：[hybrid-retrieval-live.json](hybrid-retrieval-live.json)。前5题走单篇原路由，第6题走deepseek跨篇Agent，实际retrieve/search元数据可查。问题沿用此前官方六道原题。

论文标识：

- A（Attention）：`paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697`。
- B（BERT）：`paper-987545ffb087f1ece898142c403a516baeabeb70ce19089397fac6f7db12c3d4`。

下表页码为PDF物理页。Chunk后缀与A/B前缀组成完整chunk_id；完整section数组均保留在JSON，未省掉契约锚点字段。

| 题 | 答案核对 | 方法/候选证据数 | 最终锚点及数字状态 | HTTP耗时 | 结果 |
| --- | --- | --- | --- | ---: | --- |
| 1 第6作者与机构 | Aidan N. Gomez；University of Toronto | hybrid / 24窗口 | 1锚点，A页1/p0001-c00004；数字not_applicable | 16.330862秒 | 通过 |
| 2 Adam β₁、β₂ | 0.9、0.98 | hybrid / 24窗口 | 1锚点，A页7/p0007-c00088，5 Training/5.3 Optimizer；passed | 16.215422秒 | 通过 |
| 3 Base训练GPU | 8个NVIDIA P100 | hybrid / 24窗口 | 1锚点，A页7/p0007-c00086，5 Training/5.2 Hardware and Schedule；passed | 16.377191秒 | 通过 |
| 4 big BLEU、SOTA与提升 | 28.4；ConvS2S Ensemble 26.36；原文more than 2.0 BLEU | hybrid / 24窗口 | 2锚点，A页8/p0008-c00098正文、p0008-c00093表格；passed | 16.915673秒 | 通过 |
| 5 Layer Normalization完整引用 | Jimmy Lei Ba、Jamie Ryan Kiros、Geoffrey E Hinton，2016 | hybrid / 24窗口 | 1锚点，A页10/p0010-c00127，References；passed | 15.747314秒 | 通过 |
| 6 BERT与Transformer承袭及decoder | BERT为基于Vaswani et al.(2017)的多层双向Transformer encoder；与原Transformer encoder/decoder架构原文并列核对 | hybrid / 4次search各24原始窗口；去重后Agent证据32 | A5＋B5=10锚点；两篇数字均passed | 69.689243秒 | 通过 |

第1题批准摘录：`Aidan N. Gomez ∗  † University of Toronto aidan@cs.toronto.edu`。仍使用原首页版面作者顺序辅助，不把解析列块顺序当作者序。

第4题同时给出正文28.4与既往SOTA表格26.36，原文逐字说提升more than 2.0。报告端用Decimal确定性计算`28.4 - 26.36 = 2.04 BLEU`，两个数都回指已校验的页8锚点；2.04是代码算得的差值，不冒充模型或原文逐字给出的数字。旧解析对表格所属section存在误分，本单沿用真实已落盘section，没有伪造更漂亮的章节锚点。

第6题A来源包括页3encoder/decoder（p0003-c00031、p0003-c00032）、页5self-attention与encoder-decoder attention（p0005-c00058、p0005-c00057）、页2架构（p0002-c00026）。B来源包括页3架构（p0003-c00040、p0003-c00041）、页4encoder/decoder术语（p0004-c00056）、页13双向说明（p0013-c00212）、页1摘要（p0001-c00009）。BERT原文明确为encoder并基于原Transformer实现，与A的生成decoder来源对照可核对它没有沿用该生成解码器；这不是声称BERT原文逐字用了discard，也不把局域引用边当成因果证明。响应仍是证据表在先、逐篇QAAnswer与回指证据的综合在后。

真实走图一次：plan→retrieve→qa→validate，最终校验true，未走拒答；4次search均来自真实模型Function Calling，实际方法hybrid，合并后32条证据，最终10个不同Chunk锚点。单篇保留双窗口以覆盖SOTA表格；Agent每轮每Chunk一段和跨工具按Chunk去重，避免违反原600字符连续摘录门禁。

## 同义改写查询：实际观察到优势

构造与Base训练硬件同义的中文查询：**“基础网络借助哪种加速卡完成学习？”**。将“Base模型/GPU/训练”换成“基础网络/加速卡/学习”，没有触发原GPU、显卡、训、硬件等别名规则，且语料正文为英文。

| 同一个查询 | 实测 |
| --- | --- |
| 原严格摘录词法retrieve | 0条 |
| 原模型候选词法evidence_candidates（含原别名扩展） | 0条 |
| 新链路 | method=vector，vector_status=READY，向量24块、词法0块，生成24个窗口 |
| 命中 | 真实Base硬件原文，页7/p0007-c00086 |

其中一段实际命中：

> We trained our models on one machine with 8 NVIDIA P100 GPUs. For our base models using the hyperparameters described throughout the paper, each training step took about 0.4 seconds.

完整连续原文及锚点在paraphrase.target_hits中，所有24个候选锚点均重新校验。另一个含8/P100的命中是big结果段，不能把它冒充Base证据；上述Base原文是本例优势依据。这是**单例跨语言同义改写召回优势**，不是全查询准确率/召回率提升的统计结论。

## 无Key、回退、拒答与元数据

独立删除Key/Token类环境变量的子进程真实运行[run_hybrid_no_key_probe.py](../run_hybrid_no_key_probe.py)，结果见[hybrid-retrieval-no-key.json](hybrid-retrieval-no-key.json)。问“基础网络借助什么加速卡完成学习？”：HTTP200、method=vector、不拒答、有真实原文锚点，回答为摘录式，没有DeepSeek调用。随后将向量Python设为明确不存在的路径：HTTP200、method=lexical-fallback、vector_status=UNAVAILABLE，不假装使用向量。第二问无证据时原拒答规则仍有效。

故意错问Adam β₁=0.5、β₂=0.6仍返回refused=true；本轮模型未提供纠正摘录，numeric_fact_check=unverifiable，不虚称failed/已逐项纠正。完整拒答响应在最终JSON，不把缺失证据写成数字校验通过。

新增元数据仅进入原X-ScholarGraph-QA-Meta / X-ScholarGraph-Agent-Meta头（UTF-8百分号编码），以及SSE原retrieve节点完成、done.metadata；原CORS已暴露这些头。body仍为原QAAnswer或比较传输封装。每次列method、vector_status、reason、双路候选数、实际证据数、重排选择与阶段计时。模型回落原因和向量回退原因分别记录；无Key摘录SSE不伪造token流。前端未改，用户可将字段说明转达WorkBuddy。

本轮最终六题＋拒答实际调用deepseek/deepseek-chat共8次，调用时间累计15.496636秒，prompt74526、completion3145、total77671 tokens。该累计不含首次预跑与pytest实连，不冒充整单账单；Key只在进程环境读取，未打印/写入文件/提交。只保存批准答案、锚点与安全调用元数据，不保存原始模型响应体、思考内容或规划消息。

## 首次失败与修复

[hybrid-retrieval-attempt-1.json](hybrid-retrieval-attempt-1.json)保留首轮：前5题通过，第6题三轮校验均被“同一Chunk的摘录跨度超出600字符。”驳回，最终拒答，整组5/6；同时保留首次175/277向量冷建索引与真实重排基准计时。没有把这轮写成六题全过。

原因：模型将同块两个远距离窗口当不同证据并同时引用，合并后越过原长度门禁。修复仅约束Agent retrieve候选：每轮每Chunk最多一段连续窗口，跨工具合并也按Chunk去重；保留单篇双窗口供SOTA表格覆盖。原QAAnswer、字面子串、600字符、真实锚点与数字校验全部未放宽。增加对应回归后，冻结代码重新跑完六题，最终6/6。没有凭最终文件覆盖失败历史。

## 最终回归与审计

```powershell
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --run-real-model --basetemp data/hybrid-release-regression --junitxml tests/reports/hybrid-retrieval-pytest.xml
```

最终原文：

```text
528 passed in 162.72s (0:02:42)
```

[JUnit](hybrid-retrieval-pytest.xml)：总528，通过528，失败/错误/跳过0，JUnit时间162.696秒。原511项＋新增17项。普通回归用词法或显式假向量保证确定性，真实BGE六题由独立探针证明；原OCR和既有可选真模型回归也实际执行。新增覆盖双路/纯向量/明确回退、时序计时、缓存慢重排策略、重排失败RRF、损坏策略不冒充向量失效、元数据快照、Agent工具与retrieve节点、直接QA/比较、无KeySSE元数据接线、单Chunk连续证据约束。

审计：[audit_hybrid_retrieval.py](../audit_hybrid_retrieval.py)、[hybrid-retrieval-audit.json](hybrid-retrieval-audit.json)，**82项通过，0失败**。独立重新检查六题批准摘录、每个锚点/数字来源、2.04确定性算式、实际双路候选、模型加载计时、跨篇走图和真实工具调用、同义原文、无Key与缺向量回退、首次拒答、452条Chroma行、重排权重SHA、源码SHA、最终JUnit和Git边界。pdf/仍被忽略，模型/索引/语料均未跟踪，所有本单文件实际Key字节扫描未命中。

限制：512 token截断、24块每路候选预算，不证明所有长文尾部都召回；没有用六题结果宣称全领域零误报。模型可用仍可能上游失败，原统一错误与拒答保留。Cold索引可显著慢于热查询；后台常驻模型、重建Docker镜像及前端接线不在本单完成范围。

## 提交与文件

| 完整哈希 | 文件/事项 |
| --- | --- |
| a0b976abb6409dcbc7afa97dec59310d6e100373 | backend/download_bge_reranker.py；backend/scholar_graph/{qa_retrieval,vector_search,vector_worker}.py；tests/test_qa_hybrid_retrieval.py |
| 38f70eca287b27f2d81e034603e7e7b34ec6989f | backend/scholar_graph/{agent_tools,grounded_model,orchestration,qa,qa_routes}.py；tests/conftest.py |
| 766fadcc0a8256b955565933e91f9f26cce7e7aa | backend/scholar_graph/{agent_tools,orchestration}.py；tests/test_qa_hybrid_retrieval.py，单Chunk证据约束 |
| 37a595ea8a5233b712690c70c6f1e3a916814455 | backend/README.md，配置、融合公式、真实耗时与元数据 |
| 3a6cbc215fa2c17e309bb14b28c18cfc458a5aff | tests/{run_hybrid_retrieval_acceptance,run_hybrid_no_key_probe,audit_hybrid_retrieval}.py；tests/reports/hybrid-retrieval-{live,attempt-1,no-key,audit}.json及hybrid-retrieval-pytest.xml |

本报告单独提交，完整哈希和实际push原文见最终交付回报。没有修改frontend、contracts、docs、prompts、experiments、test-records；不需变更数据契约口径。

依据：[BGE-M3官方说明](https://huggingface.co/BAAI/bge-m3)、[bge-reranker-large官方说明](https://huggingface.co/BAAI/bge-reranker-large)。性能数字来自本机实际运行，不从模型卡推测。
