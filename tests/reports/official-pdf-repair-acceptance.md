# 官方 pdf/ 真文件三缺口修复验收

本单修改后端实现并重验同一批**官方 pdf/ 真文件**。三项实际通过 3/3；失败 0/3。全量回归统计见下方，不与业务验收混计。未调用真实大模型或使用真实API Key。开工main `fb98c8fddadfebdcc58e325f7bdd53b4d42ba71f`，`git pull --ff-only` 原文 `Already up to date.`，工作区干净。

## 官方 pdf/ 真文件修复前后对照

| 项目 | 修复前：官方 pdf/ 真文件 | 修复后：官方 pdf/ 真文件 | 结论 |
| --- | --- | --- | --- |
| 去重触发 | v7/v1上传201，175/162 Chunk；无预警；裁决/差异404 | v7：175 Chunk；7.850778秒；RSS 403.000000 MiB（422576128字节）；v1：162 Chunk；9.326942秒；RSS 386.140625 MiB（404897792字节）；第二传预警“建议保留库里较新版本（v7）；本次上传为v1。依据同一arXiv身份及PDF原文版本标识，避免降级覆盖；不代表学术质量排名。”；裁决/差异200/200 | 通过 |
| 扫描OCR | 307.664604秒，TimeoutExpired，HTTP422，OCR_FAILED，0有效Chunk | HTTP201；989 Chunk；688.328745秒；RSS 1015.902344 MiB（1065250816字节）；失败页[] | 通过 |
| 长书 | 541页，pipeline.py:124–125的200页上限拒绝；0 Chunk；未索引；RSS 143.453125 MiB | HTTP201；6859 Chunk；166.185635秒；RSS 830.339844 MiB（870674432字节）；17个批次；索引相关累计5.342秒 | 通过 |

扫描件修复后耗时可能长于旧版超时失败，长书RSS也高于原来直接拒绝的143.453125MiB；旧版没有完成同等工作，不能比较为性能改善。RSS每50ms轮询本测试进程与全部子进程的采样合计，可能重复计算共享页，不是精确系统高水位。索引相关累计计时包含规范化、批次Schema/外键门禁、文件发布与SQLite提交，不冒充纯SQL耗时。

## 去重实现与实测

解析完成后查本地候选：精确DOI/arXiv/标题作者身份优先；身份缺失时用真实词频Dice，阈值0.90，明确冲突的DOI/arXiv不会配对。不宣称语义向量去重。PDF原文中的arXiv版本标识现会提取为PaperMeta的原有字段，未从文件名虚构版本。

同一arXiv的低版本上传，保留库内高版本建议只依据身份及版本先后，不称学术质量更好。`new_paper_id`仍是本次后上传v1的paper_id。第二传预警原文：

> 建议保留库里较新版本（v7）；本次上传为v1。依据同一arXiv身份及PDF原文版本标识，避免降级覆盖；不代表学术质量排名。

不改变PaperMeta：单篇HTTP201响应体仍是原记录；预警通过`X-ScholarGraph-Dedup-Warning`返回UTF-8百分号编码文本，编码标记响应头为`percent-encoded-utf-8`，Link指向裁决接口，CORS已暴露两头。未修改前端，不声称前端已显示弹窗。批量成功项命中时可带新增可选传输字段warning。裁决原文与完整DiffSummary见[去重JSON](official-pdf-repair-dedup.json)，均按new_paper_id真实落盘可查；human_override读取优先规则未改变，系统原记录仍保留。

## OCR逐页产出与失败恢复

直接上传官方`1706.03762v1_img.pdf`，没有重制、抽页或换文件。显式固定PP-OCRv5_mobile_det与英文en_PP-OCRv5_mobile_rec，不再只指定检测器而让识别模型落到默认配置；本机旧缓存中存在PP-OCRv6_medium_rec，新英文轻量模型已实际下载并推理。包版本：PaddleOCR 3.7.0 / PaddlePaddle 3.3.1。实际OCR仍为本地CPU，不是大模型调用。复用本机模型缓存不计入上传耗时，未使用Key。

每页独立运行、独立限时、逐页校验并原子发布，后续页失败不会丢掉已发布Chunk。扫描页直接PaddleOCR；文本批次MinerU超时后逐页PaddleOCR兜底。错误明确列出失败物理页；原错误契约只允许标量details，因此failed_pages用逗号分隔字符串、page_errors用安全逐页原因文本，没有改Schema或塞业务记录。内部progress.json保留完整页列表；再次传相同源文件可补未完成页，并修复批次已落盘而索引/检查点未提交的中断。

