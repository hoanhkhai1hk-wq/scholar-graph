---
name: "研枢 ScholarGraph · 青瓷书页"
description: "雾青外框、实体白纸与一层缓慢流动的悬浮玻璃，服务中文科研操作与长时间阅读。"
colors:
  canvas: "#eaf1f0"
  paper: "#ffffff"
  annotation: "#eff5f2"
  ink: "#16342f"
  text-secondary: "#506a64"
  text-muted: "#586e68"
  primary: "#14766c"
  primary-hover: "#105e56"
  primary-subtle: "#e1efea"
  accent-subtle: "#e4f1ed"
  link: "#145e55"
  border: "#d8e4df"
  control-border: "#a8bdb6"
  button-hover: "#234b42"
  ghost-hover-border: "#7c9d90"
  disabled-surface: "#edf1ee"
  disabled-text: "#566b63"
  disabled-border: "#c7d5cd"
  error-text: "#752b20"
  error-surface: "#fcf0eb"
  destructive-text: "#912c20"
  destructive-border: "#d5b1a9"
  danger-hover-surface: "#fcebe6"
  danger-hover-border: "#b28b7c"
  success-text: "#245b42"
  success-surface: "#e9f4ec"
  error-tag-surface: "#f9ece7"
  warning-text: "#75540f"
  warning-surface: "#fbf3df"
  glass: "rgba(244,251,248,.85)"
  glass-border: "rgba(255,255,255,.86)"
  glass-solid: "#f8fcfa"
typography:
  headline:
    fontFamily: '"Segoe UI", "Microsoft YaHei", "PingFang SC", system-ui, sans-serif'
    fontSize: "28px"
    fontWeight: 650
    lineHeight: 1.4
    letterSpacing: "-.025em"
  title:
    fontFamily: '"Segoe UI", "Microsoft YaHei", "PingFang SC", system-ui, sans-serif'
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.5
  body:
    fontFamily: '"Segoe UI", "Microsoft YaHei", "PingFang SC", system-ui, sans-serif'
    fontSize: "15px"
    lineHeight: 1.65
  prose:
    fontFamily: '"Segoe UI", "Microsoft YaHei", "PingFang SC", system-ui, sans-serif'
    fontSize: "15px"
    lineHeight: 1.85
  label:
    fontFamily: '"Segoe UI", "Microsoft YaHei", "PingFang SC", system-ui, sans-serif'
    fontSize: "14px"
    fontWeight: 500
    lineHeight: 1.55
  metadata:
    fontFamily: '"Segoe UI", "Microsoft YaHei", "PingFang SC", system-ui, sans-serif'
    fontSize: "13px"
    lineHeight: 1.6
  preview-title:
    fontFamily: 'Georgia, "Times New Roman", "Songti SC", serif'
    fontSize: "23px"
    fontWeight: 500
    lineHeight: 1.5
  preview-body:
    fontFamily: 'Georgia, "Times New Roman", "Songti SC", serif'
    fontSize: "15px"
    lineHeight: 1.9
  code:
    fontFamily: '"Cascadia Code", Consolas, monospace'
    fontSize: "12px"
rounded:
  tag: "3px"
  control: "5px"
  surface: "8px"
  drawer: "16px"
  nav-mobile: "18px"
  nav: "22px"
spacing:
  "1": "4px"
  "2": "8px"
  "3": "12px"
  "4": "16px"
  "5": "24px"
  "6": "32px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "9px 17px"
  button-primary-hover:
    backgroundColor: "{colors.button-hover}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "9px 17px"
  button-secondary-hover:
    backgroundColor: "{colors.annotation}"
  button-text:
    backgroundColor: "transparent"
    textColor: "{colors.link}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "9px 4px"
  button-text-hover:
    backgroundColor: "{colors.accent-subtle}"
    textColor: "{colors.primary-hover}"
  button-danger:
    backgroundColor: "transparent"
    textColor: "{colors.destructive-text}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "9px 17px"
  button-danger-hover:
    backgroundColor: "{colors.danger-hover-surface}"
    textColor: "{colors.error-text}"
  button-disabled:
    backgroundColor: "{colors.disabled-surface}"
    textColor: "{colors.disabled-text}"
    rounded: "{rounded.control}"
  input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "9px 12px"
  navigation:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.nav}"
    padding: "10px 24px"
  tag-success:
    backgroundColor: "{colors.success-surface}"
    textColor: "{colors.success-text}"
    rounded: "{rounded.tag}"
    padding: "3px 7px"
  paper-container:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
    padding: "26px"
  source-preview:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "25px 23px"
  error-message:
    backgroundColor: "{colors.error-surface}"
    textColor: "{colors.error-text}"
    rounded: "{rounded.control}"
