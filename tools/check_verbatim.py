#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""保真校验：证明 build/entries.json 里的每个字都来自上游原文，一个字没改。

    python3 tools/check_verbatim.py                        # 校验默认产物
    python3 tools/check_verbatim.py --json build/entries.json --root <上游目录>

设计要点：这里**故意不复用** tools/lib/hltb.py 的解析代码，而是用一套独立的、
更笨的逐行读法重新抽一遍字段，再和 JSON 比。两边是同一份代码就永远对得上，
那就不叫校验了。

退出码非 0 即表示有内容被改动或丢失。
"""

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RE_ENTRY = re.compile(r"^###\s+(\d+)\.\s+(.*)$")
RE_FIELD = re.compile(r"^-\s*(成本|说人话|收益|证据等级|来源|备注)：(.*)$")
RE_TAGLINE = re.compile(r"<!--\s*成本标签:\s*(.*?)\s*-->")
RE_SECTION_FILE = re.compile(r"^(\d{2})-(.+)\.md$")


def norm(s):
    """归一化：只去掉空白，其它一个字都不许动。"""
    return re.sub(r"\s+", "", s or "")


def _default_root():
    """上游目录：优先用 sync.py 记下来的那份，否则 .cache/upstream（本脚本独立实现，不引解析库）。"""
    meta = os.path.join(ROOT, "build", "upstream.json")
    if os.path.isfile(meta):
        try:
            with open(meta, encoding="utf-8") as fh:
                recorded = json.load(fh).get("root")
            if recorded and os.path.isfile(os.path.join(recorded, "README.md")):
                return recorded
        except Exception:
            pass
    return os.path.join(ROOT, ".cache", "upstream")


def extract_raw(root):
    """独立实现的抽取器：逐行读，返回 {(节, 条): {title, tags, fields}}。"""
    book_dir = os.path.join(root, "book")
    out = {}
    for name in sorted(os.listdir(book_dir)):
        m = RE_SECTION_FILE.match(name)
        if not m:
            continue
        sec = int(m.group(1))
        with open(os.path.join(book_dir, name), encoding="utf-8") as fh:
            lines = fh.read().replace("\r\n", "\n").split("\n")
        cur = None
        for line in lines:
            em = RE_ENTRY.match(line)
            if em:
                cur = {"title": em.group(2).strip(), "tags": {}, "fields": {}}
                out[(sec, int(em.group(1)))] = cur
                continue
            if cur is None:
                continue
            tm = RE_TAGLINE.search(line)
            if tm:
                for kv in tm.group(1).split():
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        cur["tags"][k.strip()] = v.strip()
                continue
            fm = RE_FIELD.match(line.strip())
            if fm:
                k, v = fm.group(1), fm.group(2).strip()
                cur["fields"][k] = (cur["fields"].get(k, "") + " " + v).strip()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=os.path.join(ROOT, "build", "entries.json"))
    ap.add_argument("--root", default=None, help="上游目录，默认取 build/upstream.json 里记的那份")
    a = ap.parse_args()

    a.root = a.root or _default_root()
    for p, what in ((a.json, "entries.json"), (os.path.join(a.root, "book"), "上游正文")):
        if not os.path.exists(p):
            raise SystemExit("找不到%s：%s" % (what, p))

    with open(a.json, encoding="utf-8") as fh:
        data = json.load(fh)

    raw = extract_raw(a.root)
    bad, checked = [], 0

    if len(raw) != len(data["entries"]):
        bad.append(("条目数", "上游 %d 条 / 产物 %d 条" % (len(raw), len(data["entries"]))))

    for e in data["entries"]:
        key = (e["sec"], e["num"])
        src = raw.get(key)
        if not src:
            bad.append((key, "上游找不到这一条"))
            continue
        checked += 1
        if norm(e["title"]) != norm(src["title"]):
            bad.append((key, "标题", e["title"][:40], src["title"][:40]))
        for k, want in src["fields"].items():
            checked += 1
            got = e["fields"].get(k)
            if norm(got) != norm(want):
                bad.append((key, "字段 " + k, str(got)[:40], want[:40]))
        for k, want in src["tags"].items():
            checked += 1
            got = e["tags"].get(k)
            if norm(got) != norm(want):
                bad.append((key, "标签 " + k, str(got), want))

    print("保真校验：比对 %d 项（%d 条 × 标题/字段/标签），不一致 %d 项"
          % (checked, len(data["entries"]), len(bad)))
    for b in bad[:20]:
        print("  ✗ %s" % (b,))
    if bad:
        print("结论：产物与上游原文不一致，不许发布")
        sys.exit(1)
    print("结论：产物与上游原文逐字一致（只做了技术性处理：去空白差异、转链接）")


if __name__ == "__main__":
    main()
