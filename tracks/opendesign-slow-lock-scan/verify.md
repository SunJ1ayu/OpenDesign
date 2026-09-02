# Verify: opendesign-slow-lock-scan

- Date: 2026-09-01 起,2026-09-02 收口

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明,不复制枚举。

## Mechanical checks

- [ ] build passes / tests pass —— **此刻还没跑最终总跑,所以这两个勾不许先打**
      (2026-09-02 自查抓到:我先打了勾才去跑,那正是"打了勾的第 11 项是假的"那种假。
       收口时跑完 `runlog --final`、把收据行贴到下面,再回来改这两个框。)
      已知两条与本刀无关的红:`stage_timer.e2e.mjs` 开工前就红,上一单已量证。
- [x] no secrets / unsafe ops(本刀只动 `bin/ds_shell_core.py` 的锁扫描与两个 docstring、
      `tests/` 判据、`tracks/` 工件;无新写口、无凭证、无网络出口)

**机器打印的**(不是我的转述)—— 全部 17 份收据,逐字节:

```
runlog: l6-red rc=1 commit=7ea4262 dirty=yes at=2026-09-01T13:08:54Z file=tracks/opendesign-slow-lock-scan/evidence/20260901T130854Z-01-l6-red.txt
runlog: l6-green-Lgroup rc=0 commit=0b90451 dirty=yes at=2026-09-01T13:09:47Z file=tracks/opendesign-slow-lock-scan/evidence/20260901T130947Z-01-l6-green-Lgroup.txt
runlog: l1-control-serial-must-still-fail rc=1 commit=7ce5cac dirty=yes at=2026-09-01T13:10:52Z file=tracks/opendesign-slow-lock-scan/evidence/20260901T131052Z-01-l1-control-serial-must-still-fail.txt
runlog: l1-green-new-budget rc=0 commit=7ce5cac dirty=yes at=2026-09-01T13:11:36Z file=tracks/opendesign-slow-lock-scan/evidence/20260901T131136Z-01-l1-green-new-budget.txt
runlog: l2-flipped-red rc=1 commit=d4c2272 dirty=yes at=2026-09-01T13:35:49Z file=tracks/opendesign-slow-lock-scan/evidence/20260901T133549Z-01-l2-flipped-red.txt
runlog: connect-latency-before rc=0 commit=d4c2272 dirty=yes at=2026-09-01T13:36:18Z file=tracks/opendesign-slow-lock-scan/evidence/20260901T133618Z-01-connect-latency-before.txt
runlog: l2-green-connect-1500 rc=0 commit=34a7411 dirty=yes at=2026-09-01T13:37:51Z file=tracks/opendesign-slow-lock-scan/evidence/20260901T133751Z-01-l2-green-connect-1500.txt
runlog: probes-after-connect-1500 rc=0 commit=34a7411 dirty=yes at=2026-09-01T13:38:34Z file=tracks/opendesign-slow-lock-scan/evidence/20260901T133834Z-01-probes-after-connect-1500.txt
runlog: l7-control-hardcoded-must-fail rc=1 commit=0e8256b dirty=yes at=2026-09-01T13:40:26Z file=tracks/opendesign-slow-lock-scan/evidence/20260901T134026Z-01-l7-control-hardcoded-must-fail.txt
runlog: l7-green-Lgroup rc=0 commit=0e8256b dirty=yes at=2026-09-01T13:40:48Z file=tracks/opendesign-slow-lock-scan/evidence/20260901T134048Z-01-l7-green-Lgroup.txt
runlog: l2-control-old-bound-lets-1200ms-through rc=0 commit=f926a6c dirty=yes at=2026-09-02T00:50:00Z file=tracks/opendesign-slow-lock-scan/evidence/20260902T005000Z-01-l2-control-old-bound-lets-1200ms-through.txt
runlog: l2-control-old-bound-lets-1000ms-through-below-p99 rc=0 commit=f926a6c dirty=yes at=2026-09-02T00:50:28Z file=tracks/opendesign-slow-lock-scan/evidence/20260902T005028Z-01-l2-control-old-bound-lets-1000ms-through-below-p99.txt
runlog: l2-new-floor-bites-1000ms rc=1 commit=f926a6c dirty=yes at=2026-09-02T00:51:13Z file=tracks/opendesign-slow-lock-scan/evidence/20260902T005113Z-01-l2-new-floor-bites-1000ms.txt
runlog: l2-new-floor-bites-1200ms rc=1 commit=f926a6c dirty=yes at=2026-09-02T00:51:20Z file=tracks/opendesign-slow-lock-scan/evidence/20260902T005120Z-01-l2-new-floor-bites-1200ms.txt
runlog: l2-green-floor-1500-Lgroup rc=0 commit=f926a6c dirty=yes at=2026-09-02T00:51:31Z file=tracks/opendesign-slow-lock-scan/evidence/20260902T005131Z-01-l2-green-floor-1500-Lgroup.txt
runlog: yield-race-30-rounds rc=0 commit=72581f1 dirty=yes at=2026-09-02T00:53:36Z file=tracks/opendesign-slow-lock-scan/evidence/20260902T005336Z-01-yield-race-30-rounds.txt
runlog: l5-control-drop-patient-must-fail rc=1 commit=4687bef dirty=yes at=2026-09-02T00:54:25Z file=tracks/opendesign-slow-lock-scan/evidence/20260902T005425Z-01-l5-control-drop-patient-must-fail.txt
```

