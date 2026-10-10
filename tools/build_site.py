#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""站点生成器：build/entries.json → 模板版静态站（build/site/）。

    python3 tools/build_site.py
    python3 tools/build_site.py --base https://better.aigcwei.cn --out build/site

本站是**独立站**：页头是我们自己的（品牌 + 检索/下载/关于/仓库链接），不套主站的家族导航；
只在页面上留一个 `<div id="site-footer"></div>` 占位符，由网站家族的 scripts/inject.py
在构建时注入页脚 —— 与主站共用的只有**备案号**那一份信息，其真源是 site-config.json，
所以这个脚本一个字都不写死备案号。

零 JS 可读：除了 search.html（检索页，唯一需要 JS 的地方），全站不含 <script>。
正文原样转载，未作内容改动；每页标注同步自哪个上游提交。
"""

import argparse
import html
import json
import os
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import hltb  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STYLE_VERSION = "26"  # 改 style.css 时 +1，避免浏览器缓存旧样式

# ---------------------------------------------------------------- 页面骨架

TOKENS = """:root {
  --paper: #faf8f4; --paper-soft: #f6f3ec;
  --hairline: #e2dccf; --hairline-soft: #ece7db;
  --ink: #26292f; --ink-secondary: #5b6069; --muted: #8b8f97;
  --accent: #b3402f; --accent-strong: #8f2f22; --accent-soft: #f4e5e0;
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC",
               "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  --font-serif: "Source Han Serif SC", "Noto Serif CJK SC", "Songti SC", "STSong", SimSun, Georgia, serif;
  --radius-sm: 3px; --radius-md: 6px; --radius-lg: 10px;
}
"""

STYLE = TOKENS + """
/* 这一份是 better 站自己的样式，叠在共享的 assets.aigcwei.cn/style.css 之上 */
/* ---- 深色主题：默认跟随系统（不需要 JS），用户选过就用 data-theme 覆盖 ----
   选择器写成 html:not([data-theme="light"]) 是为了让"系统深色 + 用户显式选浅色"也正确。 */
