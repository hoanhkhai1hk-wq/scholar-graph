# 公开等价物、非官方 pdf/ 文件：三项验收与回归总报告

范围：**公开等价物、非官方 pdf/ 文件**。用户尚未提供官方pdf/文件，本轮没有运行、没有声称官方三用例通过。执行日期2026-10-25（Asia/Shanghai），在2026-10-30目标前完成；工作目录D:\AI_Workspace\Tasks\scholar-graph，分支main。

开工前git pull --ff-only原文 `Already up to date.`，主干完整哈希 **7ac617a4ff818cc3840069098fc3477ca614b0e8**，工作区干净。本单仅增加tests/探针与报告，backend/、contracts/、services/、compose、前端及其他工具负责目录均零改动。所有契约目录26个已跟踪文件（含12类Schema/example与说明文件）逐一Git blob与开工基线相同。

## 结论：公开等价物、非官方 pdf/ 文件

**三个业务目标均未通过；三项真实验证已经完成。最终296项回归通过不能替代三个业务目标，也不是官方用例通过。** 不修改生产限制、身份抽取、去重策略或契约来掩盖失败，不用小文档替代完整长书。

| 公开等价物、非官方 pdf/ 文件用例 | 业务结论 | 实测原始数字与原因 |
| --- | --- | --- |
| 1706.03762v7→v1去重触发 | 未通过 | 原始上传均201；175/162个Chunk；两次去重与差异查询均404，无warning字段、无自动保留v7建议。辅助公开抓取带真实arXiv元数据可生成裁决，词频Dice=0.933224，recommendation=manual_review、human_override=false，仍不是语义去重或自动保留新版 |
| v1完整15页合成扫描OCR | 未通过 | 150 DPI逐页光栅化，15页文本层字符数均0；默认300秒：304.962881秒、422 OCR_FAILED、有效Chunk=0；900秒补测：904.776897秒、422 OCR_FAILED、有效Chunk=0；输入SHA相同，均确实进入OCR |
| Understanding Deep Learning完整541页 | 未通过 | 作者公开v5.0.3原书22,344,992字节；541页；422 PARSE_FAILED，命中200页上限；已发布Chunk=0，未进入索引，索引耗时null；上传0.386671秒，采样RSS峰值161,959,936字节=154.457031MiB；目标chunks分页404 |

长书内存数字只代表早期拒绝过程，不是541页完整索引内存需求。内存按50ms采样测试进程及全部子进程RSS合计，不冒称精确瞬时高水位。未进入索引不能写耗时0秒，也不能拿空库分页壳正常冒充长书分页通过。

## 去重原文：公开等价物、非官方 pdf/ 文件

原始上传第二篇v1后的去重响应：

```json
{"error_code":"PAPER_NOT_FOUND","message":"无该新版论文的去重记录。","details":null}
```

上传没有预警字段，因此不存在可引用的预警消息，不能捏造。原始PDF提取的title=null、authors=[]、doi/arxiv_id/version=null，当前精确身份查找无法配对；已具备的BGE/Chroma搜索器未被接入版本去重。辅助/retrieval/fetch真实公开调用附带arXiv标识后可配对，系统依据原文：

```text
已检出文本变化，但文本相似度和版本序号不能证明新版质量更高；需人工核对差异。
```

辅助裁决是manual_review，未自动选择保留v7。本次实现实际将先入库v7写为old_paper_id、后入库v1写为new_paper_id；这是观察到的实现行为，不是改变契约的“新版”业务口径。不能因此把keep_new误称为保留v7。完整DedupDecision、38个解析分组的差异摘要原文及38条带锚点关键句，已原样保存在[去重JSON](public-equivalent-dedup.json)，摘要原文亦完整写入[去重报告](public-equivalent-dedup.md)。章节分组中存在正文/公式/邮箱误识别，不把38当作人工认定的科研章节变化数。

## OCR与长书原文：公开等价物、非官方 pdf/ 文件

OCR两次均返回：

```json
{"error_code":"OCR_FAILED","message":"本地 OCR 未完成，请检查依赖、模型与运行时限。","details":null}
```

300/900秒测试均未发布有效Chunk或文本。耗时与配置时限相符，但当前适配器把底层退出错误和超时统一脱敏，未保存原异常类别，不能声称精确定位为依赖缺失、OOM或其他具体缺陷。补测只设置已有LocalEngines的900秒参数，生产API默认300秒未改，后续不再延长重试。

