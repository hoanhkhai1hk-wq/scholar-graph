# 开源组件登记表

建立日期：2026-10-24。维护方：WorkBuddy（前端、文档与跑测）。本表登记本项目已定选型的开源组件及其许可证核验结果。

## 主表

| 名称 | 仓库地址 | 协议 | 用途 | 自研／调用方式 |
| --- | --- | --- | --- | --- |
| MinerU | https://github.com/opendatalab/MinerU | Apache-2.0 + MinerU 附加条款（已核） | 文档解析与结构提取 | 调用；接入形态待 Codex 确定 |
| GROBID | https://github.com/grobidOrg/grobid | Apache-2.0（已核） | 参考文献抽取与结构化 | 调用；按 `docker-compose.yml` 独立服务部署 |
| DeepSeek-OCR | https://github.com/deepseek-ai/DeepSeek-OCR | MIT（已核） | OCR 识别（主力） | 调用；独立推理服务或独立进程 |
| PaddleOCR | https://github.com/PaddlePaddle/PaddleOCR | Apache-2.0（已核） | OCR 识别（备选／补充） | 调用；独立进程 |
| Docling | https://github.com/docling-project/docling | MIT（已核） | 文档解析备选方案 | 调用；当前未启用 |
| PaperQA2 | https://github.com/Future-House/paper-qa | Apache-2.0（已核） | 论文问答与证据链 | 调用 |
| LightRAG | https://github.com/HKUDS/LightRAG | MIT（已核） | 知识组织与图检索 | 调用 |
| LlamaIndex | https://github.com/run-llama/llama_index | MIT（已核） | 检索索引与编排支撑 | 调用 |
| LangGraph | https://github.com/langchain-ai/langgraph | MIT（已核） | Agent 流程编排 | 调用 |
| pdf.js | https://github.com/mozilla/pdf.js | Apache-2.0（已核） | PDF 浏览器渲染 | 调用；前端依赖 |
| Cytoscape.js | https://github.com/cytoscape/cytoscape.js | MIT（已核） | 知识图谱可视化 | 调用；前端依赖 |
| Mermaid | https://github.com/mermaid-js/mermaid | MIT（已核） | 图示与流程渲染 | 调用；前端依赖 |
| pandas | https://github.com/pandas-dev/pandas | BSD-3-Clause（已核） | CSV 表格数据处理 | 调用 |
| Matplotlib | https://github.com/matplotlib/matplotlib | Matplotlib 自有许可协议（BSD 风格 License Agreement，已核） | CSV 图表绘制 | 调用 |
| PyMuPDF | https://github.com/pymupdf/PyMuPDF | AGPL-3.0（已核） | PDF 读取与文本层判定 | 调用；按项目约定作 AGPL 隔离，隔离形态待总指挥确认 |
| PDFMathTranslate | https://github.com/Byaidu/PDFMathTranslate | AGPL-3.0（已核） | 公式友好翻译 | 调用；按项目约定作 AGPL 隔离，隔离形态待总指挥确认 |

## 核验方法与口径

1. 协议以**各仓库 LICENSE 文件的实际内容**为准，不看包管理器的元数据字段，不看第三方许可证速查表，不看组件官网的广告式描述。
2. 核查日期统一为 2026-10-24，取内容为仓库默认分支（`HEAD`）下的许可证文件。
3. 「已核」表示已读过该文件的许可证正文并据此认定协议名称；「待核」表示未能取得该文件的许可证正文，本表不允许对「待核」项填任何协议猜测。
4. 本次核验**只覆盖组件自身的许可证**，不覆盖其传递依赖（例如各 Python 包的子依赖）的许可证。该部分需要在安装后另做一轮清单核验，属于后续单，不在本单范围内。
5. 组件实际版本号、许可证原文链接、版权声明全文、AGPL 隔离边界说明，在 `README.md` 中标注为 TODO，不在本表格口径内，需后续单补齐。

## 逐条核验证据

