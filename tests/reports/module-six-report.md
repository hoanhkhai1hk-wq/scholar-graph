# 模块六：综述框架、摘录草稿与CSV图表

执行日期2026-10-24（Asia/Shanghai），在2026-10-30目标前完成。工作目录D:\AI_Workspace\Tasks\scholar-graph，分支main。开工前git pull --ff-only原文 `Already up to date.`，工作区干净，主干完整哈希 **aee2853ed9cc8d294860496fef65085046f310aa**。

新增POST /api/v1/frameworks、POST /api/v1/reviews、POST /api/v1/charts/csv，OpenAPI核对共 **19/19条业务端点已落地**，未落地端点清单为0。异步队列、真实模型自由写作、导出、GROBID联调仍是明确后续能力，不能用19/19暗示这些已完成。没有修改前端、prompts/、experiments/、test-records/、compose或其他docs；只改授权的backend/、contracts/、tests/及docs/api-draft-v1.md。

所有输入是**自制多篇落盘契约记录与CSV，非官方pdf/用例**。没有运行官方三用例，不声称前端接通，不调用真实大模型、不使用真实API Key、不读取.env。不直接联系WorkBuddy或DeepSeek Harness，协作信息由用户中转。

## FrameworkOutline v1.2正式补齐

新增contracts/framework-outline.v1.2.schema.json与framework-outline.v1.2.example.json。顶层3字段：schema_version、paper_ids、chapters；每章6字段：chapter_id、kind、title、paper_ids、anchors、writing_points；每个待写要点是{text,anchor}。所有对象全字段必填、禁额外字段。锚点沿用paper_id/page_number/section/chunk_id，页码是PDF物理页码。

原十一类Schema与example共22个Git blob逐一与基线相同，字段、类型、required与枚举均零改动；清单见[module-six-audit.json](module-six-audit.json)与[module-six-smoke.json](module-six-smoke.json)。原字段数（含schema_version）仍为：PaperMeta14、Chunk11、ReferenceEntry10、CitationLink6、QAAnswer5、DedupDecision7、DiffSummary6、ParseStatus7、ChartOutput7、GraphNode6、GraphEdge5。仅更新CONTRACTS.md登记本单新增框架，保留图谱首次发布的历史变更记录。

示例复用原PaperMeta/Chunk示例的真实合成标识、章节与12样本原文，不伪装成真实论文生成结果。框架返回前除Schema外，重建图谱/归位/标题/摘录并比较，拒绝未知锚点、错页码、篡改原文或无依据章节；没有改变任何旧记录的口径。

## 复用图谱、未来方向、推荐及检索

仅使用请求论文集合的已落盘四类记录。复用模块五build_graph：verified边参与PageRank与分层；每篇cornerstone成章，derived沿verified边的无向最短距离归入最近基石。并列距离及章内衍生排序复用模块四recommendations，视图限制为本次选择集合，不借集合外论文添依据；评分年取集合最大已知发表年，无年份用1。公式与权重完全沿用模块四：

```text
score = 100 * (0.40*G + 0.35*P + 0.15*T + 0.10*C); missing terms contribute 0, without reweighting
```

无基石可达的衍生论文、孤立论文各自单独成章，不假造基石。均匀A↔B引用循环的测试验证：两篇均为derived、各自归位，不能把均匀PR冒充基石。章节材料选择复用模块四lexical_ranking，以本篇标题对本篇Chunk排序；无匹配取首物理页/块id的首条非空原文，最多600字符，不跨块拼接。这个有限材料选择不声称具备语义推理或完整综述召回。

未来方向只从模块五已过滤的worth_exploring取有锚点原文，形成独立future_work章；excluded与时间不可验证条目不进入该章，没有依据不造章。正文历史摘录仍可引用作者当年提出未来方向的原文，不能把它改写成目前尚未解决的结论。

## 框架与综述HTTP实测

复用模块五自制A→B→C、D孤立的4篇落盘记录，C/B为基石。POST /frameworks请求 `{paper_ids:[paper-graph-a,paper-graph-b,paper-graph-c,paper-graph-d]}`，200返回：

| 章节 | 依据论文 | 待写摘录数 | 章节锚点数 |
| --- | --- | ---: | ---: |
| 基石论文：Synthetic Graph Study C | C | 1 | 1 |
| 基石论文：Synthetic Graph Study B | B、A（衍生归位） | 2 | 2 |
| 独立论文：Synthetic Graph Study D | D | 1 | 1 |
| 未来方向（所选语料尚未证实已解决） | C | 2 | 1 |

