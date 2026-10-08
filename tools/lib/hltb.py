# -*- coding: utf-8 -*-
"""《高性价比人生指南》正文解析：上游 Markdown → 结构化条目。

只依赖上游稳定的形状，不维护硬编码的文件名单（节名与「这一节回答什么」从 README 的表格读）：

    ### N. 标题
    <!-- 成本标签: 钱=0 时间=少 毅力=否 收益=大 口径=死亡率 -->
    - 成本：… - 说人话：… - 收益：… - 证据等级：… - 来源：… - 备注：…

上游改格式时这里会直接抛错（而不是悄悄写出半本书），CI 当天就红。
只依赖标准库，按 Python 3.9 兼容写。
"""

import html
import json
import os
import re

REPO = "https://github.com/eternity4719/HowToLiveBetter"
AUTHOR = "eternity4719"
TITLE = "高性价比人生指南"
LICENSE_NAME = "CC BY 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"

FIELDS = ("成本", "说人话", "收益", "证据等级", "来源", "备注")
TAG_KEYS = ("钱", "时间", "毅力", "收益", "口径")

RE_SECTION_FILE = re.compile(r"^(\d{2})-(.+)\.md$")
RE_H1 = re.compile(r"^#\s+(\d+)\.\s+(.*)$", re.M)
RE_ENTRY = re.compile(r"^###\s+(\d+)\.\s+(.*)$", re.M)
RE_TAGLINE = re.compile(r"<!--\s*成本标签:\s*(.*?)\s*-->")
RE_FIELD = re.compile(r"^-\s*(成本|说人话|收益|证据等级|来源|备注)：(.*)$")
RE_README_ROW = re.compile(r"^\|\s*(.+?)\s*\|\s*\[(\d+)\.\s*([^\]]+)\]\([^)]*\)\s*\|$", re.M)
# 正文里的互相指路：「见第 8 节第 17 条」「见本节第 3 条」
RE_XREF_FAR = re.compile(r"见第\s*(\d+)\s*节第\s*(\d+)\s*条")
RE_XREF_NEAR = re.compile(r"见本节第\s*(\d+)\s*条")
# 上游每节开头的返回链接，我们自己的壳负责导航
RE_BACK_LINK = re.compile(r"^\[← 回总目录\]\([^)]*\)\s*\n")
RE_H2 = re.compile(r"^##\s+(.+)$", re.M)

# 上游 docs/ 下"按时间排的场景长文"：H2 就是时间段（当天 / 头一周 / 头一个月…）。
# 只收这份白名单里的，顺序即页面展示顺序；上游哪天新加一篇，这里加一行、给个英文 slug 即可。
SCENE_SLUGS = {
    "被裁了之后先做什么": "laid-off",
    "孩子出生前后要办的事": "having-a-baby",
    "刚确诊慢性病之后": "new-diagnosis",
    "换工作、换城市之前": "job-and-city-change",
}


class ParseError(RuntimeError):
    pass


def read_text(root, rel):
    """读一个正文文件，统一成 LF（Windows 检出可能是 CRLF）。"""
    with open(str(root) + "/" + rel, encoding="utf-8") as fh:
        return fh.read().replace("\r\n", "\n")


def default_root(repo_root):
    """上游正文目录：优先用 sync.py 记下来的那份（可能是本地克隆），否则 .cache/upstream。

    这样 `tools/sync.py --local ~/某处` 之后，后面所有脚本不用再传 --root。
    """
    meta = os.path.join(repo_root, "build", "upstream.json")
    if os.path.isfile(meta):
        try:
            with open(meta, encoding="utf-8") as fh:
                recorded = json.load(fh).get("root")
            if recorded and os.path.isfile(os.path.join(recorded, "README.md")):
                return recorded
        except Exception:
            pass
    return os.path.join(repo_root, ".cache", "upstream")


