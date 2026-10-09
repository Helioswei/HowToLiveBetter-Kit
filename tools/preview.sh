#!/usr/bin/env bash
# 本地预览：重建 dist/ 并起一个本地服务 —— 改完页面就跑这一条。
#
#   bash tools/preview.sh              # 重建 + 确保本地服务在跑
#   bash tools/preview.sh --no-serve   # 只重建，不起服务
#
# 上游正文从哪来：默认用 ~/.hermes/cache/scratch/htlb/repo（本机那份独立克隆），
# 不去动用户自己下载的那份；想换地方就 XIAOJIU_UPSTREAM=/path/to/upstream。
#
# 为什么不用 npm：这个仓库的构建链是 Python（npm 只管 MCP 那个包）。
set -euo pipefail
cd "$(dirname "$0")/.."

UPSTREAM="${XIAOJIU_UPSTREAM:-$HOME/.hermes/cache/scratch/htlb/repo}"
PORT="${PORT:-8100}"
SERVE=1
[ "${1:-}" = "--no-serve" ] && SERVE=0

# 0. 有本地克隆就顺手更新一下（干净的工作区才 pull；不确定就跳过，不阻塞预览）
if [ -d "$UPSTREAM/.git" ]; then
  if git -C "$UPSTREAM" diff --quiet && git -C "$UPSTREAM" diff --cached --quiet; then
    git -C "$UPSTREAM" pull -q --ff-only 2>/dev/null && echo "上游已更新到 $(git -C "$UPSTREAM" rev-parse --short HEAD)" \
      || echo "上游没拉成（离线？），用当前这份 $(git -C "$UPSTREAM" rev-parse --short HEAD)"
  else
    echo "上游工作区有未提交的改动，按现状用：$(git -C "$UPSTREAM" rev-parse --short HEAD)"
  fi
fi

echo "== 1/4 同步 → 解析 → MCP 数据 =="
python3 tools/sync.py --local "$UPSTREAM"
python3 tools/parse.py
python3 tools/build_mcp_data.py

echo "== 2/4 生成静态站 =="
python3 tools/build_site.py

echo "== 3/4 注入全站外壳（备案号/页头页脚）→ dist/ =="
python3 deploy/scripts/inject.py --root build/site --out dist \
  --config deploy/site-config.json --config-url https://aigcwei.cn/site-config.json
# 本地没有电子版文件，这一步会跳过（体积那一行留空）
python3 tools/annotate_downloads.py --site dist --quiet || true

echo "== 4/4 自检 =="
python3 tools/check_python_warnings.py
python3 tools/check_site.py --root dist --injected --skip-downloads | tail -3

if [ "$SERVE" = "1" ]; then
  if curl -ks -o /dev/null --max-time 3 "http://127.0.0.1:$PORT/" 2>/dev/null; then
    echo "本地服务已经在跑（http.server 每次请求都从磁盘读，dist 换了就是新的）"
  else
    # 独立会话起服务：不要 nohup 共享当前终端的 pty（见 AGENTS.md）
    perl -e 'setsid' python3 -m http.server "$PORT" --bind 127.0.0.1 --directory dist \
      </dev/null >>/tmp/hltb-preview.log 2>&1 &
    sleep 1
    echo "本地服务已起（日志 /tmp/hltb-preview.log）"
  fi
  echo "→ 打开 http://127.0.0.1:$PORT/"
fi