**红的那几遍都在上面,一份没藏**:l6-red、l1-control(串行必须仍然红)、l2-flipped-red、
l7-control(写死当前正确值也必须红)、l2-new-floor-bites-1000ms/1200ms、
l5-control-drop-patient —— 共 7 份 rc=1。

**最终收据(全仓总跑,在最后一次编辑之后跑的那一遍)**:

```
<收口时补:runlog --final 的那一行>
```

## Review

### 规格自查(读任何 panel 输出之前先答)

规格是"业主双击后不该干等十几秒",第一性的约束是"**省时间不许拿数据面去换**"。
如果规格本身错了,会错成:我把"单实例"默认翻译成了"占住最靠前的那个锁位",
而这个翻译在**陌生程序占过 base** 的机器上不成立 —— 这正是第一轮评审打穿的地方,
也是今天仍然敞着、已另开一单的那条拓扑盲区(`opendesign-lock-seniority-field`)。
panel 只验"实现合不合规格",验不出这一层;它是我自己写下来、并在下一单里去修的。

### 腿的花名册

第一轮(`panel-slowlock-1788268399`,snapshot d4c2272),从盘上重建:

```
submimo=PASS(verdict=UNKNOWN) subdeepseek=PASS(verdict=BLOCK) subglm=SKIP(rotation) subkimi=SKIP(rotation) subgemini=PASS(verdict=BLOCK)
```

第二轮(`panel-slowlock-r2-1788270163`,snapshot f926a6c),从盘上重建:

```
submimo=SKIP(health:cooldown:INCOMPLETE) subdeepseek=PASS(verdict=BLOCK) subglm=FAIL(rc=1,降级:回落聊天腿也没成) subkimi=SKIP(rotation) subgemini=SKIP(rotation)
```

🔴 **这一行里 `subkimi=SKIP(rotation)` 是假的,别照着它下结论。** 盘上有
`panel-slowlock-r2-1788270163.subkimi.facts.json`(22:13)、`.subkimi.log`(86 KB,22:20)
和 `.subkimi.log.err`(内容:`Terminated`)—— 它**真的跑了七分钟**,是断线把它砍了。
它没写 `.state`,而 `panel-roster` 判"派没派"看的就是 `.state` ⇒ 一条**被砍的腿**
被印成了"压根没派"。花名册抬头自己写了 `escalation=unknown`(控制器没活到收尾)
并声明"不含升级追加的腿",但**每条腿那一行仍然给出了断言**。
两句话打架时,底下那句更响 —— 这是 aiwork 侧的一笔账,已记在下面的发现里。
(它是不是升级追加的第三条腿,盘上分辨不出来:`.plan` 是派发前的快照,里面 subkimi=0。)