---

# Design System: 研枢 ScholarGraph · 青瓷书页

## Overview

**Creative North Star: "青瓷书页"**

雾青像桌面与装帧，白纸承载真实材料，深墨支撑中文科研操作。整体安静、清楚、适合长时间阅读；气质来自纸页、细线、间距与信息秩序，不靠装饰堆叠。

用户选择的液态玻璃集中于顶部一层悬浮导航，半透明高光缓慢流动。原文、表单与结果保持实体底色，主操作、次操作与文字操作具有不同的视觉分量。拒绝 emoji、廉价紫蓝渐变和功能卡片墙；系统操作使用中文，论文与原始 PDF 保持材料本身的语言与字体。

**Key Characteristics:**

- 雾青外框与不透明白色工作面。
- 单层受约束的悬浮玻璃与可关闭的缓慢流动。
- 深墨主按钮、细边次按钮与带下划线的文字操作。
- 中文系统字体处理操作，局部衬线呈现书页预览。
- 列表、细线与明确状态支撑科研工作。

本文件记录 2026-10-29 用户已确认的 B 方向及最终实现。提取依据为 `frontend/app/celadon.css`，并核对其前置样式、`SiteNav.tsx`、`ReadingWorkbench.tsx`；产品事实见 `PRODUCT.md`，页面策略与验收场景留在 `docs/ui-celadon-surface.md`。前置 YAML 是规范 token；`.impeccable/design.json` 补充阴影、动效、断点和自包含组件示例。sidecar 中的八阶 OKLCH 色条是为面板合成的预览元数据，不是实际 CSS 新增的色板。

## Colors

青瓷色低饱和而有温度，墨色承担层级，青绿用于定位与交互；状态色只服务其对应语义。

### Primary

- **青瓷绿**（`primary` / `primary-hover`）：链接强调、选择提示、导航活动下划线和键盘焦点。
- **深青链接**（`link`）：文字操作与正文链接，区别于普通说明。
- **浅青选中面**（`primary-subtle`）：移动导航选中项及信息标签。

### Neutral

- **雾青桌面**（`canvas`）：全局外框。
- **实体白纸**（`paper`）：原文、结果、输入框和主要工作区。
- **浅青批注纸**（`annotation`）：目录、注释、状态与次按钮悬停底色。
- **深墨**（`ink` / `button-hover`）：正文、标题与主按钮；主按钮悬停使用略亮墨绿。
- **次墨与柔墨**（`text-secondary` / `text-muted`）：元数据、说明和占位符。
- **纸缝与控件边**（`border` / `control-border`）：前者分隔内容，后者界定可操作控件。
- **青瓷玻璃**（`glass` / `glass-border` / `glass-solid`）：导航的透明表面、浅色边与实体回退。

### Semantic states

- **赭红错误**（`error-text` / `error-surface`）：错误正文与浅赭底，区别于破坏操作。
- **破坏操作与错误标签**（`destructive-text` / `destructive-border` / `error-tag-surface`）：区分删除等操作与普通主操作。
- **叶绿成功、麦色警示**（`success-*` / `warning-*`）：标签用底色加文字描述状态。
- **禁用色组**（`disabled-*`）：保留清晰文字、边界与不可操作状态，不靠整体透明度表达。

**The Semantic Color Rule.** 颜色伴随文字或交互状态；失败信息不能伪装成空结果，成功色不能替代真实完成状态。

## Typography

**Display / Body Font:** 本地 Segoe UI、Microsoft YaHei、PingFang SC 与系统无衬线栈，供标题、中文操作与说明使用。

**Source Preview Font:** 本地 Georgia、Times New Roman、Songti SC 与衬线回退，仅用于材料预览标题和摘要。

**Code / Numeric Font:** 本地 Cascadia Code、Consolas 与等宽回退。该字体来自前置工作台样式；未下载新的 Web 字体。

