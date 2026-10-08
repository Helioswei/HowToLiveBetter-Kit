#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 build/entries.json 压成 MCP 随包发布的数据（data/book.json）。

    python3 tools/build_mcp_data.py
    python3 tools/build_mcp_data.py --site-base https://better.aigcwei.cn

只做三件事，不改任何原文：
  1. 证据等级拆成 level（A/B/C）+ 原文（A（争议）这种原样留在 lvNote）
  2. 按上游算法算性价比档（cost / ratio）—— 权重表照抄上游 tools/lib/book.mjs
  3. 去掉站点渲染才需要的字段（节首导览、引言），压体积
"""

import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "build", "entries.json")
OUT = os.path.join(ROOT, "data", "book.json")

# 逐字照抄上游 tools/lib/book.mjs 的 COST_W（上游代码为 MIT，已署名）。
# 注意：「少」在三项里权重不同 —— 钱「少」= 1，时间「少」= 0。共用一张表会算错。
MONEY_W = {"0": 0, "少": 1, "多": 2}
TIME_W = {"少": 0, "中": 1, "多": 2}
WILL_W = {"否": 0, "些": 1, "是": 2}


def cost_of(tags):
    return (MONEY_W.get(tags.get("钱", "少"), 1)
            + TIME_W.get(tags.get("时间", "少"), 0)
            + WILL_W.get(tags.get("毅力", "些"), 1))


def ratio_of(cost, benefit):
    """照抄上游 ratioOf()。"""
    if benefit == "大":
        return "极高" if cost == 0 else ("高" if cost <= 2 else "一般")
    return "高" if (benefit == "中" and cost == 0) else "一般"


def level_of(raw):
    raw = (raw or "").strip()
    lv = raw[0] if raw[:1] in ("A", "B", "C") else "?"
    return lv, raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--site-base", default="https://better.aigcwei.cn",
                    help="我们镜像站的域名（用于生成单条链接）")
    a = ap.parse_args()

    with open(a.src, encoding="utf-8") as fh:
        data = json.load(fh)

    entries = []
    for e in data["entries"]:
        tags = e["tags"]
        cost = cost_of(tags)
        benefit = tags.get("收益", "中")
        lv, lv_note = level_of(e["fields"].get("证据等级", ""))
        entries.append({
            "s": e["sec"], "n": e["num"], "t": e["title"],
            "g": tags,
            "lv": lv, "lvNote": lv_note,
            "cost": cost, "ratio": ratio_of(cost, benefit),
            "f": e["fields"],
            "x": [list(r) for r in e["xrefs"]],
        })

    sections = [{"n": s["num"], "t": s["title"], "q": s["question"], "count": len(s["entries"])}
                for s in data["sections"]]

    src = dict(data["source"])
    src["site_base"] = a.site_base.rstrip("/")
    src["unofficial"] = True

    payload = {
        "source": src,
        "stats": data["stats"],
        "sections": sections,
        "entries": entries,
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))

    from collections import Counter
    rc = Counter(e["ratio"] for e in entries)
    print("MCP 数据：%d 条 / %d 节 → %s（%.0f KB）"
          % (len(entries), len(sections), a.out, os.path.getsize(a.out) / 1024.0))
    print("性价比档：%s" % dict(rc))
    print("证据等级：%s" % dict(Counter(e["lv"] for e in entries)))
    print("分带原文等级的：%s" % dict(Counter(e["lvNote"] for e in entries if e["lvNote"] != e["lv"])))
    print("镜像站链接前缀：%s" % src["site_base"])


if __name__ == "__main__":
    main()
