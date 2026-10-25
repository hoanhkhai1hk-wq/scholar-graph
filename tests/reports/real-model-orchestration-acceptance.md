# 真模型联调、LangGraph编排与Function Calling验收

日期：2026-10-25。输入为**官方 pdf/ 真文件**，Attention v7与BERT N19-1423；语料仅保留在本地 pdf/，未进入Git。

开工前 main：`4f6ae8cbb5959e061cad292a394a8879e33abc73`；`git pull --ff-only` 原文为 `Already up to date.`，开工工作区干净。

本轮最终六题6/6通过，错前提示例拒答，真实多篇Agent在第3轮通过代码校验。全量回归326通过、0失败、0错误、0跳过；另以无Key子进程验证实连测试1项跳过。历史未通过轮次单列，未改写为通过。

## 环境、模型与检索实际方式

| 环境变量 | 状态 |
| --- | --- |
| SCHOLAR_GRAPH_QA_MODE | 已设置 |
| DEEPSEEK_MODEL | 已设置 |
| DEEPSEEK_API_KEY | 已设置 |

服务商deepseek；请求模型名deepseek-chat（来自DEEPSEEK_MODEL），后端httpx 0.28.1调用官方HTTPS /chat/completions。只报告接口请求模型名，不推测服务商内部别名版本。规划和问答节点均为真实调用；校验节点为代码。thinking设为disabled，以使用required工具选择。

本轮QA及Agent search均为**词法检索**：读取已有Chunk，扩展有限中英文检索词，选择最多24个连续证据窗口，单段≤600字符；未接入模块四BGE-M3/Chroma作为QA检索器。既有向量服务及其历史验收未改动。本轮模型负责选择真实原文，最终回答是有锚点的原文摘录，并非开放式生成文章。

Key只从进程环境读取，未写入文件、代码或日志。不保留原始请求/响应、思考内容、工具原始查询正文或论文全文；下列答案是任务要求的已批准QAAnswer内容。LangGraph关闭检查点和外部追踪，状态只在内存。状态含paper_ids、bundles、evidence、anchors；不含Key或客户端对象。

## 官方语料与已落盘记录

| 本地文件 | PDF物理页数 | Chunk数 | paper_id |
| --- | ---: | ---: | --- |
| pdf/1706.03762v7.pdf | 15 | 175 | `paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697` |
| pdf/N19-1423.pdf | 16 | 277 | `paper-987545ffb087f1ece898142c403a516baeabeb70ce19089397fac6f7db12c3d4` |

Attention沿用已校验的解析结果；BERT通过已有模块一管线入库。审计重新核对PDF SHA-256、全部记录与锚点，不重造论文元数据。源摘要散列见审计JSON。

## 六道命题例题逐题结果

题面来自本地命题PDF，仅规范空格与β下标。所有页码为PDF物理页，锚点四项使用原契约。数字passed只说明与同一源Chunk字面回溯通过，不评价科学结论真实性。

### 第1题：通过

论文Attention Is All You Need的第6作者是谁，在哪个公司/机构工作？

**核对结论：**第6作者为 Aidan N. Gomez，首页列出的机构为 University of Toronto。作者块按行/列坐标辅助恢复顺序，未把同块另一位作者误当第6位。

HTTP 200；程序检查：`{"aidan": true, "toronto": true, "not_refused": true, "anchors_present": true}`。

已批准答案原文：

```text
【证据 A】
Aidan N. Gomez ∗  † University of Toronto aidan@cs.toronto.edu
```

数字回溯：`not_applicable`；拒答：`false`；锚点：

```json
[
  {
    "paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697",
    "page_number": 1,
    "section": [],
    "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0001-c00004"
  }
]
```

真实模型调用1次；累计调用耗时1.213039秒；token合计7349。

### 第2题：通过

其中Adam优化器的超参数β₁和β₂分别被设置为了多少？

**核对结论：**Adam：β₁=0.9，β₂=0.98。

