# GROBID 默认路径增强验收（打磨 A）

日期：2026-10-26。输入为 **官方 pdf/ 真文件**。

**最终结论：通过。** 默认HTTP单/批上传及arXiv下载后的工厂已接入可回落GROBID增强，原有契约零改动。

开工 `git pull --ff-only`：`Already up to date.`；主干及干净工作区基线：`a7aacc3672bb8a58e3e723b0ce235ce3b9c19515`。

## 默认接线和边界

UploadService默认工厂与ArxivFetcher默认工厂都创建Pipeline(enhancement=DefaultGrobid())，MinerU产生完整记录后执行增强。抓取仍复用原ParseJob、门禁与存储，没有另建解析管线。默认启用，服务地址GROBID_URL默认http://127.0.0.1:8070，超时默认60秒、上限120秒；显式禁用设SCHOLAR_GRAPH_GROBID_ENABLED=false。Docker Desktop配置提供host.docker.internal:8070；已从现有后端容器实测该地址isalive为200 true。

本单官方两组入口为工作树的真实默认ASGI应用（TestClient，不传pipeline_factory），本地MinerU和HTTP GROBID均实际执行，没有替换引擎或TEI。现有已运行的部署镜像没有在本单重建，不能把工作树验证写成旧镜像已更新。前端源码未动；只读核实原同源代理会转发全部X-ScholarGraph-*响应头。

独立CLI --grobid-url和Pipeline(grobid=...)继续保留显式严格行为；本单安全回落用于新接入的默认工厂。相同文件哈希命中不可覆盖旧记录，复用原方法并标cache_hit=true/grobid_attempted=false，不谎称再次调用；历史记录不会自动迁移增强。

## 合并规则

| 字段/内容 | 权威和冲突规则 | 空值规则 |
| --- | --- | --- |
| title / abstract | 默认上传采用经门禁的GROBID非空值；arXiv已核验非空值优先 | null/空数组不清空原值 |
| authors / institutions | 同上；合并层过滤明显机构作者和工作声明/会议脚注，原值和过滤原因留证 | 过滤后为空则保留本地值 |
| year | 保留本地或已核验arXiv值；GROBID header可能是版本日期，不自动采用 | 未知保留null |
| doi | 已知本地或arXiv裸DOI优先，GROBID只补空DOI | 空值不清空 |
| id/schema_version/file_hash/page_count/has_text_layer/source/arxiv_id/version | 保留文件身份和既有来源；GROBID不覆盖 | 沿用原值 |
| 全部Chunk、正文、章节、PDF物理页、bbox | MinerU/OCR为准，GROBID不替换 | 沿用原值 |
| ReferenceEntry | 保留本地number/ref_id/paper_id；同序号还必须有一致DOI/arXiv、规范化标题或作者年份依据，显式标题/标识冲突不合并；通过后采用GROBID非空字段 | 无法对齐条目保留本地，不猜补、不追加无锚点条目 |
| CitationLink | 保留已有真实引用出现位置，仅从实际Chunk重建并补充合法链接 | Schema、外键和锚点门禁均保留 |

GROBID处理的是隔离的候选副本；不可达、超时、非2xx、无效XML/Schema、改动Chunk、无可合并内容都丢弃整个候选并回落原MinerU结果。不会把部分修改混入发布组。其异常位于可选解析元数据，整体ParseStatus仍可completed，error_code/error_message保持成功口径。

## 可选方法标记（没有新增契约字段）

- 单上传、详情、解析状态：响应头 `X-ScholarGraph-Parse-Meta`，percent-encoded UTF-8 JSON，CORS已暴露。
- 批量成功项及arXiv抓取封装：可选 `parse_metadata`。四类记录及ParseStatus响应体仍为原契约。
- 本地逐次记录：`jobs/<job_id>/parse-metadata.json`；逐条参考匹配依据仅留本地，响应给数量摘要，避免过大响应头。
- method：`mineru`为明确禁用；`mineru+grobid`为真实调用且有可发布增强；`mineru-fallback`为尝试失败或无可合并内容。另有grobid_attempted、耗时、fallback_reason、grobid_error、增强字段及参考数量。

