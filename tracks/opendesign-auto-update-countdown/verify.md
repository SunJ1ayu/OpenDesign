# Verify: opendesign-auto-update-countdown

- Date: 2026-09-17

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

**机器打印的**(不是我的转述)。

### 判据先行:实现之前的红(基线 bdad422 + 判据改动,未提交时跑)

- python:au1~au5、au7~au10、au12 + t9a 红,**缺 auto_update / 没记账 / 没二次把关**,红的原因都对。
  au6 / au11 在基线就绿 —— 它们是**防修过头**的反面判据(手动那条路不许被自动那条路连累),基线手动那条路本来就对,结构上红不了。
- node:ac1~ac8 全红(函数不存在)。
- e2e:AC-A / AC-B / AC-D 红(没有横幅)、AC-C 红一半(设置里没有解释)。AC-E / AC-F 与 AC-C 的"不出横幅"是**什么都不该发生**的守卫,基线本来就什么都不发生,结构上红不了;它们的咬合要等实现落地后用变异证(把「只在打开后第一次自动查」那道闸去掉)。
- Windows 判定器:aw1~aw4 在本机随判定器一起写,变异自证:删掉 `_auto_update_eligible` 调用 ⇒ 9 条红;删掉 `_auto_not_retried` ⇒ 11 条红(已恢复)。真机那半等实现落地后推 `ci-update/*` 跑。

```
runlog: oracle-red-python rc=1 commit=bdad422 dirty=yes at=2026-09-17T11:36:17Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T113617Z-01-oracle-red-python.txt
runlog: oracle-red-node rc=1 commit=bdad422 dirty=yes at=2026-09-17T11:36:42Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T113642Z-01-oracle-red-node.txt
runlog: oracle-red-e2e rc=1 commit=bdad422 dirty=yes at=2026-09-17T11:36:49Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T113649Z-01-oracle-red-e2e.txt
```

## Review

- 规格自查(读任何 panel 输出之前先答):<如果规格本身就是错的,会错成什么样、我怎么发现?
  panel 只验"实现合不合规格",验不了"规格对不对" —— 全池一致 PASS 也不等于题是对的。>
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
