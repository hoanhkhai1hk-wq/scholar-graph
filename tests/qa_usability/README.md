# 问答易用性修复与真实验收

范围：普通中文问答、跨篇关系、阅读研究助手和证据定位。任务开始于2026-10-28，收尾于2026-10-29。不是命题1.1–1.6的整体验收。

`data/qa-usability-20261028/` 保存完整真实SSE、失败尝试、语料副本和浏览器trace，不进入Git。公开结果在 `test-records/qa-usability-20261028/`；原文引用仅公开锚点与哈希，原始PDF不进入Git。

运行使用项目已有Python虚拟环境、Playwright依赖、本机Chrome、Docker镜像和本地`.env`。不输出凭据；原有官方语料与历史测试目录不覆盖。

```powershell
# 3400演示库，37篇论文；后端8100。必须带最后一个覆盖文件，才能保持本次修复镜像。
docker compose -p scholar-graph-item04 --env-file .env -f tests/item04/compose.yml -f tests/qa_usability/release.yml up -d --wait

# 主网页仍为3000。本机8000被另一Python进程占用，保留该进程，主后端发布为8030。
docker compose --env-file .env -f docker-compose.yml -f docker-compose.override.yml -f tests/qa_usability/main-release.yml up -d --no-build --wait

backend/.venv/Scripts/python.exe tests/qa_usability/live_cases.py --run fresh-service --extended
backend/.venv/Scripts/python.exe tests/qa_usability/official_regression.py --run fresh-official
backend/.venv/Scripts/python.exe tests/qa_usability/run_related.py --run fresh-related
backend/.venv/Scripts/python.exe tests/run_regression.py fast --no-key
node tests/qa_usability/browser_acceptance.cjs fresh-browser
backend/.venv/Scripts/python.exe tests/qa_usability/runtime_probe.py
```

服务与官方回归拒绝覆盖运行目录。官方回归复制第2项的五篇真实论文与工作台数据库到新目录，再用真实模型测试；原目录不写入。它通过进程内ASGI客户端验证后端，不能代替浏览器证据。浏览器脚本通过原生按钮操作，复用真实的修复前拒答会话验证追加重试；只在独立配置中设置真实会话ID，不伪造答案、拦截接口或注入DOM。

证据跳转验收同时检查目标页高亮、定位说明、地址栏页码、以及高亮实际进入阅读区。只检查存在高亮会误把旧页高亮算作成功。

重新构建镜像时先运行 `npm --prefix frontend run build`，再分别运行 `build_runtime.py frontend/backend --run 新目录`。依赖基础为本机已验证的item04镜像，源码覆盖层不包含Key、PDF或宿主node_modules。容器自动恢复的前提是Docker已运行，手工停止的容器保持停止。
