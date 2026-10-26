# 缺口单 A：语义向量去重验收

2026-10-26（Asia/Shanghai），D:\AI_Workspace\Tasks\scholar-graph，分支main。开工`git pull --ff-only`原文`Already up to date.`，主干完整哈希`8d15d1229451703805848f5ca3023a40fd5e027c`，工作区干净。

已将真实本地BGE-M3论文向量余弦接进上传解析后的去重链路。**官方pdf/真文件三组验收均通过**：v7→v1为0.9441684126150971、换名同内容为1.0、Attention与BERT为0.8336028145662489。最终全量回归511通过，0失败/错误/跳过；审计55通过。前端、docs与12份业务契约零改动，不调用外部Embedding API或真实大语言模型完成本单去重。

## 真实模型、代表文本与上传链路

| 项目 | 本次实际值 |
| --- | --- |
| 模型 | BAAI/bge-m3，快照5617a9f61b028005a4858fdac845db406aefb181 |
| 权重 | 本地pytorch_model.bin，2271145830字节 |
| 权重SHA-256 | b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38；本次重新核验与模块四一致 |
| 调用方/设备 | FlagEmbedding 1.4.2，BGEM3FlagModel，CPU float32 |
| torch / transformers | 2.14.1+cpu / 5.20.2 |
| Python/模型目录 | data/module-four-runtime/.venv/Scripts/python.exe / data/module-four-models/bge-m3 |
| 论文向量 | 最多8个真实正文Chunk，每段最多2000字符、512 token，dense向量均值再归一化，1024维 |
| 运行方式 | 隔离本地worker，运行时离线，移除Key/Token类环境变量，240秒超时，无外部Embedding调用 |

代表段优先覆盖Abstract、Introduction、Conclusion，其余按正文位置等距补足，保持原序；明确References/Bibliography/参考文献节过滤，缺正文时才退到真实text块。代表段id记录在运维元数据，审计逐条核对真实已落盘Chunk。采样不等于全文每个段落都已嵌入，长块尾部可能被截断。

Pipeline在解析、Schema/外键校验之后、正式论文和裁决发布前执行语义评估。裸DOI精确匹配先走身份快速通道，不编码、不虚构分数；其他情况用新论文与库内已发布候选的代表向量计算真实余弦。原检索的dense/sparse融合名次没有被拿来充当余弦。

默认SCHOLAR_GRAPH_DEDUP_MODE=auto，独立于检索开关；复用本机既有模型路径，可用SCHOLAR_GRAPH_VECTOR_PYTHON和SCHOLAR_GRAPH_BGE_M3_PATH指定其他实际本地环境。Linux必须指定实际Python路径，不能使用Windows默认exe路径。off显式禁用。缺模型、超时、非法向量、无效校准配置会明确status=unavailable及fallback_reason，保留原DOI/身份、词频Dice和人工核对兜底；不把失败写成已启用语义向量。

SQLite按模型快照、采样版本和代表文本指纹缓存论文向量；换名同内容可复用。模型文件和向量SQLite都在忽略的data/，不进Git或本单镜像；未声明已完成Docker向量联调。

## 阈值分档与测试依据

校准脚本：[calibrate_semantic_dedup.py](../calibrate_semantic_dedup.py)；原始分数、版本与输入SHA：[semantic-dedup-calibration.json](semantic-dedup-calibration.json)。配置随Python包交付：[semantic_thresholds.json](../../backend/scholar_graph/semantic_thresholds.json)。

使用与三组验收输入**分离**的4篇官方pdf/真文件：Layer Normalization（1607.06450v1）、PPO（1707.06347v2）、ZeRO（1910.02054v3）、Scaling Laws（2001.08361v1），实际原管线解析分别192、36、249、453 Chunk。没有用Attention v7/v1或BERT的验收分数调整阈值。

正样本：每篇同一论文每5个Chunk删去1个，4对，明确为人工缺块扰动，不冒充另一版官方PDF。负样本：4篇不同论文两两组合6对，均使用实际BGE向量。

| 类别 | 全部分数 |
| --- | --- |
| 4个校准正样本 | 0.9411207661、0.9923528256、0.9543000443、0.9137429009 |
| 6个校准负样本 | 0.7248961742、0.7538387679、0.7582957276、0.7604680277、0.8021498198、0.8098823029 |

令N=max(负样本)=0.8098823029271678，P=min(正样本)=0.9137429008639619。N<P时，将观测间隔三等分：

```text
review_threshold = N + (P-N)/3 = 0.8445025022394325
duplicate_threshold = N + 2*(P-N)/3 = 0.8791227015516972
```

