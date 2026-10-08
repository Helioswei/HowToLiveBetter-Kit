#!/usr/bin/env bash
# 一条命令跑完整条链。任何一步失败立刻停（失败就停，不带着半成品往下走）。
#
#   bash tools/sync_all.sh                      # 从 .cache/upstream 拉最新
#   HLTB_UPSTREAM=~/AIWork/HowToLiveBetter bash tools/sync_all.sh   # 用本地那份克隆
#
# 步骤：同步 → 解析 → 格式体检 → 保真校验 → MCP 数据 → 内容指纹 → 编译 → 测试
set -euo pipefail
cd "$(dirname "$0")/.."

ARGS=""
if [ -n "${HLTB_UPSTREAM:-}" ]; then ARGS="--local ${HLTB_UPSTREAM}"; fi

echo "== 1/8 同步上游 =="
python3 tools/sync.py $ARGS

echo "== 2/8 解析正文 → build/entries.json =="
python3 tools/parse.py

echo "== 3/8 格式体检（上游改了格式/取值就报出来）=="
python3 tools/check_drift.py

echo "== 4/8 保真校验（逐字段比对原文）=="
python3 tools/check_verbatim.py

echo "== 5/8 生成 MCP 数据 → data/book.json =="
python3 tools/build_mcp_data.py

echo "== 6/8 更新内容指纹 → sync/fingerprint.json =="
python3 tools/fingerprint.py

echo "== 7/8 编译 MCP 服务 =="
npm run --silent build

echo "== 8/8 测试 =="
node --test

echo
echo "全部通过。本地 Hermes 里的 MCP 会自动读到新数据（它每次启动重读 data/book.json）。"
