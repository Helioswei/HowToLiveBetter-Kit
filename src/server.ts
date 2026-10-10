// MCP 服务：注册四个工具。每条响应都带署名（CC BY 4.0 第 3(a)(1) 条）。
// 只检索、不生成：服务端不含任何模型调用，也不联网。

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

import { loadBook, type Book } from "./data.js";
import {
  dailyText,
  getEntryText,
  sectionsText,
  searchText,
  LIMIT_DEFAULT,
  LIMIT_MAX,
} from "./tools.js";

export const SERVER_NAME = "howtolivebetter";
export const SERVER_VERSION = "0.1.0";

const instructions = (n: number) => `《高性价比人生指南》（HowToLiveBetter）的检索工具，${n} 条按性价比排序的循证建议。

用法：先用 search 找相关条目，再把原文读给用户，并注明「第 X 节第 Y 条」。
规则（重要）：
- 只回答书里写过的东西。返回结果里的每个数字、每条款项都来自原文，不要自己补、不要换算、不要推测。
- 查不到就说书里没有写，不要用常识或记忆替它回答。
- 引用时保留条目自带的限制：收益量级、证据等级 A/B/C、口径（死亡率/金钱/时间/自由）。
- 不同口径之间不比大小（书里明确规定），不要替用户排"哪个更值"。
- 医学问题不是诊断，法律问题不是法律意见；个案让用户找医生或律师。
- 涉及正在发生的急症或法律程序，先按返回结果里的提示让用户去看对应章节。`;

/** const-string 数组参数（证据等级这类取值有限的筛选用） */
const multi = (values: readonly string[], desc: string) =>
  z.array(z.enum(values as [string, ...string[]])).optional().describe(desc);

export function buildServer(book: Book = loadBook()): McpServer {
  const server = new McpServer(
    { name: SERVER_NAME, version: SERVER_VERSION },
    { instructions: instructions(book.entries.length) },
  );

  server.registerTool(
    "search",
    {
      title: "检索建议",
      description:
        "按关键词和筛选条件找条目。返回标题、说人话、成本标签、证据等级和出处；不给全文（全文用 get_entry）。关键词是字面匹配，不是语义检索。",
      inputSchema: {
        query: z.string().optional().describe("关键词，例如「戒烟」「担保」「产假」「止血」"),
        evidence: multi(["A", "B", "C"], "证据等级，可多选"),
        money: multi(["0", "少", "多"], "花钱：0=不花钱或省钱，少=几十到几百元，多=上千元"),
        time: multi(["少", "中", "多"], "花时间：少=一次几分钟，中=数小时或每周小时级，多=每天占用"),
        will: multi(["否", "些", "是"], "要毅力：否=做一次就完，些=改一个习惯，是=长期对抗惯性"),
        benefit: multi(["大", "中", "小"], "收益量级"),
        caliber: multi(["死亡率", "金钱", "时间", "自由"], "口径：换回的是哪一类东西"),
        ratio: multi(["极高", "高", "一般"], "性价比档（照上游算法算）"),
        section: z.number().int().min(1).max(34).optional().describe("限定某一节"),
        limit: z
          .number()
          .int()
          .min(1)
          .max(LIMIT_MAX)
          .optional()
          .describe(`返回条数，默认 ${LIMIT_DEFAULT}，最多 ${LIMIT_MAX}`),
      },
    },
    async (args) => ({ content: [{ type: "text", text: searchText(book, args) }] }),
  );

  server.registerTool(
    "get_entry",
    {
      title: "取一条全文",
      description: "按节号和条号取一整条的六个字段：成本、说人话、收益、证据等级、来源、备注。",
      inputSchema: {
        section: z.number().int().min(1).max(34).describe("节号"),
        num: z.number().int().min(1).describe("条号"),
      },
    },
    async ({ section, num }) => ({ content: [{ type: "text", text: getEntryText(book, section, num) }] }),
  );

  server.registerTool(
    "list_sections",
    {
      title: "看目录",
      description: "列出 34 节的标题、节点问题与条数；带上节号时只列该节。不知道从哪查时先用它。",
      inputSchema: {
        section: z.number().int().min(1).max(34).optional().describe("只看某一节"),
      },
    },
    async ({ section }) => ({ content: [{ type: "text", text: sectionsText(book, section) }] }),
  );

  server.registerTool(
    "daily",
    {
      title: "今天这一条",
      description: "按日期稳定取一条（同一天多次调用结果一致），适合做每日提醒或随机挑一条开始。",
      inputSchema: {
        date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional().describe("YYYY-MM-DD，默认今天（北京时区）"),
      },
    },
    async ({ date }) => ({ content: [{ type: "text", text: dailyText(book, date) }] }),
  );

  return server;
}
