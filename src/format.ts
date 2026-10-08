// 输出格式：每个响应都必须带署名（CC BY 4.0 第 3(a)(1) 条的要求，也是许可规定不是客气）。

import type { Book, Entry, Section } from "./data.js";

/** 署名头：作者、作品、许可、原始链接、是否改动、同步版本 —— 一条都不能少。 */
export function credit(b: Book): string {
  const s = b.source;
  return [
    `${s.title} · 作者 ${s.author} · ${s.license} · 非官方转载（正文未改动，只做了结构化与排版处理）`,
    `许可 ${s.license_url} ｜ 原始仓库 ${s.repo}`,
    `同步自上游 ${s.commit_short}（${s.commit_date.slice(0, 10)}）｜ 共 ${b.entries.length} 条 / ${b.sections.length} 节`,
  ].join("\n");
}

/** 免责尾：医学/法律内容不构成专业意见。 */
export function disclaimer(): string {
  return [
    "以上均为《高性价比人生指南》原文字段，未作解释或改写。",
    "医学内容不构成诊疗意见，法律内容不构成法律意见；个案请咨询执业医师或律师。",
  ].join("\n");
}

export function entryUrl(b: Book, e: Entry): string | undefined {
  const base = b.source.site_base;
  if (!base) return undefined;
  return `${base}/${String(e.s).padStart(2, "0")}/${String(e.n).padStart(2, "0")}.html`;
}

export function originUrl(b: Book, e: Entry): string {
  return `${b.source.repo}/blob/main/book/`;
}

export function tagsLine(e: Entry): string {
  const g = e.g;
  const parts = [
    `性价比 ${e.ratio}`,
    `收益 ${g.收益 ?? "?"}`,
    `证据 ${e.lvNote || e.lv} 级`,
    `口径 ${g.口径 ?? "?"}`,
    `成本 钱${g.钱 ?? "?"}/时间${g.时间 ?? "?"}/毅力${g.毅力 ?? "?"}`,
  ];
  return parts.join(" · ");
}

/** 一条的紧凑写法（列表里用） */
export function renderHit(b: Book, e: Entry): string {
  const lines = [`【第 ${e.s} 节第 ${e.n} 条】${e.t}`, `  ${tagsLine(e)}`];
  if (e.f.说人话) lines.push(`  说人话：${e.f.说人话}`);
  const url = entryUrl(b, e);
  if (url) lines.push(`  看全文：${url}`);
  return lines.join("\n");
}

/** 一条的完整写法（get_entry 用，六个字段全给，字段名沿用原文） */
export function renderFull(b: Book, e: Entry, titles: Map<string, string>): string {
  const out = [`【第 ${e.s} 节第 ${e.n} 条】${e.t}`, tagsLine(e), ""];
  for (const k of ["成本", "说人话", "收益", "证据等级", "来源", "备注"] as const) {
    const v = e.f[k];
    if (v) out.push(`${k}：${v}`);
  }
  if (e.x.length) {
    const refs = e.x.map(([s, n]) => `第 ${s} 节第 ${n} 条${titles.has(`${s}-${n}`) ? `（${titles.get(`${s}-${n}`)}）` : ""}`);
    out.push("", `这一条还指向：${refs.join("；")}`);
  }
  const url = entryUrl(b, e);
  if (url) out.push("", `全文页面：${url}`);
  out.push(`原始出处：${b.source.repo}`);
  return out.join("\n");
}

export function renderSections(b: Book, only?: Section[]): string {
  const list = only ?? b.sections;
  return list
    .map((s) => `${String(s.n).padStart(2, "0")}. ${s.t}（${s.count} 条）—— ${s.q}`)
    .join("\n");
}

/** 立刻要停下的事：只指路，不自己生成医嘱。 */
export function urgentHint(sectionNo: number, text: string): string | undefined {
  const legal = [8, 9, 11, 19];
  const emergency = /急|急救|大出血|溺水|触电|中毒|起火|火灾|没呼吸|昏迷|自杀|轻生/.test(text);
  if (sectionNo === 13 || emergency) {
    return "⚠️ 如果这是正在发生的紧急情况：先看第 13 节（紧急情况：先做什么），不要先读建议。";
  }
  if (legal.includes(sectionNo) || /法律|犯法|官司|拘留|起诉|报案|劳动仲裁/.test(text)) {
    return "书里给的是通用口径，个案请找执业律师；涉及程序的事见第 8 节。";
  }
  return undefined;
}
