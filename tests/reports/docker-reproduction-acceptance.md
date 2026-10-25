# Docker干净环境复现验收

开工main：`11170bcc1bce36a7984ccc27325e4117bdc037b8`，git pull原文`Already up to date.`，工作区干净。验收结果：**passed**。

真实远端main新克隆：`142e01087da3dbfd1ca80adb5d070a36fc03916c`；目录`D:\AI_Workspace\Tasks\scholar-graph\data\docker-reproduction\8979c2928f744601a65bc4781b5a8608\checkout`；构建前后Git工作区均干净。初始无backend/.venv、frontend/node_modules、frontend/.next、.env、pdf、data。没有复制宿主机依赖、模型缓存或已解析记录。

## 构建和启动

Docker CLI/Engine 29.9.2、Docker Desktop4.96.3、Compose v5.6.1，Linux/amd64引擎，20 CPU、约7.57GiB总内存。最初WSL未就绪，引擎不能启动；用户完成环境准备后已返回Server信息，随后才开始实际构建。本报告不将CLI安装等同于引擎就绪。

| 阶段 | 退出码 | 秒 |
| --- | ---: | ---: |
| clone-main | 0 | 2.681993 |
| clone-head | 0 | 0.044339 |
| clone-status | 0 | 0.100804 |
| compose-config | 0 | 0.364411 |
| docker-version | 0 | 0.228302 |
| build-no-cache | 0 | 392.413293 |
| up-wait | 0 | 17.069189 |
| container-state | 0 | 0.487472 |
| container-acceptance | 0 | 519.105200 |
| export-container-results | 1 | 0.505122 |
| clone-final-status | 0 | 0.224614 |
| export-file-container-results-json | 0 | 0.385086 |
| export-file-container-pytest-xml | 0 | 0.421136 |
| export-file-dedup-json | 0 | 0.386936 |
| export-file-ocr-json | 0 | 0.404725 |
| export-file-longbook-json | 0 | 0.387760 |
| export-file-pytest-console-txt | 0 | 0.419907 |

额外执行同一克隆的up --build -d --wait一条命令入口，退出码0，耗时7.177846秒，两服务仍healthy。该次使用前面构建的层缓存；真正的全新无缓存构建耗时按上表build-no-cache实测登记，不把缓存启动冒充冷构建。

### Windows导出失败与修复

首次整目录docker compose cp退出码1，原因是pytest临时树含Linux的*current符号链接，Windows创建链接缺权限，原文：

```text
 sg-clean-8979c2928f-backend-1 Copying sg-clean-8979c2928f-backend-1:/app/data/docker-acceptance to D:\AI_Workspace\Tasks\scholar-graph\data\docker-reproduction\8979c2928f744601a65bc4781b5a8608\container-output
symlinkat /app/data/docker-acceptance/b5cb8b0a984749a4b769d2311d2cf3fc/pytest-temp/api-local-engines0 container-output\b5cb8b0a984749a4b769d2311d2cf3fc\pytest-temp\api-local-enginescurrent: A required privilege is not held by the client.
```

此时容器内业务与回归已通过，但整单尚未交付。修复tests/reproduce_docker.py，只复制明确列出的JSON/XML/控制台日志文件，6次文件导出均退出0；--resume-export从同一仍运行的容器取回原始产出，没有重跑三项、没有换用宿主机结果。初次失败证据另存docker-reproduction-initial-export-failure.json，不覆盖为成功。README同步改为逐文件导出，不要求用户开Windows符号链接权限。后续仅修改宿主机导出辅助、README与报告，容器业务实现和已验收构建配置未改动。


构建命令确有--no-cache，Node npm ci / npm run build及Python pyproject安装均在构建阶段执行。固定基础镜像python:3.12.15-slim-bookworm、node:22.23.4-bookworm-slim；backend安装backend[ocr,test]并执行pip check。未使用宿主机venv/node_modules；前端源文件零改动。后端附带容器内安装的Node/TypeScript，既有真实代理回归没有因缺工具跳过。

完整构建日志留在本地`D:\AI_Workspace\Tasks\scholar-graph\data\docker-reproduction\8979c2928f744601a65bc4781b5a8608\build-no-cache.log`，100958字节，SHA-256 `3081c8bda1f1b1d6ae153fcec0d34ee5298b246ad4867730505282e240835f53`。日志尾摘要：

