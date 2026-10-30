# 技术文档构建与核对

源码为technical-document.md；唯一允许入库的PDF为technical-document.pdf。技术文档构建不是重新运行全部业务验收。

先安装后端及前端锁定依赖（README），文档额外依赖：

```powershell
backend/.venv/Scripts/python.exe -m pip install -r docs/requirements.txt
backend/.venv/Scripts/python.exe scripts/sync_submission_metrics.py
node scripts/build_technical_document.cjs
backend/.venv/Scripts/python.exe scripts/check_technical_document.py
```

Chromium使用本机Chrome；非默认安装可设置SG_CHROME_PATH。Python可用SG_DOC_PYTHON指定；默认使用项目backend/.venv。Linux需安装可用的中文字体及Chrome，再设置相同变量。构建只读本地图片，不加载境外字体或网络脚本。

metrics脚本从test-records原始JSON、JUnit及逐项报告重新提取20组实测数字，附路径和规则。数字变化时需同时更新Markdown里的对应值并重新生成PDF；check脚本不会用新结果静默覆盖旧文档。旧报告仍保留，不用修改原证据来适配文档。

检查包括：PDF页数≤30、实测值与JSON登记和正文/PDF一致、团队/评分权重/保留项存在、物理页文本边界。所有页渲染到data/submission-20261030/technical-pages并生成联系表；必须查看渲染图检查孤行、断表、截图和文字。坐标检查不能代替视觉检查。

发布前运行scripts/audit_submission.py扫描当前跟踪文件及全部可达Git历史的Key格式与本地真实Key；只输出命中数量和位置，不输出候选值。本地被忽略的.env、data/和pdf/不作为公开内容；只读配置值用于查泄露，不能把它们打包进证据。
