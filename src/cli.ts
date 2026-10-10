#!/usr/bin/env node
// 入口：stdio 传输，给 npx / 任何 MCP 客户端用。
// 保持 stdout 干净（日志一律走 stderr），否则会污染 JSON-RPC 流。

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { loadBook } from "./data.js";
import { buildServer, SERVER_NAME, SERVER_VERSION } from "./server.js";

async function main(): Promise<void> {
  if (process.argv.includes("--version")) {
    process.stdout.write(`${SERVER_NAME} ${SERVER_VERSION}\n`);
    return;
  }

  const server = buildServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);

  // 只写 stderr，绝不写 stdout
  process.stderr.write(
    `${SERVER_NAME} ${SERVER_VERSION} 已就绪（${loadBook().entries.length} 条 · 正文 CC BY 4.0 转载自 eternity4719/HowToLiveBetter，非官方）\n`,
  );
}

main().catch((err: unknown) => {
  process.stderr.write(`启动失败：${err instanceof Error ? err.message : String(err)}\n`);
  process.exit(1);
});