HTTP 200；程序检查：`{"0.9": true, "0.98": true, "not_refused": true, "anchors_present": true, "numeric_backtrace": true}`。

已批准答案原文：

```text
【证据 A】
We used the Adam optimizer [20] with β 1  = 0.9, β 2  = 0.98 and ϵ = 10 −9 . We varied the learning rate over the course of training, according to the formula:
```

数字回溯：`passed`；拒答：`false`；锚点：

```json
[
  {
    "paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697",
    "page_number": 7,
    "section": [
      "5 Training",
      "5.3 Optimizer"
    ],
    "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0007-c00088"
  }
]
```

真实模型调用1次；累计调用耗时1.298705秒；token合计1324。

### 第3题：通过

这篇论文中提到的Transformer架构，在训练Base模型时使用了多少个GPU？具体是什么型号？

**核对结论：**Base训练使用8个GPU，型号为 NVIDIA P100。

HTTP 200；程序检查：`{"8": true, "p100": true, "not_refused": true, "anchors_present": true, "numeric_backtrace": true}`。

已批准答案原文：

```text
【证据 A】
We trained our models on one machine with 8 NVIDIA P100 GPUs. For our base models using the hyperparameters described throughout the paper, each training step took about 0.4 seconds.
```

数字回溯：`passed`；拒答：`false`；锚点：

```json
[
  {
    "paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697",
    "page_number": 7,
    "section": [
      "5 Training",
      "5.2 Hardware and Schedule"
    ],
    "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0007-c00086"
  }
]
```

真实模型调用1次；累计调用耗时2.003068秒；token合计7319。

### 第4题：通过

Transformer (big)模型在English-to-German任务上的BLEU分数是多少？当时的State-of-the-art模型是多少？提升了多少？

**核对结论：**English-to-German：Transformer (big) 为28.4 BLEU；当时表中的最佳既往结果为26.36（Deep-Att + PosUnk Ensemble）。代码计算28.4−26.36=2.04 BLEU；论文正文的措辞是超过2.0，并非逐字写2.04。

HTTP 200；程序检查：`{"28.4": true, "26.36": true, "not_refused": true, "anchors_present": true, "numeric_backtrace": true}`。

已批准答案原文：

```text
【证据 A】
<td>ConvS2S Ensemble [9]</td><td>26.36</td><td>41.29</td><td>7.7 · 10<sup>19</sup></td><td>1.2 · 10<sup>21</sup></td></tr><tr><td>Transformer (base model)</td><td>27.3</td><td>38.1</td><td>3.3 ·</td><td>10<sup>18</sup></td></tr><tr><td>Transformer (big)</td><td>28.4</td><td>41.8</td><td>2.3 ·</td><td>10<sup>19</sup></td></tr></tbody></tabl

【证据 B】
On the WMT 2014 English-to-German translation task, the big transformer model (Transformer (big) in Table 2) outperforms the best previously reported models (including ensembles) by more than 2.0 BLEU, establishing a new state-of-the-art BLEU score of 28.4.
```

数字回溯：`passed`；拒答：`false`；锚点：

```json
[
  {
    "paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697",
    "page_number": 8,
    "section": [
      "5 Training",
      "5.4 Regularization"
    ],
    "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0008-c00093"
  },
  {
    "paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697",
    "page_number": 8,
    "section": [
      "6 Results",
      "6.1 Machine Translation"
    ],
    "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0008-c00098"
  }
]
```

差值由Decimal代码计算：`28.4 - 26.36 = 2.04 BLEU`，两个源数字均已通过锚点检查；派生说明与源锚点保存在结果JSON中，不把派生值塞回原文摘录。

真实模型调用1次；累计调用耗时2.393084秒；token合计8816。

### 第5题：通过

请列出论文中引用的关于“Layer Normalization”的参考文献（References）的完整作者和年份。

**核对结论：**Jimmy Lei Ba、Jamie Ryan Kiros、Geoffrey E. Hinton，2016年。