合计 **4章，5处章节锚点引用，4个唯一锚点，0处无证据标注**。未来方向仅document-level extraction、robust noisy labels；cross-lingual transfer已有更晚B论文的明确声明/verified引用锚点，继续沿用模块五排除结果。两条未来摘录来自同一C块，因而章节锚点去重为1。

POST /reviews携带同一paper_ids和上一步完整framework。响应为传输封装 `{framework,chapters,mode,unverifiable_count}`，mode=extractive。默认 **4章、6条原文摘录、6处要点锚点引用（4个唯一锚点）、0处unverifiable**。每条事实是同一Chunk的连续原文，status=verified只表示原文/数字回溯成立，不表示独立实验验证或已回应任意写作要求。数字检查复用模块二/五anchored_quote与QAAnswer门禁，passed必带同一来源锚点。

再请求requirements=[zzzzquantumteleportation]，在本章已有材料中词法未命中，返回 **4章、10条要点、6处要点锚点引用（4个唯一锚点）、4处unverifiable**。占位原文固定“未在本章摘录材料中检出所需要点；不可验证，未补写结论。”，anchors=[]，未添加论文事实。不能据此断言全文没有相关信息。额外要求只在本章已支持摘录中取证，即使共享Chunk还有已排除的未来方向，也不能把它重新塞回未来章。

框架被篡改、集合不一致或证据变化返回422 VALIDATION_ERROR；缺论文404 PAPER_NOT_FOUND。当前/reviews只接受当前同集合生成且未被无依据修改的框架，不支持自由编辑框架。框架是结构，综述是摘录草稿，最终成文仍由用户完成；没有把任何输出称为大模型生成。

## CSV图表HTTP实测

输入自制UTF-8 CSV，**2条数据记录**，表头为第1条记录：

```csv
step,samples
1,12
2,18
```

POST /charts/csv：multipart file=synthetic.csv、value_columns='["samples"]'、chart_type=bar，HTTP200返回原样7字段ChartOutput v1.1：series=[{name:samples,values:[12,18]}]，caption=`CSV values: 12, 18.`。图注12回溯到第2条CSV记录/samples，18到第3条/samples；csv_ref为原始字节哈希 **csv-d957fad585105ca7c817ce4ae5f69dc4147ef0e6bf612833705a9f2e68833af5**。两项verified均为true；不同单元格即使数值相同也各保留一项检查。

Matplotlib **3.11.2 / Agg**实际渲染PNG，image_ref为data:image/png;base64 URI；实际图片保存在本地被忽略的data/module-six-final-release/chart.png并目视检查。柱高12与18、横轴CSV记录2与3，轴标签/图例可读，没有不存在的图片路径，也未新增下载端点。完整响应含实际PNG字节在smoke JSON，可独立解码；本接口不持久保存用户原CSV，上传者保留原文件用于哈希/单元格复核。

图注默认枚举前最多6个所选源单元格，自定义也只接受 `CSV values: 十进制或科学计数值, 数值.` 的受限语法。无原始数值依据的差值、均值、数量叙述、自由中英文图注和百分比单位都拒绝，不靠漏识中文数字通过校验。CSV数值有限且须能无损转为float；不自动换算单位、补缺失或静默舍入。

CSV约束：UTF-8/BOM、≤1MiB、1–1000条数据记录、1–20个唯一非空表头、无首尾空白列名、整齐记录。line/bar可选1–10数值列，支持独立数值横轴；scatter须独立x列+一个y列，histogram仅一列且分箱min(10,数据行数)。分类横轴未实现，不宣称任意CSV可画。实际CSV读取使用Python csv与Decimal进行明确检查，未声称pandas进行了数据清洗。

非法CSV `broken`，HTTP422原文：

```json
{"error_code":"CSV_INVALID","message":"CSV须含表头与1–1000条数据记录。","details":null}
```

图注改为 `CSV values: 999.`，HTTP422原文：

```json
{"error_code":"CHART_VALIDATION_FAILED","message":"图注数字未回溯到所选源CSV单元格。","details":null}
```

两码均沿用既有v1.1枚举，错误固定三字段；没有改错误Schema或在错误体中塞业务记录。发布前重验ChartOutput Schema、原始系列、全部源单元格、verified、每个图注数字与实际PNG。图表独立返回，不塞QAAnswer.answer。

## 回归与复现

最终全量数字与JUnit在本节末尾由实际结果附入；包含原241项、本单55项新增，真实MinerU/PaddleOCR和既有CORS/同源代理回归均启用。独立HTTP实测6组（框架、默认草稿、缺证据草稿、图表、坏CSV、坏图注），19条端点计数与22份冻结文件均通过，论文输入文件的SHA-256在操作前后保持不变。

