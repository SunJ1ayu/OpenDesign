# Verify: opendesign-release-09811

- Date: 2026-09-24

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
runlog -t opendesign-release-09811 -- <判据命令>
```

```
runlog: run-all rc=3 commit=c7aee6f dirty=no final=yes at=2026-09-24T06:40:59Z file=tracks/opendesign-release-09811/evidence/20260924T064059Z-01-run-all.txt
runlog: cloud-e2e rc=0 commit=c7aee6f dirty=yes at=2026-09-24T07:02:52Z file=tracks/opendesign-release-09811/evidence/20260924T070252Z-01-cloud-e2e.txt
```
- run-all rc=3 = 六段全过(python 1507 / node 509 / e2e 41),3 条既有 SKIP 要起 gateway。
- cloud-e2e = run 35965656125(head `c7aee6f`,payload + e2e 两个 job 都 success):**141 OK / 0 FAIL**。
  quiet-start 移交的两条兑现:E2.connecting「后台没好时不挂横幅」、E2.noreload「就绪后整页不重载」;E4 应用内更新(0.98.11 → 替身 0.98.12)
  「重启以更新」→ 向导两下 → 自己重开、版本三方一致;E1r 出货版与被测版逐文件只差更新源。

## Review

- 规格自查(读任何 panel 输出之前先答):<回看 design 的用户成功条件、前提证据和未解决项。
  实现符合规格不证明规格合理;实现评审也可质疑规格,但不能替代实施前 panel 4c 的方案检查。
  本轮若暴露能推翻方向的前提,先回到设计;全池一致 PASS 也不等于题是对的。>
- 腿的花名册: <把 `<日志前缀>.roster` 里那一行**原样粘过来**,别手写>
  > panel-review 收尾自己写这个文件(off / FAIL(rc) / 降级 都在里面)。
  > **控制器没活到收尾时它压根不存在** —— 那时跑 `panel-roster <日志前缀>` 从盘上重建,
  > 与控制器自己写的**归一化后一致**(判据 R5b 守着;抬头有渲染时间戳,不是字面逐字节)。**一轮零记录的评审也粘得出这一行**,
  > 所以"那轮被砍了所以没有花名册"不再是理由(2026-08-23,track panel-roster-from-disk)。
  > 08-06 立这条的理由:08-05 我在这里手写了"三条腿一致 PASS",而 Kimi 根本没出结论
  > (同一页第 90 行我自己还写着它没出报告)—— 手抄一份终端上的东西,抄错那次没人会发现。
- 轮次记录(每次派发一行;实质评审与基础设施重试分开,重试不算轮但次数与耗时照记):

  | 轮 | 类型(实质 / 重试) | 派发前 `track preflight` | 日志前缀 | 新增有效阻断 |
  |---|---|---|---|---|
  | 1 | 实质 | <rc,BLOCK 数> | <…> | <n> |

- findings(**先处置、后动手**;一轮一份修复清单,一次修完再复审 —— panel 抽屉 4b):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | 1 | <…> | <file:line / 复现收据> | 必须修 / 延期 / 驳回 / 尚未核实 | <延期必写:它在业主或下一个使用者那边会长成什么样> |

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
