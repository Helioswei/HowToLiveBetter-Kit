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
STYLE_VERSION = "4"  # 改 style.css 时 +1，避免浏览器缓存旧样式

# ---------------------------------------------------------------- 页面骨架

TOKENS = """:root {
  --paper: #faf8f4; --paper-deep: #f1ede4; --paper-soft: #f6f3ec;
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
/* ---- 深色主题：默认跟随系统（不需要 JS），用户选过就用 data-theme 覆盖 ---- */
@media (prefers-color-scheme: dark) and (not (prefers-color-scheme: light)) {
  :root { --paper: #16181c; --paper-deep: #1d2025; --paper-soft: #1e2126;
          --hairline: #2e3238; --hairline-soft: #262a30;
          --ink: #e9e5df; --ink-secondary: #ada79e; --muted: #837d74;
          --accent: #cf6a4f; --accent-strong: #e08567; --accent-soft: #2a1f1a; }
}
html[data-theme="dark"] { --paper: #16181c; --paper-deep: #1d2025; --paper-soft: #1e2126;
          --hairline: #2e3238; --hairline-soft: #262a30;
          --ink: #e9e5df; --ink-secondary: #ada79e; --muted: #837d74;
          --accent: #cf6a4f; --accent-strong: #e08567; --accent-soft: #2a1f1a; }
/* 主站共享样式给 .container/.article 的浅色底与深色字，在深色模式下要跟着走 */
html[data-theme="dark"] .container, html[data-theme="dark"] .article,
html[data-theme="dark"] .article-body, html[data-theme="dark"] .article-header,
html[data-theme="dark"] .breadcrumb { background: transparent; color: var(--ink); }
html[data-theme="dark"] .article-body a { color: var(--accent-strong); }

/* ---- 字号 / 行距档位（阅读设置那一行控制；默认不设属性 = 标准）---- */
html[data-size="s"] { font-size: 15px; }
html[data-size="l"] { font-size: 18px; }
html[data-size="xl"] { font-size: 21px; }
html[data-size="s"] body, html[data-size="l"] body, html[data-size="xl"] body,
html[data-size="s"] .article-body p, html[data-size="l"] .article-body p, html[data-size="xl"] .article-body p,
html[data-size="s"] .b-entry, html[data-size="l"] .b-entry, html[data-size="xl"] .b-entry { font-size: 1rem; }
html[data-leading="w"] body, html[data-leading="w"] .article-body p, html[data-leading="w"] .b-entry { line-height: 2.05; }

.b-prefs { display: flex; gap: .8rem; align-items: center; flex-wrap: wrap; margin: 1.6rem 0 0;
           padding: .6rem .8rem; border: 1px solid var(--hairline); border-radius: var(--radius-md);
           background: var(--paper-soft); font-size: .84rem; color: var(--ink-secondary); }
.b-prefs label { display: inline-flex; align-items: center; gap: .3rem; }
.b-prefs select { font: inherit; font-size: .84rem; padding: .15rem .3rem; background: var(--paper);
                  color: var(--ink); border: 1px solid var(--hairline); border-radius: var(--radius-sm); }
.b-prefs button { font: inherit; font-size: .84rem; padding: .2rem .7rem; cursor: pointer;
                  background: var(--paper); color: var(--ink); border: 1px solid var(--hairline);
                  border-radius: var(--radius-md); }
.b-prefs .b-sep { margin-left: auto; color: var(--muted); font-size: .78rem; }
a, code, p, li, h1, h2, h3 { overflow-wrap: anywhere; }  /* 长 URL 不许撑破 375px 窄屏 */
/* 本站自己的页头：这是独立站，不用主站的家族导航；页脚仍然用家族那份（只出备案号） */
.b-topbar { position: sticky; top: 0; z-index: 10; background: var(--paper);
            border-bottom: 1px solid var(--hairline); }
.b-topbar-inner { display: flex; align-items: center; gap: .9rem; flex-wrap: wrap; padding: .65rem 0; }
.b-brand { font-weight: 700; text-decoration: none; color: var(--ink); font-family: var(--font-serif); }
.b-tag { font-size: .78rem; color: var(--muted); }
.b-links { margin-left: auto; display: flex; gap: .9rem; flex-wrap: wrap; font-size: .9rem; }
.b-hero { padding: 1.4rem 0 0.6rem; }
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
           border: 1px solid var(--hairline); color: var(--ink-secondary); background: var(--paper-soft); }
.b-badge.lv { color: #1f7a4d; border-color: currentColor; }
.b-badge.ku { color: var(--accent); border-color: currentColor; }
.b-badge.top { color: var(--accent-strong); border-color: currentColor; font-weight: 600; }
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
          margin-top: 1.2rem; padding: .7rem .9rem; background: var(--paper-deep);
          border-top: 2px solid var(--accent); font-size: .88rem; }
.b-bar button { font: inherit; font-size: .85rem; cursor: pointer; padding: .3rem .8rem;
          border: 1px solid var(--hairline); border-radius: var(--radius-md); background: var(--paper); }
.b-bar .b-count { font-weight: 600; }
.b-bar .b-hint { color: var(--muted); }
.b-hit h3 { font-size: 1rem; margin: 0 0 .3rem; }
@media (max-width: 520px) {
  .b-secs a { grid-template-columns: 2.2rem 1fr; grid-template-areas: "n t" ". c" ". q"; }
  .b-hero h1 { font-size: 1.6rem; }
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
BODY_PREFS = """<script>
(function(){
  var K='hltb.prefs', h=document.documentElement;
  function load(){try{return JSON.parse(localStorage.getItem(K)||'{}')||{}}catch(e){return {}}}
  var p=load();
  function sel(id,label,opts){var s='<label>'+label+'<select id="'+id+'">';
    for(var i=0;i<opts.length;i++){s+='<option value="'+opts[i][0]+'">'+opts[i][1]+'</option>';}
    return s+'</select></label>';}
  var box=document.createElement('div'); box.className='b-prefs';
  box.innerHTML='<span>阅读设置</span>'
    +sel('b-size','字号',[['s','小'],['','标准'],['l','大'],['xl','特大']])
    +sel('b-leading','行距',[['','标准'],['w','宽']])
    +sel('b-theme','主题',[['','跟随系统'],['light','浅色'],['dark','深色']])
    +'<button type="button" id="b-speak">朗读</button>'
    +'<span class="b-sep" id="b-say">设置只存在你自己的浏览器里</span>';
  var anchor=document.querySelector('footer.site-footer')||document.getElementById('site-footer')||document.body;
  anchor.parentNode.insertBefore(box, anchor);

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


def page(title, desc, body, base, path, ld=None, depth=0, extra_js=False):
    """一个页面。path 是相对站点根的路径（如 "08/18.html"），用来算相对前缀与 canonical。"""
    up = "../" * depth
    canonical = "%s/%s" % (base, path) if not path.endswith("index.html") else \
        "%s/%s" % (base, path.rsplit("index.html", 1)[0])
    import re as _re

    canonical = _re.sub(r"/+$", "/", canonical)
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
  <meta name="twitter:card" content="summary">
  {SHARED_CSS}
  <link rel="stylesheet" href="{up}style.css?v={STYLE_VERSION}">
{HEAD_PREFS}
{ld_block}</head>
<body data-site="better">
  <nav class="b-topbar" aria-label="本站导航">
    <div class="container b-topbar-inner">
      <a class="b-brand" href="{up}index.html">{html.escape(hltb.TITLE)}</a>
      <span class="b-tag">非官方转载 · 正文未改动</span>
      <div class="b-links">
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
    </div>
  </main>

  {BODY_PREFS}
  <div id="site-footer"></div>
</body>
</html>
"""


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


def paras(text, sec, titles):
    if not text:
        return ""
    return "".join("<p>%s</p>" % hltb.inline(p, sec, titles) for p in hltb.split_paras(text))


def sync_line(src):
    return ("同步自上游 <a href=\"%s/commit/%s\" target=\"_blank\" rel=\"noopener nofollow\">%s</a>（%s）"
            % (src["repo"], src.get("commit") or "", src.get("commit_short") or "?", (src.get("commit_date") or "")[:10]))


DISCLAIMER = ("本条内容来自《%s》原文，未作改动。医学内容不构成诊疗意见，法律内容不构成法律意见；"
              "个案请咨询执业医师或律师。" % hltb.TITLE)
DISCLAIMER_NOTE = '<p class="b-note">%s</p>' % DISCLAIMER


# ---------------------------------------------------------------- 各类页面

def entry_body(b, e, titles):
    f = e["fields"]
    extra = ""
    for label in ("收益", "来源", "备注"):
        if f.get(label):
            extra += '<div class="b-fl"><b>%s</b>%s</div>' % (label, paras(f[label], e["sec"], titles))
    if e["xrefs"]:
        refs = []
        for s, n in e["xrefs"]:
            t = titles.get((s, n))
            href = "%02d.html" % n if s == e["sec"] else "../%02d/%02d.html" % (s, n)
            refs.append('<a class="b-xref" href="%s">第 %d 节第 %d 条%s</a>'
                        % (href, s, n, ("（%s）" % html.escape(t)) if t else ""))
        extra += '<div class="b-fl"><b>这一条还指向</b><p>%s</p></div>' % "；".join(refs)
    return f"""      <nav class="breadcrumb"><a href="../">目录</a> <span class="sep">›</span> <a href="./">第 {e['sec']} 节 {html.escape(e['sec_title'])}</a> <span class="sep">›</span> <span class="cur">{e['num']}</span></nav>
      <article class="article">
        <header class="article-header">
          <h1>{html.escape(e['title'])}</h1>
          <p class="article-meta"><span>第 {e['sec']} 节第 {e['num']} 条</span></p>
        </header>
        {badge_html(e)}
        <div class="article-body">
          {paras(f.get('说人话'), e['sec'], titles) if f.get('说人话') else ''}
          {('<div class="b-fl"><b>成本</b>%s</div>' % paras(f['成本'], e['sec'], titles)) if f.get('成本') else ''}
          {extra}
        </div>
      </article>
      <p class="b-note">{DISCLAIMER}</p>
      <p class="b-perma">{sync_line(b['source'])}　原文出处：<a href="{b['source']['repo']}" target="_blank" rel="noopener nofollow">{html.escape(hltb.TITLE)}</a></p>
      <nav class="b-pager">{e['pager']}</nav>"""


def section_body(b, sec, titles):
    items = []
    for e in sec["entries"]:
        f = e["fields"]
        extra = ""
        for label in ("收益", "来源", "备注"):
            if f.get(label):
                extra += '<div class="b-fl"><b>%s</b>%s</div>' % (label, paras(f[label], sec["num"], titles))
        items.append(f"""      <section class="b-entry" id="e{e['num']}">
        <h3><a href="#e{e['num']}" style="color:var(--muted);text-decoration:none">{e['num']}.</a> {html.escape(e['title'])}</h3>
        {badge_html(e)}
        {('<p class="b-human">%s</p>' % hltb.inline(f['说人话'], sec['num'], titles)) if f.get('说人话') else ''}
        {('<p class="b-cost">成本：%s</p>' % hltb.inline(f['成本'], sec['num'], titles)) if f.get('成本') else ''}
        <details><summary>收益 / 来源 / 备注</summary>{extra}</details>
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
      <div class="article-body">
        {paras(sec['intro'], sec['num'], titles)}
      </div>
      <p class="b-stat">{len(sec['entries'])} 条，按性价比从高到低　·　{sync_line(b['source'])}</p>
{chr(10).join(items)}
      <p class="b-note">{DISCLAIMER}</p>
      <nav class="b-pager">{pager}</nav>"""


def index_body(b):
    total = len(b["entries"])
    top = sum(1 for e in b["entries"] if e.get("ratio") == "极高")
    rows = "".join(
        '<li><a href="%02d/"><span class="b-sn">%02d</span><span class="b-st">%s</span>'
        '<span class="b-sc">%d 条</span><span class="b-sq">%s</span></a></li>'
        % (s["num"], s["num"], html.escape(s["title"]), len(s["entries"]), html.escape(s["question"]))
        for s in b["sections"])
    return f"""      <div class="b-hero">
        <h1>{html.escape(hltb.TITLE)}</h1>
        <p>按性价比排序的 {total} 条建议，来自 <a href="{b['source']['repo']}" target="_blank" rel="noopener nofollow">eternity4719/HowToLiveBetter</a>。
           每条写明花掉什么、换回什么、证据有多硬，来源只引期刊论文与官方文件。</p>
        <p class="b-stat">本站是<strong>原文转载</strong>：正文一个字未改，只重排版式并加了导航、检索与单条链接。
           共 {len(b['sections'])} 节 {total} 条　·　{sync_line(b['source'])}</p>
        <p class="b-stat"><a href="search.html#ratio=%E6%9E%81%E9%AB%98">我该做哪几条（{top} 条零成本高收益）</a>　·　<a href="search.html">检索全部 {total} 条</a>　·　<a href="download.html">下载电子版</a>　·　<a href="about.html">关于与许可</a></p>
      </div>
      <ol class="b-secs">{rows}</ol>
      <p class="b-note">{DISCLAIMER}</p>"""


def about_body(b):
    src = b["source"]
    return f"""      <nav class="breadcrumb"><a href="./">目录</a> <span class="sep">›</span> <span class="cur">关于与许可</span></nav>
      <div class="b-hero"><h1>关于本站与许可</h1></div>
      <div class="article-body">
        <h2>这是转载</h2>
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
    return f"""      <nav class="breadcrumb"><a href="./">目录</a> <span class="sep">›</span> <span class="cur">下载</span></nav>
      <div class="b-hero"><h1>下载电子版</h1>
        <p class="b-stat">下面几份由上游在正文更新后自动重新生成，本站做了国内镜像（打开更快）。</p></div>
      <div class="article-body">
        <ul>
          <li><a href="download/HowToLiveBetter.epub">EPUB 电子书</a> —— 手机阅读器 / Kindle（Send to Kindle 发过去即可）</li>
          <li><a href="download/HowToLiveBetter.pdf">PDF</a> —— A4 排版，带目录页码，适合打印</li>
          <li><a href="download/HowToLiveBetter.html">离线单文件 HTML</a> —— 整本书连同检索都在这一个文件里，双击就开</li>
          <li><a href="download/HowToLiveBetter.apkg">Anki 牌组</a> —— 一条一张卡，按节分子牌组</li>
        </ul>
        <p>镜像失败时请直接到上游下载：<a href="{b['source']['repo']}/releases" target="_blank" rel="noopener nofollow">上游 Release</a>。</p>
        <h2>许可</h2>
        <p>这些文件同样是《{html.escape(hltb.TITLE)}》的正文，按 {b['source']['license']} 转载，
           作者 {b['source']['author']}，原始仓库见上。转发出去的那一份不会跟着更新，以在线版为准。</p>
      {DISCLAIMER_NOTE}
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
        <p class="b-stat">按关键词、成本、证据等级、口径筛这 __TOTAL__ 条；看中的打勾，就成了「我的清单」——
           勾选只存在你自己的浏览器里，不会上传；要发给别人就复制分享链接。</p>
        <div class="b-presets">
          <button type="button" data-preset="top">性价比「极高」（__TOP__ 条）</button>
          <button type="button" data-preset="a">只看证据 A 级</button>
          <button type="button" data-preset="clear">清空条件</button>
          <button type="button" data-preset="mine">只看我的清单</button>
        </div>
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
        <button type="button" id="share">复制分享链接</button>
        <button type="button" id="copy">复制清单文本</button>
        <button type="button" id="reset">清空我的清单</button>
        <span class="b-hint" id="say"></span>
      </div>
      <p class="b-note">关键词是字面匹配，不是语义检索。不同口径之间不做比较（书里的规定）；
         勾选只存在你自己的浏览器里，没有账号、没有服务器。</p>
      <script>
      (function () {
        var CFG = __CFG__;
        var DATA = null, mode = 'explore', mine = {}, byKey = {};
        var form = document.getElementById('f'), hits = document.getElementById('hits');
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
          return '<div class="b-badges"><span class="b-badge top">性价比 ' + e.r + '</span>' +
                 '<span class="b-badge">收益 ' + e.g.b + '</span>' +
                 '<span class="b-badge lv">证据 ' + e.v + '</span>' +
                 '<span class="b-badge ku">' + e.k + '</span></div>';
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
          var n = Object.keys(mine).length;
          mycount.textContent = '已选 ' + n + ' 条';
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

        document.addEventListener('change', function (ev) {
          var t = ev.target;
          if (t && t.getAttribute && t.getAttribute('data-pick')) {
            var k = t.getAttribute('data-pick');
            if (t.checked) mine[k] = 1; else delete mine[k];
            saveMine();
            var box = t.closest('.b-hit');
            if (box) box.classList[ t.checked ? 'add' : 'remove' ]('picked');
            var n = Object.keys(mine).length;
            mycount.textContent = '已选 ' + n + ' 条';
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
          var m = /#p=([0-9.,]*)/.exec(location.hash);
          if (!m) return false;
          var keys = m[1].split(',').filter(Boolean);
          if (!keys.length) return false;
          keys.forEach(function (k) { mine[k] = 1; });
          saveMine();
          mode = 'list';
          return true;
        }
        loadMine();
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
    return body + DISCLAIMER_NOTE


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(ROOT, "data", "book.json"),
                    help="规范化数据（tools/build_mcp_data.py 产出；站点与 MCP 共用同一份）")
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "site"))
    ap.add_argument("--base", default="https://better.aigcwei.cn", help="站点根 URL（canonical/sitemap 用）")
    a = ap.parse_args()

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
            it = {"sec": e["s"], "num": e["n"], "title": e["t"], "tags": e["g"],
                  "fields": e["f"], "xrefs": [tuple(x) for x in e["x"]],
                  "ratio": e["ratio"], "lv": e["lv"], "lvNote": e["lvNote"],
                  "sec_title": s["t"]}
            sec["entries"].append(it)
            entries.append(it)
        sections.append(sec)
    data = {"source": src, "sections": sections, "entries": entries}

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

    # 首页
    write("index.html", page("%s · 按性价比排序的 %d 条建议" % (hltb.TITLE, len(entries)),
                             "672 条按性价比排序的循证建议，每条写明成本、收益、证据等级和原始出处。国内可访问的在线阅读版，每条一个链接。",
                             index_body({"sections": data["sections"], "entries": entries, "source": src}),
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
                           "url": "%s/%02d/%02d.html" % (base, s["num"], e["num"])}, depth=1),
                  e["title"], e["fields"].get("说人话") or e["title"], 0.7)

    write("about.html", page("关于与许可 - %s" % hltb.TITLE,
                             "本站转载自《%s》，CC BY 4.0，正文未作改动。署名、免责与校验说明。" % hltb.TITLE,
                             about_body({"source": src}), base, "about.html",
                             ld={"@context": "https://schema.org", "@type": "WebPage",
                                 "name": "关于与许可", "inLanguage": "zh-CN", "url": base + "/about.html"},
                             depth=0),
          "关于与许可", "转载说明与许可", 0.5)
    write("download.html", page("下载电子版 - %s" % hltb.TITLE,
                                "EPUB / PDF / 离线单文件 HTML / Anki 牌组的国内镜像下载。",
                                download_body({"source": src}), base, "download.html",
                                ld={"@context": "https://schema.org", "@type": "CollectionPage",
                                    "name": "下载电子版", "inLanguage": "zh-CN", "url": base + "/download.html"},
                                depth=0),
          "下载", "电子版下载", 0.5)
    write("search.html", page("全文检索 - %s" % hltb.TITLE,
                              "按关键词、成本、证据等级、口径筛选 672 条建议。",
                              search_body({"total": len(entries), "top": top_count, "base": base}),
                              base, "search.html",
                              ld={"@context": "https://schema.org", "@type": "WebPage",
                                  "name": "全文检索", "inLanguage": "zh-CN", "url": base + "/search.html",
                                  "potentialAction": {"@type": "SearchAction",
                                                      "target": "%s/search.html?q={q}" % base,
                                                      "query-input": "required name=q"}},
                              depth=0),
          "检索与我的清单", "筛选 672 条、勾出我的清单、复制分享链接", 0.6)

    # 检索索引（只在这一页按需加载）
    idx = [{"s": e["sec"], "n": e["num"], "t": e["title"], "h": (e["fields"].get("说人话") or "")[:160],
            "u": "%02d/%02d.html" % (e["sec"], e["num"]), "r": e["ratio"], "v": e["lv"],
            "k": e["tags"].get("口径", ""),
            "g": {"m": e["tags"].get("钱", ""), "t": e["tags"].get("时间", ""),
                  "w": e["tags"].get("毅力", ""), "b": e["tags"].get("收益", "")}}
           for e in entries]
    with open(os.path.join(a.out, "search-index.json"), "w", encoding="utf-8") as fh:
        json.dump(idx, fh, ensure_ascii=False, separators=(",", ":"))

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
