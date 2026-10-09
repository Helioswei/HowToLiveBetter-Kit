#!/usr/bin/env bash
# better.aigcwei.cn 的构建脚本（在 EdgeOne Makers 的构建环境里跑）。
#
#   1. 拉站点产物包（我们仓库 CI 打好挂在 Release site-latest 上：710 个页面 + 四个电子版）
#   2. 拉全站配置（真源 aigcwei.cn/site-config.json；失败回退 deploy/site-config.json）
#   3. 注入 header/footer（含备案号，由 deploy/scripts/inject.py 强制）
#
# 产物写**仓库根的 dist/** —— 与 Makers 控制台默认的输出目录、以及 edgeone.json 里的
# outputDirectory 一致（TS 编译产物已挪到 lib/，不再和站点抢 dist/）。
# 任何一步失败立刻停，不出半成品。
set -euo pipefail
cd "$(dirname "$0")/.." # 仓库根

WORK="deploy/build" # 中间产物（.gitignore 里 build/ 已忽略）
SITE_TARBALL="${SITE_TARBALL:-https://github.com/Helioswei/HowToLiveBetter-Kit/releases/download/site-latest/site.tar.gz}"
CONFIG_URL="${CONFIG_URL:-https://aigcwei.cn/site-config.json}"

echo "== 1/3 拉站点产物 =="
rm -rf "$WORK" dist
mkdir -p "$WORK/site"
curl -fsSL --retry 3 --retry-delay 2 --max-time 180 "$SITE_TARBALL" -o "$WORK/site.tar.gz"
tar -xzf "$WORK/site.tar.gz" -C "$WORK/site"
rm -f "$WORK/site.tar.gz"
pages=$(find "$WORK/site" -name '*.html' | wc -l | tr -d ' ')
echo "  解出 ${pages} 个页面"
if [ "$pages" -lt 700 ]; then echo "✗ 页面数不对（${pages} < 700），产物包可能坏了"; exit 1; fi

echo "== 2/3 拉全站配置 =="
if curl -fsSL --max-time 20 "$CONFIG_URL" -o deploy/site-config.json; then
  echo "  配置来自 $CONFIG_URL"
else
  echo "  ⚠️ 配置拉取失败，回退仓库里的 deploy/site-config.json"
fi

echo "== 3/3 注入全站外壳（含备案号）=="
python3 deploy/scripts/inject.py --root "$WORK/site" --out dist \
  --config deploy/site-config.json --config-url "$CONFIG_URL"

# 自检：注入后每页都要有备案号，且不许残留占位符；四个电子版都要在
# ⚠️ 两处坑：
#   1. grep 在「一行都没匹配」时退出码是 1，set -e 下会让脚本直接挂 —— 必须 || true
#   2. download/ 里是镜像来的上游电子版（PDF/EPUB/离线单文件），那是**下载附件**不是本站页面，
#      本来就没有我们的外壳与备案号，必须排除
miss=$({ grep -rL 'ICP备' dist --include='*.html' --exclude-dir=download || true; } | wc -l | tr -d ' ')
left=$({ grep -rl 'id="site-footer"></div>' dist --include='*.html' --exclude-dir=download || true; } | wc -l | tr -d ' ')
echo "  缺备案号的页面：${miss}　残留占位符的页面：${left}"
if [ "$miss" != "0" ] || [ "$left" != "0" ]; then echo "✗ 外壳注入不合格"; exit 1; fi
for f in HowToLiveBetter.epub HowToLiveBetter.pdf HowToLiveBetter.html HowToLiveBetter.apkg; do
  if [ ! -s "dist/download/$f" ]; then echo "✗ 电子版缺失：$f"; exit 1; fi
done
echo "  电子版镜像齐全：$(ls -1 dist/download | tr '\n' ' ')"
# 下载页的电子版体积：生成站点时文件还没到手，这里补上（幂等，缺文件就不填）
python3 tools/annotate_downloads.py --site dist --quiet || true
echo "构建完成 → dist/（$(find dist -name '*.html' | wc -l | tr -d ' ') 个页面）"