@media (prefers-color-scheme: dark) {
  html:not([data-theme="light"]) { --paper: #16181c; --paper-soft: #1e2126;
          --hairline: #2e3238; --hairline-soft: #262a30;
          --ink: #e9e5df; --ink-secondary: #ada79e; --muted: #837d74;
          --accent: #cf6a4f; --accent-strong: #e08567; --accent-soft: #2a1f1a; }
  html:not([data-theme="light"]) .container, html:not([data-theme="light"]) .article,
  html:not([data-theme="light"]) .article-body, html:not([data-theme="light"]) .article-header,
  html:not([data-theme="light"]) .breadcrumb { background: transparent; color: var(--ink); }
  html:not([data-theme="light"]) .article-body a { color: var(--accent-strong); }
  html:not([data-theme="light"]) .b-intro, html:not([data-theme="light"]) .b-lead { background: var(--paper-soft); }
}
html[data-theme="dark"] { --paper: #16181c; --paper-soft: #1e2126;
          --hairline: #2e3238; --hairline-soft: #262a30;
          --ink: #e9e5df; --ink-secondary: #ada79e; --muted: #837d74;
          --accent: #cf6a4f; --accent-strong: #e08567; --accent-soft: #2a1f1a; }
/* 主站共享样式给 .container/.article 的浅色底与深色字，在深色模式下要跟着走 */
html[data-theme="dark"] .container, html[data-theme="dark"] .article,
html[data-theme="dark"] .article-body, html[data-theme="dark"] .article-header,
html[data-theme="dark"] .breadcrumb { background: transparent; color: var(--ink); }
html[data-theme="dark"] .article-body a { color: var(--accent-strong); }
/* 这两个块自己有色底，别被上面那条"透明"规则抹掉 */
html[data-theme="dark"] .b-intro, html[data-theme="dark"] .b-lead { background: var(--paper-soft); }

/* ---- 字号 / 行距档位（阅读设置那一行控制；默认不设属性 = 标准）---- */
html[data-size="s"] { font-size: 15px; }
html[data-size="l"] { font-size: 18px; }
html[data-size="xl"] { font-size: 21px; }
html[data-size="s"] body, html[data-size="l"] body, html[data-size="xl"] body,
html[data-size="s"] .article-body p, html[data-size="l"] .article-body p, html[data-size="xl"] .article-body p,
html[data-size="s"] .b-entry, html[data-size="l"] .b-entry, html[data-size="xl"] .b-entry { font-size: 1rem; }
html[data-leading="w"] body, html[data-leading="w"] .article-body p, html[data-leading="w"] .b-entry { line-height: 2.05; }

/* 阅读设置：右下角一个悬浮按钮，点开才是面板（原来是页脚里横着一条，占版面又像正文的一部分） */
.b-prefs { position: fixed; right: .9rem; bottom: .9rem; z-index: 30; display: flex;
           flex-direction: column; align-items: flex-end; gap: .4rem; margin: 0; padding: 0;
           border: 0; background: none; font-size: .84rem; color: var(--ink-secondary); }
.b-prefs.lifted { bottom: 5.2rem; }   /* 检索页底部有操作条，别压在一起 */
.b-prefs > button { font: inherit; font-size: .84rem; cursor: pointer; padding: .4rem .85rem;
           border: 1px solid var(--hairline); border-radius: 999px; background: var(--paper);
           color: var(--ink); box-shadow: 0 2px 8px rgba(0,0,0,.10); }
.b-prefs > button:hover { border-color: var(--accent); color: var(--accent-strong); }
.b-prefs-panel { display: flex; flex-wrap: wrap; align-items: center; gap: .6rem .8rem;
           padding: .7rem .9rem; border: 1px solid var(--hairline); border-radius: var(--radius-lg);
           background: var(--paper-soft); box-shadow: 0 4px 16px rgba(0,0,0,.14); }
.b-prefs-panel[hidden] { display: none; }
.b-prefs label { display: inline-flex; align-items: center; gap: .3rem; }
.b-prefs select { font: inherit; font-size: .84rem; padding: .15rem .3rem; background: var(--paper);
                  color: var(--ink); border: 1px solid var(--hairline); border-radius: var(--radius-sm); }
.b-prefs-panel button { font: inherit; font-size: .84rem; padding: .2rem .7rem; cursor: pointer;
                  background: var(--paper); color: var(--ink); border: 1px solid var(--hairline);
                  border-radius: 999px; }
.b-prefs .b-sep { flex-basis: 100%; color: var(--muted); font-size: .76rem; }
/* 页脚小字区：署名一行 + 免责一句，永远待在一起（免责以前挂在正文末尾，
   于是"离署名多远"取决于这页有没有翻页块 —— 首页 38px、条目页 152px，看着像不一致）。
   ⚠️ ① 免责那句别挪回正文：check_site 会断言每页都有"不构成诊疗意见"。
   ⚠️ ② 这个块必须留在 <main .container> **里面**：放外面就只有最大宽度、没有居中，
        会贴到屏幕最左边（曾经就这么错过）。
   ③ 用居中 + 与正文同宽（44rem）：条目页的正文是居中窄列，页脚版权行也是居中，
      小字跟着居中才在同一根轴线上（左对齐会变成第三根轴，看着就是"左右位置不对"）。 */
.b-smallprint { max-width: 44rem; margin: 2.6rem auto .3rem; text-align: center;
                font-size: .8rem; line-height: 1.8; color: var(--muted); }
.b-smallprint p { margin: 0; }
.b-smallprint p + p { margin-top: .22rem; }
.b-smallprint a { color: var(--ink-secondary); }
a, code, p, li, h1, h2, h3 { overflow-wrap: anywhere; }  /* 长 URL 不许撑破 375px 窄屏 */
/* 本站自己的页头：这是独立站，不用主站的家族导航；页脚仍然用家族那份（只出备案号） */
.b-topbar { position: sticky; top: 0; z-index: 10; background: var(--paper);
            border-bottom: 1px solid var(--hairline); }
/* ⚠️ 只能改上下内边距，别写 padding: … 0 —— 那会把 .container 的左右内边距清零，
   顶栏内容就会比正文左移 24px（实测过：顶栏 90 / 正文 114）。 */
.b-topbar-inner { display: flex; align-items: center; gap: .9rem; flex-wrap: wrap;
                  padding-top: .65rem; padding-bottom: .65rem; }
.b-brand { font-weight: 700; text-decoration: none; color: var(--ink); font-family: var(--font-serif); }
.b-tag { font-size: .78rem; color: var(--muted); }
.b-links { margin-left: auto; display: flex; gap: .9rem; flex-wrap: wrap; font-size: .95rem; }
.b-links a { color: var(--ink); text-decoration: none; }
.b-links a:hover { color: var(--accent-strong); }
.b-hero { padding: 1.4rem 0 0.6rem; }
/* 长文页（about / download）：hero 跟下面的正文列用同一根列，
   不然 hero 铺满容器、正文是窄列，左边缘对不上（这轮就退回过一次）。 */
.b-hero.narrow { max-width: 44rem; margin-inline: auto; }
.b-hero h1 { font-family: var(--font-serif); font-size: 1.9rem; margin: 0 0 .4rem; }
.b-hero p { color: var(--ink-secondary); margin: .3rem 0; }
.b-stat { font-size: .86rem; color: var(--muted); }
.b-secs { list-style: none; padding: 0; margin: 1.2rem 0; }
.b-secs li { border-bottom: 1px solid var(--hairline-soft); }
.b-secs a { display: grid; grid-template-columns: 2.6rem 1fr auto; grid-template-areas: "n t c" ". q q";
            gap: .1rem .6rem; padding: .7rem .15rem; text-decoration: none; color: inherit; }
.b-secs a:hover { background: var(--paper-soft); }
.b-sn { grid-area: n; color: var(--muted); font-variant-numeric: tabular-nums; }
.b-st { grid-area: t; font-weight: 600; }
.b-sc { grid-area: c; font-size: .82rem; color: var(--muted); white-space: nowrap; }
.b-sq { grid-area: q; font-size: .85rem; color: var(--muted); }
.b-q { background: var(--paper-soft); border-left: 3px solid var(--accent); padding: .55rem .85rem;
       font-size: .95rem; color: var(--ink-secondary); margin: .8rem 0 1.2rem; }
.b-entry { border-top: 1px solid var(--hairline-soft); padding: 1.05rem 0; }
.b-entry h3 { font-size: 1.06rem; margin: 0 0 .35rem; line-height: 1.6; }
.b-badges { display: flex; gap: .32rem; flex-wrap: wrap; margin: .1rem 0 .5rem; }
.b-badge { font-size: .72rem; padding: .08rem .45rem; border-radius: 999px;
           border: 1px solid var(--hairline-soft); color: var(--muted); background: transparent; }
/* 标签只留一个强调：性价比。其它（钱/时间/毅力/收益/证据/口径）一律灰阶 —— 密集列表里
   红绿灰三色混在一起是噪音，读者要的是"哪几条值得做"，不是分辨颜色。 */
.b-badge.top { color: var(--accent-strong); border-color: var(--accent);
               background: var(--accent-soft); font-weight: 600; }
.b-human { margin: .3rem 0; font-weight: 600; }
.b-cost { font-size: .9rem; color: var(--ink-secondary); margin: .25rem 0; }
.b-entry details { margin: .45rem 0 .2rem; }
.b-entry summary { cursor: pointer; font-size: .86rem; color: var(--muted); }
.b-fl { margin: .5rem 0; }
.b-fl b { display: block; font-size: .78rem; color: var(--muted); font-weight: 600; }
.b-fl p { margin: .15rem 0; font-size: .94rem; }
.b-fl a, .b-src a { word-break: break-all; }
.b-perma { font-size: .8rem; margin: .35rem 0 0; }
.b-xref { border-bottom: 1px dotted var(--muted); text-decoration: none; }
.b-meta { font-size: .82rem; color: var(--muted); }
.b-pager { display: flex; gap: 1rem; flex-wrap: wrap; margin: 1.6rem 0; padding-top: 1rem;
           border-top: 1px solid var(--hairline); }
.b-note { font-size: .84rem; color: var(--muted); margin-top: 2rem; padding-top: .8rem;
          border-top: 1px solid var(--hairline-soft); }
.b-filters { display: flex; flex-wrap: wrap; gap: .5rem 1.2rem; align-items: center;
             margin: .8rem 0 1.2rem; font-size: .9rem; }
.b-filters fieldset { border: 1px solid var(--hairline); border-radius: var(--radius-md);
             padding: .4rem .7rem; margin: 0; }
.b-filters legend { font-size: .78rem; color: var(--muted); padding: 0 .3rem; }
.b-filters label { margin-right: .6rem; white-space: nowrap; }
.b-hit { border-top: 1px solid var(--hairline-soft); padding: .8rem 0; }
.b-hit-head { display: flex; gap: .6rem; align-items: flex-start; }
.b-hit-head h3 { flex: 1; margin: 0 0 .3rem; }
.b-pick { display: flex; align-items: center; gap: .35rem; font-size: .8rem; color: var(--muted);
          white-space: nowrap; cursor: pointer; padding-top: .15rem; }
.b-pick input { width: 1.05rem; height: 1.05rem; accent-color: var(--accent); }
.b-hit.picked { background: var(--accent-soft); }
.b-presets { display: flex; gap: .5rem; flex-wrap: wrap; margin: .6rem 0 0; }
.b-presets button { font: inherit; font-size: .85rem; cursor: pointer; padding: .3rem .7rem;
          border: 1px solid var(--hairline); border-radius: 999px; background: var(--paper-soft);
          color: var(--ink); }
.b-presets button:hover { border-color: var(--accent); color: var(--accent-strong); }
.b-bar { position: sticky; bottom: 0; display: flex; gap: .7rem; align-items: center; flex-wrap: wrap;
          margin-top: 1.2rem; padding: .7rem .9rem; background: var(--paper-soft);
          border-top: 2px solid var(--accent); font-size: .88rem; }
.b-bar button { font: inherit; font-size: .85rem; cursor: pointer; padding: .3rem .8rem;
          border: 1px solid var(--hairline); border-radius: var(--radius-md); background: var(--paper); }
.b-bar .b-count { font-weight: 600; }
.b-bar .b-hint { color: var(--muted); }
/* ⚠️ 样式规则见 docs/site-design.md（token、两档列宽、每个组件允许的变体）。
   改这里之前先改那份规范 —— 历史上每次"哪里不对修哪里"都会让别处不一致。 */
/* ---- 版面规则（改宽度只改这里的两档，别在别处动）------------------------------------
   p-list    列表/网格/时间轴页：满宽
   p-article 长文本页：44rem **居中列**（书页感：左右留白对称，标题与正文同列）
   → 教训 1：以前让每个页型各自决定宽度，修一处就会让别处不一致 → 现在只有两档。
   → 教训 2：试过"靠左对齐"（为了和面包屑同一条线），结果是右边空一大片、字还被窄列挤着换行，
     看着是错版 → 长文就该居中列，外壳（面包屑）自己统一贴左边即可。
   → check_site §7 断言"每页的 body class 只能是这两个之一"。 */
.article, .article-body, body.p-article .b-hero, body.p-article .b-note,
body.p-article .b-tablewrap, body.p-article .b-intro { max-width: 44rem; margin-inline: auto; }
body.p-article .b-hero h1 { margin-bottom: .5rem; }
/* 长文页在窄列里排版，但列表/表格仍然不超出这一列 */
.article-body p { line-height: 1.95; margin: .78rem 0; }
.article-header h1 { font-family: var(--font-serif); letter-spacing: .01em; }
.article-meta { color: var(--muted); font-size: .84rem; }
/* 说人话 = 整条的结论，做成引文块 */
.b-lead { background: var(--paper-soft); border-left: 3px solid var(--accent);
          border-radius: 0 var(--radius-md) var(--radius-md) 0; padding: .8rem 1rem; margin: .9rem 0 1.1rem; }
.b-lead p { margin: 0; font-weight: 600; font-size: 1.03rem; line-height: 1.9; }
/* 字段：标签像小标题 */
.b-fl { margin: 1.1rem 0; }
.b-fl > b { display: block; font-size: .78rem; letter-spacing: .06em; color: var(--muted);
            font-weight: 600; margin-bottom: .2rem; }
.b-fl p { margin: .3rem 0; }
/* 折叠区看起来像一行按钮，不是一行灰字 */
details.b-more { margin: 1.1rem 0 .3rem; }
details.b-more > summary { display: inline-flex; align-items: center; gap: .35rem; cursor: pointer;
   padding: .25rem .8rem; font-size: .85rem; color: var(--ink-secondary);
   border: 1px solid var(--hairline); border-radius: 999px; background: var(--paper-soft); }
details.b-more > summary:hover { border-color: var(--accent); color: var(--accent-strong); }
details.b-more[open] > summary { margin-bottom: .6rem; }
/* 条号引用做成小药丸（书里 421 处「（第 N 条）」） */
.b-ref { display: inline-block; padding: 0 .38rem; border-radius: 999px; background: var(--accent-soft);
         color: var(--accent-strong); text-decoration: none; font-size: .9em; white-space: nowrap; }
.b-ref:hover { background: var(--accent); color: #fff; }
.b-refs-inline { line-height: 2.2; }
/* 节页导览块：书里"本节条目按主题分成下面几块，括号里是条号"那一段。
   上游是一句话式的清单，这里按它本来的结构分块：组名做小标题、每条一个可点 chip。
   ⚠️ 一个字都不许改 —— check_site 会断言导览原文在页面上逐字按序出现。 */
.b-intro { background: var(--paper-soft); border: 1px solid var(--hairline);
           border-radius: var(--radius-lg); padding: .3rem 1.1rem .8rem; margin: 1rem 0 1.4rem;
           max-width: none; }
.b-intro p { line-height: 1.95; }
.b-intro > p { font-size: .93rem; color: var(--ink-secondary); }
.b-group { margin: 1.1rem 0 .1rem; }
.b-group-t { font-size: .98rem; font-weight: 700; color: var(--accent-strong); margin: 0 0 .5rem;
             padding-left: .55rem; box-shadow: inset 3px 0 0 var(--accent); letter-spacing: .01em; }
.b-items { margin: 0; line-height: 2.5; }
.b-chip { display: inline-block; margin: 0 .3rem .3rem 0; padding: .1rem .55rem;
          border: 1px solid var(--hairline-soft); border-radius: var(--radius-sm);
          background: var(--paper); color: var(--ink); text-decoration: none; font-size: .9rem; }
.b-chip:hover { border-color: var(--accent); color: var(--accent-strong); background: var(--accent-soft); }
.b-chip .b-ref-n { color: var(--muted); font-size: .88em; }
/* 极高性价比那几条：用淡底填充，而不是描边 —— 描边在密集的 chip 里像"当前选中"，会误导 */
.b-chip.top { background: var(--accent-soft); border-color: transparent; }
.b-chip.top .b-ref-n { color: var(--accent-strong); }
.b-sep-c { color: var(--muted); }
.b-intro strong { color: var(--accent-strong); }
/* 节页条目卡：留白更松、极高那几条左边补一道强调条、悬停有反馈 */
.b-entry { padding: 1.15rem .9rem; margin: 0 -.9rem; border-radius: var(--radius-md); }
.b-entry:hover { background: var(--paper-soft); }
.b-entry.is-top { box-shadow: inset 3px 0 0 var(--accent); }
.b-entry .b-num { color: var(--muted); text-decoration: none; }
.b-entry .b-human { font-size: 1.01rem; line-height: 1.9; }
.b-badges { gap: .3rem; margin: .35rem 0 .6rem; }
.b-badge { background: transparent; border-color: var(--hairline-soft); }
.b-secs a { border-radius: var(--radius-sm); }
.b-tl-step { margin-bottom: 2rem; }
.b-tl-step li { line-height: 1.9; }

/* ---- 场景时间轴 ---- */
.b-tl { margin: 1.4rem 0 0; }
.b-tl-step { position: relative; padding: 0 0 0 1.5rem; border-left: 2px solid var(--hairline);
             margin: 0 0 1.7rem; }
.b-tl-step::before { content: ""; position: absolute; left: -8px; top: .3rem; width: 14px; height: 14px;
             border-radius: 50%; background: var(--accent); border: 3px solid var(--paper); }
.b-tl-step h2 { font-size: 1.14rem; margin: 0 0 .6rem; }
.b-tl-step ol { padding-left: 1.3rem; margin: .4rem 0; }
.b-tl-step li { margin: .5rem 0; }
.b-refs { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--hairline); }
.b-refs h2 { font-size: 1rem; margin: 0 0 .6rem; }
.b-refs ul { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: .35rem;
             font-size: .92rem; }
.b-scenes { display: grid; grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); gap: .8rem;
            margin: 1rem 0 0; }
.b-scene-card { display: block; padding: .9rem 1rem; border: 1px solid var(--hairline);
            border-radius: var(--radius-md); background: var(--paper-soft); text-decoration: none;
            color: inherit; }
.b-scene-card:hover { border-color: var(--accent); }
.b-scene-card b { display: block; margin-bottom: .3rem; }
.b-scene-card span { font-size: .84rem; color: var(--muted); }
.b-hit h3 { font-size: 1rem; margin: 0 0 .3rem; }
/* ================= 第二轮：控件 / 列表 / 卡片 ================= */

/* 阅读设置条：它以前被插到 <html> 下、横在页面顶部当裸条；后来归到正文末尾，现在改成右下角悬浮 */
.b-prefs select { appearance: none; -webkit-appearance: none; padding: .22rem 1.5rem .22rem .5rem;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' fill='none' stroke='%238b8478' stroke-width='1.5'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right .45rem center; }
.b-prefs select:hover, .b-prefs button:hover { border-color: var(--accent); color: var(--accent-strong); }
.b-prefs button { border-radius: 999px; padding: .22rem .8rem; }

/* CTA：按钮，而不是一串点号分隔的链接 */
.b-cta { display: flex; flex-wrap: wrap; gap: .5rem; margin: 1.1rem 0 .2rem; }
.b-btn { display: inline-block; padding: .45rem .95rem; border: 1px solid var(--hairline);
  border-radius: 999px; background: var(--paper); color: var(--ink); text-decoration: none;
  font-size: .92rem; line-height: 1.6; }
.b-btn:hover { border-color: var(--accent); color: var(--accent-strong); background: var(--paper-soft); }
.b-btn.primary { background: var(--accent); border-color: var(--accent); color: #fff;
  box-shadow: 0 1px 2px rgba(0,0,0,.08); }
.b-btn.primary:hover { background: var(--accent-strong); border-color: var(--accent-strong); color: #fff;
  box-shadow: 0 2px 6px rgba(0,0,0,.12); }
.b-lede { font-size: .99rem; color: var(--ink-secondary); }
.b-meta { display: flex; flex-wrap: wrap; gap: .3rem .9rem; margin: .9rem 0 0; padding: .6rem 0 0;
  border-top: 1px solid var(--hairline-soft); font-size: .84rem; color: var(--ink-secondary); }
.b-meta a { color: var(--ink-secondary); }
.b-h2 { font-size: 1.05rem; margin: 1.8rem 0 .2rem; }

/* 首页 34 节列表：不再是"表格感"的三列，而是能扫的行 */
.b-secs { list-style: none; padding: 0; margin: 1.2rem 0 0; border: 1px solid var(--hairline);
  border-radius: var(--radius-lg); overflow: hidden; background: var(--paper); }
.b-secs li + li { border-top: 1px solid var(--hairline-soft); }
.b-secs a { display: grid; grid-template-columns: 2.4rem 1fr auto; align-items: baseline;
  gap: .2rem .9rem; padding: .7rem .9rem; text-decoration: none; color: inherit; }
.b-secs a:hover { background: var(--paper-soft); box-shadow: inset 3px 0 0 var(--accent); }
.b-sn { grid-column: 1; grid-row: 1 / span 2; align-self: center; font-variant-numeric: tabular-nums;
  font-size: .85rem; color: var(--muted); }
.b-st { grid-column: 2; grid-row: 1; font-weight: 600; font-size: 1.02rem; }
.b-sc { grid-column: 3; grid-row: 1; font-size: .78rem; color: var(--muted); white-space: nowrap;
  border: 1px solid var(--hairline-soft); border-radius: 999px; padding: 0 .45rem; }
.b-sq { grid-column: 2 / -1; grid-row: 2; font-size: .88rem; color: var(--ink-secondary); }

/* 场景卡：有边界、有反馈、元数据不散 */
.b-scenes { grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr)); gap: .7rem; }
.b-scene-card { padding: 1rem 1.1rem; background: var(--paper); border-color: var(--hairline);
  box-shadow: 0 1px 3px rgba(0,0,0,.05); transition: box-shadow .15s, border-color .15s; }
.b-scene-card:hover { border-color: var(--accent); box-shadow: 0 4px 14px rgba(0,0,0,.09); }
.b-scene-card b { font-family: var(--font-serif); font-size: 1.05rem; margin-bottom: .35rem; }
.b-scene-card span { font-size: .8rem; color: var(--muted); }

