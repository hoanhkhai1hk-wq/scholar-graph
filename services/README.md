# 可配置解析服务

GROBID 为可选补充服务；文本主路径是 MinerU 本地直跑，无 Docker 也能运行。

官方 [快速开始](https://grobid.readthedocs.io/en/latest/getting_started/) 明确列出 `grobid/grobid:0.9.1-full`（2026-10-24 查阅）。Compose 保留这一标签，仅将 8070 绑定到本机 127.0.0.1，并使用独立 grobid profile；前后端仍是原占位服务。

有 Docker 的机器可执行：

```powershell
docker compose --profile grobid config
docker compose --profile grobid up grobid
```

启动后解析命令显式加 `--grobid-url http://127.0.0.1:8070`。也可使用进程环境变量 GROBID_URL；不在地址内携带凭据。客户端通过 [官方 processFulltextDocument API](https://grobid.readthedocs.io/en/latest/Grobid-service/) 发送用户指定的 PDF，关闭 consolidation，不使用公开演示站点上传样例。

本轮真实状态：GROBID **待验证**。本机没有 Docker Desktop / CLI，未拉取镜像、未调用真实 GROBID；`docker compose config` 真校验也待验证。镜像文档可确认不等于镜像运行通过，摘要与资源参数保留 TODO。HTTP/TEI 的模拟测试不能作为服务联调证据。
