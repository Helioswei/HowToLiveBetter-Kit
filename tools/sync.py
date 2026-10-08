#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把上游仓库同步到本地缓存，并记下同步的是哪一版。

    python3 tools/sync.py                     # 浅克隆到 .cache/upstream
    python3 tools/sync.py --local ~/path      # 直接用本地已有的克隆（开发时用）
    python3 tools/sync.py --force             # 忽略缓存，重新克隆

产物：.cache/upstream/（正文，gitignore）+ build/upstream.json（版本指纹）

为什么不用 raw.githubusercontent：实测国内直连返回 000 不可达；git 走 SSH/HTTPS 更稳。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

REPO = "https://github.com/eternity4719/HowToLiveBetter"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*args, **kw):
    out = subprocess.run(("git",) + args, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, **kw)
    if out.returncode != 0:
        raise SystemExit("git %s 失败：\n%s" % (" ".join(args), out.stdout.decode("utf-8", "replace")))
    return out.stdout.decode("utf-8", "replace").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", help="已有的上游克隆目录（不联网）")
    ap.add_argument("--dest", default=os.path.join(ROOT, ".cache", "upstream"))
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "upstream.json"))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    if a.local:
        src = os.path.abspath(os.path.expanduser(a.local))
        if not os.path.isfile(os.path.join(src, "README.md")):
            raise SystemExit("%s 看起来不是上游仓库（没有 README.md）" % src)
    else:
        src = a.dest
        if a.force and os.path.isdir(src):
            shutil.rmtree(src)
        if not os.path.isdir(os.path.join(src, ".git")):
            os.makedirs(os.path.dirname(src), exist_ok=True)
            print("浅克隆上游 → %s" % src)
            git("clone", "--depth", "1", REPO, src)
        else:
            print("复用已有缓存 %s（--force 可重新克隆）" % src)

        # 缓存已经有就拉一下，拿最新版
        try:
            git("-C", src, "fetch", "--depth", "1", "origin", "HEAD")
            git("-C", src, "reset", "--hard", "FETCH_HEAD")
        except SystemExit as e:
            print("拉取失败，继续用缓存里的版本：%s" % str(e).splitlines()[0])

    commit = git("-C", src, "rev-parse", "HEAD")
    short = commit[:10]
    date = git("-C", src, "log", "-1", "--format=%cI")
    meta = {
        "repo": REPO,
        "commit": commit,
        "commit_short": short,
        "commit_date": date,
        "synced_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source": "local" if a.local else "clone",
        "root": src,
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    print("上游版本：%s（%s）" % (short, date))
    print("写出版本指纹：%s" % a.out)


if __name__ == "__main__":
    main()
