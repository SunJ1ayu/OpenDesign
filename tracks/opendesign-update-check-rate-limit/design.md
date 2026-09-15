# Design: opendesign-update-check-rate-limit

- Change: opendesign-update-check-rate-limit
- Status: draft

- 规划双出: 不适用(没派 GPT 双出);改用 panel-explore 做前提攻击 —— 主 agent 方向先落盘 `/root/aiwork/tasks/opendesign-update-check-rate-limit-my-direction.md`,
  四家(MiMo / DeepSeek / GLM-5.3 / Grok)对同一份 brief 各出一个方向,综合写在 `evidence/explore-update-source.md`。

## Approach

### 查法:订阅源为主,API 为备

- **主**:`https://github.com/SunJ1ayu/OpenDesign/releases.atom`(github.com 网页端,不是 api.github.com)。
  从每个 entry 的 `<link href=".../releases/tag/<tag>">` 取 tag 原文;只认 `TAG_RE`;**按版本号取最大,不按条目先后**。
- 取到最大那一版后,拉同一 release 下的清单 `releases/download/<tag>/OpenDesign-update.json`(和安装包同一个下载通道):
  ```json
  {"schema": 1, "tag": "win-installer-0.98.6", "version": "0.98.6",
   "asset": {"name": "OpenDesign-Setup-0.98.6.exe", "size": 46751938, "sha256": "<64 hex>"},
   "notes": "<发布说明 markdown,可缺>"}
  ```
  清单逐项核对:schema==1、tag 与来路 tag 相同、version 与 tag 里的版本同值、asset.name 合 `ASSET_RE` 且版本同值、sha256 是 64 位十六进制、size 是正整数。
  任一不符 ⇒ 这条来源失败(不是"无校验地继续")。
- 订阅源 + 清单拼成与 API 同形的 releases 列表(`tag_name / html_url / body / draft / assets[{name, browser_download_url, size, digest}]`),
  **交给现有 `decide()`** —— 挑最新、跳草稿、不往回装、release_url 用 GitHub 给的原文,这些既有判据(t1~t3、F1)全部照旧生效。
  下载地址 = `https://github.com/<repo>/releases/download/<tag 原文>/<清单里的 asset.name>`,与 GitHub 的 `browser_download_url` 同形。
- **备**:订阅源这条失败(网络 / 解析 / 清单缺或不符 / decide 报错)⇒ 照旧问 API。两条都失败 ⇒ error 里两条原因都写上。
- 最大那一版不比本机新 ⇒ 不拉清单,直接"已是最新"(省一次请求,也不因为老版本没有清单而误报失败)。
- `check_for_update(current, fetch=None)`:显式传 `fetch` 时只用它(既有判据的注入方式不变);不传时依次 订阅源 → API。

### 联网:代理在请求那一刻读

`fetch_releases`、订阅源、清单三处一律 `urllib.request.build_opener().open(req, timeout)`(t30b 同一修法),不用进程级缓存的 `urlopen`。

### 失败要说人话

- 后端 `error` 改成人话 + 括号里的技术细节,例如
  `查更新失败:GitHub 限制了这个网络出口的查询次数(同一出口的人查得太多)(HTTP 403)`;
  超时 / 连不上 ⇒ `连不上 GitHub(检查网络或 VPN)`;清单不对 ⇒ `新版缺少可核对的安装包信息`。两条来源各一句,用「;」连。
- 界面:「查不到更新」那一行下面多一行小字显示 `error`(`updateReason()` 纯函数给出;ds_web 不可达时说「软件后台没响应」)。

### 发版

- `installer/make-update-manifest.py <exe> <tag> [--notes FILE] --out FILE`:从**构建产物本身**算 sha256 与大小,写清单。
- 发版步骤:`gh release create <tag> <exe> OpenDesign-update.json …`;发布后核对:用产品自己的订阅源路径以旧版身份查到新版、digest 与本地一致。
  (下一版 0.98.6 起执行;0.98.5 及以前的 release 没有清单 ⇒ 订阅源路径看到它们时回落 API —— 但新客户端本机就是 ≥0.98.6,不会以它们为目标。)

### Windows 真机 e2e

`.github/scripts/fake_github.py` 增加 `releases.atom` 与清单两个端点;API 端点加一种「403 限流」模式。
e2e 全部场景默认让 API 回 403 ⇒ **一键更新走的是订阅源 + 清单这条新路**;另加一场景:订阅源坏、API 好 ⇒ 仍能更新(备路)。

## Key trade-offs / risks

1. **订阅源是 GitHub 没有承诺稳定的网页端点**:改版会让主路失效 —— 有 API 备路;两路都坏时界面说清原因。
2. **信任根不变、没有更强**:清单与安装包出自同一个 GitHub 账号。三家主张给清单加签名(GPG / Ed25519),**本单不做**:
   这次要治的是"查不到"(可用性),不是"被冒充";私钥只能放在发版这台机器上,和 gh 凭证在一起,挡不住最现实的那种失陷;
   丢钥匙 = 已装客户端再也不能自动更新。记为以后可选,不假装做了。
3. **atom 在共用 VPN 出口上是否另有限流没实测**(我只从一台干净 IP 连打 70 次 = 70 个 200)。所以必须留 API 备路,且失败原因必须显示出来。
4. **安装包地址由清单 + tag 拼出**(F1 纪律说"地址由 GitHub 给"):用 tag 原文与清单里的文件名原文拼,不用补零后的版本号;e2e 走真下载。
5. **发版多一个必须做对的步骤**:清单由脚本从构建产物生成,发布后核对用产品自己的新路径 —— 漏传清单会在发布核对里当场红。
6. 订阅源只含最近 10 个 release:取最新一版足够。
7. **不在本单**:撤回 / 最低支持版本开关(MiMo、DeepSeek 提)、启动时绕过 6 小时缓存与失败退避(DeepSeek、GLM 提)、断点续传(GLM 提)
   —— 前两项归「打开软件倒计时自动更新」那单;续传另议。

