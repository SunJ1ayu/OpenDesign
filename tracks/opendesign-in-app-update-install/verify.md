# Verify: opendesign-in-app-update-install

- Date: 2026-09-08

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再按 impact-risk 预算跑 panel-review；只有特殊控制面
> 才显式 `--all` 做全池评审。最后仍由主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] tests pass(段① + 接线两块;全仓总跑见下)
- [x] no secrets / unsafe ops(判据一次真网都不打,下载/装/问 health 全走注入替身)
- [x] 全仓总跑 `tests/run-all.sh --with-gateway`(**收口时跑,收据要是最后一次编辑之后那一遍**)—— 09-15 `final-run-all-with-gateway`(commit 0595b85,代码此后未动)

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,收据行原样粘在这里:

```
runlog: red-t4-t18-update-apply rc=1 commit=4b4e683 dirty=yes at=2026-09-08T12:30:02Z file=tracks/opendesign-in-app-update-install/evidence/20260908T123002Z-01-red-t4-t18-update-apply.txt
# 判据先行,30 failed(bin/ds_update_apply.py 还不存在)

runlog: green-t4-t18-update-apply rc=0 commit=856f3fb dirty=yes at=2026-09-08T12:45:26Z file=tracks/opendesign-in-app-update-install/evidence/20260908T124526Z-01-green-t4-t18-update-apply.txt
# 30 passed / 6 subtests passed

runlog: redcheck-update-apply-19bites rc=0 commit=856f3fb dirty=yes at=2026-09-08T12:45:31Z file=tracks/opendesign-in-app-update-install/evidence/20260908T124531Z-01-redcheck-update-apply-19bites.txt
# 咬住 19 / 漏网 0(含反误报对照组 c1)

runlog: red-t19-t20-flag-and-nonce rc=1 commit=c7910f2 dirty=yes at=2026-09-08T12:46:57Z file=tracks/opendesign-in-app-update-install/evidence/20260908T124657Z-01-red-t19-t20-flag-and-nonce.txt
# 判据先行,3 failed / 39 passed(红的是 t19a、t20b、t20c)

runlog: green-t19-t20-flag-and-nonce rc=0 commit=f77699b dirty=yes at=2026-09-08T12:51:14Z file=tracks/opendesign-in-app-update-install/evidence/20260908T125114Z-01-green-t19-t20-flag-and-nonce.txt
# 42 passed / 10 subtests passed

runlog: redcheck-t19-t20-24bites rc=0 commit=f77699b dirty=yes at=2026-09-08T12:51:24Z file=tracks/opendesign-in-app-update-install/evidence/20260908T125124Z-01-redcheck-t19-t20-24bites.txt
# update-apply 咬 24 / 漏 0;ds-web 咬 9 / 漏 0
```

### 接线那一段(t21 / t22 / t23 / m1~m4 / w8~w9)

```
runlog: red-t21-t22-m-w-wiring rc=1 commit=fefa008 dirty=yes at=2026-09-08T13:21:00Z file=tracks/opendesign-in-app-update-install/evidence/20260908T132100Z-01-red-t21-t22-m-w-wiring.txt
runlog: green-t21-m-w-endpoint-still-red rc=0 commit=5c5398a dirty=yes at=2026-09-08T13:26:21Z file=tracks/opendesign-in-app-update-install/evidence/20260908T132621Z-01-green-t21-m-w-endpoint-still-red.txt
runlog: red-t23-where-new-tree-goes rc=1 commit=c1bf217 dirty=yes at=2026-09-08T13:27:41Z file=tracks/opendesign-in-app-update-install/evidence/20260908T132741Z-01-red-t23-where-new-tree-goes.txt
runlog: green-t22-t23-endpoint rc=0 commit=34e23a4 dirty=yes at=2026-09-08T13:34:41Z file=tracks/opendesign-in-app-update-install/evidence/20260908T133441Z-01-green-t22-t23-endpoint.txt
runlog: redcheck-handoff-chain-final rc=1 commit=beb0eae dirty=no at=2026-09-08T14:05:34Z file=tracks/opendesign-in-app-update-install/evidence/20260908T140534Z-01-redcheck-handoff-chain-final.txt
```

🔴 **最后那一行 rc=1,不是我这一单的判据红了**,而是 `mutation-shell-restart.sh`
里有**两条陈年变异是坏的**(M9 红在别处、M10 锚点在 2026-08-17 c22 改动后就失效了),
它们让整支脚本永远以 rc=1 收场。**这一单自己的 27 条全部如期咬红、0 条漏网**,
被测文件 4 个哈希逐字节还回。两条陈年账已开在 `docs/backlog.md`,
**没有顺手修** —— 改红检的锚点要真懂被测那段逻辑,而那是别的 track 的活;
顺手修一个自己没读懂的闸,正是闸被悄悄改弱的方式。