def _readme_questions(readme):
    """README 的表格给了节名和「这一节回答什么问题」，节号 -> (节名, 问题)。"""
    out = {}
    for m in RE_README_ROW.finditer(readme):
        out[int(m.group(2))] = (m.group(3).strip(), m.group(1).strip())
    return out


def _parse_tags(block):
    m = RE_TAGLINE.search(block)
    if not m:
        return {}
    tags = {}
    for kv in m.group(1).split():
        if "=" in kv:
            k, v = kv.split("=", 1)
            tags[k.strip()] = v.strip()
    return tags


def _parse_fields(block):
    fields = {}
    for line in block.split("\n"):
        m = RE_FIELD.match(line.strip())
        if m:
            fields.setdefault(m.group(1), []).append(m.group(2).strip())
    return {k: " ".join(v).strip() for k, v in fields.items()}


def parse(root):
    """解析整本书。返回 {"sections": [...], "entries": [...]}。"""
    from os import listdir

    readme = read_text(root, "README.md")
    questions = _readme_questions(readme)

    book_dir = str(root) + "/book"
    names = sorted(n for n in listdir(book_dir) if RE_SECTION_FILE.match(n))
    if not names:
        raise ParseError("book/ 下没有找到 NN-xxx.md 形式的正文文件")

    sections, entries = [], []
    for name in names:
        num = int(name[:2])
        md = RE_BACK_LINK.sub("", read_text(root, "book/" + name))
        h1 = RE_H1.search(md)
        if not h1:
            raise ParseError("第 %s 节找不到一级标题：%s" % (num, name))
        title = h1.group(2).strip()
        body = md[h1.end():]

        heads = list(RE_ENTRY.finditer(body))
        if not heads:
            raise ParseError("第 %s 节里没有条目标题（### N. …）：%s" % (num, name))

        sec_entries = []
        for i, h in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
            block = body[h.end():end]
            e_num = int(h.group(1))
            fields = _parse_fields(block)
            missing = [k for k in ("成本", "收益", "证据等级", "来源") if k not in fields]
            if missing:
                raise ParseError("第 %d 节第 %d 条缺字段：%s" % (num, e_num, "、".join(missing)))
            e = {
                "sec": num,
                "num": e_num,
                "title": h.group(2).strip(),
                "tags": _parse_tags(block),
                "fields": fields,
            }
            sec_entries.append(e)
            entries.append(e)

        sections.append({
            "num": num,
            "title": title,
            "file": name,
            "question": questions.get(num, ("", ""))[1],
            "nav_label": questions.get(num, (title, ""))[0],
            "intro": body[:heads[0].start()].strip(),
            "entries": sec_entries,
        })

    _attach_xrefs(sections)
    return {"sections": sections, "entries": entries}


def _attach_xrefs(sections):
    """把「见第 X 节第 Y 条」解析成结构化引用，并标出指向不存在的条目。"""
    known = {(s["num"], e["num"]) for s in sections for e in s["entries"]}
    for s in sections:
        for e in s["entries"]:
            blob = "\n".join(e["fields"].get(k, "") for k in FIELDS)
            refs = [(int(a), int(b)) for a, b in RE_XREF_FAR.findall(blob)]
            refs += [(s["num"], int(b)) for b in RE_XREF_NEAR.findall(blob)]
            e["xrefs"] = sorted(set(refs))
            e["xrefs_missing"] = sorted({r for r in e["xrefs"] if r not in known})


def stats(book):
    entries = book["entries"]
    by = lambda key, src: {v: sum(1 for e in entries if src(e) == v) for v in sorted({src(e) for e in entries})}
    refs = [r for e in entries for r in e["xrefs"]]
    return {
        "sections": len(book["sections"]),
        "entries": len(entries),
        "evidence": by("证据等级", lambda e: e["fields"].get("证据等级", "?")),
        "benefit": by("收益", lambda e: e["tags"].get("收益", "?")),
        "cost_money": by("钱", lambda e: e["tags"].get("钱", "?")),
        "cost_time": by("时间", lambda e: e["tags"].get("时间", "?")),
        "cost_will": by("毅力", lambda e: e["tags"].get("毅力", "?")),
        "caliber": by("口径", lambda e: e["tags"].get("口径", "?")),
        "xrefs": len(refs),
        "xrefs_missing": sum(len(e["xrefs_missing"]) for e in entries),
    }