### findings

**第一轮(2×BLOCK)** —— 已全部落地,见 `bin/ds_shell_core.py` 的三处 🔴 注释:
connect 期限从 0.25s 收回 1.5s;`_someone_ahead_of` 的 overclaim 改成如实说明;
l5 docstring 说清它只覆盖"第一份占着 base"这一种拓扑。

**第二轮(subdeepseek,BLOCK,5 条)** —— 我**逐条自己去核**,五条全部成立:

1. **MEDIUM 成立 · 已修** — l2 钉的是 `≥1.0`,而它自己的报错文案引的是实测 p99
   1022.975ms ⇒ **1.0s 落在尾巴下面,判据照样绿**;连带 `lock_timeouts()` 那句
   "都不许再往下调,考卷 l2 钉着这条下限"是假话。
   机器证的:旧闸 rc=0 放行 1.0s 与 1.2s;新闸 rc=1 咬住两者;L 组 7/7 绿。
   ⚠️ **我不采纳它给的修法**(抬到 1.1s = Linux 实测 max 加一点):那正是第一轮
   BLOCK 的同一个动作 —— 拿 Linux 的尾巴去定业主那台 Windows 的期限。
   下限取 **1.5**(这一刀之前就在跑的值,来路干净、零跨平台推断),
   顺带让 `lock_timeouts()` 那句话**自动变成真话**,不用再改代码。
   ⚠️ 1.2s 那两份收据证的是"注释在撒谎",**不是安全洞** —— 1.2s > 实测 max 1060ms,
   它罩得住尾巴。这两件事我分开记。
2. **MEDIUM 成立 · 已修** — "整段都问会双向让位,3 轮里 1 轮存活 0 份"是驳回那条修法的
   **全部依据**,而仓库里复现不出来。(被断线砍掉的 subkimi 在它那份没写完的日志里
   **独立命中同一条**。)补了 `probes/yield_race.py`,量的是一笔**取舍**
   (盲区堵不堵得住 × 同时启动活下来几份),三组 × 每组 30 轮:

   | 组 | 拓扑盲区 | 同时启动出现 0 存活 |
   |---|---|---|
   | A 树上的实现(只问 `p < mine`) | **放行**(两份并存) | 0/30(三遍都是 0) |
   | B 评审建议(绑完问整段) | 堵住 | 18/30、10/30、9/30 |
   | C 我构造的最强变体(只让 base 上那份回头问) | 堵住 | 13/30、9/30 |

   C 是我为了攻自己"B 是不是稻草人"专门构造的(自审 D1):**它确实比 B 强** ——
   盲区照堵、非 base 一侧让位方向仍唯一 —— **但照样出现 0 存活**。
   ⇒ 结论从"某个比例"升级成**结构性的**:光靠"问谁在监听",分不出
   "对面已经站住了"和"对面正和我同时启动"。驳回成立,而且理由比原来硬。

   🔴 **我在这条上自己犯过一次"话比证据重"**:上午一度把单次的 18/30 写成
   "实测 60%,比原话严重一倍"写进代码注释,下一遍跑出来就是 30%。已改成不引用任何比例,
   只留三条每遍都成立的定性事实。(记忆里那条"n=3 的行为考卷不足以下任何结论"。)
3. **MEDIUM 成立 · 已修** — accepted deviation 空、没开"另一单"、`outcome.verdict` 为 null。
   这条最实:数据面缺口当时**没有关闭机制**。现在 deviation 写在下面,
   后续单 `tracks/opendesign-lock-seniority-field/` 已建并写了真正的 proposal
   (含四步拓扑、验收就用 yield_race 的 A/B 对照、impact=high/data_consistency)。
