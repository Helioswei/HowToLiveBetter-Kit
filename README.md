# HowToLiveBetter-Kit

把《高性价比人生指南》接给 AI 助手用：一个 **MCP 服务** + 一套**国内可访问的静态站**工具。

[![npm](https://img.shields.io/npm/v/howtolivebetter-mcp.svg)](https://www.npmjs.com/package/howtolivebetter-mcp)

近 700 条建议，34 节。装上一个 MCP 客户端，你问「替朋友担保签不签」，AI 会先去查这本书，
再把原文读给你听，并注明**出自第几节第几条**；书里没写的，它会说没写。

**非官方项目**，与原作者无关联。正文一个字未改，只做了结构化解析与排版处理。

> An unofficial MCP server + static-site toolkit for the Chinese evidence-graded life guide
> 《高性价比人生指南》 by [eternity4719](https://github.com/eternity4719/HowToLiveBetter) (CC BY 4.0).

---

## 状态

| 部分 | 状态 |
|:---|:---|
| MCP 服务（四个工具） | ✅ 可用，19 个测试全绿 |
| npm 包 [`howtolivebetter-mcp`](https://www.npmjs.com/package/howtolivebetter-mcp) | ✅ 已发布 0.1.0（npx 真装真连验过；国内镜像已同步） |
| 在线阅读版 [`better.aigcwei.cn`](https://better.aigcwei.cn/) | ✅ 已上线：710 页，含检索与「我的清单」、阅读设置（字号/行距/深色）与朗读 |
| 每日自动同步上游 | ✅ 已配（`.github/workflows/sync.yml`） |
| 站点每日自动重打包 | ✅ 已配（`.github/workflows/site.yml`） |

---

## 30 秒装上

已发布到 npm：`npx -y howtolivebetter-mcp`（国内镜像 registry.npmmirror.com 已同步，装得快）。
一行配置就够了（不需要 API key、不需要联网）：

```json
{
  "mcpServers": {
    "howtolivebetter": {
      "command": "npx",
      "args": ["-y", "howtolivebetter-mcp"]
    }
  }
}
```

放到对应位置即可：

| 客户端 | 放哪里 |
|:---|:---|
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json`（macOS） |
| Cursor | 项目里 `.cursor/mcp.json`，或全局 `~/.cursor/mcp.json` |
| Claude Code | 一条命令：`claude mcp add howtolivebetter -- npx -y howtolivebetter-mcp` |
| Cherry Studio / Cline / 其它 | 图形界面里填命令 `npx`，参数 `-y howtolivebetter-mcp` |
| Hermes Agent | `~/.hermes/config.yaml` 里加 `mcp_servers:`（见下） |

<details>
<summary>Hermes Agent 的写法</summary>

```yaml
mcp_servers:
  howtolivebetter:
    command: "npx"
    args: ["-y", "howtolivebetter-mcp"]
    timeout: 30
```
</details>

### 从源码跑（想改代码时用这个）

```bash
git clone https://github.com/Helioswei/HowToLiveBetter-Kit.git
cd HowToLiveBetter-Kit
npm install
npm run sync          # 同步上游正文 → 生成数据 → 编译 → 跑测试
```

然后用 `node dist/cli.js` 当命令（把上面配置里的 `npx -y howtolivebetter-mcp`
换成 `node /绝对路径/HowToLiveBetter-Kit/dist/cli.js`）。

---

## 装上之后能问什么

- 替朋友担保签不签？替人担保前要看清什么？
- 我妈 60 多岁总说膝盖疼，书里有什么不花钱的建议？
- 被裁了，头一个月先办哪些事、能领什么？
- 有人在我面前倒地没呼吸，先做什么？
- 孩子发烧，家里那几种退烧药哪些不能给？
- 攒了 20 万，怎么放才不被费率和骗局吃掉？

真实返回长这样（问「担保」，节选）：

```
高性价比人生指南 · 作者 eternity4719 · CC BY 4.0 · 非官方转载（正文未改动，只做了结构化与排版处理）
许可 https://creativecommons.org/licenses/by/4.0/ ｜ 原始仓库 https://github.com/eternity4719/HowToLiveBetter
同步自上游 33362aff50（2026-10-10）｜ 共 677 条 / 34 节

【第 8 节第 18 条】借钱写清借条，替人担保前先想清楚自己愿不愿意替他还
  性价比 极高 · 收益 大 · 证据 A 级 · 口径 金钱 · 成本 钱0/时间少/毅力否
  说人话：借条要写全：出借人、借款人、金额、利率、期限、还款方式，双方签名。……
  替人担保时看清有没有「连带」两个字。……
```

---

## 四个工具

| 工具 | 干什么 | 主要参数 |
|:---|:---|:---|
| `search` | 按关键词 + 条件找条目，返回标题、说人话、成本标签、证据等级、出处 | `query`、`evidence`(A/B/C)、`money`(0/少/多)、`time`(少/中/多)、`will`(否/些/是)、`benefit`(大/中/小)、`caliber`(死亡率/金钱/时间/自由)、`ratio`(极高/高/一般)、`section`、`limit` |
| `get_entry` | 按节号 + 条号取一整条（成本 / 说人话 / 收益 / 证据等级 / 来源 / 备注） | `section`、`num` |
| `list_sections` | 34 节目录，带每节回答的问题和条数 | `section`（可选） |
| `daily` | 按日期稳定取一条，同一天同一条 | `date`（可选） |

筛选口径来自书上自己的标签，不是我们发明的：成本按「钱 / 时间 / 毅力」各三档，
收益量级大中小，口径分死亡率 / 金钱 / 时间 / 自由，证据等级 A / B / C。
性价比档（极高 / 高 / 一般）用的是上游 `tools/lib/book.mjs` 里那套算法，逐字照抄 ——
免得用户在我们这儿和官方检索页看到两个不一样的数。

---

## 为什么可以信它

**1. 只检索，不生成。** 服务端没有任何模型调用，也不联网：返回的每个字都是原文切片。
不解释、不换算、不补数字。不需要 API key，答案可复现。

**2. 查不到就说查不到。** 关键词是字面匹配（不是语义检索），命中率低于阈值就直接回
「书里没有写这件事」并给最接近的几节 —— 把不相关的建议推给模型，比说"没写"更糟。

**3. 保真校验是可以自己跑的。**

```bash
python3 tools/check_verbatim.py     # 逐字段比对上游原文：8064 项，0 失配
python3 tools/test_detection.py     # 六种破坏方式，检测器必须全部抓到
```

第二条是重点：**一个永远通过的检测器等于没有检测器**，
所以这个仓库里连"检测器是否有效"都有自测（改字段名、用没见过的标签取值、
新增字段、加条目、改写正文、删掉一整节 —— 六种都得被抓到）。

---

## 这个仓库产出两样东西

**1. 给 AI 用：MCP 服务（主要产物）**

让任何 AI 客户端直接按这本书回答：你问一句，它先去查这些条目的原文，再把原文读给你听，
并注明出自第几节第几条；书里没写的，它会说没写。
写这个仓库的时候，这本书还没有给 AI 用的接口 —— 这就是它存在的理由。

**2. 给国内读者用：`better.aigcwei.cn`（部署中）**

同一份解析结果再渲染成一个静态站，为国内读者准备：

- **能被搜索引擎搜到**：每节一页、每条一个独立链接，面向百度收录。
- **每一条能单独发出去**：`/08/18.html` 这样一个地址，微信里能直接发「你看这条」。
- **弱网也能读**：正文不依赖 JS（阅读设置与检索是仅有的两处脚本，内联在页面里，不额外发请求），无外部字体，打开一页一次请求（最重的一节 gzip 约 58KB）。

两样东西共用同一份解析结果，所以内容永远一致 —— 上游改一个字，MCP 和站点同时对齐。

---

## 它不做什么

- **不发布结构化数据集**：我们自用解析，不重复造。
- **不做翻译**：已有十来个语种版本。
- **不做 App、不做打卡清单**。
- **没有服务端**：没有后端、没有数据库、没有账号。

---

## 它是怎么跟上上游的

上游一天改好几轮的库，我们自己不盯：

- **每天 06:00（北京）** 自动检查上游提交，没变就跳过（不产生噪音提交）。
- 变了 → 重新解析 → 过四道检查 → 更新内容指纹并提交。
- **任何一步失败自动开 issue**（附运行链接和本地复现命令）。
- 内容指纹只存哈希（`sync/fingerprint.json`），所以"上游哪天动了哪几条"在 git 历史里查得到，
  而这个仓库里没有一个字是别人的正文。

四道检查：字段名 / 新增字段 / 新标签取值 / 断号 / 条数增减（`check_drift.py`）、
逐字段保真（`check_verbatim.py`）、内容变动（`fingerprint.py`）、
检测器自测（`test_detection.py`）。

---

## 开发

```bash
npm install
npm run sync        # 同步 → 解析 → 体检 → 保真 → 数据 → 指纹 → 编译 → 测试
npm test            # 14 个单元 + 5 个端到端（真起 stdio 服务）
npm run typecheck
```

目录：

```
src/           MCP 服务（TypeScript，stdio）
tools/         同步与解析（Python，只用标准库，兼容 3.9）
sync/          内容指纹（可入库，只存哈希）
test/          单元 + 端到端测试
```

---

## 许可

- **代码：MIT**（见 [LICENSE](LICENSE)）。
- **正文：《高性价比人生指南》** 作者 [eternity4719](https://github.com/eternity4719/HowToLiveBetter)，
  许可 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)，**原样转载、未作内容改动**。
  本项目不做任何再授权（CC BY 4.0 第 2(a)(5)(b) 条也不允许转载方施加额外限制）。
  下游使用时的署名义务见 [LICENSE-CONTENT](LICENSE-CONTENT)。

正本以原始仓库为准；本项目可能滞后于上游，每页/每次返回都标注同步到的是哪个提交。

医学内容不构成诊疗意见，法律内容不构成法律意见；个案请咨询执业医师或律师。
