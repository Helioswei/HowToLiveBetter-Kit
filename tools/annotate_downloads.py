#!/usr/bin/env python3
"""把镜像来的电子版体积填进下载页（构建/发布时调用）。

为什么不在 build_site.py 里量：生成站点的时候这些文件还没到手 ——
CI 里是"先生成站点、后镜像电子版"，Makers 构建时又是解包来的。
所以下载页只留空占位，谁手上有文件谁填：幂等、缺文件就不填、不报错。

用法：
    python3 tools/annotate_downloads.py --site build/site      # CI
    python3 tools/annotate_downloads.py --site dist --quiet    # 部署脚本里再兜一次
"""
from __future__ import annotations

import argparse
import os
import re
import sys

FILES = ("HowToLiveBetter.epub", "HowToLiveBetter.pdf",
         "HowToLiveBetter.html", "HowToLiveBetter.apkg")


def human(n: int) -> str:
    if n >= 1048576:
        mb = n / 1048576.0
        return ("%.1f MB" % mb) if mb < 10 else ("%.0f MB" % mb)
    return "%d KB" % max(1, round(n / 1024.0))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="build/site", help="站点产物目录（含 download.html 与 download/）")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    page = os.path.join(a.site, "download.html")
    if not os.path.exists(page):
        print("✗ 找不到 %s（先跑 build_site.py）" % page, file=sys.stderr)
        return 1
    with open(page, encoding="utf-8") as fh:
        html = fh.read()

    sizes, missing = {}, []
    for name in FILES:
        path = os.path.join(a.site, "download", name)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            sizes[name] = os.path.getsize(path)
        else:
            missing.append(name)

    slot = re.compile(r'(<em class="b-dl-size" data-file="([^"]+)">)(.*?)(</em>)')

    def fill(m: "re.Match[str]") -> str:
        head, name, _old, tail = m.groups()
        return head + (human(sizes[name]) if name in sizes else "") + tail

    new = slot.sub(fill, html)

    if len(sizes) == len(FILES):
        total = sum(sizes.values())
        note = "四份合计 %.1f MB。按需下载，不必全下 —— 只想手机上看就 EPUB，想打印就 PDF。" % (total / 1048576.0)
    else:
        note = ""  # 只量到一部分时不给总数：宁可空着，不许给错数
    new = re.sub(r'(<p class="b-stat" data-dl-total>)(.*?)(</p>)',
                 lambda m: m.group(1) + note + m.group(3), new, flags=re.S)

    if new != html:
        with open(page, "w", encoding="utf-8") as fh:
            fh.write(new)
    if not a.quiet:
        print("  填了 %d/%d 个体积%s" % (len(sizes), len(FILES),
              ("（缺：" + " ".join(missing) + "）") if missing else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