/* 检索页：筛选合成一块面板，不再碎成一堆小框 */
.b-filters { display: grid; grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  gap: .1rem 1.6rem; margin: 1.2rem 0 .8rem; padding: .9rem 1.1rem 1.1rem;
  border: 1px solid var(--hairline); border-radius: var(--radius-lg); background: var(--paper-soft); }
.b-filters fieldset { border: 0; padding: .5rem 0; margin: 0; min-width: 0; }
.b-filters legend { font-size: .74rem; letter-spacing: .06em; color: var(--muted); padding: 0 0 .15rem; }
.b-filters label { display: inline-flex; align-items: center; gap: .25rem; margin: 0 .7rem .2rem 0;
  font-size: .88rem; }
.b-filters input[type="search"] { font: inherit; font-size: .9rem; padding: .3rem .5rem;
  border: 1px solid var(--hairline); border-radius: var(--radius-sm); background: var(--paper); color: var(--ink); }
.b-presets { display: flex; flex-wrap: wrap; gap: .4rem; margin: .8rem 0 0; }
.b-presets button { font: inherit; font-size: .86rem; cursor: pointer; padding: .3rem .8rem;
  border: 1px solid var(--hairline); border-radius: 999px; background: var(--paper); color: var(--ink); }
.b-presets button:hover { border-color: var(--accent); color: var(--accent-strong); background: var(--paper-soft); }

/* 检索结果：卡片化；勾选就在标题行右侧；标签降色，只留性价比一个强调 */
#hits { padding-bottom: 1rem; }
.b-hit { padding: 1rem 1.1rem; margin: 0 0 .6rem; border: 1px solid var(--hairline);
  border-radius: var(--radius-md); background: var(--paper); }
.b-hit:hover { background: var(--paper-soft); }
.b-hit.picked { border-color: var(--accent); box-shadow: inset 3px 0 0 var(--accent); }
.b-hit-head { display: flex; align-items: flex-start; gap: .8rem; }
.b-hit-head h3 { flex: 1; margin: 0; }
.b-pick { display: inline-flex; align-items: center; gap: .3rem; flex: none; cursor: pointer;
  font-size: .82rem; color: var(--ink-secondary); border: 1px solid var(--hairline);
  border-radius: 999px; padding: .15rem .6rem; background: var(--paper); }
.b-pick:hover { border-color: var(--accent); color: var(--accent-strong); }
.b-hit.picked .b-pick { background: var(--accent); border-color: var(--accent); color: #fff; }
.b-hit p { margin: .4rem 0 0; font-size: .92rem; color: var(--ink-secondary); line-height: 1.8; }
.b-hit .b-badges { margin: .45rem 0 .1rem; }

/* 底部操作条：有层次、有禁用态 */
.b-bar { position: sticky; bottom: .6rem; display: flex; flex-wrap: wrap; gap: .5rem; align-items: center;
  margin: 1rem 0 0; padding: .7rem .9rem; border: 1px solid var(--hairline);
  border-radius: var(--radius-lg); background: var(--paper); box-shadow: 0 -2px 12px rgba(0,0,0,.06); }
.b-bar button { font: inherit; font-size: .86rem; cursor: pointer; padding: .35rem .85rem;
  border-radius: 999px; border: 1px solid var(--hairline); background: var(--paper); color: var(--ink); }
.b-bar button:hover:not(:disabled) { border-color: var(--accent); color: var(--accent-strong); }
.b-bar button:disabled { opacity: .45; cursor: not-allowed; }
.b-bar .b-count { font-size: .86rem; color: var(--ink-secondary); margin-right: auto; }
.b-hint { font-size: .8rem; color: var(--accent-strong); }

/* 下载页：四份文件做成卡片（整张卡可点 + 体积由构建时量出来填） */
.b-dl { list-style: none; padding: 0; margin: 1rem 0; display: grid;
  grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); gap: .7rem; }
.b-dl li { border: 1px solid var(--hairline); border-radius: var(--radius-md); background: var(--paper);
  box-shadow: 0 1px 3px rgba(0,0,0,.04); transition: border-color .15s, box-shadow .15s; }
.b-dl li:hover { border-color: var(--accent); box-shadow: 0 4px 14px rgba(0,0,0,.08); }
.b-dl a { display: block; padding: 1rem 1.1rem; text-decoration: none; color: inherit; }
.b-dl b { font-weight: 600; font-size: 1.02rem; color: var(--accent-strong); }
.b-dl em, .b-dl .b-dl-size { font-style: normal; font-size: .8rem; color: var(--muted); margin-left: .5rem; }
.b-dl span { display: block; margin-top: .35rem; font-size: .86rem; color: var(--ink-secondary); }

/* 长文页：上游长文里的表格（如"做平台要办哪些证"的三张表）与长文清单 */
.b-tablewrap { overflow-x: auto; margin: 1.2rem 0; }
.b-tablewrap table { border-collapse: collapse; width: 100%; font-size: .88rem; }
.b-tablewrap th, .b-tablewrap td { border: 1px solid var(--hairline); padding: .45rem .6rem;
  text-align: left; vertical-align: top; }
.b-tablewrap th { background: var(--paper-soft); font-weight: 600; }
.b-lf { list-style: none; padding: 0; margin: .6rem 0 0; }
.b-lf li { border-bottom: 1px solid var(--hairline-soft); }
.b-lf a { display: block; padding: .65rem .2rem; text-decoration: none; color: inherit; }
.b-lf a:hover { color: var(--accent-strong); }
.b-lf b { font-weight: 600; }
.b-lf span { color: var(--muted); font-size: .84rem; margin-left: .6rem; }

/* 性价比分布图（/map.html）：canvas 交互 + noscript 静态图兜底（工具页允许 JS，但没 JS 也得能看） */
.b-mapbar[hidden], .b-mapwrap[hidden] { display: none !important; }   /* hidden 要压过 flex */
.b-mapbar { display: flex; flex-wrap: wrap; gap: .5rem; margin: 1.1rem 0 .7rem; }
.b-mapbar button { font: inherit; font-size: .85rem; padding: .35rem .85rem; border: 1px solid var(--hairline);
                   background: var(--paper); color: var(--ink-secondary); border-radius: 999px; cursor: pointer; }
.b-mapbar button:hover { border-color: var(--ink-secondary); }
.b-mapbar button.on { border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }
.b-mapbar button[data-reset] { margin-left: auto; }
.b-mapwrap { position: relative; margin: .2rem 0 .6rem; border: 1px solid var(--hairline); border-radius: 10px;
             background: var(--paper-soft); overflow: hidden; }
.b-mapcanvas { display: block; width: 100%; height: 460px; cursor: grab; touch-action: none; }
.b-mapcard { position: absolute; top: 0; left: 0; width: min(21rem, calc(100% - 1rem)); background: var(--paper);
             border: 1px solid var(--hairline); border-radius: 8px; padding: .7rem .85rem;
             box-shadow: 0 6px 18px rgba(38, 41, 47, .12); }
.b-mapcard b { display: block; font-size: .95rem; line-height: 1.45; }
.b-mapcard .k { display: block; margin-top: .35rem; font-size: .75rem; color: var(--muted); }
.b-mapcard .t { margin: .45rem 0 .55rem; font-size: .82rem; line-height: 1.65; color: var(--ink-secondary); }
.b-mapcard .hint { display: block; font-size: .78rem; color: var(--accent); }
.b-mapcanvas.grabbing { cursor: grabbing; }
@media (max-width: 640px) { .b-mapcanvas { height: 360px; } }

/* 静态兜底（noscript）与打印：窄屏横向可滚，不压缩气泡 */
.b-scatterwrap { margin: 1.2rem 0 .4rem; overflow-x: auto; }
.b-scatter { display: block; width: 100%; min-width: 560px; height: auto; }
.b-legend { display: flex; flex-wrap: wrap; gap: .3rem 1.2rem; align-items: center;
            margin: .6rem 0 0; font-size: .85rem; color: var(--ink-secondary); }
.b-legend i.b-lg-dot { display: inline-block; width: .7rem; height: .7rem; border-radius: 50%;
            margin-right: .35rem; vertical-align: -1px; }
.b-legend .b-lg-note { color: var(--muted); font-size: .8rem; }

/* 正文小标题的节奏 + 上一/下一条 */
.article-body h2 { margin: 2rem 0 .6rem; font-size: 1.16rem; }
.article-body h2:first-child { margin-top: .4rem; }
.b-pager { display: flex; flex-wrap: wrap; gap: .5rem; margin: 1.8rem 0 0; padding-top: 1rem;
  border-top: 1px solid var(--hairline); font-size: .9rem; }
.b-pager a { padding: .3rem .75rem; border: 1px solid var(--hairline); border-radius: 999px;
  text-decoration: none; }
.b-pager a:hover { border-color: var(--accent); color: var(--accent-strong); }

