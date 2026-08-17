# Verify: opendesign-console-windows

- Date: 2026-08-17
- Verdict: **PASS(代码面)** —— 欠业主真机(那才是这一单唯一的真判官)

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] build passes(`dist 新鲜度` 那一段:重新 build 后 git 无差异)
- [x] tests pass(五段全跑 **0 跳过**,见下面最后一行收据)
- [x] no secrets / unsafe ops(这一单只动子进程创建参数与判据,不碰凭据/网络/写口)

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,把它打印的收据行原样粘进来:

```
runlog -t opendesign-console-windows -- <判据命令>
```

```
runlog: redcheck-console rc=1 commit=ec84897 dirty=yes at=2026-08-17T04:40:29Z file=tracks/opendesign-console-windows/evidence/20260817T044029Z-01-redcheck-console.txt
runlog: redcheck-console-r2 rc=1 commit=ec84897 dirty=yes at=2026-08-17T04:48:32Z file=tracks/opendesign-console-windows/evidence/20260817T044832Z-01-redcheck-console-r2.txt
runlog: redcheck-console-r3 rc=1 commit=ec84897 dirty=yes at=2026-08-17T04:49:05Z file=tracks/opendesign-console-windows/evidence/20260817T044905Z-01-redcheck-console-r3.txt
runlog: greencheck-console rc=0 commit=1504ae9 dirty=yes at=2026-08-17T04:51:18Z file=tracks/opendesign-console-windows/evidence/20260817T045118Z-01-greencheck-console.txt
runlog: mutation-console rc=1 commit=0369475 dirty=yes at=2026-08-17T04:55:10Z file=tracks/opendesign-console-windows/evidence/20260817T045510Z-01-mutation-console.txt
runlog: mutation-console-r2 rc=0 commit=f68e60b dirty=yes at=2026-08-17T05:07:42Z file=tracks/opendesign-console-windows/evidence/20260817T050742Z-01-mutation-console-r2.txt
runlog: redcheck-exempt-mark rc=1 commit=56d54fb dirty=yes at=2026-08-17T05:26:20Z file=tracks/opendesign-console-windows/evidence/20260817T052620Z-01-redcheck-exempt-mark.txt
runlog: mutation-console-r3 rc=0 commit=5e31a4a dirty=yes at=2026-08-17T05:26:51Z file=tracks/opendesign-console-windows/evidence/20260817T052651Z-01-mutation-console-r3.txt
runlog: runall-0.90.0 rc=3 commit=bacc2c1 dirty=yes at=2026-08-17T06:05:17Z file=tracks/opendesign-console-windows/evidence/20260817T060517Z-01-runall-0.90.0.txt
runlog: runall-0.90.0-withgw rc=1 commit=bacc2c1 dirty=yes at=2026-08-17T06:19:03Z file=tracks/opendesign-console-windows/evidence/20260817T061903Z-01-runall-0.90.0-withgw.txt
runlog: redcheck-gate-reach rc=1 commit=bacc2c1 dirty=yes at=2026-08-17T06:36:21Z file=tracks/opendesign-console-windows/evidence/20260817T063621Z-01-redcheck-gate-reach.txt
runlog: greencheck-gate-reach rc=0 commit=67780a7 dirty=yes at=2026-08-17T06:37:06Z file=tracks/opendesign-console-windows/evidence/20260817T063706Z-01-greencheck-gate-reach.txt
runlog: mutation-console-r4 rc=0 commit=cc071cf dirty=yes at=2026-08-17T06:39:50Z file=tracks/opendesign-console-windows/evidence/20260817T063950Z-01-mutation-console-r4.txt
runlog: redcheck-exempt-rules rc=0 commit=4356757 dirty=yes at=2026-08-17T07:31:22Z file=tracks/opendesign-console-windows/evidence/20260817T073122Z-01-redcheck-exempt-rules.txt
runlog: redcheck-exempt-vs-old rc=1 commit=4356757 dirty=yes at=2026-08-17T07:32:22Z file=tracks/opendesign-console-windows/evidence/20260817T073222Z-01-redcheck-exempt-vs-old.txt
runlog: mutation-console-r5 rc=0 commit=c76c612 dirty=yes at=2026-08-17T07:33:04Z file=tracks/opendesign-console-windows/evidence/20260817T073304Z-01-mutation-console-r5.txt
runlog: runall-0.90.0-final rc=0 commit=8cbcd44 dirty=yes at=2026-08-17T07:45:58Z file=tracks/opendesign-console-windows/evidence/20260817T074558Z-01-runall-0.90.0-final.txt
```

