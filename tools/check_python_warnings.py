#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""护栏：我们自己的 .py 里不许出现"无效转义序列"。

为什么单独立这一条：页面脚本（阅读设置的悬浮面板、检索页）是**嵌在 Python 字符串里的
JavaScript**，里面有 /\\s+/g、\\u3002 这类 JS 正则与转义。只要写成非 raw 字符串，Python 就会
提前解析它或告警 —— 这个坑实际踩过两次：
  1. \\n 被 Python 吃成真换行，生成出一段语法错误的 JS（首屏卡在"正在载入索引…"）
  2. \\s 触发告警（当晚就被人看见），而当时的检查用 -W error::SyntaxWarning 只盯了一类，
     3.12 报的却是 DeprecationWarning，于是漏检
所以这里**两类都算**，并且把 SyntaxWarning 一律当问题（几乎总是真 bug）。

用法：
    python3 tools/check_python_warnings.py              # 默认扫 tools/ deploy/ scripts/
    python3 tools/check_python_warnings.py tools lib    # 指定文件或目录
退出码非 0 = 有人又写了非 raw 的嵌 JS 字符串（或别的无效转义）。
"""
from __future__ import annotations

import os
import sys
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DIRS = ("tools", "deploy", "scripts")
SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__", ".cache", ".venv", "venv"}


def targets(paths):
    for p in paths:
        if os.path.isfile(p):
            if p.endswith(".py"):
                yield p
            continue
        for dp, dn, fns in os.walk(p):
            dn[:] = [x for x in dn if x not in SKIP_DIRS]
            if os.path.abspath(dp) == ROOT:      # 仓库根的 lib/ 是 TS 编译产物，不是我们的源码
                dn[:] = [x for x in dn if x != "lib"]
            for f in sorted(fns):
                if f.endswith(".py"):
                    yield os.path.join(dp, f)


def main() -> int:
    paths = [os.path.join(ROOT, d) if not os.path.exists(d) else d
             for d in (sys.argv[1:] or list(DEFAULT_DIRS))]
    bad, n = [], 0
    for p in targets(paths):
        try:
            src = open(p, encoding="utf-8").read()
        except Exception as exc:                 # 读不了也要报，别静默跳过
            bad.append((p, 0, "读不了：%s" % exc))
            continue
        n += 1
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                compile(src, p, "exec")
            except SyntaxError as exc:
                bad.append((p, exc.lineno or 0, "语法错误：%s" % exc.msg))
                continue
            for it in caught:
                msg = str(it.message)
                if issubclass(it.category, SyntaxWarning) or "escape" in msg:
                    bad.append((p, it.lineno or 0, "%s: %s" % (it.category.__name__, msg)))

    for p, ln, msg in bad:
        print("  ✗ %s:%s  %s" % (os.path.relpath(p, ROOT), ln, msg))
    print("Python 告警自检：扫了 %d 个文件，问题 %d 处" % (n, len(bad)))
    if bad:
        print("  提示：嵌 JavaScript 的字符串必须写成 raw（r\"\"\"...\"\"\"）—— "
              "JS 的 /\\s+/g、\\u3002 才不会被 Python 提前解析或告警。")
        return 1
    print("  没有无效转义序列 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
