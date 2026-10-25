# 模块三英→中翻译端点验收（2026-10-25）

开工前在D盘工作目录执行git pull --ff-only，输出Already up to date.，工作区干净；主干为`349369388b31033dc624ace815b9189a0569b4e4`。本单仅改backend/与tests/，不改前端、既有契约或API草案。

最终结论：英→中翻译端点、段级对齐与全文Markdown已落地并完成真实DeepSeek验收。摘要和Introduction各抽查一段；全文175段通过结构、源Chunk对齐和数字回溯校验，不把这等同于175段逐句专家审校。

语料为**官方 pdf/ 真文件1706.03762v7.pdf**，复用此前解析入库的175个Chunk；本单没有重新解析PDF，没有用公开替代文件或自制样例冒充这次实测。官方文件与已落盘PaperMeta.file_hash的SHA-256一致：

`bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697`。PDF与完整源文/译文响应只留本地忽略目录，不进入Git或镜像。

## 端点与对齐结构

`POST /api/v1/papers/{paper_id}/translate`，JSON请求；沿用现有/api/v1前缀。请求的scope必填，target默认zh且仅接受zh。示例：

```json
{"scope":"abstract","target":"zh"}
{"scope":"section","target":"zh","section_path":["1 Introduction"]}
{"scope":"selection","target":"zh","chunk_ids":["<已落盘chunk_id>"]}
{"scope":"full","target":"zh"}
```

section_path按源Chunk路径前缀取章节及子章节；selection按真实chunk_id选整段，按文档顺序返回。重复/未知Chunk、无该范围、额外参数、中→英target=en均返回422；论文不存在404。Chunk内字符选区、中→英全文、前端同步滚动均不在本单。

| 响应字段 | 含义 |
| --- | --- |
| paper_id / scope / target | 论文id、本次范围、zh |
| segments | 段级对齐列表，一条源Chunk对应一条译文 |
| markdown | full时为整篇Markdown字符串，其他范围为null |
| metadata | 服务商、请求模型名、耗时、安全调用统计、本次术语表与对齐说明 |

segments每项固定为`{source_chunk_id,source_text,translated_text,paper_id,page_number,section_path,type}`。source_chunk_id直接取源Chunk.chunk_id，page_number为PDF物理页；paper_id/章节/类型均由服务端从落盘Chunk复制，模型不能指定这些字段。长Chunk仅在内部拆分翻译，再拼回一个对齐项，不生成新的业务记录。Pydantic校验传输封装，原有contracts/所有schema与example零改动。

无Key或缺模型名返回HTTP502，统一三字段`{error_code,message,details}`，error_code=UPSTREAM_ERROR，消息为“DeepSeek环境变量未设置，未调用模型。”；没有摘录式假译文。上游HTTP、连接或超时也明确返回UPSTREAM_ERROR，不暴露原始上游正文。批次校验失败最多再试一次，仍不合法时不返回任何部分译文。

## 真模型实测

调用方为现有DeepSeekClient，直接请求官方api.deepseek.com；Key/模型变量仅从启动环境读取，二者均已设置。以下为最后一轮成功请求的用量，不是整个开发会话累计。只报告请求模型名，不推测服务商别名背后的底层版本。

| 范围 | HTTP/结论 | 对齐段数 | 耗时（秒） | 模型调用数 | token总数 | Markdown字符数 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| abstract | 200 / passed | 6 | 3.377079 | 1 | 2111 | 0 |
| section | 200 / passed | 5 | 3.762612 | 1 | 1842 | 0 |
| full | 200 / passed | 175 | 60.044221 | 11 | 46379 | 39148 |

请求模型：`deepseek-chat`。完整安全调用元数据见translation-live-results.json：provider/model/phase/elapsed_seconds/prompt_tokens/completion_tokens/total_tokens/http_status/status，无Key、请求消息或思考内容。

abstract实际返回6段，包含源解析归入Abstract的标题、正文、arXiv信息与贡献/会议脚注；不把6段都称为摘要正文。Introduction返回标题与4个正文段，共5段。PaperMeta.title与abstract在这份既有源记录中为空；范围选择来自真实Chunk章节，不伪造元数据锚点。

### 摘要抽查

源Chunk：`paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0001-c00010`；PDF第1页，章节路径`["Abstract"]`。

原文：

