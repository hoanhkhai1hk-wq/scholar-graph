# 教师评价整改与验证记录（2026-11-14）

截图中的原评分为80.0。本次完成教师提出的两项工程修改；没有新的官方复评分数，测试通过不等于能承诺最终评分不下降。

## 改动与对应评价

| 教师建议 | 本次实现 |
|---|---|
| 将解析坐标跟随检索片段，并加入答案引用定位 | 复用已冻结的Chunk.bbox，为词法、混合检索证据及检索接口增加location定位信息；研究回答引用及计算操作数从真实Chunk重建location，防止模型或候选元数据改写位置。 |
| 扫描件与原生PDF共用段落高亮 | 阅读器优先使用解析时保存的归一化区域；扫描件不再因缺文字层直接退回整页。高亮使用百分比坐标，保留缩放后的对齐；文末引用与返回使用同一逻辑。 |
| 固定各半融合改为按实际贡献记录的可解释权重 | 检索页dense/sparse及问答dense/lexical共用确定性融合函数；输出各路权重、召回/独有/共有数量，记录逐段排名和得分分解。检索页可展开“排序依据”，问答诊断保留权重摘要和完整记录ID。 |

坐标格式为`location = {bbox, coordinate_system: "page-normalized-top-left", precision}`，bbox使用左上原点的`[x0,y0,x1,y1]`页面归一化坐标。bbox为空时标记page（页级），不编造区域。原生PDF缺坐标时仍可搜索文字层；扫描件缺坐标时明确回退物理页。

原有v1冻结记录和四字段锚点保持兼容。v2研究回答携带定位附加信息；旧答案与历史会话仍可通过锚点读取真实Chunk并定位。用户原有UploadForm修改及其他未跟踪工作未被纳入本次改动。

## 权重如何复算

设某片段在一路的排名为r，RRF常数k=60；该片段被s条路召回。该路获得`61/(60+r)/s`的贡献累计值。将各路累计值归一化得到权重；两路均有效时限制为35%–65%，避免一路压过另一条有效召回渠道。只有一路有效时其权重为1，空路为0。最终片段得分为各路`weight*61/(60+r)`之和，未命中的路贡献0。

这是本次召回贡献的可解释度量，不是答案正确率，也不是人工标注的相关性概率。两路实际贡献相同时权重仍可为各半。原来的词法回退、数字/原文校验、作者首页覆盖和受限精排接口继续保留。

问答逐段完整记录原子保存在数据目录`qa-retrieval/fusion/<trace_id>.json`，包含排名、权重、贡献和最终顺序，不保存查询正文、引文或凭据。记录失败会显示UNAVAILABLE，不把有效向量召回误记成回退。这里另外保留了真实验收的七份`fusion-*.json`，便于独立复算。

## 验证结果

| 检查 | 结果 | 证据 |
|---|---|---|
| 修改前快速回归 | 200通过 | baseline-fast.xml |
| 修改后快速回归 | 223通过 | final-fast.xml |
| 定向回归 | 143通过 | targeted.xml |
| 全量回归（含真实OCR） | 841通过、7跳过 | full-regression.xml |
| 独立真实BGE-M3/Chroma测试 | 1通过 | real-vector.xml |
| 生产构建与TypeScript校验 | 通过 | verification-summary.json |
| 实际阅读器组件的浏览器检查 | 12项通过、无页面异常 | browser-component.json |
| 技术PDF | 14页，20项原数字索引与来源一致，无文字越出物理页面 | technical-document-check.json |

全量中的7项跳过为5项真实外部模型调用、1项541页长书解析、1项需显式启用的真实向量测试。最后一项已在独立测试中执行并通过；本次没有重新执行外部模型生成和541页整本解析，不把这些记作通过。

浏览器使用实际LayoutViewer和AnchorTag源码编译成隔离测试页面，加载真实原生PDF和真实PaddleOCR扫描件；验证1440/390宽度高亮、引用点击、正文至文末往返、无坐标文字层回退、无坐标扫描件页级回退。测试页面的API代理及旧数据null坐标响应由验证脚本提供。本次四张核对截图保存在[browser-screenshots/](browser-screenshots/)，完整本地输出位于`output/playwright/teacher-feedback-20261114/`。