@media (max-width: 520px) {
  .b-secs a { grid-template-columns: 1.9rem 1fr auto; gap: .15rem .6rem; padding: .65rem .7rem; }
  .b-hero h1 { font-size: 1.6rem; }
  .b-filters { grid-template-columns: 1fr; }
  .b-bar { justify-content: space-between; }
  .b-prefs { right: .6rem; bottom: .6rem; }
  .b-prefs.lifted { bottom: 4.6rem; }
  .b-prefs-panel { max-width: calc(100vw - 1.2rem); }
  /* 长文页的表格在窄屏折成卡片：每格用 data-label 标出列名，手机不用横拖看 4 列表 */
  .b-tablewrap { overflow-x: visible; }
  .b-tablewrap table, .b-tablewrap tbody, .b-tablewrap tr, .b-tablewrap td { display: block; width: auto; }
  .b-tablewrap thead { display: none; }
  .b-tablewrap tr { border: 1px solid var(--hairline); border-radius: var(--radius-md);
                    padding: .55rem .7rem; margin: 0 0 .6rem; background: var(--paper); }
  .b-tablewrap td { border: 0; padding: .15rem 0; }
  .b-tablewrap td::before { content: attr(data-label) "："; color: var(--muted); font-size: .82rem; }
  .b-tablewrap td:empty { display: none; }
}
"""

GH_REPO = "https://github.com/Helioswei/HowToLiveBetter-Kit"

FAVICON = '<link rel="icon" type="image/svg+xml" href="https://assets.aigcwei.cn/favicon.svg">'
SHARED_CSS = '<link rel="stylesheet" href="https://assets.aigcwei.cn/style.css">'

# 放在 <head> 里的极小脚本（约 200 字节）：把用户存过的阅读偏好先套上，避免先亮后暗闪一下。
# 全站只有这一处（外加检索页自己的检索脚本）；正文不依赖任何 JS。
HEAD_PREFS = """<script>
(function(){try{var p=JSON.parse(localStorage.getItem('hltb.prefs')||'{}'),h=document.documentElement;
if(p.size)h.setAttribute('data-size',p.size);
if(p.leading)h.setAttribute('data-leading',p.leading);
if(p.theme)h.setAttribute('data-theme',p.theme);}catch(e){}})();
</script>"""



# 页尾的阅读设置那一行：字号 / 行距 / 主题 + 朗读。
# 正文不依赖它（没有 JS 时这一行不出现，页面照读）；设置只存在浏览器里。
# ⚠️ 必须是 raw 字符串：下面是嵌进去的 JavaScript，里面有 /\s+/g 这种 JS 正则
# 和非 raw 字符串里会被 Python 当"非法转义序列"告警（SyntaxWarning/DeprecationWarning）。
# 同理，\u3002 交给 JS 自己解，Python 在 raw 下不会动它。
BODY_PREFS = r"""<script>
(function(){
  var K='hltb.prefs', h=document.documentElement;
  function load(){try{return JSON.parse(localStorage.getItem(K)||'{}')||{}}catch(e){return {}}}
  var p=load();
  function sel(id,label,opts){var s='<label>'+label+'<select id="'+id+'">';
    for(var i=0;i<opts.length;i++){s+='<option value="'+opts[i][0]+'">'+opts[i][1]+'</option>';}
    return s+'</select></label>';}
  var box=document.createElement('div'); box.className='b-prefs';
  box.innerHTML='<div class="b-prefs-panel" hidden>'
    +'<span class="b-sep" id="b-say">设置只存在你自己的浏览器里</span>'
    +sel('b-size','字号',[['s','小'],['','标准'],['l','大'],['xl','特大']])
    +sel('b-leading','行距',[['','标准'],['w','宽']])
    +sel('b-theme','主题',[['','跟随系统'],['light','浅色'],['dark','深色']])
    +'<button type="button" id="b-speak">朗读</button></div>'
    +'<button type="button" id="b-toggle" aria-expanded="false">阅读设置</button>';
  if(document.getElementById('bar')) box.className+=' lifted';  // 检索页底部有操作条，抬起来
  document.body.appendChild(box);
  var panel=box.querySelector('.b-prefs-panel'), toggle=box.querySelector('#b-toggle');
  function flip(open){ panel.hidden=!open; toggle.setAttribute('aria-expanded', open?'true':'false'); }
  toggle.addEventListener('click', function(){ flip(panel.hidden); });
  document.addEventListener('click', function(ev){ if(!box.contains(ev.target)) flip(false); });
  document.addEventListener('keydown', function(ev){ if(ev.key==='Escape') flip(false); });

  var size=box.querySelector('#b-size'), lead=box.querySelector('#b-leading'), theme=box.querySelector('#b-theme');
  var say=box.querySelector('#b-say');
  size.value=p.size||''; lead.value=p.leading||''; theme.value=p.theme||'';
  function set(a,v){ if(v) h.setAttribute(a,v); else h.removeAttribute(a); }
  function apply(){ set('data-size',size.value); set('data-leading',lead.value); set('data-theme',theme.value); }
  function save(){ p.size=size.value; p.leading=lead.value; p.theme=theme.value;
    try{ localStorage.setItem(K, JSON.stringify(p)); }catch(e){} apply(); }
  size.addEventListener('change',save); lead.addEventListener('change',save); theme.addEventListener('change',save);
  apply();

  var sp=box.querySelector('#b-speak');
  if(!('speechSynthesis' in window) || !window.SpeechSynthesisUtterance){ sp.style.display='none'; return; }
  var MAX=2500, speaking=false;
  sp.addEventListener('click', function(){
    if(speaking){ window.speechSynthesis.cancel(); speaking=false; sp.textContent='朗读'; return; }
    var parts=[].slice.call(document.querySelectorAll('.b-human'));   // 节页：读每条的说人话
    var text=parts.length ? parts.map(function(e){return e.innerText.trim();}).join('\u3002')
                          : ((document.querySelector('article.article')||{}).innerText||'');
    text=(text||'').replace(/\s+/g,' ').trim();
    if(!text){ say.textContent='这一页没有可朗读的文字'; return; }
    var cut=false;
    if(text.length>MAX){ text=text.slice(0,MAX); cut=true; }
    var u=new SpeechSynthesisUtterance(text);
    u.lang='zh-CN'; u.rate=1; u.pitch=1;
    u.onend=function(){ speaking=false; sp.textContent='朗读'; say.textContent=cut?'前面太长，只读了前半段':'设置只存在你自己的浏览器里'; };
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
    speaking=true; sp.textContent='停止';
    say.textContent=cut?'内容较长，只读前半段':'正在朗读…';
  });
})();
</script>"""


def page(title, desc, body, base, path, ld=None, depth=0, extra_js=False, with_legal=True, kind="list"):
    """一个页面。path 是相对站点根的路径（如 "08/18.html"），用来算相对前缀与 canonical。"""
    up = "../" * depth
    canonical = "%s/%s" % (base, path) if not path.endswith("index.html") else \
        "%s/%s" % (base, path.rsplit("index.html", 1)[0])
    import re as _re

    canonical = _re.sub(r"/+$", "/", canonical)
    # 自动收录的长文用中文文件名（URL 更可读、百度也认），canonical 里必须百分号编码
    from urllib.parse import quote as _quote
    canonical = _quote(canonical, safe="/:%")
    ld_block = ""
    if ld:
        ld_block = '<script type="application/ld+json">\n%s\n</script>\n' % json.dumps(ld, ensure_ascii=False, indent=2)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  {FAVICON}
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(desc[:200])}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:title" content="{html.escape(title)}">
  <meta property="og:description" content="{html.escape(desc[:200])}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canonical}">
  <meta property="og:site_name" content="{html.escape(hltb.TITLE)}">
  <meta property="og:image" content="{base}/og.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="《{html.escape(hltb.TITLE)}》在线阅读：按性价比排序的建议">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:image" content="{base}/og.png">
  {SHARED_CSS}
  <link rel="stylesheet" href="{up}style.css?v={STYLE_VERSION}">
{HEAD_PREFS}
{ld_block}</head>
<body class="p-{kind}" data-site="better">
  <nav class="b-topbar" aria-label="本站导航">
    <div class="container b-topbar-inner">
      <a class="b-brand" href="{up}index.html">{html.escape(hltb.TITLE)}</a>
      <div class="b-links">
        <a href="{up}scenes/">场景</a>
        <a href="{up}map.html">分布图</a>
        <a href="{up}search.html">检索</a>
        <a href="{up}download.html">下载</a>
        <a href="{up}about.html">关于与许可</a>
        <a href="{GH_REPO}" target="_blank" rel="noopener">GitHub 仓库</a>
      </div>
    </div>
  </nav>

  <main>
    <div class="container">
{body}
      <div class="b-smallprint">
        <p>转载《{html.escape(hltb.TITLE)}》· 作者 eternity4719 · 正文未改动 · <a href="{up}about.html">署名与许可</a></p>
        {('<p>%s</p>' % DISCLAIMER) if with_legal else ''}
      </div>
    </div>
  </main>

  {BODY_PREFS}
  <div id="site-footer"></div>
</body>
</html>
"""


try:
    MAP_JS = open(os.path.join(ROOT, "tools", "map.js"), encoding="utf-8").read()
except OSError:
    MAP_JS = ""


def map_json(entries):
    """交互图的数据（/map.json）：每条一行，只放画图与跳转要用的。
    [url, 节, 条, 标题, 投入分, 收益, 档]  —— 悬停不出卡片了，所以不带正文（省 3/4 体积）"""
    rows = []
    for e in entries:
        said = re.sub(r"\s+", " ", (e["fields"].get("说人话") or e["title"])).strip()
        rows.append(["%02d/%02d.html" % (e["sec"], e["num"]), e["sec"], e["num"], e["title"],
                     e["cost"], e["tags"].get("收益", "中"), e["ratio"],
                     e["lv"], said[:70]])
    return rows


def scatter_svg(entries, w=760, h=420, dot_max=34, pad=(56, 34, 42, 74), font=13, dot_link=False):
    """把 676 条画成「投入 × 收益」的气泡图（静态 SVG，零 JS）。

    横轴 = 书里算的投入分（钱 / 时间 / 毅力按上游权重相加，0–6）；
    纵轴 = 收益（小 / 中 / 大）。**颜色是书里自己算出的性价比档** —— 因为书里的档就是
    由这两维推出来的（收益大 + 投入 0 = 极高），所以这张图等于把那套算法摊开给人看。
    气泡面积 ∝ 条数；每格带 <title>，鼠标悬停能看到"多少条、书里算什么档"。
    """
    from collections import Counter
    cells = Counter((e["cost"], e["tags"].get("收益", "中")) for e in entries)
    ratios = {(e["cost"], e["tags"].get("收益", "中")): e["ratio"] for e in entries}
    l, r, t, b = pad
    iw, ih = w - l - r, h - t - b
    ys = {"大": 0, "中": 1, "小": 2}
    n_max = max(cells.values()) if cells else 1
    col = {"极高": "var(--accent)", "高": "var(--ink-secondary)", "一般": "var(--muted)"}
    out = ['<svg class="b-scatter" viewBox="0 0 %d %d" role="img" aria-label="676 条建议的性价比分布">' % (w, h)]
    # 网格：横轴 0–6（投入），纵轴 收益 三档
    for cx in range(7):
        x = l + iw * cx / 6
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--hairline-soft)"/>'
                   % (x, t, x, t + ih))
        out.append('<text x="%.1f" y="%.1f" font-size="%d" fill="var(--muted)" text-anchor="middle">%d</text>'
                   % (x, t + ih + 22, font, cx))
    for name, i in ys.items():
        y = t + ih * (i + 0.5) / 3
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--hairline-soft)"/>'
                   % (l, y, l + iw, y))
        out.append('<text x="%.1f" y="%.1f" font-size="%d" fill="var(--ink-secondary)">%s</text>'
                   % (l - 12, y + 5, font + 1, name))
    for (cost, ben), n in sorted(cells.items()):
        cx = l + iw * cost / 6
        cy = t + ih * (ys[ben] + 0.5) / 3
        rr = dot_max * (n / n_max) ** 0.5
        ratio = ratios.get((cost, ben), "")
        tip = "投入 %d × 收益%s：%d 条（书里算「%s」）" % (cost, ben, n, ratio)
        out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" fill-opacity="%.2f" '
                   'stroke="var(--paper)" stroke-width="1.5"><title>%s</title></circle>'
                   % (cx, cy, rr, col.get(ratio, "var(--muted)"),
                      {"极高": 0.85, "高": 0.5}.get(ratio, 0.28), html.escape(tip, quote=True)))
    out.append('<text x="%.1f" y="%.1f" font-size="%d" fill="var(--muted)" text-anchor="middle">'
               '投入（钱 / 时间 / 毅力 按书里的权重相加）</text>' % (l + iw / 2, h - 8, font))
    out.append("</svg>")
    return "\n".join(out)


def map_body(b, entries, base):
    """性价比分布图：canvas 交互（悬停出条目、点开、按档筛、拖拽缩放）。
    没有 JS 时 <noscript> 里是同一套数据的静态 SVG —— 页面不会空，搜索引擎和打印也看得到。"""
    from collections import Counter
    tally = Counter(e["ratio"] for e in entries)
    n = len(entries)
    legend = f"""<p class="b-legend">
        <span><i class="b-lg-dot" style="background:var(--accent)"></i>书里算「极高」{tally.get('极高', 0)}</span>
        <span><i class="b-lg-dot" style="background:var(--ink-secondary)"></i>「高」{tally.get('高', 0)}</span>
        <span><i class="b-lg-dot" style="background:var(--muted)"></i>「一般」{tally.get('一般', 0)}</span>
        <span class="b-lg-note">气泡大小 = 这一格有多少条　·　拖动平移　·　滚轮缩放</span>
      </p>"""
    return f"""      <nav class="breadcrumb"><a href="./">目录</a> <span class="sep">›</span> <span class="cur">性价比分布</span></nav>
      <div class="b-hero">
        <h1>性价比分布</h1>
        <p>把全部 {n} 条点在一张图上：横轴是<strong>投入</strong>（钱 / 时间 / 毅力按书里的权重相加，0–6），
           纵轴是<strong>收益</strong>，颜色是<strong>书里算出的性价比档</strong> —— 书里的档就是这两维推出来的，
           所以这张图等于把那套算法摊开给人看。<strong>鼠标移到点上会高亮，点一下就打开那一条</strong>；
           也可以只看某一档。</p>
      </div>
      <div class="b-mapbar" hidden>
        <button type="button" data-ratio="all" class="on">全部 {n}</button>
        <button type="button" data-ratio="极高">极高 {tally.get('极高', 0)}</button>
        <button type="button" data-ratio="高">高 {tally.get('高', 0)}</button>
        <button type="button" data-ratio="一般">一般 {tally.get('一般', 0)}</button>
        <button type="button" data-reset="1">重置视图</button>
      </div>
      <div class="b-mapwrap" hidden>
        <canvas id="hltb-map" class="b-mapcanvas" aria-label="{n} 条建议的性价比分布图"></canvas>
        <div class="b-mapcard" hidden></div>
      </div>
      <div class="b-mapstatic">
        <div class="b-scatterwrap">{scatter_svg(entries)}</div>
      </div>
      {legend}
      <p class="b-stat">书里的规则：收益「大」且投入 0 → <strong>极高</strong>（{tally.get('极高', 0)} 条）；
           收益「大」且投入 ≤2 → 高；收益「中」且投入 0 → 高；其余 → 一般。</p>
      <p class="b-stat"><a href="search.html#ratio=%E6%9E%81%E9%AB%98">只看这 {tally.get('极高', 0)} 条极高 →</a>
         　·　<a href="search.html">去检索全部 {n} 条 →</a></p>
      <script>{MAP_JS}</script>"""


def badge_html(e):
    g = e["tags"]
    bits = []
    if e.get("ratio"):
        bits.append('<span class="b-badge top">性价比 %s</span>' % e["ratio"])
    for label, key, cls in (("钱", "钱", ""), ("时间", "时间", ""), ("毅力", "毅力", "")):
        if key in g:
            bits.append('<span class="b-badge %s">%s %s</span>' % (cls, label, g[key]))
    if "收益" in g:
        bits.append('<span class="b-badge">收益 %s</span>' % g["收益"])
    if "口径" in g:
        bits.append('<span class="b-badge ku">%s</span>' % g["口径"])
    bits.append('<span class="b-badge lv">证据 %s</span>' % html.escape(e["lvNote"] or e["lv"]))
    return '<div class="b-badges">%s</div>' % "".join(bits)


