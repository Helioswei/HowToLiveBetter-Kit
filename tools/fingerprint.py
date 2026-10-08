#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容指纹：把每条（标题 + 六个字段）哈希成 12 位，存进 sync/fingerprint.json。

为什么要这么绕：我们不想把别人的正文放进自己仓库，但又必须能一眼看出
"上游哪一条被改了、哪一条是新加的"。存哈希就同时满足这两条 ——
仓库里没有一个字是正文，任何一条内容变化都会让对应哈希变掉。

    python3 tools/fingerprint.py            # 生成/更新 sync/fingerprint.json
    python3 tools/fingerprint.py --diff     # 与 git HEAD 里那版比，打印变动清单
    python3 tools/fingerprint.py --diff --prev <文件>   # 与指定文件比
    python3 tools/fingerprint.py --check    # 有变动时退出码 1（CI 用它决定要不要提交）
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import hltb  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FP = os.path.join(ROOT, "sync", "fingerprint.json")
VERSION = 1


def entry_hash(e):
    h = hashlib.sha1()
    h.update(e["title"].encode("utf-8"))
    for k in hltb.FIELDS:
        h.update(b"\x1f")
        h.update((e["fields"].get(k) or "").encode("utf-8"))
    for k in hltb.TAG_KEYS:
        h.update(b"\x1f")
        h.update((e["tags"].get(k) or "").encode("utf-8"))
    return h.hexdigest()[:12]


def build(root):
    book = hltb.parse(root)
    entries = {"%d.%d" % (e["sec"], e["num"]): entry_hash(e) for e in book["entries"]}
    sections = {"%d" % s["num"]: hashlib.sha1(s["title"].encode("utf-8")).hexdigest()[:12]
                for s in book["sections"]}
    commit = _commit(root)
    return {
        "version": VERSION,
        "commit": commit,
        "commit_short": commit[:10],
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "count": len(entries),
        "sections": len(sections),
        "note": "只存哈希，不含正文。条目哈希 = sha1(标题 + 六个字段 + 五个标签)[:12]",
        "entries": entries,
        "section_titles": sections,
    }


def _commit(root):
    try:
        return subprocess.check_output(["git", "-C", root, "rev-parse", "HEAD"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""


def load_prev(root, prev_path=None):
    if prev_path:
        with open(prev_path, encoding="utf-8") as fh:
            return json.load(fh)
    try:
        out = subprocess.check_output(["git", "-C", ROOT, "show", "HEAD:sync/fingerprint.json"],
                                      stderr=subprocess.DEVNULL)
        return json.loads(out.decode("utf-8"))
    except Exception:
        return None


def diff(old, new):
    if not old:
        return {"added": sorted(new["entries"]), "removed": [], "changed": [], "first": True}
    o, n = old.get("entries", {}), new["entries"]
    return {
        "added": sorted(set(n) - set(o)),
        "removed": sorted(set(o) - set(n)),
        "changed": sorted(k for k in set(o) & set(n) if o[k] != n[k]),
        "first": False,
    }


def summarize(d):
    if d["first"]:
        return "首次生成指纹：%d 条" % len(d["added"])
    bits = []
    if d["added"]:
        bits.append("新增 %d 条（%s）" % (len(d["added"]), "、".join(d["added"][:8])))
    if d["removed"]:
        bits.append("删除 %d 条（%s）" % (len(d["removed"]), "、".join(d["removed"][:8])))
    if d["changed"]:
        bits.append("改写 %d 条（%s）" % (len(d["changed"]), "、".join(d["changed"][:8])))
    return "；".join(bits) if bits else "内容无变化"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="上游目录，默认取 build/upstream.json 里记的那份")
    ap.add_argument("--out", default=FP)
    ap.add_argument("--diff", action="store_true", help="与上一版比对并打印变动")
    ap.add_argument("--prev", help="指定上一版指纹文件")
    ap.add_argument("--check", action="store_true", help="有变动时退出码 1")
    a = ap.parse_args()

    a.root = a.root or hltb.default_root(ROOT)
    new = build(a.root)
    old = load_prev(a.root, a.prev)
    d = diff(old, new)
    summary = summarize(d)

    if a.diff or a.check:
        print("内容变动：%s" % summary)
        for label, keys in (("新增", d["added"]), ("删除", d["removed"]), ("改写", d["changed"])):
            if keys:
                print("  %s：%s%s" % (label, "、".join(keys[:30]), " …" if len(keys) > 30 else ""))
        if old and old.get("commit_short") and old["commit_short"] != new["commit_short"]:
            print("  上游提交：%s → %s" % (old["commit_short"], new["commit_short"]))
        if a.check:
            changed = bool(d["added"] or d["removed"] or d["changed"])
            sys.exit(1 if changed else 0)
        return

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(new, fh, ensure_ascii=False, indent=0, sort_keys=True)
        fh.write("\n")
    print("指纹：%d 条 / %d 节 → %s（%.0f KB，不含正文）"
          % (new["count"], new["sections"], a.out, os.path.getsize(a.out) / 1024.0))
    print("与上一版比：%s" % summary)


if __name__ == "__main__":
    main()
