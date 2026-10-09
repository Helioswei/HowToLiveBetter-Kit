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
from urllib.parse import quote

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
# 指向上游文件本身的相对链接，如 [docs/生物钟和夜班.md](../docs/生物钟和夜班.md)
RE_MD_LINK = re.compile(r"\[([^\]]{1,60})\]\(([^)\s]{1,120})\)")

# 上游正文里会互相指路（"见 docs/生物钟和夜班.md"）。这些文档我们自己也有页面，
# 所以由站点生成器登记一张映射表，inline() 把这种链接指回**我们自己的那一页**
# （指到 GitHub 读者在墙内根本打不开）。没登记的（如 docs/核实记录/…）才退回升 GitHub。
_DOCMAP = {}


def set_docmap(mapping):
    """登记 {上游文档名: 我们页面的相对 URL}。build_site 启动时调一次。"""
    global _DOCMAP
    _DOCMAP = dict(mapping or {})
# 同节条号：书里写作「（第 N 条）」，节首导览里就是它的目录写法
RE_SAME_REF = re.compile(r"（第\s*(\d+)\s*条）")
# 上游每节开头的返回链接，我们自己的壳负责导航
RE_BACK_LINK = re.compile(r"^\[← 回总目录\]\([^)]*\)\s*\n")
RE_H2 = re.compile(r"^##\s+(.+)$", re.M)

# 上游 docs/ 下"按时间排的场景长文"：H2 就是时间段（当天 / 头一周 / 头一个月…）。
# 收哪几篇由 scene_doc_files() 按**结构**判定（不看名单），这里只定**展示顺序**。改前几条时
# 顺手把这里当白名单用过 —— 现在不是白名单了，加了新文件它自己会进来，不在名单里的排在后面。
#
# 场景页的文件名 = **上游 docs/ 里的文件名**（中文）→ URL 就是 /scenes/被裁了之后先做什么.html
# （链接/canonical/sitemap 里一律百分号编码）。
#
# 为什么不再手工起英文名：上游以后新写同类长文要能**自动上站**，而起名这件事没法自动。
# 2026-10-09 把最开始那 4 篇从英文 slug（laid-off / having-a-baby / new-diagnosis /
# job-and-city-change）统一成中文：当时站点上线才一天、sitemap 没提交过、仓库与公众号
# 都没有引用过它们，换 URL 的代价是 0；再晚就得长期维护"新旧两套风格"。
# ⚠️ 以后若真要重命名某个文件，等于换 URL，得先想清楚已收录/已分享的链接。
SCENE_ORDER = (
    "被裁了之后先做什么",
    "孩子出生前后要办的事",
    "刚确诊慢性病之后",
    "换工作、换城市之前",
)

# 「按场景看」收不收一篇，不看人写的名单，看它的**结构**：
#   有 ≥2 个 H2 时间段 + ≥20 处「见第 X 节第 Y 条」指路 + 没有任何 bullet + 篇幅不巨大。
# 实测这条规则正好选中上面那 4 篇（30~64 处指路、0 bullet），不多不少；
# 而《引用对照》（11 万字引用表）、《家庭应急装备清单》《结婚划不划算》（清单/长文，有 bullet）、
# 《生物钟和夜班》《做平台要办哪些证》（0 指路）都会被排除 —— 它们不是时间轴。
# 所以上游以后新写一篇同类长文，不用改代码就会自动上站。
SCENE_MIN_SECTIONS = 2
SCENE_MIN_REFS = 20
SCENE_MAX_CHARS = 30000

# docs/ 里还有一类**长文/清单型**（有 H2 分组、正文是段落 + bullet + 表格，不是按时间排的步骤）：
# 家庭应急装备清单、结婚划不划算、做平台要办哪些证、生物钟和夜班、遇到陌生人出事该不该停。
# 它们上站的价值一样（都是上游正文、都该能被搜到），只是版式不同 → 用「长文页」渲染。
# 太长的（如 11.4 万字的《引用对照》，它是"条目→出处"的核对表）这轮不上：单页过大，
# 而且它是核对记录，不是给读者读的长文。以后想上就单独做"引用总表"页。
LONGFORM_MAX_CHARS = 20000


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