def paras(text, sec, titles, on_section=True):
    if not text:
        return ""
    return "".join("<p>%s</p>" % hltb.inline(p, sec, titles, on_section)
                   for p in hltb.split_paras(text))



DISCLAIMER = ("医学与法律内容仅供一般参考，不构成诊疗意见或法律意见；"
              "个案请咨询执业医师、律师或当地主管部门。")

# 节首导览的形状（上游写法，别改）：**组名**：条目A（第 N 条），条目B（第 M 条），…。
RE_GROUP = re.compile(r"^\*\*(?P<name>[^*\n]{1,40}?)\*\*：(?P<body>.+)$", re.S)
RE_INTRO_ITEM = re.compile(r"(?P<text>.+?（第\s*(?P<n>\d+)\s*条）)(?P<sep>[，,。；;、]|$)", re.S)


# ---------------------------------------------------------------- 各类页面

def entry_body(b, e, titles):
    f = e["fields"]
    sec = e["sec"]
    hidden = ""   # 来源 / 备注 收进折叠区（收益是证据，留在正文里）
    for label in ("来源", "备注"):
        if f.get(label):
            hidden += '<div class="b-fl"><b>%s</b>%s</div>' % (label, paras(f[label], sec, titles, False))
    if e["xrefs"]:
        refs = []
        for s, n in e["xrefs"]:
            t = titles.get((s, n))
            href = "%02d.html" % n if s == sec else "../%02d/%02d.html" % (s, n)
            refs.append('<a class="b-ref" href="%s" title="%s">第 %d 节第 %d 条</a>'
                        % (href, html.escape(t or ""), s, n))
        hidden += '<div class="b-fl"><b>这一条还指向</b><p class="b-refs-inline">%s</p></div>' % " ".join(refs)
    return f"""      <nav class="breadcrumb"><a href="../">目录</a> <span class="sep">›</span> <a href="./">第 {sec} 节 {html.escape(e['sec_title'])}</a> <span class="sep">›</span> <span class="cur">{e['num']}</span></nav>
      <article class="article b-entry-page">
        <header class="article-header">
          <h1>{html.escape(e['title'])}</h1>
          <p class="article-meta"><span>第 {sec} 节第 {e['num']} 条</span></p>
        </header>
        {badge_html(e)}
        <div class="article-body">
          {('<div class="b-lead">%s</div>' % paras(f['说人话'], sec, titles, False)) if f.get('说人话') else ''}
          {('<div class="b-fl"><b>成本</b>%s</div>' % paras(f['成本'], sec, titles, False)) if f.get('成本') else ''}
          {('<div class="b-fl"><b>收益</b>%s</div>' % paras(f['收益'], sec, titles, False)) if f.get('收益') else ''}
          {('<details class="b-more"><summary>来源与备注</summary>%s</details>' % hidden) if hidden else ''}
        </div>
        <p class="b-perma">原文出处：<a href="{b['source']['repo']}" target="_blank" rel="noopener nofollow">{html.escape(hltb.TITLE)}</a></p>
        <nav class="b-pager">{e['pager']}</nav>
      </article>"""


RE_MD_H = re.compile(r"^(#{1,6})\s+(.+)$")
RE_MD_UL = re.compile(r"^\s*[-*]\s+(.+)$")
RE_MD_OL = re.compile(r"^\s*\d+\.\s+(.+)$")
RE_MD_TBL_SEP = re.compile(r"^\s*\|[\s:|-]+\|\s*$")


def md_blocks(text):
    """把上游长文切成块。只认它们**实际用到**的语法：标题 / 段落 / 无序列表 / 有序列表 / 表格
    （实测这 5 篇没有代码块、图片、引用块）。切块是为了让每个块都能单独排版 + 被保真校验逐块比对。
    """
    # 相对链接（如 [核实记录](核实记录/追加-第26节做平台.md)）交给 hltb.inline 处理：
    # 它优先指回我们自己的那一页，没登记的才指上游原文。
    text = re.sub(r"(?m)^\[← 回总目录\]\([^)]*\)\s*$", "", text)   # 上游仓库内的返回链接
    lines = text.replace("\r\n", "\n").split("\n")
    blocks, i = [], 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        m = RE_MD_H.match(line)
        if m:
            blocks.append(("h", len(m.group(1)), m.group(2).strip()))
            i += 1
            continue
        if line.strip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = lines[i].strip()
                if not RE_MD_TBL_SEP.match(row):     # 表头下的 |---|---| 是排版符号，不进内容
                    rows.append([c.strip() for c in row.strip("|").split("|")])
                i += 1
            blocks.append(("table", rows))
            continue
        m = RE_MD_UL.match(line)
        if m:
            items = []
            while i < len(lines) and RE_MD_UL.match(lines[i].rstrip()):
                items.append(RE_MD_UL.match(lines[i].rstrip()).group(1).strip())
                i += 1
            blocks.append(("ul", items))
            continue
        m = RE_MD_OL.match(line)
        if m:
            items = []
            while i < len(lines) and RE_MD_OL.match(lines[i].rstrip()):
                items.append(RE_MD_OL.match(lines[i].rstrip()).group(1).strip())
                i += 1
            blocks.append(("ol", items))
            continue
        para = []
        while i < len(lines) and lines[i].strip() and not RE_MD_H.match(lines[i].rstrip()) \
                and not RE_MD_UL.match(lines[i]) and not RE_MD_OL.match(lines[i]) \
                and not lines[i].strip().startswith("|"):
            para.append(lines[i].strip())
            i += 1
        blocks.append(("p", " ".join(para)))
    return blocks


def longform_body(b, doc, titles, longform):
    """长文页：上游 docs/ 里的清单/长文（不是按时间排的场景）。一个字不改，只重排版式。"""
    parts = []
    for blk in doc["blocks"]:
        kind = blk[0]
        if kind == "h":
            lvl, txt = blk[1], blk[2]
            if lvl == 1:                          # 文里的 H1 已经用作页面标题了
                continue
            parts.append("<h%d>%s</h%d>" % (3 if lvl >= 3 else 2, hltb.inline(txt, 0, titles), 3 if lvl >= 3 else 2))
        elif kind == "p":
            parts.append("<p>%s</p>" % hltb.inline(blk[1], 0, titles))
        elif kind in ("ul", "ol"):
            tag = "ul" if kind == "ul" else "ol"
            parts.append("<%s>%s</%s>" % (tag, "".join("<li>%s</li>" % hltb.inline(x, 0, titles) for x in blk[1]), tag))
        elif kind == "table":
            rows = blk[1]
            if not rows:
                continue
            heads = rows[0]
            head = "".join("<th>%s</th>" % hltb.inline(c, 0, titles) for c in heads)
            # 每格带 data-label=列名：窄屏下 CSS 把表格折成卡片（手机不用横拖）
            body = "".join("<tr>%s</tr>" % "".join(
                '<td data-label="%s">%s</td>' % (html.escape(heads[i] if i < len(heads) else ""),
                                                 hltb.inline(c, 0, titles))
                for i, c in enumerate(r)) for r in rows[1:])
            parts.append('<div class="b-tablewrap"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
                         % (head, body))
    others = "".join('<li><a href="%s.html">%s</a></li>' % (d["url"], html.escape(d["title"]))
                     for d in longform if d["base"] != doc["base"])
    return f"""      <nav class="breadcrumb"><a href="../index.html">目录</a> <span class="sep">›</span> <a href="../scenes/">按场景看</a> <span class="sep">›</span> <span class="cur">{html.escape(doc['title'][:14])}</span></nav>
      <div class="b-hero">
        <h1>{html.escape(doc['title'])}</h1>
      </div>
      <div class="article-body">
{chr(10).join('        ' + x for x in parts)}
      </div>
      <!-- 来源：{html.escape(doc['file'])}（机器可读的来源声明：保真校验照它比对；读者要核对走页脚的「署名与许可」） -->
      <p class="b-stat"><a href="../scenes/">← 返回按场景看</a></p>"""


def intro_html(intro, sec, titles, ratios):
    """节首导览的排版。

    上游把「分组清单」写成了一整句：「**组名**：条目A（第 N 条），条目B（第 M 条），…。」
    照字面渲染就是一屏散落的小药丸。这里**一个字都不动**，只按它本来就有的结构重排：
    组名做小标题、每个条目（连它的括号编号）做成一个可点的 chip、逗号原样留在 chip 之间。
    形态不符的段落照旧当普通段落渲染（所以上游改写法也不会崩）。
    """
    out = []
    for p in hltb.split_paras(intro or ""):
        m = RE_GROUP.match(p.strip())
        if not m:
            out.append("<p>%s</p>" % hltb.inline(p, sec, titles))
            continue
        pieces, hit = [], False
        for it in RE_INTRO_ITEM.finditer(m.group("body")):
            hit = True
            text, n = it.group("text"), int(it.group("n"))
            head = re.sub(r"（第\s*\d+\s*条）$", "", text)
            num = text[len(head):]
            cls = "b-chip" + (" top" if ratios.get((sec, n)) == "极高" else "")
            inner = '%s<span class="b-ref-n">%s</span>' % (hltb.inline(head, sec, titles), html.escape(num))
            title = titles.get((sec, n))
            if title:  # 目标条目确实存在才做链接（不存在就原样，不去猜）
                pieces.append('<a class="%s" href="#e%d" title="%s">%s</a>' % (cls, n, html.escape(title), inner))
            else:
                pieces.append('<span class="%s">%s</span>' % (cls, inner))
            # 原文里条目之间是「，」、段末是「。」：这些**列表分隔标点按排版隐藏**（用户拍过），
            # 一个字的内容都没丢 —— 只是 chip 之间用留白分隔更干净。
            # check_site 的「导览保真」知道这条规则（分组段比对时两边都去掉这几个标点），
            # 说明段照旧严格比对（那里的标点不许动）。
        if not hit:  # 这个"组"里没有条目指路 → 别硬套 chip，照旧
            out.append("<p>%s</p>" % hltb.inline(p, sec, titles))
            continue
        out.append('<div class="b-group"><h3 class="b-group-t">%s<span class="b-sep-c">：</span></h3><p class="b-items">%s</p></div>'
                   % (hltb.inline(m.group("name"), sec, titles), "".join(pieces)))
    return "".join(out)


def section_body(b, sec, titles):
    ratios = {(sec["num"], e["num"]): e.get("ratio") for e in sec["entries"]}
    items = []
    for e in sec["entries"]:
        f = e["fields"]
        extra = ""
        for label in ("收益", "来源", "备注"):
            if f.get(label):
                extra += '<div class="b-fl"><b>%s</b>%s</div>' % (label, paras(f[label], sec["num"], titles))
        top = ' is-top' if e.get("ratio") == "极高" else ''
        items.append(f"""      <section class="b-entry{top}" id="e{e['num']}">
        <h3><a class="b-num" href="#e{e['num']}" title="锚点：本页第 {e['num']} 条">{e['num']}.</a> {html.escape(e['title'])}</h3>
        {badge_html(e)}
        {('<p class="b-human">%s</p>' % hltb.inline(f['说人话'], sec['num'], titles)) if f.get('说人话') else ''}
        {('<p class="b-cost">成本：%s</p>' % hltb.inline(f['成本'], sec['num'], titles)) if f.get('成本') else ''}
        <details class="b-more"><summary>收益 / 来源 / 备注</summary>{extra}</details>
        <p class="b-perma"><a href="{e['num']:02d}.html">单独打开这条 →</a></p>
      </section>""")
    prev_l = next((s for s in b["sections"] if s["num"] == sec["num"] - 1), None)
    next_l = next((s for s in b["sections"] if s["num"] == sec["num"] + 1), None)
    pager = ""
    if prev_l:
        pager += '<a href="../%02d/">← 第 %d 节 %s</a>' % (prev_l["num"], prev_l["num"], html.escape(prev_l["title"]))
    pager += '<a href="../">目录</a>'
    if next_l:
        pager += '<a href="../%02d/">第 %d 节 %s →</a>' % (next_l["num"], next_l["num"], html.escape(next_l["title"]))
    return f"""      <nav class="breadcrumb"><a href="../">目录</a> <span class="sep">›</span> <span class="cur">第 {sec['num']} 节</span></nav>
      <div class="b-hero">
        <h1>{sec['num']}. {html.escape(sec['title'])}</h1>
        {('<p class="b-q">这一节回答：%s</p>' % html.escape(sec['question'])) if sec['question'] else ''}
      </div>
      <div class="b-intro">
        {intro_html(sec['intro'], sec['num'], titles, ratios)}
      </div>
      <p class="b-stat">{len(sec['entries'])} 条，按性价比从高到低</p>
{chr(10).join(items)}
      <nav class="b-pager">{pager}</nav>"""