⚠️ 这一轮红检**咬出过我自己判据的一个洞**(U5 漏网):t22a~t22g 把整座桥换成了
替身,于是桥内部那句"只有点名了动词才算成功"**从来没被执行过** ——
我把最要紧的那条纪律藏在了替身后面。补了 t22h~t22k 直接考那个纯函数,
定点复验:同一条变异现在一次咬红三条。

### 界面「更新」按钮(u27~u37;实现派给了 codex)

```
runlog: red-u27-u33-update-button rc=1 commit=090834c dirty=yes at=2026-09-08T14:28:30Z file=tracks/opendesign-in-app-update-install/evidence/20260908T142830Z-01-red-u27-u33-update-button.txt
runlog: red-u27-u37-after-attack rc=1 commit=bc13218 dirty=yes at=2026-09-08T14:41:43Z file=tracks/opendesign-in-app-update-install/evidence/20260908T144143Z-01-red-u27-u37-after-attack.txt
runlog: red-u35b-canapply-white-screen rc=1 commit=b05d85a dirty=yes at=2026-09-08T14:56:13Z file=tracks/opendesign-in-app-update-install/evidence/20260908T145613Z-01-red-u35b-canapply-white-screen.txt
runlog: green-u27-u37-button-done rc=0 commit=d81ac14 dirty=yes at=2026-09-08T14:57:33Z file=tracks/opendesign-in-app-update-install/evidence/20260908T145733Z-01-green-u27-u37-button-done.txt
```

**这一段的顺序是:考卷 → 攻题 → 改考卷 → 派活 → 收货三闸 → 闸③抓到洞 → 判据先行 → 修。**

- **攻题(派活之前)**:`gpt-5.6-sol` 只读腿,记录在仓外
  `/root/aiwork/tasks/update-button-attack.md`。它报 13 条,**打穿我 4 条断言**
  (u29/u30/u31/u33 全是"黑名单只挡我想得到的词"),外加一个我写错的产品事实:
  🔴 **`started` 不等于"更新完成"** —— 端点只证明接力起来了、外壳认了收摊,
  后面的改名和拉起仍可能失败。还指出一条我完全没想到的时序:
  **"软件会自己关掉"必须在点下去那一刻就说**,因为成功响应到浏览器时窗口可能已经在关了
  (u31 只证明那句话写对了,证明不了它上过屏)⇒ 新增 u34。
- **收货三闸**:闸① 判卷逐字节没动过、判卷路径下没多出文件;闸② 我亲跑 38/38,
  集成后又重跑一遍(worktree 的绿不复用);闸③ 三个文件逐行读。
- 🔴 **闸③ 抓到判据没覆盖的白屏路径**(实测复现,不是推论):`canApply` 在
  `name`/`url` 为 `null` 时抛 TypeError,而它在 Sidebar 渲染体里调用 ⇒ 卸整棵树 ⇒ 整页白。
  够得着真实数据(后端 `asset.get(...)` 取不到就是 None)。
  **这是我考卷的洞,不是腿的锅** —— u35 只喂了"字段在但为空"。已补 u35b/u35c 后修。

⚠️ 一条我自己抓自己的:`5332aa2` 的提交信息第一版把收据行写成了
`commit=RUNLOG_PLACEHOLDER`(收据是 runlog 跑完才打印的,而我把提交信息写死在前面)。
已 amend。**track-guard 只查 verify.md,查不到 commit 信息** —— 没人拦得住这句假话。

**没走 runlog 的两项,在这里认账**(5c:沉默不算理由):

- `installer/check-installer.py static`:合计 23 条、0 条不合格。裸跑的。
  安装器在本机跑不了,这道静态闸是它唯一的机器意见 —— 收口时补一份 runlog 收据。
- 全仓 python 段(`tests/dead_assertions.py`)裸跑过两遍,两遍都记在这儿:
  - 第一遍 `Ran 1505 tests in 469.365s` → **FAILED(failures=1)**,咬出黑窗口那个真 bug
    (`ds_update_apply.py:206` 没走 `spawn_kwargs()`),外加 1 条死断言。**两条都已修。**
  - 第二遍(修完之后)`Ran 1512 tests in 471.312s` → **OK**;死断言闸
    「扫了 64 个判据文件、3581 条断言;✅ 没有从没跑过的断言」。
    条数 1505→1512 正好是本轮新增的 7 条(t19 四条 + t20 三条),对得上。
  ⚠️ **这两笔都不是"最终收据"**:裸跑的、而且 §2/§3 还要再动代码。
  收口时连同 `run-all.sh --with-gateway` 一起走 runlog,且必须是**最后一次编辑之后**那一遍。

  ⚠️ 顺带记一条量具的坑(2026-09-08,当场发现):我用
  `pgrep -f "python tests/dead_assertions.py"` 去看它跑完没,**那句话匹配到了监视脚本自己**
  ——读到的 15:43 是监视器的年龄,不是测试的(测试当时才跑了 3 分钟),
  我差点据此判它"挂住了"。同一个自匹配还让那个 `until` 循环**永远退不出去**。
  改用 PID(`kill -0`)。**`pkill -f` 自杀的老坑,这次换了张脸又来了一遍。**

