# ScholarGraph（研枢）

科研助手 Agent 系统：面向论文 PDF 的解析、问答、图谱、综述与写作辅助的全栈 Web 应用。

当前仅完成仓库骨架、五份数据契约与 API 草案；没有业务实现、解析调用、模型调用、页面或可启动应用。仓库名：`scholar-graph`；后续 Python 包名：`scholar_graph`。所有路径和文件名使用英文。

## 架构图占位

TODO：按总指挥验收的模块边界补充架构图。

## 目录骨架

```text
backend/       后端预留；只有占位 README
frontend/      WorkBuddy 前端区域；本单仅建立空目录
contracts/     五份 JSON Schema、五份合成示例与中文说明
services/      服务集成预留；只有占位 README
docs/          本单只有 api-draft-v1.md，其他文档归 WorkBuddy
prompts/       DeepSeek Harness 区域；本单仅建立空目录
experiments/   实验区域；本单仅建立空目录
test-records/  跑测记录区域；本单仅建立空目录
fixtures/      测试样本预留；只有占位 README，PDF 被忽略
```

Git 不保存空目录。为遵守分工，本单不向 frontend、prompts、experiments、test-records 写入 README 或 .gitkeep；克隆后可在仓库根目录用 PowerShell 恢复这些空目录：

```powershell
'frontend', 'prompts', 'experiments', 'test-records' | ForEach-Object {
    New-Item -ItemType Directory -Path $_ -Force | Out-Null
}
```

数据契约入口：[contracts/CONTRACTS.md](contracts/CONTRACTS.md)。API 清单：[docs/api-draft-v1.md](docs/api-draft-v1.md)。未被现有五份契约覆盖的数据结构在 API 草案中明确登记，不能由后续模块自行补充。

## 协作边界

总指挥（威龙）负责拆单与验收，用户负责工具间中转。Codex 为主力开发，本单仅建立骨架与契约；WorkBuddy 负责前端、文档和跑测；DeepSeek Harness 负责 Prompt 实验。工具不直接沟通，不越单补做其他工具的工作。数据契约的任何字段或语义变更必须先交总指挥裁定，再升版本并记录变更。

## 开源组件声明

以下为已定选型清单，本单未安装、接入、验证或打包这些组件；不表示相应能力已经实现。

| 组件 | 规划用途 |
| --- | --- |
| MinerU、GROBID、Docling | 文档解析与结构提取 |
| DeepSeek-OCR、PaddleOCR | OCR 识别 |
| PaperQA2、LightRAG、LlamaIndex | 论文问答、检索与知识组织 |
| LangGraph | Agent 流程编排 |
| pdf.js | PDF 浏览 |
| Cytoscape.js、Mermaid | 图谱与图示展示 |
| pandas、Matplotlib | 表格数据与图表 |

PyMuPDF 与 PDFMathTranslate 按本项目约定作为 AGPL 组件隔离使用，规划采用独立服务或独立进程边界，本单未接入。TODO：在后续文档单中补充组件实际版本、许可证原文链接、版权声明和隔离边界说明；此处不等于许可证核验完成。

GROBID 在 Compose 中使用官方仓库名 `grobid/grobid` 作为占位，镜像写法参考 [GROBID 官方快速开始](https://grobid.readthedocs.io/en/latest/getting_started/)。镜像版本、变体与摘要仍标 TODO，未下载或启动镜像。

## 复现指南占位

TODO：业务实现后补充依赖版本、安装、数据准备、启动、验证与结果复现步骤。

- `.env.example` 只有变量名，没有真实值；环境值的配置方式在后续实施单确定。不要提交 `.env`、API 密钥、真实 PDF 或本地数据。
- `docker-compose.yml` 仅定义 frontend、backend、grobid 三个占位服务，全部放在 `scaffold` profile。前后端镜像尚不存在，无 Dockerfile、构建上下文或启动实现；不应据此宣称应用可运行。
- 结构验证可使用 `docker compose --profile scaffold config`；无 Docker 时只能对 YAML 语法及占位结构做自查，不能替代 Compose 官方校验或服务运行验证。
- 合成示例只用于契约格式，不是真实论文、实验或功能演示。`.gitignore` 排除 `.env`、`data/`、PDF、node_modules 与 Python 缓存，fixtures 目录只跟踪占位说明。