def scenes_index_body(b, scenes, longform=()):
    # 场景页与长文页用**同一种卡片**，一个网格里排下来；卡片上那句"5 个时间段 · 34 步"
    # 是内容自身的描述，不是我们的分类规则（分类规则不该出现在页面上）。
    cards = "".join(
        '<a class="b-scene-card" href="%s.html"><b>%s</b><span>%d 个时间段 · %d 步</span></a>'
        % (sc["url"], html.escape(sc["title"]), len(sc["sections"]),
           sum(len(x["steps"]) for x in sc["sections"]))
        for sc in scenes)
    cards += "".join(
        '<a class="b-scene-card" href="../articles/%s.html"><b>%s</b><span>%d 个部分</span></a>'
        % (d["url"], html.escape(d["title"]),
           sum(1 for x in d["blocks"] if x[0] == "h" and x[1] == 2))
        for d in longform)
    return f"""      <nav class="breadcrumb"><a href="../index.html">目录</a> <span class="sep">›</span> <span class="cur">按场景看</span></nav>
      <div class="b-hero">
        <h1>按场景看</h1>
        <p>不知道从哪下手的时候，从"我正在经历什么"进。这些都是《{html.escape(hltb.TITLE)}》原文里已有的内容，
           <strong>未改动</strong>，只是把它们里的「见第 X 节第 Y 条」变成了可以点的链接。</p>
      </div>
      <div class="b-scenes">{cards}</div>"""


def scene_body(b, scene, scenes, titles):
    steps_html, refs = [], set()
    for sec in scene["sections"]:
        items = "".join("<li>%s</li>" % hltb.inline(x, 0, titles) for x in sec["steps"])
        tail = "".join(paras(x, 0, titles) for x in sec["paras"])
        steps_html.append('<section class="b-tl-step"><h2>%s</h2>%s%s</section>'
                          % (html.escape(sec["heading"]), tail, ("<ol>%s</ol>" % items) if items else ""))
        for x in sec["steps"]:
            for a_, b_ in hltb.RE_XREF_FAR.findall(x):
                refs.add((int(a_), int(b_)))
    chips = "".join(
        '<li><a href="../%02d/%02d.html">第 %d 节第 %d 条 %s</a>'
        '<span class="b-badge %s">性价比 %s</span></li>'
        % (sn, en, sn, en, html.escape(titles.get((sn, en), "")),
           "top" if RATIO.get((sn, en)) == "极高" else "", RATIO.get((sn, en), ""))
        for sn, en in sorted(refs))
    idx = [x["slug"] for x in scenes].index(scene["slug"])
    pager = '<a href="index.html">← 按场景看</a>'
    if idx > 0:
        pager += '<a href="%s.html">← %s</a>' % (scenes[idx - 1]["url"], html.escape(scenes[idx - 1]["title"]))
    if idx + 1 < len(scenes):
        pager += '<a href="%s.html">%s →</a>' % (scenes[idx + 1]["url"], html.escape(scenes[idx + 1]["title"]))
    return f"""      <nav class="breadcrumb"><a href="../index.html">目录</a> <span class="sep">›</span> <a href="index.html">按场景看</a> <span class="sep">›</span> <span class="cur">{html.escape(scene['title'][:12])}</span></nav>
      <div class="b-hero">
        <h1>{html.escape(scene['title'])}</h1>
        {paras(scene['intro'], 0, titles)}
        <p class="b-stat">按时间排 · 共 {len(scene['sections'])} 个时间段 {sum(len(x['steps']) for x in scene['sections'])} 步
           　·　每步都链到书里对应的条目</p>
      </div>
      <div class="b-tl">{''.join(steps_html)}</div>
      <div class="b-refs"><h2>这一篇引用了这些条目（{len(refs)} 条）</h2><ul>{chips}</ul></div>
      <!-- 来源：{html.escape(scene['file'])}（机器可读的来源声明：保真校验照它比对；读者要核对走页脚的「署名与许可」） -->
      <nav class="b-pager">{pager}</nav>"""


def index_body(b):
    total = len(b["entries"])
    top = sum(1 for e in b["entries"] if e.get("ratio") == "极高")
    scenes = b.get("scenes") or []
    scene_cards = ""
    if scenes:
        cards = "".join(
            '<a class="b-scene-card" href="scenes/%s.html"><b>%s</b><span>%d 个时间段 · %d 步</span></a>'
            % (sc["url"], html.escape(sc["title"]), len(sc["sections"]),
               sum(len(x["steps"]) for x in sc["sections"]))
            for sc in scenes)
        scene_cards = ('<h2 class="b-h2">按场景看（不知道从哪下手就从这里进）</h2>'
                       '<div class="b-scenes">%s</div>'
                       '<p class="b-stat" style="margin-top:.6rem"><a href="scenes/">全部场景 →</a></p>' % cards)
    rows = "".join(
        '<li><a href="%02d/"><span class="b-sn">%02d</span><span class="b-st">%s</span>'
        '<span class="b-sc">%d 条</span><span class="b-sq">%s</span></a></li>'
        % (s["num"], s["num"], html.escape(s["title"]), len(s["entries"]), html.escape(s["question"]))
        for s in b["sections"])
    return f"""      <div class="b-hero">
        <h1>{html.escape(hltb.TITLE)}</h1>
        <p class="b-lede">按性价比排序的 {total} 条循证建议。
           每条写明花掉什么、换回什么、证据有多硬，来源只引期刊论文与官方文件。</p>
        <div class="b-cta">
          <a class="b-btn primary" href="search.html#ratio=%E6%9E%81%E9%AB%98">我该做哪几条（{top} 条零成本高收益）</a>
        </div>
        <p class="b-meta">
          <span>共 {len(b['sections'])} 节 {total} 条</span>
        </p>
      </div>
      {scene_cards}
      <h2 class="b-h2">全部 {len(b['sections'])} 节</h2>
      <ol class="b-secs">{rows}</ol>"""


def about_body(b):
    src = b["source"]
    return f"""      <nav class="breadcrumb"><a href="./">目录</a> <span class="sep">›</span> <span class="cur">关于与许可</span></nav>
      <div class="b-hero">
        <h1>关于本站与许可</h1>
      </div>
      <div class="article-body">
        <h2>这是转载</h2>
        <p><strong>本站是第三方转载</strong>：与作者、与原始仓库没有关系；书名与作者署名只用于说明出处。
           上游要求转载时写明出处、附许可链接、说明是否改动 —— 三件都在下面写清。</p>
        <p>本站正文全部来自 <a href="{src['repo']}" target="_blank" rel="noopener nofollow">eternity4719/HowToLiveBetter</a>
           （《{html.escape(hltb.TITLE)}》），按
           <a href="{src['license_url']}" target="_blank" rel="noopener nofollow">{src['license']}</a> 许可转载。
           <strong>正文与上游逐字一致，没有任何内容改动</strong>；本站只做了四件事：重排版式、加导航、加检索、给每一条生成独立链接。</p>
        <h2>署名</h2>
        <p>作品：《{html.escape(hltb.TITLE)}》。作者：{src['author']}。原始仓库：
           <a href="{src['repo']}">{src['repo']}</a>。许可：{src['license']}
           （<a href="{src['license_url']}">{src['license_url']}</a>）。<br>
           本站同步的上游版本：<code>{src.get('commit_short') or '?'}</code>（{src.get('commit_date') or ''}）。
           正本以原始仓库为准，本站可能滞后。</p>
        <h2>免责</h2>
        <p>书中内容涉及医学、法律、社保、理财等专业领域，仅为一般性参考，<strong>不构成诊疗意见、法律意见或投资建议</strong>。
           具体情形请咨询执业医师、律师或当地主管部门，以官方文件原文为准。</p>
        <h2>本站做了什么、没做什么</h2>
        <ul>
          <li>没改正文：一个字都没动，可以逐字比对（<a href="https://github.com/Helioswei/HowToLiveBetter-Kit" target="_blank" rel="noopener">校验脚本</a>公开）。</li>
          <li>没做判断：条目的性价比、证据等级、口径全部是书上自己的标签，本站只做展示与筛选。</li>
          <li>不同口径之间不比较：这是书里的规定，本站也不替读者排「哪个更值」。</li>
        </ul>
        <h2>为什么不直接看上游</h2>
        <p>上游的在线阅读页需要浏览器实时拉取 34 个正文文件才能显示内容，弱网和手机流量下容易中断，
           内容也不在搜索引擎的收录范围里。本站把每一节和每一条都预先渲染成独立页面，
           因此可以被搜到、可以被单独分享，弱网下打开一页也只需要一次请求。</p>
      </div>"""


def download_body(b):
    src = b["source"]
    def card(f, name, url, why):
        return ('<li><a href="%s"><b>%s</b><em class="b-dl-size" data-file="%s"></em>'
                '<span>%s</span></a></li>' % (url, name, f, why))
    return f"""      <nav class="breadcrumb"><a href="./">目录</a> <span class="sep">›</span> <span class="cur">下载</span></nav>
      <div class="b-hero">
        <h1>下载电子版</h1>
        <p class="b-stat">下面几份由上游在正文更新后自动重新生成，本站做了国内镜像（打开更快）。
           对应上游版本 <code>{src.get('commit_short') or '?'}</code>（{src.get('commit_date') or ''}）。</p></div>
      <div class="article-body">
        <ul class="b-dl">
          {card('HowToLiveBetter.epub', 'EPUB', 'download/HowToLiveBetter.epub',
                '手机阅读器 / Kindle：用 Send to Kindle 发过去即可')}
          {card('HowToLiveBetter.pdf', 'PDF', 'download/HowToLiveBetter.pdf',
                'A4 排版、带目录页码，适合打印或存档')}
          {card('HowToLiveBetter.html', '离线单文件 HTML', 'download/HowToLiveBetter.html',
                '整本书连同检索都在一个文件里，下载后用浏览器打开（电脑上双击即可），不需要联网')}
          {card('HowToLiveBetter.apkg', 'Anki 牌组', 'download/HowToLiveBetter.apkg',
                '一条一张卡，按节分子牌组，适合反复复习')}
        </ul>
        <p class="b-stat" data-dl-total></p>
        <p>镜像失败时请直接到上游下载：<a href="{b['source']['repo']}/releases" target="_blank" rel="noopener nofollow">上游 Release</a>。这些文件是<strong>快照</strong>：转发出去的那一份不会跟着更新，以在线版为准。</p>
      </div>"""