本次状态最终为`completed`；已处理15/15页；有效Chunk 989；失败页[]。真实首批文本：

```text
Attention Is All You Need
Ashish Vaswani*
Noam Shazeer*
```

运行中观测见[OCR JSON](official-pdf-repair-ocr.json)的observations：OCR状态未完成时，原Chunk端点已返回非空记录；最终数据经过原门禁。识别完成不等同于逐字准确率评测，未声称数学公式/表格逐字正确。

## 长书流式与分批索引

官方长书原文件541页、22344992字节。取消200页硬拒绝，默认可配置2000页（范围1–10000）。以PDFium逐页检查文本层，只保留首个有效页的元数据候选；原始PDF快照受50MiB上传限制。每批最多32物理页切成临时PDF交给MinerU，解析后释放该批原始布局对象，页码映射回原始物理页；最终仍需保存规范化Chunk列表，内存随文本记录规模增长，不声称完全常量内存。

每批先通过原Schema与外键门禁，原子写partial目录并事务提交SQLite物理页/序号Chunk索引，解析状态持续更新。原Chunk端点通过SQLite分页，不为一页请求重新加载所有布局结果；非空产出在完成前即可读取。partial论文不混入完成论文列表。最终合并参考文献/引用再发布四类记录。索引是本地锚点索引，未冒充BGE-M3或向量去重。

本次17批处理全部541页，产出6859 Chunk，空白/无文本页登记为[2, 4, 10, 12]，无失败页；末页查询可到物理页541，越界页返回空表。详细进度、各批页码、计时及内存原始值见[长书JSON](official-pdf-repair-longbook.json)。

默认防呆：文本批32页/120秒，OCR单页90秒，分批整篇1800秒；worker等待也受剩余整篇时限约束。配置变量及范围见backend/README.md的新修复节。原小文本PDF继续用MinerU完整解析；GROBID状态仍为待验证。

## 回归、契约与边界审计

三项官方 pdf/ 真文件重验完成后执行 `backend/.venv/Scripts/python.exe tests/run_official_repair_regression.py`；包含`--run-ocr`，全量不依赖Docker或真实GROBID，既有自制样例加本轮故障注入回归，不能把回归输入称作官方文件。

```text
306 passed in 176.44s (0:02:56)
```

JUnit统计：总数306，失败0，错误0，跳过0。新增测试覆盖：无身份Dice候选、冲突身份排除、无关文档不误报、旧版本上传预警与裁决；单页失败保留其余页、补页恢复、全篇时限点名未处理页、索引中断恢复、非法OCR页码；201页分批与分页、配置页数上限。参见[JUnit](official-pdf-repair-pytest.xml)。

原26个契约文件Git blob零改动，旧官方报告与原始JSON未覆盖；只改backend/与tests/。`/pdf/`仍被.gitignore排除，Git未跟踪官方语料；运行前后源哈希一致。[审计脚本](../audit_official_repairs.py)核对真实落盘、Chunk锚点、索引计数及回归，输出[审计JSON](official-pdf-repair-audit.json)。

实现及证据提交（报告自身最终提交哈希另由交付回报列出，避免自引用）：

```text
78b5ddb59762c386c4d9f9d9429e8f8fcb797484 归档同批官方真文件三项修复后的真实上传与逐批产出
8ba4f31ae300242c165fd282ff38a78ffbfa0688 同步页面分批限制恢复机制与去重预警读取方式
bcd8511015a8e96d17092414da76c95bf52188ad 拒绝非法OCR物理页索引并保留逐页失败诊断
2ce52132fc300853d6013e00e40ceae5ee1d2108 修复OCR逐页限时保留产出并以受限批次解析索引长书
acc04e264632c305608a6a00357a0a618fa5314f 修复上传去重候选查找并返回保留较新库内版本预警
```

实际官方验收启动时部分实现尚未提交，三份JSON的source_commit记录当时HEAD，不假称该HEAD已包含全部修复；最终实现以本轮提交与全量回归为准。未变更前端或API路径，未调用真实大模型或真实API Key。原PDF和模型/临时运行数据全部留在被忽略的本地目录。