> 读法(免得把红收据当事故):
> · `redcheck-*` **rc=1 就是它该有的样子** —— 判据先红才算红检过;
> · `redcheck-exempt-vs-old` 的 rc=1 是**对照组**:同一份红检拿 67780a7 的旧闸跑,
>   旧闸 0 咬 2 漏。没有这一行,"新判据红了"也可能只是它本来就红在别处。
> · `runall-0.90.0` rc=3 / `runall-0.90.0-withgw` rc=1 是**作废重跑前的两遍**,按 5b 不藏:
>   前者 2 条 e2e 整块 SKIP(本机 gateway 配置 08-15 被写成了 Windows 形状,已记 backlog),
>   后者是补起 gateway 后 `chat_reconnect` 的 ㉜ 红了一次 —— 随后 2 批量 + 2 单跑全绿,
>   **没有改它、没有放宽预算**,当天的账记在 docs/backlog.md。
> · 最后一行 `runall-0.90.0-final rc=0 @8cbcd44` 是**在最终代码上**跑的那一遍。

## Review

- lane: **fast**(主 + 1 腿)
  > 硬规矩逐条对过:**没碰**新写口 / 权限 / auth / 钱 / 数据一致性 —— 改的是子进程
  > **创建参数**,不是它们能写什么。所以硬规矩不强制 full。
  >
  > 不降到 self 的理由:它动的是外壳收尸那条命脉的邻居(`spawn_kwargs` 同时管着
  > POSIX 的 `start_new_session`,那一位没了就是"孙进程收不干净"),不是纯观感。
  >
  > 不升 full 的理由(说清楚,免得下次照抄):**这个 bug 两轮 full 四审都没人提过一句** ——
  > 0.89.0 的 13 条发现里没有任何一条是"你的子进程会弹控制台窗口"。
  > 这条轴上 panel 的实测收益接近零,而**真正的判官是业主的机器**。
  > ⇒ 省下来的注意力放在真机清单上,不是放在第四条腿上。
- 派给: **主 agent 直接干** —— 按 delegate 抽屉的分档表,这是"小而明显的活"
  (一个纯函数 + 两个调用点改成用它;判据我自己写)。切碎派出去、写任务书、
  过三道闸的成本高于自己动手。判卷不起服务。
  ⚠️ 这条理由**只对这一单成立**,别当默认值抄(07-31 教训:自述型字段挡不住惯性)。
- 规格自查(读任何 panel 输出之前先答):

  **如果规格本身错了,会错成什么样?** 这一单的规格是一句可证伪的话:
  「业主打开软件,一个黑窗口都不许有」。它错不到哪儿去 —— 业主已经亲眼看见、
  亲手关掉过。**真正的风险在"我以为的根因是不是真根因"**:
  我断定是 `CREATE_NO_WINDOW` 缺失,但这一层 Linux 上**一条判据也证不了** ——
  上面所有闸问的都是"标志有没有传对",不是"Windows 有没有听我的"。
  **如果真因另有其人(比如 pywebview 起 webview 时自己带了控制台),
  业主装完 0.90.0 会看见一模一样的两个黑窗口,而我这一单全绿。**
  ⇒ 真机清单第一条就是它,红了就回来重新找根因,别在判据上加戏。

  第二条风险:`spawn_kwargs` 把两个平台的参数并成一个函数,
  **POSIX 那半边是回归面** —— 那一位丢了,收尸就收不干净(c1/c2/c13 咬的正是它),
  而这类坏法在 Linux 上是跑得出来的,所以本机回归对它有效。
- 腿的花名册(原样粘自 `/root/aiwork/logs/panel-console-r2-20260817-145238.roster`):
  `submimo=PASS subdeepseek=PASS subglm=off subkimi=PASS`
  > panel-review 收尾自己写这个文件(off / FAIL(rc) / 降级 都在里面)。
  > 08-06 立这条的理由:08-05 我在这里手写了"三条腿一致 PASS",而 Kimi 根本没出结论
  > (同一页第 90 行我自己还写着它没出报告)—— 手抄一份终端上的东西,抄错那次没人会发现。
