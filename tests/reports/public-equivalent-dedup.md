# 去重触发验证：公开等价物、非官方 pdf/ 文件

公开等价物、非官方 pdf/ 文件；未运行或宣称官方三用例通过。

开工基线：7ac617a4ff818cc3840069098fc3477ca614b0e8；git pull --ff-only：Already up to date.；main干净。

结论：**原始上传自动去重预警未触发，且没有建议保留v7；本项目标未通过。** 公开抓取端点附带真实arXiv元数据的辅助流程能生成精确身份裁决，但建议manual_review，不等于语义去重或自动保留新版。没有修改业务代码或契约来掩盖结果。

## 公开来源与上传顺序

先从公开arXiv取得1706.03762v7，再取得1706.03762v1，随后按相同顺序以原始PDF字节POST /api/v1/papers。没有改写PDF、注入元数据、Mock解析器或使用Key。两份实际均15个物理页，字节哈希不同，未把版本号或页数猜成来源证据。

| 来源 | 字节数 | SHA-256 | 上传HTTP | Chunk/参考/引用 | 上传秒 |
| --- | ---: | --- | ---: | --- | ---: |
| 1706.03762v7 | 2215244 | bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697 | 201 | 175/40/69 | 8.118367 |
| 1706.03762v1 | 2128686 | 0a9bff1be3575cf9fe26a4a3d3a9175bc791ecec90de8b9deba4cff75d2b9476 | 201 | 162/36/64 | 7.373756 |

