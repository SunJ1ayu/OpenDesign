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

**机器打印的**(不是我的转述)—— **全部 29 份收据,逐字节**
(2026-09-02 第四轮 subkimi 发现 3:上一版这里写"全部 17 份",而当时 evidence/ 已有 28 份 ——
 "全部"两个字是过期宣称。这一版是从 29 份收据文件里逐份抓尾行拼的,不是我打的字):

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
runlog: yield-race-3-variants-30-rounds rc=0 commit=78f1a0d dirty=yes at=2026-09-02T01:04:14Z file=tracks/opendesign-slow-lock-scan/evidence/20260902T010414Z-01-yield-race-3-variants-30-rounds.txt
runlog: yield-race-3-variants-30-rounds-repeat rc=0 commit=78f1a0d dirty=yes at=2026-09-02T01:04:47Z file=tracks/opendesign-slow-lock-scan/evidence/20260902T010447Z-01-yield-race-3-variants-30-rounds-repeat.txt
runlog: empty-range-baseline-and-blackhole rc=0 commit=48cc9fd dirty=yes at=2026-09-02T01:08:57Z file=tracks/opendesign-slow-lock-scan/evidence/20260902T010857Z-01-empty-range-baseline-and-blackhole.txt
runlog: after-number-audit-unit-tests rc=0 commit=48cc9fd dirty=yes at=2026-09-02T01:09:59Z file=tracks/opendesign-slow-lock-scan/evidence/20260902T010959Z-01-after-number-audit-unit-tests.txt
runlog: blackhole-with-connect-025-the-1250ms-question rc=0 commit=3a95d50 dirty=yes at=2026-09-02T01:12:00Z file=tracks/opendesign-slow-lock-scan/evidence/20260902T011200Z-01-blackhole-with-connect-025-the-1250ms-question.txt
runlog: l2-selfevident-old-floor-1000-lets-connect-1000-through rc=0 commit=3a95d50 dirty=yes at=2026-09-02T01:12:51Z file=tracks/opendesign-slow-lock-scan/evidence/20260902T011251Z-01-l2-selfevident-old-floor-1000-lets-connect-1000-through.txt
runlog: l2-selfevident-new-floor-1500-bites-connect-1000 rc=1 commit=3a95d50 dirty=yes at=2026-09-02T01:13:01Z file=tracks/opendesign-slow-lock-scan/evidence/20260902T011301Z-01-l2-selfevident-new-floor-1500-bites-connect-1000.txt
runlog: yield-race-stagger-sweep-30 rc=0 commit=44d0bd7 dirty=yes at=2026-09-02T01:41:52Z file=tracks/opendesign-slow-lock-scan/evidence/20260902T014152Z-01-yield-race-stagger-sweep-30.txt
runlog: yield-race-stagger-fine-40 rc=0 commit=44d0bd7 dirty=yes at=2026-09-02T01:44:14Z file=tracks/opendesign-slow-lock-scan/evidence/20260902T014414Z-01-yield-race-stagger-fine-40.txt
runlog: yield-race-stagger-fine-40-repeat rc=0 commit=44d0bd7 dirty=yes at=2026-09-02T01:44:34Z file=tracks/opendesign-slow-lock-scan/evidence/20260902T014434Z-01-yield-race-stagger-fine-40-repeat.txt
runlog: acquire-duration-explains-the-window rc=0 commit=2f2e6d3 dirty=yes at=2026-09-02T01:51:19Z file=tracks/opendesign-slow-lock-scan/evidence/20260902T015119Z-01-acquire-duration-explains-the-window.txt
runlog: probe-tombstone-in-the-tool rc=0 commit=5954132 dirty=yes at=2026-09-02T02:36:36Z file=tracks/opendesign-slow-lock-scan/evidence/20260902T023636Z-01-probe-tombstone-in-the-tool.txt
```

**红的那几遍都在上面,一份没藏** —— 共 8 份 rc=1:
- `l6-red`
- `l1-control-serial-must-still-fail`
- `l2-flipped-red`
- `l7-control-hardcoded-must-fail`
- `l2-new-floor-bites-1000ms`
- `l2-new-floor-bites-1200ms`
- `l5-control-drop-patient-must-fail`
- `l2-selfevident-new-floor-1500-bites-connect-1000`

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

第三轮(`panel-slowlock-r3-1788310891`,snapshot 78f1a0d),从盘上重建:

```
submimo=SKIP(rotation) subdeepseek=PASS(verdict=PASS) subglm=PASS(verdict=NEEDS_MORE_INFO,降级:回落聊天腿,只看得见 diff) subkimi=SKIP(rotation) subgemini=SKIP(rotation)
```

🔴 **`subkimi=SKIP(rotation)` 又是假的 —— 同一笔账的第二个实例。** 这一轮
`driver.log` 自己写着 `escalation: degraded -> add subkimi`,盘上有
`.subkimi.facts.json`(09:29)、`.subkimi.log`(15.7 KB,09:32)、`.subkimi.log.err`
(内容 `Terminated`,09:34) —— 它**真的被派了、真的跑了五分钟**,只是没写 `.state`,
而 `panel-roster` 判"派没派"只看 `.state`。上一轮我把这条记成"盘上分辨不出它是不是
升级追加的腿";这一轮**分辨得出来,信息就在 driver.log 里,只是没人读**。

🔴 **本轮预算实况:high 要 2 条 coverage-eligible,实际只站住 1 条。**
subdeepseek rc=0/证据完整/verdict=PASS = 1 条;subglm **降级 + NEEDS_MORE_INFO**
⇒ 按规矩不许补预算;subkimi 被砍且零结论。**所以第三轮不足以支撑归档**,见下面第四轮。

⚠️ **09:13 那个 commit 的标题「第三轮 PASS」是在两条腿还没跑完时写的**
(subdeepseek 09:10 出结论,subglm 09:29 才结束,subkimi 09:34 被砍;断线在 09:14 前后)。
标题不算假话(deepseek 确实判了 PASS),但它**读起来像整轮的裁决**,而整轮当时还没结束。
—— 记忆里那条"机器打印的一句话,和这句话是真的,是两件事"的又一个形态:
这次撒谎的是**我自己的 commit 标题**,不是机器。

第四轮(`panel-slowlock-r4-1788314050`,snapshot **5954132**),从盘上重建:

```
submimo=SKIP(rotation) subdeepseek=SKIP(rotation) subglm=未收尾(无 state:被砍或仍在跑) subkimi=PASS(verdict=PASS) subgemini=SKIP(rotation)
```

🔴 **本轮预算实况:high 要 2 条 coverage-eligible,又只站住 1 条。**
subkimi rc=0 / 证据完整 / verdict=PASS = 1 条(它的 subject digest 里
`head_oid=5954132`、`worktree_tree_oid=69d76a13`,与我接手时的树逐字节一致,已核)。
subglm 在 10:08:38 被**断线的 SIGTERM** 砍掉(`.log` 只有 09:54 那份 526 字节的抬头,
`.log.err` 内容是 `Terminated`,workspace `/tmp/aiwork-review-workspaces/subglm-agent.JNDzqWaJ`
已不存在),**零结论,不许补预算**。
这一次 `panel-roster` 印的是"未收尾(无 state:被砍或仍在跑)"—— **第一、二个实例那笔账
(把被砍的腿印成 SKIP)在这里没有复发**,它如实说了"分不出被砍还是在跑",而我用 `ps`
查过:没有任何活腿(见发现 12 的记账)。

🔴 **更要命的一条:控制器也死了 ⇒ 这一轮的 compact observation 一个字都没落盘。**
`track-record` 判归档预算只认"同一次成功 panel、同一 subject digest 下 N 条
coverage-eligible 的不同家族腿",**不许跨 run 拼接**。所以即使 subkimi 这份 PASS
本身完整可读,它在机器眼里**等于不存在**:第三轮的 subdeepseek(PASS)和第四轮的
subkimi(PASS)是两次 run,拼不起来。⇒ **必须真跑第五轮**,这不是形式主义:
两条腿看的是不同的树,而第四轮修的四条正是第五轮该覆盖的新增区间。

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

   ⛔ **上面这一段(表格 + "结构性" + "驳回成立")在同一天下午被我自己推翻了,
   别照它下结论** —— 表里三组数全是 Barrier 对齐这一种情态;补量错开启动后,
   B/C 的 0 存活只活在 1~2ms 窗口里。**留在这里是为了让"我当时判错了"这件事查得到**,
   现行结论以 findings 第 10 条与 deviation 1 为准。

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

**第三轮(subdeepseek PASS + 4 条,subglm 降级瞎审 + NEEDS_MORE_INFO)**:

7. subdeepseek 四条(60% 是单次值 / 量到的与我判的要分开 / 旧闸那两份收据不自证 /
   252ms 漏网)—— 已在 `44d0bd7` 逐条办掉,理由与收据见该 commit。第 5 条 INFO
   (verdict 仍是 null)与"最终总跑还没跑"自洽,收口时填。
8. **subglm 是瞎着审的,但它瞎着提对了两条** —— 它的底座腿 rc=1 死于
   **被自己的权限闸拦在被审 track 的 `evidence/` 外面**
   (`permission requested: external_directory (…/evidence/*); auto-rejecting`),
   回落聊天腿后又拿到**空 diff、零附件**(工作树 == HEAD ⇒ `git diff` 为空,
   而没设 `PANEL_DIFF_BASE`)⇒ 它明说自己"没有任何可审的树状态"。
   即便如此,两条不依赖读仓库的发现成立:
   - **"B 组 18/30 是 0 存活,那其余 12/30 是 1 份还是 2 份?若有 2 份,那比 0 存活更坏。"**
     —— 树上的收据本来就有这一格:**存活 2 份在所有组、所有档、所有遍里都是 0**。
     它看不见而已;但这一格以前没写进 verify.md,现在写了。
   - **"Barrier 对齐只是一种情态,错开启动没量过,措辞必须限定。"** —— 见下面第 9 条。
     这条和我自审 D2 是同一条,**两条独立来源命中同一处**。
9. subkimi(升级追加腿)09:29 起跑、09:34 被砍,日志停在"正在找 l1~l7 判据源"这一步,
   **零结论**。收尸读完了,没有可捞的发现。

**我自己新找的(腿没报)**:

6. **aiwork 工具账(不属于本仓)** — `panel-roster` 会把**被砍的腿**印成
   `SKIP(rotation)`(判据只看 `.state` 在不在),而同一份输出的抬头又说自己看不见
   升级追加的腿。**抬头免责、正文照样断言** —— 记忆里那条"机器打印的一句话,
   和这句话是真的,是两件事"的第二个实例。已在下面记账,归 aiwork 侧另开。

10. 🔴 **我写在树上的"结构性做不到两全"是错的 —— 是我的量具造出来的**
    (2026-09-02 上午,断线接手后自己攻出来的,B/C 那三组数全是 `threading.Barrier`
    对齐的近同时启动)。补量错开启动,判读规则**写在跑之前**(探针 (3) 段会打印它),
    三遍收据一致:

    | 组 | 0ms | 1ms | 2ms | 5ms | 10ms | 50ms | 200ms | 500ms |
    |---|---|---|---|---|---|---|---|---|
    | A 树上的实现 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
    | B 问整段 | 10/30、12/40、13/40、3/20、4/20 | 1/40、1/40、0/20、1/20 | 0 | 0 | 0 | 0 | 0 | 0 |
    | C base回头看 | 6/30、21/40、14/40、5/20、5/20 | 0/40、0/40、1/20、0/20 | 0 | 0 | 0 | 0 | 0 | 0 |

    🔴 **1ms 那两格是第四轮抓到的(见发现 11):它在遍与遍之间翻过面**
    (第三遍 B=0/20 而 C=1/20,和另外三遍反过来)⇒ 两组都在噪声底,
    **不许写 B/C 谁的窗口更窄**。上一版这张表把它写成 "B 1/40 / C 0",
    是挑了其中两遍。

    ⇒ **双向让位的危险窗口只有 1~2ms 量级**,不是结构性的。
    按跑之前写死的判读规则,这落在"0 存活在某一档之后消失"那一支:
    "这条修法行不通"**不成立**,成立的只是"它拿一个极窄的 0 存活窗口换盲区被堵住"。
    - 已改:`bin/ds_shell_core.py` 那段注释(把"结构性"改成"1~2ms 窗口"并写明是量具造的);
    - 已改:`tracks/opendesign-lock-seniority-field/proposal.md` —— 它的立论就建在这句
      被推翻的话上,现在加了"第 0 步:先证明便宜修法不够,别跳过去直接做协议字段";
    - **本刀仍不改让位方向**,但理由换了(见 deviation 1):不是"它行不通",
      而是"那条盲区是既有的、不是本刀引入的回归,换方向要重开判据与评审轮次"。

**第四轮(subkimi,PASS,4 条)** —— 断线砍掉了另一条腿,但这条跑完了。
我**逐条自己核了树**(不看它的结论就信),**四条全部成立**;第 1 条比它说的还该改:

11. 🔴 **MEDIUM 成立 · 已修 · 比它说的更狠** — 注释里"C 已经是 0"被树上自己
    **70 秒后**的收据推翻。`bin/ds_shell_core.py` 09:50(commit 2f2e6d3)写下
    "错开 1ms 时 B 还剩 1/40、C 已经是 0",而 09:51 跑出、**和它同一个 commit
    5954132 一起落盘**的收据 `*acquire-duration-explains-the-window*` 给的是
    **B=0/20、C=1/20 —— 方向正好反过来**。
    它说的是"方向写反了";我核完五份收据后认为**真相更重**:1ms 那一档
    B/C 都已掉到噪声底(1/40、1/40、0/20、1/20 对 0/40、0/40、1/20、0/20),
    **谁没掉到 0 会在遍与遍之间翻面** ⇒ 任何 B/C 方向性的话都写不得,
    不是"改成正确方向"就完事。
    最难看的是:**同一段注释往下六行,就是我自己写的 ⚠️"别引用其中任何一个比例"**
    —— 违反的是我六行后自己立的规矩。已改三处(注释表、注释正文、
    `opendesign-lock-seniority-field/proposal.md` 的表)+ 上面 findings 10 的表。
    机器证的:`runlog: probe-tombstone-in-the-tool ... at=2026-09-02T02:36:36Z`
    —— **第五遍**又翻回 B=1/20、C=0/20,当场再证一次"方向不稳"。

12. 🔴 **MEDIUM 成立 · 已修** — **墓碑立在了 verify.md,没立在探针里。**
    `probes/yield_race.py` 的 docstring 判读段和 (2) 段的打印,到 HEAD 为止
    仍然无条件断言"B/C 只要出现过 0 ⇒ 这条修法被证伪 ⇒ 必须给锁协议加先来后到字段"
    —— 那句话**已被同一支探针的 (3) 段推翻**。也就是说:最新那三份收据里,
    **同一次运行先印出被推翻的旧结论,再在下面把它推翻**,而工具本身没有任何标记。
    这是"假话留在树上"的**可执行形态**:它还会不断生产带假话的新收据。
    已改:docstring 加 ⛔ 墓碑(保留原话 + 指向本条与 deviation 1),
    (2) 段的打印改成只报事实、并明说"到此为止不许下结论,窗口宽度由 (3) 段说了算"。
    机器证的(对照组):旧收据 `*acquire-duration-explains-the-window*` 里
    "必须加先来后到字段" 出现 1 次;修完后跑的 `*probe-tombstone-in-the-tool*` 里
    出现 **0 次**,取而代之的是第 36~37 行那两行墓碑。

13. **LOW 成立 · 已修** — verify.md 顶部写"**全部** 17 份收据,逐字节",而当时
    `evidence/` 已有 28 份。"全部"两个字是**过期宣称**(记忆里那条"过期的绿不只是
    数字过期"的又一个形态)。已改成从 29 份收据文件里逐份抓机器尾行拼出来的全量清单,
    rc=1 的份数也从 7 更正为 8(漏掉的是 `l2-selfevident-new-floor-1500-bites-connect-1000`)。

14. **LOW 成立 · 记账不修(本单)** — 错开量是**名义值**:`time.sleep(offset)` 打在
    `Barrier` 之后,两条线程**真实起跑偏斜从未打点实测**。方向双刃(sleep 过冲会放大、
    Barrier 释放偏斜会缩小),≥2ms 档五遍全零在经验上把它夹住了,但这确实是
    "我用没量过的量具去证伪自己上午的强结论"。
    ⇒ 写进下一单第 0 步:两个**进程**测量时必须记 `perf_counter` 起跑差。
    (它同轮还指出 proposal 表里 "B 10~13/40" 混了分母 —— 10 来自 /30 —— 已一并改掉。)

⚠️ **subkimi 这份 PASS 的可信度我自己打个折**:它在结论里明说自己在 PASS 和 BLOCK
之间来回了好几轮(日志里能看到它反复自问"a false statement in the reviewed range
should block?"),最后按"不改变技术决定"落在 PASS。**我不拿它的 PASS 当通过凭证**
—— 本轮真正有价值的是那四条发现,而它们四条全部成立、且第 1 条打在我自己
"让这句话自证"的那个 commit 上。

### arbitrated verdict(主裁)

<收口时填>

## Accepted deviations

1. **拓扑盲区:第一份在备用锁位、base 空着时,兜底结构上够不着** ⇒ 两份并存。
   - 影响范围:**数据面**(两个后台对着同一个 data_root)。
   - 今天靠什么防:唯一一层是快扫的 connect 期限(`lock_timeouts()` 两个 1.5s,
     判据 l2 钉着下限 ≥1.5,往下调必须先有那台 Windows 的实测)。
   - 为什么本单不修 —— **量到的**和**我判的**分开写(第三轮评审 LOW 第 2 条要求,成立):

     ⚠️ **2026-09-02 下午重写:这一格原先写的"结构性做不到两全"被我自己的收据推翻了**
     (见 findings 第 10 条)。下面是改正后的版本。

     **量到的(五遍都成立)**:A 组在任何错开档上都没出现过 0 存活;
     B/C 的 0 存活**只出现在 ≲1~2ms 的对齐窗口内**,错开 2ms 以上五遍一次都没有;
     存活 2 份在所有组、所有档、所有遍里恒为 0;盲区那一格每遍一样(A 放行、B/C 堵住)。
     0ms 那一档的比例给出过 6/30~21/40,**别引用比例**;1ms 那一档两组都在噪声底、
     方向在遍与遍之间翻面(第四轮发现 11),**也不许比较 B 和 C 谁更窄**。
     ⇒ 量到的是"B/C 用一个 **1~2ms 量级的 0 存活窗口** 换盲区被堵住"这笔取舍,
     **不是**"做不到两件事兼得"。

     **我判的(价值判断 + 排期,不是量出来的)**:本刀不换让位方向,因为
     (a) 那条盲区是**既有**的,不是本刀引入的回归 —— 本刀只动扫描代价与期限;
     (b) 换方向是并发裁决的改动,要重开判据与评审轮次,而这一刀的存在理由是
     "双击后别干等十几秒"。
     ⚠️ **这一条同样可以被推翻**,而且现在比之前更容易被推翻:C 的代价已经量到是
     1~2ms 窗口,不再是"行不通"。真要推翻它的人该带的数是:业主那台 Windows 上
     两个**进程**两次 acquire 的时间差分布 —— 落进 1~2ms 的概率有多大。
     那正是下一单写死的第 0 步。

     先来后到字段**不再是唯一候选**:下一单要先算清 C 够不够,不够才做协议改动。
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
