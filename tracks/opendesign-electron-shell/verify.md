# Verify: opendesign-electron-shell

- Date: 2026-09-21

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再按 impact-risk 预算跑 panel-review；只有特殊控制面
> 才显式 `--all` 做全池评审。最后仍由主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [ ] build passes
- [ ] tests pass
- [ ] no secrets / unsafe ops

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,把它打印的收据行原样粘进来:

```
runlog -t opendesign-electron-shell -- <判据命令>
```

T3 判据先红(实现一行都还没写;红因全是「被测模块/文件不存在」或「退役文件还在」,不是判据自己坏):

```
runlog: t3-red-node rc=1 commit=521bdaf dirty=yes at=2026-09-22T08:17:14Z file=tracks/opendesign-electron-shell/evidence/20260922T081714Z-01-t3-red-node.txt
runlog: t3-red-py rc=1 commit=521bdaf dirty=yes at=2026-09-22T08:17:19Z file=tracks/opendesign-electron-shell/evidence/20260922T081719Z-01-t3-red-py.txt
```

派活前的判据 commit(旧判据按迁移账删 / 改写)之后,改写过的几条在旧实现上红(`rc=0` 是管道末尾那个 grep 的,
红在内容里:w3/w4/s17 找不到 ds_host.py、ctypes 豁免失效、shell_chrome 5 条、startup_report 2 条):

```
runlog: t4pre-retarget-red rc=0 commit=6e397b4 dirty=yes at=2026-09-22T08:24:32Z file=tracks/opendesign-electron-shell/evidence/20260922T082432Z-01-t4pre-retarget-red.txt
```

派活前攻题(23 条,处置 `evidence/20260922-t4-attack-disposition.md`)之后补的判据,在旧实现上全红
(node 42/42 红、python 15 条红;`rc=0` 同样是管道末尾 grep 的;desktop_update e2e 已改成红在有名字的 FAIL 上):

```
runlog: t4pre-attackfix-red rc=0 commit=dd2d2e1 dirty=yes at=2026-09-22T09:09:56Z file=tracks/opendesign-electron-shell/evidence/20260922T090956Z-01-t4pre-attackfix-red.txt
```

派活前复核(Cursor grok-4.7-high,BLOCK 两条必须修 + 我同类再扫,处置在同一份 disposition 的「复核」一节)之后补的判据
(mc2b/mc2c/mc5b、mc14/mc16 加断言、c10 补齐 + c10b~c10e、r8、desktop_update 提示改对照)在旧实现上红;
**判据的判据** `evidence/c10_samples_check.py`:写对的样例 main.js 全绿、11 种写错的各在对应那一条上红(0 例不符预期):

```
runlog: t4pre-recheckfix-red rc=0 commit=a74d33a dirty=yes at=2026-09-22T11:15:19Z file=tracks/opendesign-electron-shell/evidence/20260922T111519Z-01-t4pre-recheckfix-red.txt
```

另:c1/c2/c2b/c5 对着探路版的 package.json / installer.nsh 跑过是绿的(证明判据**过得去**,不是出了一道做不对的题);
c3 对探路版是红的 —— 对的,探路版的 publish 指本机替身源。