### §3 Windows 端到端(e1~e5)—— 2026-09-14 晚,六趟真跑

收据行从证据文件末行机器提取,不是手抄:

```
runlog: harness-selftest-and-mutation rc=0 commit=eea4521 dirty=yes at=2026-09-14T13:21:58Z file=tracks/opendesign-in-app-update-install/evidence/20260914T132158Z-01-harness-selftest-and-mutation.txt
runlog: red-t25-t26-relay-empty-and-pointers-repointed rc=1 commit=99d97b9 dirty=yes at=2026-09-14T13:48:32Z file=tracks/opendesign-in-app-update-install/evidence/20260914T134832Z-01-red-t25-t26-relay-empty-and-pointers-repointed.txt
runlog: harness-selftest-and-mutation-round2 rc=0 commit=99d97b9 dirty=yes at=2026-09-14T13:48:32Z file=tracks/opendesign-in-app-update-install/evidence/20260914T134832Z-02-harness-selftest-and-mutation-round2.txt
runlog: green-t25-t26 rc=0 commit=7e5efbd dirty=yes at=2026-09-14T13:50:56Z file=tracks/opendesign-in-app-update-install/evidence/20260914T135056Z-01-green-t25-t26.txt
runlog: red-t27-relay-dies-with-the-job rc=1 commit=6209044 dirty=yes at=2026-09-14T14:24:04Z file=tracks/opendesign-in-app-update-install/evidence/20260914T142404Z-01-red-t27-relay-dies-with-the-job.txt
runlog: harness-selftest-and-mutation-round3 rc=0 commit=6209044 dirty=yes at=2026-09-14T14:24:05Z file=tracks/opendesign-in-app-update-install/evidence/20260914T142405Z-01-harness-selftest-and-mutation-round3.txt
runlog: green-t27 rc=0 commit=d76bca4 dirty=yes at=2026-09-14T14:28:09Z file=tracks/opendesign-in-app-update-install/evidence/20260914T142809Z-01-green-t27.txt
runlog: red-t28-gate-40ms-and-no-way-back rc=1 commit=86dce8e dirty=yes at=2026-09-14T15:03:53Z file=tracks/opendesign-in-app-update-install/evidence/20260914T150353Z-01-red-t28-gate-40ms-and-no-way-back.txt
runlog: red-t28-ignores-comment-lines rc=1 commit=ba605d5 dirty=yes at=2026-09-14T15:06:28Z file=tracks/opendesign-in-app-update-install/evidence/20260914T150628Z-01-red-t28-ignores-comment-lines.txt
runlog: green-t28-and-full-mutation rc=0 commit=0ad89cb dirty=yes at=2026-09-14T15:09:14Z file=tracks/opendesign-in-app-update-install/evidence/20260914T150914Z-01-green-t28-and-full-mutation.txt
runlog: red-t29-relay-cwd-inside-live rc=1 commit=34cde42 dirty=yes at=2026-09-14T15:32:39Z file=tracks/opendesign-in-app-update-install/evidence/20260914T153239Z-01-red-t29-relay-cwd-inside-live.txt
runlog: harness-selftest-and-mutation-round5 rc=0 commit=34cde42 dirty=yes at=2026-09-14T15:32:39Z file=tracks/opendesign-in-app-update-install/evidence/20260914T153239Z-02-harness-selftest-and-mutation-round5.txt
runlog: green-t29-and-full-mutation rc=0 commit=4a07db7 dirty=yes at=2026-09-14T15:33:38Z file=tracks/opendesign-in-app-update-install/evidence/20260914T153338Z-01-green-t29-and-full-mutation.txt
runlog: red-z2-wait-relay-chain-broken rc=1 commit=004ae80 dirty=yes at=2026-09-14T15:57:11Z file=tracks/opendesign-in-app-update-install/evidence/20260914T155711Z-01-red-z2-wait-relay-chain-broken.txt
runlog: harness-selftest-and-mutation-round6 rc=0 commit=004ae80 dirty=yes at=2026-09-14T15:57:11Z file=tracks/opendesign-in-app-update-install/evidence/20260914T155711Z-02-harness-selftest-and-mutation-round6.txt
runlog: judge-fix-dead-t24b-and-leak rc=0 commit=32b4f47 dirty=yes at=2026-09-14T16:16:26Z file=tracks/opendesign-in-app-update-install/evidence/20260914T161626Z-01-judge-fix-dead-t24b-and-leak.txt
runlog: windows-e2e-run6-facts-rejudged-locally rc=0 commit=7d963e2 dirty=yes at=2026-09-14T16:17:48Z file=tracks/opendesign-in-app-update-install/evidence/20260914T161748Z-01-windows-e2e-run6-facts-rejudged-locally.txt
```

