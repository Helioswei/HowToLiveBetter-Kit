// 端到端测试：像真客户端那样启动服务（stdio），列工具、调工具。
import assert from "node:assert/strict";
import { test } from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const here = dirname(fileURLToPath(import.meta.url));
const CLI = join(here, "..", "dist", "cli.js");

async function withClient(fn) {
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [CLI],
    env: { ...process.env },
    stderr: "pipe",
  });
  const client = new Client({ name: "hltb-test", version: "0.0.0" });
  await client.connect(transport);
  try {
    await fn(client);
  } finally {
    await client.close();
  }
}

test("MCP 端到端：列出四个工具", async () => {
  await withClient(async (client) => {
    const { tools } = await client.listTools();
    const names = tools.map((t) => t.name).sort();
    assert.deepEqual(names, ["daily", "get_entry", "list_sections", "search"]);
    for (const t of tools) assert.ok(t.description && t.description.length > 10, `${t.name} 缺说明`);
  });
});

test("MCP 端到端：search 关键词 → 原文 + 出处 + 署名", async () => {
  await withClient(async (client) => {
    const res = await client.callTool({ name: "search", arguments: { query: "担保" } });
    const text = res.content.map((c) => c.text ?? "").join("\n");
    assert.match(text, /第 \d+ 节第 \d+ 条/);
    assert.match(text, /CC BY 4\.0/);
    assert.match(text, /非官方/);
    assert.ok(!res.isError);
  });
});

test("MCP 端到端：筛选参数走通，返回「极高」清单条数", async () => {
  await withClient(async (client) => {
    const res = await client.callTool({
      name: "search",
      arguments: { money: ["0"], time: ["少"], will: ["否"], benefit: ["大"], limit: 5 },
    });
    const text = res.content.map((c) => c.text ?? "").join("\n");
    assert.match(text, /命中 114 条/);
  });
});

test("MCP 端到端：get_entry 与 daily、list_sections", async () => {
  await withClient(async (client) => {
    const one = await client.callTool({ name: "get_entry", arguments: { section: 8, num: 17 } });
    assert.match(one.content[0].text, /【第 8 节第 17 条】/);
    const day = await client.callTool({ name: "daily", arguments: { date: "2026-10-09" } });
    assert.match(day.content[0].text, /今天这一条/);
    const secs = await client.callTool({ name: "list_sections", arguments: {} });
    assert.match(secs.content[0].text, /34 节 672 条/);
  });
});

test("MCP 端到端：查不到时不会编", async () => {
  await withClient(async (client) => {
    const res = await client.callTool({ name: "search", arguments: { query: "怎么用区块链炒币稳赚" } });
    assert.match(res.content[0].text, /书里没有写这件事/);
  });
});
