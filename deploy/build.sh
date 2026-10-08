#!/usr/bin/env bash
# better.aigcwei.cn 的构建脚本（在 EdgeOne Makers 的构建环境里跑）。
#
#   1. 拉站点产物包（我们仓库 CI 打好挂在 Release site-latest 上，里面含 710 个页面 + 4 个电子版）
#   2. 拉全站配置（真源 aigcwei.cn/site-config.json；失败回退本地副本，构建不挂）
#   3. 注入 header/footer（含备案号，由 scripts/inject.py 强制）
#
# 任何一步失败立刻停 —— 构建不出半成品。
set -euo pipefail
cd "$(dirname "$0")"

SITE_TARBALL="${SITE_TARBALL:-https://github.com/Helioswei/HowToLiveBetter-Kit/releases/download/site-latest/site.tar.gz}"
CONFIG_URL="${CONFIG_URL:-https://aigcwei.cn/site-config.json}"

echo "== 1/3 拉站点产物 =="
rm -rf site dist site.tar.gz
mkdir -p site
curl -fsSL --retry 3 --retry-delay 2 --max-time 180 "$SITE_TARBALL" -o site.tar.gz
tar -xzf site.tar.gz -C site
rm -f site.tar.gz
pages=$(find site -name '*.html' | wc -l | tr -d ' ')
echo "  解出 ${pages} 个页面"
if [ "$pages" -lt 700 ]; then echo "✗ 页面数不对（${pages} < 700），产物包可能坏了"; exit 1; fi

echo "== 2/3 拉全站配置 =="
if curl -fsSL --max-time 20 "$CONFIG_URL" -o site-config.json; then
  echo "  配置来自 $CONFIG_URL"
else
  echo "  ⚠️ 配置拉取失败，回退本地副本（site-config.json）"
fi

echo "== 3/3 注入全站外壳（含备案号）=="
python3 scripts/inject.py --root site --out dist

# 自检：注入后的产物每页都必须有备案号，且不能残留占位符
miss=$(grep -rL 'ICP备' dist --include='*.html' | wc -l | tr -d ' ')
left=$(grep -rl 'id="site-header"></div>' dist --include='*.html' | wc -l | tr -d ' ')
echo "  缺备案号的页面：${miss}　残留占位符的页面：${left}"
if [ "$miss" != "0" ] || [ "$left" != "0" ]; then echo "✗ 外壳注入不合格"; exit 1; fi

for f in HowToLiveBetter.epub HowToLiveBetter.pdf HowToLiveBetter.html HowToLiveBetter.apkg; do
  if [ ! -s "dist/download/$f" ]; then echo "✗ 电子版缺失：$f"; exit 1; fi
done
echo "  电子版镜像齐全：$(ls -1 dist/download | tr '\n' ' ')"
echo "构建完成 → dist/"