**Character:** 操作文字清晰、朴素而紧凑，衬线只在书页预览处增加阅读感。原始 PDF 保持自身字体与版式。

### Hierarchy

- **Headline**：页面标题采用 YAML 的 `headline`；手机缩为 24px。阅读页标题另用 23px / 1.45，手机 21px。
- **Title**：区块标题采用 `title`；阅读助手与空状态标题为 17px，论文列表标题桌面 17px、手机 16px。
- **Body / Prose**：基础文字采用 `body`，长说明采用 `prose`；导语为 15px / 1.8、上限 78ch，阅读页元数据为 13px。
- **Label / Metadata**：按钮采用 `label`，元数据与表头采用 `metadata`；不把中文说明转成大写或日志体。
- **Source preview**：预览标题和摘要分别采用 `preview-title`、`preview-body`。
- **Code / Numbers**：诊断与代码采用 `code`；数值列使用等宽数字。普通说明即使沿用历史命名，也使用 UI 字体。

**The Original Source Rule.** 只为操作与材料预览设定系统字体；保持原始 PDF 的文字层、语言与版式。

## Layout

工作面居中，内容容器上限 1380px；应用桌面内边距为上 108px、横向 32px、下 32px。导航独立固定在顶部，上距 16px、左右 28px，上限 1512px；用预留空间保护标题与焦点目标。手机在 760px 及以下改为上 98px、横向 16px、下 24px，导航上距与左右距均为 12px。

间距以 YAML 的 4/8/12/16/24/32px 级数为底，局部阅读工作面保留实际的 18/20/26px。区块常用 26px 内边距和 24px 底部间隔，手机区块为 20px。论文以分隔线列表呈现，选中材料使用轻底色，不给每篇材料重复阴影。

论文库桌面为伸缩列表加 310px 预览栏、间隔 24px；1100px 及以下预览栏为 275px、间隔 20px；760px 及以下改为单列，预览不再粘附，保留返回列表入口。桌面预览顶部粘附位置为 112px。

阅读区桌面由 205px 目录、伸缩原文与 300px 助手组成。1100px 及以下阅读区改为单列：目录初始收起，助手在没有保存过偏好时默认收起；可分别展开。打开助手时切换工作区而不是挤窄原文，返回“原版式”会收起两侧区域。助手开合偏好保存在本地。1000px 及以下顶部五模块与桌面工具移入移动菜单；1250px 及以下先收紧导航间距和搜索宽度。

表格在自身容器横向滚动，不把长字段挤成逐字竖排。论文解析表实际表宽至少 960px，长文本列至少 360px、第二列至少 210px，其余列至少 100px；文本在单元格内部正常断行，外层保留可达的滚动区域。

## Elevation & Depth

实体纸面以色阶、留白与细线分层，默认没有卡片阴影。真正的悬浮层才使用环境阴影；顶部玻璃是用户选定的材质，不能扩散到正文背景。

### Shadow Vocabulary

- **导航浮起**（`0 8px 22px rgba(22,52,47,.07)`）：顶部玻璃条。
- **显示偏好浮层**（`0 6px 20px rgba(22,52,47,.09)`）：导航内偏好菜单。
- **移动导航抽屉**（`0 12px 30px rgba(22,52,47,.14)`）：独立模态导航。

桌面导航仅在自身边界内模糊 14px，并使用 `saturate(1.08)`；760px 及以下改为 8px 模糊。高光用 26s、`ease-in-out`、往返 CSS transform 循环，不移动正文。手动关闭时暂停并隐藏高光，标签页隐藏时暂停；系统减少动态时禁用动画。手动减少透明度、系统减少透明度与不支持 backdrop-filter 的环境均采用实体回退。

**The One Glass Rule.** 慢流动只发生在顶部导航这一层，实体阅读与操作工作面始终可辨。

## Shapes

形状由用途区分：标签采用 `tag` 的小圆角，按钮和输入框采用 `control`，工作面采用 `surface`，导航采用更柔和的 `nav`。手机导航改用 `nav-mobile`，独立抽屉用 `drawer`。论文列表与 PDF 纸页保持直边，PDF 仅用细边界而不用投影；聊天问题保留轻微不对称的 8px/8px/2px/8px 轮廓。

