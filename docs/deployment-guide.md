# 本地与演示部署指南

更新日期：2026-10-30。公网部署另行推进；本文件不提供虚构的在线地址。

## 首次准备

需要 Docker Compose、Git；宿主运行预热和验收脚本还需要 Python 3.12 与 `httpx`（已列在后端依赖中）。首次安装按项目锁定依赖构建，不以已有容器通过代替首次配置。

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
if (!(Test-Path docker-compose.override.yml)) {
  Copy-Item deploy/compose.provider.example.yml docker-compose.override.yml
}
```

在本机编辑 `.env` 的 `DEEPSEEK_API_KEY` 和 `DEEPSEEK_MODEL`。真实值不写进 override、不进 Git、不贴进报告或截图。已有 override 应合并所需字段，保留自己的卷和端口；示例只通过 `${...}` 引用本地变量。

```powershell
docker compose config -q
docker compose build
docker compose up -d --wait
docker compose ps
docker compose exec -T frontend getent hosts backend
docker compose exec -T backend python -c "import os; print('KEY_SET' if os.environ.get('DEEPSEEK_API_KEY') else 'KEY_MISSING'); print('MODEL_SET' if os.environ.get('DEEPSEEK_MODEL') else 'MODEL_MISSING')"
```

不要输出完整 `docker compose config` 或容器全部环境变量，它们会展开凭据。`config -q` 只检查配置。`KEY_SET` 仅证明变量存在，还必须实跑模型任务。

Key 或模型修改后执行 `docker compose up -d --wait backend`。单独 `restart` 不会重新载入新的容器环境。网页的摘要翻译、全文翻译都应各完成一次并核对段落覆盖；失败或部分成功不能算完成。没有模型配置时如实报错，不生成替代译文。

## 端口与数据

默认前端 `3000`、后端 `8000`，只绑定本机。可以在本地 `.env` 设置 `SCHOLAR_GRAPH_FRONTEND_PORT`、`SCHOLAR_GRAPH_BACKEND_PORT`；这台工作站的主后端使用 `8030`，避免与已有 `8000` 服务冲突。容器之间始终走 `http://backend:8000`，不能把宿主端口写成容器服务端口。

默认命名卷 `backend-data` 保存原 PDF 与工作台数据库。`docker compose down` 不带 `-v` 才能保留卷；测试必须使用独立项目和卷。不得删除论文目录来修复部署。

本机增量验收镜像通过本地 `SCHOLAR_GRAPH_BACKEND_IMAGE`、`SCHOLAR_GRAPH_FRONTEND_IMAGE` 选择；这些是这台机器已有的镜像，不能当成云端可拉取镜像。新机器执行前面的 `docker compose build`，或使用自己实际发布的镜像与对应源码版本。

## 演示前预热

先导入演示实际选用的论文。脚本按真实标题查找；找不到或不唯一会失败，不会替换为示意论文。以下标题对应本地官方样本，必须已在选定后端的论文库中。

```powershell
backend/.venv/Scripts/python.exe scripts/warm_demo.py --base-url http://127.0.0.1:8030 --paper-titles "Attention Is All You Need" "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding" --question "BERT与Transformer Encoder是什么承袭关系？" --output data/demo-warmup.json
```

Linux 使用已安装项目依赖的 `python` 执行同一脚本；后端容器中也可执行 `/app/scripts/warm_demo.py`，API 地址改成 `http://127.0.0.1:8000`。用 `--paper-ids` 可以显式选择2–10篇论文。

预热会真实读取材料、建立必要的向量索引并调用已配置的模型，消耗相应服务额度。脚本必须得到有锚点、未拒答且经校验的最终回答才报告 `ready: true`；原始增量属于草稿。它分别记录首事件、首个真实内容增量和最终完成耗时，不用连接成功冒充模型已输出。

若要验证 hybrid 路径，需先准备经许可核查的本地 BGE-M3 模型及其只读挂载，并加 `--require-vector`。`SCHOLAR_GRAPH_VECTOR_RESIDENT=true` 启用本地向量进程复用；重启、换模型或新增论文后重新预热。没有本地向量模型时显示真实词法回落；输出会注明实际检索方式。预热指定论文不等于整库都已预热。

当前排序为 RRF；本地向量模型常驻不等于 cross-encoder 精排上线。FlagEmbedding 及模型许可证仍待完整核查，不能把本机试验写成已完成许可证审查。

## 操作验收与恢复

在真实网页核对上传、查看、提问与锚点、扫描件定位、翻译、图谱及任务恢复。扫描件只提供物理页定位；OCR文字不是原PDF文字层，也不声称提供段落或字符坐标。翻译未通过段落完整性校验时显示原因、保留已校验部分并阻止不完整导出；追踪和抓取失败显示真实原因及重试入口。

部署后还应核对前后端源码／镜像版本与数据卷，确认服务重启后任务与会话可恢复。上线前的域名、HTTPS、访问码、反向代理流式不缓冲、上传体积和超时、备份恢复、容量与资源限制见提交就绪清单；这些事项需要实际部署证据，文档存在不代表已经上线。
