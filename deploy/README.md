# 上线 better.aigcwei.cn（EdgeOne Makers）

这套东西**不需要新建部署仓库**：Makers 直接读本仓库根的 `edgeone.json`，
构建命令是 `bash deploy/build.sh`，产物目录 `deploy/dist`。

## 构建链（每一步都会自检，失败就不出产物）

```
deploy/build.sh
├─ 1. 拉站点产物包   GitHub Release「site-latest」的 site.tar.gz（710 页 + 四个电子版）
│                    —— 只依赖这一个文件：少一个失败点，也免得 Makers 去连 GitHub 的多个下载地址
├─ 2. 拉全站配置     https://aigcwei.cn/site-config.json（失败回退仓库里的兜底副本，构建不挂）
└─ 3. 注入全站外壳   scripts/inject.py —— header/footer 与**备案号**在构建时写进每个页面
     然后自检：页面数 ≥ 700、每页都有备案号、不许残留占位符、四个电子版都在
```

**备案号不在这套代码里**：页面只留两个占位符 `<div id="site-header"></div>` 和
`<div id="site-footer"></div>`，真源是网站家族的 `site-config.json`（`icp` 字段）。
`deploy/scripts/inject.py` 与 `website/scripts/inject.py` 是同一份文件（md5 一致），
改的话两边都要同步 —— 真源在 `~/work/project/web/website/scripts/inject.py`。

## 上手步骤

1. **EdgeOne 控制台 → Makers → 新建项目**，仓库选 `Helioswei/HowToLiveBetter-Kit`，
   分支 `main`。构建配置读仓库里的 `edgeone.json`，不用手填（和 website 一样是"配置即代码"）。
2. 首次构建会看构建日志；成功后拿到 Makers 给的默认域名，先点开验收：
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' https://<默认域名>/
   curl -s https://<默认域名>/ | grep -c 'ICP备'          # 应 ≥ 1
   curl -s https://<默认域名>/08/18.html | grep -c '第 8 节第 18 条'   # 应 ≥ 1
   ```
3. **加子域** `better.aigcwei.cn`：在 Makers 项目里绑定自定义域名，按它给的记录去 DNS 加解析
   （与 life.aigcwei.cn 同一套流程）。
4. 绑定后复验：
   ```bash
   curl -s https://better.aigcwei.cn/ | grep -c 'ICP备'
   curl -s -o /dev/null -w '%{http_code}\n' https://better.aigcwei.cn/sitemap.xml
   ```
5. 收录：把 `https://better.aigcwei.cn/sitemap.xml` 提交到百度站长（和主站同一流程）。

## 出问题怎么办

| 现象 | 原因与处理 |
|:---|:---|
| 构建日志里拉 site.tar.gz 失败/超时 | Makers 构建环境连 GitHub Release 不稳。备份方案：把产物包推到仓库的 `site-dist` 分支，改用 jsDelivr 取（国内可达）：`SITE_TARBALL=https://cdn.jsdelivr.net/gh/Helioswei/HowToLiveBetter-Kit@site-dist/site.tar.gz` —— build.sh 的 `SITE_TARBALL` 环境变量可直接覆盖 |
| "缺备案号的页面：N" 报错 | 某个页面没带占位符，或 `site-config.json` 拉取失败且兜底副本也被改坏。查 `deploy/site-config.json` 里的 `icp` |
| "电子版缺失" 报错 | 上游改了 Release 文件名。看 `tools/build_site.py` 里 `download_body()` 的四个文件名，与上游 Release 对齐 |
| 页面上样式不对 | 共享样式在 `assets.aigcwei.cn/style.css`（另一个仓库 website-tools），改那里 |

## 内容怎么更新

不用管。上游正文一变，我们仓库的「同步上游」workflow（每天 06:00）会更新指纹，
「站点产物」workflow（每天 06:30）会重新打包并覆盖 Release 里的 site.tar.gz；
Makers 那边重新构建一次就拿到新内容（也可以在 Makers 里开自动构建）。