```
# T4 Python 管家那一半(主 agent 写)的判据跑
runlog: t4-python-half rc=0 commit=d064fa2 dirty=yes at=2026-09-22T11:32:49Z file=tracks/opendesign-electron-shell/evidence/20260922T113249Z-01-t4-python-half.txt
# **红**:T4 收货读 diff 抓到的规格洞判据先红(567d4c4),修复 10dadf7
runlog: t4recv-red rc=0 commit=7a86006 dirty=yes at=2026-09-22T12:21:44Z file=tracks/opendesign-electron-shell/evidence/20260922T122144Z-01-t4recv-red.txt
# **rc=3**:收货后本地总跑,各段全绿、3 条老的没跑(1 条 python skip 09-19 起就在;2 条要活 gateway 的聊天 e2e)—— 不算通过也不算红,如实贴
runlog: t4-runall-after-receive rc=3 commit=10dadf7 dirty=no final=yes at=2026-09-22T12:26:14Z file=tracks/opendesign-electron-shell/evidence/20260922T122614Z-01-t4-runall-after-receive.txt
# **红**:c11 锁文件钉在腾讯云内网镜像(云跑 E1 npm ci 死因),修复 a30dcb4
runlog: c11-lock-red rc=0 commit=caadd68 dirty=yes at=2026-09-22T12:43:28Z file=tracks/opendesign-electron-shell/evidence/20260922T124328Z-01-c11-lock-red.txt
# **红**:c12 PowerShell 大小写同名(第二跑 E5.samever 假红 / E4.oldmap 假绿的根因),修复 2c9e477
runlog: c12-ps-case-red rc=0 commit=a30dcb4 dirty=yes at=2026-09-22T13:03:47Z file=tracks/opendesign-electron-shell/evidence/20260922T130347Z-01-c12-ps-case-red.txt
# **红**:c12b `$名字:`(我自己改 SilentUninstall 时写出的解析错 + 老的 E4 说明行),修复 34a8e14
runlog: c12b-drive-colon-red rc=0 commit=fdf2185 dirty=yes at=2026-09-22T13:32:25Z file=tracks/opendesign-electron-shell/evidence/20260922T133225Z-01-c12b-drive-colon-red.txt
# 云 Windows 第五跑 FAIL 0(T4 定稿)
runlog: t4-cloud5-run35734249784 rc=0 commit=03fe6d8 dirty=no at=2026-09-22T13:47:40Z file=tracks/opendesign-electron-shell/evidence/20260922T134740Z-01-t4-cloud5-run35734249784.txt
# **rc=3**:T5 派发前本地总跑,各段全绿、同样 3 条老的没跑
runlog: t4-runall-before-t5 rc=3 commit=8090486 dirty=no final=yes at=2026-09-22T13:48:17Z file=tracks/opendesign-electron-shell/evidence/20260922T134817Z-01-t4-runall-before-t5.txt
# **红**:T5 第 1 轮修复清单的判据先红(C13a/b/c + mc16b),修复 a5641db / 13749e8 / 24eaf99
runlog: t5r1-oracle-red rc=0 commit=6c7cc8e dirty=yes at=2026-09-22T14:37:44Z file=tracks/opendesign-electron-shell/evidence/20260922T143744Z-01-t5r1-oracle-red.txt
# **rc=3**:第 1 轮修复后本地总跑,各段全绿、同样 3 条老的没跑
runlog: t5r1-runall-after-fix rc=3 commit=fd7be20 dirty=no final=yes at=2026-09-22T14:41:18Z file=tracks/opendesign-electron-shell/evidence/20260922T144118Z-01-t5r1-runall-after-fix.txt
# **最后一份**:第 1 轮修复后云 Windows 整跑 FAIL 0(118 OK,含 E3c);第 2 轮评审即绑定这份内容
runlog: t5r1-cloud-fix2-run35744916011 rc=0 commit=a0d8921 dirty=no at=2026-09-22T15:24:20Z file=tracks/opendesign-electron-shell/evidence/20260922T152420Z-01-t5r1-cloud-fix2-run35744916011.txt
```
云端红检另两路(不是 runlog 收据,run 在 GitHub 上可查):red-a run 35741688483 FAIL 6、red-b run 35741877114 FAIL 5 —— 照预期红,见 `evidence/20260922-t5r1-cloud-redcheck.md`;
第二~四跑(35728968821 / 35731332274 / 35732054927)的红全是判据,分型见 `evidence/20260922-t4-cloud2-run35728968821.md`。

## Review

