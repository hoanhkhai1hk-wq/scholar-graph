# 可配置解析服务

GROBID 为可选补充服务；文本主路径是 MinerU 本地直跑，无 Docker 也能运行。

官方 [Docker 文档](https://grobid.readthedocs.io/en/latest/Grobid-docker/) 列出 `grobid/grobid:0.9.1-full`（2026-10-26 查阅）。本目录的独立 Compose 使用该 full 标签，仅将 8070 绑定到本机 127.0.0.1，限制容器内存为 6 GiB，禁用 core dump；不声明 GPU 或运行时并发配置已调优。根 Compose 的前后端服务不受影响。

有 Docker 的机器可执行：

```powershell
docker compose -f services/docker-compose.grobid.yml -p scholar-graph-grobid config
docker compose -f services/docker-compose.grobid.yml -p scholar-graph-grobid up -d
backend/.venv/Scripts/python.exe tests/run_grobid_acceptance.py
```

启动后解析命令显式加 `--grobid-url http://127.0.0.1:8070`。也可使用进程环境变量 GROBID_URL；不在地址内携带凭据。客户端通过 [官方 processFulltextDocument API](https://grobid.readthedocs.io/en/latest/Grobid-service/) 发送用户指定的 PDF，关闭 consolidation，不使用公开演示站点上传样例。

探针对官方 pdf/ 真文件 `1706.03762v7.pdf` 从空目录运行 MinerU，再调用真实 GROBID 完整解析，最后在第二个空目录运行显式启用 GROBID 的 Pipeline。完整 TEI 和四类业务记录保留在忽略的 data/ 下；Git 只收字段数量、有限原文样本与测试证据。PDF 不挂载进服务、不 COPY 进镜像；通过本机 multipart 请求发送，无密钥、无 Crossref consolidation。

当前真实服务状态与失败证据见 [联调报告](../tests/reports/grobid-integration-acceptance.md) 和 [探针 JSON](../tests/reports/grobid-integration-live.json)。`docker compose config` 校验配置语法，并不证明引擎、镜像或解析成功。单元测试中的自制 TEI 与 mock 不计入容器联调通过。

生产分工：仅 CLI 的 `--grobid-url` / `GROBID_URL` 或调用方显式注入 `Pipeline(grobid=...)` 会启用 GROBID；负责补充 PaperMeta 的标题、作者、机构、摘要、年份、DOI 与 ReferenceEntry，再按 MinerU Chunk 中的引用标记重新生成 CitationLink。GROBID 的正文、表格、公式不会替换 Chunk；Chunk/物理页锚点仍来自 MinerU。默认 HTTP 上传工厂和 arXiv 抓取工厂不注入 GROBID，设置 GROBID_URL 不会使这两条 HTTP 路径自动启用它。

停止本单独立服务：

```powershell
docker compose -f services/docker-compose.grobid.yml -p scholar-graph-grobid down
```
