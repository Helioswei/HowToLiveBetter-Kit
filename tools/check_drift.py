#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""格式体检：上游改了格式 / 新增了字段 / 出现了没见过的标签取值 —— 当天就报出来。

    python3 tools/check_drift.py                # 体检并写出 build/drift.json
    python3 tools/check_drift.py --quiet        # 只报结论（CI 用）

分两档：
  error   = 我们的解析或筛选会出错/漏内容，退出码 1，CI 红
  warning = 值得人看一眼（上游新增字段、新增标签取值、条目数变化），退出码仍是 0

为什么要有这个：解析器只认它认识的形状，上游新增一个字段不会报错，
只会被静默丢掉 —— 静默丢失比报错危险得多。
"""

import argparse
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import hltb  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 我们认识的标签取值。上游出现新取值时不报错，但要立刻让人看见（否则筛选会漏条目）。
KNOWN_VALUES = {
    "钱": {"0", "少", "多"},
    "时间": {"少", "中", "多"},
    "毅力": {"否", "些", "是"},
    "收益": {"大", "中", "小"},
    "口径": {"死亡率", "金钱", "时间", "自由"},
}
KNOWN_FIELDS = set(hltb.FIELDS)
# 上游正文里出现过的、我们知道但故意不搬的字段标签（别把正常的当异常报）
IGNORED_LABELS = {"证据等级", "成本", "收益", "说人话", "来源", "备注"}

RE_ANY_LABEL = re.compile(r"^-\s*([^\s：:]{1,8})\s*[：:]", re.M)


def scan_raw_labels(root):
    """独立扫一遍原文，找出所有「- xxx：」形式的字段名（不靠解析库）。"""
    from os import listdir

    seen = Counter()
    for name in sorted(listdir(os.path.join(root, "book"))):
        if not re.match(r"^\d{2}-.+\.md$", name):
            continue
        with open(os.path.join(root, "book", name), encoding="utf-8") as fh:
            for m in RE_ANY_LABEL.finditer(fh.read()):
                seen[m.group(1)] += 1
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="上游目录，默认取 build/upstream.json 里记的那份")
    ap.add_argument("--json", default=os.path.join(ROOT, "build", "drift.json"))
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    a.root = a.root or hltb.default_root(ROOT)
    errors, warnings, info = [], [], []

    try:
        book = hltb.parse(a.root)
    except Exception as exc:  # parse 抛错本身就是最严重的一档
        errors.append("解析失败（上游格式可能变了）：%s" % exc)
        report(a, errors, warnings, info, quiet=a.quiet)
        return

    sections, entries = book["sections"], book["entries"]
    info.append("节 %d · 条目 %d" % (len(sections), len(entries)))

    # 1. 条号必须从 1 连续
    for s in sections:
        nums = [e["num"] for e in s["entries"]]
        if nums != list(range(1, len(nums) + 1)):
            if len(set(nums)) != len(nums):
                errors.append("第 %d 节条号有重复：%s" % (s["num"], nums))
            else:
                warnings.append("第 %d 节条号不连续（不一定是错，但值得看）：%s" % (s["num"], nums))

    # 2. 成本标签行：我们靠它做筛选，缺一个就会漏
    missing_tags = [e for e in entries if not e["tags"]]
    if missing_tags:
        errors.append("%d 条缺成本标签注释（会被筛选漏掉），例如 %s"
                      % (len(missing_tags), ["%d.%d" % (e["sec"], e["num"]) for e in missing_tags[:5]]))

    # 3. 标签取值：上游新增取值 → 提醒（不是错，但筛选要跟着加）
    for key, allowed in KNOWN_VALUES.items():
        bad = Counter(e["tags"].get(key) for e in entries
                      if key in e["tags"] and e["tags"][key] not in allowed)
        if bad:
            warnings.append("标签「%s」出现没见过的取值：%s（筛选枚举要跟着加）"
                            % (key, dict(bad)))

    # 4. 说人话覆盖率（阅读页最显眼的一行，缺了整块少一段）
    no_human = [e for e in entries if not e["fields"].get("说人话")]
    if no_human:
        warnings.append("%d 条没有「说人话」，例如 %s"
                        % (len(no_human), ["%d.%d" % (e["sec"], e["num"]) for e in no_human[:5]]))

    # 5. 有没有我们不认识的字段名（上游新增字段会被静默丢掉）
    labels = scan_raw_labels(a.root)
    unknown = {k: v for k, v in labels.items() if k not in KNOWN_FIELDS}
    if unknown:
        warnings.append("上游正文出现我们不认识的字段名：%s（如果不是引文里的冒号，就要加进解析）"
                        % unknown)

    # 6. 交叉引用
    refs = [r for e in entries for r in e["xrefs"]]
    broken = sum(len(e["xrefs_missing"]) for e in entries)
    info.append("交叉引用 %d 处（指向不存在的 %d 处）" % (len(refs), broken))
    if broken:
        warnings.append("%d 处交叉引用指向不存在的条目" % broken)

    # 7. 与仓库里那份指纹比对（内容增减）
    fp = os.path.join(ROOT, "sync", "fingerprint.json")
    if os.path.isfile(fp):
        with open(fp, encoding="utf-8") as fh:
            old = json.load(fh)
        old_n, new_n = old.get("count", 0), len(entries)
        old_s, new_s = old.get("sections", 0), len(sections)
        if old_n and new_n < old_n:
            errors.append("条目数减少：%d → %d（少了 %d 条 —— 上游删了，还是我们漏解析了？）"
                          % (old_n, new_n, old_n - new_n))
        elif old_n and new_n > old_n:
            warnings.append("条目数增加：%d → %d（新增 %d 条，会一起进站点与 MCP）"
                            % (old_n, new_n, new_n - old_n))
        if old_s and old_s != new_s:
            errors.append("节数变化：%d → %d（少一节通常意味着文件名或格式变了）" % (old_s, new_s))
        if old.get("commit") and old["commit"] != _commit(a.root):
            info.append("上游提交推进：%s → %s" % (old["commit"][:10], _commit(a.root)[:10]))

    report(a, errors, warnings, info, quiet=a.quiet)


def _commit(root):
    try:
        import subprocess
        return subprocess.check_output(["git", "-C", root, "rev-parse", "HEAD"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""


def report(a, errors, warnings, info, quiet=False):
    payload = {"errors": errors, "warnings": warnings, "info": info}
    os.makedirs(os.path.dirname(a.json), exist_ok=True)
    with open(a.json, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    if not quiet:
        for line in info:
            print("  · %s" % line)
    for line in warnings:
        print("  ⚠️ %s" % line)
    for line in errors:
        print("  ✗ %s" % line)
    print("格式体检：错误 %d 项，提醒 %d 项 → %s" % (len(errors), len(warnings), a.json))
    if errors:
        print("结论：上游格式已经偏离我们的假设，先修解析再发布")
        sys.exit(1)
    print("结论：格式与取值都在已知范围内" + ("（有提醒，建议看一眼）" if warnings else ""))


if __name__ == "__main__":
    main()
