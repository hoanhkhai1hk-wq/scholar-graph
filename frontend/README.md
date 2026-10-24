# frontend — ScholarGraph（研枢）前端说明

建立日期：2026-10-24。维护方：WorkBuddy（前端主力）。本目录为**演示假数据壳**，不接后端、不含任何真实业务能力。

## 0. 本单范围与红线

- 只写 `frontend/` 下的文件。不碰 `backend/`、`contracts/`、`services/`、`docker-compose.yml`、`Dockerfile`、`tests/`、`experiments/`。
- 假数据全部来自 `contracts/` 下 v1 与 v1.1 九份记录的 example，**字段与契约一一对应，不新增、不改名、不臆造字段**。
- 页面顶部明标「演示假数据，未接后端」。
- 本单不产生任何「已验证」「测试通过」表述，不修改 `test-records/`，不把任何用例标为通过。
- 图表图片位只用占位框，不贴假造的实测图。

## 1. 开源 UI skill / 设计系统调研

### 1.1 调研方法

三条做法保证数据不是凭印象：

1. 候选的 star 数、最近更新时间，均通过 GitHub REST API 现场拉取（**核实当天：2026-10-24**）。
2. 协议不看包管理器元数据、不看徽章，**一律直读仓库 LICENSE 文件原文**后认定。
3. 组件与 token 体系的描述，取自仓库 README 的原文表述，不转述加工。

### 1.2 对比表（3 个候选）

| 候选 | 仓库地址 | star 数（2026-10-24 核实） | 最近更新 | 协议 | 组件与 token 体系 |
| --- | --- | ---: | --- | --- | --- |
| UI UX Pro Max（首选参照） | https://github.com/nextlevelbuilder/ui-ux-pro-max-skill | 139,625 | 2026-10-23 | MIT（LICENSE 原文：Copyright (c) 2024 Next Level Builder） | 79 种可检索 UI 风格（50 个启用）、192 套行业配色、74 组字体搭配、25 种图表类型、119 条 UX 准则、192 条行业推理规则；以「推理规则」驱动设计系统生成 |
| Carbon Design System（IBM） | https://github.com/carbon-design-system/carbon | 9,576 | 2026-10-23 | Apache-2.0 | 完整分层 token 体系（color / type / spacing / motion），IBM Plex 字体族，面向数据密集型后台（data table、tag、structured list） |
| Radix Primitives | https://github.com/radix-ui/primitives | 19,420 | 2026-10-14 | MIT（LICENSE 原文：Copyright (c) 2022 WorkOS） | 无样式（unstyled）可访问性原语，**不提供任何配色 token**，行为与视觉分离 |

### 1.3 逐个候选：借鉴什么、不借鉴什么

**候选一　UI UX Pro Max**

- 借鉴：① 图表类型与信息密度的匹配方法（其 25 种图表类型的适用场景）；② 字体搭配的取法（衬线正文与无衬线界面的分工方式）；③ 排版节奏类准则（紧凑标签、可取消交互、抗变形文本布局）。以上**只取方法论**。
- 不借鉴：① 其任何默认配色（多为 SaaS 企业蓝与 AI 紫系）；② 其成品组件代码（避免协议与署名复杂度）；③ 其「AI 自动生成设计系统」的黑箱流程——本单配色由我方自拟、对总指挥负责。

**候选二　Carbon Design System（IBM）**

- 借鉴：① token 分层命名方法（语义角色 → 主题 → 具体值）；② 数据表格、标签、结构化列表的**信息布局方式**（行高、对齐、状态色用法）；③ 排版尺度的制定方法。
- 不借鉴：① IBM Plex 默认字体与 IBM 品牌蓝（`#0F62FE`）；② 其 React 组件实现代码（本单只搭壳，不引入组件库）；③ IBM 专属的网格与品牌规范。

**候选三　Radix Primitives**

- 借鉴：①「行为与视觉分离」的组件拆分方法——壳只写结构与状态，视觉全部交给自定 token；② 可访问性基线（键盘可达、焦点管理）作为后续组件的验收项。
- 不借鉴：① 不引入其运行时依赖（本单零 UI 依赖，保持壳轻量）；② 其示例主题配色。

### 1.4 最终推荐