- **lane 实际执行:full(派了全部腿,3 条出结论)** —— 上面那段"不升 full 的理由"
  写于开工时,派发前我改了主意并照 full 派了。理由:这一单最大的风险是
  **"根因判错了而我全绿"**(S1),那正是多个模型家族能帮上忙的轴 ——
  它不是"多跑一遍测试",是"有没有别的东西也会弹那两个窗口"。
  **事后看这个改主意是对的**:三条腿里最值钱的一条(subdeepseek 的 BLOCK)
  抓的正是我自己漏掉的一条真红。留着原文不删,免得下次照抄一个"当时没执行的理由"。
- findings(逐条对代码验过才写进来;`—— 驳回` 的也留着):

  **F1 [BLOCK,已修] 搬运保真闸的基线过期,HEAD 上 `test_structure_moves` 是红的。**
  subdeepseek 孤腿命中。**我亲跑证实,而且比它说的多一条**:它点名 `_open_windows`,
  实测 `_default_open_launcher` 也红(我改豁免措辞时又碰了一次)。
  病根是我自己那条教训 **「我给的绿是过期的」**:最后一份总跑收据停在 `bacc2c1`,
  而 `cc071cf` 之后没人再跑过。⇒ `655038c` 先证明"只加注释"再重设两条基线。

  **F2 [MEDIUM,已修] 闸问的是"它的邻居",不是"这次调用"。三条腿独立命中。**
  老实现查"包住它的 def 里出现过 `spawn_kwargs` 吗" ⇒ 同一函数里再插一个裸调用
  就白拿豁免;模块级调用点拿到整段文件头、永远绿。⇒ `c76c612` 改用 `ast`,
  问"这次调用的实参"+"`**名字` 在本函数里被谁喂过";M21 咬住这一形态。

  **F3 [MEDIUM,已修] 判据自己在撒谎:"豁免必须给理由",实际不给也放行。**
  subkimi 单独命中。`near` 窗口里标记之后还有下一行代码,`.strip()` 当然非空。
  连同"豁免会串到 3 行内的隔壁调用点"一起修(只认自己那行 / 紧贴其上的连续注释块)。
  一次性红检 `tests/redcheck-exempt-window.sh`:新闸 2 咬 0 漏、旧闸 0 咬 2 漏。

  **F4 [LOW,已修] BLIND_FORMS 漏了 `subprocess.getoutput/getstatusoutput`。**
  两条腿独立命中。它**长得像自己人**(带 `subprocess.` 前缀),却不在闸① 认的五个
  函数名里 ⇒ 掉进两道闸中间的缝。一并补了 `asyncio.create_subprocess_*`、`os.exec*`。

  **F5 [INFO,不修,已进真机清单 B4] 这一单把腿从"有控制台"变成"没有控制台"。**
  deepseek/kimi 都点了:翻面是腿自己起的孙进程以前能挂在已有控制台上,现在没得挂,
  谁没带参数就**新开一扇**。启动期判据/清单盯得住(B1/B2),会话中途只有业主看得见。

  **F6 [LOW,不修] 豁免理由只验非空,写一句废话也能过 —— 保留,这是取舍不是漏。**
  机器判不了"理由对不对";强度在"必须写在调用点旁边、必须被人看见"。
  已写在闸的自述里,不当成比它强的东西卖。

  **F7 [驳回] submimo 说 `os.exec*` 不该进 BLIND_FORMS("它是替换不是起进程")。**
  —— 在 POSIX 上对,在 Windows 上不对:那儿没有真正的 exec 语义,CPython 用起新进程
  实现,无控制台父进程照样会招来一扇窗。kimi 的判断对,采纳它的。
  **两条腿意见相反时,以我自己查证的为准。**
  > 只写发现。腿的身份/降级不在这儿抄第二遍:日志自带身份牌(降级横幅 + 视野边界),
  > 花名册在上一格,查工件不查自述。
- arbitrated verdict (主裁): **PASS(代码面),欠业主真机。**
  三条腿的 12 条发现我逐条对着代码验过:1 条真红(F1)已修、3 条闸精度洞(F2/F3/F4)已修、
  1 条驳回(F7)、其余是取舍或真机项。**没有一条是"多数说没事所以放过"。**
  仍然成立的是我开工时就写下的 S1:**本机所有判据问的都是"标志有没有传对",
  答不了"Windows 有没有听我的"** —— 真机 B 组红了就回来重新找根因,别在判据上加戏。
  > **归档时这一条和顶部的 `Verdict:` 都不许还是占位符**,`track-guard` 规矩3 会挡;
  > 没归档但已经合并上线的,`track list` 会打 ⚠️(stage-timer 就这么漏了两个月)。

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>
