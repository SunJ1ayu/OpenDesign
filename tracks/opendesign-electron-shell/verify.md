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
<粘收据行,逐字节,别改数。**每次提交**都会跟 evidence/ 里的收据逐字节比对(5a);
 **归档时**还要求:最后跑的那一遍必须在这儿、跑红的那几遍一份都不许藏(5b)、
 收据得进 git(5d)。一份收据都没有的话,写一行
 「- 无机器证据:<理由>」认账 —— 沉默不算理由(5c)。>
```

## Review

- 规格自查(读任何 panel 输出之前先答;正文在仓外自审 `/root/aiwork/tasks/opendesign-electron-shell-t5-review-my-review.md`,派发前落盘):
  业主成功条件 = 换壳后能装能开、过渡不丢东西、以后能自动更新、git-pull 形态不坏;云 Windows 第五跑 FAIL 0 + 本地总跑全绿覆盖**快乐路径**。
  我自己最没把握的是过渡在失败路径上的行为与判据假绿 —— 本轮两条腿抓到的正好落在这里(失败重试 / 装不上时的恢复),规格方向不受影响。
- 腿的花名册(第 1 轮,`/root/aiwork/logs/panel-opendesign-electron-shell-t5-20260922-2200.roster`):
  `subkimi=PASS(verdict=PASS) subcursor.grok-4.7-high=PASS(verdict=PASS)`
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

  > 只写发现。腿的身份/降级不在这儿抄第二遍:日志自带身份牌(降级横幅 + 视野边界),
  > 花名册在上一格,查工件不查自述。延期 = 留在这里,不自动开新单。
- arbitrated verdict (主裁): <...>
  > 这里写理由；最终枚举写进 `decision.json.outcome.verdict`。归档时仍为空会被
  > `track-record validate --phase archive` 挡住，`track list` 也会打 ⚠️。

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:<开工 commit 时刻 → 归档 commit 时刻>
- 每轮新增有效阻断:<第 1 轮 n / 第 2 轮 n>
- 基础设施等待:<重试次数;observations 里 panel-review 的 duration_ms 求和>
- 交付后返工:<归档后因本单再改过几次;不知道写 unknown>
