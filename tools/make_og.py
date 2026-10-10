#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成社交分享图 deploy/assets/og.png（1200×630）。

**只在本机跑**：它用 headless Chrome 把 tools/og.html 截成 PNG，然后把结果入库
（CI 里没有 Chrome，也不需要 —— 产物直接提交，build_site 只负责把它拷进站点）。

    python3 tools/make_og.py

图里的小图 = /map.html 那张分布图的同款气泡（复用 build_site.scatter_svg，
保证分享图和站内那张图长得一样）。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "lib"))

import build_site  # noqa: E402  只为了复用 scatter_svg（模块级常量，不会跑 main）

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def main() -> int:
    with open(os.path.join(ROOT, "data", "book.json"), encoding="utf-8") as fh:
        book = json.load(fh)
    entries = [{"cost": e.get("cost", 0), "tags": e["g"], "ratio": e["ratio"]} for e in book["entries"]]

    tpl = open(os.path.join(ROOT, "tools", "og.html"), encoding="utf-8").read()
    dots = build_site.scatter_svg(entries, w=430, h=430, dot_max=19, pad=(38, 28, 26, 50), font=13)
    html = tpl.replace("__POINTS__", dots)
    tmp = os.path.join(ROOT, "build", "og.html")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("  填好模板 → %s（%d 个气泡）" % (tmp, dots.count("<circle")))

    if not os.path.exists(CHROME):
        print("  ✗ 找不到 Chrome，无法截图（模板已生成，可在浏览器里手动导）")
        return 1
    out = os.path.join(ROOT, "deploy", "assets", "og.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
                    "--window-size=1200,630", "--screenshot=" + out, "file://" + tmp],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    size = os.path.getsize(out)
    print("  ✅ %s（%.1f KB）" % (out, size / 1024))
    if size < 20000:
        print("  ⚠️ 文件偏小，可能没截到内容")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
