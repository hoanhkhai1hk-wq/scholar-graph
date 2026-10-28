# 第3项：真实阅读、翻译与同步验收

正式源文件：`pdf/1706.03762v7.pdf`，15页、175个已解析段落。独立数据目录 `data/item03-20261028/records`，前后端3380/8080，原始论文与个人库不修改。

```powershell
docker compose -p scholar-graph-item03 --env-file .env -f tests/item03/compose.yml up -d
backend/.venv/Scripts/python.exe tests/item03/ingest.py
```

上传脚本要求空库。正式浏览器先在阅读页“**双语与翻译→全文→开始翻译**”启动真实任务；记录任务ID到本地 `full-task-browser.json`。本次原始ID已保存在本地证据中，完整翻译不公开到Git。

```powershell
backend/.venv/Scripts/python.exe tests/item03/live_translation.py --run fresh-run --direct-full
backend/.venv/Scripts/python.exe tests/item03/check_source_scope.py --run fresh-scope-check
backend/.venv/Scripts/python.exe tests/item03/protection_fixture.py
backend/.venv/Scripts/python.exe tests/item03/live_protection.py --run fresh-protection
backend/.venv/Scripts/python.exe tests/item03/run_related.py --run fresh-related
backend/.venv/Scripts/python.exe tests/run_regression.py fast --no-key
node tests/item03/native_scroll_browser.cjs fresh-native-browser
```

每次使用新的运行目录，已有目录拒绝覆盖。生成保护样本脚本只运行一次：它创建两个明确标记的自编PDF、验证源文与PDF文本一致，再保存人工定义的测试段落。此样本验证真实翻译服务的代码、LaTeX、HTML保护及中文原稿英译，**不作为官方PDF自动解析准确性证据**。生成样本需要当前宿主已安装的reportlab、pypdfium2；浏览器脚本使用项目Playwright与Windows已安装Chrome，创建独立临时配置，不打开用户配置。

浏览器拖动使用真实滚动条鼠标输入，未设置滚动位置伪造操作；禁用Playwright默认隐藏滚动条参数。导出和刷新恢复也通过实际按钮完成。两个方向的对应位置误差，由实际DOM段落边界和段内进度计算；边界截断不是任意字符对齐。本功能为页＋段落定位，字符级定位未实现。

`check_error_contracts.py` 单独验证中译英不支持章节范围、以及隔离移除Key后返回502且无译文。正常服务凭据仅由本地`.env`注入，脚本与报告不打印值。

公开证据由`curate_evidence.py`整理，保留命令原始字节与源文/译文哈希；官方完整译文、原始PDF、浏览器trace均留在被忽略的本地data目录。主环境更新后，`runtime_probe.py`核对健康、DNS、7个服务文件哈希、原始PDF未变、选区真实模型调用，以及导出文件与保存译文一致。