控件边界为 1px，分隔线薄而稳定。不要把所有操作做成相同胶囊，也不要给平面工作区套上玻璃圆角和厚阴影。

## Components

### Buttons

明确分级，采用短中文动作名称。主按钮为深墨实体、白字，次按钮透明底配控件边线，文字按钮使用深青与下划线；破坏按钮独立用赭红文字和浅红边。基础内边距与颜色见 YAML。

通用按钮最小高度为 42px，桌面论文行紧凑操作为 38px；手机论文行、阅读页签与主要导航目标为 44px。主按钮悬停切换为 `button-hover`，次按钮悬停使用批注纸与较深边线。文字按钮悬停采用深青字与浅青底，破坏按钮悬停采用赭红字、浅红底与更深边线；具体赋值见 YAML 的对应 hover 变体。所有可聚焦控件保留 3px 青瓷绿焦点轮廓及 3px 偏移。禁用使用实体禁用色组与不可操作光标。

### Chips

小圆角、轻底色与文字状态，内边距为 3px/7px。成功、失败、警示、信息与静默标签各有语义，不能靠彩色标签声称任务已完成。

### Cards / Containers

白纸工作面默认无投影、无外边框，以标题、细线和间距组织。论文库材料区桌面内边距 24px，手机 20px；列表条目直边分隔，当前预览行以浅底色标记。选中材料预览用更小圆角和衬线标题，摘要可在自身区域内滚动，最大高度为 300px。

### Inputs / Fields

实体白底、1px 控件边、5px 圆角，基础最小高度 42px，内边距为 9px/12px；保持宽度可收缩，长说明允许换行。占位符用柔墨并保持实体显示。键盘焦点沿用全局轮廓；错误由独立可读信息呈现，错误正文采用 `error-text` 和 `error-surface`。

### Navigation

品牌、五个模块、搜索与工具横排；当前模块用深墨加粗及 2px 青瓷绿下划线。移动导航包含搜索、模块、设置与显示偏好，并以实体抽屉呈现；有明确关闭按钮、Escape 关闭、焦点限制与关闭后返回触发器。打开时背景工作区不可交互。

显示偏好分别控制“关闭缓慢流动”和“减少透明度”，并保存到本地；系统减少动态与减少透明度同样生效。导航玻璃与动效的确切值见 Elevation & Depth 及 sidecar，不为操作添加人为等待。

### Reading and source evidence

原文是实体白纸，目录是浅青旁注，助手是独立白色工作面。页码、引用、选区与翻译结果靠明确控件和文字关联；窄屏用开合与区域切换保住可读宽度。诊断信息默认折叠，展开后使用浅底与等宽代码文字，失败与空结果分别呈现。加载骨架保持布局轮廓，当前骨架不闪烁、不循环动画。

### Visual assets

品牌、导航图标与空状态为代码内联的几何 SVG，没有生成式照片或位图 UI 素材。`frontend/public` 当前仅有 PDF worker 脚本；用户上传的 PDF、原文截图与论文材料不属于品牌装饰素材。

## Do's and Don'ts

### Do:

- **Do** 用雾青外框、实体白纸与深墨文字保持长时间阅读的稳定层级。
- **Do** 让主按钮、细边次按钮和带下划线的文字操作具有不同分量。
- **Do** 保留键盘焦点、可关闭的移动导航和返回原文的明确入口。
- **Do** 尊重手动显示偏好、系统减少动态与减少透明度，并在后台暂停高光。
- **Do** 让长文本在可读列宽中换行，让宽表在自身容器内滚动。
- **Do** 用中文说明空、加载、部分成功、失败和完成，并保留真实材料语言。

### Don't:

- **Don't** 用 emoji、廉价紫蓝渐变或功能卡片墙替代科研信息组织。
- **Don't** 把导航玻璃、模糊和慢流动扩展到正文、表单或结果底面。
- **Don't** 重排原始 PDF 字体，或把普通中文说明统一排成等宽日志。
- **Don't** 用状态颜色、骨架或示例内容冒充真实完成、精度或业务验收。
- **Don't** 用装饰动效增加等待，或让窄屏助手和目录持续挤压原文。
- **Don't** 为当前系统虚构已下载字体、位图素材来源或无证据的性能与无障碍认证。
