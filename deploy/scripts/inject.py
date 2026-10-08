#!/usr/bin/env python3
"""inject.py — 全站外壳静态注入（v4 架构）

把模板版页面（占位符）渲染为注入版（最终 header/footer HTML），
替代 v3 的运行时 JS 渲染（site-shell.js）。机制与 VitePress 构建时预渲染同构。

用法:
  python3 scripts/inject.py [--root <站点根>] [--config <site-config.json>]
                            [--config-url <url>] [--out <产物目录>]

默认:
  --root    当前目录（自动探测含 index.html 的站点根）
  --config  <root>/site-config.json（缺失时用内置默认 + 告警）
  --out     <root>/dist（镜像产物，Makers outputDirectory）

行为:
  1. 读 site-config.json（或 --config-url 拉取，失败回退本地副本）
  2. 遍历站点内所有 .html（排除 dist/.git）
  3. 按 <body data-site> 渲染 header/footer（与 v3 site-shell.js 逐字节一致）
  4. 替换占位符 → 写入 dist/ 镜像

备案号强制（合规）:
  icp/icpUrl 内置默认值（鄂ICP备2026041178号），配置缺失时使用默认并告警；
  任何站的构建产物 footer 必带备案号。
"""
import argparse
import json
import os
import re
import shutil
import sys
import urllib.request
from datetime import date

# 备案号内置默认（合规硬要求，子域名共用主域备案）
DEFAULT_ICP = "鄂ICP备2026041178号"
DEFAULT_ICP_URL = "https://beian.miit.gov.cn/"

HEADER_RE = re.compile(r'<div id="site-header"></div>')
# footer 占位符 + 可选跟随的 v3 script 引用（不同缩进/换行兼容）
FOOTER_RE = re.compile(
    r'<div id="site-footer"></div>\s*'
    r'(?:<script src="https://assets\.aigcwei\.cn/site-config\.js"></script>\s*)?'
    r'(?:<script src="https://assets\.aigcwei\.cn/site-shell\.js"></script>\s*)?'
)
SITE_RE = re.compile(r'<body[^>]*data-site="([^"]*)"')


def load_config(root, config_path, config_url):
    """加载配置：--config-url 优先（拉取失败回退本地），否则本地文件；缺 icp 用内置默认。"""
    cfg = {}
    if config_url:
        try:
            with urllib.request.urlopen(config_url, timeout=15) as r:
                cfg = json.loads(r.read().decode("utf-8"))
            print("✅ 配置从 %s 拉取成功" % config_url)
        except Exception as e:
            print("⚠️  配置拉取失败（%s），回退本地副本" % e)
    if not cfg and config_path and os.path.isfile(config_path):
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)
        print("✅ 配置读取本地 %s" % config_path)
    if not cfg:
        print("⚠️  未找到配置，使用内置默认（仅品牌 Helios）")
    # 备案号强制
    if not cfg.get("icp"):
        print("⚠️  配置缺失 icp，使用内置默认：%s" % DEFAULT_ICP)
        cfg["icp"] = DEFAULT_ICP
    if not cfg.get("icpUrl"):
        cfg["icpUrl"] = DEFAULT_ICP_URL
    cfg.setdefault("brand", "Helios")
    return cfg


def render_header(cfg, current):
    """与 v3 site-shell.js renderHeader 逐字节一致。"""
    nav = cfg.get("nav") or []
    html = '<nav class="site-header" aria-label="全站导航"><div class="nav-inner">'
    html += '<a class="brand" href="%s">%s</a>' % (nav[0]["href"] if nav else "/", cfg["brand"])
    html += '<div class="nav-links">'
    for item in nav:
        cls = ' class="active"' if item.get("site") and item["site"] == current else ""
        ext = ' target="_blank" rel="noopener"' if item.get("external") else ""
        html += '<a href="%s"%s%s>%s</a>' % (item["href"], cls, ext, item["label"])
    html += "</div></div></nav>"
    return html


def render_footer(cfg, year):
    """与 v3 site-shell.js renderFooter 逐字节一致。"""
    return (
        '<footer class="site-footer"><div class="footer-inner">'
        '<div class="footer-copy">© %d %s · '
        '<a href="%s" target="_blank" rel="noopener">%s</a>'
        "</div></div></footer>" % (year, cfg["brand"], cfg["icpUrl"], cfg["icp"])
    )


def inject_html(path, cfg):
    """对单个 html 执行注入，返回是否发生替换。"""
    with open(path, encoding="utf-8") as f:
        html = f.read()
    if not HEADER_RE.search(html) and not FOOTER_RE.search(html):
        return False
    m = SITE_RE.search(html)
    current = m.group(1) if m else ""
    year = date.today().year
    html = HEADER_RE.sub(render_header(cfg, current), html, count=1)
    html = FOOTER_RE.sub(render_footer(cfg, year), html, count=1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return True


def main():
    ap = argparse.ArgumentParser(description="全站外壳静态注入")
    ap.add_argument("--root", default=os.getcwd())
    ap.add_argument("--config", default="")
    ap.add_argument("--config-url", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    root = os.path.realpath(args.root)
    out = os.path.realpath(args.out) if args.out else os.path.join(root, "dist")
    config_path = args.config or os.path.join(root, "site-config.json")
    cfg = load_config(root, config_path, args.config_url)

    # 镜像全树到 dist（排除 .git / dist / 自身产物）
    if os.path.isdir(out):
        shutil.rmtree(out)
    shutil.copytree(
        root, out,
        ignore=shutil.ignore_patterns(".git", "dist", ".DS_Store", "__pycache__"),
    )
    print("📁 镜像到 %s" % out)

    injected = skipped = 0
    for dirpath, _, files in os.walk(out):
        for fn in sorted(files):
            if not fn.endswith(".html"):
                continue
            p = os.path.join(dirpath, fn)
            if inject_html(p, cfg):
                injected += 1
            else:
                skipped += 1
    print("✅ 注入完成：%d 页注入，%d 页无占位符跳过（保留原样）" % (injected, skipped))


if __name__ == "__main__":
    main()