**推荐以 UI UX Pro Max 为主要参照（方法论层面），token 结构按 Carbon 的分层法落地，组件验收口径参考 Radix 的可访问性基线。**

理由：

1. 本项目是**学术研究工具、数据密集、以阅读为主**，UI UX Pro Max 的图表选型与排版准则最直接对应「信息怎么摆、字怎么读」这一类问题，而它自带的配色恰恰是我们要避开的——方法论能摘，配色不能摘，这个取舍在它身上最干净。
2. Carbon 的 star 数（9,576）是三者最低，但它的价值不在组件而在**token 分层命名**。本单要自建一套配色 token，且要求「总指挥确认或驳回后，下一单只改 token 不重建」——只有先分层，才谈得上只改一层。这是选它的决定性理由。
3. Radix 不提供配色 token，正好与配色红线不冲突；引入它只增加依赖，因此**只取其可访问性基线作为验收项，不取代码**。
4. 三者均为 MIT 或 Apache-2.0，协议允许复用思路，且本单不复制任何组件源码，署名义务降到最低。

### 1.5 协议红线执行结果

| 项 | 结果 |
| --- | --- |
| 只借鉴 MIT / Apache-2.0 等允许复用的开源设计 | 三个候选分别为 MIT、Apache-2.0、MIT，全部合规 |
| 抄来的组件按协议要求署名 | **本单未复制任何组件源码**，因此无组件级署名义务；参照来源已在上表逐条写明仓库地址与版权行 |
| 协议不明或不允许复用时只借鉴思路并写明 | 未出现协议不明项；UI UX Pro Max 存在「Basic／Premium」版本区分，本单**仅参照其开源 Basic 仓库，未使用任何 Premium 内容** |
| 不套用默认企业蓝配色 | 已遵守，配色全部自拟，见第 2 节 |

---

## 2. 拟议配色 token（待总指挥确认）

> **本套 token 为 provisional（拟议中）。** 壳已按它搭建，但它尚未获总指挥确认。若总指挥确认或驳回，**下一单只改本节的 token 值，不重建页面结构**。

### 2.1 设计定位

学术研究工具：冷静、可读、数据密集。取「纸本＋墨水」的意象——暖白底、近墨黑字、深松绿作主色、赭石作强调，避免科技感的企业蓝与紫蓝渐变。

### 2.2 主色与背景

| 类别 | Token | 拟议值 | 用途 |
| --- | --- | --- | --- |
| 背景 | `--sg-bg-canvas` | `#F7F6F3` | 页面底色（暖白纸感） |
| 背景 | `--sg-bg-surface` | `#FFFFFF` | 卡片／面板底色 |
| 背景 | `--sg-bg-subtle` | `#F0EEE9` | 表头、代码块、次级区块 |
| 背景 | `--sg-bg-inverse` | `#1B1B19` | 反色区块（演示横幅） |
| 主色 | `--sg-primary` | `#14544B` | 主按钮、选中态、链接 |
| 主色 | `--sg-primary-hover` | `#0E3F38` | 主色悬浮／按下 |
| 主色 | `--sg-primary-subtle` | `#E4EDEA` | 主色浅底（标签、选中背景） |

### 2.3 文字

| 类别 | Token | 拟议值 | 用途 |
| --- | --- | --- | --- |
| 文字 | `--sg-text-primary` | `#1B1B19` | 正文与标题 |
| 文字 | `--sg-text-secondary` | `#5A5851` | 次级说明、表头 |
| 文字 | `--sg-text-muted` | `#8A877E` | 占位符、辅助信息 |
| 文字 | `--sg-text-inverse` | `#F7F6F3` | 反色区块上的文字 |
| 文字 | `--sg-text-link` | `#14544B` | 正文链接（与主色同） |

### 2.4 强调与状态

| 类别 | Token | 拟议值 | 用途 |
| --- | --- | --- | --- |
| 强调 | `--sg-accent` | `#B4551D` | 锚点高亮、关键句、重点数字 |
| 强调 | `--sg-accent-subtle` | `#F6E9DF` | 锚点高亮底色 |
| 成功 | `--sg-success` | `#2E6B4F` | 校验通过、解析完成 |
| 成功 | `--sg-success-subtle` | `#E6EFE9` | 成功标签底色 |
| 失败 | `--sg-error` | `#A32B1E` | 解析失败、校验矛盾 |
| 失败 | `--sg-error-subtle` | `#F7E6E3` | 失败标签底色 |
| 警告 | `--sg-warning` | `#8A5D0E` | 需人工复核、不可验证 |
| 警告 | `--sg-warning-subtle` | `#F6EEDC` | 警告标签底色 |