## 官方 Attention v7 两组实测

输入：`pdf/1706.03762v7.pdf`，2215244字节，SHA-256：`bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697`。两组均为新空目录，上传前状态404；原件下载哈希一致。输出根目录：`D:\AI_Workspace\Tasks\scholar-graph\data\grobid-default-live\7b92b4e4076b4c08b1f38efde1ffecaf`。

真实服务镜像：`grobid/grobid:0.9.1-crf`；`/api/isalive`=true；版本响应：`{"version": "0.9.1", "revision": "0.9.1"}`。关闭header/citations consolidation，无Crossref补全。

| 组 | HTTP | method | 上传秒 | GROBID阶段秒 | Chunk/参考/引用 | 端点检查 |
| --- | ---: | --- | ---: | ---: | --- | --- |
| 服务可用 | 201 | mineru+grobid | 11.989063 | 4.951727 | 175/40/69 | 9/9 |
| 真实TCP不可达 | 201 | mineru-fallback | 9.360166 | 2.067636 | 175/40/69 | 9/9 |

不可达组使用真实绑定但未监听的本地TCP端点，连接真实拒绝；GROBID容器保持运行。该组未用HTTP mock，也未把停用配置的mineru分支当作不可达回落。

可用组增强字段：`["title", "authors", "institutions", "abstract"]`；参考匹配 40 条，实际字段增强 39 条。无法匹配 0 条；有1条匹配但无可用非空改动，保留本地值。两组Chunk逐条完全相同。

可用组题录样本：

```json
{
  "title": "Attention Is All You Need",
  "authors": [
    "Ashish Vaswani",
    "Noam Shazeer",
    "Niki Parmar",
    "Jakob Uszkoreit",
    "Llion Jones",
    "Aidan N Gomez",
    "Łukasz Kaiser",
    "Illia Polosukhin"
  ],
  "institutions": [
    "University of Toronto"
  ],
  "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely. Experiments on two machine translation tasks show these models to be superior in quality while being more parallelizable and requiring significantly less time to train. Our model achieves 28.4 BLEU on the WMT 2014 Englishto-German translation task, improving over the existing best results, including ensembles, by over 2 BLEU. On the WMT 2014 English-to-French translation task, our model establishes a new single-model state-of-the-art BLEU score of 41.8 after training for 3.5 days on eight GPUs, a small fraction of the training costs of the best models from the literature. We show that the Transformer generalizes well to other tasks by applying it successfully to English constituency parsing both with large and limited training data.* Equal contribution. Listing order is random. Jakob proposed replacing RNNs with self-attention and started the effort to evaluate this idea. Ashish, with Illia, designed and implemented the first Transformer models and has been crucially involved in every aspect of this work. Noam proposed scaled dot-product attention, multi-head attention and the parameter-free position representation and became the other person involved in nearly every detail. Niki designed, implemented, tuned and evaluated countless model variants in our original codebase and tensor2tensor. Llion also experimented with novel model variants, was responsible for our initial codebase, and efficient inference and visualizations. Lukasz and Aidan spent countless long days designing various parts of and implementing tensor2tensor, replacing our earlier codebase, greatly improving results and massively accelerating our research.† Work performed while at Google Brain.",
  "year": null,
  "doi": null
}
```

过滤/暂不采用的原始候选：

```json
{
  "discarded_header_values": {
    "authors": [
      "Google Brain",
      "Google Research"
    ],
    "institutions": [
      "Work performed while at Google Research. 31st Conference on Neural Information Processing Systems (NIPS 2017)"
    ]
  },
  "withheld_header_fields": {
    "year": {
      "candidate": 2023,
      "reason": "GROBID header日期未区分版本日期与发表年，不自动采用。"
    }
  }
}
```