使用pdf-pro流程：pypdfium2 5.14.0按150/72比例将原v1全部页面渲染RGB，再由ReportLab 5.1.0按原页尺寸drawImage合成。两次扫描PDF SHA均为51bc393630fc62cd866604ae5297bf901a268469c00975df972947c2feb39264，5,210,401字节，全部15页无文本层；未抽页或用短句替代。PaddleOCR3.7.0、PaddlePaddle3.3.1与原模型/阈值保持不变。合成件不是官方img文件。完整数字、状态与合成方法见[OCR报告](public-equivalent-ocr.md)、[默认JSON](public-equivalent-ocr.json)、[补测JSON](public-equivalent-ocr-extended.json)。

长书原始错误：

```json
{"error_code":"PARSE_FAILED","message":"PDF 页数必须在 1 到 200 之间。","details":null}
```

下载来自[作者官方v5.0.3发布](https://github.com/udlbook/udlbook/releases/tag/v5.0.3)，完整PDF SHA为f8237d393163900fa8e43210e680a3f987b45ccac7750b372e156fae3df0bf32，实际541页。下载成功且未超50MiB，失败原因是当前200页检查，不是下载失败或已证实的内存不足。未调用整书MinerU切块/Chroma索引，也未拆成小文档绕过限制。完整分页响应与内存口径见[长书报告](public-equivalent-longbook.md)、[长书JSON](public-equivalent-longbook.json)。

## 三项结束后的全量回归

三项输入范围始终为公开等价物、非官方 pdf/ 文件；以下pytest是既有回归（主要为自制样例），不与这三项业务验收混计。执行在900秒补测结束之后：

```powershell
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --basetemp data/public-equivalents/regression-temp --junitxml tests/reports/public-equivalent-pytest.xml
```

原文：

```text
296 passed in 146.48s (0:02:26)
```

[JUnit](public-equivalent-pytest.xml)：296总数、296通过、0失败、0错误、0跳过。真实单页自制PaddleOCR、MinerU、CORS/同源代理与既有模块端点回归均执行；单页烟测通过不能替代本轮15页扫描件失败。没有把公开案例脚本注册为默认pytest联网任务，也没有降低或删除旧覆盖。pip check原文 `No broken requirements found.`。

[证据交叉核验](public-equivalent-audit.json)检查报告与真实PDF哈希、实际落盘Chunk/参考/引用数量、裁决/差异原文、失败无半组记录、相同扫描字节、完整541页输入及冻结契约一致。evidence_consistency_checks_passed=true，business_acceptance_all_passed=false，两者明确分开。新增文件常见Key/私钥及下载签名模式扫描0匹配；这是有限模式扫描，不保证检出所有秘密。未读取.env、不调用真实大语言模型、不使用真实API Key；下载签名查询串不进交付文件。

## 提交与复现

三个公开等价物、非官方 pdf/ 文件用例各自一个提交，完整哈希及文件如下；全量回归与总报告另一个验证提交，最终哈希及git push原文由交付回报给出。

| 完整提交哈希 | 用例 | 文件 |
| --- | --- | --- |
| 3b49fe56649d6ef9d845f7e720f05271d3855be8 | 去重 | tests/public_pdf_support.py；tests/run_public_dedup.py；tests/reports/public-equivalent-dedup.json；tests/reports/public-equivalent-dedup.md |
| 3e5a44b31fd62189b1cbce0e8261f871a9dd679e | 长书 | tests/run_public_longbook.py；tests/reports/public-equivalent-longbook.json；tests/reports/public-equivalent-longbook.md |
| dfb60865f5e995a2ea03ce3c443f5cd20f2ceddb | OCR默认与补测 | tests/run_public_ocr.py；tests/reports/public-equivalent-ocr.json；tests/reports/public-equivalent-ocr-extended.json；tests/reports/public-equivalent-ocr.md |

每份用例报告有实际复现命令，须选尚不存在的data输出目录。真实PDF、扫描件、预览图、模型缓存只留D盘被忽略的data/；未提交原论文/整本书。三项公开等价物、非官方 pdf/ 文件记录完整，不请求用户把它们认可为官方用例。

交由用户转达总指挥的后续缺口：原始上传身份字段抽取与去重触发、语义去重接入/版本新旧方向及保留策略、长扫描页OCR性能与超时诊断、长书页数/任务策略及真正全量索引性能。它们需要后续正式拆单，本单不改接口契约、不改实现、不触碰前端，也不直接联系其他工具。
