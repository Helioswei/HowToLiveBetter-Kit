// MCP 服务：注册四个工具。每条响应都带署名（CC BY 4.0 第 3(a)(1) 条）。
// 只检索、不生成：服务端不含任何模型调用，也不联网。

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { readFileSync } from "node:fs";
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

// 版本号的真源只有 package.json 一处：以前这里写死 "0.1.0"，发版时得记着改两处，
// 迟早会漏（客户端显示的版本就与包里不一致）。lib/server.js 与 src/server.ts 都在
// 包的下一层，"../package.json" 在源码态和发布态都指向包根。
export const SERVER_VERSION: string = (() => {
  try {
    const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as {
      version?: unknown;
    };
    return typeof pkg.version === "string" ? pkg.version : "0.0.0";
  } catch {
    return "0.0.0";
  }
})();

// 两段文字都是为了「让模型知道什么时候该用它」：
// ① instructions —— 支持该字段的客户端会把它注入系统提示（Hermes 目前不注入，见 skill hermes-local-ops）；
//    **第一行尤其重要**：pi 这类客户端在没配 server description 时，就拿第一行当系统提示里的一行摘要，
//    所以第一行必须写「什么时候用它」，不能只写「我是什么」。
// ② 每个工具的 description 首句 —— 所有客户端都会把它喂给模型，也是 tool_search 目录里显示的正文。
const instructions = (n: number) => `《高性价比人生指南》（HowToLiveBetter）的循证建议检索：健康与就医、安全与急救、法律与维权、花钱与消费、工作与离职、租房买房、养孩子、家里老人这类生活决策问题，先用它查原文再回答。

什么时候该用（重要）：用户问的是日常生活里「该不该做、怎么做、要花多少、有没有用」这类问题时，
**先查这本再回答**，不要用自己的记忆或联网搜索替它回答。典型问题：
- 健康与就医：体检套餐要不要买、这个症状先做什么、慢病长期怎么管
- 安全与急救：着火了先做什么、有人倒地没呼吸、家里该备什么
- 法律与维权：替朋友担保签不签、借条怎么写、被欠薪怎么办、被人报案指控
- 钱与消费：攒下的钱怎么放、保险和保健品值不值、哪些是智商税
- 工作与生活：被裁能拿多少、押金被扣、租房买房、养孩子、家里老人
查之前先用 search（关键词 + 筛选条件），需要目录用 list_sections。

用法：全书 ${n} 条，把查到的原文读给用户，并注明「第 X 节第 Y 条」。
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
        "查《高性价比人生指南》里的循证建议：回答生活决策类问题（健康与就医、安全与急救、法律与维权、花钱与消费、工作与离职、租房买房、养孩子、家里老人）时先用它。问「替朋友担保签不签」「体检套餐要不要买」「被裁了能拿多少」这类问题也用它。返回标题、说人话、成本标签、证据等级和出处；不给全文（全文用 get_entry）。关键词是字面匹配，不是语义检索。",
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
      description:
        "按节号和条号取一整条的六个字段：成本、说人话、收益、证据等级、来源、备注。参数名是 section（节号）和 num（条号）—— 条号那个参数叫 num，不是 number（写错会调用失败）。search 的结果里带节号条号，要看某一条的全文（含来源与备注）时用它。",
      inputSchema: {
        section: z.number().int().min(1).max(34).describe("节号"),
        num: z.number().int().min(1).describe("条号。参数名是 num（不是 number）"),
      },
    },
    async ({ section, num }) => ({ content: [{ type: "text", text: getEntryText(book, section, num) }] }),
  );

  server.registerTool(
    "list_sections",
    {
      title: "看目录",
      description:
        "列出全书各节的标题、这一节回答的问题与条数；带上节号时只列该节。不知道用户的问题落在哪一节，或想让用户先看看这本书都写了什么时用它。",
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
      description:
        "按日期稳定取一条（同一天多次调用结果一致），适合做每日提醒，或用户想随便挑一条开始了解这本书时用它。",
      inputSchema: {
        date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional().describe("YYYY-MM-DD，默认今天（北京时区）"),
      },
    },
    async ({ date }) => ({ content: [{ type: "text", text: dailyText(book, date) }] }),
  );

  return server;
}