4. **LOW 成立 · 已修,而且比它报的多三处** — 它只报了 l5:2031;我搜了一遍,
   `0.049 / 1023.510 / 1060.341` 这组手抄数还出现在 l2 的 docstring 两处和
   `probes/connect_latency.py` 头部,**四处全换成收据里的真数**并注明出处。
5. **LOW 成立 · 用今天的收据兑现** — evidence/ 缺 l5 的红收据(判据先行走 runlog 是从
   l6 那笔才开始的)。历史的红补不回来;改为证"它今天还咬得动":拿掉 patient 兜底
   ⇒ l5 rc=1,且红在它自己那句断言上,不是红在 TypeError 上。

**我自己新找的(腿没报)**:

6. **aiwork 工具账(不属于本仓)** — `panel-roster` 会把**被砍的腿**印成
   `SKIP(rotation)`(判据只看 `.state` 在不在),而同一份输出的抬头又说自己看不见
   升级追加的腿。**抬头免责、正文照样断言** —— 记忆里那条"机器打印的一句话,
   和这句话是真的,是两件事"的第二个实例。已在下面记账,归 aiwork 侧另开。

### arbitrated verdict(主裁)

<收口时填>

## Accepted deviations

1. **拓扑盲区:第一份在备用锁位、base 空着时,兜底结构上够不着** ⇒ 两份并存。
   - 影响范围:**数据面**(两个后台对着同一个 data_root)。
   - 今天靠什么防:唯一一层是快扫的 connect 期限(`lock_timeouts()` 两个 1.5s,
     判据 l2 钉着下限 ≥1.5,往下调必须先有那台 Windows 的实测)。
   - 为什么本单不修 —— **量到的**和**我判的**分开写(第三轮评审 LOW 第 2 条要求,成立):

     **量到的(每一遍都成立)**:A 组从没出现 0 存活;B 组和 C 组每一遍都出现;
     盲区那一格三组的结果每遍一样(A 放行、B/C 堵住)。
     比例三遍从 30% 跳到 60%(评审腿独立复跑还得过 23%),**别引用比例**。
     ⇒ 量到的是"**光靠问谁在监听,做不到两件事兼得**"这个结构性事实。

     **我判的(价值判断,不是量出来的)**:我认为"业主双击后一个窗口都不开"比
     "两份并存"更该避免 —— 因为本单存在的全部理由就是修双击体验,而 0 存活
     直接把它推到更坏;且 0 存活可重试,两份并存伤的是档案。
     ⚠️ 这一条**可以被推翻**:两份并存是数据面,重试是体验面,谁更难看不是我量出来的。
     推翻它的后果不是"本单改法不同",而是"这条缺口该更早修" —— 它已经开成单了。

     真修法要给锁协议加先来后到字段,那是一次协议改动,不该塞进这一刀。
   - 关闭机制:**已开单** `tracks/opendesign-lock-seniority-field`(impact=high,
     data_consistency),proposal 里写死了四步拓扑和验收标准。
2. **业主那台 Windows 的 connect 尾巴从没量过** —— 全部实测来自 Linux。
   所以下限取 1.5(这一刀之前的值),不取任何从 Linux 外推的数。
   要往下调,先在那台机器上跑 `probes/connect_latency.py`。
3. **第二次双击那条路不打 `lock.acquired`**(`ds_shell.py` 在 mark 之前就 return 了)
   ⇒ 业主双击第二下时快扫花了多久不进诊断。诊断覆盖面的洞,不是本刀引入的回归,本单不修。
4. **`stage_timer.e2e.mjs` 开工前就红**,上一单已量证,与本刀无关。
5. **业主那台机器上 6 个锁位为什么全耗满**,仍然不知道(他实测软件关着时那 6 个口是空的
   ⇒ 丢包,不是有人占)。本单只让"耗满"这个结果从 9047ms 变成 1502ms。
