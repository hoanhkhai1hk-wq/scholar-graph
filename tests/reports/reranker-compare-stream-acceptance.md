# 二段精排与跨篇比较 SSE 验收

本单为后端实现与验收，输入使用**官方 pdf/ 真文件**对应的已解析 Attention v7、BERT 记录；本单未重新解析论文。没有修改前端、docs、prompts、experiments、test-records 或任何业务契约。`pdf/` 仍被忽略，模型权重与语料不进 Git。

开工前 `git pull --ff-only` 为 `Already up to date.`，main 与工作区均干净，基线为 `9f30f089548d4211445b132deab30ca1efc87a0b`。

本次官方 **6/6 题通过**，真实 DeepSeek 跨篇 SSE 通过；**本机精排未达到 5 秒预算，官方六题实际使用 hybrid + RRF，精排接受 0 次、RRF 回落 9 次**。未将回落标成 reranked。独立完整温态诊断为 5.977314、6.880856 秒，均超预算；这是性能限制，不报告成精排达标。

## 实现与预算

每篇先召回向量前24块与现有词法前24块，等权 RRF 粗排。只将 **RRF 前10块**传入 `bge-reranker-large`，不是把36/48候选全部送入精排。精排有效时用其结果替换前10名前缀，其余召回保留在后，继续沿用显式首页作者布局规则。所有候选和最终答案仍过原锚点、连续引文、数字门禁。

本地模型仍为 CPU、float32、2线程、每对最多512 token，文本最多2000字符；BAAI/bge-reranker-large 固定快照 `55611d7bca2a7133960a6d3b71e083071bbfc312`。BGE-M3/Chroma 固定快照与版本逐次见 live.json 的 `retrieval[].model_revision/versions`，没有把词法结果称为向量结果。

默认路径新增隔离常驻 reranker worker，同一 Python/模型目录复用模型。每请求 **5秒预算包含锁等待、尚未完成的冷加载、IPC及推理**，不因显式指定 cross_encoder 绕过预算。冷加载未就绪则本次 RRF，worker可在后台完成预热；推理超时终止该worker，避免迟到结果污染下次请求。忙、模型缺失、worker失败、非法分数/候选均保留明确回落原因。旧36候选的性能缓存不再禁止新前10策略重测。worker 不继承 API_KEY/TOKEN/SECRET/PASSWORD 类变量，离线读权重，不保存问题或原始模型响应。

| 实测项目 | 结果 | 口径 |
|---|---:|---|
| 旧36候选参考 | worker 27.557949秒；推理12.423250秒 | 旧单历史值，非本单重跑 |
| 首次冷请求预算回落 | 5.011231秒 | 10块，含冷加载等待；未输出精排结果 |
| 显式预热 | worker启动到就绪34.356854秒；模型构造9.881998秒 | 单独记录，没有从冷请求中隐去 |
| 预热后的受预算调用 | 5.079360秒 | 超预算终止；采用 RRF |
| 独立完整温态诊断1 | 推理5.976726秒；IPC总段5.977314秒 | 返回10个真实分数；超过5秒 |
| 独立完整温态诊断2 | 推理6.880165秒；IPC总段6.880856秒 | 返回10个真实分数；超过5秒 |

完整诊断另一次启动为27.324113秒、模型构造8.928843秒，CPU/内存状态与前一预热不同，不混为同一次测量。诊断输入是 Attention 前10个原始 Chunk，与 live.json 冷/温基准一致，**不是六题实际的 RRF 前10候选池**。诊断的90秒时限只用于得到完整耗时，没有改变生产HTTP的5秒预算。六题实际候选均经前10限制，在预算截止时明确回落，原因与耗时逐次保留。

## 官方六题重跑

新建隔离数据目录，复制已校验的官方记录后重新建立该目录的真实 Chroma 索引：Attention 175块、BERT 277块，共452块。Attention 首次索引140.697586秒，BERT首次219.104455秒；其余请求索引指纹命中，仍有独立 BGE worker 的导入、构造和查询开销。首次 Attention 模型构造3.990261秒、启动到就绪31.185456秒；首次 BERT 构造3.896898秒、启动到就绪25.656381秒。不能把构造耗时与旧端到端15–20秒混比。

调用真实 DeepSeek，服务商 `deepseek`，模型 `deepseek-chat`；向量与精排均本地运行。环境只记录“已设置/未设置”，无Key写文件。批准答案与每条锚点、数字检查在 [live JSON](reranker-compare-stream-live.json)，未保存请求正文、思考正文或完整未校验模型JSON。