```text
#35 DONE 0.1s

#36 [backend backend 11/12] COPY services/docker-compose.acceptance.yml ./services/docker-compose.acceptance.yml
#36 DONE 0.1s

#37 [backend backend 12/12] RUN useradd --uid 1000 --create-home --home-dir /home/scholar scholar     && mkdir -p /app/data/home /app/tests/reports     && chown -R scholar:scholar /app/data /app/tests/reports
#37 DONE 0.5s

#38 [backend] exporting to image
#38 exporting layers
#38 exporting layers 49.9s done
#38 exporting manifest sha256:61bbe1ec93f13da838069d6498b28804dd0d78c3082a987073045856cc564863 0.0s done
#38 exporting config sha256:792fa23209dd14a353faa2aaf4527917895816a2864376f1c167b64ea0802e83 0.0s done
#38 exporting attestation manifest sha256:473094f6365b486c7606662b1c7d4eba2d54ecd1147be205f57762c2e74d67de 0.0s done
#38 exporting manifest list sha256:fc4e9126c0cf244248d1b51422d1c28137ec0a01afdc8cc82c6f364ec2697d18 0.0s done
#38 naming to docker.io/library/sg-clean-8979c2928f-backend:latest done
#38 unpacking to docker.io/library/sg-clean-8979c2928f-backend:latest
#38 unpacking to docker.io/library/sg-clean-8979c2928f-backend:latest 26.4s done
#38 DONE 76.4s

#39 [backend] resolving provenance for metadata file
#39 DONE 0.2s
 Image sg-clean-8979c2928f-backend Built 
 Image sg-clean-8979c2928f-frontend Built 
```

构建时只有受.dockerignore过滤的源码上下文，语料不在镜像。另用该backend镜像启动无网络、无挂载的一次性容器检查：/app下PDF为0，.git/.env/宿主机venv/已解析papers均不存在，未设置模型Key；证据docker-image-input-audit.json。

## 健康检查与端口

后端8000、前端3000均绑定宿主机127.0.0.1。Compose健康检查实际请求后端论文列表和前端同源代理；两个容器均healthy。宿主机访问8000列表、3000首页、3000代理均HTTP200；没有把静态HTML成功冒充问答通过。镜像ID、容器ID、真实只读挂载与端口见docker-runtime-inspection.json。

## 回归测试

容器内：329项收集，**323通过、6跳过、0失败、0错误**；耗时102.259309秒。完整JUnit为docker-container-pytest.xml。

6项跳过逐项为：

- test_transient_lock_retries_with_backoff[5]：Windows error/backoff semantics
- test_transient_lock_retries_with_backoff[32]：Windows error/backoff semantics
- test_transient_lock_retries_with_backoff[33]：Windows error/backoff semantics
- test_permanent_access_error_is_not_swallowed：Windows error/backoff semantics
- test_real_directory_lock_blocks_native_rename_then_releases：Real native Windows handle test
- test_real_deepseek_connectivity_without_body_logging：real model disabled or environment credentials unset; never a fabricated live pass

宿主机：329项收集，**328通过、1跳过、0失败、0错误**；JUnit为docker-host-pytest.xml。宿主机包含Windows锁实测，唯一跳过为无Key实连。两边均启用--run-ocr --run-real-model：实际OCR已运行，真实大模型无Key跳过，不冒充实连通过。回归输入仍为自制样例；下面三项另用官方真文件运行。

## 官方 pdf/ 真文件三项容器实测

官方语料仅只读绑定/corpus；容器statvfs与Docker inspect均确认只读。首次HTTP论文列表为0，每次源文件parse-status为404才上传，禁止复用已解析结果。原文件SHA-256在上传前后核对；容器源码指纹与干净克隆的8份输入逐一一致。

| 项目 | HTTP | Chunk | 秒（实际上传） | RSS采样峰值MiB | 结论 |
| --- | ---: | ---: | ---: | ---: | --- |
| 1706.03762v7.pdf | 201 | 175 | 6.160709 | 561.996094 | 通过 |
| 1706.03762v1.pdf | 201 | 162 | 5.985380 | 582.191406 | 通过 |
| 1706.03762v1_img.pdf | 201 | 989 | 279.175055 | 1442.132812 | 通过 |
| UnderstandingDeepLearning_02_09_26_C.pdf | 201 | 6859 | 119.744032 | 1090.945312 | 通过 |