HTTP 200；程序检查：`{"ba": true, "kiros": true, "hinton": true, "2016": true, "not_refused": true, "anchors_present": true}`。

已批准答案原文：

```text
【证据 A】
[1] Jimmy Lei Ba, Jamie Ryan Kiros, and Geoffrey E Hinton. Layer normalization. arXiv preprint  arXiv:1607.06450 , 2016.
```

数字回溯：`passed`；拒答：`false`；锚点：

```json
[
  {
    "paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697",
    "page_number": 10,
    "section": [
      "References"
    ],
    "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0010-c00127"
  }
]
```

真实模型调用1次；累计调用耗时1.197946秒；token合计7547。

### 第6题：通过

根据《Attention Is All You Need》和《BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding》。请对比：BERT的架构和原始Transformer的Encoder有什么承袭关系？BERT丢弃了原始Transformer的哪个部分？

**核对结论：**BERT承袭Vaswani等人的Transformer编码器实现，采用多层双向Transformer encoder。原始Transformer包含encoder和decoder；BERT保留编码器、没有原始序列到序列decoder部分。这是两篇架构原文的对照归纳，不是新增跨篇因果主张。

HTTP 200；程序检查：`{"encoder": true, "bidirectional": true, "decoder_source": true, "vaswani_source": true, "both_supported": true}`。

逐篇1：

已批准答案原文：

```text
【证据 A】
The Transformer follows this overall architecture using stacked self-attention and point-wise, fully connected layers for both the encoder and decoder, shown in the left and right halves of Figure 1, respectively.

【证据 B】
• The encoder contains self-attention layers. In a self-attention layer all of the keys, values and queries come from the same place, in this case, the output of the previous layer in the encoder. Each position in the encoder can attend to all positions in the previous layer of the encoder.

【证据 C】
In addition to attention sub-layers, each of the layers in our encoder and decoder contains a fully connected feed-forward network, which is applied to each position separately and identically. This consists of two linear transformations with a ReLU activation in between.

【证据 D】
Decoder:  The decoder is also composed of a stack of N = 6 identical layers. In addition to the two sub-layers in each encoder layer, the decoder inserts a third sub-layer, which performs multi-head attention over the output of the encoder stack. Similar to the encoder, we employ residual connections around each of the sub-layers, followed by layer normalization. We also modify the self-attention sub-layer in the decoder stack to prevent positions from attending to subsequent positions. This masking, combined with fact that the output embeddings are offset by one position, 
```

数字回溯：`passed`；拒答：`false`；锚点：

```json
[
  {
    "paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697",
    "page_number": 3,
    "section": [
      "3 Model Architecture"
    ],
    "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0003-c00029"
  },
  {
    "paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697",
    "page_number": 5,
    "section": [
      "MultiHead(Q, K, V ) = Concat(head 1 , ..., head h )W O",
      "3.2.3 Applications of Attention in our Model"
    ],
    "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0005-c00058"
  },
  {
    "paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697",
    "page_number": 5,
    "section": [
      "MultiHead(Q, K, V ) = Concat(head 1 , ..., head h )W O",
      "3.3 Position-wise Feed-Forward Networks"
    ],
    "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0005-c00061"
  },
  {
    "paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697",
    "page_number": 3,
    "section": [
      "3 Model Architecture",
      "3.1 Encoder and Decoder Stacks"
    ],
    "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0003-c00032"
  }
]
```

逐篇2：

已批准答案原文：

