# 接续验收：启动直接更新（2026-09-19）

## 需求和现场

- 09-18 用户已确认继续取消倒计时方案；从 9e7f95d 接续。原有 5 个测试文件修改及两条变异修复收据保留。
- 旧方案 Windows run 35222749618 只证明旧交互；新方案不能沿用其通过结论。
- 判据先行：旧源码跑新前端单测 48/50（shouldAutoUpdate 尚不存在）；旧 dist 跑新浏览器流程 15 条失败。

## 实现与自审

- 移除倒计时常量、计时器、取消按钮及相关状态；启动 checking/updating/ready 三阶段控制工作区挂载。
- 检查回包先同步 updateInfoRef，再立即安装，避免拿到 render 前的旧数据；effect 重放不重复请求。
- 安装成功交棒后继续等待重启；失败进入旧版，保留失败文案、服务端防循环和手动出口。
- 只读检查 35 秒超时并取消，迟到回包不能自动安装；安装本身不套该超时。
- 逐项保留后端原有协议；本次没有修改后端产品或安装器。
- 原外审阻断：mutation harness 的 M8/M13/M26 锚点修复与 ds-web n1/n3/n4 锚点修复已在接续现场，09-17 收据均通过；错误的函数名自证声明现已撤回。
- 新增前端逻辑由本次主 agent 自审，未把旧方案的外审 PASS 当作新方案外审结论。

## 机械验证

- 前端单测 50/50；后端及 Windows harness 209/209；TypeScript/Vite 构建通过。
- 新浏览器流程单跑通过；全仓 browser 41 PASS / 0 FAIL / 2 SKIP（两个依赖活 gateway 的既有场景）。
- 全仓 node 451 通过；MCP 三闸通过；泄漏闸 14 通过。
- 全仓 Python 1727 条中 1 失败、1 跳过：失败是构建后 CSS 改动导致 dist 不同步，非产品断言失败；零死断言。重新构建后复核 dist 判据，收据待补。
- 全仓 dist 段要求产物已提交；待提交后单独复核，不为已通过的其他段重复总跑。
- Windows 新方案、前端变异收据待补。最终 outcome 暂不填写，未正式发布。

## 历史验收（倒计时版本）

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
- Windows 判定器:aw1~aw4 在本机随判定器一起写。旧记录声称删掉 `_auto_update_eligible` / `_auto_not_retried` 后分别红 9 / 11 条，但当前代码没有这些函数，缺可复现证据，撤回该声明（09-17 外审指出）。实际 Windows 旧方案收据见后续记录；不能用于证明新方案。

```
runlog: oracle-red-python rc=1 commit=bdad422 dirty=yes at=2026-09-17T11:36:17Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T113617Z-01-oracle-red-python.txt
runlog: oracle-red-node rc=1 commit=bdad422 dirty=yes at=2026-09-17T11:36:42Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T113642Z-01-oracle-red-node.txt
runlog: oracle-red-e2e rc=1 commit=bdad422 dirty=yes at=2026-09-17T11:36:49Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T113649Z-01-oracle-red-e2e.txt
```

### 判据第二版:攻题之后(派活之前)

- 第三方攻题(GPT-5.6-sol,只读)报 19 条;逐条核对后改规格 5 处、改考卷 12 处、驳回 3 条、接受 1 条。
  攻题记录在仓外(进仓 = 把考卷的洞递给考生),**收货之后**再把处置表并进本文件。
- 最重的三条都是结构性的:Windows 真机场景会被产品自己的倒计时抢跑(且外壳 child_env 剥掉 `DS_*`,开关名必须避开)、
  接力脚本回滚后业主眼前没有任何说明、「10 秒」没有被真正量过。
- 第二版红:python au1~au5、au7~au10、au9b/au9c、au12a~e、au13~au15 + t9a 红(au6 / au11 仍是基线结构上红不了的反面判据);
  node ac1~ac9 红;e2e AC-A / AC-B / AC-C(设置解释)/ AC-C2 / AC-D / AC-H 红,AC-E / AC-F 是"什么都不该发生"的守卫。
  Windows 判定器 aw1 / e9 / H8 本机全绿(判定器与脚本静态检查,不依赖产品)。

```
runlog: oracle-v2-red-python rc=1 commit=a057f6b dirty=yes at=2026-09-17T12:04:55Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T120455Z-01-oracle-v2-red-python.txt
runlog: oracle-v2-red-node rc=1 commit=a057f6b dirty=yes at=2026-09-17T12:05:24Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T120524Z-01-oracle-v2-red-node.txt
runlog: oracle-v2-red-e2e rc=1 commit=a057f6b dirty=yes at=2026-09-17T12:05:25Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T120525Z-01-oracle-v2-red-e2e.txt
```

### 判据第三版:第二轮攻题之后(派活之前)

- 第二轮只攻 v2 增量,报 11 条:1 条是我的错(au8 仍按两字段断言,合规实现必红),8 条成立已改,1 条驳回为规格
  (查更新不许等更新锁),1 条接受为规格(`os.fsync` / `os.replace` 模块属性调用)。v3 是这 11 条处置的直接落实,未再攻第三轮。
- 第三版红:python 26 条红(au1~au5、au7~au10、au9b/c、au12a~e、au13~au15、au15b + t9a),au6 / au11 绿;node ac1~ac9 红;e2e 7 条没过。

```
runlog: oracle-v3-red-python rc=1 commit=ea81c72 dirty=yes at=2026-09-17T12:23:19Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T122319Z-01-oracle-v3-red-python.txt
runlog: oracle-v3-red-node rc=1 commit=ea81c72 dirty=yes at=2026-09-17T12:23:49Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T122349Z-01-oracle-v3-red-node.txt
runlog: oracle-v3-red-e2e rc=1 commit=ea81c72 dirty=yes at=2026-09-17T12:23:49Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T122349Z-02-oracle-v3-red-e2e.txt
```

### 基线总跑被我中途停掉(内存)

本机 2G 内存,攻题(codex)与基线总跑并跑时系统杀了两个等待进程;为保攻题,我停掉了总跑(rc=143,半截)。实现落地后重跑。

```
runlog: baseline-run-all rc=143 commit=a057f6b dirty=no at=2026-09-17T11:50:56Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T115056Z-01-baseline-run-all.txt
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
