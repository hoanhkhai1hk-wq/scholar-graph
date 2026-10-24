# 长书验证：公开等价物、非官方 pdf/ 文件

公开等价物、非官方 pdf/ 文件；未运行或宣称官方三用例通过。

结论：**失败。下载的是完整541页原书，但当前管线200页上限拒绝输入，未切块、未进入索引，长书分页未通过。** 没有用小文档替代，也没有拆小、绕过或修改生产限制。

## 公开来源与文件核对

作者官方仓库发布：[Understanding Deep Learning v5.0.3](https://github.com/udlbook/udlbook/releases/tag/v5.0.3)，资产[完整免费PDF](https://github.com/udlbook/udlbook/releases/download/v5.0.3/UnderstandingDeepLearning_02_09_26_C.pdf)。GitHub公开API显示资产大小22,344,992字节，实际下载同大小。原PDF仅在被忽略的D盘data/，不提交整本书。公开等价物、非官方 pdf/ 文件。

开工基线：7ac617a4ff818cc3840069098fc3477ca614b0e8；下载HTTP 200，耗时4.487秒；物理页数541；SHA-256 f8237d393163900fa8e43210e680a3f987b45ccac7750b372e156fae3df0bf32。下载重定向不保留query签名；没有API Key。以哈希固定整书输入，未传页范围参数。

## 当前配置下实跑原始结果

以完整PDF字节POST /api/v1/papers，没有改生产代码、解析页数限制、错误码或数据契约。

```json
{
  "request": {
    "method": "POST",
    "path": "/api/v1/papers",
    "file_sha256": "f8237d393163900fa8e43210e680a3f987b45ccac7750b372e156fae3df0bf32"
  },
  "http_status": 422,
  "response": {
    "error_code": "PARSE_FAILED",
    "message": "PDF 页数必须在 1 到 200 之间。",
    "details": null
  },
  "measurement": {
    "sample_interval_seconds": 0.05,
    "rss_peak_bytes": 161959936,
    "private_peak_bytes": 146825216,
    "sample_count": 6,
    "includes_descendant_processes": true,
    "rss_start_bytes": 93491200,
    "elapsed_seconds": 0.386671,
    "scope": "整个测试进程及全部子进程的采样合计，不是精确瞬时峰值；不含下载阶段。"
  }
}
```

解析状态原文：

```json
{
  "path": "/api/v1/papers/paper-f8237d393163900fa8e43210e680a3f987b45ccac7750b372e156fae3df0bf32/parse-status",
  "http_status": 200,
  "response": {
    "schema_version": "1.1.0",
    "paper_id": "paper-f8237d393163900fa8e43210e680a3f987b45ccac7750b372e156fae3df0bf32",
    "status": "failed",
    "progress": 5,
    "current_stage": "解析未完成",
    "error_code": "PARSE_FAILED",
    "error_message": "PDF 页数必须在 1 到 200 之间。"
  }
}
```

状态历史为queued→parsing(5)→failed(5)。Pipeline._inspect在调用MinerU、OCR和indexing之前检查1–200页，故本书541页被拒绝；文件22.3MB未触发50MiB大小限制。错误是实际PARSE_FAILED/422，不能泛称下载失败或内存不足。

| 指标 | 实测 |
| --- | --- |
| 实际输入物理页数 | 541 |
| 已发布Chunk总数 | 0，输入在分块前失败 |
| 是否进入indexing | 否 |
| 索引耗时 | null/未进入，不写0秒 |
| 上传请求耗时 | 0.386671秒，含复制/检查/失败状态发布 |
| 采样RSS峰值 | 161959936字节（154.457031MiB） |
| 采样起始RSS | 93491200字节 |
| 采样private峰值 | 146825216字节 |
| 内存采样 | 每0.05秒，6次，测试进程及其全部子进程合计 |

这是早期拒绝过程的内存采样峰值，不是完整541页切块/向量索引的内存需求；50ms采样可能漏掉短瞬态，不冒称OS精确高水位。下载与文件来源检查不在上传计时/内存窗口，其他OCR验证进程不是其子进程，未计入。没有调用Chroma/BGE索引；null比伪造索引完成耗时更准确。

## 分页检查原文

```json
{
  "paper_list": {
    "path": "/api/v1/papers?page=1&page_size=100",
    "http_status": 200,
    "response": {
      "items": [],
      "page": 1,
      "page_size": 100,
      "total": 0,
      "total_pages": 0,
      "has_next": false
    }
  },
  "chunks_first": {
    "path": "/api/v1/papers/paper-f8237d393163900fa8e43210e680a3f987b45ccac7750b372e156fae3df0bf32/chunks?page=1&page_size=100",
    "http_status": 404,
    "response": {
      "error_code": "PAPER_NOT_FOUND",
      "message": "无该论文记录。",
      "details": null
    }
  },
  "chunks_overflow": {
    "path": "/api/v1/papers/paper-f8237d393163900fa8e43210e680a3f987b45ccac7750b372e156fae3df0bf32/chunks?page=999&page_size=100",
    "http_status": 404,
    "response": {
      "error_code": "PAPER_NOT_FOUND",
      "message": "无该论文记录。",
      "details": null
    }
  }
}
```

论文列表仍可返回合法空分页壳，但目标长书未落盘，chunks首/越界页均404。**空库分页正常不等于长书分页通过**。未发布任何该书PaperMeta/Chunk组，不使用其他论文或小样例的分页结果顶替。

## 复现与范围

公开等价物、非官方 pdf/ 文件。默认命令会从固定作者公开发布链接完整下载；不会修改生产页数限制：

```powershell
backend/.venv/Scripts/python.exe tests/run_public_longbook.py --output-root data/public-equivalents/longbook-reproduce --report data/public-equivalents/longbook-reproduce.json
```

交付本次实际复用已下载原书及其公开下载manifest，脚本核对SHA-256与541页后才上传：

```powershell
backend/.venv/Scripts/python.exe tests/run_public_longbook.py --source data/public-equivalents/understanding-deep-learning.pdf --download-provenance data/public-equivalents/book-download.json --output-root data/public-equivalents/longbook-release --report tests/reports/public-equivalent-longbook.json
```

完整下载元信息、请求/响应、内存与状态记录见[JSON](public-equivalent-longbook.json)。本case文件组为run_public_longbook.py、本Markdown及JSON；不改业务功能/契约，不声称官方三用例通过。