自动审批拦截了单独启动Next.js前端服务的命令，只返回“blocked by policy”，未给出更具体原因。因此本次采用已编译组件的真实浏览器验证，未声称启动完整Next.js应用并完成端到端验收；完整应用生产构建已通过。最初隔离脚本缺少框架环境替换的失败保留于browser-harness-initial-failure.json，修正后完成上述12项检查。

## 固定六题的真实召回对照

对同一批本地真实BGE-M3向量召回，分别执行原固定等权RRF及新贡献加权RRF。原来的作者首页覆盖在两边完全一致，避免把已有规则差异误判成新权重退步。第六题跨两篇论文，故共七组论文级对照；下表名次为目标原文片段在融合排序中的名次，不是最终模型回答得分。

| 固定问题 | 原名次 | 新名次 | 本次语义/词法权重 | 对照 |
|---|---|---|---|---|
|第六作者与机构|4|4|0.496756 / 0.503244|通过|
|Adam超参数|2|2|0.502143 / 0.497857|通过|
|Base训练硬件|4|4|0.497970 / 0.502030|通过|
|BLEU与基线|5、1|5、1|0.496346 / 0.503654|通过|
|Layer Normalization书目|15|15|0.495453 / 0.504547|通过|
|承袭关系：Attention侧|1|1|0.497949 / 0.502051|通过|
|承袭关系：BERT侧|4|4|0.499479 / 0.500521|通过|

七组目标片段名次均保持一致；前8与前24的目标片段覆盖率均未比原方案下降。Layer Normalization书目原本位于第15名，不能把它记作前8命中。完整数据和逐段记录见real-recall-comparison.json及对应fusion文件。此结果仅支持这些固定问题的检索未退步，不外推为所有问题的准确率、最终生成质量或教师分数保证。

## 代码和文档

- `backend/scholar_graph/evidence_location.py`：统一定位信息；`grounded_model.py`、`qa_evidence.py`、`workspace_research.py`：检索与引用传递。
- `backend/scholar_graph/rank_fusion.py`：共享贡献加权函数；`qa_retrieval.py`、`retrieval.py`、`vector_search.py`：两种检索路径及解释记录。
- `frontend/components/LayoutViewer.tsx`：坐标高亮与缩放；`AnchorTag.tsx`、`ResearchAnswerView.tsx`、`RetrievalWorkspace.tsx`：引用、检索跳转和排序依据。
- `tests/test_evidence_location.py`、`tests/test_rank_fusion.py`：新增23项检查；原有检索已知顺序测试保留，更新其分数断言以匹配新公式。
- README、后端说明及技术文档Markdown/PDF已同步；技术PDF沿用原14页版式、原历史实测数字与限制披露，并更新版本日期和页脚。原技术PDF/Markdown备份于本地`data/teacher-feedback-20261114/before-document/`。

## 在现有工作站复跑

```powershell
backend/.venv/Scripts/python.exe -m pytest tests --layer fast -q
backend/.venv/Scripts/python.exe -m pytest tests --run-ocr -q
backend/.venv/Scripts/python.exe -m pytest tests/test_full_layer_live.py::test_real_local_bge_m3_dense_sparse_chroma --run-vector -q
backend/.venv/Scripts/python.exe scripts/verify_feedback_retrieval.py
backend/.venv/Scripts/python.exe scripts/prepare_feedback_fixtures.py
```

浏览器脚本`node scripts/verify_feedback_browser.cjs`使用隔离后端8045端口，数据目录为`data/teacher-feedback-20261114/records`；本次已执行并通过，验证完成后关闭测试服务。召回对照依赖现有工作站的Attention/BERT冻结来源、本地BGE-M3权重及独立向量运行时；这些论文和权重不随仓库分发。

```powershell
$env:SG_DOC_BUILD_DIR = "$PWD/data/teacher-feedback-20261114/document-build"
node scripts/build_technical_document.cjs
backend/.venv/Scripts/python.exe scripts/check_technical_document.py
```

本记录与verification-summary.json保存推送前的本地验收快照，不记录其后的发布状态。已有部署和参赛平台提交均没有在验收中替换；GitHub发布以实际提交为准，Docker更新步骤见[更新说明](../../docs/docker-update-20261114.md)。
