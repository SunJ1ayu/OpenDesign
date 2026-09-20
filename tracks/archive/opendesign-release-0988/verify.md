# Verify: OpenDesign 0.98.8 发布

## 范围

代码面只有三样:`bin/ds_web.py` 的 `VERSION`、Windows 探针 workflow 的四处默认值,
以及一处**归档打断的路径引用**(`tests/e2e/auto_update_countdown.e2e.mjs:8` 里的收据目录,
原 track 归档后失效,改指 `tracks/archive/…`)。业务行为一个字没动。
本版要发布的那件事(打开软件不再被更新检查挡住)的验收与四轮外审属于原功能 track,见
`../archive/opendesign-startup-not-blocked-by-update/verify.md`,本单不重复计入。

## 收据(机器写的,逐字节粘;别手改)

runlog: release-regression rc=3 commit=1db78c2 dirty=no final=yes at=2026-09-20T10:00:02Z file=tracks/opendesign-release-0988/evidence/20260920T100002Z-01-release-regression.txt
runlog: build-installer-0988-release rc=0 commit=1db78c2 dirty=yes final=yes at=2026-09-20T10:13:23Z file=tracks/opendesign-release-0988/evidence/20260920T101323Z-01-build-installer-0988-release.txt
runlog: make-update-manifest-0988 rc=0 commit=1db78c2 dirty=yes at=2026-09-20T10:16:49Z file=tracks/opendesign-release-0988/evidence/20260920T101649Z-01-make-update-manifest-0988.txt
runlog: published-bytes-match-0988 rc=0 commit=1db78c2 dirty=yes at=2026-09-20T10:17:40Z file=tracks/opendesign-release-0988/evidence/20260920T101740Z-01-published-bytes-match-0988.txt
runlog: real-feed-path-as-0987 rc=0 commit=1db78c2 dirty=yes at=2026-09-20T10:17:58Z file=tracks/opendesign-release-0988/evidence/20260920T101758Z-01-real-feed-path-as-0987.txt
runlog: update-code-identical-to-0987 rc=0 commit=1db78c2 dirty=yes at=2026-09-20T10:18:28Z file=tracks/opendesign-release-0988/evidence/20260920T101828Z-01-update-code-identical-to-0987.txt

发布:https://github.com/SunJ1ayu/OpenDesign/releases/tag/win-installer-0.98.8
(prerelease,target `1db78c20043a69710c37e777147d8748a10b8c3d`;
安装包 `OpenDesign-Setup-0.98.8.exe` 46799268 字节,
sha256 `4766e45d316f1acc3c6216b7d1aacfbd158dd4ba29b38fd30015cc7dee84e4bc`;清单一起传了)

## 判读(别让收据被误读)

**1. 回归 `rc=3` 不是失败,但也不许说成全绿。** 六段全 PASS、0 FAIL:
泄漏闸 14 条、node 461 通过/0 跳过、python **1793 跑过/1 跳过**、MCP 三闸全绿、
dist 与源码同步、e2e 41 PASS/0 FAIL/2 SKIP。
`rc=3` = 那 3 条要起 gateway 才能跑的没跑(与 0.98.7 那单、与历史 `9e7f95d` 同形)。
这一版没碰 gateway 那条路,不因此挡发布。要真绿须起 gateway 跑 `--with-gateway`。

> 顺带一条事实:原功能 track 最终回归里红过的 `test_ds_shell_core.test_b8`
> (双击两下只许一份赢),**这一趟是绿的**。与当时"不是本单引入、不修不调判据"的定性一致;
> 那张待开单(给 b8 加失败当场取证)照旧欠着。

**2. 🔴「以 0.98.7 身份查得到 0.98.8」这条,对业主是成立的 —— 而且这次有 blob 级证据。**
`real-feed-path-as-0987` 跑的是**本仓当前代码**;光凭它不能断言业主那台查得到
(0.98.7 那单的「0.98.5 也查得到」就是这么假绿的)。所以另跑了 `update-code-identical-to-0987`:

```
bin/ds_update.py:       blob@0.98.7=58cb20c31a658eecc19102c6272aaf7d98d3da71  blob@HEAD=同
bin/ds_update_apply.py: blob@0.98.7=7a2f73832c48b7c1ced76397a0f89a85141a3d22  blob@HEAD=同
```

两份字节完全相同 ⇒ 他 0.98.7 里跑的查更新代码就是我核对时跑的那一份。
调用顺序断言 `['fetch_atom','fetch_manifest']` ⇒ 只问订阅源 + 清单,**API 一次没问**
(他的 VPN 出口被限流也不影响)。
⚠️ **0.98.6 及更早**本单不给结论:那要跑旧版实现才问得出。发布说明里写的是
"0.98.6 / 0.98.7 可以点检查更新;0.98.5 及更早请手动装"——0.98.6 那句沿用 0.98.7 单的结论。

**3. 已发布字节 == 本地构建 == 清单描述**,并逐字节 `cmp` 通过;
清单 sha256 由 `make-update-manifest.py` 从构建产物本身算(不手写),且**在最后一次打包之后**生成。