状态色一律配 `-subtle` 浅底做标签底色，用**左侧色条＋文字**表达状态，不用整块彩色卡片。

### 2.5 边框与形状

| 类别 | Token | 拟议值 | 用途 |
| --- | --- | --- | --- |
| 边框 | `--sg-border` | `#DDD9D1` | 常规分隔线、卡片描边 |
| 边框 | `--sg-border-strong` | `#C4BFB4` | 强调分隔、表头下边线 |
| 圆角 | `--sg-radius-sm` | `2px` | 标签、按钮 |
| 圆角 | `--sg-radius-md` | `3px` | 卡片、代码块 |
| 阴影 | `--sg-shadow` | `0 1px 0 rgba(27,27,25,.04)` | 仅在必需时；默认靠 1px 边框分层，不用阴影堆卡片 |

### 2.6 数据可视化色板（分类色，低饱和）

`--sg-chart-1` `#14544B` ／ `--sg-chart-2` `#B4551D` ／ `--sg-chart-3` `#3C6E8F` ／ `--sg-chart-4` `#7A6A2E` ／ `--sg-chart-5` `#6B4E71` ／ `--sg-chart-6` `#4C7A5A`

图表占位区按此顺序取色；本单不出图，只用占位框。

### 2.7 字体方案

| 用途 | 字体栈 |
| --- | --- |
| 界面与表格（数据密集处） | `Inter, "Segoe UI", system-ui, -apple-system, "Helvetica Neue", sans-serif` |
| 论文正文内容区 | `"Source Serif 4", "Iowan Old Style", Georgia, "Times New Roman", serif` |
| 标识符（id、DOI、哈希、页码角标） | `"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace` |

正文行高 1.6，界面行高 1.45；表格行高按 36px 基准；正文基准 15px，辅助文本 13px。字体通过 Google Fonts 引入，系统字体完整兜底，**离线环境不阻塞构建与运行**。

### 2.8 明令禁止

- 不套用任何 skill 的默认企业蓝配色（含 Carbon 的 `#0F62FE`）。
- 不用紫蓝渐变。
- 不用大面积圆角＋阴影卡片堆版式；用 1px 边框与留白分层。
- 不用 emoji 当图标；图标一律用内联 SVG 或纯文字标记。

---

## 3. 目录结构

```text
frontend/
  README.md              本文件：调研结论、拟议配色 token、运行说明
  package.json           依赖与脚本
  next.config.mjs        Next.js 配置
  tsconfig.json          TypeScript 配置
  .gitignore             忽略 .next/ 与 node_modules/
  app/
    layout.tsx           根布局，引入全局样式与演示横幅
    globals.css          拟议配色 token 与基础排版
    page.tsx             论文列表页
    papers/[id]/page.tsx 论文详情页（解析状态、分块、引用、问答、去重、图表占位）
  components/
    DemoBanner.tsx       「演示假数据，未接后端」横幅
  mock/
    *.mock.ts            与契约 example 字段一一对应的假数据
    index.ts             汇总导出
```

## 4. 本地运行

在本目录（`D:\AI_Workspace\Tasks\scholar-graph\frontend`）执行：

```bash
npm install          # 安装依赖
npm run dev          # 启动开发服务器，默认 http://localhost:3000
npm run build        # 生产构建
npm run start        # 启动生产服务（需先 build），端口 3000
```

自定义端口：`npm run dev -- -p 3100`。

## 5. 假数据说明

`mock/` 下每个文件头部均标注 `MOCK DATA`，说明对应哪一份契约 example。页面只渲染与契约字段一致的数据；**任何字段对不上契约的内容不上页面**。这些数据由契约合成示例得来，不是真实论文，也不是后端实跑产物。后端已真实跑通的记录格式见 `tests/reports/module-one-report.md`，壳的数据结构按它对齐，但壳当前不消费其数据。
