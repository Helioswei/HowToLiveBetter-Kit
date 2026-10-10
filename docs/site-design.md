---
version: alpha
name: 高性价比人生指南 · 在线阅读站
description: 一本书的国内镜像站：纸墨质感、克制、以正文为唯一主角；所有页面共用一套骨架与两档列宽。
colors:
  primary: "#b3402f"
  paper: "#faf8f4"
  paper-soft: "#f6f3ec"
  hairline: "#e2dccf"
  hairline-soft: "#ece7db"
  ink: "#26292f"
  ink-secondary: "#5b6069"
  muted: "#8b8f97"
  accent: "#b3402f"
  accent-strong: "#8f2f22"
  accent-soft: "#f4e5e0"
typography:
  h1:
    fontFamily: Source Han Serif SC
    fontSize: 1.9rem
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: "0.01em"
  h2:
    fontFamily: Source Han Serif SC
    fontSize: 1.16rem
    fontWeight: 700
    lineHeight: 1.5
  body-md:
    fontFamily: PingFang SC
    fontSize: 1rem
    lineHeight: 1.95
  body-sm:
    fontFamily: PingFang SC
    fontSize: 0.93rem
    lineHeight: 1.8
  caption:
    fontFamily: PingFang SC
    fontSize: 0.8rem
    lineHeight: 1.8
rounded:
  sm: 3px
  md: 6px
  lg: 10px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 42px
components:
  topbar:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    height: 46px
    padding: 10px
  breadcrumb:
    textColor: "{colors.ink-secondary}"
    typography: caption
  hero:
    textColor: "{colors.ink}"
    typography: h1
  article-body:
    textColor: "{colors.ink}"
    typography: body-md
  card:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: 16px
  chip:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: 8px
  chip-top:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.accent-strong}"
    rounded: "{rounded.sm}"
    padding: 8px
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#ffffff"
    rounded: "{rounded.lg}"
    padding: 12px
  intro-card:
    backgroundColor: "{colors.paper-soft}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: 16px
  link:
    textColor: "{colors.accent}"
    typography: body-md
  divider:
    backgroundColor: "{colors.hairline}"
    height: 1px
  divider-soft:
    backgroundColor: "{colors.hairline-soft}"
    height: 1px
  smallprint:
    textColor: "{colors.muted}"
    typography: caption
  table:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: body-sm
    padding: 8px
---

## Overview

一本书的**国内镜像站**：正文来自上游（CC BY 4.0），我们在不改变一个字的前提下重排版式、
把「见第 X 节第 Y 条」变成可点的链接、并让手机也能读。

视觉基调：**纸墨**。米白纸底、深墨正文、唯一强调色是砖红（`accent`），只用在"可交互"与
"最值得做"两件事上 —— 别的都不许上色。克制优先于装饰：版面靠留白与细线分隔，不靠阴影与色块。

给 AI 协作者的一句话：**这个文件是站点的样式唯一来源。改样式先改这里，再改代码；代码里的注释
要指回本节**。历史上反复出问题都是因为"哪里不对修哪里"，而不是"先定规则再让所有页面照着做"。

## Colors

- **paper 系列**（`#faf8f4` / `#f1ede4` / `#f6f3ec`）：纸底、卡片的浅底、代码与统计行底。三层足够，不要再加第四层灰。
- **hairline 系列**（`#e2dccf` / `#ece7db`）：分隔线与描边。重线只用于"块与块的边界"，轻线用于"行与行的分隔"。
- **ink 系列**（`#26292f` / `#5b6069` / `#8b8f97`）：正文 / 次级（说明、统计）/ 最弱（脚注、单位）。
- **accent 系列**（`#b3402f` / `#8f2f22` / `#f4e5e0`）：链接与交互（hover）、`accent-strong` 用于强调文字、
  `accent-soft` 作"极高性价比"这类标记的底色。**一个页面里 accent 出现的区域不超过三处**（顶栏链接、
  主按钮/标记、hover 态）。

深色模式：`prefers-color-scheme` 跟随系统；用户显式选过就由 `data-theme` 覆盖。
选择器写成 `html:not([data-theme="light"])`，让"系统深色 + 用户选浅色"也正确。

## Typography

- 标题（h1/h2）用衬线（`Source Han Serif SC` 系列），正文用系统无衬线 —— **书**的感觉来自标题，不是正文。
- 正文行高 1.95、行宽上限 44rem（见 Layout）。正文里不出现字号小于 0.8rem 的文字。
- 小字（统计行、脚注、署名）统一 0.8rem / `muted`，且**同一种小字在全站只有一种样式**。

