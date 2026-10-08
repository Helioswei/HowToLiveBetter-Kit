#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""证明"检测不是摆设"：故意按几种方式破坏上游，看每个检查能不能抓到。

    python3 tools/test_detection.py
    python3 tools/test_detection.py --upstream ~/AIWork/HowToLiveBetter

一个永远通过的检测器等于没有检测器。这个脚本每次都真的改坏一份上游副本，
然后断言对应的那个检查确实报出来了（并且退出码符合预期）。
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(cmd, **kw):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kw)
    return p.returncode, p.stdout.decode("utf-8", "replace")


def copy_upstream(src, dst):
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git"))


def first_section_file(root):
    book = os.path.join(root, "book")
    return os.path.join(book, sorted(os.listdir(book))[0])


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def write(p, s):
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(s)


# ---------------------------------------------------------------- 六种破坏方式

def break_field_name(root):
    """上游把字段名改了（收益 → 利润）：解析必须直接失败，不许写出半本书。"""
    p = first_section_file(root)
    s = read(p)
    s = s.replace("- 收益：", "- 利润：", 1)
    write(p, s)
    # 用格式体检跑：它会接住解析异常并给人话（parse.py 单独跑也会退出 1）
    return ["python3", "tools/check_drift.py"]


def break_tag_value(root):
    """上游用了没见过的标签取值（钱=负）：格式体检要提醒，不能静默漏掉这批条目。"""
    p = first_section_file(root)
    s = read(p)
    s = re.sub(r"钱=0", "钱=负", s, count=1)
    write(p, s)
    return ["python3", "tools/check_drift.py"]


def add_unknown_field(root):
    """上游新增了一个字段（适用人群）：我们没搬，体检要提醒（否则等于丢内容）。"""
    p = first_section_file(root)
    s = read(p)
    s = s.replace("\n- 证据等级：", "\n- 适用人群：成年人\n- 证据等级：", 1)
    write(p, s)
    return ["python3", "tools/check_drift.py"]


def add_entry(root):
    """上游新增一条：指纹要报出来（新增不会被拦，但必须看得见）。"""
    p = first_section_file(root)
    s = read(p)
    s += ("\n### 9999. 这是一条用来验证检测的新条目\n"
          "<!-- 成本标签: 钱=0 时间=少 毅力=否 收益=大 口径=死亡率 -->\n"
          "- 成本：不花钱。\n- 说人话：检测用。\n- 收益：检测用。\n- 证据等级：C\n"
          "- 来源：检测用。\n- 备注：检测用。\n")
    write(p, s)
    return ["python3", "tools/fingerprint.py", "--diff"]


def edit_entry(root):
    """上游改写了一条：指纹要报"改写"，我们才知道要重新同步。"""
    p = first_section_file(root)
    s = read(p)
    s = re.sub(r"(- 说人话：.{0,20})", r"\1【改过】", s, count=1)
    write(p, s)
    return ["python3", "tools/fingerprint.py", "--diff"]


def delete_section(root):
    """上游少了一节（改名/合并）：体检要报错，因为整节的条目会凭空消失。"""
    os.remove(first_section_file(root))
    return ["python3", "tools/check_drift.py"]


SCENARIOS = [
    ("字段改名（收益→利润）", break_field_name, "解析失败", 1, ["解析失败", "缺字段"]),
    ("标签新取值（钱=负）", break_tag_value, "提醒", 0, ["没见过的取值", "负"]),
    ("上游新增字段（适用人群）", add_unknown_field, "提醒", 0, ["不认识的字段名", "适用人群"]),
    ("新增一条", add_entry, "指纹报新增", 0, ["新增 1 条", "9999"]),
    ("改写一条正文", edit_entry, "指纹报改写", 0, ["改写 1 条"]),
    ("少了一节", delete_section, "报错", 1, ["节数变化", "条目数减少"]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", default=os.path.expanduser("~/AIWork/HowToLiveBetter"))
    ap.add_argument("--keep", action="store_true", help="保留临时目录，方便自己看")
    a = ap.parse_args()

    if not os.path.isfile(os.path.join(a.upstream, "README.md")):
        raise SystemExit("找不到上游：%s" % a.upstream)

    # 先按正常上游跑一遍流水线，生成 build/entries.json 与 sync/fingerprint.json（供比对）
    print("准备：用真实上游生成基线 …")
    for cmd in (["python3", "tools/sync.py", "--local", a.upstream],
                ["python3", "tools/parse.py", "--root", a.upstream],
                ["python3", "tools/fingerprint.py", "--root", a.upstream]):
        rc, out = run(cmd, cwd=ROOT)
        if rc != 0:
            print("基线生成失败：%s\n%s" % (cmd, out))
            sys.exit(1)

    passed = failed = 0
    for name, mutate, expect_what, expect_rc, needles in SCENARIOS:
        tmp = tempfile.mkdtemp(prefix="hltb-drift-")
        work = os.path.join(tmp, "upstream")
        copy_upstream(a.upstream, work)
        cmd = mutate(work)
        # 指纹对比默认读 git HEAD 里的那版；这里还没提交过，所以显式给基线文件
        if "tools/fingerprint.py" in " ".join(cmd):
            cmd += ["--prev", os.path.join(ROOT, "sync", "fingerprint.json")]
        rc, out = run(cmd + ["--root", work], cwd=ROOT)
        hit = all(n in out for n in needles)
        ok = (rc == expect_rc) and hit
        if ok:
            passed += 1
            print("  ✔ %-22s → 抓到了（%s；退出码 %d）" % (name, expect_what, rc))
        else:
            failed += 1
            print("  ✗ %-22s → 没抓到！期望退出码 %d 且包含 %s，实际退出码 %d"
                  % (name, expect_rc, needles, rc))
            print("     输出：%s" % out.strip()[:400].replace("\n", "\n     "))
        if not a.keep:
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            print("     保留：%s" % tmp)

    print()
    print("破坏性检测自测：%d 项通过，%d 项失败" % (passed, failed))
    if failed:
        print("结论：有检查抓不到对应的破坏方式，检测不等于有效")
        sys.exit(1)
    print("结论：六种破坏方式全部被对应检查抓到")


if __name__ == "__main__":
    main()