**六趟 Windows 真跑**(workflow `windows-update-e2e.yml`,推 `ci-update/e2e-N` 触发;事实在 pwsh 采、判定在 python 下):

| 趟 | run | 结果 | 这一趟照出来什么 |
|---|---|---|---|
| 1 | 34848924198 | e2 ✅,其余 ❌/崩 | 🔴 **t25** 盘上接力脚本变量全空(apply_update 只传了 plan);🔴 **t26** 更新档把 InstallDir/卸载/快捷方式写成 .new;考卷病:死端口扫描 42 秒、重装不带 /D= |
| 2 | 34851863087 | 全 ❌ | t25/t26 真机生效;🔴 **t27** 接力脚本在 ds-web 的 KILL_ON_JOB_CLOSE Job 里,收摊 1 秒内被杀;量具病:WScript.Shell 读不出中文 .lnk |
| 3 | 34855947275 | e2 e3 ✅ | t27 真机生效;🔴 **t28** 收摊闸 40 毫秒放行、外壳没退完 ⇒ 改名失败 ⇒ 关了不回来 |
| 4 | 34860373658 | e2 e3 ✅,**e4 假绿** | 🔴 **t29** 启动器 SetOutPath 活树 ⇒ 接力脚本自己占着活树;e4 走的是"放弃"不是"回滚",终态一样被放过 ⇒ 考卷补 old_seen |
| 5 | 34863116162 | 全 ❌(考卷坏) | 接力脚本日志第一次「更新成功,已切到 0.98.900」;全红是我插 old_seen 那行拆断了 pwsh 的 if/elseif 链 ⇒ 结构钉 z2 |
| 6 | **34865587921** | **五个全 ✅** | 产品代码同第五趟,只换考卷 |

**第六趟我亲读的**(不只看收据绿;事实与接力脚本日志已复制进 `evidence/windows-e2e-run-34865587921/`,本机同一判定器复判五份全 OK,收据见上最后一行):

- e1:接力脚本 12 秒;`.old` 出现过又被清掉;在答的是 0.98.900;活树版本号文件 0.98.900;`.new` 没了;
  注册表 InstallDir、三个快捷方式都指活树;档案标记 4 份逐字节不变;窗口是 `pythonw` 的 WinForms 类(不是报错框)。
  截图亲眼看过:界面正常渲染(侧栏 + 首次使用的填 key 对话框,CI 上没 key 是对的形状),不是白屏。
- e4:`.old` 出现过(第一次改名真做成了)⇒ 第二次改名失败 ⇒ 1 秒内回滚,旧版被接力脚本拉起。
- e5:坏新版真的起来过(答过 0.0.1)⇒ 约 2 分钟收口超时 ⇒ 回滚,旧版在答,**没有旧树塞进活树**。
- e3:收摊闸等满 ~60 秒放弃,`.new` 删掉,活树没动。

**这一轮我自己犯的错**(都已修,如实记):
1. 写 t28 实现时为让 t28c 过,在停进程命令尾巴硬塞 `%LIVE%`(判据绿、真跑会坏);亲读生成物才发现,没提交就改掉。
2. t28 判据不认注释行(`rem ... GEQ ...` 能骗过)⇒ 补强 `4650fdb`。
3. 一份红检收据用 `| tail -12` 截断,藏掉了自 09-08 就 [BAD] 的 m14 ⇒ 重跑留完整输出;顺带修 m14/m22/m26 三个靶子。
4. 第五趟那行 old_seen 拆断 if/elseif(见上表)。
5. 一个提交信息里的收据行写成了占位符(`4650fdb` amend 之前)—— 和 09-08 那次同一种病,track-guard 查不到 commit 信息。

**全仓总跑(本地,非最终)**:node 416 / MCP 三闸 / dist 新鲜度 / e2e 39 PASS 2 SKIP 全绿;python 1583 OK 但死断言闸咬出
t24b 自 09-08 起没执行过 + 泄漏闸咬出我 e2e 判据漏 5 个目录 ⇒ 都修了(`7d963e2`)。最终那一遍放到收口、最后一次编辑之后。

**偶发,待查**:`test_ds_shell_core.LockScanCost.l1`(锁扫描并发耗时)在一次组合跑里 ERROR 一次,单跑与重跑两遍都绿。计时断言,本机 2G 内存。