def inline(text, sec, entry_titles, on_section=True):
    """把正文里的 <url>、[文字](链接)、**加粗**、「见第 X 节第 Y 条」、「（第 N 条）」变成真 HTML。

    entry_titles: {(节, 条): 标题}，用来给互相指路加 title 提示。
    on_section: 当前页是不是节页。同节条号在节页上指向本页锚点（#eN），
                在条目页上要指回节页（index.html#eN），否则点了没反应。
    """
    s = html.escape(text, quote=False)
    s = re.sub(r"&lt;(https?://[^&\s]+?)&gt;",
               r'<a href="\1" target="_blank" rel="noopener nofollow">\1</a>', s)

    # 书里的 markdown 加粗（92 处）。三个细节：转义星号（HLA-B\*5801）、跨段落的加粗、
    # 以及源里偶尔落单的 ** —— 都不能留在页面上当字面星号。
    s = s.replace("\\*", "*")
    s = re.sub(r"\*\*(.{1,400}?)\*\*", r"<strong>\1</strong>", s, flags=re.S)
    s = s.replace("**", "")

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

    def same(m):
        """同节条号，书里写作「（第 N 条）」—— 节首导览里就是它的目录写法，共 421 处。
        目标条目确实存在时才变成链接，否则原样留着（不去猜）。"""
        e_num = int(m.group(1))
        title = entry_titles.get((sec, e_num)) if sec else None
        if not title:
            return m.group(0)
        href = ("#e%d" % e_num) if on_section else ("index.html#e%d" % e_num)
        return '<a class="b-ref" href="%s" title="%s">%s</a>' % (href, html.escape(title), m.group(0))

    # 顺序要紧：先处理「本节」，再处理跨节；m.group(0) 已经是转义过的文本，不能再转义一次
    s = RE_XREF_NEAR.sub(near, s)
    s = RE_XREF_FAR.sub(far, s)
    s = RE_SAME_REF.sub(same, s)

    def mdlink(m):
        """[文字](目标)：http 的照旧；相对路径的优先指回我们自己的那一页，否则指上游原文。
        （上游正文里大量引用同书的其它长文，这些链接以前会以原始 markdown 形式漏在页面上。）
        注意 text 取自已经 html.escape 过的串，别再转义一次。"""
        text, target = m.group(1), m.group(2)
        if target.startswith(("http://", "https://")):
            return '<a href="%s" target="_blank" rel="noopener nofollow">%s</a>' % (target, text)
        name = re.sub(r"^(\.\./)*docs/", "", target).replace(".md", "")
        if name in _DOCMAP:
            return '<a href="%s">%s</a>' % (_DOCMAP[name], text)
        return ('<a href="%s/blob/main/docs/%s" target="_blank" rel="noopener nofollow">%s</a>'
                % (REPO, target, text))

    return RE_MD_LINK.sub(mdlink, s)


def split_paras(text):
    """把字段文本切成段落：上游字段多是单行，少数用空行分段。"""
    if not text:
        return []
    return [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]


def scene_doc_files(root):
    """扫 docs/*.md，按结构挑出「时间轴长文」→ [(文件名, key, slug, url)]。

    新文章自动收录：文件名 = 上游文件名（中文），URL 走百分号编码。收哪几篇由结构决定，
    顺序由 SCENE_ORDER 决定（不在名单里的按文件名排在后面）。
    """
    docs_dir = os.path.join(str(root), "docs")
    out = []
    if not os.path.isdir(docs_dir):
        return out
    for name in sorted(os.listdir(docs_dir)):
        if not name.endswith(".md"):
            continue
        base = name[:-3]
        text = read_text(root, "docs/" + name)
        if len(text) > SCENE_MAX_CHARS:
            continue
        if len(RE_H2.findall(text)) < SCENE_MIN_SECTIONS:
            continue
        if re.search(r"(?m)^\s*[-*]\s+\S", text):  # 有 bullet = 清单或长文，不是按时间排的场景
            continue
        refs = len(RE_XREF_FAR.findall(text)) + len(RE_XREF_NEAR.findall(text))
        if refs < SCENE_MIN_REFS:
            continue
        slug = base  # 文件名 = 上游文件名（中文），URL 编码后使用
        out.append((name, base, slug, quote(slug)))
    order = {k: i for i, k in enumerate(SCENE_ORDER)}
    out.sort(key=lambda x: order.get(x[1], 99))
    return out


def longform_files(root):
    """docs/ 下的「长文页」：不是时间轴型、篇幅也没大到不适合单页的那些 → [(文件名, key, url)]。

    判定与 scene_doc_files 互补：能被时间轴判据收走的就不在这里，
    所以两边的名单永远不重叠（加一篇上游长文时，只会落到其中一边）。
    """
    docs_dir = os.path.join(str(root), "docs")
    out = []
    if not os.path.isdir(docs_dir):
        return out
    timeline = {base for _n, base, _s, _u in scene_doc_files(root)}
    for name in sorted(os.listdir(docs_dir)):
        if not name.endswith(".md"):
            continue
        base = name[:-3]
        if base in timeline:
            continue
        text = read_text(root, "docs/" + name)
        if len(text) > LONGFORM_MAX_CHARS or len(text) < 200:
            continue
        out.append((name, base, quote(base)))
    return out


def parse_docs(root):
    """解析上游 docs/ 的「场景长文」：H1 标题、H2 时间段、每段正文（编号列表 + 段落）。

    不新增任何内容，只把已有的条目按时间重排并保留其「见第 X 节第 Y 条」的指路，
    渲染时再把那些指路变成真链接。收哪几篇见 scene_doc_files()（按结构判定，不看名单）。
    """
    out = []
    for name, base, slug, url in scene_doc_files(root):
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
        out.append({"key": base, "slug": slug, "url": url, "title": title, "intro": intro,
                    "file": "docs/" + name, "sections": sections})
    return out


def entry_titles(book):
    return {(s["num"], e["num"]): e["title"] for s in book["sections"] for e in s["entries"]}