## Layout

**三条硬规则，违反任何一条都会立刻被 `tools/check_site.py` 抓出来：**

1. **外壳位置全站唯一**：顶栏（`.b-topbar`）、面包屑（`.breadcrumb`）、页脚小字（`.b-smallprint`）
   在所有页面处于同一位置。面包屑必须是 `<main><div class="container">` 的**第一个子元素**
   （首页是站点根，允许没有面包屑）。
2. **正文列只有两档**，由 `<body class="p-list|p-article">` 声明：
   - `p-list`：列表 / 网格 / 时间轴页（首页、节页、检索、场景索引、场景页）→ **满宽**（容器内容宽，
     起点 114）
   - `p-article`：长文本页（条目页、长文页、关于、下载）→ **44rem 居中列**（书页感：左右留白对称）。
     标题、正文、表格、小字区**都在这一个列里**，它们之间不许有横向偏移。
3. **外壳贴左边、内容列居中**：
   - 外壳（顶栏、面包屑、页脚）统一贴容器左边（1200px 视口下 = 114px），全站一样；
   - `p-article` 的正文列居中（1200px 视口下 = 288…992），**标题与正文必须同列**；
   - ⚠️ 试过让 `p-article` 也左对齐（好跟面包屑连成一条线）：结果是右边空一大片、字还被窄列挤着
     换行，看着像错版 —— 长文就该居中，别为了"一条线"牺牲书页感。

容器与间距：家族 `.container`（1100px + 24px 内边距）不变；块与块之间用
`margin: 24px`（`lg`）或 `2.6rem`（小字区），行内元素之间用 `8px`（`sm`）。

## Elevation & Depth

**尽量不用阴影**。仅两处允许：卡片 hover（`0 4px 14px rgba(0,0,0,.08)`）与悬浮控件
（阅读设置按钮 `0 2px 8px rgba(0,0,0,.10)`）。所有"层级"优先靠细线 + 底色差表达。

## Shapes

圆角三档：`sm` 3px（表格、chip）、`md` 6px（卡片、字段块）、`lg` 10px（页级卡片、按钮、面板）。
**胶囊形（999px）只给两类**：高亮主按钮与"可点的小标记"（条号药丸、上一/下一条、预设按钮）。

## Components

每个组件：**结构（class 顺序）→ 变体 → 不许做什么**。改组件从这里改起。

### 页面骨架
`<body class="p-list|p-article">` → `.b-topbar`（品牌 + `.b-links` 导航）→ `<main><div class="container">`
→ `.breadcrumb` → `.b-hero`（h1 + 一行统计 `.b-stat`）→ 正文块 → `.b-smallprint`（署名 + 免责）
→ 页脚（家族注入，只有备案号）。**页面骨架由 `page()` 一处生成，页面体只产出"正文块"。**

### .b-hero
标题 + 一行说明/统计。`p-article` 页里与正文同宽（44rem 左对齐）。
变体：`.b-hero.narrow` 已废弃（列宽改由 `p-article` 决定）。
**不许**：在 hero 里放假按钮集合（首页只留一个主 CTA）。

### .b-smallprint
署名一行 + 免责一句，两者紧挨（行距 0 间距，`p + p` 4px）。全站文案一致，只在模板里生成一次。
**不许**：在正文里再写一遍署名/许可（那是这一块和「关于与许可」的事）。

### .b-intro（节页导览）
浅底卡片（`paper-soft` + `hairline`）→ 若干 `.b-group`，每组一个 `.b-group-t`（组名 + 左侧 `accent` 竖条）
和一行 `.b-items`（若干 `.b-chip`）。chip 内文字为条目标题，条号在 `.b-ref-n`（`muted`）；
"极高性价比"的条目用 `.b-chip.top`（`accent-soft` 底）。
**不许**：改导览里的字（保真校验逐字比对）；chip 之间加标点（列表分隔标点按排版隐藏）。

### .b-entry（节页条目卡）
编号 → 标题 → `.b-badges`（性价比 / 钱 / 时间 / 毅力 / 收益 / 口径 / 证据）→ `.b-human`（说人话）
→ `.b-cost` → `.b-more`（折叠：收益 / 来源 / 备注）→ `.b-perma`（单独打开）→ `.b-pager`。
`is-top` 变体：左侧 `accent` 竖条，表示"性价比 极高"。**徽章只允许 `.top` 上色**，其余一律灰阶。

### .b-fl / .b-lead（条目页字段）
`.b-lead` 是说人话（左侧 accent 竖线的引文块，唯一次级强调）；`.b-fl` 是"标签 + 内容"的字段块，
标签 0.78rem / `muted` 全大写感。**不许**：把来源/备注挪出折叠区（长文本页允许直出）。