> The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely. Experiments on two machine translation tasks show these models to be superior in quality while being more parallelizable and requiring significantly less time to train. Our model achieves 28.4 BLEU on the WMT 2014 Englishto-German translation task, improving over the existing best results, including ensembles, by over 2 BLEU. On the WMT 2014 English-to-French translation task, our model establishes a new single-model state-of-the-art BLEU score of 41.8 after training for 3.5 days on eight GPUs, a small fraction of the training costs of the best models from the literature. We show that the Transformer generalizes well to other tasks by applying it successfully to English constituency parsing both with large and limited training data.

译文：

> 主流的序列转导模型基于复杂的循环或卷积神经网络，其中包含一个编码器和一个解码器。性能最好的模型还通过注意力机制将编码器和解码器连接起来。我们提出了一种新的简单网络架构——Transformer，它完全基于注意力机制，完全摒弃了循环和卷积。在两个机器翻译任务上的实验表明，这些模型在质量上更优，同时具有更强的并行性，且训练所需时间显著更少。我们的模型在 WMT 2014 英德翻译任务上达到 28.4 BLEU，比现有最佳结果（包括集成模型）高出 2 BLEU 以上。在 WMT 2014 英法翻译任务上，我们的模型在八块 GPU 上训练 3.5 天后，建立了新的单模型最先进水平 BLEU 分数 41.8，这只是文献中最佳模型训练成本的一小部分。我们通过将 Transformer 成功应用于英语成分句法分析（无论训练数据充足还是有限），表明它能很好地泛化到其他任务。

### Introduction抽查

源Chunk：`paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0002-c00016`；PDF第2页，章节路径`["1 Introduction"]`。

原文：

> Recurrent neural networks, long short-term memory [13] and gated recurrent [7] neural networks in particular, have been firmly established as state of the art approaches in sequence modeling and transduction problems such as language modeling and machine translation [35, 2, 5]. Numerous efforts have since continued to push the boundaries of recurrent language models and encoder-decoder architectures [38, 24, 15].

译文：

> 循环神经网络，特别是长短期记忆网络 [13] 和门控循环神经网络 [7]，已被牢固确立为序列建模和转导问题（如语言建模和机器翻译）中的最先进水平方法 [35, 2, 5]。此后，大量工作持续推动着循环语言模型和编码器-解码器架构的边界 [38, 24, 15]。

抽查结论：摘要保留编码器/解码器与纯注意力架构、28.4 BLEU、超过2 BLEU、41.8 BLEU、3.5天与八个GPU等原文信息；章节保留循环网络、长短期记忆、门控循环网络、编码器-解码器与引文编号，未在样本中发现新增事实。两个样本通过；语言自然度仍有可润色空间，不宣称已完成整篇人工校译。

## 全文版式与保护规则

full覆盖175/175个已落盘Chunk（166 text、4 table、5 figure）；为每段生成唯一`<a id="chunk_id"></a>`定位点。标题按已有section_path层级生成；表格和公式保留源Chunk顺序及已有HTML/Markdown结构。论文标题段已真实翻译为“注意力就是你所需要的一切”。原解析没有独立formula类型Chunk，公式保护另由自制LaTeX/公式块测试覆盖，不谎称该官方文件已有完整数学结构识别。

代码块、行内代码、LaTeX、公式块与HTML/表格结构从文字片段中移除，不交给模型改写；由代码在原位置拼回。链接与表格行列标记保留。正文数字通过Decimal按源值核验，允许4.5 million→450万、36M→3600万及2 Aug 2023→2023年8月2日，拒绝数字新增、改值和丢失；英文may等普通词不能冒充月份数字依据。

固定NLP术语词表加本次有原译依据且前后兼容的新术语贯穿所有批次；普通介词短语不由模型擅自升为必须逐字匹配的术语。已有术语不许改写。结构和数字校验只证明对应关系与源值可回溯，不证明所有翻译语义都正确。

全文保持源解析已有结构，不重新推断未入库的标题属性、不复原PDF字体/栏位、不补造Chunk中缺失的图片。原解析误分的章节路径、纯文本数学表达式和无网格表格会继承；不把Markdown称为PDF原版式重建。

端点同步完成后返回，不是流式翻译或后台队列。源文上限600000字符；内部约3000字符单元，批次最多4000字符或32单元，max_tokens=8192；旧问答默认2400不变。批次间检查900秒预算，上游网络超时60秒，不声称绝对900秒强制中断持续传输的HTTP读取。

## 开发轮次中的失败与修正

下表保留真实失败及中断记录，早期失败不计为通过；最终结论以上述最后一轮及实现散列匹配审计为准。