**这些 CI 覆盖不了、只有业主真机答得了**:杀软(可能秒删下回来的 exe)、他家的网速(43MB)、VPN;中文 Windows 上接力脚本的 GBK 日志(runner 是英文,
日志文件名乱码但不影响判定)。

**记下的小尾巴(不影响打开和使用,进 Accepted deviations)**:回滚后「设置 → 应用」里的版本号显示新版的号;
回滚后 `.new`(~150MB)留在盘上,下次更新会先删;e3 那种"一直有东西占着活树"时接力脚本会尝试打开旧版,但占着的东西不放手时旧版也起不来。

### 09-15 收口(断线接手):t30b / t33~t40 / e6·e7 / 最终总跑

过程、每条发现的来源与仲裁见下方 `## Review` 的「收口外审 —— 2026-09-15」。收据按时间序,**原样取自各收据文件末行**:

```
runlog: red-t33-t36-panel-findings rc=1 commit=05d0fd5 dirty=yes at=2026-09-15T01:34:32Z file=tracks/opendesign-in-app-update-install/evidence/20260915T013432Z-01-red-t33-t36-panel-findings.txt
# 判据先行 12 红(t33a×2 t34a t35a t36a×8);反面 t33z/t35b/t36b 本就绿
runlog: green-t33-t36 rc=0 commit=89ac2b5 dirty=yes at=2026-09-15T01:43:12Z file=tracks/opendesign-in-app-update-install/evidence/20260915T014312Z-01-green-t33-t36.txt
# 修后 133 OK
runlog: red-t30b-proxy-read-once rc=1 commit=e968e04 dirty=yes at=2026-09-15T01:44:24Z file=tracks/opendesign-in-app-update-install/evidence/20260915T014424Z-01-red-t30b-proxy-read-once.txt
# t30b 红 + g1→t30a 顺序依赖复现
runlog: green-t30b-and-combined rc=0 commit=ffff3c2 dirty=yes at=2026-09-15T01:45:04Z file=tracks/opendesign-in-app-update-install/evidence/20260915T014504Z-01-green-t30b-and-combined.txt
# 相关考卷合跑 278 OK(基线 05d0fd5 同命令 ERROR 1);两个顺序各 3 OK
runlog: redcheck-t30b-t33-t36-and-t34a-tighten rc=0 commit=d6312c3 dirty=yes at=2026-09-15T01:47:49Z file=tracks/opendesign-in-app-update-install/evidence/20260915T014749Z-01-redcheck-t30b-t33-t36-and-t34a-tighten.txt
# ⚠️ rc=0 是 bash -c 末条的 rc:内含 update_apply 44/2(m20、m33 [BAD] 锚点漂移)、ds_web 13/0
runlog: redcheck-update-apply-after-anchor-sync rc=0 commit=d6312c3 dirty=yes at=2026-09-15T01:52:36Z file=tracks/opendesign-in-app-update-install/evidence/20260915T015236Z-01-redcheck-update-apply-after-anchor-sync.txt
# 锚点同步后 46/0
runlog: red-t37-t40-slice-findings rc=1 commit=49fde81 dirty=yes at=2026-09-15T02:03:33Z file=tracks/opendesign-in-app-update-install/evidence/20260915T020333Z-01-red-t37-t40-slice-findings.txt
# 判据先行 7 失败 4 错误;反面 t37c/t40b 本就绿
runlog: green-t37-t40 rc=0 commit=e2bf8d5 dirty=yes at=2026-09-15T02:06:02Z file=tracks/opendesign-in-app-update-install/evidence/20260915T020602Z-01-green-t37-t40.txt
# 相关考卷合跑 288 OK;安装器静态闸 17/0
runlog: redcheck-t37-t40-and-direction rc=1 commit=350fef1 dirty=yes at=2026-09-15T02:08:15Z file=tracks/opendesign-in-app-update-install/evidence/20260915T020815Z-01-redcheck-t37-t40-and-direction.txt
# 57/1:m46~m57 全咬住;m8 [BAD](锚点正是 t37 改掉的那行)
runlog: redcheck-update-apply-after-m8-sync rc=0 commit=350fef1 dirty=yes at=2026-09-15T02:11:54Z file=tracks/opendesign-in-app-update-install/evidence/20260915T021154Z-01-redcheck-update-apply-after-m8-sync.txt
# 58/0
runlog: redcheck-e2e-harness-e6-e7 rc=0 commit=350fef1 dirty=yes at=2026-09-15T02:14:26Z file=tracks/opendesign-in-app-update-install/evidence/20260915T021426Z-01-redcheck-e2e-harness-e6-e7.txt
# e2e 考卷红检 28/28
runlog: green-e2e-harness-e6-e7 rc=0 commit=350fef1 dirty=yes at=2026-09-15T02:15:05Z file=tracks/opendesign-in-app-update-install/evidence/20260915T021505Z-01-green-e2e-harness-e6-e7.txt
# e2e 考卷搭子 25 OK
runlog: run-all-after-t37-t40-and-e6-e7 rc=1 commit=eaec8f0 dirty=no final=yes at=2026-09-15T02:17:14Z file=tracks/opendesign-in-app-update-install/evidence/20260915T021714Z-01-run-all-after-t37-t40-and-e6-e7.txt
# 🔴 e2e 段 39/0/2SKIP 但泄漏闸 1 个空前缀残留(形状同 org.chromium.Chromium.*);复现探针 0 残留,判为 e2e 考卷时有时无的卫生问题,未改判据
runlog: windows-e2e-run8-and-prefix-rejudged-locally rc=0 commit=eaec8f0 dirty=yes at=2026-09-15T02:37:17Z file=tracks/opendesign-in-app-update-install/evidence/20260915T023717Z-01-windows-e2e-run8-and-prefix-rejudged-locally.txt
# 修后 run 34920544736 e1~e7 OK;修前对照 run 34920544526 e6/e7 FAIL;本机复判一致
runlog: final-run-all-with-gateway rc=0 commit=0595b85 dirty=yes final=yes at=2026-09-15T02:55:39Z file=tracks/opendesign-in-app-update-install/evidence/20260915T025539Z-01-final-run-all-with-gateway.txt
# ✅ 最终:6 段全绿,e2e 含 gateway 41/0/0;source-stable yes(dirty 仅外审观测 json)
```

