#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析上游正文 → build/entries.json（站点与 MCP 共用的唯一中间产物）。

    python3 tools/parse.py                          # 读 .cache/upstream
    python3 tools/parse.py --root ~/HowToLiveBetter # 读指定目录
    python3 tools/parse.py --check                  # 只校验不写文件（CI 用）
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import hltb  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="上游目录，默认取 build/upstream.json 里记的那份")
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "entries.json"))
    ap.add_argument("--check", action="store_true", help="只校验，不写文件")
    a = ap.parse_args()

    a.root = a.root or hltb.default_root(ROOT)
    if not os.path.isfile(os.path.join(a.root, "README.md")):
        raise SystemExit("找不到上游正文：%s（先跑 tools/sync.py）" % a.root)

    try:
        book = hltb.parse(a.root)
    except hltb.ParseError as exc:
        # Blender 的教训：上游改格式时我们要看到一句人话，而不是一段 traceback
        raise SystemExit("解析失败（上游格式可能变了）：%s\n"
                         "处理方式：看第 %s 节那个文件的新写法，改 tools/lib/hltb.py 的解析规则后重跑。"
                         % (exc, getattr(exc, "section", "对应")))
    st = hltb.stats(book)

    print("节 %d · 条目 %d · 交叉引用 %d 处（指向不存在的 %d 处）"
          % (st["sections"], st["entries"], st["xrefs"], st["xrefs_missing"]))
    print("证据等级 %s" % st["evidence"])
    print("收益量级 %s" % st["benefit"])
    print("成本 钱=%s 时间=%s 毅力=%s" % (st["cost_money"], st["cost_time"], st["cost_will"]))
    print("口径 %s" % st["caliber"])

    if st["entries"] < 600:
        raise SystemExit("条目数异常（%d < 600），上游可能改了格式" % st["entries"])
    if st["xrefs_missing"]:
        print("⚠️ 有 %d 处交叉引用指向不存在的条目（上游自己也可能有，不拦构建）" % st["xrefs_missing"])

    if a.check:
        print("校验通过（未写文件）")
        return

    meta = {}
    plain = os.path.join(ROOT, "build", "upstream.json")
    if os.path.isfile(plain):
        with open(plain, encoding="utf-8") as fh:
            meta = json.load(fh)

    payload = {
        "source": {
            "repo": hltb.REPO,
            "author": hltb.AUTHOR,
            "title": hltb.TITLE,
            "license": hltb.LICENSE_NAME,
            "license_url": hltb.LICENSE_URL,
            "commit": meta.get("commit"),
            "commit_short": meta.get("commit_short"),
            "commit_date": meta.get("commit_date"),
            "synced_at": meta.get("synced_at"),
            "note": "正文原样转载，未作内容改动；只做了结构化解析。",
        },
        "stats": st,
        "sections": book["sections"],
        "entries": book["entries"],
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    size = os.path.getsize(a.out)
    print("写出 %s（%.0f KB）" % (a.out, size / 1024.0))


if __name__ == "__main__":
    main()
