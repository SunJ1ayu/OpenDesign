# Verify: opendesign-kimi-glm-vendors

- Date: 2026-09-23

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
runlog -t opendesign-kimi-glm-vendors -- <判据命令>
```

```
runlog: bash rc=1 commit=53560cc dirty=yes at=2026-09-23T09:37:17Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T093717Z-01-bash.txt
```
(上一行 = 判据先行红检:k1/k2/k4/k5/k5b/k6 + ku1/ku3 红,红因都是「不认识的厂商 / 缺 keyUrl / 卡片无链接」;k3、ku2 是守卫型、现状即绿。)

```
runlog: bash rc=3 commit=64442c0 dirty=no at=2026-09-23T09:39:46Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T093946Z-01-bash.txt
```
(上一行 = 第一版实现后总跑:六段全 PASS(rc=3 = 活网关 e2e 2 条 + python 1 条跳过)。**之后自审抓到两条真 bug,见下。**)

```
runlog: python rc=1 commit=64442c0 dirty=yes at=2026-09-23T09:51:37Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T095137Z-01-python.txt
```
(上一行 = 自审补判据 k4b/k7/k7b 的红检:① 重启后 GLM 同名预设被 prepare_gateway 按「最后一家」重指,三种槽位组合全红;
② Kimi 每个模型真发出去的 temperature=0.1(nanobot 的 moonshot 覆盖只对它自己的 moonshot 规格生效)。)

```
runlog: python rc=1 commit=a913a4f dirty=yes at=2026-09-23T09:53:18Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T095318Z-01-python.txt
```
(上一行 = 修 k4b 时想到的反面 k4c 红检(工作树里已有 k4b/k7 的修法):存第二家 GLM 的 key 后「想换过去」,
同名预设被保留给原来那家 ⇒ 重启后仍在原来那家,两个方向都红;k4b/k7/k7b 此时已绿。)

```
<粘收据行,逐字节,别改数。**每次提交**都会跟 evidence/ 里的收据逐字节比对(5a);
 **归档时**还要求:最后跑的那一遍必须在这儿、跑红的那几遍一份都不许藏(5b)、
 收据得进 git(5d)。一份收据都没有的话,写一行
 「- 无机器证据:<理由>」认账 —— 沉默不算理由(5c)。>
```

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