```text
【证据 A】
Model Architecture  BERT’s model architecture is a multi-layer bidirectional Transformer encoder based on the original implementation described in Vaswani et al. (2017) and released in the tensor2tensor library. 1  Because the use of Transformers has become common and our implementation is almost identical to the original, we will omit an exhaustive background description of the model architecture and refer readers to Vaswani et al. (2017) as well as excellent guides such as “The Annotated Transformer.” 2  In this work, we denote the number of layers (i.e., Transformer bloc

【证据 B】
former is often referred to as a “Transformer encoder” while the left-context-only version is referred to as a “Transformer decoder” since it can be used for text generation.

【证据 C】
 BERT uses a bidirectional Transformer. OpenAI GPT uses a left-to-right Transformer. ELMo uses the concatenation of independently trained left-to-right and right-to-left LSTMs to generate features for downstream tasks. Among the three, only BERT representations are jointly conditioned on both left and right context in all layers. In addition to the architecture differences, BERT and OpenAI GPT are fine-tuning approaches, while ELMo is a feature-based approach.
```

数字回溯：`passed`；拒答：`false`；锚点：

```json
[
  {
    "paper_id": "paper-987545ffb087f1ece898142c403a516baeabeb70ce19089397fac6f7db12c3d4",
    "page_number": 3,
    "section": [
      "3 BERT"
    ],
    "chunk_id": "paper-987545ffb087f1ece898142c403a516baeabeb70ce19089397fac6f7db12c3d4-p0003-c00040"
  },
  {
    "paper_id": "paper-987545ffb087f1ece898142c403a516baeabeb70ce19089397fac6f7db12c3d4",
    "page_number": 4,
    "section": [
      "4 We note that in the literature the bidirectional Trans-",
      "3.1 Pre-training BERT"
    ],
    "chunk_id": "paper-987545ffb087f1ece898142c403a516baeabeb70ce19089397fac6f7db12c3d4-p0004-c00056"
  },
  {
    "paper_id": "paper-987545ffb087f1ece898142c403a516baeabeb70ce19089397fac6f7db12c3d4",
    "page_number": 13,
    "section": [
      "A.1 Illustration of the Pre-training Tasks"
    ],
    "chunk_id": "paper-987545ffb087f1ece898142c403a516baeabeb70ce19089397fac6f7db12c3d4-p0013-c00212"
  }
]
```

真实模型调用4次；累计调用耗时13.439502秒；token合计34176。

多篇响应仍先返回evidence_table，再返回逐篇QAAnswer与引用该表的synthesis；综合只并列已核验摘录，并明确跨篇因果不可验证。完整表与数字检查逐项证据在结果JSON，无额外业务Schema。

## 故意错前提拒答

论文用Adam的β₁=0.5、β₂=0.6进行训练，对吗？请确认。

```text
拒答：本文本无相关证据，未检索到足以回答该问题的原文或所需数值；不能据此断言全文未报告。
```

HTTP 200，refused=true；数字状态为`unverifiable`。本次模型拒绝提供支持错误前提的摘录，未把β₁=0.5、β₂=0.6标为通过；此例没有输出纠正数字，不能冒充已给出纠错证据。第2题另有0.9/0.98的真实锚点答案。

独立回归还覆盖模型给出原文纠错证据时，代码将具名β参数冲突标failed并附锚点；该项为模拟协议测试，不冒充第二次真实纠错调用。

## 完整真实走图记录

LangGraph 1.2.17：plan→retrieve→qa→validate；校验不通过回retrieve，最多3轮；超限进入refuse。以下来自单独一次真实多篇任务，而非手写轨迹。默认deepseek /compare本身也使用联合图。

| 节点 | 轮次 | 耗时秒 | 证据数 | 校验 | 原因 |
| --- | ---: | ---: | ---: | --- | --- |
| plan | 0 | 1.670669 | 0 | 未执行校验 |  |
| retrieve | 1 | 0.111068 | 24 | 未执行校验 |  |
| qa | 1 | 6.595030 | 24 | 未执行校验 |  |
| validate | 1 | 0.002303 | 24 | 未通过 | 同一Chunk的摘录跨度超出600字符。 |
| retrieve | 2 | 1.742928 | 20 | 未执行校验 |  |
| qa | 2 | 4.892951 | 20 | 未执行校验 |  |
| validate | 2 | 0.003004 | 20 | 未通过 | 同一Chunk的摘录跨度超出600字符。 |
| retrieve | 3 | 1.867047 | 20 | 未执行校验 |  |
| qa | 3 | 4.504974 | 20 | 未执行校验 |  |
| validate | 3 | 0.009933 | 20 | 通过 |  |

