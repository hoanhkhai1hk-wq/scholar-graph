# 技术文档大纲与材料补录计划

建立日期：2026-10-24。维护方：WorkBuddy（前端、文档与跑测）。本文件**不写正文**，只回答每章「要补什么材料、材料从哪来、卡在谁身上」。

## 目录来源说明（请务必先读）

本单在动手前已做三处检索，均**未找到**总指挥《技术文档初稿 v1》的十二节原文：

1. 仓库内（`docs/`）只有 Codex 产出的 `api-draft-v1.md`，无技术文档初稿文件。
2. 历史对话检索（conversation_search）返回 0 条。
3. 磁盘检索（`D:/AI_Workspace`、`D:/AI输出`）无命中文件。

因此下表的十二节，是**依据仓库现有材料推定**的章节划分，推定依据为：`README.md` 的目录骨架、`contracts/CONTRACTS.md` 定义的五类记录、`docs/api-draft-v1.md` 登记的 16 个端点、本单在 `test-records/test-cases-checklist.md` 拆的比赛三用例、以及 `README.md` 开源组件声明中的 AGPL 隔离约定。

**请总指挥用正式目录校对或替换。** 校对结果有两种可能：章节增删／改名，或仅顺序调整。若章节标题变更，本文件重写；若仅顺序调整，本文件的「材料来源」与「依赖」两栏仍可直接沿用。此说明与推定的章节标题本身，都不代表行进中的正文内容已被确认。

---

## 十二节材料补录表

### 第 1 节　项目概述与创新点

| 项 | 内容 |
| --- | --- |
| 要补什么材料 | 项目一句话定义与三到五条创新点；与常见 PDF 阅览／问答工具的差异化说明；比赛命题对应情况（三个用例分别落在哪个能力上） |
| 材料来源 | `README.md`（已有项目定位，可引用不可照扩）；`test-records/test-cases-checklist.md`（三用例，用于反查能力覆盖）；总指挥提供的比赛命题原文（**用户待转达**） |
| 依赖关系 | 依赖总指挥提供比赛命题原文与评分口径；不依赖 Codex 代码 |

### 第 2 节　系统总体架构与技术选型

| 项 | 内容 |
| --- | --- |
| 要补什么材料 | 模块边界图、请求流转路径、三服务（frontend / backend / grobid）职责与往来方式；选型对照（为什么选 MinerU 而非 Docling 等） |
| 材料来源 | `docker-compose.yml`（三服务占位，已有）；`README.md`「协作边界」小节；`docs/open-source-register.md`（本单产出，选型清单与用途）；Codex 后端实现单（**待其交付后回填真实模块边界**） |
| 依赖关系 | 依赖 Codex 交付后端模块划分与实际服务边界；依赖总指挥确认 AGPL 组件隔离形态是否被架构图体现；README 中「架构图占位」标注 TODO，本单不代画 |

### 第 3 节　数据契约与 API 接口设计

| 项 | 内容 |
| --- | --- |
| 要补什么材料 | 五类记录字段表、跨记录约束、16 个端点的输入输出、四处待裁定缺口的裁定结果 |
| 材料来源 | `contracts/CONTRACTS.md`（已入库，可直接引用节次与字段表）；五份 `*.v1.schema.json` 与五份 `*.v1.example.json`；`docs/api-draft-v1.md`（Codex 产出，端点清单已备） |
| 依赖关系 | 依赖 Codex；缺口 A/B/C（去重规则、版本差异摘要结构、解析状态响应结构）依赖总指挥裁定，记录见 `test-records/test-cases-checklist.md` 附录。未裁定前本章只能写「已定义」与「待裁定」两态，不得自行补结构 |

### 第 4 节　PDF 解析管线（文本层判定、分块、OCR 分支）