新增测试分组：FrameworkOutline契约2项、框架/归位/锚点9项、综述/缺证据/数字/篡改8项、CSV/四种图表/来源核验36项，共55项。开发中的超大CSV参数曾被自动展开成超长用例id并出现fixture错误；改显式短id后图表36项通过，不把那次错误计为全绿或声称应用错误已定位。随后首次全量295通过，补均匀引用循环测试与最终图像刻度后再次完整验证。

```powershell
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --basetemp data/module-six-final-test-temp --junitxml tests/reports/module-six-pytest.xml
backend/.venv/Scripts/python.exe tests/run_module_six_smoke.py --output-root data/module-six-reproduce --report data/module-six-reproduce.json
```

实跑要求使用尚不存在的data输出目录；不联网、不依赖Docker、真实GROBID、模型或Key。现有模块一/四旧实跑脚本只新增排除模块六端点/契约的明确范围过滤，保持各自历史10/16条端点和旧记录审计范围；没有减少旧pytest覆盖或修改旧报告。

backend/pyproject.toml固定新增matplotlib==3.11.2，pip check原文 `No broken requirements found.`。图像实现依据[Matplotlib官方CanvasAgg示例](https://matplotlib.org/stable/gallery/user_interfaces/canvasagg.html)。GROBID仍待验证，未改compose；模块二QA的原词法模式、模块四可选BGE/Chroma与模块五图谱保持原行为，本单不再调用真实Embedding或生成模型。

## 逐提交文件与协作交付

实现提交完整哈希和对应文件清单随后附表，并在audit JSON保留；报告自身的最终提交与git push原文由最终交付回报给出，避免自引用哈希。

交由用户转达WorkBuddy：按API草案新增FrameworkOutline、摘录草稿封装及ChartOutput data URI对接；不把unverifiable占位变成已验证论文事实，也不把extractive模式显示为模型生成。当前前端未修改、未验收接通。自由编辑框架、自由图注/分类横轴、成文导出及异步队列是明确未实现能力，不影响本单已定义请求范围的十九端点核验。

最终全量原文：

```text
296 passed in 138.00s (0:02:17)
```

[module-six-pytest.xml](module-six-pytest.xml)：296总数、296通过、0失败、0错误、0跳过。

| 完整提交哈希 | 事项 | 对应文件（相对D盘仓库） |
| --- | --- | --- |
| 312369adc3471d8293f7ed069bcb126b6f132c4f | 新增v1.2综述框架契约与逐层必填门禁且冻结原十一类记录 | backend/scholar_graph/validation.py<br>contracts/CONTRACTS.md<br>contracts/framework-outline.v1.2.example.json<br>contracts/framework-outline.v1.2.schema.json<br>tests/test_framework_contract.py |
| c9a47a7c8f71659983e97279f30d18b09182289f | 落地框架端点并复用图谱分层未来方向与推荐取证规则 | backend/scholar_graph/api.py<br>backend/scholar_graph/frameworks.py<br>backend/scholar_graph/writing_routes.py<br>tests/test_frameworks.py |
| da0c439627322c7ac5bfb995a9636302294feb5a | 落地摘录式综述端点并标注无证据要点及复用数字核验 | backend/scholar_graph/reviews.py<br>backend/scholar_graph/writing_routes.py<br>tests/test_reviews.py |
| e66761a5969259d8c045fa7dd7e7e4ac8ef1ca21 | 落地CSV图表端点与实际PNG及逐单元格图注校验 | backend/pyproject.toml<br>backend/scholar_graph/api.py<br>backend/scholar_graph/chart_routes.py<br>backend/scholar_graph/charts.py<br>tests/test_api_comparison.py<br>tests/test_charts.py |
| 89935882aae371626bbbb238be2092ef2a5126ca | 增加模块六HTTP与CSV实跑证据脚本并保留历史验收范围 | tests/run_module_four_smoke.py<br>tests/run_module_one_api_smoke.py<br>tests/run_module_six_smoke.py |
| 949feb55e4e0871028b898cf2200f6fa7f03d8eb | 修正CSV记录横轴为整数刻度并更新十九端点应用说明 | backend/scholar_graph/api.py<br>backend/scholar_graph/charts.py |
| 60186878184e40130d8a3a414c1214df35073195 | 同步十九端点全部落地及综述框架摘录图表的真实限制 | backend/README.md<br>docs/api-draft-v1.md |
| 0835b6d19196f80d6b9bdac69c53b6039cd6bc0b | 验证均匀引用循环无基石时衍生论文仍有真实章节归位 | tests/test_frameworks.py |
