# 第 0 步：环境基线复位（2026-10-28）

**最新结论：第 0 步修复后通过（本机增量镜像），在此停止，未进入 1.1。** 当前 Compose 已运行包含工作区新版工作台代码的镜像；9 项运行探针全部通过。下方保留首次未通过的实测记录。全新环境的标准镜像构建仍未完成，不能将此次本机增量构建称为全新构建通过。

## 重试后的最终结果

原始 XML、运行探针和两份成功增量构建日志同时收录于 [baseline-20261028](baseline-20261028/)，供仓库内复核；下表中的 `data/` 路径是本机完整原始记录位置。该证据目录不包含论文、模型密钥或代理地址。

| 检查 | 实际结果 | 原始证据 |
|---|---|---|
| 当前源码快速回归 | 188 passed、513 deselected，25.94 秒 | `data/baseline-20261028/fast-local-retry-final.xml`、`data/baseline-20261028-fast-local-retry-final.log` |
| 不挂载个人卷、禁用外网的候选镜像快速回归 | 188 passed、513 deselected，25.80 秒；1 条 pytest 缓存权限警告 | `data/baseline-20261028/fast-candidate-final.xml`、`data/baseline-20261028-candidate-fast.log` |
| 本步全部相关测试：Docker 配置、回归分层、实际代理兼容、无密钥翻译错误 | 源码 6 passed，5.24 秒；新部署容器 6 passed，2.54 秒，容器有同一缓存警告 | `data/baseline-20261028/related-retry-03.xml`、`related-container-final.xml` |
| Compose 前后端健康与网络 | 两服务 running/healthy；`getent hosts backend` 返回 `172.21.0.2 backend` | `data/baseline-20261028/runtime-final.json` |
| 新版接口与前端代理 | `/api/v2/system`、`/api/workspace/system`、旧论文代理全部 HTTP 200；版本 `20261027-workbench-r2` 与 8 项必需能力齐全 | 同上 |
| 模型配置 | `.env` 和容器内模型密钥、模型名均非空；只记录布尔值。无密钥翻译返回 502 的专项通过 | 同上及相关测试 XML |
| 源码一致性抽查 | 后端 `api.py`、`workspace.py`、前端 `ResearchChat.tsx` 共 3 个文件哈希与工作区一致 | 同上 |

模型配置非空不等于本步已验证真实模型输出。当前 Compose 问答配置仍为 `extractive`（摘录模式）；本步未更改这一默认设置，也未将其结果称为模型生成。之后测试模型问答时需明确选择生成模式并保留调用证据。

当前 Docker 数据库原本为空，复位后论文总数仍为 0；本地 `pdf/` 实际有 41 个 PDF 文件（文件数不等同于官方“39 篇测试论文”的口径），未挂载、上传或写入镜像。前后原始论文目录均为空，因此不能用“0 个哈希相等”证明非空个人库的数据完整性。`data-integrity-final.json` 的空集合比较只保留为原始探针结果，正确解释见 `data-integrity-reviewed.json`。命名卷保持为 `scholar-graph_backend-data`。

## 重试中修复与优化