| 项 | 内容 |
| --- | --- |
| 要补什么材料 | 解析流程图；文本层判定算法与阈值；分块策略（页为单位、跨页拆分的实际行为）；表格／图片／公式的文本化表示规则；OCR 触发条件与后置校验 |
| 材料来源 | Codex 解析管线实现单（**待交付**）；`contracts/CONTRACTS.md` 中 `Chunk` 的类型枚举与 bbox 归一化口径（已有）；`test-records/test-cases-checklist.md` 用例二（跑测后可引 OCR 耗时与准确率数据） |
| 依赖关系 | 依赖 Codex 实现细节；依赖用例二跑测产出 `case2-parse-timing.log`、`case2-ocr-accuracy.md`；OCR 组件选型的合规说明来自 `docs/open-source-register.md` |

### 第 5 节　版本去重与版本差异感知

| 项 | 内容 |
| --- | --- |
| 要补什么材料 | 重合判定算法、相似度阈值、保留策略的人工否决机制、版本差异摘要的生成方式 |
| 材料来源 | `test-records/test-cases-checklist.md` 用例一（预警截图、差异文本、比对记录）；Codex 去重实现单（**待交付**） |
| 依赖关系 | **强阻断点**：依赖总指挥对缺口 A、B 的裁定。契约 v1 明确「不定义去重业务规则」，在裁定前本章无正文可写，只能写未决事项清单 |

### 第 6 节　参考文献解析与双向引用跳转

| 项 | 内容 |
| --- | --- |
| 要补什么材料 | GROBID 接入方式、条目抽取与编号规则、正文引用标记解析、正文↔文末双向跳转的实现与前端交互 |
| 材料来源 | `contracts/CONTRACTS.md` 中 `ReferenceEntry` 与 `CitationLink` 的唯一键与一致性要求（已有）；`docs/api-draft-v1.md` 中 `GET /papers/{paper_id}/references` 与 `/citation-links`；用例二第 9 步跳转留证 `case2-citation-jump.png` |
| 依赖关系 | 依赖 Codex 解析与后端；依赖跑测用例二验证 OCR 场景下的跳转可用性；Compose 中 grobid 镜像占位写法参考 README 所述官方快速开始 |

### 第 7 节　知识图谱构建与可视化

| 项 | 内容 |
| --- | --- |
| 要补什么材料 | 节点与边的定义、构建流程、规模上限、前端 Cytoscape.js 布局与交互、Mermaid 图示的适用场景 |
| 材料来源 | `docs/api-draft-v1.md` 中 `GET /graph`（已登记为「原始数据引用三类契约，专用节点/边格式待裁定」）；Codex 图谱实现单（**待交付**）；WorkBuddy 前端可视化单（后续） |
| 依赖关系 | 依赖总指挥裁定图谱专用结构；依赖 Codex 图构建；依赖 WorkBuddy 前端-Cytoscape.js / Mermaid 集成 |

### 第 8 节　检索增强问答与数字事实校验

| 项 | 内容 |
| --- | --- |
| 要补什么材料 | 检索与召回策略、证据注入方式、拒答策略、数字事实校验的三态判定与汇总规则、典型的 passed/failed/unverifiable 实例 |
| 材料来源 | `contracts/CONTRACTS.md` 中 `QAAnswer` 的 anchors 四字段与 `numeric_fact_check` 状态汇总规则（已有）；`contracts/qa-answer.v1.example.json`（示例为合成数据，只能用于说明格式）；用例二第 7、8 步产出 `case2-qa-answer.json` |
| 依赖关系 | 依赖 Codex；依赖 DeepSeek Harness 的 Prompt 实验产出（`prompts/prompt-chain-template.md` 归档的结论，本单已建账表）；注意契约明确「示例中的通过仅为合成数据示意」，不得当作实测证据引用 |

### 第 9 节　综述、推荐与框架生成的 Agent 编排

