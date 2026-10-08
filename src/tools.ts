// 四个工具的实现。硬约束：只检索、不生成 —— 返回的每个字都来自正文，
// 不解释、不换算、不补数字；查不到就返回"书里没写"。

import type { Book, Entry, Section } from "./data.js";
import { titleIndex } from "./data.js";
import { credit, disclaimer, renderFull, renderHit, renderSections, urgentHint } from "./format.js";

export const LIMIT_DEFAULT = 8;
export const LIMIT_MAX = 25;

export interface SearchParams {
  query?: string;
  evidence?: string[];
  money?: string[];
  time?: string[];
  will?: string[];
  benefit?: string[];
  caliber?: string[];
  ratio?: string[];
  section?: number;
  limit?: number;
}

function bigrams(s: string): string[] {
  const t = s.replace(/\s+/g, "").toLowerCase();
  if (t.length <= 1) return t ? [t] : [];
  const set = new Set<string>();
  for (let i = 0; i + 1 < t.length; i++) set.add(t.slice(i, i + 2));
  return [...set];
}

/** 字面匹配打分：整串命中优先，否则要求"查询里的大部分二字切片都出现"。
 *
 * 只按二字切片算分太松（"如何用机器学习预测股票" 会因为"学习"二字命中一堆条目），
 * 所以要卡覆盖率：非整串命中时，至少一半的切片要在这一条里出现才算命中 ——
 * 宁可返回"书里没有写"，也不要把不相关的条目推给模型。
 */
function scoreEntry(e: Entry, q: string, grams: string[]): number {
  const title = e.t.toLowerCase();
  const human = (e.f.说人话 ?? "").toLowerCase();
  const body = [e.f.成本, e.f.收益, e.f.备注, e.f.来源, e.lvNote].join(" ").toLowerCase();
  const all = `${title} ${human} ${body}`;

  let present = 0;
  for (const g of grams) if (all.includes(g)) present++;
  const coverage = grams.length ? present / grams.length : 0;

  const inTitle = title.includes(q);
  const inHuman = human.includes(q);
  const inBody = body.includes(q);
  const exact = inTitle || inHuman || inBody;

  if (!exact && coverage < 0.5) return 0;

  let sc = coverage * 40;
  if (inTitle) sc += 30;
  else if (inHuman) sc += 18;
  else if (inBody) sc += 10;
  for (const g of grams) if (title.includes(g)) sc += 1;
  return sc;
}

const has = (v: string | undefined, want: string[] | undefined): boolean =>
  !want || want.length === 0 || (v !== undefined && want.includes(v));

export function search(book: Book, p: SearchParams): { hits: Entry[]; matched: number; limit: number } {
  const limit = Math.min(Math.max(1, p.limit ?? LIMIT_DEFAULT), LIMIT_MAX);
  let pool = book.entries.filter(
    (e) =>
      (!p.section || e.s === p.section) &&
      has(e.lv, p.evidence) &&
      has(e.g.钱, p.money) &&
      has(e.g.时间, p.time) &&
      has(e.g.毅力, p.will) &&
      has(e.g.收益, p.benefit) &&
      has(e.g.口径, p.caliber) &&
      has(e.ratio, p.ratio),
  );

  const q = (p.query ?? "").replace(/\s+/g, "").toLowerCase();
  if (q) {
    const grams = bigrams(q);
    const scored = pool
      .map((e) => ({ e, sc: scoreEntry(e, q, grams) }))
      .filter((x) => x.sc > 0)
      .sort((a, b) => b.sc - a.sc || a.e.s - b.e.s || a.e.n - b.e.n);
    return { hits: scored.slice(0, limit).map((x) => x.e), matched: scored.length, limit };
  }
  // 无关键词：按书的顺序（每节内本来就是按性价比排的）
  return { hits: pool.slice(0, limit), matched: pool.length, limit };
}

export function getEntry(book: Book, section: number, num: number): Entry | undefined {
  return book.entries.find((e) => e.s === section && e.n === num);
}

export function listSections(book: Book, section?: number): Section[] {
  return section ? book.sections.filter((s) => s.n === section) : book.sections;
}

/** 每日一条：同一天多次调用结果一致（按日期稳定取模，不做随机）。 */
export function daily(book: Book, date?: string): Entry {
  const day = date ?? new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Shanghai" });
  let h = 2166136261;
  for (const ch of day) {
    h ^= ch.codePointAt(0) ?? 0;
    h = Math.imul(h, 16777619);
  }
  const idx = Math.abs(h) % book.entries.length;
  return book.entries[idx] as Entry;
}

// ------------------------------------------------------------------ 文本输出