| 题 | 核对结果 | 实际召回 / 精排 | 候选证据窗口数（每次retrieve） | 最终锚点数 | 数字校验 | HTTP / 耗时 | 结论 |
|---|---|---|---|---|---|---|---|
| 1 第6作者与机构 | Aidan N. Gomez；University of Toronto | hybrid / rrf | 24 | 1 | not_applicable | 200 / 182.807194秒 | 通过 |
| 2 Adam β₁/β₂ | 0.9、0.98 | hybrid / rrf | 24 | 1 | passed | 200 / 45.110794秒 | 通过 |
| 3 Base GPU | 8 × NVIDIA P100 | hybrid / rrf | 24 | 1 | passed | 200 / 42.889806秒 | 通过 |
| 4 BLEU与原SOTA | 28.4，对照26.36，原文“more than 2.0 BLEU” | hybrid / rrf | 24 | 2 | passed | 200 / 46.278626秒 | 通过 |
| 5 Layer Normalization作者/年 | Jimmy Lei Ba、Jamie Ryan Kiros、Geoffrey E. Hinton，2016 | hybrid / rrf | 24 | 1 | passed | 200 / 42.516475秒 | 通过 |
| 6 BERT/Transformer结构 | 两篇真实摘录：Transformer编码器/解码器结构与BERT双向Transformer encoder；依据encoder stack对照，无虚构decoder内容 | hybrid / rrf | 24 / 24 / 24 / 24 | Attention 5、BERT 4 | passed / passed | 200 / 413.386189秒 | 通过 |

每题同时要求非拒答、锚点存在、schema合规、原文回溯；数字题passed的检查必须有evidence。六题的核对标准未因回落放宽。第6题的4次检索汇合成30个不同Chunk证据，最终输出9个锚点；不是把候选窗口数当成最终引用数。

锚点示例，论文id公共前缀为 `paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697`：

- 题1：物理第1页，section=[]，chunk后缀`-p0001-c00004`。
- 题2：物理第7页，`5 Training / 5.3 Optimizer`，`-p0007-c00088`。
- 题3：物理第7页，`5 Training / 5.2 Hardware and Schedule`，`-p0007-c00086`。
- 题4：物理第8页，`6 Results / 6.1 Machine Translation`的`-p0008-c00098`，表格锚点`-p0008-c00093`保留源解析的章节标签，没有在本单擅自重标。
- 题5：物理第10页，`References`，`-p0010-c00127`。
- 题6：逐篇完整四字段锚点见live.json第6项及evidence_table，综合逐条回指E编号。

## 跨篇 SSE

最终路径：`POST /api/v1/compare/stream`。请求沿用同步比较：

```json
{"paper_ids":["论文1的id","论文2的id"],"question":"跨篇问题"}
```

论文2至10篇且不得重复，资源/参数错误在发送SSE响应头之前按原HTTP三字段错误体返回。前端未改，用户可将本节转给WorkBuddy接入。

| 事件 | 数据与校验语义 |
|---|---|
| mode | 模式、token_streaming、fallback_reason；声明draft未校验，final须校验 |
| node_start / node_end | plan/retrieve/qa/validate；轮次、耗时、证据数、校验通过/原文驳回原因；retrieve带实际方法 |
| tool_start / tool_end | 真实模型Function Calling，工具名、来源、参数摘要、返回证据数 |
| token | 只来自真实qa上游增量；`verified:false`、`channel:model_json_draft`，按attempt分离重试草稿 |
| final | 沿用同步`{evidence_table,per_paper,synthesis}`；每篇QAAnswer不增加字段；锚点、原文和数字校验后才发 |
| done | 最终状态、`verified:true`、方法/模型/走图元数据；拒答与completed区分 |
| error | 真实上游/执行错误的原三字段封装；随后done，不发编造final |

真实 TCP 使用临时 Uvicorn 与 httpx 逐事件消费，非TestClient缓冲样本。Cache-Control=`no-cache, no-transform`、X-Accel-Buffering=`no`。队列有界，断连取消上游；校验仍最多3轮。部分关键事件：