| 项 | 内容 |
| --- | --- |
| 要补什么材料 | LangGraph 流程图、各节点的 Prompt 出处与版本、失败重试与人工兜底、生成结果如何携带论文锚点 |
| 材料来源 | `docs/api-draft-v1.md` 中 `POST /reviews`、`GET /recommendations`、`POST /frameworks`（三者均含「待裁定」标注）；`prompts/prompt-chain-template.md`（本单产出，每条 core 功能的 Prompt 链） |
| 依赖关系 | 依赖 Codex 编排实现；依赖 DeepSeek Harness 提供真实 Prompt 实验链（当前归档表为空）；依赖总指挥裁定综述结构与推荐中「分数、理由」字段是否允许存在 |

### 第 10 节　前端应用与阅读交互实现

| 项 | 内容 |
| --- | --- |
| 要补什么材料 | 页面结构与技术栈、pdf.js 渲染与锚点定位、目录分级加载、懒渲染策略、CSV 图表上传入口 |
| 材料来源 | 用例三全部留证（`case3-env-base.md`、`case3-progress.csv`、`case3-memory.png`、`case3-frontend-first-paint.json`、`case3-frontend-scroll.json`、`case3-multitab.png`）；`frontend/`（WorkBuddy 产出，**尚未开工**） |
| 依赖关系 | 依赖 WorkBuddy 自身后续前端单；依赖用例三跑测完成才有性能数据；依赖总指挥裁定 CSV 图表输出结构（契约未覆盖） |

### 第 11 节　测试与验证

| 项 | 内容 |
| --- | --- |
| 要补什么材料 | 三用例的完整实测记录（必须是填充后的结果，不是空表）、性能数据表、已知缺陷清单、未能验证项与原因 |
| 材料来源 | `test-records/test-cases-checklist.md`（本单产出，含三个用例的实测结果栏与留证物清单）；三个用例的实际留证物目录 |
| 依赖关系 | 依赖 Codex 后端可用；依赖缺口 A/B/C 裁定；依赖三个 PDF 就位与哈希登记。**在实测结果栏为空之前，本章不得出现任何通过性表述** |

### 第 12 节　开源组件合规、部署与结果复现

| 项 | 内容 |
| --- | --- |
| 要补什么材料 | 组件清单与实际版本号、许可证原文链接与版权声明、AGPL 组件的隔离边界说明、安装与启动步骤、复现验证的最低环境要求 |
| 材料来源 | `docs/open-source-register.md`（本单产出，16 个组件的协议与调用方式）；`README.md` 开源组件声明与 `.env.example`；`docker-compose.yml`；各组件仓库 LICENSE 文件（本单已逐个核对，证据路径见登记表备注） |
| 依赖关系 | 依赖总指挥确认 AGPL 隔离的具体形态（独立服务／独立进程的边界画法）；依赖 Codex 实际接入后回填真实版本号；README 中「复现指南占位」标注 TODO，本单不替写安装步骤 |

---

## 材料到位跟踪表

跑测与 upstream 交付到位后由执行人逐格回填，反映本章何时可以动笔。

| 节 | 材料是否齐备 | 可开始撰写日期 | 阻塞项 | 实际成稿日期 |
| --- | --- | --- | --- | --- |
| 1 | 否 |  | 等待比赛命题原文 |  |
| 2 | 否 |  | 等待 Codex 模块边界 |  |
| 3 | 否 |  | 等待缺口 A/B/C 裁定 |  |
| 4 | 否 |  | 等待 Codex 管线实现与用例二跑测 |  |
| 5 | 否 |  | 等待缺口 A/B 裁定 |  |
| 6 | 否 |  | 等待 Codex 实现与用例二跳转留证 |  |
| 7 | 否 |  | 等待图谱结构裁定与前端集成 |  |
| 8 | 否 |  | 等待 Prompt 实验归档与用例二问答留证 |  |
| 9 | 否 |  | 等待编排实现与 Prompt 链归档 |  |
| 10 | 否 |  | 等待前端开工与用例三跑测 |  |
| 11 | 否 |  | 等待三用例实测完成 |  |
| 12 | 否 |  | 等待实际版本号与隔离边界确认 |  |