## Alternatives considered

- **API 为主、订阅源兜底**(我原来的方向):以后每次打开都查,共用出口上 API 多半已被限流,先问它纯属白等;四家里三家主订阅源为主。改。
- **只传一个 `.sha256` 小文件**(我原来的方向):清单 JSON 能同时带大小、文件名、版本、说明,一次拿全且可交叉核对。改。
- **仓库里放 `update/latest.json` 走 raw.githubusercontent.com**:发版后要多一次提交;raw 同样有未登录限流;国内 raw 常被污染。不选。
- **发版改成正式版,用 `releases/latest/download/…` 一次拿全**:要改发版性质,业主定;`/releases/latest` 当年踩过 404(t1)。不选。
- **自建镜像 / 带 token**:新基础设施或把密钥放进客户端。不选。

## Test strategy (oracle)

主 agent 拥有,先行落盘、单独 commit。编号前缀 `rl`。判据一律不打外网(替身 + t30 那套"DNS 非本机一律拒绝")。

| id | 断言 | 文件 |
|---|---|---|
| `rl1` | `parse_atom`:从真实形状的 atom 里取出 tag / html_url;非 `win-installer-*` 的 tag 丢弃;不是 XML ⇒ 抛 | `tests/test_ds_update_source.py` |
| `rl2` | **按版本号取最大**:atom 条目顺序是 0.98.5、0.99.1、0.98.7 ⇒ 选 0.99.1(不是第一条) | 同上 |
| `rl3` | 清单核对:合法清单 ⇒ asset `{name, browser_download_url, size, digest:"sha256:<hex>"}`,地址 = `…/releases/download/<tag 原文>/<name>`;tag 不符 / version 不符 / 文件名版本不符 / sha256 形状错 / size≤0 / schema≠1 / 不是 JSON 各自 ⇒ 失败 | 同上 |
| `rl4` | 订阅源这条成功时,**API 一次都不问**;结果与 API 给同一版时 `decide` 的结果同形(latest / asset / release_url / notes) | 同上 |
| `rl5` | 订阅源这条失败(网络异常 / 清单 404 / 清单不符)⇒ 回落 API 并成功;API 也失败 ⇒ `error` 同时含两条原因,`update_available` 为假 | 同上 |
| `rl6` | 最大那一版不比本机新 ⇒ 不拉清单,返回"已是最新"(无 error) | 同上 |
| `rl7` | 人话:HTTP 403 带 rate limit ⇒ error 含「限制了这个网络出口的查询次数」;超时 / URLError ⇒ 含「连不上 GitHub」;原技术细节仍在括号里 | 同上 |
| `rl8` | 三处联网都**在请求那一刻读代理**:先装一个不走代理的全局 opener(模拟进程早先联过网),再打开假代理 ⇒ API / 订阅源 / 清单三个请求都进了代理、没有直连(t30b 同法) | 同上 |
| `rl8e` | 清单请求的 `Accept` 是 `application/octet-stream`(不含 json)—— **真 GitHub 的下载地址带 `Accept: application/json` 回 404**(09-15 夜真 GitHub 冒烟照出,curl 三种 Accept 实测) | `tests/test_ds_update_source.py` |
| `rl9` | 显式传 `fetch=` 时只用它、不碰订阅源(既有 t7~t9 注入方式不变,也防判据真打网) | 同上 |
| `rl10` | `make-update-manifest.py`:sha256 / size 来自文件本身;tag 与文件名版本不一致 ⇒ 拒绝生成;生成物能被 `rl3` 的核对原样接受(往返) | `tests/test_update_manifest.py` |
| `rl11` | 界面 `updateReason()`:有 error ⇒ 原样给出;查完没拿到数据 ⇒「软件后台没响应」;成功 / 检查中 ⇒ 空 | `tests/test_update_ui.mjs` |
| `rl12` | fake_github:atom 与清单两个端点、API 的 403 模式;e2e 场景默认 API=403 | `tests/test_update_e2e_harness.py` |
| `e2e` | Windows 真机:API 回 403 时一键更新照常完成(全部既有场景走新路);订阅源坏、API 好 ⇒ 仍完成 | `.github/workflows/windows-update-e2e.yml` |

另:`t12`(`fetch_releases` 问的就是 `releases_url()`)原来靠替换 `urllib.request.urlopen` 截获地址 —— 改成 `build_opener()` 之后它截不到、还会真打网。
**判卷改问法**(先于实现单独提交):截获点换成 `urllib.request.OpenerDirector.open`。

### 这个 oracle 能被什么骗过?

1. **替身形状 ≠ GitHub 真形状**:rl1 的 atom 夹具从真 `releases.atom` 裁剪(录于 09-15),而不是手写;发布核对用产品真路径打真 GitHub。
2. **单测里订阅源成功,真 GitHub 上清单没传**:发布核对与 Windows e2e 接住;漏传会当场红。
3. **共用 VPN 出口上 atom 也被限**:任何判据都答不了 —— 只能靠备路 + 界面显示原因,真机上业主会看到哪一条挂了。
4. **rl8 用环境变量代理模拟 Windows 注册表代理**:两者都经 `getproxies()`,读取时机同一处;注册表那半只有真机答得了。