| 名称 | 许可证文件路径 | 核对日期 | 协议结论 | 状态 |
| --- | --- | --- | --- | --- |
| MinerU | `HEAD/LICENSE.md` | 2026-10-24 | Apache-2.0 并附 MinerU 开源许可附加条款 | 已核 |
| GROBID | `HEAD/LICENSE` | 2026-10-24 | Apache License 2.0 | 已核 |
| DeepSeek-OCR | `HEAD/LICENSE` | 2026-10-24 | MIT License | 已核 |
| PaddleOCR | `HEAD/LICENSE` | 2026-10-24 | Apache License 2.0 | 已核 |
| Docling | `HEAD/LICENSE` | 2026-10-24 | MIT License | 已核 |
| PaperQA2 | `HEAD/LICENSE` | 2026-10-24 | Apache License 2.0 | 已核 |
| LightRAG | `HEAD/LICENSE` | 2026-10-24 | MIT License | 已核 |
| LlamaIndex | `HEAD/LICENSE` | 2026-10-24 | The MIT License | 已核 |
| LangGraph | `HEAD/LICENSE` | 2026-10-24 | MIT License | 已核 |
| pdf.js | `HEAD/LICENSE` | 2026-10-24 | Apache License 2.0 | 已核 |
| Cytoscape.js | `HEAD/LICENSE` | 2026-10-24 | MIT（版权行 The Cytoscape Consortium） | 已核 |
| Mermaid | `HEAD/LICENSE` | 2026-10-24 | The MIT License (MIT) | 已核 |
| pandas | `HEAD/LICENSE` | 2026-10-24 | BSD 3-Clause License | 已核 |
| Matplotlib | `HEAD/LICENSE/LICENSE` | 2026-10-24 | Matplotlib 自有 License Agreement（BSD 风格） | 已核 |
| PyMuPDF | `HEAD/COPYING` | 2026-10-24 | GNU AGPL v3 | 已核 |
| PDFMathTranslate | `HEAD/LICENSE` | 2026-10-24 | GNU AGPL v3 | 已核 |

## 三条必须留意的备注

**MinerU 不是纯 Apache-2.0。** 其 `LICENSE.md` 在 Apache-2.0 之上附加了三类条款：（a）MAU 超过 1 亿或月收入超过 2000 万美元时须单独取得商业许可；（b）基于 MinerU 向第三方提供在线服务时，必须在产品界面或公开文档中显著标明使用了 MinerU；（c）违反上述两项时许可自动终止。这意味着**额外署名义务**，与 `README.md` 里笼统的写作不同。实施时必须落实署名条款，不能只写「Apache-2.0」。

**Matplotlib 用的不是标准 SPDX 协议名。** 其许可证是 Matplotlib 开发团队自拟的 License Agreement（BSD 风格，适用于 1.3.0 及以后版本），要求保留版权声明与许可声明、衍生作品须说明改动摘要。填写正式合规清单时不能简单写成 BSD-3-Clause。**本次核验到的是协议正文，SPDX 标识符一项标注为待核**，待其官方明示后回填，本单不猜填。

**GROBID 仓库地址已迁移。** GitHub API 显示旧址 `kermitt2/grobid` 已重定向至 `grobidOrg/grobid`。本表已登记新址。注意 `docker-compose.yml` 中占位镜像写作 `grobid/grobid`（Docker Hub 镜像名），与 GitHub 组织名不一致，两者不是同一回事，实施时不要混用。

## 待办与缺口

| # | 待办项 | 责任人 | 阻塞依赖 |
| --- | --- | --- | --- |
| 1 | 各组件实际版本号回填 | Codex（接入时） | 后端／前端依赖安装完成 |
| 2 | 许可证原文链接与版权声明全文补齐 | WorkBuddy 后续单 | 无 |
| 3 | AGPL 组件（PyMuPDF、PDFMathTranslate）隔离边界的具体画法确认 | 总指挥裁定 | `README.md` 已声明「独立服务或独立进程边界」，未定义具体实现形态 |
| 4 | 传递依赖许可证清单核验 | 后续单 | 依赖安装与 `pip list`／`npm ls` 产出 |
| 5 | MinerU 在线服务署名义务的落地位置（界面还是文档） | 总指挥裁定 | 用途是否为在线服务 |

## 统计

| 状态 | 条数 |
| --- | --- |
| 协议已核（已读 LICENSE 正文并认定） | 16 |
| 协议待核（未取得 LICENSE 正文） | 0 |
| SPDX 标识符待核（协议正文已核，标准 ID 未明示） | 1（Matplotlib） |

更新统计时同步更新时间戳：

| 项目 | 值 |
| --- | --- |
| 最近一次统一核验日期 | 2026-10-24 |
| 核验人 | WorkBuddy |