Windows 端到端第八趟:修后 https://github.com/SunJ1ayu/OpenDesign/actions/runs/34920544736(e1~e7 全绿,我亲读 e6/e7 事实、
e6 接力脚本日志与 20 秒截图);修前对照 https://github.com/SunJ1ayu/OpenDesign/actions/runs/34920544526(e6 活树版本号被改成 0.98.900
而在答的是 0.98.4;e7 rc=0、活树 4 个文件被覆盖)。原始事实在 `evidence/windows-e2e-run-3492054*/`。

## 上一轮(判据先行之前)的收据

⚠️ 这四行 2026-09-08 21:0x **从证据文件末行逐字节取的,不是手抄**。
我第一次写这一段时把它们缩成了 `... 文件名`,`track-guard` 规矩 5a 当场挡下 ——
它防的正是这种"顺手四舍五入",而我确实顺手了。

```
runlog: red-u23-u25-notes-setext rc=1 commit=f194983 dirty=yes at=2026-09-08T11:03:26Z file=tracks/opendesign-in-app-update-install/evidence/20260908T110326Z-01-red-u23-u25-notes-setext.txt
runlog: green-notes-setext-fix rc=0 commit=f194983 dirty=yes at=2026-09-08T11:08:38Z file=tracks/opendesign-in-app-update-install/evidence/20260908T110838Z-01-green-notes-setext-fix.txt
runlog: green-notes-setext-fix-with-u26 rc=0 commit=8a0906b dirty=yes at=2026-09-08T11:30:07Z file=tracks/opendesign-in-app-update-install/evidence/20260908T113007Z-01-green-notes-setext-fix-with-u26.txt
runlog: green-t12-asset-name-contract rc=0 commit=47e2320 dirty=yes at=2026-09-08T11:30:39Z file=tracks/opendesign-in-app-update-install/evidence/20260908T113039Z-01-green-t12-asset-name-contract.txt
```

## Review

- 规格自查(读任何 panel 输出之前先答,**本轮已答,panel 还没跑**):

  **规格错了会错成什么样?** 最像绿其实错的那条:更新"成功"了 —— 版本号对、窗口在 ——
  而业主的档案没了。`t13` 就是为它存在的,而且它必须比对**真实文件内容**,不是"目录还在"。

  **我怎么发现?** 这一轮已经发现三处规格级的错,全不是我自审出来的:
  ① design 正文和末节讲两套机制(接手复核时查出);
  ② 「provisioning 会写 UserData ⇒ 死线永远绿不了」是**推的**,探针当场证伪;
  ③ `t20b` 自己退化成注释级契约,红检 m23 漏网才照出来。
  ⇒ 共同形状:**我给的"因为",覆盖不到问题的全宽**。这一单已犯四次(含双出抓到那次)。

  **panel 验不到的那一块**:段②(`.cmd`)的真行为、以及业主那台机器上的杀软/VPN/网速。
  前者归 Windows CI `e1~e4`,后者**结构上只有业主验得到** —— 不假装 CI 覆盖了它。
### 收口外审 —— 2026-09-15(断线接手后)

**第 0 轮(作废)** `panel-opendesign-in-app-update-install-final-20260915-004418`:submimo 报告写到半句、rc=0、判 no_verdict;
subdeepseek 在 00:48 断线时被砍(`.err` 末行 `Terminated`),控制器没写 roster/final。**零条可计数结论**。
setsid 没挡住真断线 —— 此后评审一律 `setsid -f` 脱到 PID 1 并核 ppid。

