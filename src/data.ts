// 数据加载：data/book.json 是 tools/build_mcp_data.py 生成的唯一数据源。
// 路径按模块位置解析（dist/ 与 data/ 在包里是兄弟目录），也可以用 HLTB_DATA 覆盖，方便测试。

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export interface EntryTags {
  钱?: string;
  时间?: string;
  毅力?: string;
  收益?: string;
  口径?: string;
}

export interface EntryFields {
  成本?: string;
  说人话?: string;
  收益?: string;
  证据等级?: string;
  来源?: string;
  备注?: string;
}

export interface Entry {
  s: number; // 节号
  n: number; // 条号
  t: string; // 标题
  g: EntryTags;
  lv: string; // 归一化后的证据等级 A/B/C
  lvNote: string; // 原文写法（可能是「A（争议）」）
  cost: number; // 成本档 0..6（照抄上游权重）
  ratio: string; // 性价比档 极高/高/一般
  f: EntryFields; // 六个字段的原文
  x: [number, number][]; // 「见第 X 节第 Y 条」的引用
}

export interface Section {
  n: number;
  t: string;
  q: string; // 这一节回答什么问题
  count: number;
}

export interface Source {
  repo: string;
  author: string;
  title: string;
  license: string;
  license_url: string;
  commit: string;
  commit_short: string;
  commit_date: string;
  synced_at: string;
  note: string;
  site_base: string;
  unofficial: boolean;
}

export interface Book {
  source: Source;
  stats: Record<string, unknown>;
  sections: Section[];
  entries: Entry[];
}

export function dataPath(): string {
  if (process.env.HLTB_DATA) return process.env.HLTB_DATA;
  const here = dirname(fileURLToPath(import.meta.url));
  return join(here, "..", "data", "book.json");
}

export function loadBook(path = dataPath()): Book {
  let raw: string;
  try {
    raw = readFileSync(path, "utf-8");
  } catch (err) {
    throw new Error(
      `读不到数据文件 ${path}（跑一次 tools/build_mcp_data.py 生成它，或用 HLTB_DATA 指定路径）`,
    );
  }
  const book = JSON.parse(raw) as Book;
  if (!Array.isArray(book.entries) || book.entries.length < 600) {
    throw new Error(`数据文件异常：条目数 ${book.entries?.length}（expected >= 600）`);
  }
  return book;
}

// 节号/条号 -> 标题，给互相指路用
export function titleIndex(book: Book): Map<string, string> {
  const m = new Map<string, string>();
  for (const e of book.entries) m.set(`${e.s}-${e.n}`, e.t);
  return m;
}