首轮未加保护的原始结果另存grobid-default-path-initial-live.json：作者中混入Google Brain/Research、机构中混入工作脚注、year为2023。最终保留8个人名、1个机构；2023仅留方法日志，论文year保持null，没有猜填发表年。此保护是有限规则，不把CRF输出宣称为通用实体识别或题录准确率评测。

上游CRF仍有质量边界：这里的1个机构不代表全文机构全集，摘要还夹带部分贡献脚注。本单验证接线、回落、合规发布与本例保护规则，不宣称完整题录抽取准确率通过。

不可达组回落原文：`GROBID 服务不可达，未采用增强结果。`；错误封装：`{"error_code": "UPSTREAM_ERROR", "message": "GROBID 服务不可达，未采用增强结果。", "details": {"failure_kind": "unavailable"}}`。结果为completed/100，原MinerU数据完整发布。

## 回归和审计

| 层/证据 | 结果 |
| --- | --- |
| 最终全量 | 628项：623通过、5跳过、0失败、0错误 |
| 快速层 | 163通过；提交钩子实际执行；不依赖Docker或模型 |
| 默认路径新增测试 | 15项：成功/不可达/超时/HTTP/XML/配置错误/坏Schema或Chunk回滚/空结果/重传/批量/arXiv/合并质量保护 |
| 两组真实端点 | 各9项检查通过，包含Schema/真实锚点、详情方法持久化、原PDF哈希 |
| 最终审计 | 25/25通过 |

全量命令：`python tests/run_regression.py full --no-key --corpus-dir pdf`。真实本地BGE-M3/Chroma、真实自制OCR、官方541页长书均执行；5项无Key真模型跳过不算通过。组件回归隔离关闭可选GROBID，新测试显式启用模拟响应；真实GROBID由上表两组官方实测证明。arXiv默认工厂的接线另由合成Atom/PDF测试覆盖，不写成真实公共抓取已通过。

首次全量为627项，620通过、5跳过、2失败：新增日志对直接调用_publish而未启动parse的既有去重用例不兼容；已修复并定向22项通过，失败JUnit保留。随后627项全量为622通过/5跳过；题录质量保护新增1项后，以最终628项结果为准。另一次定向运行曾因临时目录父路径缺失出现11个setup错误，目录修正后原35项定向通过，旧证据在data/grobid-default-tests/保留。没有把这些失败/错误改写为通过。

两组实际生成物均为官方pdf/真文件；普通单元测试使用自制PDF/TEI。未调用生成式大模型、未使用真实API Key；语料pdf/仍忽略且未跟踪。contracts/、frontend/、docs/、prompts/、experiments/、test-records/相对开工基线零改动。现有运行的旧后端镜像不计入这次新接线部署验收。

- [最终两组实测](grobid-default-path-live.json)
- [最终JUnit](grobid-default-path-pytest.xml)
- [首轮失败JUnit](grobid-default-path-initial-pytest.xml)
- [保护前题录原值](grobid-default-path-initial-live.json)
- [审计](grobid-default-path-audit.json)

全量JUnit执行时间：358.005秒（公开OCR模型准备另计）。原始控制台见[grobid-default-path-console.txt](grobid-default-path-console.txt)。

## 本单提交

| 完整哈希 | 事项 |
| --- | --- |
| 939c693d2ffa8203ca343acd3bafd5e7cfe502bb | 默认上传与arXiv抓取接入GROBID增强并安全回落留证 |
| e1a5342dcedbb48b508d8ef5fa5a399b5de15a3c | 兼容直接发布记录时尚无解析方法上下文的调用 |
| 841949bde1de5cff257b9fd43f1f640fc15ada1c | 合并层拦截机构作者与版本年份污染并保留原始候选 |
| 2f5f59152490c2b9312a2941c3ef7f73df15f532 | 补充默认GROBID配置合并说明与官方双路验收审计 |

最终审计与证据提交自身哈希见交付回报。