**第 1 轮(整份,subject 05d0fd5)** 花名册原样:
```
    # panel-review 花名册(2026-09-15 09:21:45)task=opendesign-in-app-update-install-final
    # PASS = 进程 rc=0,**不等于给了裁决**;off = 这条腿压根没派(不许读成通过)。
    # impact-risk=high requested-budget=2 selected-count=2
    # selected=subdeepseek(deepseek/subdeepseek-agent),subglm(zhipu/subglm-agent)
    # escalation=none
    # snapshot=head:05d0fd5
    # 日志:/root/aiwork/logs/panel-opendesign-in-app-update-install-final-20260915-091314.*.log
    submimo=SKIP(rotation) subdeepseek=PASS(verdict=PASS) subglm=PASS(verdict=PASS) subkimi=SKIP(rotation) subgemini=SKIP(health:dead:FAIL:6) subgrok=SKIP(rotation)
```

- DeepSeek 与 GLM **各自独立**指出 `/D=` 带空格会被 list2cmdline 加引号,都只判「中」(不确定 NSIS 怎么读)。
  **我读 NSIS 源码(kichik/nsis Main.c:244-288)坐实:引号包住时 `CMP4CHAR(cmdline-2," /D=")` 不成立 ⇒ /D= 被当没传 ⇒
  退回 InstallDirRegKey = 正在运行的活树。** 升级为阻断 ⇒ t33(命令行自己拼)+ t34(.onInit 更新档只许装 .new)。
  **真机坐实**:修前对照 run 34920544526 e6 活树版本号文件变成 0.98.900 而在答的是 0.98.4;e7 活树 4 个文件被覆盖、rc=0。
- 成立并修:t35(stage=shell 放锁 ⇒ 两份接力脚本,DeepSeek F4)、t36(`'`/`%`/非 GBK/代码页 ≠936 ⇒ 关了不回来,GLM F2/F4 + DeepSeek F2
  + 对我自审第 1 条的更正:乱码路径让"打开旧版"也打不开,不是安全失败)、t20a 收紧(argv 问不出命令行形态,DeepSeek F6)。
- 合跑判据时照出 t30b(urlopen 进程级缓存代理,g1↔t30a 双向顺序依赖;基线 05d0fd5 同样红)⇒ 修产品不修考卷。
- 记账不修:rollback_stuck 不拉起任何东西(双重失败,自审第 2 条已记)、两次改名之间断电(design 明账)、
  e2e 档案标记只盯标记目录(provisioning 字节级幂等 + t20c/t26b 方向已收紧 + t26 真机 pointers;全树哈希会被运行中的软件合法写入弄抖)、
  GLM F5 固定 od-health.txt(单飞,无场景)。

**切片评审(对照实验,subject 05d0fd5,scoped 结果不计入归档覆盖)** `/root/aiwork/logs/slice-manifest-20260915-092514`:
relay#1 submimo PASS / stage1#1 subdeepseek BLOCK / installer-ui#1 subglm PASS / e2e#1 subkimi BLOCK / overall#1 subcodex(gpt-6-astra) BLOCK。
⚠️ overall 腿派发时主工作区多了一个 runlog 观测 json(runlog `--repo 工作树` 仍写主工作区),其余四片源指纹一致;产品代码五份相同。