这是由观测数据确定的显式规则；若类别交叠、样本不足或有非有限数，校准拒绝生成自动重复策略，不手填一个分数蒙混。两阈值不压在校准样本点上，中间区间留给人工核对。

| 余弦范围 | 分档/实际行为 |
| --- | --- |
| ≥0.8791227015516972 | duplicate（重复候选）；同论文且版本可核验时建议保留较新版本，旧库v7对本次v1给keep_old |
| ≥0.8445025022394325且低于重复阈值 | manual_review；人工核对预警，不宣称已确认重复 |
| <0.8445025022394325 | new_paper；没有其他身份依据时判新论文，不发重复预警 |

持久身份显式冲突，即使高分也不能自动判重复，改人工核对；低分与已有精确身份依据冲突也保留人工核对。未知身份或无法核验版本顺序时，不由向量编造“哪个质量更高”。同一arXiv身份且新版版本号更高可给keep_new，新版真实Chunk作为证据；高相似不会自动删除论文。

另保留每7块删1块的同论文扰动4对，不参与求阈值：0.9819304407、0.9930867911、0.9591820029、0.9331952665，均高于重复阈值。它们与训练是同4篇论文的不同扰动，**不是独立新论文测试集**。独立论文验收为下述Attention与BERT三组。

本次校准范围小，正例是同文缺块，不是任意释义改写的大样本；不据此宣称中文、多学科或所有同主题论文零误报。BERT负例距离人工核对阈值约0.010900，说明需要保留人工核对和后续更广校准。阈值/采样/模型版本绑定，不通过环境变量随意调到验收通过。

## 官方pdf/真文件三组实测

探针：[run_semantic_dedup_acceptance.py](../run_semantic_dedup_acceptance.py)；完整响应、判定、差异及逐候选分数：[semantic-dedup-live.json](semantic-dedup-live.json)。三个独立空库分别进行真实HTTP上传；前一个库的解析结果没有复制到另一个库。worker无Key，实际加载本地权重，status均ready。第一篇无候选时score=null，表示未比较，不伪造0分。

| 组别 | 上传顺序 | 状态码 | Chunk数 | 每次HTTP耗时（秒） | 第二次余弦/判定 | 最终论文数 |
| --- | --- | --- | --- | --- | --- | ---: |
| ①版本 | 1706.03762v7.pdf → 1706.03762v1.pdf | 201 / 201 | 175 / 162 | 25.922 / 25.125 | 0.9441684126150971 / duplicate，keep_old | 2（保留两版供核对） |
| ②换名 | 1706.03762v7.pdf → 相同字节，以attention-renamed.pdf上传 | 201 / 201 | 175 / 175（复用） | 23.485 / 1.250 | 1.0 / duplicate，keep_old | 1 |
| ③不同论文 | 1706.03762v7.pdf → 官方N19-1423.pdf（BERT） | 201 / 201 | 175 / 277 | 23.109 / 23.578 | 0.8336028145662489 / new_paper | 2 |

①预警原文：

> 建议保留库里较新版本（v7）；本次上传为v1。依据同一arXiv身份及PDF原文版本标识，避免降级覆盖；不代表学术质量排名。 本地 BGE-M3 语义余弦=0.944168413；分档=duplicate。本地 BGE-M3 余弦达到重复阈值；版本偏好须另有真实版本依据。

GET /api/v1/papers/{v1_paper_id}/dedup-decision与/diff-summary均HTTP200。DedupDecision.similarity实际为0.9441684126150971，推荐keep_old，human_override=false；证据锚点均经既有Gate校验。DiffSummary为原版本逐章节原文差异，完整summary_text和关键句在JSON。旧解析的章节误分沿用，不把任意章节名变化写成经模型确认的学术变化。

②预警原文：

> 同一文件内容已入库；换名重传触发重复判定，保留已有论文，不重复入库。

元数据reason原文：

> 同一文件内容已入库（SHA-256 一致）；换名重传不新增论文。本地 BGE-M3 向量余弦为 1。

源字节SHA与paper_id完全相同，只有上传文件名不同；第二次复用已发布合法记录，不重复跑解析，向量自余弦取真实缓存向量计算。原DedupDecision要求两个不同PaperMeta，所以不伪造old=new的业务记录；该组裁决/差异端点404是**没有跨版本记录**，不是未触发重复。判定由预警、新元数据头和本地assessment提供，且不发指向不存在自比较的Link。这一限制已明确记录，契约未改。

③判定原文（上传元数据）：

> 本地 BGE-M3 余弦低于人工核对阈值；判为新论文。