# ------------------------------------------------------------------ 渲染辅助

def inline(text, sec, entry_titles):
    """把正文里的 <url>、[文字](链接)、「见第 X 节第 Y 条」变成真 HTML 链接。

    entry_titles: {(节, 条): 标题}，用来给互相指路加 title 提示。
    """
    s = html.escape(text, quote=False)
    s = re.sub(r"&lt;(https?://[^&\s]+?)&gt;",
               r'<a href="\1" target="_blank" rel="noopener nofollow">\1</a>', s)

    def far(m):
        s_num, e_num = int(m.group(1)), int(m.group(2))
        title = entry_titles.get((s_num, e_num))
        href = ("../%02d/%02d.html" % (s_num, e_num)) if s_num != sec else ("%02d.html" % e_num)
        tip = ' title="%s"' % html.escape(title) if title else ""
        return '<a class="xref" href="%s"%s>%s</a>' % (href, tip, m.group(0))

    def near(m):
        e_num = int(m.group(1))
        title = entry_titles.get((sec, e_num))
        tip = ' title="%s"' % html.escape(title) if title else ""
        return '<a class="xref" href="#e%d"%s>%s</a>' % (e_num, tip, m.group(0))

    # 顺序要紧：先处理「本节」，再处理跨节；m.group(0) 已经是转义过的文本，不能再转义一次
    s = RE_XREF_NEAR.sub(near, s)
    s = RE_XREF_FAR.sub(far, s)
    s = re.sub(r"\[([^\]]{1,40})\]\((https?://[^)\s]+)\)",
               r'<a href="\2" target="_blank" rel="noopener nofollow">\1</a>', s)
    return s


def split_paras(text):
    """把字段文本切成段落：上游字段多是单行，少数用空行分段。"""
    if not text:
        return []
    return [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]


def parse_docs(root):
    """解析上游 docs/ 的「场景长文」：H1 标题、H2 时间段、每段正文（编号列表 + 段落）。

    不新增任何内容，只把已有的条目按时间重排并保留其「见第 X 节第 Y 条」的指路，
    渲染时再把那些指路变成真链接。
    """
    out = []
    docs_dir = os.path.join(str(root), "docs")
    if not os.path.isdir(docs_dir):
        return out
    for name in sorted(os.listdir(docs_dir)):
        base = name[:-3]
        if not name.endswith(".md") or base not in SCENE_SLUGS:
            continue
        md = RE_BACK_LINK.sub("", read_text(root, "docs/" + name))
        h1 = re.search(r"^#\s+(.+)$", md, re.M)
        title = h1.group(1).strip() if h1 else base
        body = md[h1.end():] if h1 else md
        heads = list(RE_H2.finditer(body))
        sections = []
        for i, h in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
            raw = body[h.end():end].strip()
            steps, tail = [], []
            for line in raw.split("\n"):
                line = line.strip()
                if not line:
                    continue
                m = re.match(r"^\d+\.\s+(.*)$", line)
                if m:
                    steps.append(m.group(1))
                elif steps:
                    steps[-1] += " " + line      # 续行并进上一条
                else:
                    tail.append(line)
            sections.append({"heading": h.group(1).strip(), "steps": steps, "paras": tail})
        intro = body[:heads[0].start()].strip() if heads else body.strip()
        out.append({"key": base, "slug": SCENE_SLUGS[base], "title": title, "intro": intro,
                    "file": "docs/" + name, "sections": sections})
    order = {k: i for i, k in enumerate(SCENE_SLUGS)}
    out.sort(key=lambda x: order.get(x["key"], 99))
    return out


def entry_titles(book):
    return {(s["num"], e["num"]): e["title"] for s in book["sections"] for e in s["entries"]}