- 规格自查(读任何 panel 输出之前先答;正文在仓外自审 `/root/aiwork/tasks/opendesign-electron-shell-t5-review-my-review.md`,派发前落盘):
  业主成功条件 = 换壳后能装能开、过渡不丢东西、以后能自动更新、git-pull 形态不坏;云 Windows 第五跑 FAIL 0 + 本地总跑全绿覆盖**快乐路径**。
  我自己最没把握的是过渡在失败路径上的行为与判据假绿 —— 本轮两条腿抓到的正好落在这里(失败重试 / 装不上时的恢复),规格方向不受影响。
- 腿的花名册(第 1 轮,`/root/aiwork/logs/panel-opendesign-electron-shell-t5-20260922-2200.roster`):
  `subkimi=PASS(verdict=PASS) subcursor.grok-4.7-high=PASS(verdict=PASS)`
- 腿的花名册(第 2 轮,`/root/aiwork/logs/panel-opendesign-electron-shell-t5r2-20260922-2324.roster`):
  `subkimi=PASS(verdict=PASS) subcursor.grok-4.7-high=PASS(verdict=PASS)`
- 反锚定记账:第 1 轮 Kimi 只在 `git diff --stat` 里见到 verify.md 文件名、没打开;Cursor 见到 evidence/*.md 文件名(列目录 / 跨仓 grep / design.md 引用),
  实际打开的只有允许读的 design.md 与云跑 .txt 收据;两腿都没读仓外自审。第 2 轮任务书明确放开 verify.md 与云端对照记录(4b ②,复审核处置表)。
  > panel-review 收尾自己写这个文件(off / FAIL(rc) / 降级 都在里面)。
  > **控制器没活到收尾时它压根不存在** —— 那时跑 `panel-roster <日志前缀>` 从盘上重建,
  > 与控制器自己写的**归一化后一致**(判据 R5b 守着;抬头有渲染时间戳,不是字面逐字节)。**一轮零记录的评审也粘得出这一行**,
  > 所以"那轮被砍了所以没有花名册"不再是理由(2026-08-23,track panel-roster-from-disk)。
  > 08-06 立这条的理由:08-05 我在这里手写了"三条腿一致 PASS",而 Kimi 根本没出结论
  > (同一页第 90 行我自己还写着它没出报告)—— 手抄一份终端上的东西,抄错那次没人会发现。
- 轮次记录(每次派发一行;实质评审与基础设施重试分开,重试不算轮但次数与耗时照记):

  | 轮 | 类型(实质 / 重试) | 派发前 `track preflight` | 日志前缀 | 新增有效阻断 |
  |---|---|---|---|---|
  | 1 | 实质(22:00→22:26,绑定 HEAD 98ecb4d) | rc=3,BLOCK=0 | `/root/aiwork/logs/panel-opendesign-electron-shell-t5-20260922-2200` | 4(两腿都判 PASS;我核实后 4 条归「必须修」) |
  | 2 | 实质(23:24→23:39,绑定 HEAD 4ea5f57;核第 1 轮修复清单) | rc=3,BLOCK=0 | `/root/aiwork/logs/panel-opendesign-electron-shell-t5r2-20260922-2324` | 0 |
  | — | 基础设施重试 | — | 无 | — |

- findings(**先处置、后动手**;一轮一份修复清单,一次修完再复审 —— panel 抽屉 4b):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | R1-1(Cursor 中) | 旧卸载器两次都没卸干净 ⇒ 先 `Delete 卸载.exe` 再弹「请重启后再运行」;重启重试时第 32 行要求卸载器在 ⇒ 过渡整段跳过,新文件叠进留着旧 `ds\`/`python\` 的目录。**我往下挖出更深一层**:旧卸载器先删自启项与 `Software\OpenDesign` 指针再删文件 ⇒ 拒装后重试,开机自启丢失;旧版在 A、新装选 B 时重试找不到 A | 读 `desktop/build/installer.nsh:32-61`;旧卸载段 `git show 6e397b4:installer/OpenDesign.nsi`(先 DeleteRegValue Run / DeleteRegKey 指针,后 RMDir /r) | **必须修** | 过渡(承诺②)每台机器只走一次,提示框自己说「为避免新旧文件混在一起」而重试恰恰混在一起;业主不会收拾这种残局。修:拒装时保留卸载器 + 写回旧卸载器删掉的指针与自启;新云判据 E3c(锁住哨兵 → 第一次拒装 → 解锁 → 不带 /D 重试) |
  | R1-2(Cursor 中;Kimi #5;我自审 M8) | electron-updater `quitAndInstall()` **从不抛**:装不上时 `dispatchError` + 什么都不做;`lifecycle.installUpdate` 只在抛时恢复 ⇒ 后台已收、窗口留着、不提示不重开;main 的 `quitting` 已是 true ⇒ 托盘「退出」被 `quitAll` 第一行吞掉 ⇒ 只能任务管理器强杀 | 读 electron-updater 6.8.9 `out/BaseUpdater.js:13-26,42-67`;`desktop/lib/lifecycle.js:37-47`;`desktop/main.js:145-146,174-179`;mc16 的假件会抛,真库不会 ⇒ **判据假绿** | **必须修** | 考卷假绿(「装失败恢复」是攻题轮定下的接线承诺)。我自审 M8 把后果写成「窗口还在」、判极低 —— 漏了托盘退不掉。修:照真库形状判(交棒期间收到 error 事件即失败 → 恢复) |
  | R1-3(Kimi 低) | 首装时 ds_provision 失败被吞(`Pop $0` 不判) | `installer.nsh:67-68`;旧 `OpenDesign.nsi:301-307` 同位置弹「配置初始化没有成功(错误码)… 第一次打开时它会告诉你还缺什么」,注释「别让它悄悄过去」 | **必须修** | **本次引入的回归**(T3 退役旧判据时这条约束没搬过来)。修:照旧文案弹框,不中止 |
  | R1-4(Cursor 低) | 安装路径含单引号 ⇒ 嵌进 PowerShell 单引号串的 `$INSTDIR`/`$odOldDir` 断句 ⇒ 脚本退出非 0 ⇒ 误报「还在运行,关不掉」,拒装 | `installer.nsh:25,36,53` | **必须修** | **本次引入的回归**:旧安装器不经 PowerShell,这类路径装得上。业主目录无单引号不受影响;别的机器(用户名 O'Brien 默认目录就中)装不上。修:路径经环境变量传,不拼进命令;E3c 的旧目录带单引号 |
  | R1-5(Cursor 低) | 主框架服务端跳转没拦(无 `will-redirect`) | `desktop/main.js` 只挂 will-navigate + setWindowOpenHandler;`bin/ds_web.py` 无任何 30x/Location | 延期 | 业主那边不会发生:主框架只加载本机 ds_web,它不对外跳转;将来 ds_web 若加对外 302,外站会拿到 preload 的窗口按钮与「重启以更新」—— 那时再挂 will-redirect |
  | R1-6(Kimi 中) | `desktop_update.e2e.mjs` 在没配 key 的 HOME 下被 key 卡遮罩挡住 ⇒ 「绿取决于开发机」 | `tests/e2e/run-all.sh:135-155`:总跑给每次建隔离 HOME 并预置假 key(注释写明就是防这个遮罩);Kimi 是单独跑这一个文件 | 驳回 | 总跑是封闭环境,40 PASS 不看开发机脸色;单独跑要自备夹具,总跑缺 gateway 时会把手工命令打印出来 |
  | R1-7(Kimi 低) | 卸载后留下 `%LOCALAPPDATA%\OpenDesign\Electron`(Chromium 缓存) | `desktop/main.js:17`;`deleteAppDataOnUninstall:false` | 延期 | 资料根整体保留是 0.87 起的既定设计(E6 验过);缓存夹子在里面,重装复用,业主看到的只是资料目录里多一个文件夹 |
  | R1-8(Kimi 低 推测;我自审 M4) | 杀进程段信注册表 `InstallDir`,无哨兵 | `installer.nsh:25` | 延期 | 该值只由旧安装器按 /D 写入,业主两台是 `D:\AI\OpenDesign` / `F:\AI\OpenDesign`;要先有人把 HKCU 写坏才会扩大杀伤 |
  | R2-1(两腿 info;我自审「已知不管」) | 交棒时安装包文件在、但**异步** spawn 失败(如被杀软删了)⇒ 同步监听已摘 ⇒ 当成交棒成功、软件退出、安装器没起来 | 读 electron-updater 6.8.9 `NsisUpdater.js:131-141`(spawnLog().catch→dispatchError,异步) | 延期 | 修复前就如此,不是本轮引入。业主那边:点「重启以更新」后软件关了、没弹安装向导;自己再打开一次,更新提示还在 |
  | R2-2(Cursor 低) | C13a 静态判据只要求 Delete 在最后一次哨兵检查之后、不认值 ⇒ 把 Delete 挪进拒装分支 Quit 之前本地仍可能绿 | 读 `tests/test_desktop_config.py` C13a;云 E3c 的 red-b 在「卸载器还在 / 指针 / 自启」上红 | 延期 | 行为由云 E3c 钉住(三路对照两个方向都有牙);静态那道是提早报警,挡不住任意未来写法 = 默认延期 |
  | R2-3(两腿 info) | 点击量具在没有选项的页(卸载页)白等 3 秒 | fix2 收据:卸载两页各 `等页面内容 3000ms` | 驳回 | 只耗时(最多 8 页 × 3s,对 480s 超时可忽略),判定看卸载结果不看这 3 秒 |

  > 只写发现。腿的身份/降级不在这儿抄第二遍:日志自带身份牌(降级横幅 + 视野边界),
  > 花名册在上一格,查工件不查自述。延期 = 留在这里,不自动开新单。
- arbitrated verdict (主裁): **PASS(承诺 ①~④)** —— 两轮两家族(moonshot / xai)均 PASS;第 1 轮 4 条「必须修」我核实成立、判据先红后修,
  云端三路对照(red-a / red-b 照预期红、fix 全绿)证明新判据两个方向有牙;第 2 轮核修复清单 0 新阻断;延期 6 条、驳回 2 条理由写在上表。
  预算 2 轮已用完、无真实阻断 ⇒ 结束评审。承诺 ⑤(业主真机 A0)见下一节。
  > 这里写理由；最终枚举写进 `decision.json.outcome.verdict`。归档时仍为空会被
  > `track-record validate --phase archive` 挡住，`track list` 也会打 ⚠️。

## Accepted deviations

- **承诺 ⑤「业主真机 A0」移交发版单,不在本单里验。** 原因:发版要改版本号(ds_web.VERSION / desktop/package.json)= 改产品文件 ⇒ 本单两轮评审绑定的交付内容作废;
  本仓一向发版单独开单(release-0987 / 0988 / 0989)。发版单的完成标准 = 业主两台真机上运行中的 OpenDesign 回显新版本号 + A0「界面出来了吗」,
  外加发版前补测「所有用户」分支、发布后生产源 smoke、托盘真点清单(design 里的延期项)。影响范围:本单归档不代表业主已经用上新壳。

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:`3508670` 09-21 23:46 → 归档 09-23 00:0x(约 24 小时,含 U1~U4 四次等业主拍板)
- 每轮新增有效阻断:第 1 轮 4 / 第 2 轮 0
- 基础设施等待:重试 0 次;两轮 panel-review duration_ms 求和 2,466,765(≈41 分钟:第 1 轮 1,571,854 / 第 2 轮 894,911)
- 交付后返工:unknown(归档时还没发版)
