# 第2项真实问答验收

本目录测试命题的单篇5问、跨篇4问，以及错误前提、改写、追问。模拟单测、真实服务验收、源文语义核对分别记录。`audit_answers.py` 的固定规则是辅助检查，不能代替语义复核。

需要本地 `pdf/` 官方文件、已有 `.env` 的 DeepSeek 配置，以及第1项构建的本地基础镜像。`compose.yml` 只引用环境变量，不包含密钥。验收库固定在 `data/item02-20261028/records`，不会修改个人库。它故意不提供 BGE，验证词法检索降级仍可调用真实模型。

```powershell
docker compose -p scholar-graph-item02 --env-file .env -f tests/item02/compose.yml up -d
backend/.venv/Scripts/python.exe tests/item02/ingest.py
backend/.venv/Scripts/python.exe tests/item02/run_cases.py --run answers-new-run
backend/.venv/Scripts/python.exe tests/item02/audit_answers.py --run answers-new-run --review data/item02-20261028/answers-new-run/source-review.json
backend/.venv/Scripts/python.exe tests/item02/probe_compare.py --run stream-new-run
backend/.venv/Scripts/python.exe tests/item02/run_related.py --run related-new-run
backend/.venv/Scripts/python.exe tests/run_regression.py fast --no-key
```

上传脚本要求全新空验收库。原始运行目录禁止覆盖；重测应使用新名称。语义核对还需要本次独立提取的本地 `independent-source-pages.json`（不随 Git 发布）。页码是 PDF 物理页，从1计数。

复核者需实际核对每题原文，在 `source-review.json` 记录14题的 `case`、`passed`、`notes`、`result_sha256`，顶层注明 `reviewer`。哈希由 `audit_rules.result_digest` 对具体结果计算，不能把旧答案的审核套给新答案。缺少复核、复核失败或哈希不符时，审计退出1；结构化拒答不等于语义正确，语义复核仍为必需。报告区分自动检查与Codex源文复核，后者不是独立人工评审。

可选的真实 BGE 性能路径使用已有 `data/module-four-runtime/.venv/Scripts/python.exe`、`data/module-four-models/bge-m3` 和 `bge-reranker-large`，不自动下载或用模拟分数顶替：

```powershell
data/module-four-runtime/.venv/Scripts/python.exe tests/item02/prepare_rerank_pool.py
data/module-four-runtime/.venv/Scripts/python.exe tests/item02/benchmark_reranker.py
data/module-four-runtime/.venv/Scripts/python.exe tests/item02/check_rerank_budget.py
backend/.venv/Scripts/python.exe tests/item02/hybrid_live.py
```

本次性能报告已经保存原始候选哈希、真实CPU线程数、模型版本及冷启动回落。`benchmark_reranker.py` 测同一组10个真实候选，生产验收仍使用5秒预算。不要用诊断耗时替代完整问答耗时。

`runtime_probe.py` 只读取健康、公开能力信息、源码哈希和文件哈希，不读取容器环境。`curate_evidence.py` 发布日志原字节及引用哈希摘要；原始PDF、模型缓存、原文全文和包含完整引用的SSE留在本地 `data/`。`test-records/第2项报告.md` 是逐题结论与限制说明。
