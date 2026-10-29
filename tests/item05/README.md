# 第5项复现实测

只对隔离库 `data/item05-20261029/records20` 进行验收，不覆盖个人库。原始 PDF、完整解析记录与模型原始结果保留本地；提交的证据有摘要、锚点和 SHA-256。

本轮网页：`http://127.0.0.1:3420/graph`，后端：`http://127.0.0.1:8120`。模型凭据由 `tests/item02/local_environment.py` 读取本地配置，禁止打印值或把值写入 Compose 文件。

1. `prepare_sources.py` 冻结20篇不同文件及评分前定性预期。
2. `upload_browser.cjs` 在原生Chrome一次选择20个文件，一次上传；目录名参数必须未存在。
3. `rebuild.py --run NAME` 重建原文引用侧表；保留原始解析 JSON。
4. `graph_probe.py --run NAME` 请求真实图谱、独立线性方程复算PageRank、直接抽取原始PDF参考文献核对完整标题。
5. `browser_acceptance.cjs NAME` 原生点击生成图谱/综述/未来方向，并记录成功或失败；外部服务失败会使此成功路径测试报错，不替换为假结果。
6. `browser_restore.cjs NAME` 重新读取已完成的真实任务，核对四种窗口、完整诊断及引用原文跳转；此步骤不算新的模型生成测试。
7. `live_writing.py --kind future --run NAME` 对全部20篇做真实未来方向核查；公共API失败及保留的证据如实记录。
8. `benchmark_graph.py --run NAME` 对比完整及精简响应字节数与耗时，断言节点、关系、排名一致；精简响应不篡改完整缓存。
9. `run_related.py --run NAME` 运行相关全量套件；快速回归用 `tests/run_regression.py fast --no-key`。语义审查和真模型实测另外记录。
10. `runtime_audit.py` 核对三个部署、源码哈希、DNS、库数量、41份原始PDF和100份冻结文件。
11. `curate_evidence.py` 核验真实引用后整理可提交证据；最终证据文件的SHA-256由交付脚本再核对。

部署：`compose.yml` 为本项隔离栈；`runtime-release.yml` 是已有主栈/第4项栈的镜像覆盖配置；`main-ports.yml` 保留本机已占用的8000端口。只更新前端可用 `release_runtime.py --frontend-only`，不会重启正在生成内容的后端。

依赖：已有本机Python虚拟环境、Next.js依赖、原生Chrome、Docker及本地基础镜像。此处的20篇规模成绩不代表100篇性能，也不代表全球查新证明。
