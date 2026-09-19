# Verify: opendesign-startup-not-blocked-by-update

- Date: 2026-09-19

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
runlog -t opendesign-startup-not-blocked-by-update -- <判据命令>
```

```
<粘收据行,逐字节,别改数。**每次提交**都会跟 evidence/ 里的收据逐字节比对(5a);
 **归档时**还要求:最后跑的那一遍必须在这儿、跑红的那几遍一份都不许藏(5b)、
 收据得进 git(5d)。一份收据都没有的话,写一行
 「- 无机器证据:<理由>」认账 —— 沉默不算理由(5c)。>
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

## 判据先行:实现之前的红(基线 34b0805)

`python -m unittest tests.test_ds_update_startup` ⇒ **Ran 25 tests, FAILED (failures=24, errors=1)**

红的原因逐条核过,都对(`ds_update_startup` 整个模块还不存在):
- **su1**(唯一该装的那条路)+ **su2~su12**(缺文件/非对象/半写/schema 不认/phase 不对/
  包不见了/摘要对不上/大小对不上/版本不新/版本号读不出/path 是目录或符号链接)⇒ 一律该进工作区
- **su13** 永远不许抛 —— 本项目四次"打不开"前科的机械防线
- **su14** reason 必须是稳定枚举,不是自由散文
- **su_net1~3** 🔴 本卷核心:决策期间创建 socket 算失败;读状态文件也不许联网;
  把 ds_update 的取数函数全换成"一调用就炸"后,启动决策仍须正常返回
- **sw1~sw4** 原子写(用 `os.replace` 被调用那一刻目标路径的内容来验半写窗口)、坏文件读成 None
- **sc1~sc4** 首次检查有延迟、轮询带抖动、失败退避且有上限、间隔不许为负
  (sc1 是 error 不是 failure:它读常量 `FIRST_CHECK_DELAY_S`,桩返回的是函数 ⇒ TypeError。原因同样是"还不存在"。)

**这份考卷防的两种作弊**(写在文件头):
① 把超时从 35s 改小就宣称修好 —— 照样在启动路径上联网,网一慢照样等。su_net 段钉它,
   且**故意不用"量耗时"来验**(耗时判据会被"把 35s 调成 3s"骗过,还会因机器快慢变 flaky)。
② 状态文件一有问题就抛,把"不更新"变成"打不开"。su4~su13 钉它。