真实两次驳回原因：同一Chunk所选两处原文跨度超过600字符；重新检索并重新问答，第三次获得合法连续原文。未返回前两轮未校验草稿。最终fallback_reason=null、validated=true；没有把回落或超限拒答写成本次业务成功。

## Function Calling实际调用轨迹

模型规划响应包含实际tool_calls，后端执行工具，将同一tool_call_id的role=tool结果回传后再调用问答模型。下表只保留参数摘要和返回摘要，查询正文不落盘。

| 轮次 | 工具 | 模型调用ID | 参数摘要 | 返回摘要 | 工具耗时秒 |
| ---: | --- | --- | --- | --- | ---: |
| 1 | search | `call_00_U5HwkHLmRmW3bfcz6bt42879` | Attention；query_chars=76；limit=12 | 12条；lexical；succeeded | 0.045727 |
| 1 | search | `call_01_cclucgoz8OjQXd7DcbkY7382` | BERT；query_chars=72；limit=12 | 12条；lexical；succeeded | 0.065177 |
| 2 | search | `call_00_aGz0NiWCAkxRZXvVuXko8080` | Attention；query_chars=50；limit=10 | 10条；lexical；succeeded | 0.051545 |
| 2 | search | `call_01_HcYwbBWo1z7LGrB1w3ih2840` | BERT；query_chars=63；limit=10 | 10条；lexical；succeeded | 0.066522 |
| 3 | search | `call_00_GpBkJNbosZs4iC0RMO2n8989` | Attention；query_chars=50；limit=10 | 10条；lexical；succeeded | 0.049849 |
| 3 | search | `call_01_5pfAGKVvN3bi3wh2I3XL9888` | BERT；query_chars=63；limit=10 | 10条；lexical；succeeded | 0.065752 |

三个工具均定义了严格参数Schema（全字段必填、禁止额外字段）：search复用真实Chunk词法取证；graph_query复用既有构图；arxiv_fetch按名复用现有抓取服务和模块一解析，需要显式allow_fetch及fetcher。本轮对比不授权新增论文，HTTP Agent中的arxiv_fetch会明确拒绝。真实演示为search；graph_query/arxiv_fetch仅验证实际分派及模拟抓取失败，未宣称三工具都完成线上调用。

## 上游错误、回落与兼容性

默认deepseek上游失败返回HTTP502及原统一三字段UPSTREAM_ERROR，无原始上游正文；模拟覆盖HTTP401/429/500/302的脱敏错误返回。显式?agent=true允许模型不可用时回落原QuestionAnswerer，元数据记录MODEL_CONFIGURATION_UNAVAILABLE或UPSTREAM_ERROR；模拟覆盖规划/问答失联。没有人为中断本轮真实服务来冒充失联实测。

单篇QAAnswer与跨篇三字段响应不变，全部已有契约零改动，端点仍19条。仅新增可选agent查询参数及UTF-8百分号编码的X-ScholarGraph-QA-Meta / X-ScholarGraph-Agent-Meta响应头；已在原CORS中暴露，保留既有同源代理。前端零修改，未验证前端展示；需用户转达WorkBuddy：如展示元数据，先解码这两个头。

## 保留的历史未通过结果