来源：[v7](https://arxiv.org/pdf/1706.03762v7)、[v1](https://arxiv.org/pdf/1706.03762v1)。公开等价物、非官方 pdf/ 文件。下载PDF仅留被Git忽略的D盘data/，原始元数据与全部请求/响应、耗时、内存采样见[JSON](public-equivalent-dedup.json)。

## 原始上传：预警及裁决原文

两次上传均201，仅返回PaperMeta，无warning字段。提取出的title=null、authors=[]、doi=null、arxiv_id=null、version=null；未从正文arXiv页眉抽出这些身份字段。第二次上传后按其paper_id查询dedup-decision与diff-summary均404。没有预警可引用，不能把不存在的预警写成已触发。

```json
{
  "decision": {
    "path": "/api/v1/papers/paper-0a9bff1be3575cf9fe26a4a3d3a9175bc791ecec90de8b9deba4cff75d2b9476/dedup-decision",
    "http_status": 404,
    "response": {
      "error_code": "PAPER_NOT_FOUND",
      "message": "无该新版论文的去重记录。",
      "details": null
    }
  },
  "diff": {
    "path": "/api/v1/papers/paper-0a9bff1be3575cf9fe26a4a3d3a9175bc791ecec90de8b9deba4cff75d2b9476/diff-summary",
    "http_status": 404,
    "response": {
      "error_code": "PAPER_NOT_FOUND",
      "message": "无该新版论文的差异记录。",
      "details": null
    }
  }
}
```

原因核对：RecordStore.previous_version依次以共有DOI、arXiv去版本基号、标题+作者精确匹配；本次原始上传缺身份字段，无法配对，因此没有自动比较记录。compare.similarity为词频Counter重叠Dice，不调用已有BGE/Chroma搜索器；相似度也不能说明科研质量。上传端点本来没有专门预警响应封装，本单不改契约或业务形状。

## 真实公开抓取辅助流程：裁决原文

另起干净存储，真实调用POST /api/v1/retrieval/fetch，reference.arxiv_id依次v7、v1，公开API真实元数据进入原解析管线；两次succeeded=true，没有使用缓存Mock或人工身份注入。v1后入库的裁决查询200，similarity=0.933224，human_override=false，recommendation=manual_review。

**old_paper_id是先入库的v7，new_paper_id是后入库的v1。** 这里new不是发表版本更新；若keep_new反而会保留v1。实际manual_review没有自动选择保留v7，不能报“建议保留新版通过”。

系统依据/预警内容原文：

已检出文本变化，但文本相似度和版本序号不能证明新版质量更高；需人工核对差异。

```json
{
  "schema_version": "1.1.0",
  "old_paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697",
  "new_paper_id": "paper-0a9bff1be3575cf9fe26a4a3d3a9175bc791ecec90de8b9deba4cff75d2b9476",
  "similarity": 0.933224,
  "evidence": [
    {
      "anchor": {
        "paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697",
        "page_number": 2,
        "section": [
          "1 Introduction"
        ],
        "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0002-c00016"
      },
      "reason": "已检出文本变化，但文本相似度和版本序号不能证明新版质量更高；需人工核对差异。"
    },
    {
      "anchor": {
        "paper_id": "paper-0a9bff1be3575cf9fe26a4a3d3a9175bc791ecec90de8b9deba4cff75d2b9476",
        "page_number": 1,
        "section": [
          "1 Introduction"
        ],
        "chunk_id": "paper-0a9bff1be3575cf9fe26a4a3d3a9175bc791ecec90de8b9deba4cff75d2b9476-p0001-c00012"
      },
      "reason": "已检出文本变化，但文本相似度和版本序号不能证明新版质量更高；需人工核对差异。"
    }
  ],
  "recommendation": "manual_review",
  "human_override": false
}
```

## 差异摘要原文（公开等价物、非官方 pdf/ 文件）

检出章节文本差异：Unsectioned；1 Introduction；2 Background；2014 English-French dataset consisting of 36M sentences and split tokens into a 32000 word-piece vocabulary [34]. Sentence pairs were batched together by approximate sequence length. Each training batch contained a set of sentence pairs containing approximately 25000 source tokens and 25000 target tokens.；2014 English-French dataset consisting of 36M sentences and split tokens into a 32000 word-piece vocabulary [34]. Sentence pairs were batched together by approximate sequence length. Each training batch contained a set of sentence pairs containing approximately 25000 source tokens and 25000 target tokens. / 5.2 Hardware and Schedule；2014 English-French dataset consisting of 36M sentences and split tokens into a 32000 word-piece vocabulary [34]. Sentence pairs were batched together by approximate sequence length. Each training batch contained a set of sentence pairs containing approximately 25000 source tokens and 25000 target tokens. / 5.3 Optimizer；2014 English-French dataset consisting of 36M sentences and split tokens into a 32000 word-piece vocabulary [34]. Sentence pairs were batched together by approximate sequence length. Each training batch contained a set of sentence pairs containing approximately 25000 source tokens and 25000 target tokens. / 5.4 Regularization；3 Model Architecture；3 Model Architecture / 3.1 Encoder and Decoder Stacks；3 Model Architecture / 3.2 Attention；3 Model Architecture / 3.2 Attention / 3.2.1 Scaled Dot-Product Attention；3 Model Architecture / 3.2 Attention / 3.2.2 Multi-Head Attention；3 Model Architecture / 3.2 Attention / 3.2.3 Applications of Attention in our Model；3 Model Architecture / 3.3 Position-wise Feed-Forward Networks；3 Model Architecture / 3.4 Embeddings and Softmax；3 Model Architecture / 3.5 Positional Encoding；3 We used values of 2.8, 3.7, 6.0 and 9.5 TFLOPS for K80, K40, M40 and P100, respectively.；4 To illustrate why the dot products get large, assume that the components of q and k are independent random variables with mean 0 and variance 1. Then their dot product, q · k = Pdk i=1 qiki, has mean 0 and variance dk.；4 Why Self-Attention；5 Training / 5.1 Training Data and Batching；5 Training / 5.2 Hardware and Schedule；5 Training / 5.3 Optimizer；5 Training / 5.4 Regularization；5 We used values of 2.8, 3.7, 6.0 and 9.5 TFLOPS for K80, K40, M40 and P100, respectively.；5 We used values of 2.8, 3.7, 6.0 and 9.5 TFLOPS for K80, K40, M40 and P100, respectively. / 6.3 English Constituency Parsing；6 Results / 6.1 Machine Translation；6 Results / 6.2 Model Variations；6 Results / 6.3 English Constituency Parsing；7 Conclusion；Abstract；Illia Polosukhin ∗  ‡；MultiHead(Q, K, V ) = Concat(head 1 , ..., head h )W O；MultiHead(Q, K, V ) = Concat(head 1 , ..., head h )W O / 3.2.3 Applications of Attention in our Model；MultiHead(Q, K, V ) = Concat(head 1 , ..., head h )W O / 3.3 Position-wise Feed-Forward Networks；MultiHead(Q, K, V ) = Concat(head 1 , ..., head h )W O / 3.4 Embeddings and Softmax；MultiHead(Q, K, V ) = Concat(head 1 , ..., head h )W O / 3.5 Positional Encoding；References；illia.polosukhin@gmail.com。关键句为对应版本的原文摘录，不代表质量排名。

共38个解析分组列为changed_sections，38条带锚点关键句；完整DiffSummary及所有锚点原样保存在JSON的fetch_controls[1].comparison.diff.response，未删除或改写字段。正文、公式、邮箱等有被当前MinerU归为章节的情况，故本数字不是人工认定的科研章节变化数，也不证明差异定位质量合格。

## 结论与复现边界

公开等价物、非官方 pdf/ 文件：原始上传去重预警未触发；辅助精确arXiv身份配对触发、词频Dice=0.933224，但只要求人工核对，不提供新版质量排序。本单仅验证并报告，不新增向量去重、不改身份抽取或保留策略。

复现（选择新的data目录）：

```powershell
backend/.venv/Scripts/python.exe tests/run_public_dedup.py --output-root data/public-equivalents/dedup-reproduce --report data/public-equivalents/dedup-reproduce.json
```

本case提交包括public_pdf_support.py、run_public_dedup.py、本Markdown和JSON；后续两项及全量回归分别留证。未声称官方三用例通过。