去重第二传预警原文：

> 建议保留库里较新版本（v7）；本次上传为v1。依据同一arXiv身份及PDF原文版本标识，避免降级覆盖；不代表学术质量排名。

去重判定HTTP200、recommendation=keep_old；差异摘要HTTP200。完整原记录见docker-dedup.json；语义为保留库内v7，本次new_paper_id仍指上传v1。机制仍是现有身份匹配与词频Dice，没有宣称向量去重。

OCR：全部15/15物理页完成，失败页[]；真实首批文本如下。同一后端运行中快照：已处理4/15页，已发布244个Chunk；失败页[]，分页total=244；见匹配本轮run_id的docker-ocr-progress-snapshot.json。

```text
Attention Is All You Need
Ashish Vaswani*
Noam Shazeer*
```

OCR模型来自容器首次联网下载，没有挂宿主机模型缓存；上传计时包含该请求中的模型准备和推理，不把宿主机缓存耗时混入。相同容器本轮运行产生的缓存属于容器自身产物。识别完成不等同逐字准确率评测。

长书：541物理页、22344992字节；17批；完成页数541，失败页[]；索引相关累计2.446103秒。末分页HTTP200，59条，最大物理页541；越界页返回0条。没有200页拒绝，默认上限仍2000页。索引计时含批次规范化、Schema/外键门禁、发布与SQLite提交，不是纯SQL时间。

RSS为每50ms采样容器内可读进程的合计，可能重复计算共享页；不宣称精确系统高水位。每次上传另保存cgroup采样峰值和容器生命周期memory.peak，后者包含之前回归/用例，不能当作该单次上传峰值。未拿宿主机RSS数字冒充容器内存。

## 一次实际无Key问答

问题：Which optimizer?；HTTP200；refused=false；锚点2处；数字校验passed。

```text
【证据 A】
5.3 Optimizer

【证据 B】
We used the Adam optimizer [20] with β 1  = 0.9, β 2  = 0.98 and ϵ = 10 −9 .
```

```json
[
  {
    "paper_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697",
    "page_number": 7,
    "section": [
      "5 Training",
      "5.3 Optimizer"
    ],
    "chunk_id": "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697-p0007-c00087"
  },
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

回答来自容器当轮上传Attention v7的真实Chunk。审计通过同一容器HTTP重新读取两篇论文的四类记录，复核原Schema、去重/差异外键与问答原文锚点；没有从宿主机已有解析目录取证。模型调用0，两个容器环境均没有API_KEY/TOKEN/SECRET变量，不写Key到镜像、Compose或报告。

## README与复现边界

README.md第111行新增“Docker 复现”，含构建、启动、跑测试三条命令、两个端口和预期输出；一条启动入口为docker compose up --build -d --wait。

基本启动与--suite-only不要求私有语料；官方验收用services/docker-compose.acceptance.yml覆盖，设置现有语料路径并使用新项目名/空数据卷。探针拒绝复用非空论文库。Docker数据卷不会自动删除；本轮容器和数据保留供复核，项目名见下。GROBID与独立BGE模型不包含在默认两服务，未宣称本轮接通；前端源码、全部既有契约及prompts/experiments/test-records零改动。

本轮项目名：`sg-clean-8979c2928f`。临时克隆、完整日志和导出的中间数据仅在被忽略的data/；Git只保存脚本、配置与报告/JSON/JUnit，不含PDF、模型或真实Key。审计47/47项通过，详见docker-reproduction-audit.json。

复核脚本tests/audit_docker_reproduction.py需要本地原文件、当轮临时克隆和仍运行的容器；它是交付审计工具，不是应用启动前提。已有容器仍占用8000/3000，新项目启动前应先停止本轮项目，保留数据卷即可，无需删除官方文件或模型。

技术依据：[Docker构建上下文与忽略规则](https://docs.docker.com/build/concepts/context/)、[Compose构建](https://docs.docker.com/reference/compose-file/build/)、[Compose只读绑定挂载](https://docs.docker.com/reference/compose-file/services/#volumes)、[Next.js自托管](https://nextjs.org/docs/app/guides/self-hosting)。