### .b-tablewrap（长文页表格）
宽屏：正常表格（`hairline` 边线、表头 `paper-soft` 底）。窄屏（≤640px）：**折成卡片**，
每格用 `data-label` 标出列名。**不许**：让 4 列表格在手机上横向拖动。

### .b-scene-card / .b-scenes（场景与长文卡片）
一个网格里排所有入口卡；副标题只写**可数事实**（"5 个时间段 · 34 步" / "7 个部分"）。
**不许**：在页面上出现"我们的分类规则"（如"按时间排的 / 不是按时间排的"）。

### /map.html（性价比分布图）—— 唯一的交互页
**允许有 JS**（全站唯一的例外），但必须满足两条，缺一条就算错：
1. **默认显示静态图**（`scatter_svg()` 生成，纯 markup），**画布与工具栏默认 `hidden`**，
   由加载完数据后的脚本换上 → 关掉 JS / 脚本失败 / 数据没到，页面看到的都是完整那张图。
2. 脚本**内联**（`tools/map.js` 构建时注入），不引外部脚本；数据走 `/map.json`（按需加载，不进 sitemap）。
**不许**：把 canvas 当成"JS 好了才有的东西"（那样关掉 JS 就是一块空白 ✗）。
颜色/坐标轴语义与"档"的定义见 `/map.html` 本身 —— **档是书里算出来的，不是我们的判断**。

### 社交分享图（deploy/assets/og.png）
1200×630，由 `tools/og.html` 模板 + `tools/make_og.py` 生成（**本机跑**，CI 不需要 Chrome；
产物入库，`build_site` 只负责拷进站点）。图里的小图复用 `scatter_svg()`，与 `/map.html` 同款。
**改了 token 记得重跑 `python3 tools/make_og.py`** —— 否则分享图和站点会走样。

### .b-prefs（阅读设置）
右下角**悬浮按钮**，点开才是面板（字号/行距/主题/朗读）。检索页上加 `.lifted` 抬高 5.2rem 避开底部操作条。
**不许**：放回页脚或页首当一条常驻栏。

### .b-hit / .b-filters / .b-bar（检索页）
筛选块合成一块面板；结果卡片化，勾选在标题行右侧（`.b-pick`）；底部 `.b-bar` 是 sticky 操作条，
按钮在"已选 0 条"时禁用。链接里可以带筛选条件（`#ratio=极高`），用完把 URL 收干净。

## Do's and Don'ts

**Do**

- 改样式：先改本文件 → 再改 `tools/build_site.py` 的 `STYLE` 常量 → 跑 `bash tools/preview.sh`。
- 加页面类型：先在本文件 Layout 里定列宽档位，再在 `page()` 里传 `kind=`。
- 新增可点元素：先想清楚它属于"内容"还是"外壳" —— 外壳位置全站唯一，内容列宽才分两档。

**Don't**

- 别在页面体里自己写宽度/居中（`margin: auto` 之类）—— 列宽只有 `p-list` / `p-article` 两档。
- 别让某一个页型的标题/面包屑偏移到别处（历史事故：条目页 250、长文页 288、其余 114）。
- 别把"我们的决策/规则"写进读者可见文案（分类名、收录策略、同步版本号只写一次在「关于与许可」）。
- 别用 `str.replace` 静默改模板 —— 它不匹配时不报错（历史事故：面包屑移位失败、7 个冒号丢失）。
- 别留重复定义：同一个选择器在 `STYLE` 里只允许出现一次（历史上 `.b-bar` 有两份，
  后者赢、前者悄悄失效；还有一次删 token 声明却忘了改使用处，背景直接空掉）。
- 别改正文一个字：所有正文页的保真校验（条目字段 / 场景页 / 长文页 / 节页导览）会立刻红。

**每条规则对应的自检**（规则不是文档里的一句话，是脚本里的断言）：

| 规则 | 由谁断言 |
| 骨架 / 面包屑位置 / 两档列宽 | `tools/check_site.py` §7「版面规则」 |
| 正文一字不改 | `check_verbatim.py`（条目）+ `check_site.py` §6d/§6e（场景页、长文页、节页导览） |
| 页面数与 sitemap | `check_site.py` §1 |
| 内联 JS 语法 | `check_site.py` §6c（node --check） |
| 嵌 JS 的 Python 字符串必须 raw | `tools/check_python_warnings.py`（CI 第一步） |
| 链接与死链 | `check_site.py` §6（含中文 URL 的百分号编码） |
