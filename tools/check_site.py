#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""站点自检：证明生成出来的静态站是合格的（SEO / 零 JS / 链接 / 保真 / 备案号）。

    python3 tools/check_site.py                      # 检查模板版 build/site/
    python3 tools/check_site.py --root dist --injected # 检查注入后的产物（含备案号）

和 check_verbatim.py 一样，这里**不复用生成器的代码**、独立地读 HTML 做断言 ——
用同一份代码检查自己写出来的东西没有意义。
"""

import argparse
import gzip
import html as htmlmod
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RE_HREF = re.compile(r'href="([^"]+)"')
RE_SRC = re.compile(r'src="([^"]+)"')
RE_LD = re.compile(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', re.S)
RE_CANON = re.compile(r'<link rel="canonical" href="([^"]+)">')


def norm(s):
    """归一化：正文里的 <url> 会被渲染成链接（尖括号去掉），所以比对时也要去掉尖括号。"""
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s or "")
    return re.sub(r"\s+", "", s.replace("<", "").replace(">", ""))


def strip_tags(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", s, flags=re.S)
    return htmlmod.unescape(re.sub(r"<[^>]+>", "", s))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(ROOT, "build", "site"))
    ap.add_argument("--data", default=os.path.join(ROOT, "data", "book.json"))
    ap.add_argument("--base", default="https://better.aigcwei.cn")
    ap.add_argument("--injected", action="store_true", help="这是注入后的产物（要有备案号，不应再有占位符）")
    ap.add_argument("--skip-downloads", action="store_true",
                    help="跳过「电子版文件在不在」的检查（本地跑没有镜像，CI 里要查）")
    ap.add_argument("--icp", default="鄂ICP备")  # 只查前缀，真值由 site-config.json / inject.py 决定
    a = ap.parse_args()

    errors, warnings, info = [], [], []
    root, base = a.root, a.base.rstrip("/")

    with open(a.data, encoding="utf-8") as fh:
        book = json.load(fh)
    entries = book["entries"]
    sections = book["sections"]

    pages = []
    for dp, _dn, fns in os.walk(root):
        # download/ 里是镜像来的上游电子版（PDF/EPUB/离线单文件）：那是下载附件，
        # 不是本站页面，没有外壳与备案号也不该有，一律不算页面
        if os.sep + "download" in dp + os.sep:
            continue
        for fn in fns:
            if fn.endswith(".html"):
                pages.append(os.path.relpath(os.path.join(dp, fn), root))
    pages = sorted(p.replace(os.sep, "/") for p in pages)

    # 1. 页数
    expect_pages = len(sections) + len(entries) + 4  # 节页 + 条目页 + 首页/关于/下载/检索
    info.append("页面 %d 个（期望 %d = %d 节 + %d 条 + 4 个固定页）"
                % (len(pages), expect_pages, len(sections), len(entries)))
    if len(pages) != expect_pages:
        errors.append("页面数不对：实际 %d，期望 %d" % (len(pages), expect_pages))

    canon_seen, no_script_except_search, ld_bad, shell_missing = {}, [], [], []
    disclaimer_missing, placeholder_left, icp_missing = [], [], []
    missing_targets, gzip_big, download_links = [], [], set()

    titles = {(e["s"], e["n"]): e["t"] for e in entries}

    for rel in pages:
        p = os.path.join(root, rel)
        with open(p, encoding="utf-8") as fh:
            doc = fh.read()

        # 2. 骨架：favicon / 共享样式 / 我们自己的页头 / 页脚（本站独立，页头不套主站家族导航；
        #    页脚仍是家族注入的那份，只出备案号）
        if a.injected:
            shell_needles = (("assets.aigcwei.cn/favicon.svg", "favicon"),
                             ("assets.aigcwei.cn/style.css", "共享样式"),
                             ('class="b-topbar"', "本站页头"),
                             ('class="site-footer"', "注入后的页脚"),
                             ('data-site="better"', "data-site"))
        else:
            shell_needles = (("assets.aigcwei.cn/favicon.svg", "favicon"),
                             ("assets.aigcwei.cn/style.css", "共享样式"),
                             ('class="b-topbar"', "本站页头"),
                             ('<div id="site-footer"></div>', "footer 占位符"),
                             ('data-site="better"', "data-site"))
        for needle, label in shell_needles:
            if needle not in doc:
                shell_missing.append("%s 缺 %s" % (rel, label))

        # 3. 零 JS（检索页除外）—— JSON-LD 也是 <script>，但它不是可执行脚本
        exec_scripts = re.findall(r'<script(?![^>]*type="application/ld\+json")', doc)
        if exec_scripts and rel != "search.html":
            no_script_except_search.append("%s（%d 个）" % (rel, len(exec_scripts)))

        # 4. canonical 唯一且规范
        m = RE_CANON.search(doc)
        if not m:
            errors.append("%s 缺 canonical" % rel)
        else:
            c = m.group(1)
            if not c.startswith(base):
                errors.append("%s 的 canonical 不在本站：%s" % (rel, c))
            if c in canon_seen:
                errors.append("canonical 重复：%s（%s 与 %s）" % (c, rel, canon_seen[c]))
            canon_seen[c] = rel

        # 5. JSON-LD 恰好一块且能解析
        blocks = RE_LD.findall(doc)
        if len(blocks) != 1:
            ld_bad.append("%s 有 %d 块 JSON-LD" % (rel, len(blocks)))
        else:
            try:
                json.loads(blocks[0])
            except Exception as exc:
                ld_bad.append("%s JSON-LD 解析失败：%s" % (rel, exc))

        # 6. 内部链接都能落地（download/ 里的电子版是上线时由 deploy/build.sh 镜像进来的，单独校验）
        for href in RE_HREF.findall(doc) + RE_SRC.findall(doc):
            if href.startswith(("http", "mailto:", "#", "data:")):
                continue
            if "download/" in href:
                download_links.add(href.split("#")[0])
                continue
            if "'" in href or "+" in href or "${" in href:  # 脚本里拼出来的字符串，不是真链接
                continue
            target = href.split("#")[0].split("?")[0]
            if not target:
                continue
            tpath = os.path.normpath(os.path.join(os.path.dirname(p), target))
            if target.endswith("/") or os.path.isdir(tpath):
                tpath = os.path.join(tpath, "index.html")
            if not os.path.exists(tpath):
                missing_targets.append("%s → %s" % (rel, href))

        # 7. 免责声明
        text = strip_tags(doc)
        if rel != "about.html" and "不构成诊疗意见" not in text:
            disclaimer_missing.append(rel)

        # 8. 注入后的产物：要有备案号，不应残留占位符
        if a.injected:
            if a.icp not in doc:
                icp_missing.append(rel)
            if '<div id="site-header"></div>' in doc or '<div id="site-footer"></div>' in doc:
                placeholder_left.append(rel)

        # 9. 体积预算
        gz = len(gzip.compress(doc.encode("utf-8"), 6))
        if gz > 120 * 1024:
            gzip_big.append("%s gzip %.0fKB" % (rel, gz / 1024.0))

    # 10. 逐条保真：每条六个字段的原文都要出现在它自己的页面上
    checked = bad = 0
    for e in entries:
        rel = "%02d/%02d.html" % (e["s"], e["n"])
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            errors.append("条目页缺失：%s" % rel)
            continue
        with open(p, encoding="utf-8") as fh:
            text = norm(strip_tags(fh.read()))
        for k in ("成本", "说人话", "收益", "证据等级", "来源", "备注"):
            v = e["f"].get(k)
            if not v:
                continue
            checked += 1
            if norm(v) not in text:
                bad += 1
                errors.append("%s 的「%s」在页面上找不到（渲染丢了内容）" % (rel, k))
    info.append("逐条保真：比对 %d 个字段，缺失 %d 个" % (checked, bad))

    # 11. 检索索引
    idx_path = os.path.join(root, "search-index.json")
    if not os.path.exists(idx_path):
        errors.append("缺 search-index.json")
    else:
        with open(idx_path, encoding="utf-8") as fh:
            idx = json.load(fh)
        if len(idx) != len(entries):
            errors.append("检索索引条目数不对：%d ≠ %d" % (len(idx), len(entries)))
        for it in idx:
            if not os.path.exists(os.path.join(root, it["u"])):
                errors.append("索引指向不存在的页面：%s" % it["u"])
        info.append("检索索引 %d 条（%.0fKB）" % (len(idx), os.path.getsize(idx_path) / 1024.0))

    # 12. sitemap / robots
    sm_path = os.path.join(root, "sitemap.xml")
    if not os.path.exists(sm_path):
        errors.append("缺 sitemap.xml")
    else:
        with open(sm_path, encoding="utf-8") as fh:
            sm = fh.read()
        locs = re.findall(r"<loc>([^<]+)</loc>", sm)
        if len(locs) != len(pages):
            errors.append("sitemap 条数 %d ≠ 页面数 %d" % (len(locs), len(pages)))
        if len(set(locs)) != len(locs):
            errors.append("sitemap 有重复 URL")
        if not all(l.isascii() for l in locs):
            errors.append("sitemap 里有非 ASCII URL（必须百分号编码）")
        if not all(l.startswith(base) for l in locs):
            errors.append("sitemap 里有不在本站的 URL")
        info.append("sitemap %d 条，全部 ASCII、无重复" % len(locs))
    if not os.path.exists(os.path.join(root, "robots.txt")):
        errors.append("缺 robots.txt")

    # 6b. 下载页必须正好指向那四个电子版；注入后的产物里它们要真的在（由 deploy/build.sh 镜像）
    expect_dl = {"download/HowToLiveBetter.epub", "download/HowToLiveBetter.pdf",
                 "download/HowToLiveBetter.html", "download/HowToLiveBetter.apkg"}
    got_dl = {l.lstrip("./") for l in download_links}
    missing_dl = expect_dl - got_dl
    if missing_dl:
        errors.append("下载页少了这几个链接：%s" % sorted(missing_dl))
    if a.injected and not a.skip_downloads:
        absent = [f for f in sorted(expect_dl) if not os.path.exists(os.path.join(root, f))]
        if absent:
            errors.append("注入后的产物里缺电子版文件（镜像没成功）：%s" % absent)
        else:
            sizes = {f: os.path.getsize(os.path.join(root, f)) // 1024 for f in sorted(expect_dl)}
            info.append("电子版镜像已就位：%s" % sizes)

    # 6c. 页面内联 JS 的语法检查（用 node，没有就跳过并说明）
    #     为什么要这道：我写检索页时踩过 —— Python 字符串把 JS 里的 \n 提前解析成真换行，
    #     生成出一段语法错误的 JS；零 JS 的那部分页面永远不会暴露这种错，所以必须机器查。
    import shutil
    import subprocess
    import tempfile
    inline = []
    for rel in pages:
        with open(os.path.join(root, rel), encoding="utf-8") as fh:
            doc = fh.read()
        for body in re.findall(r"<script(?![^>]*type=\"application/ld\+json\")[^>]*>(.*?)</script>", doc, re.S):
            if body.strip():
                inline.append((rel, body))
    if inline:
        node = shutil.which("node")
        if not node:
            warnings.append("页面里有 %d 段内联 JS，但本机没有 node，跳过语法检查" % len(inline))
        else:
            bad = []
            for rel, body in inline:
                with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
                    fh.write(body)
                    tmp = fh.name
                p = subprocess.run([node, "--check", tmp], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                if p.returncode != 0:
                    out = p.stdout.decode("utf-8", "replace")
                    first = next((l for l in out.splitlines() if "Error" in l), (out.splitlines() or ["未知"])[0])
                    bad.append("%s：%s" % (rel, first.strip()[:140]))
                os.unlink(tmp)
            if bad:
                errors.append("内联 JS 有语法错误：%s" % bad)
            else:
                info.append("内联 JS 语法检查通过（%d 段，node --check）" % len(inline))

    # ---------------- 报告
    for line in info:
        print("  · %s" % line)
    for line in warnings:
        print("  ⚠️ %s" % line)
    for label, items in (("缺骨架", shell_missing), ("出现了 script（应零 JS）", no_script_except_search),
                         ("JSON-LD 有问题", ld_bad), ("缺免责声明", disclaimer_missing),
                         ("内部链接指向不存在的文件", missing_targets[:20]),
                         ("注入后缺备案号", icp_missing), ("注入后仍有占位符", placeholder_left),
                         ("页面过大（gzip）", gzip_big)):
        if items:
            errors.append("%s：%d 处，例如 %s" % (label, len(items), items[:5]))
    for e in errors:
        print("  ✗ %s" % e)
    print("站点自检：%d 个页面，错误 %d 项" % (len(pages), len(errors)))
    if errors:
        print("结论：站点不合格，先修再上线")
        sys.exit(1)
    print("结论：结构 / SEO / 零 JS / 链接 / 保真 / 索引 / sitemap 全部合格"
          + ("，备案号已注入" if a.injected else ""))


if __name__ == "__main__":
    main()
