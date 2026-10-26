# Docker 最终部署验收

日期：2026-10-26（Asia/Shanghai）。语料为 **官方 pdf/ 真文件**。

**最终结论：通过。** 宿主机与容器独立记录，未以宿主机结果替代容器结果。

## 基线、干净克隆与镜像版本

开工 main：`8de7a907c212b49588fdf00ef9842e45863b273f`，git pull 为 `Already up to date.`，工作区干净。

本次先推送全部应用、配置与回归用例，再从远端 main 新克隆：`62dca5182b6098a883e0ffe8d72d9560f291e1ff`。

克隆目录：`D:\AI_Workspace\Tasks\scholar-graph\data\final-deployment-build\2653edb0cc1c4ef49c28b66bf89451e7\checkout`。构建前后均干净；初始没有 backend/.venv、frontend/node_modules、frontend/.next、.env、pdf/、data/。没有复制宿主机依赖、模型缓存或已解析记录。

镜像 OCI revision 标签均为该功能主干提交；后续交付仅增加宿主机检查脚本、运行说明与验收证据，不改变已构建的应用、配置或被执行回归用例。

| 阶段 | 退出码 | 实测秒 |
| --- | ---: | ---: |
| clone-main | 0 | 6.927945 |
| compose-config | 0 | 0.616158 |
| build-no-cache | 0 | 1525.450406 |
| up-healthy | 0 | 20.668233 |
| prepare-public-vector-model-range-parallel | 0 | 19.953914 |
| confirm-public-vector-model | 0 | 1.456218 |
| container-acceptance-after-model-preparation | 1 | 999.095048 |
| container-full-isolated-test-env | 0 | 332.209442 |

首轮镜像来源 `000e8023a068c978138aece9aff8fbb2b8743e81`，无缓存构建 768.059373秒，容器全量实测3失败/10跳过；不是最终通过结果。

首轮失败逐项：①Linux venv符号链接经Path.resolve变成系统Python，worker缺torch；改为venv --copies，构建时用解析后的解释器实际导入torch/Chroma/FlagEmbedding；②.dockerignore排除了全量测试必需的semantic-dedup-calibration.json，现仅放行这一份公开数值证据，其他报告仍排除；③调度单测继承部署Attention种子而测试库只含seed，现单测显式设定种子。没有放宽断言或把真向量改成假向量。

另一次修正过程中的构建主动中止，实测退出码 4294967295、144.452083秒；原JSON/日志保留。公共依赖下载另有npm ECONNRESET退出1（329.919312秒）及主动中止的重试（261.743425秒、4294967295），原JSON/日志另存final-deployment-runtime-rebuild-network-failure.json。最终再次从远端main干净克隆、无缓存构建，使用官方HTTPS Debian源及npm有界重试，耗时见本节阶段表。

首轮容器官方业务记录移到同一卷的独立归档目录，最终重验HTTP库重新为空；只保留该容器自身从公开源下载并完整校验过的模型权重，未复制宿主机缓存。归档：`{"archived": "records-before-runtime-fix-3bf85263527e4e8394168160cd5bf0ee", "new_http_library_absent": true, "retained_public_ocr_weight_files": 2}`。

历次重建保留的原始结果（同一日志SHA去重）：

| 来源主干 | 构建阶段 | 退出码 | 秒 |
| --- | --- | ---: | ---: |
| af5160bc7c577f7526b3370ad4ec55ab32ad7f25 | build-no-cache | 4294967295 | 144.452083 |
| 26804191cfdeb7e2c5f0bb8680c274bfb45531e4 | build-no-cache-network-failure | 1 | 329.919312 |
| 26804191cfdeb7e2c5f0bb8680c274bfb45531e4 | build-no-cache-network-retry | 4294967295 | 261.743425 |
| 4f87ad3f13fa04f353986750e90f4e8582015064 | build-no-cache | 1 | 415.716465 |
| 62dca5182b6098a883e0ffe8d72d9560f291e1ff | build-no-cache | 0 | 1525.450406 |