1. 标准重建再次出现 npm `ECONNRESET`，临时构建代理也未消除慢速下载。未修改软件源和依赖完整性校验，未将模型密钥用于构建；所有失败和中断日志保留在 `data/baseline-20261028-build-retry-02.log`、`data/baseline-20261028-build-retry-03.log`。
2. 根 `Dockerfile` 为 npm、主 Python 环境增加 BuildKit 下载缓存。只有公开依赖缓存可复用；密钥、论文和本地覆盖配置仍被构建上下文排除。临时代理使用 Docker 预定义构建参数，未在 Dockerfile 添加代理 `ARG` 或 `ENV`；依据 [Docker 官方代理参数说明](https://docs.docker.com/build/building/variables/#proxy-arguments)。
3. 新增 `scripts/Dockerfile.local-incremental`，专用于复用本机此前已运行的 Linux 镜像。后端通过逐字比较 `pyproject.toml` 和 `pip check` 后才复用环境；当前前端锁文件与旧镜像比较为新增 16 项、变更 1 项，均未声明安装脚本或平台限制。前端实际执行 npm 安装，输出“added 17 packages, changed 1 package”，锁文件 SHA 校验不变，依赖关系检查退出码 0。依赖安装 116.0 秒，生产编译 28.6 秒（各构建阶段自身计时，不当作端到端总耗时）。
4. 前端以当前源码重新编译，后端复制当前源码、契约、测试和前端代理测试环境。本机增量镜像构建均退出码 0，分别见 `data/baseline-20261028-incremental-frontend-03.log`、`data/baseline-20261028-incremental-backend.log`。
5. 新增 `scripts/verify_environment_baseline.py`，读取真实 Compose 和 HTTP 结果；配置只记录非空状态，失败不写通过。命令为 `backend/.venv/Scripts/python.exe scripts/verify_environment_baseline.py --output data/<新的证据文件>.json`。

本机增量构建命令（在仓库根目录运行）：

```powershell
docker build --file scripts/Dockerfile.local-incremental --target frontend --tag scholar-graph-frontend:baseline-20261028 .
docker build --file scripts/Dockerfile.local-incremental --target backend --tag scholar-graph-backend:baseline-20261028 .
docker tag scholar-graph-backend:baseline-20261028 scholar-graph-backend:latest
docker tag scholar-graph-frontend:baseline-20261028 scholar-graph-frontend:latest
docker compose down
docker compose up -d --wait
```

此次实际构建另传入非秘密的 `WORKSPACE_REVISION`，前端下载时使用进程级临时代理参数；没有将代理地址或模型密钥写入文件。增量构建依赖本地 `pre-baseline-20261028` 基础镜像，因此上述命令不能在只有干净源码的新机器上独立复现；新机器应使用根 `Dockerfile` 的标准构建。后端基础镜像 ID 为 `sha256:450f47f4410487a8bdb6a585d34ee8ff179eb0e9690f76791bec1d5ad1172783`，前端基础镜像 ID 为 `sha256:6ab9c62ddf2b82064cb6a9766e4a89781e81bfcd9a5698376b8116d9aff52d32`。

当前后端镜像 ID：`sha256:9920bcf01a57d7c1d416518d93d8f08a711dbeaf473447db2925b0dbcb6de78b`；前端：`sha256:219b4894cfea83a4d7b5c46c8e1a2909f9b8c2ed742e344e16e137746ab5fe74`。镜像标记为 `c6af2c62642305e9fbf888b21c6a767a7cd65772-dirty`，如实表示包含既有未提交的工作区源码。本步提交只包含环境构建与验证相关文件，不将既有大量未提交的功能代码混入本步；仅检出本步提交不等于获得当前完整工作区。

## 首次尝试记录（原结果保留）

## 实测步骤与结果

1. 分支为 `main`。测试开始前工作区有大量既有未提交及未跟踪修改；本次没有覆盖、重置或纳入提交。用户提供的本地论文和数据未删除。
2. 执行 `docker compose down`，随后执行 `docker compose up -d --wait`，均返回退出码 0。未使用删除数据卷的选项；后端原有命名卷 `scholar-graph_backend-data` 保留。
3. 执行 `docker compose ps --all`，前后端均为 `healthy`；前端 `127.0.0.1:3000`、后端 `127.0.0.1:8000`。
4. 执行 `docker compose exec -T frontend getent hosts backend`，得到 `172.21.0.2 backend`；构建尝试中断后再次执行，结果相同。
5. 只检查非空状态：本地 `.env` 和后端容器中的模型密钥、模型名均为非空；`docker-compose.override.yml` 引用环境变量而非写入值。报告和命令输出不记录凭据内容。`.env` 与 `pdf/` 已确认被 Git 忽略。
6. 工作区运行 `backend/.venv/Scripts/python.exe tests/run_regression.py fast --no-key --junit data/baseline-20261028/fast-local.xml`：**188 passed、513 deselected、27.10 秒**。
7. 旧后端容器运行 `docker compose exec -T backend python tests/run_regression.py fast --no-key --junit /app/data/regression/baseline-20261028-container.xml`：**187 passed、461 deselected、24.53 秒**；有 1 条 pytest 缓存目录无写权限警告。XML 复制到 `data/baseline-20261028/fast-container-old-image.xml`。
8. 缺失密钥翻译专项 `tests/test_translation.py::test_missing_credentials_and_upstream_errors_are_explicit`：工作区 **1 passed，1.79 秒**；旧容器 **1 passed，1.00 秒**。用例验证返回 502 和明确错误，无生成译文；不是对真实模型质量的测试。证据分别为 `data/baseline-20261028/no-key-translation.xml` 和 `data/baseline-20261028/no-key-container-old-image.xml`。
9. 对运行中后端请求 `/api/v2/system` 得到 **404**；容器内 `scholar_graph.workspace` 模块检查为不存在。当前工作区包含该模块及 `/api/v2/system`。因此旧镜像通过健康检查和自己的快速回归，不能证明当前工作区版本已在 Docker 中运行。

## 本次改动与构建尝试

- `.dockerignore` 新增排除 `docker-compose.override.yml` 和 `.next-*` 构建目录，以避免本地覆盖配置及构建缓存进入 Docker 构建上下文。原有 `.env`、`pdf/` 等排除规则仍保留。
- 对原前后端镜像分别增加本地 `pre-baseline-20261028` 回退标签；没有删除原镜像、命名卷或历史数据。
- 执行标准 `docker compose --progress plain build`，前端依赖下载第一次出现 `ECONNRESET` 并开始重试；后端依赖下载缓慢。测试了公开软件源的连通性，但没有更改项目的依赖来源或关闭完整性检查。为避免长时间占用网络，本次在重试期间手动中断构建；**未取得构建成功结果，也未切换到新镜像**。原始输出位于 `data/baseline-20261028-build.log`。
- 中断后重新核查，旧前后端均 healthy，容器间 DNS 仍返回 `172.21.0.2`。

## 首次尝试时的残留问题

首次尝试时源码与运行镜像不一致，需重建并核查双容器健康、`getent hosts backend`、模型配置及 `/api/v2/system`，再对新镜像重跑快速回归。上方重试通过了本机增量镜像的这些检查；全新环境标准构建仍需单独完成。

首次尝试依据“全绿才提交”的要求未提交；上方重试后的本机基线验证现已通过。既有未提交修改继续保留；未进入命题 1.1–1.6 的分项测试。全新环境标准构建、模型问答模式和模型输出质量仍属于后续明确验收范围。
