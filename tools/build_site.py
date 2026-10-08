#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""站点生成器：build/entries.json → 模板版静态站（build/site/）。

    python3 tools/build_site.py
    python3 tools/build_site.py --base https://better.aigcwei.cn --out build/site

产出的是**模板版**：页面上只有 `<div id="site-header"></div>` 与 `<div id="site-footer"></div>`
两个占位符，header/footer（含备案号）由网站家族的 scripts/inject.py 在构建时注入 ——
所以备案号这类合规信息只在一个地方维护，这个脚本一个字都不写死。

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
STYLE_VERSION = "2"  # 改 style.css 时 +1，避免浏览器缓存旧样式

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
a, code, p, li, h1, h2, h3 { overflow-wrap: anywhere; }  /* 长 URL 不许撑破 375px 窄屏 */
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
.b-hit h3 { font-size: 1rem; margin: 0 0 .3rem; }
@media (max-width: 520px) {
  .b-secs a { grid-template-columns: 2.2rem 1fr; grid-template-areas: "n t" ". c" ". q"; }
  .b-hero h1 { font-size: 1.6rem; }
}
"""

FAVICON = '<link rel="icon" type="image/svg+xml" href="https://assets.aigcwei.cn/favicon.svg">'
SHARED_CSS = '<link rel="stylesheet" href="https://assets.aigcwei.cn/style.css">'


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
{ld_block}</head>
<body data-site="better">
  <div id="site-header"></div>

  <main>
    <div class="container">
{body}
    </div>
  </main>

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
        <p class="b-stat"><a href="search.html">全文检索</a>　·　<a href="download.html">下载电子版</a>　·　<a href="about.html">关于与许可</a></p>
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


def search_body():
    return """      <nav class="breadcrumb"><a href="./">目录</a> <span class="sep">›</span> <span class="cur">检索</span></nav>
      <div class="b-hero"><h1>全文检索</h1>
        <p class="b-stat">按关键词、成本、证据等级、口径筛选这 672 条。<strong>没有 JS 也能读全书</strong> —— 这一页只是方便检索，正文在目录里。</p></div>
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
      <p class="b-note">关键词是字面匹配，不是语义检索。不同口径之间不做比较（书里的规定）。</p>
      <script>
      (function () {
        var DATA = null, form = document.getElementById('f'), hits = document.getElementById('hits'), cnt = document.getElementById('count');
        function load() {
          fetch('search-index.json', { cache: 'no-cache' }).then(function (r) { return r.json(); }).then(function (d) {
            DATA = d; cnt.textContent = '索引就绪：共 ' + d.length + ' 条'; render();
          }).catch(function (e) { cnt.textContent = '索引载入失败（' + e.message + '），可以直接看目录。'; });
        }
        function picked(name) {
          return Array.prototype.slice.call(form.querySelectorAll('input[name=' + name + ']:checked')).map(function (i) { return i.value; });
        }
        function render() {
          if (!DATA) return;
          var q = (document.getElementById('q').value || '').replace(/\\s+/g, '').toLowerCase();
          var f = { money: picked('money'), time: picked('time'), will: picked('will'), benefit: picked('benefit'), evidence: picked('evidence'), caliber: picked('caliber'), ratio: picked('ratio') };
          var out = DATA.filter(function (e) {
            if (f.evidence.length && f.evidence.indexOf(e.v) < 0) return false;
            if (f.caliber.length && f.caliber.indexOf(e.k) < 0) return false;
            if (f.ratio.length && f.ratio.indexOf(e.r) < 0) return false;
            if (f.benefit.length && f.benefit.indexOf(e.g.b) < 0) return false;
            if (f.money.length && f.money.indexOf(e.g.m) < 0) return false;
            if (f.time.length && f.time.indexOf(e.g.t) < 0) return false;
            if (f.will.length && f.will.indexOf(e.g.w) < 0) return false;
            if (q && (e.t + e.h).toLowerCase().indexOf(q) < 0) return false;
            return true;
          });
          cnt.textContent = '命中 ' + out.length + ' 条';
          hits.innerHTML = out.slice(0, 60).map(function (e) {
            return '<div class="b-hit"><h3><a href="' + e.u + '">' + e.t + '</a></h3>' +
              '<div class="b-badges"><span class="b-badge top">性价比 ' + e.r + '</span>' +
              '<span class="b-badge">收益 ' + e.g.b + '</span><span class="b-badge lv">证据 ' + e.v + '</span>' +
              '<span class="b-badge ku">' + e.k + '</span></div>' +
              '<p>' + e.h + '</p></div>';
          }).join('') + (out.length > 60 ? '<p class="b-stat">只显示前 60 条，请加条件缩小范围。</p>' : '');
        }
        form.addEventListener('change', render);
        document.getElementById('q').addEventListener('input', render);
        form.addEventListener('submit', function (e) { e.preventDefault(); });
        load();
      })();
      </script>""" + DISCLAIMER_NOTE


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
                              search_body(), base, "search.html",
                              ld={"@context": "https://schema.org", "@type": "WebPage",
                                  "name": "全文检索", "inLanguage": "zh-CN", "url": base + "/search.html",
                                  "potentialAction": {"@type": "SearchAction",
                                                      "target": "%s/search.html?q={q}" % base,
                                                      "query-input": "required name=q"}},
                              depth=0),
          "全文检索", "检索 672 条", 0.6)

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