| 真实DeepSeek事件 | 到达时间（秒） | 内容摘要 |
|---|---:|---|
| plan开始 / 完成 | 0.387646 / 2.558164 | 真模型规划 |
| 四次search完成 | 45.180787 / 82.534823 / 119.068205 / 155.937949 | 每次12个证据，真实Function Calling |
| retrieve完成 | 155.940803 | 去重后33个真实Chunk证据，hybrid + rrf |
| qa开始 | 155.946614 | 未输出经校验结论 |
| 首个未校验增量 | 157.254072 | verified=false，随后共1,739个增量事件 |
| qa完成 | 163.216935 | JSON草稿留内存校验，不当作final |
| validate完成 | 163.254710 | 通过，1轮，无驳回 |
| final | 163.419922 | 校验后逐篇答案与证据表 |
| 结束 | 163.425875 | completed，verified=true |

共1,758个事件；1,739是**增量事件数**，不是模型token统计。首字等待主要在检索，不宣称低延迟。规划调用1,388 tokens，流式问答28,094 tokens，合计29,482；本单六题加该SSE合计9次真实模型调用、99,051 tokens，服务商/模型/耗时/HTTP/状态逐次存元数据。

无Key且无向量模式，真实TCP耗时0.479763秒、11个事件、0个token增量、无模型/工具调用。mode明确“回落模式、非 token 流式”，method=lexical-fallback、ranking_method=lexical，fallback_reason=MODEL_CONFIGURATION_UNAVAILABLE。对`Which optimizer?`，Attention有原文摘录，BERT本次词法未召回而refused=true，done.status=refused；不声称BERT全文没有优化器，不编造补答。

首轮无Key协议探针退出1：错误要求每篇都非拒答，将上述合法拒答计为失败。首轮完整结果保留在 [first-probe JSON](reranker-compare-stream-first-probe.json)。只修正协议验收为“有效答案或经过门禁的真实拒答”，重跑真实TCP后协议通过；BERT仍拒答，六题质量验收仍严格要求非拒答。无Key、无向量、运行中向量失败三个分支另有确定性单测；运行中失败在qa前补发mode，不产生假token。

所有未校验增量日志只保存字符长度与SHA-256，不保存delta原文；最终批准答案保留。最终比较综合仍为原代码的证据摘录并列与E编号，不引入自由生成的无依据综合。

## 可选传输元数据与兼容性

12份业务schema零改动；没有为流式另造答案格式。仅在既有HTTP元数据头或SSE传输层增加以下可选信息：

- `ranking_method`：reranked / rrf / lexical / mixed / none。
- `fallback_reasons`，以及`retrieval[].ranking_method/fallback_reason`。
- 实际可得时的`rerank.cold_start/startup`，候选数、预算与阶段耗时。
- `mode.draft_verified/final_verified`、`done.verified/answer_format`，描述草稿与final语义，不写入QAAnswer。

`method`原有hybrid/vector/lexical-fallback口径保留。向量成功但精排超预算时是hybrid+rrf，不能写reranked。模型回落原因与检索/精排回落原因分开。方法同步覆盖单篇同步、Agent、单篇SSE、同步比较、比较SSE；元数据头仍使用现有百分号编码JSON与已有CORS暴露规则。

## 回归、审计与复现

| 运行 | 总数 | 通过 | 失败/错误 | 跳过 | JUnit耗时 |
|---|---:|---:|---:|---:|---:|
| 首轮全量，修正路由断言前 | 648 | 642 | 1 / 0 | 5 | 557.715秒 |
| 最终全量，修正后完整重跑 | 648 | 643 | 0 / 0 | 5 | 549.903秒 |
| 最终快速层（提交钩子） | 187 | 187 | 0 / 0 | 0 | 44.080秒 |
| 路由定向检查 | 4 | 4 | 0 / 0 | 0 | 1.63秒（控制台） |

最终全量包含两项真实PaddleOCR测试、真实BGE-M3/Chroma推理及官方541页长书解析索引；都不是skip。真实向量4块、1024维；worker39.997522秒，其中模型构造4.461144秒、启动到就绪29.866500秒。长书实际6,859块、索引4.422秒。向量版本为Chroma 1.5.9、FlagEmbedding 1.4.2、torch 2.14.1+cpu、transformers 5.20.2。两项旧有record_property/xunit2告警保留，属性仍在JUnit中，未计为失败或抹去告警。

5项无Key跳过原规则保持：真模型3D图注、DeepSeek连通、单篇SSE、英→中翻译、中→英翻译，**跳过不计通过**。本单真实六题与比较SSE单独使用环境中已配置的DeepSeek运行，不以这些skip充数。

最终确定性审计76/76项通过：官方文件与已落盘记录哈希、运行时代码哈希、六题schema/原文/数字回溯、每次方法与前10上限、两个SSE样本、真实OCR/向量/长书未跳过、5项真模型跳过规则、首轮失败证据、保护目录零差异及不回显的环境Key精确扫描。审计中的“通过”不改变本机精排0次接受、9次RRF回落的实测结论。