| 轮次 | 六题通过 | 拒答示例 | Agent | 当轮缺陷及处理 |
| --- | --- | --- | --- | --- |
| real-model-orchestration-attempt-1.json | 4/6 | 未通过 | 未通过 | 作者题拒答；多篇证据不足；故意错问未拒答；Agent三轮未过门禁。后续加入题设具名参数检查、逐篇贡献规则。 |
| real-model-orchestration-attempt-2.json | 4/6 | 通过 | 通过 | 作者列块顺序误判；多篇HTTP422（同Chunk多段处理）。后续加入版面行序提示与连续原文合并。 |
| real-model-orchestration-attempt-3.json | 4/6 | 通过 | 通过 | 单窗口检索试验丢失SOTA表格证据，多篇一侧拒答。恢复双窗口并改联合规划。 |
| real-model-orchestration-attempt-4.json | 5/6 | 通过 | 通过 | BLEU缺前SOTA表格分数，其他五题通过。增加表格覆盖校验及反馈，再取得最终六题通过结果。 |

最终作者序号门禁增加后单独重跑作者题，仍通过，证据保存在real-model-final-author-check.json；未覆盖此前整组六题结果。校验脚本重新核对该结果与其余答案。作者版面辅助不是通用完整作者抽取器，本篇只验收第6作者，不宣称所有作者/任意版面已正确恢复。

## 调用元数据汇总

| 范围 | 次数 | 调用耗时累计秒 | prompt tokens | completion tokens | total tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| 最终六题、拒答、单独Agent、作者补验、全量实连测试 | 18 | 45.523904 | 122870 | 8533 | 131403 |
| 四轮历史报告内保留的调用 | 50 | 121.172964 | 388617 | 22297 | 410914 |

上述服务商均deepseek，请求模型名均deepseek-chat。累计耗时是各次请求耗时之和，不是整单墙钟时间。初次连通额外1次：1.217860秒、37 prompt + 5 completion = 42 token；此前仅输出安全元数据未存原始正文，另记不重复计表。早期HTTP422丢失响应头的调用没有完整元数据，未计入汇总；不把已留存统计冒充完整账单。

## 回归与审计

全量命令：

```powershell
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --run-real-model --basetemp data/real-model/full-regression-final --junitxml tests/reports/real-model-orchestration-pytest.xml
```

结果：326通过、0失败、0错误、0跳过，JUnit总耗时120.626秒。旧306项加新增20项（19项模拟/确定性、1项真实模型连通）。真实OCR也已启用；新模型协议测试使用自制数据，与本轮官方真文件实测分开登记。pip check：`No broken requirements found.`。

另以删除三个变量的子进程运行test_deepseek_live.py --run-real-model：1项跳过，0失败/错误，退出码0；证据real-model-no-key-pytest.xml。无Key不是实连通过。

审计重新校验11份QAAnswer、21处锚点出现及比较表；核对六题、错误前提拒答、[false,false,true]的真实校验序列和6次实际search工具调用。contracts/frontend/prompts/experiments/test-records相对基线无改动；pdf/忽略且Git未跟踪语料；全部本单文件完成真实Key字节扫描，未检出。

## 复现与交付文件

- tests/run_real_model_acceptance.py：使用现有官方落盘记录运行真实六题、拒答和Agent；--author-guard-only为最终作者补验。需要进程已有变量，不读取或写入Key文件。
- tests/reports/real-model-orchestration-results.json：最终批准答案、完整锚点/数字检查、安全元数据与真实走图。
- tests/reports/real-model-orchestration-attempt-1.json 至 attempt-4.json：保留历史失败。
- tests/reports/real-model-final-author-check.json：最终作者门禁补验。
- tests/audit_real_model_acceptance.py 与 real-model-orchestration-audit.json：无模型调用的本地源数据复核；重跑需要本地原文件/记录。
- tests/write_real_model_report.py：仅渲染批准答案与安全元数据。
- tests/reports/real-model-orchestration-pytest.xml 与 real-model-no-key-pytest.xml：全量与无Key跳过证据。

技术依据：[DeepSeek工具调用协议](https://api-docs.deepseek.com/guides/tool_calls/)、[DeepSeek聊天API](https://api-docs.deepseek.com/api/create-chat-completion/)、[LangGraph图API](https://docs.langchain.com/oss/python/langgraph/graph-api)。