预警头不存在；没有创建重复裁决/差异，两个相关查询HTTP404。两篇都真实入库，BERT没有被错误归并。不是用缺失分数或未启用模型冒充不同论文判定。

## 兼容性、回退及人工意见

单篇上传响应仍为原PaperMeta。新增百分号编码UTF-8 JSON头X-ScholarGraph-Dedup-Meta，包含status、method、score、band、reason和可用推荐/回退原因；原预警头保留。CORS暴露新头。批量成功项增加dedup_metadata。仅为传输封装的向后兼容加法，原业务记录字段、必填和类型均未动。

不同文件的DedupDecision在实际向量ready时使用语义分值，证据文字注明算法；原禁用/离线兜底继续为词频Dice，不混写。原schema下限0：若有身份依据导致比较负余弦，similarity截为0，原始负值仍在元数据和证据；三组实测均为正值，没有截断。

完整运维判定落在本地semantic-dedup/assessments/{paper_id}/latest.json，记录候选、策略、真实代表段id；向量在semantic-dedup/vectors.sqlite3。运维封装不是新增业务契约。人工意见仍按原查询优先返回，未覆盖系统记录；新增回归验证人工keep_both在后续系统记录后仍保持。

本单没有更换契约、前端、页面流程、检索模型、推荐评分或图谱实现。旧Docker镜像与未配置本地BGE的部署不会凭空拥有模型，启用方式见[backend README](../../backend/README.md#上传语义向量去重2026-10-26)。Key不写文件，不读写.env；pdf/、模型、SQLite仍被忽略。

## 回归、打包与审计

```powershell
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --run-real-model --basetemp data/semantic-dedup-regression --junitxml tests/reports/semantic-dedup-pytest.xml
```

最终原文：

```text
511 passed in 161.94s (0:02:41)
```

[JUnit](semantic-dedup-pytest.xml)：511总数，511通过，0失败/错误/跳过，JUnit时间161.907秒。原481项＋新增30项。新增覆盖阈值边界、校准交叠拒绝、无效向量、Dice不匹配仍由语义触发、人工核对/低分、冲突身份、DOI免编码、模型超时明确回退、代表段真实且有界、换名幂等、较新版本建议、人工否决保留，以及离线worker/缓存/错误协议。

普通pytest通过显式假向量/禁用大模型保持确定性，不能把其结果当成BGE实连证明；真实BGE由独立官方探针验证。原OCR和既有可选真模型回归也执行；本单向量/校准/官方验收均在移除Key的子进程执行，不靠DeepSeek算分。

本地打包命令：`backend/.venv/Scripts/python.exe -m pip wheel --no-index --no-deps --no-build-isolation ./backend --wheel-dir data/semantic-dedup-wheel-local`，生成scholar_graph_backend-0.1.0-py3-none-any.whl，实际解包确认semantic_thresholds.json内容与策略一致。首次命令误将backend识别为同名外部包，仅生成忽略目录下的wheel、未安装，已纠正为显式本地路径及no-index；不是后端依赖新增。

审计：[audit_semantic_dedup.py](../audit_semantic_dedup.py)、[semantic-dedup-audit.json](semantic-dedup-audit.json)，**55项通过，0失败**。核对实际权重SHA、三组官方文件SHA、真实Chunk、向量维数/模型快照、源码SHA、分档、裁决锚点、阈值重算、4组保留扰动、wheel配置、最终JUnit、Git范围、pdf/忽略与实际Key扫描。前端、contracts、docs、prompts、experiments、test-records与.gitignore相对开工主干均零改动，语料未入Git。

## 提交清单

| 完整哈希 | 对应文件/事项 |
| --- | --- |
| 8e5287927658dc028d514633699815e430143a09 | backend/pyproject.toml；backend/scholar_graph/{semantic_vectors.py,semantic_thresholds.json,vector_worker.py}；tests/test_semantic_vector_adapter.py、calibrate_semantic_dedup.py；校准JSON |
| c22f2af0868da82680c428c498d84cbf2b21669b | backend/scholar_graph/{semantic_dedup.py,pipeline.py}；tests/conftest.py、test_semantic_dedup.py |
| 48bf1de978c5669a1621b8ed31277f5cd77445b5 | backend/scholar_graph/{api_uploads.py,api.py}，兼容响应头、批量元数据、CORS与换名预警 |

其余文档、实测证据与本报告分别提交，完整哈希及实际git push原文见最终交付回报。

模型调用依据：[BGE-M3官方说明](https://huggingface.co/BAAI/bge-m3)、[FlagEmbedding官方实现](https://github.com/FlagOpen/FlagEmbedding)。阈值来自本地记录的实测数据，不来自模型文档中的通用推荐值。
