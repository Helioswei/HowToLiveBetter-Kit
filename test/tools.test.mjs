// 单元测试：数据、归一化、四个工具的文本输出。跑的是 dist/（先 npm run build）。
import assert from "node:assert/strict";
import { test } from "node:test";

import { loadBook, titleIndex } from "../dist/data.js";
import { daily, getEntryText, search, searchText, sectionsText } from "../dist/tools.js";
import { credit } from "../dist/format.js";

const book = loadBook();

test("数据完整：672 条 / 34 节", () => {
  assert.equal(book.entries.length, 672);
  assert.equal(book.sections.length, 34);
  // 每条的六个字段里至少要有 成本/收益/证据等级/来源
  for (const e of book.entries) {
    for (const k of ["成本", "收益", "证据等级", "来源"]) {
      assert.ok(e.f[k] && e.f[k].length > 0, `第 ${e.s} 节第 ${e.n} 条缺 ${k}`);
    }
  }
});

test("证据等级已归一化，原文写在 lvNote", () => {
  const bad = book.entries.filter((e) => !["A", "B", "C"].includes(e.lv));
  assert.equal(bad.length, 0, `有 ${bad.length} 条的等级不是 A/B/C`);
  const withNote = book.entries.filter((e) => e.lvNote !== e.lv);
  assert.equal(withNote.length, 5, "带附注的等级应为 5 条（A（争议）3 + B（…低）1 + C（争议）1）");
  for (const e of withNote) assert.ok(e.lvNote.startsWith(e.lv));
});

test("成本权重按上游算法：「少」在时间上是 0、在钱上是 1", () => {
  const zero = book.entries.filter((e) => e.cost === 0);
  assert.equal(zero.length, 239, "三项成本全零应为 239 条");
  for (const e of zero) {
    assert.equal(e.g.钱, "0");
    assert.equal(e.g.时间, "少");
    assert.equal(e.g.毅力, "否");
  }
  const top = book.entries.filter((e) => e.ratio === "极高");
  assert.equal(top.length, 114, "性价比「极高」= 三项成本全零 + 收益大，应为 114 条");
});

test("search：关键词能命中，返回带出处", () => {
  const { hits } = search(book, { query: "低钠盐" });
  assert.ok(hits.length > 0);
  assert.ok(hits[0].t.includes("低钠盐"));
  const text = searchText(book, { query: "低钠盐" });
  assert.match(text, /第 \d+ 节第 \d+ 条/);
  assert.match(text, /说人话/);
});

test("search：筛选条件能算出书里说的「极高」清单", () => {
  const { matched } = search(book, { money: ["0"], time: ["少"], will: ["否"], benefit: ["大"], limit: 25 });
  assert.equal(matched, 114);
});

test("search：查不到就明确说书里没写，并给最接近的节", () => {
  const text = searchText(book, { query: "如何用机器学习预测股票" });
  assert.match(text, /书里没有写这件事/);
  assert.match(text, /不要凭印象替这本书回答/);
  assert.match(text, /\d\d\. /); // 兜底给了节
});

test("search：急症关键词会先提示去看第 13 节", () => {
  const text = searchText(book, { query: "溺水" });
  assert.match(text, /紧急情况/);
});

test("get_entry：给全文六字段 + 署名 + 免责", () => {
  const text = getEntryText(book, 34, 1);
  assert.match(text, /【第 34 节第 1 条】/);
  for (const k of ["成本：", "说人话：", "收益：", "证据等级：", "来源：", "备注："]) {
    assert.ok(text.includes(k), `缺字段 ${k}`);
  }
  assert.match(text, /CC BY 4\.0/);
  assert.match(text, /非官方/);
  assert.match(text, /不构成诊疗意见/);
});

test("get_entry：互相指路带上别节的标题", () => {
  const withRef = book.entries.find((e) => e.x.length > 0);
  assert.ok(withRef, "应该有带互相指路的条目");
  const text = getEntryText(book, withRef.s, withRef.n);
  assert.match(text, /这一条还指向：/);
  const [s, n] = withRef.x[0];
  assert.ok(text.includes(`第 ${s} 节第 ${n} 条`), "指路要写清指向哪一条");
  const titles = titleIndex(book);
  assert.equal(titles.size, 672);
});

test("get_entry：越界时说实话，不编", () => {
  assert.match(getEntryText(book, 8, 999), /没有第 999 条/);
  assert.match(getEntryText(book, 99, 1), /书里没有这一节/);
});

test("list_sections：目录带条数与节点问题", () => {
  const all = sectionsText(book);
  assert.match(all, /34 节 672 条/);
  const one = sectionsText(book, 13);
  assert.match(one, /第 13 节/);
  assert.match(one, /紧急情况/);
});

test("daily：同一天结果稳定", () => {
  const a = daily(book, "2026-10-09");
  const b = daily(book, "2026-10-09");
  assert.equal(a.s * 1000 + a.n, b.s * 1000 + b.n);
});

test("署名行含作者、许可、原始仓库、同步版本", () => {
  const c = credit(book);
  for (const needle of ["eternity4719", "CC BY 4.0", "creativecommons.org/licenses/by/4.0", "github.com/eternity4719/HowToLiveBetter", book.source.commit_short]) {
    assert.ok(c.includes(needle), `署名缺 ${needle}`);
  }
});

test("单条链接指向镜像站", () => {
  const text = getEntryText(book, 1, 1);
  assert.match(text, new RegExp(`${book.source.site_base}/01/01\\.html`));
});