后续一次大依赖下载仅34.0/196.3MB即断开，被SHA-256校验拒绝（415.716465秒）；未放宽校验。构建两个Python环境固定pip26.2.2并设20次有界恢复，依据[pip官方断点恢复说明](https://pip.pypa.io/en/stable/cli/pip/#cmdoption-resume-retries)。

构建命令确有 `build --no-cache`。前端 npm ci/build、类型检查以及后端两套 Python 依赖安装/pip check 均由容器构建执行；未修改前端源码。

首次容器验收尚在模型准备阶段时，因公开权重下载慢而主动中止（退出143），当时没有运行容器回归或上传官方文件。SDK重启后新建了下载临时文件，本轮保留其原约1.06GB容器内下载数据，改用公开文件范围请求续传，并按实测单连接带宽改为最多4路；中止阶段仍为143。完整文件通过固定大小与SHA-256校验，再由原SDK确认。下载准备阶段的实测时间/退出码完整保留在final-deployment-build-before-runtime-fix.json、final-deployment-build-initial-preparation.json；没有使用宿主机模型/解析缓存。

完整构建日志（本地忽略目录）：`D:\AI_Workspace\Tasks\scholar-graph\data\final-deployment-build\2653edb0cc1c4ef49c28b66bf89451e7\build-no-cache.log`；SHA-256：`d11cd80729af63c7c7680796d61515e58a3965ab4c2a14dccf50e18353ef2173`。

Docker Engine/CLI 29.9.2、Desktop 4.96.3、Compose v5.6.1，Linux/amd64。运行期版本：`{"python": "Python 3.12.15", "node": "v22.23.4", "api": "1.2.0"}`。Python/Node基础镜像固定为3.12.15-slim-bookworm与22.23.4-bookworm-slim。

| 服务 | 镜像 ID | 字节 | healthy | 镜像内 PDF / 密钥变量 |
| --- | --- | ---: | --- | --- |
| backend | sha256:cbe2f03a24c80bde427daf741dee700a91a4a5f64cc54b13835c086efb8f3dc6 | 6865945421 | True | 0 / 0 |
| frontend | sha256:1132a1971614ba66ab28696ea927fbda597db7288afe1a0508ba8e1271034873 | 1312356516 | True | 0 / 0 |

镜像审计使用无网络、无挂载的一次性容器；未拿含语料的运行容器冒充镜像本体。两镜像均无 .env/.git/官方pdf或已解析数据。官方语料仅在验收时只读挂载 /corpus，模型在容器内从固定公开快照下载到本轮新持久卷。最终权重字节/完整SHA-256：`{"bytes": 2271145830, "sha256": "b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38", "matches_fixed_revision_weights": true}`。根 .dockerignore 仍排除 pdf/、所有PDF、环境文件、宿主机依赖和Git。仓库既有 docs/technical-document.pdf 属于技术文档，未改动且同样被构建忽略；官方 pdf/ 没有跟踪文件。

## 健康检查与无 Key 问答

最终默认配置（每日调度）下：`{"backend": 200, "frontend": 200, "proxy": 200}`；后端8000、前端3000均绑定127.0.0.1。两个服务均healthy，使用restart:unless-stopped。

资源调整：独立可选 GROBID 容器实占约 3.892 GiB，而引擎总内存 7.568 GiB。本轮已停止该容器以给真实向量/OCR联测释放内存，退出码 0，保留容器及配置；最终运行的是本单要求的前后端两服务。GROBID不是默认HTTP解析路径，本轮不宣称它仍在线。

一次容器内真实 HTTP 摘录式问答：`Which optimizer?`，HTTP 200，refused=False，锚点数 4。答案、数字校验与锚点见容器JSON；未调用生成式大模型。

## 宿主机与容器全量回归

| 环境 | 收集 | 通过 | 跳过 | 失败 | 错误 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 宿主机最终 | 613 | 608 | 5 | 0 | 0 |
| Linux容器 | 613 | 603 | 10 | 0 | 0 |

全量入口实际执行真实本地 BGE-M3/Chroma（4个自制Chunk、1024维dense+sparse）、真实自制扫描OCR，以及官方541页长书解析与分页索引；不是只跑假向量单测。真实向量版本/加载与查询耗时、长书Chunk数/索引秒数写入JUnit testcase properties。属性记录产生的xunit2兼容警告不计为失败；未隐藏警告。

容器另有两项纯词法用例继承生产混合检索默认值而失败（完整JSON/JUnit保留在final-deployment-container-before-test-isolation*）。最终全量只给exec测试子进程设置SCHOLAR_GRAPH_RETRIEVAL_MODE=lexical，原断言不变，生产服务仍为bge_m3_hybrid；真实向量验收直接调用BGE-M3/Chroma并实际跑过，未用词法冒充。官方三用例来自同一最终镜像此前空库HTTP上传，未为此环境隔离复用宿主机解析结果。最终向量解释器及依赖：`{"resolved_executable": "/opt/vector-venv/bin/python", "prefix": "/opt/vector-venv", "isolated_after_resolution": true, "versions": {"torch": "2.14.1+cpu", "chromadb": "1.5.9", "FlagEmbedding": "1.4.2", "transformers": "5.20.2"}}`。首轮容器失败JUnit仍在final-deployment-container-before-runtime-fix-pytest.xml。

两边均保留5项无Key真实模型测试跳过，跳过不计为通过。容器另有Windows专属测试跳过；逐项如下：

- `test_transient_lock_retries_with_backoff[5]`：Windows error/backoff semantics
- `test_transient_lock_retries_with_backoff[32]`：Windows error/backoff semantics
- `test_transient_lock_retries_with_backoff[33]`：Windows error/backoff semantics
- `test_permanent_access_error_is_not_swallowed`：Windows error/backoff semantics
- `test_real_directory_lock_blocks_native_rename_then_releases`：Real native Windows handle test
- `test_live_3d_trend_caption_requires_real_model`：real model disabled or environment credentials unset; never a fabricated live pass
- `test_real_deepseek_connectivity_without_body_logging`：real model disabled or environment credentials unset; never a fabricated live pass
- `test_real_deepseek_sse_endpoint_when_credentials_available`：real model disabled or environment credentials unset; never a fabricated live pass
- `test_live_translation_uses_real_model_with_stored_chunk`：real model disabled or environment credentials unset; never a fabricated live pass
- `test_live_chinese_to_english_requires_actual_model`：real model disabled or environment credentials unset; never a fabricated live pass

最终原始控制台：宿主机 2 条警告，容器 3 条警告。两边有record_property与xunit2兼容警告，Linux另有只读源码目录pytest缓存写入警告；原文见[宿主机控制台](final-deployment-host-console.txt)、[容器控制台](final-deployment-container-console.txt)，未计为失败或隐去。

宿主机首轮全量有1项失败：新增真向量测试错误地将排序列表当字典读取。已修正断言，定向真向量测试通过，再完整重跑得到上表最终结果。首轮JSON/JUnit及原日志保留，不将失败改成通过。并行重建期间另一轮为604通过/5跳过/2个真实OCR失败（单页90秒超时），原JSON/JUnit另存final-deployment-host-during-rebuild*，未把负载认定为唯一根因。随后新增共享公开OCR权重缓存及独立7200秒准备步骤，推理仍为真实Paddle、单页仍90秒，再串行跑完整层。最终宿主机JSON合并最后回归与本单此前新目录已完成的官方三用例并明确来源；PDF切块算法未改，容器则使用最终镜像从空HTTP库重新上传。

## 官方三用例：两环境分别实测

| 环境 | 文件 | HTTP | Chunk | 上传秒 | RSS采样峰值 MiB | 通过 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 宿主机 | 1706.03762v7.pdf | 201 | 175 | 27.448826 | 2089.093750 | True |
| 宿主机 | 1706.03762v1.pdf | 201 | 162 | 25.856166 | 2094.226562 | True |
| 宿主机 | 1706.03762v1_img.pdf | 201 | 989 | 588.150858 | 1974.175781 | True |
| 宿主机 | UnderstandingDeepLearning_02_09_26_C.pdf | 201 | 6859 | 163.434450 | 2075.585938 | True |
| 容器 | 1706.03762v7.pdf | 201 | 175 | 22.314523 | 2211.636719 | True |
| 容器 | 1706.03762v1.pdf | 201 | 162 | 22.573003 | 2220.738281 | True |
| 容器 | 1706.03762v1_img.pdf | 201 | 989 | 326.504238 | 2202.082031 | True |
| 容器 | UnderstandingDeepLearning_02_09_26_C.pdf | 201 | 6859 | 155.173268 | 2418.152344 | True |

每次上传前状态接口为404，后续为completed且Chunk>0；源文件SHA-256在两环境与本地原件一致。容器用本轮空卷的实际HTTP上传，未挂宿主机解析结果。宿主机测量为测试进程及子进程RSS采样合计；容器测量为容器内可读进程RSS采样合计，含共享页重复计数可能。容器另存cgroup采样与生命周期峰值，后者不能当作单次上传峰值。宿主机用例与初期构建曾并行；最终容器官方用例与组件回归串行。记录的是当时环境墙钟耗时，不作为独占硬件性能对比。

### 宿主机业务证据

第二传预警原文：

> 建议保留库里较新版本（v7）；本次上传为v1。依据同一arXiv身份及PDF原文版本标识，避免降级覆盖；不代表学术质量排名。 本地 BGE-M3 语义余弦=0.944168413；分档=duplicate。本地 BGE-M3 余弦达到重复阈值；版本偏好须另有真实版本依据。

去重裁决/差异HTTP均为200，建议`keep_old`。相似度/方法元数据保留在JSON，不把身份快速通道冒充向量计算。

OCR文本样本：`Attention Is All You Need / Ashish Vaswani* / Noam Shazeer*`。完成页 15，失败页 []。

长书 541页、22344992字节；批次数 17，索引相关累计 3.155秒，末页最大物理页 541，越界返回 0条。索引计时含归一化、门禁、发布和SQLite提交，不是纯SQL时间。

### 容器业务证据

第二传预警原文：

> 建议保留库里较新版本（v7）；本次上传为v1。依据同一arXiv身份及PDF原文版本标识，避免降级覆盖；不代表学术质量排名。 本地 BGE-M3 语义余弦=0.944168414；分档=duplicate。本地 BGE-M3 余弦达到重复阈值；版本偏好须另有真实版本依据。

去重裁决/差异HTTP均为200，建议`keep_old`。相似度/方法元数据保留在JSON，不把身份快速通道冒充向量计算。

OCR文本样本：`Attention Is All You Need / Ashish Vaswani* / Noam Shazeer*`。完成页 15，失败页 []。

长书 541页、22344992字节；批次数 17，索引相关累计 3.452045秒，末页最大物理页 541，越界返回 0条。索引计时含归一化、门禁、发布和SQLite提交，不是纯SQL时间。

## 自动定时实测与最终配置

实际机制是后端lifespan启动的interval线程，按数据目录持有操作系统锁；不依赖手动POST或宿主机任务计划程序。验收用同一代码的60秒覆盖配置，固定官方Attention种子、max_imports=0，只轮询公开arXiv形成候选。自动运行数（有真实公共查询记录）：8。

| 自动运行 id | UTC开始时间 | 状态 | 候选 | 导入 | 上游错误 |
| --- | --- | --- | ---: | ---: | --- |
| bc35e8cad7254e6fb52741a9de151e0b | 2026-10-26T11:57:27.333146+00:00 | completed | 1 | 0 | 无 |
| 590fce3457914d4ca22864ebc4627e33 | 2026-10-26T11:58:48.793572+00:00 | completed | 1 | 0 | 无 |
| ed6cf8d8d2bf4984915aeed3b9986a9a | 2026-10-26T11:59:54.381550+00:00 | completed | 1 | 0 | 无 |
| 6adcf921a02b4e9195c298c1790536cb | 2026-10-26T12:01:00.286888+00:00 | completed | 1 | 0 | 无 |
| 83d748a5b73f4325824b591ce871a363 | 2026-10-26T12:02:06.567420+00:00 | completed | 1 | 0 | 无 |
| 794ec21ab5bd407f9745b3cc8e4dbf62 | 2026-10-26T12:03:14.322761+00:00 | completed | 1 | 0 | 无 |
| 38812444c8734d95bf5a30eb8c7bd9fb | 2026-10-26T12:04:20.528520+00:00 | completed | 1 | 0 | 无 |
| 4bab160b5c1a46f1b7b4d23de611198a | 2026-10-26T12:05:26.238782+00:00 | completed | 1 | 0 | 无 |

上表中failed/partial/running保持原状态；自动触发成功不等于上游候选抓取成功。完整scheduler_started/run_started/run_finished、耗时、候选数和失败原文见容器JSON及持久卷tracking/scheduler-events.jsonl；运行记录另在state.sqlite3。首轮上传持有ingestion锁时，定时轮次因30秒锁等待失败；上传后另取证5轮实际公共查询全部completed（final-deployment-timer-first.json）。最终观察器在上传后最多再等600秒，要求run_finished日志与至少2条实际查询对应，未手动POST触发。原探针即时快照和退出码在probe_snapshot_before_timer_wait、original_probe_exit_code保留，不改写为原本通过。

验收后移除短周期及语料覆盖，使用根Compose恢复默认每日调度，两服务再次healthy。最终scheduler_details：

```json
{
  "enabled": true,
  "mechanism": "backend_interval",
  "active": true,
  "interval_seconds": 86400,
  "initial_delay_seconds": 15,
  "max_imports": 1,
  "run_count": 0,
  "pid": 7,
  "last_event": {
    "event": "scheduler_started",
    "timestamp": "2026-10-26T12:07:40.804378+00:00",
    "pid": 7,
    "interval_seconds": 86400
  }
}
```

演示部署沿用同一后端调度机制，默认间隔86400秒；容器启动时自动注册，在未手动停止的情况下，restart:unless-stopped会在Docker引擎恢复时重启容器。数据卷日志保留。旧镜像/旧数据卷未删除，本轮最终服务使用新项目 `sg-final-29fc813d71` 与新卷，包含本轮实际上传的4份官方文件。

## 回归分层及复现说明

后端README新增“最终 Docker 部署与回归分层”。快速层显式白名单，提交钩子每次运行148通过（新增OCR配置测试后465 deselected，之前463）；不加载模型、不跑OCR、不建大索引。Git钩子路径本工作区已启用，克隆后用`git config --local core.hooksPath services/git-hooks`启用。GitHub push/PR还有自动快速CI，部署功能提交运行已真实通过：[40301904326](https://github.com/hoanhkhai1hk-wq/scholar-graph/actions/runs/40301904326)。此前PR专用接口与匿名API403未能确认状态，随后通过连接器通用workflow接口取得该成功运行及步骤证据。

全量层仅单子验收与部署前运行：`python tests/run_regression.py full --no-key --corpus-dir pdf`；包含真向量、OCR及长书。没有Key的5项真模型测试跳过；有已授权模型环境且去掉--no-key才调用真实模型。本单未使用Key。

Docker无缓存构建：`docker compose build --no-cache`；启动：`docker compose up -d --wait`；快速测试：`docker compose exec -T backend python tests/run_regression.py fast --no-key`。公开模型准备、只读官方语料覆盖与完整探针命令详见backend/README.md。

## 审计与证据

最终审计：31/31项通过。contracts/、frontend/、docs/、prompts/、experiments/、test-records/相对开工基线零改动。已知环境Key对Git跟踪内容及本轮证据做不回显值的扫描，无命中；Key未传构建/容器，未写任何文件。

- [构建与克隆](final-deployment-build.json)
- [容器官方用例与定时记录](final-deployment-container.json)
- [容器JUnit](final-deployment-container-pytest.xml)
- [宿主机最终结果](final-deployment-host-final.json)
- [宿主机最终JUnit](final-deployment-host-final-pytest.xml)
- [宿主机首轮失败保留](final-deployment-host.json)
- [最终运行/镜像审计](final-deployment-runtime.json)
- [CI记录](final-deployment-ci.json)
- [最终审计](final-deployment-audit.json)

## 提交清单

完整哈希与每次提交对应文件见 [提交清单](final-deployment-commits.json)。证据提交自身哈希见交付回报。

| 完整哈希 | 事项 |
| --- | --- |
| bff6d3e02c05647b32c5ecd906c6c510f373b560 | 落地提交快速回归与含真向量长书的全量验收分层 |
| 0aa87f85c44994f7d996990934e051f1199c8909 | 注册后端自动追踪调度并持久记录定时运行与失败 |
| 000e8023a068c978138aece9aff8fbb2b8743e81 | 更新双服务部署镜像并加入干净构建与容器官方验收入口 |
| 8a889c8bec37f0d1dae8ea9383501ae38ae798c4 | 补充部署镜像隔离审计与双环境验收报告生成 |
| 112ab20be9313babbc440fb6e5faebcfc7154158 | 隔离公开模型下载准备并保留容器续传与完整校验记录 |
| af5160bc7c577f7526b3370ad4ec55ab32ad7f25 | 修正Linux向量虚拟环境符号链接导致worker丢失依赖 |
| 26804191cfdeb7e2c5f0bb8680c274bfb45531e4 | 补齐容器校准证据并隔离调度用例的部署种子 |
| 061863749807fa6340cbbfb4feb49f012bdbe6b9 | 分离公开OCR模型准备与逐页推理预算并复用权重缓存 |
| 4f87ad3f13fa04f353986750e90f4e8582015064 | 为公共构建依赖下载增加有界重试与官方HTTPS源 |
| 62dca5182b6098a883e0ffe8d72d9560f291e1ff | 固定支持断点恢复的pip并保留大依赖哈希校验 |
| cd20b1d28b9ee79f33dbcd6655db47762e923eb6 | 保留失败重建证据并观察上传后两轮真实定时查询 |
| 3bc9a8c2972823c11c82d6a89ff21648e51a44fb | 隔离容器组件测试默认模式并核验生产向量配置不变 |
