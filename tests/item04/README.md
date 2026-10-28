# 第4项：公开获取、参考文献、追踪和推荐

本轮只读官方命题1.4，保留所有原始PDF与旧验收库。隔离库为 `data/item04-20261028/records`，网页3400，后端8100；个人库3000/8000独立。`.env`只供本地Compose引用凭据，不提交值。普通抓取与推荐排序不调用生成模型。

## 最终环境

```powershell
docker compose -p scholar-graph-item04 --env-file .env -f tests/item04/compose.yml up -d
backend/.venv/Scripts/python.exe tests/item04/run_related.py --run new-related
backend/.venv/Scripts/python.exe tests/run_regression.py fast --no-key
```

最终Compose默认镜像固定为item04，避免重启回旧版。构建复用本机已有、已验证的item03依赖镜像，不改依赖：

```powershell
npm --prefix frontend run build
backend/.venv/Scripts/python.exe tests/item04/build_runtime.py frontend --run new-front-build
backend/.venv/Scripts/python.exe tests/item04/build_runtime.py backend --run new-back-build
```

构建脚本只复制后端模块、契约、前端编译产物与界面源码；不包含Key、PDF或个人数据。普通根目录Dockerfile仍可构建全部依赖，本轮第一次基础层下载缓慢，已停止，改用上述本地依赖复用流程，原始构建失败/中断日志保留在data。

## 重跑业务

每次使用新运行名称。`title_fetch.py`、`retry_references.py`、`failure_probe.py`、`feedback_probe.py`和浏览器脚本拒绝覆盖已有运行目录。`common.py`的初始快照与`seed_upload.py`仅首次空验收目录执行。`runtime_probe.py`需已有本轮基线文件，核对主库、镜像、DNS和源码；首次部署前应保存`main-before-release.json`。

```powershell
backend/.venv/Scripts/python.exe tests/item04/title_fetch.py --run new-titles 'BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding' 'Reformer: The Efficient Transformer'
backend/.venv/Scripts/python.exe tests/item04/feedback_probe.py --run new-feedback
node tests/item04/browser_acceptance.cjs new-browser
node tests/item04/browser_secondary.cjs new-secondary
```

浏览器脚本使用项目Playwright与本机Chrome，创建自己的临时配置；真实点击网页按钮，不模拟HTTP结果、不设置DOM状态冒充操作。主浏览器脚本会再次提交40篇参考文献获取任务、点赞并点踩BERT；第二个脚本保存周计划再恢复日计划，点击代码证据，并在独立故障网页制造失败。副作用均限制于验收库，不能对个人库改端口运行。

旧版五篇真实论文的反馈复现，从`data/tracking-acceptance-final-v4/records/papers`复制原始记录到新目录，并验证源字节。历史库不改写：v1实际4→2→4，v2实际4→1→4，程序分别报告，不强行调整旧接口分数。

## 真实定时和失败

在3400网页选择Attention，启用每日发现，保存计划；随后仅运行观察脚本，不调用手动运行端点：

```powershell
backend/.venv/Scripts/python.exe tests/item04/watch_schedule.py --run new-scheduled-cycle
```

首次等待15秒，随后真实请求arXiv Atom API；之后间隔每日/每周。这验证首次自动周期，不代表已等待24小时或完成长期稳定性试验。OAI-PMH全库采集及独立arxiv.py通道未实现；当前是自有有界Atom轮询与一次瞬态重试，不能声称已经切换到OAI或另一检索服务。

故障服务3410/8110使用自己的种子副本，将真实公网代理指向关闭端口；前后端内部网络保持正常。`failure-compose.yml`默认保留item03用于重现旧状态错误，验证新版必须显式指定最终镜像：

```powershell
$env:SG_ITEM04_FAILURE_BACKEND_IMAGE='scholar-graph-backend:item04-20261028'
$env:SG_ITEM04_FAILURE_FRONTEND_IMAGE='scholar-graph-frontend:item04-20261028'
docker compose -p scholar-graph-item04-failure -f tests/item04/failure-compose.yml up -d
backend/.venv/Scripts/python.exe tests/item04/failure_probe.py --run new-failure --expect after
```

## 证据范围

公开证据由`curate_evidence.py`从本地原始文件生成，发布前校验哈希。完整PDF、完整解析原文、完整返回、浏览器trace、工作区保护快照均在被忽略的data目录。公开结果保留元数据事实、原文定位、真实命令输出、截图和数字；摘要正文以存在标记、长度与哈希代替。

内容筛选只是可解释的启发式排序。`reference_labels.json`是运行新排序前的单人草稿；复核发现[36]确有label smoothing采用语句，另行记录修正，不能把修订后的同样本一致率当作独立准确率。本轮未取得的8条参考文献、冷启动约21秒和其他限制均见`test-records/第4项报告.md`。
