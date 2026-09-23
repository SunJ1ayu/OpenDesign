# Verify: opendesign-electron-release-0989

- Date: 2026-09-22

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
runlog -t opendesign-electron-release-0989 -- <判据命令>
```

```
runlog: rel-oracle-red rc=0 commit=5facd88 dirty=yes at=2026-09-22T15:53:39Z file=tracks/opendesign-electron-release-0989/evidence/20260922T155339Z-01-rel-oracle-red.txt
runlog: rel-red-run35750376646 rc=0 commit=81a892c dirty=no at=2026-09-22T16:16:30Z file=tracks/opendesign-electron-release-0989/evidence/20260922T161630Z-01-rel-red-run35750376646.txt
runlog: rel-fix-run35750584881 rc=0 commit=81a892c dirty=yes at=2026-09-22T16:16:33Z file=tracks/opendesign-electron-release-0989/evidence/20260922T161633Z-01-rel-fix-run35750584881.txt
runlog: rel-runall-before-review rc=3 commit=d236f61 dirty=no final=yes at=2026-09-22T16:16:48Z file=tracks/opendesign-electron-release-0989/evidence/20260922T161648Z-01-rel-runall-before-review.txt
runlog: prod-smoke rc=0 commit=cfcef3c dirty=no at=2026-09-23T04:18:51Z file=tracks/opendesign-electron-release-0989/evidence/20260923T041851Z-01-prod-smoke.txt
```

- 说明:rel-oracle-red 是判据先行的红跑(C14a/b 红,预期);rel-red 云跑 rc=0 只是取日志成功,内容里 E7.nopd 红(预期);
  rel-runall rc=3 = 各段全绿 + 3 条老的没跑;prod-smoke = T4 发布后从 GitHub 正式地址取回逐字节比对。

## Review

- 规格自查(09-23 12:2x 接手补写;诚实记:这次是读完两腿报告之后才落笔,不算事前自审):design 的用户成功条件 =
  业主从正式 release 下到的安装包 = 云上装过的那份(只差更新源)、选「所有用户」也能打开、旧壳看不见新版不会误升级。
  两件发版前修补(出货包流水线 / 「所有用户」provision 上下文)都是本单自己查出的,判据先红后绿(evidence/20260923-rel-cloud-redcheck.md)。
  未暴露能推翻方向的前提;下一版在生产上真走一次增量更新不在本单承诺里(T5 之后的事)。
- 腿的花名册:

```
# panel-review 花名册(2026-09-23 00:42:00)task=opendesign-electron-release-0989-review
# PASS = 进程 rc=0,**不等于给了裁决**;off = 这条腿压根没派(不许读成通过)。
# impact-risk=high requested-budget=2 selected-count=2
# selected=subkimi(moonshot/subkimi),subcursor.grok-4.7-high(xai/subcursor)
# escalation=none
# snapshot=head:c994ac3
# 日志:/root/aiwork/logs/panel-opendesign-electron-release-0989-20260923-0029.*.log
subkimi=PASS(verdict=PASS) subcursor.grok-4.7-high=PASS(verdict=PASS)
```

- 轮次记录:

  | 轮 | 类型(实质 / 重试) | 派发前 `track preflight` | 日志前缀 | 新增有效阻断 |
  |---|---|---|---|---|
  | 1 | 实质 | unknown(上一会话派发,未留 rc) | `/root/aiwork/logs/panel-opendesign-electron-release-0989-20260923-0029` | 0 |

- findings(主裁 12:2x 逐条对代码核实):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | 1 | (Cursor-Grok)RELEASE.md 第 1 步只要求 E1～E6 通过,而 artifact `release` 在 E7 之前就上传 ⇒ 照文档可能从 E7 红的一次运行取包,取到会把口令写进 ProgramData 的那种 | `installer/RELEASE.md:5`;`.github/workflows/electron-e2e.yml:140-149` | 延期 | 本次只从全绿 run 35750584881 取包,不受影响;改文档会动评审绑定的交付面。下一次发版若照抄清单,可能发出一个没过 E7 的包 ⇒ 下一张发版单先把「E1～E6」改成「E1～E7 全过」 |
  | 2 | (两腿)`gh-command` 不带 `--target`,tag 打在执行时 main 的 HEAD | `desktop/scripts/release-feed.mjs:49-55` | 驳回(本单按流程兜住) | 发布前核 main HEAD 与 81a892c 之间只差 tracks/(12:2x 已核:`git diff --stat 81a892c HEAD -- . ':!tracks'` 为空);安装包字节来自 artifact,不随 tag 变 |
  | 3 | (Kimi)C14a 没钉 provision 的 `--home` 取自 `$LOCALAPPDATA`,改成定死路径静态闸照绿 | `tests/test_desktop_config.py:259-274`;`desktop/build/installer.nsh:4` | 延期 | 云 E7.nopd 行为闸抓得住;若只跑本地判据会漏,下次动 installer.nsh 时顺手补 |
  | 4 | (Kimi)E1r 的 app.asar 子比较分支本次没被执行(两份 asar 逐字节相同) | fix 收据 E1r 行 | 驳回 | 防御路径,没被触发正说明两包 asar 相同;不是承诺缺口 |

- arbitrated verdict (主裁): 发布前评审 PASS —— 两家族(moonshot / xai)同一 snapshot c994ac3 均 PASS、0 新阻断,
  我核过的要点与两腿一致。本单整体 outcome 等 T4 发布 + T5 业主真机回显后再写进 decision.json。

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:<开工 commit 时刻 → 归档 commit 时刻>
- 每轮新增有效阻断:<第 1 轮 n / 第 2 轮 n>
- 基础设施等待:<重试次数;observations 里 panel-review 的 duration_ms 求和>
- 交付后返工:<归档后因本单再改过几次;不知道写 unknown>