首轮失败原文与计数保存在 [修正前全量JUnit](reranker-compare-stream-before-route-count-fix-full.xml)：`test_nineteen_business_routes_including_module_six`，`assert 30 == 29`。最终全量是修正后从头跑满648项，不是拼接首轮与定向结果。

确定性新增覆盖：RRF前10限制、召回尾部保留、精排顺序、旧36候选缓存不误用、非法候选/分数、冷启动/忙/超时、强制模式不得越预算、worker密钥隔离；跨篇草稿与final分离、三种回落、上游错误不造final、三轮重试、资源错误先于SSE头。单元测试使用自制记录/模拟provider，与官方真文件及真实模型验收分开。

首次全量触发路由计数断言29→30的失败；断言已更新并增加`/compare/stream`检查，且将该组API测试加入快速层。保留首次失败JUnit，不以定向4项通过替代修复后的全量。

复现命令（Windows本仓库环境）：

```powershell
backend/.venv/Scripts/python.exe tests/run_reranker_compare_stream_acceptance.py
backend/.venv/Scripts/python.exe tests/run_reranker_top10_benchmark.py
backend/.venv/Scripts/python.exe tests/run_regression.py full --no-key --corpus-dir pdf --junit tests/reports/reranker-compare-stream-full.xml
backend/.venv/Scripts/python.exe tests/audit_reranker_compare_stream.py
```

实连命令依赖用户已注入的模型环境与现有官方已解析记录；无模型环境标记跳过，不计为真实实连通过。完整诊断不改变默认5秒预算。独立`--fallback-only`只重跑非token样本并保留六题与原始首轮记录。

文件证据：

- [live JSON：六题完整批准答案、锚点、方法、两个TCP样本](reranker-compare-stream-live.json)
- [完整10块温态诊断](reranker-top10-benchmark.json)
- [首轮探针](reranker-compare-stream-first-probe.json)
- [最终快速层JUnit](reranker-compare-stream-fast.xml)、[全量JUnit](reranker-compare-stream-full.xml)、[定向路由检查](reranker-compare-route-count.xml)
- [确定性审计JSON](reranker-compare-stream-audit.json)，审计脚本位于`tests/audit_reranker_compare_stream.py`

为本地模型腾出内存，验收期间临时停止GROBID容器；回归后已恢复`scholar-graph-grobid-grobid-1`。首次40.688599秒就绪探针未通，后续再次查询`http://127.0.0.1:8070/api/isalive`为HTTP 200、true（该次HTTP探针0.302754秒，不是总启动耗时）。原后端8000、前端3000容器仍healthy；没有修改前端源码或容器配置。

现有Docker镜像未在本单重建；上述均为宿主机实测，不声称容器已包含新端点。后端说明位置为`backend/README.md`的“二段精排与跨篇比较流式端点”。

## 提交与文件组

- `1036214f5bed3aae87d05b4876fc25d1f291c41b`：`backend/scholar_graph/qa_retrieval.py`、`rerank_worker.py`、`vector_worker.py`，以及`tests/test_qa_two_stage.py`。
- `4f5a27be8c88270e86cdf682dea13d01ce36d5a5`：`backend/scholar_graph/orchestration.py`、`qa_sse.py`、`qa_routes.py`，以及`tests/test_compare_sse.py`、`tests/regression_layers.py`。
- `e45945db8dd0e5fde5aa73f12a7994c85b8fd31e`：`backend/README.md`，`tests/audit_reranker_compare_stream.py`、`run_reranker_compare_stream_acceptance.py`、`run_reranker_top10_benchmark.py`、`test_qa_two_stage.py`。
- `02455d178b86be6451a5f4f2d7b056becafff676`：`tests/test_api_comparison.py`、`tests/regression_layers.py`、`tests/run_reranker_compare_stream_acceptance.py`。

最后验收提交包含本报告、首轮/最终JUnit、live与完整诊断JSON、审计JSON及加强后的审计脚本；其完整哈希随推送回报提供，避免报告自引用自身提交哈希。

推送后的克隆口径检查发现Windows的CRLF与Git存储的LF会影响原始字节摘要。首轮探针记录保留Windows原始`sha256`，追加`sha256_lf`作为UTF-8/LF规范摘要，审计使用后者；路径采用正斜杠。已直接核对Git中实际存储的日志与规范摘要一致，不需要依赖某台机器的换行配置。