def search_body(cfg):
    """检索 + 我的清单。

    两条模式：
      探索 —— 筛选 + 打勾（勾选存在本地，不上传）
      清单 —— 打开带 #p=01.03,05.12 的链接时直接进这个模式，按书的顺序列出被选中的条目
    分享链接零后端：勾选状态就编码在 URL 片段里。
    """
    body = r"""      <nav class="breadcrumb"><a href="./">目录</a> <span class="sep">›</span> <span class="cur">检索与我的清单</span></nav>
      <div class="b-hero"><h1>检索与我的清单</h1>
        <p class="b-lede">按关键词、成本、证据等级、口径筛这 __TOTAL__ 条；看中的打勾，就成了「我的清单」。</p>
        <div class="b-presets">
          <button type="button" data-preset="top">性价比「极高」（__TOP__ 条）</button>
          <button type="button" data-preset="a">只看证据 A 级</button>
          <button type="button" data-preset="mine">只看我的清单</button>
          <button type="button" data-preset="clear">清空条件</button>
        </div>
        <p class="b-meta"><span>改了条件就即时生效，不用点搜索</span>
          <span>勾选只存在你自己的浏览器里，不会上传</span>
          <span>要发给别人就复制分享链接</span></p>
      </div>
      <form class="b-filters" id="f">
        <fieldset><legend>关键词</legend><input type="search" id="q" name="q" placeholder="戒烟 / 担保 / 产假" style="width:12rem"></fieldset>
        <fieldset><legend>钱</legend><label><input type="checkbox" name="money" value="0">不花</label><label><input type="checkbox" name="money" value="少">少</label><label><input type="checkbox" name="money" value="多">多</label></fieldset>
        <fieldset><legend>时间</legend><label><input type="checkbox" name="time" value="少">少</label><label><input type="checkbox" name="time" value="中">中</label><label><input type="checkbox" name="time" value="多">多</label></fieldset>
        <fieldset><legend>毅力</legend><label><input type="checkbox" name="will" value="否">否</label><label><input type="checkbox" name="will" value="些">些</label><label><input type="checkbox" name="will" value="是">是</label></fieldset>
        <fieldset><legend>收益</legend><label><input type="checkbox" name="benefit" value="大">大</label><label><input type="checkbox" name="benefit" value="中">中</label><label><input type="checkbox" name="benefit" value="小">小</label></fieldset>
        <fieldset><legend>证据</legend><label><input type="checkbox" name="evidence" value="A">A</label><label><input type="checkbox" name="evidence" value="B">B</label><label><input type="checkbox" name="evidence" value="C">C</label></fieldset>
        <fieldset><legend>口径</legend><label><input type="checkbox" name="caliber" value="死亡率">死亡率</label><label><input type="checkbox" name="caliber" value="金钱">金钱</label><label><input type="checkbox" name="caliber" value="时间">时间</label><label><input type="checkbox" name="caliber" value="自由">自由</label></fieldset>
        <fieldset><legend>性价比</legend><label><input type="checkbox" name="ratio" value="极高">极高</label><label><input type="checkbox" name="ratio" value="高">高</label><label><input type="checkbox" name="ratio" value="一般">一般</label></fieldset>
      </form>
      <p class="b-stat" id="count">正在载入索引…</p>
      <div id="hits"></div>
      <div class="b-bar" id="bar">
        <span class="b-count" id="mycount">已选 0 条</span>
        <button type="button" id="share" disabled>复制分享链接</button>
        <button type="button" id="copy" disabled>复制清单文本</button>
        <button type="button" id="reset" disabled>清空我的清单</button>
        <span class="b-hint" id="say"></span>
      </div>
      <p class="b-note">关键词是字面匹配，不是语义检索。不同口径之间不做比较（书里的规定）；
         勾选只存在你自己的浏览器里，没有账号、没有服务器。</p>
      <script>
      (function () {
        var CFG = __CFG__;
        var DATA = null, mode = 'explore', mine = {}, byKey = {};
        var form = document.getElementById('f'), hits = document.getElementById('hits');
        var FILTERS = ['money', 'time', 'will', 'benefit', 'evidence', 'caliber', 'ratio'];
        var cnt = document.getElementById('count'), mycount = document.getElementById('mycount'), say = document.getElementById('say');

        function loadMine() {
          try { mine = JSON.parse(localStorage.getItem('hltb.mine') || '{}') || {}; } catch (e) { mine = {}; }
        }
        function saveMine() {
          try { localStorage.setItem('hltb.mine', JSON.stringify(mine)); } catch (e) {}
        }
        function keyOf(e) { return e.s + '.' + e.n; }
        function esc(s) {
          return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
          });
        }
        function picked(name) {
          return Array.prototype.slice.call(form.querySelectorAll('input[name=' + name + ']:checked')).map(function (i) { return i.value; });
        }
        function badges(e) {
          var r = 'b-badge' + (e.r === '极高' ? ' top' : '');
          return '<div class="b-badges"><span class="' + r + '">性价比 ' + e.r + '</span>' +
                 '<span class="b-badge">收益 ' + e.g.b + '</span>' +
                 '<span class="b-badge">证据 ' + e.v + '</span>' +
                 '<span class="b-badge">' + e.k + '</span></div>';
        }
        function card(e) {
          var k = keyOf(e), on = !!mine[k];
          return '<div class="b-hit' + (on ? ' picked' : '') + '" data-k="' + k + '">' +
            '<div class="b-hit-head"><h3><a href="' + e.u + '">' + esc(e.t) + '</a></h3>' +
            '<label class="b-pick"><input type="checkbox" data-pick="' + k + '"' + (on ? ' checked' : '') + '>要做</label></div>' +
            badges(e) + '<p>' + esc(e.h) + '</p></div>';
        }
        function matches(e, q, f) {
          if (f.evidence.length && f.evidence.indexOf(e.v) < 0) return false;
          if (f.caliber.length && f.caliber.indexOf(e.k) < 0) return false;
          if (f.ratio.length && f.ratio.indexOf(e.r) < 0) return false;
          if (f.benefit.length && f.benefit.indexOf(e.g.b) < 0) return false;
          if (f.money.length && f.money.indexOf(e.g.m) < 0) return false;
          if (f.time.length && f.time.indexOf(e.g.t) < 0) return false;
          if (f.will.length && f.will.indexOf(e.g.w) < 0) return false;
          if (q && (e.t + e.h).toLowerCase().indexOf(q) < 0) return false;
          return true;
        }
        function render() {
          if (!DATA) return;
          var q = (document.getElementById('q').value || '').replace(/\s+/g, '').toLowerCase();
          var f = { money: picked('money'), time: picked('time'), will: picked('will'), benefit: picked('benefit'),
                    evidence: picked('evidence'), caliber: picked('caliber'), ratio: picked('ratio') };
          var out;
          if (mode === 'list') {
            out = DATA.filter(function (e) { return mine[keyOf(e)]; });
            cnt.textContent = '我的清单：' + out.length + ' 条（按书的顺序）';
          } else {
            out = DATA.filter(function (e) { return matches(e, q, f); });
            cnt.textContent = '命中 ' + out.length + ' 条' + (out.length > 60 ? '，只显示前 60 条（请加条件缩小范围）' : '');
            out = out.slice(0, 60);
          }
          hits.innerHTML = out.map(card).join('') ||
            '<p class="b-stat">' + (mode === 'list' ? '还没选任何条目。在检索里给想做的打勾，或者把别人发你的分享链接打开。' : '没有命中的条目，换个条件试试。') + '</p>';
          syncBar();
        }
        function setFilter(name, values) {
          form.querySelectorAll('input[name=' + name + ']').forEach(function (i) {
            i.checked = values.indexOf(i.value) >= 0;
          });
        }
        function setHash(keys) {
          var h = keys.length ? '#p=' + keys.slice().sort().join(',') : '';
          if (location.hash !== h) history.replaceState(null, '', location.pathname + location.search + h);
        }
        function tell(msg) { say.textContent = msg; }
        function syncBar() {
          var n = Object.keys(mine).length;
          mycount.textContent = '已选 ' + n + ' 条';
          ['share', 'copy', 'reset'].forEach(function (id) {
            document.getElementById(id).disabled = n === 0;
          });
        }

        document.addEventListener('change', function (ev) {
          var t = ev.target;
          if (t && t.getAttribute && t.getAttribute('data-pick')) {
            var k = t.getAttribute('data-pick');
            if (t.checked) mine[k] = 1; else delete mine[k];
            saveMine();
            var box = t.closest('.b-hit');
            if (box) box.classList[ t.checked ? 'add' : 'remove' ]('picked');
            syncBar();
            tell('');
          } else if (t && t.closest && t.closest('#f')) {
            render();
          }
        });
        document.getElementById('q').addEventListener('input', render);

        document.querySelector('.b-presets').addEventListener('click', function (ev) {
          var btn = ev.target.closest('button[data-preset]');
          if (!btn) return;
          var kind = btn.getAttribute('data-preset');
          if (kind === 'mine') {
            mode = 'list'; return render();
          }
          mode = 'explore';
          if (kind === 'top') { setFilter('ratio', ['极高']); setFilter('evidence', []); setFilter('caliber', []); setFilter('money', []); setFilter('time', []); setFilter('will', []); setFilter('benefit', []); }
          else if (kind === 'a') { setFilter('evidence', ['A']); setFilter('ratio', []); }
          else if (kind === 'clear') {
            ['money', 'time', 'will', 'benefit', 'evidence', 'caliber', 'ratio'].forEach(function (k) { setFilter(k, []); });
            document.getElementById('q').value = '';
          }
          render();
        });

        function copy(text, ok) {
          var ta = document.createElement('textarea');
          ta.readOnly = true;
          ta.style.cssText = 'width:100%;box-sizing:border-box;margin:.6rem 0 0;padding:.45rem;font:inherit;font-size:.8rem;border:1px solid var(--hairline);border-radius:6px;background:var(--paper)';
          ta.value = text;
          var bar = document.getElementById('bar');
          bar.parentNode.insertBefore(ta, bar);
          ta.focus(); ta.select();
          var done = false;
          try { done = document.execCommand('copy'); } catch (e) {}
          if (!done && navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(function () { done = true; tell(ok); }, function () { tell(hint()); });
          }
          if (done) { tell(ok); ta.remove(); } else tell(hint());
          function hint() { return '自动复制没成功：下面框里已经选中，按 Ctrl/Cmd + C 即可'; }
        }
        document.getElementById('share').addEventListener('click', function () {
          var keys = Object.keys(mine);
          if (!keys.length) { tell('还没选任何条目'); return; }
          setHash(keys);
          copy(location.href, '分享链接已复制（' + keys.length + ' 条）');
        });
        document.getElementById('copy').addEventListener('click', function () {
          var keys = Object.keys(mine);
          if (!keys.length) { tell('还没选任何条目'); return; }
          var lines = DATA.filter(function (e) { return mine[keyOf(e)]; }).map(function (e) {
            return '第 ' + e.s + ' 节第 ' + e.n + ' 条 ' + e.t + '\n  ' + CFG.base + '/' + e.u;
          });
          copy('我的清单（来自《高性价比人生指南》）\n\n' + lines.join('\n'), '清单文本已复制（' + keys.length + ' 条）');
        });
        document.getElementById('reset').addEventListener('click', function () {
          mine = {}; saveMine(); setHash([]); mode = 'explore'; render(); tell('已清空');
        });

        function fromHash() {
          // 链接里可以带筛选条件（如首页"我该做哪几条"的 #ratio=极高）和/或我的清单（#p=…）
          var h = decodeURIComponent((location.hash || '').replace(/^#/, ''));
          if (!h) return false;
          var took = false, filtersOn = false, listOn = false;
          h.split('&').forEach(function (kv) {
            var i = kv.indexOf('=');
            if (i < 0) return;
            var k = kv.slice(0, i), v = kv.slice(i + 1);
            if (k === 'p') {
              var keys = v.split(',').filter(Boolean);
              if (!keys.length) return;
              keys.forEach(function (x) { mine[x] = 1; });
              saveMine(); mode = 'list'; listOn = true; took = true;
            } else if (FILTERS.indexOf(k) >= 0) {
              var vals = v.split(',').filter(Boolean);
              if (!vals.length) return;
              setFilter(k, vals); filtersOn = true; took = true;
            }
          });
          if (filtersOn) {
            tell('已按链接里的条件筛选（改条件即时重筛）');
            // 用完就把 URL 收干净：否则刷新页面条件又回来了，"清空条件"会像没生效
            history.replaceState(null, '', location.pathname
              + (listOn ? '#p=' + Object.keys(mine).sort().join(',') : ''));
          }
          return took;
        }
        loadMine();
        // 站在检索页上时再点一个带条件的链接（只改 hash、不重载）也要生效
        window.addEventListener('hashchange', function () { if (fromHash()) render(); });
        fetch('search-index.json', { cache: 'no-cache' }).then(function (r) { return r.json(); }).then(function (d) {
          DATA = d; cnt.textContent = '索引就绪：共 ' + d.length + ' 条';
          fromHash(); render();
        }).catch(function (e) {
          cnt.textContent = '索引载入失败（' + e.message + '），可以直接看目录，正文不需要 JS。';
        });
      })();
      </script>"""
    body = body.replace("__TOTAL__", str(cfg["total"])).replace("__TOP__", str(cfg["top"]))
    body = body.replace("__CFG__", json.dumps({"base": cfg["base"]}, ensure_ascii=False))
    return body


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(ROOT, "data", "book.json"),
                    help="规范化数据（tools/build_mcp_data.py 产出；站点与 MCP 共用同一份）")
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "site"))
    ap.add_argument("--base", default="https://better.aigcwei.cn", help="站点根 URL（canonical/sitemap 用）")
    ap.add_argument("--upstream", default=None, help="上游目录（读 docs/ 下按时间排的场景长文）")
    a = ap.parse_args()

    a.upstream = a.upstream or hltb.default_root(ROOT)
    with open(a.data, encoding="utf-8") as fh:
        book = json.load(fh)
    src = book["source"]
    base = a.base.rstrip("/")

    # 适配层：把 MCP 那份规范化数据（s/n/t/g/f/x + ratio/lv）还原成渲染需要的形状。
    # 站点与 MCP 共用同一个中间产物，所以内容永远一致；渲染专用字段（页码导航、节标题）在这里补。
    by_sec = {}
    for e in book["entries"]:
        by_sec.setdefault(e["s"], []).append(e)
    sections, entries = [], []
    for s in book["sections"]:
        sec = {"num": s["n"], "title": s["t"], "question": s["q"],
               "intro": s.get("intro", ""), "entries": []}
        for e in by_sec.get(s["n"], []):
            it = {"sec": e["s"], "num": e["n"], "title": e["t"], "tags": e["g"], "cost": e.get("cost", 0),
                  "fields": e["f"], "xrefs": [tuple(x) for x in e["x"]],
                  "ratio": e["ratio"], "lv": e["lv"], "lvNote": e["lvNote"],
                  "sec_title": s["t"]}
            sec["entries"].append(it)
            entries.append(it)
        sections.append(sec)
    data = {"source": src, "sections": sections, "entries": entries}

    # 场景长文（上游 docs/ 里按时间排的那几篇）+ 性价比查询表（场景页要给每条挂徽章）
    scenes = hltb.parse_docs(a.upstream)
    global RATIO
    RATIO = {(e["sec"], e["num"]): e["ratio"] for e in entries}

    # 条目补上节标题与页码导航，渲染时用
    sec_title = {s["num"]: s["title"] for s in data["sections"]}
    entries = data["entries"]
    for s in data["sections"]:
        for e in s["entries"]:
            e["sec_title"] = s["title"]
    titles = {(e["sec"], e["num"]): e["title"] for e in entries}

    if os.path.isdir(a.out):
        shutil.rmtree(a.out)
    os.makedirs(a.out)
    with open(os.path.join(a.out, "style.css"), "w", encoding="utf-8") as fh:
        fh.write(STYLE)

    pages = []  # (path, title, desc, priority)

    def write(rel, text, title, desc, pri):
        p = os.path.join(a.out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        pages.append((rel, title, desc, pri))

    top_count = sum(1 for e in entries if e["ratio"] == "极高")

    # 长文页（上游 docs/ 里非时间轴的长文/清单：应急装备清单、结婚划不划算、办证、生物钟与夜班…）
    # 正文一个字不改，只换版式（H2 分组 + 段落 + 列表 + 表格）。
    longform = []
    for _name, _base, _url in hltb.longform_files(a.upstream):
        _blocks = md_blocks(hltb.read_text(a.upstream, "docs/" + _name))
        _h1 = next((b[2] for b in _blocks if b[0] == "h" and b[1] == 1), _base)
        longform.append({"name": _name, "base": _base, "url": _url, "title": _h1,
                         "file": "docs/" + _name, "blocks": _blocks})

    # 上游正文里"见 docs/xxx.md"这类互相指路 → 优先指回我们自己的页面（没登记的才去 GitHub）
    hltb.set_docmap({**{sc["key"]: "../scenes/%s.html" % sc["url"] for sc in scenes},
                     **{d["base"]: "../articles/%s.html" % d["url"] for d in longform}})

    # 场景页（上游 docs/ 里按时间排的四篇：被裁/生孩子/确诊慢病/换工作换城市）
    if scenes:
        write("scenes/index.html", page("按场景看 - %s" % hltb.TITLE,
                                        "按时间排的清单：%s。" % "、".join(sc["title"] for sc in scenes[:6]),
                                        scenes_index_body({"source": src}, scenes, longform), base, "scenes/index.html",
                                        ld={"@context": "https://schema.org", "@type": "CollectionPage",
                                            "name": "按场景看", "inLanguage": "zh-CN", "url": base + "/scenes/"},
                                        depth=1),
              "按场景看", "按时间排的四篇清单", 0.8)
        for sc in scenes:
            write("scenes/%s.html" % sc["slug"],
                  page("%s - %s" % (sc["title"], hltb.TITLE),
                       "按时间排的清单：%s" % " → ".join(x["heading"] for x in sc["sections"][:4]),
                       scene_body({"source": src}, sc, scenes, titles), base, "scenes/%s.html" % sc["slug"],
                       ld={"@context": "https://schema.org", "@type": "Article",
                           "headline": sc["title"], "inLanguage": "zh-CN",
                           "isBasedOn": "%s/blob/main/%s" % (src["repo"], sc["file"]),
                           "author": {"@type": "Person", "name": src["author"]},
                           "license": src["license_url"],
                           "url": "%s/scenes/%s.html" % (base, sc["url"])}, depth=1),
                  sc["title"], "按时间排的清单", 0.7)

    for d in longform:
        write("articles/%s.html" % d["base"],
              page("%s - %s" % (d["title"], hltb.TITLE),
                   "%s（上游长文，未作改动）" % d["title"][:60],
                   longform_body({"source": src}, d, titles, longform), base,
                   "articles/%s.html" % d["base"],
                   ld={"@context": "https://schema.org", "@type": "Article",
                       "headline": d["title"], "inLanguage": "zh-CN",
                       "isBasedOn": "%s/blob/main/%s" % (src["repo"], d["file"]),
                       "author": {"@type": "Person", "name": src["author"]},
                       "license": src["license_url"],
                       "url": "%s/articles/%s.html" % (base, d["url"])}, depth=1, kind="article"),
              d["title"], "上游长文", 0.6)

    # 首页
    write("index.html", page("%s · 按性价比排序的 %d 条建议" % (hltb.TITLE, len(entries)),
                             "%d 条按性价比排序的循证建议，每条写明成本、收益、证据等级和原始出处。国内可访问的在线阅读版，每条一个链接。" % len(entries),
                             index_body({"sections": data["sections"], "entries": entries, "source": src,
                                         "scenes": scenes, "longform": longform}),
                             base, "index.html", ld={
                                 "@context": "https://schema.org", "@type": "Book",
                                 "name": hltb.TITLE, "author": {"@type": "Person", "name": src["author"]},
                                 "inLanguage": "zh-CN", "numberOfPages": len(entries),
                                 "license": src["license_url"], "isAccessibleForFree": True,
                                 "isBasedOn": src["repo"], "url": base + "/",
                             }, depth=0), hltb.TITLE, "目录", 1.0)

    for s in data["sections"]:
        body = section_body({"sections": data["sections"], "source": src}, s, titles)
        write("%02d/index.html" % s["num"],
              page("%s - %s" % (s["title"], hltb.TITLE), s["question"] or s["title"], body, base,
                   "%02d/" % s["num"],
                   ld={"@context": "https://schema.org", "@type": "Chapter",
                       "name": s["title"], "position": s["num"], "inLanguage": "zh-CN",
                       "isPartOf": {"@type": "Book", "name": hltb.TITLE, "url": base + "/"},
                       "url": "%s/%02d/" % (base, s["num"])}, depth=1),
              s["title"], s["question"], 0.8)
        for i, e in enumerate(s["entries"]):
            pager = '<a href="../%02d/">← 本节目录</a>' % s["num"]
            if i > 0:
                pager += '<a href="%02d.html">← 上一条</a>' % s["entries"][i - 1]["num"]
            if i + 1 < len(s["entries"]):
                pager += '<a href="%02d.html">下一条 →</a>' % s["entries"][i + 1]["num"]
            e["pager"] = pager
            write("%02d/%02d.html" % (s["num"], e["num"]),
                  page("%s - 第 %d 节第 %d 条 - %s" % (e["title"], s["num"], e["num"], hltb.TITLE),
                       e["fields"].get("说人话") or e["title"],
                       entry_body({"source": src}, e, titles), base, "%02d/%02d.html" % (s["num"], e["num"]),
                       ld={"@context": "https://schema.org", "@type": "Article",
                           "headline": e["title"], "inLanguage": "zh-CN",
                           "isPartOf": {"@type": "Book", "name": hltb.TITLE, "url": base + "/"},
                           "isBasedOn": src["repo"], "license": src["license_url"],
                           "author": {"@type": "Person", "name": src["author"]},
                           "url": "%s/%02d/%02d.html" % (base, s["num"], e["num"])}, depth=1, kind="article"),
                  e["title"], e["fields"].get("说人话") or e["title"], 0.7)

    write("map.html", page("性价比分布 - %s" % hltb.TITLE,
                           "把 %d 条建议按投入与收益点在一张图上，颜色是书里算出的性价比档。" % len(entries),
                           map_body({"source": src}, entries, base), base, "map.html",
                           ld={"@context": "https://schema.org", "@type": "WebPage",
                               "name": "性价比分布", "inLanguage": "zh-CN", "url": base + "/map.html"},
                           depth=0),
          "性价比分布", "投入 × 收益 气泡图", 0.6)

    write("about.html", page("关于与许可 - %s" % hltb.TITLE,
                             "本站转载自《%s》，CC BY 4.0，正文未作改动。署名、免责与校验说明。" % hltb.TITLE,
                             about_body({"source": src}), base, "about.html",
                             ld={"@context": "https://schema.org", "@type": "WebPage",
                                 "name": "关于与许可", "inLanguage": "zh-CN", "url": base + "/about.html"},
                             depth=0, with_legal=False, kind="article"),  # 这一页自己写了完整的免责，不必在页脚再重复一句
          "关于与许可", "转载说明与许可", 0.5)
    write("download.html", page("下载电子版 - %s" % hltb.TITLE,
                                "EPUB / PDF / 离线单文件 HTML / Anki 牌组的国内镜像下载。",
                                download_body({"source": src}), base, "download.html",
                                ld={"@context": "https://schema.org", "@type": "CollectionPage",
                                    "name": "下载电子版", "inLanguage": "zh-CN", "url": base + "/download.html"},
                                depth=0, kind="article"),
          "下载", "电子版下载", 0.5)
    write("search.html", page("全文检索 - %s" % hltb.TITLE,
                              "按关键词、成本、证据等级、口径筛选 %d 条建议。" % len(entries),
                              search_body({"total": len(entries), "top": top_count, "base": base}),
                              base, "search.html",
                              ld={"@context": "https://schema.org", "@type": "WebPage",
                                  "name": "全文检索", "inLanguage": "zh-CN", "url": base + "/search.html",
                                  "potentialAction": {"@type": "SearchAction",
                                                      "target": "%s/search.html?q={q}" % base,
                                                      "query-input": "required name=q"}},
                              depth=0),
          "检索与我的清单", "筛选 %d 条、勾出我的清单、复制分享链接" % len(entries), 0.6)

    # 检索索引（只在这一页按需加载）
    idx = [{"s": e["sec"], "n": e["num"], "t": e["title"], "h": (e["fields"].get("说人话") or "")[:160],
            "u": "%02d/%02d.html" % (e["sec"], e["num"]), "r": e["ratio"], "v": e["lv"],
            "k": e["tags"].get("口径", ""),
            "g": {"m": e["tags"].get("钱", ""), "t": e["tags"].get("时间", ""),
                  "w": e["tags"].get("毅力", ""), "b": e["tags"].get("收益", "")}}
           for e in entries]
    with open(os.path.join(a.out, "search-index.json"), "w", encoding="utf-8") as fh:
        json.dump(idx, fh, ensure_ascii=False, separators=(",", ":"))

    # 分布图数据（只在这一页按需加载；不进 sitemap）
    with open(os.path.join(a.out, "map.json"), "w", encoding="utf-8") as fh:
        json.dump(map_json(entries), fh, ensure_ascii=False, separators=(",", ":"))

    # sitemap + robots
    today = time.strftime("%Y-%m-%d")
    from urllib.parse import quote
    urls = "".join("  <url><loc>%s</loc><lastmod>%s</lastmod><priority>%.1f</priority></url>\n"
                   % (quote("%s/%s" % (base, rel), safe="/:%"), today, pri)
                   for rel, _t, _d, pri in pages)
    with open(os.path.join(a.out, "sitemap.xml"), "w", encoding="utf-8") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                 + urls + "</urlset>\n")
    with open(os.path.join(a.out, "robots.txt"), "w", encoding="utf-8") as fh:
        fh.write("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % base)

    # 社交分享图（本地用 tools/make_og.py 生成后入库；这里只负责拷进产物）
    og_src = os.path.join(ROOT, "deploy", "assets", "og.png")
    if os.path.exists(og_src):
        shutil.copyfile(og_src, os.path.join(a.out, "og.png"))
    else:
        print("  ⚠️ 没找到 deploy/assets/og.png（分享图会 404；本地跑 tools/make_og.py 生成）")

    # 统计
    total = sum(os.path.getsize(os.path.join(dp, f))
                for dp, _dn, fns in os.walk(a.out) for f in fns)
    import gzip
    gz = 0
    for dp, _dn, fns in os.walk(a.out):
        for f in fns:
            with open(os.path.join(dp, f), "rb") as fh:
                gz += len(gzip.compress(fh.read(), 6))
    print("生成 %d 个页面 + sitemap/robots/索引 → %s" % (len(pages), a.out))
    print("产物体积：原始 %.1fMB，gzip 后 %.1fMB" % (total / 1e6, gz / 1e6))
    print("正文同步自：%s（%s）" % (src.get("commit_short"), (src.get("commit_date") or "")[:10]))
    print("下一步：python3 scripts/inject.py --root %s --out dist（注入 header/footer 与备案号）" % a.out)


if __name__ == "__main__":
    main()