export function searchText(book: Book, p: SearchParams): string {
  const { hits, matched, limit } = search(book, p);
  const head = credit(book);
  const filterNote = describeFilters(p);

  if (hits.length === 0) {
    const near = nearestSections(book, p.query ?? "");
    return [
      head,
      "",
      `书里没有写这件事${p.query ? `（关键词：${p.query}）` : ""}${filterNote}。`,
      "可以换个说法、或放宽筛选条件。下面几节可能最接近：",
      renderSections(book, near),
      "",
      "不要凭印象替这本书回答；确实没有就告诉用户书里没写。",
    ].join("\n");
  }

  const body = hits.map((e) => renderHit(book, e)).join("\n\n");
  const more =
    matched > hits.length ? `\n\n（命中 ${matched} 条，这里给最相关的 ${hits.length} 条；要看更多请加 limit 或收紧条件）` : "";
  const urgent = urgentHint(hits[0]?.s ?? 0, `${p.query ?? ""} ${hits.map((h) => h.t).join(" ")}`);
  return [
    head,
    "",
    urgent ? `${urgent}\n` : "",
    body,
    more,
    "",
    disclaimer(),
  ]
    .filter((x) => x !== "")
    .join("\n");
}

export function getEntryText(book: Book, section: number, num: number): string {
  const e = getEntry(book, section, num);
  if (!e) {
    const sec = book.sections.find((s) => s.n === section);
    return [
      credit(book),
      "",
      `第 ${section} 节${sec ? `「${sec.t}」` : ""}里没有第 ${num} 条${sec ? `（这一节共 ${sec.count} 条）` : "（书里没有这一节）"}。`,
      "",
      renderSections(book, sec ? [sec] : undefined),
    ].join("\n");
  }
  const urgent = urgentHint(e.s, `${e.t} ${e.f.说人话 ?? ""}`);
  return [
    credit(book),
    "",
    urgent ? `${urgent}\n` : "",
    renderFull(book, e, titleIndex(book)),
    "",
    disclaimer(),
  ]
    .filter((x) => x !== "")
    .join("\n");
}

export function sectionsText(book: Book, section?: number): string {
  const list = listSections(book, section);
  if (list.length === 0) {
    return [credit(book), "", `书里没有第 ${section} 节（共 ${book.sections.length} 节）。`].join("\n");
  }
  const total = list.reduce((n, s) => n + s.count, 0);
  return [
    credit(book),
    "",
    section ? `第 ${section} 节，共 ${total} 条：` : `全书 ${book.sections.length} 节 ${total} 条：`,
    renderSections(book, list),
    "",
    "想拿某一条的全文，用 get_entry（节号 + 条号）。",
  ].join("\n");
}

export function dailyText(book: Book, date?: string): string {
  const e = daily(book, date);
  return [
    credit(book),
    "",
    `今天这一条（按日期稳定取，同一天同一条）：`,
    "",
    renderFull(book, e, titleIndex(book)),
    "",
    disclaimer(),
  ].join("\n");
}

function describeFilters(p: SearchParams): string {
  const bits: string[] = [];
  if (p.evidence?.length) bits.push(`证据 ${p.evidence.join("/")}`);
  if (p.money?.length) bits.push(`钱 ${p.money.join("/")}`);
  if (p.time?.length) bits.push(`时间 ${p.time.join("/")}`);
  if (p.will?.length) bits.push(`毅力 ${p.will.join("/")}`);
  if (p.benefit?.length) bits.push(`收益 ${p.benefit.join("/")}`);
  if (p.caliber?.length) bits.push(`口径 ${p.caliber.join("/")}`);
  if (p.ratio?.length) bits.push(`性价比 ${p.ratio.join("/")}`);
  if (p.section) bits.push(`第 ${p.section} 节`);
  return bits.length ? `（筛选：${bits.join("，")}）` : "";
}

/** 兜底建议：按关键词粗略找最接近的几节，不假装知道用户在问什么。 */
function nearestSections(book: Book, query: string): Section[] {
  const q = query.replace(/\s+/g, "");
  if (!q) return book.sections.slice(0, 5);
  const grams = bigrams(q);
  const scored = book.sections
    .map((s) => {
      const text = `${s.t}${s.q}`.toLowerCase();
      let sc = text.includes(q.toLowerCase()) ? 10 : 0;
      for (const g of grams) if (text.includes(g)) sc += 2;
      for (const e of book.entries) {
        if (e.s !== s.n) continue;
        if (e.t.toLowerCase().includes(q.toLowerCase())) sc += 1;
      }
      return { s, sc };
    })
    .filter((x) => x.sc > 0)
    .sort((a, b) => b.sc - a.sc);
  return (scored.length ? scored.map((x) => x.s) : book.sections).slice(0, 5);
}