**4. 亲眼核过 payload 里装的确实是这一版的东西**(不只是版本号对):
`pkg/ds/bin/ds_web.py` 的 `VERSION = "0.98.8"`;本单新增的 `ds_auto_update.py` /
`ds_update_startup.py` 都在 payload 里;前端 `dist` 里能找到 `/api/update/startup`
与 `/api/update/prepare`(= 打包进去的是改过的前端,不是旧 dist)。

## Windows 云机探针

```
runlog: windows-probe-0988-verdict rc=0 commit=1db78c2 dirty=yes at=2026-09-20T10:24:55Z file=tracks/opendesign-release-0988/evidence/20260920T102455Z-01-windows-probe-0988-verdict.txt
runlog: startup-no-network-on-real-windows rc=0 commit=1db78c2 dirty=yes at=2026-09-20T10:26:18Z file=tracks/opendesign-release-0988/evidence/20260920T102618Z-01-startup-no-network-on-real-windows.txt
```

run **35504699542**(workflow `windows-package-probe`,head `1db78c20043a…`,conclusion success):

```
PHASE 1  下载安装包     OK —— OpenDesign-Setup-0.98.8.exe,44.6 MB(从已发布的 release 下的)
PHASE 2  静默安装       退出码 0,耗时 46s
PHASE 3  装完查文件     OK —— 三个关键文件都在,装完 176 MB
PHASE 4  启动           OK —— 已拉起 OpenDesign.exe
PHASE 5  服务活了吗     OK —— /api/health 通(端口 8766,**version=0.98.8**)
PHASE 6  窗口在不在     OK —— 「OpenDesign」·pythonw(另有 0 个报错框)
PHASE 7  截图与白屏体检 90s/110s/140s/170s/230s 五次:颜色 49 种 / 近白 38.2%(读数完全一致)
PHASE 10 带系统代理启动 OK —— 45s,颜色 76 种 / 近白 27.5%(与 0.98.7 那次同读数)
裁决收据独立复核:no FAIL verdict in the receipt
```

**看过图了**(探针自己写着"白屏读数不在闸内,仍要看图"):90s 与 230s 两张截图一致 ——
工作区已经打开(左侧「新对话/搜索/待办事项/技能」、首屏问候语、输入框都在),
中间是干净机器上应有的「AI 模型 key」首次配置弹窗,顶部一条「连接不上 gateway」提示
(云机上本来就没有 gateway,历史同形)。**不是白屏**;读数五次不变 = 画面停在等填 key,合理。

### 🔴 本单最硬的一份证据:真 Windows 现场的改前/改后对照

同一台云机探针、同一套流程,两次 run 取回的**真实 `工作台.log`**:

| | 启动那一批请求 | 联网查更新发生在 |
|---|---|---|
| **0.98.7**(run 35446165320) | `todos` / `health` / `credential` / `consent` / `projects` **+ `GET /api/update/check`** | **启动那一秒**(13:35:40,与其它请求同批) |
| **0.98.8**(run 35504699542) | `todos` / `health` / `credential` / `consent` / `projects` **+ `GET /api/update/startup`**(只读盘) | **10:20:55**,比启动晚整整 **60 秒**(`prepare` + `check` 一起) |

外壳日志上的启动时间线(0.98.8):`+2297ms backend.ready` → `+4906ms window.shown`
→ `+7516ms frontend.frame_submitted 1028x719`,整条路上一次网都没联。

⇒ **业主原话那件事,在真机上是成立的**:打开软件不再等更新检查。
(云机网络快,0.98.7 那一跳当时返回得也快 —— 所以这份对照证明的是**结构**:
启动路径上还有没有那一跳。业主那边网慢/挂死时,差别就是他抱怨的那 20 秒。)

## 还欠

**业主真机一趟(只有他能做)**:在他自己的机器上装一次 0.98.8(或在 0.98.7 里点「检查更新」),
并让**运行中的软件**回显版本号 0.98.8。
云机探针回显只证明安装包在干净机器上装得上、起得来,**不等于他那两台**
(公司 `F:\AI\OpenDesign` / 家里 `D:\AI\OpenDesign`,上面有他的真实档案与参考图库)。
盘上有新文件不算部署 —— 运行中的目标自己报出 0.98.8 才算。

## arbitrated verdict(主裁)

**PASS**(2026-09-20 18:2x)。impact-risk `self` ⇒ 外审预算 0:本单代码面只有版本字符串、
探针默认值和一处失效路径引用;要发布的那件事的双家族外审已在原功能 track 走完四轮。

判 PASS 的依据(不是"跑完了流程"):
1. 发出去的**字节**与本地构建、与清单三者一致并逐字节 `cmp`;
2. **业主那台查得到**,而且这次是 blob 级证明(他 0.98.7 里的 `ds_update.py` 与核对时跑的同一份);
3. **装得上、起得来、自己报出 0.98.8**(云机 `/api/health` version=0.98.8),截图亲眼看过不是白屏;
4. **本单承诺在真机上成立**:启动那一批请求里 `check` 换成了只读盘的 `startup`,
   联网推迟 60 秒 —— 用同一台云机改前/改后的日志对照,不是本地判据自证。

**没做的、不冒充**:gateway 那 3 条 e2e 没跑(要起服务);0.98.6 及更早能不能查到这一版没结论;
**业主自己那两台机器还没装** —— 按部署规矩,那才是"发完"的最后一步。
