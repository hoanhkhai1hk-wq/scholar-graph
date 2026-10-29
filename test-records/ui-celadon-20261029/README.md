# B 青瓷书页界面验收

本轮完整报告：[docs/ui-polish-acceptance.md](../../docs/ui-polish-acceptance.md)。

最终有效结果：build09生产构建；fast05 200通过；related05 418通过；browser06 12/12；states02 5/5；final-capture 9页四尺寸36截图无横向溢出；正式3400九页与研究助手实测通过；独立复核原四项及追加悬停一项全部resolved，disposition: ship。

`browser01`至`browser05`、`states01`及旧构建是失败或中间探针，保留用于追溯，不能计入最终通过。`states01`的位置记录2635→12998暴露旧断言不足，最终states02严格校验2667→2667。`taste-after`首页检查抓到初始骨架，最终taste-final-qa对真实问答页完成检查为0发现。

图谱最终真实20篇范围由graph-real20-final严格排除自编中文测试材料，ID清单保留。早期browser06图谱的20份材料含1份自编材料，不计真实20篇验收。

真实服务：DeepSeek模式问答、原文/PDF、20篇图谱、翻译端点、CSV、检索。明确注入：断网分支，真实图谱响应延迟800ms及PDF响应延迟2s以捕获骨架；不把这些延迟当性能。翻译允许已验证缓存，不声称每次都新调用模型。

命令：

```powershell
backend/.venv/Scripts/python.exe tests/ui_celadon/run_checks.py fast --run <唯一运行名>
backend/.venv/Scripts/python.exe tests/ui_celadon/run_checks.py related --run <唯一运行名>
node tests/ui_celadon/browser_acceptance.cjs <唯一运行名>
node tests/ui_celadon/finish_states.cjs <唯一运行名>
backend/.venv/Scripts/python.exe tests/ui_celadon/runtime_audit.py
```

运行前使用已存在的本地配置，不把Key写入命令行或证据。隔离测试库由runtime.py复制真实来源资料与对应历史状态。不要在个人库运行破坏性测试。本轮浏览器管理弹窗只取消，未删除原论文。

范围：本轮UI与相关回归，不宣称PDF全部内容质量重新通过；Chrome在主机，2CPU/4GiB为前后端容器合计限制；真实后台隐藏停动未验证；公网速度未验收。源码扫描只有一轮，之后由独立代理检查四项修复。截图为真实浏览器证据，来源索引见screenshot-origins.json；无AI生成位图资产。

证据清单与SHA256见manifest.json；原PDF和凭据未复制到这里。