| 轮次 | 各范围结果/原始错误 |
| --- | --- |
| 1 | abstract: failed；保护占位符顺序或内容改变 / section: failed；术语未按本次词表统一：state of the art / full: failed；英文正文未翻译为中文 |
| 2 | abstract: passed / section: passed / full: failed；术语未按本次词表统一：separable convolutions |
| 3 | abstract: passed / section: passed / full: failed；保护占位符内容、数量改变 |
| 4 | abstract: failed；译文出现新增或改写的数字 / section: passed / full: failed；译文出现新增或改写的数字 |
| 5 | abstract: passed / section: passed / full: failed；译文出现新增或改写的数字；单元u87；原数字{'2014': 2, '4.5': 1, '3': 1, '37000': 1, '36': 1, '32000': 1, '38': 1, '25000': 2}；译数字{'2014': 2, '450': 1, '3': 1, '37000': 1, '3600': 1, '32000': 1, '38': 1, '25000': 2} |
| 6 | abstract: passed / section: passed / full: failed；译文出现新增或改写的数字；单元u87；原数字{'2014': 2, '4.5E+6': 1, '3': 1, '3.7E+4': 1, '36': 1, '3.2E+4': 1, '38': 1, '2.5E+4': 2}；译数字{'2014': 2, '4.5E+6': 1, '3': 1, '3.7E+4': 1, '3.6E+7': 1, '3.2E+4': 1, '38': 1, '2.5E+4': 2} |
| 7 | abstract: passed / section: passed / 会话中断，未记录完整三项；不计为通过。 |
| 8 | abstract: passed / section: passed / full: passed |
| 9 | abstract: passed / section: passed / full: failed；术语未按本次词表统一：complexity per layer |
| 10 | abstract: passed / section: passed / full: passed |

修正包含：语法允许的数字语序不再误拒；代码/公式/结构改为代码拼回；数字校验支持确定性单位/日期换算；只接纳有一致依据的术语；模型同时接收保护后的正文与同一文字片段的原文上下文，完整翻译标题。失败批次仍不返回部分结果，未通过放宽锚点或伪造译文掩盖失败。

## 回归与安全审计

最终全量JUnit：384项，384通过，0失败，0错误，0跳过，276.782000秒；包含真实PaddleOCR、既有模型/SSE及新增翻译实连测试。

无Key/模型变量子进程：42项，41通过，1项真实翻译测试跳过，0失败/错误，8.446000秒。离线协议与未配置502错误测试照常执行。

新增测试使用自制契约样例，覆盖四种范围、源顺序和真实锚点、超长段内部拆分、代码/LaTeX/表格保护、术语规则、数字校验、上游失败、重试上限、部分批次失败整次不成功、非法输入与范围、预算限制及无Key跳过；不把这些自制样例测试称为官方PDF质量测试。

独立审计31项通过：源文件散列、最终实现散列、段级manifest、真实Chunk锚点、数字与保护片段、Markdown定位点、安全元数据、JUnit、变更目录、pdf/忽略与未跟踪、真实Key字节不在本单文件中。未修改frontend/、contracts/、docs/、prompts/、experiments/、test-records/。

复现（已具备本地依赖、同一官方源PDF/已解析数据；实连需要启动环境中的Key与模型变量）：

```powershell
backend/.venv/Scripts/python.exe tests/run_translation_acceptance.py --full
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --run-real-model --basetemp data/translation-reproduce-tests --junitxml tests/reports/translation-pytest.xml
backend/.venv/Scripts/python.exe tests/audit_translation_acceptance.py
backend/.venv/Scripts/python.exe tests/render_translation_report.py
```

探针在tests/reports/translation-live-results.json追加运行轮次；完整响应只写忽略的data/translation-acceptance/，Git仅留有限原译样本、段级散列及安全元数据。JUnit包括translation-pytest.xml与translation-no-key-pytest.xml，审计为translation-audit.json。无Key的pytest应跳过real_model实连项，探针也明确标skipped。

## 转达WorkBuddy

使用上述POST与segments.source_chunk_id匹配阅读器源段；page_number和section_path用于回溯，markdown用于全文视图。selection当前为整Chunk选择。翻译服务无Key是明确错误，不是摘录回落。前端同步滚动与中→英全文由后续单负责，本单没有实现或声称已接通。现有Docker镜像未重建，容器使用新端点须重建镜像。

实现依据：[DeepSeek Chat Completions与JSON输出](https://api-docs.deepseek.com/api/create-chat-completion/)。