- 成立并修:t37 两段版本号永远装不上(stage1 F1 + overall #10 各自复现)、t38 交棒要接力脚本自证在跑(overall #2)、
  t39 删 %TEMP% 安装包(stage1 F6)、t40 只有装出来的树才自更新(stage1 F10,我核出第 0 步会 rmtree 同名无关 .old)、
  t20c/t26b 比较方向(installer-ui GLM 亲测写反照样绿)、test_ds_update.py 入口挪到最末(overall #11)、e1/e6 收尾 health 复查(overall #9)。
- 核后记账不修:
  - overall #3 **档案 `locked_rw` 先 truncate 后 write**:早已存在、任何强杀/断电都中,更新只是多一个时机 ⇒ 另开单,已告知业主。
  - overall #4 / stage1 F3 / relay G2:接力脚本 health 用 findstr 子串、不查 ok —— `/api/health` 应答时 ok 恒为 True;
    子串对"新版严格大于旧版"造不出误判;"后端起来但窗口没起来就删 .old"是设计层明账。t18 测的 python helper 生产不调用,记为判卷诚实度欠账。
  - stage1 F2 外壳启动窗口期假应答(只在启动头几秒、外部浏览器可达;无数据/安装损坏)。
  - stage1 F4/relay G1 plan 字段未被渲染;F5 回滚 Stop-Process -Force;F7 端口换号;F9 ack 与回包竞态;F11 日志混编码(e2e 第八趟亲眼见到)。
  - e2e 片 #1 隐藏主窗口经 probe_verdict fail-open 判绿(共享判定器、有意防假红);#3/#4 与 overall #8 快捷方式存在性/autorun 不判;
    overall #9 后半 e3 自动重开结构上不可观测(注入锁住哨兵)。
  - installer-ui:更新档仍调 EnsureWebView2(缺 WebView2 时会弹 UAC)、卸载条目半守卫、查更新 fetch 无超时、busy/stale_old 走默认提示。
- **对照实验的读数**:切片审比整份审多抓到 t37/t38/t40 与多处判卷洞;其中 t37 由**同一 DeepSeek 家族**在切片里抓到、整份审没抓到。
  混杂因素:切片那边多了一条 gpt-6-astra 整体腿,t38 与若干判卷洞是它一条腿的。

**第 2 轮(复审修改,subject = 派发时 HEAD)** 花名册原样:
```
    # panel-review 花名册(2026-09-15 10:53:19)task=opendesign-in-app-update-install-final-r2
    # PASS = 进程 rc=0,**不等于给了裁决**;off = 这条腿压根没派(不许读成通过)。
    # impact-risk=high requested-budget=2 selected-count=2
    # selected=subglm(zhipu/subglm-agent),subkimi(moonshot/subkimi)
    # escalation=none
    # snapshot=head:0595b85
    # 日志:/root/aiwork/logs/panel-opendesign-in-app-update-install-final-r2-20260915-103751.*.log
    submimo=SKIP(rotation) subdeepseek=SKIP(rotation) subglm=PASS(verdict=PASS) subkimi=PASS(verdict=PASS) subgemini=SKIP(health:dead:FAIL:6) subgrok=SKIP(rotation)
```

- GLM 与 Kimi 都 PASS,**都亲自核了**:中文 Windows(936)+ 中文用户名 + 默认位置不被 t36/t40 误拒;`OpenDesign.exe` 在包根
  (build-installer.sh)、哨兵同 NSI 常量;t33 参照模型逐行对照 NSIS 源码无照搬错(Kimi 另做 5 处变异全咬住)。
- 两腿各自提:stage=shell 后更新锁留到重启(GLM 中 / Kimi 低)。**我核前端**:界面不显示服务端那句「请稍候」,
  busy 走 `applyHint` 默认句「自动更新没能继续。可以到发布页手动下载。」(实话)⇒ 剩下的影响只是"外壳没接住那次之后要重启才能再点",
  而外壳没接住本身说明锁通道坏了、不重启再点多半同样失败 ⇒ **接受,t35 的取舍不变**。
- GLM 低:第 6 步写接力脚本 / 读新树版本号无 try ⇒ 盘满时请求断、`.new` 留到下次 —— 刚装下 300MB 紧接着写 4KB 失败概率极低 ⇒ 记账不修。
- 低/疑问(两腿自判不阻断):ready 落盘恰在超时那 50ms ⇒ 误杀报没交棒(可重试);ready 重定向失败静默 ⇒ 塌成取消;
  参照模型 `/S` 大小写敏感(真 NSIS 不敏感,只会误红);e7 的 rc=3 未证明来自守卫(NSI 里 SetErrorLevel 3 仅此一处,合取事实兜住);
  注册表路径尾反斜杠(安全向,仍 rc=3)。

- arbitrated verdict (主裁): **PASS**。
  依据:三轮外审 + 切片评审的全部成立发现已修或具名记账;修后 Windows e1~e7 全绿(我亲读事实/日志/截图),
  修前对照 e6/e7 红且在真机上坐实"装进运行中的活树";红检 update_apply 58/0、ds_web 13/0、e2e 考卷 28/0;最终总跑见机械检查一格。
  **业主真机仍是硬前提**:开 VPN 走一次完整更新(t30/t30b 真机半)、中文用户名/默认位置、杀软环境。

## Accepted deviations

- 具名记账、不在本单修的,逐条理由见上方 Review「核后记账不修」三处。其中需要业主知道的两条:
  1. **档案 `locked_rw` 先截断后写**(早已存在,任何强杀/断电都可能留下空档案):建议另开单改"写临时文件再原子替换"。
  2. **开了「Beta: UTF-8 全球语言支持」的中文 Windows + 中文用户名 ⇒ 自动更新会被 t36 拒绝**(有意:GBK 接力脚本在 65001 下读乱),
     这类机器走手动下载。真机清单要问业主是否这么配。
- 外壳没接住交棒(stage=shell)之后更新锁留到重启(t35 取舍;界面提示为实话「自动更新没能继续」)。
- 两次改名之间断电 / 被杀、rollback_stuck 不拉起任何东西:design 明账,无启动期恢复。
