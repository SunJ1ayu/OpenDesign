# Verify: opendesign-b8-race-forensics

- Date: 2026-09-21

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

## Mechanical checks

- [x] build passes(总跑里的 dist 新鲜度 + 类型检查:与源码同步)
- [x] tests pass(python 1800 跑过 / 1 跳过;死断言闸不再报)
- [x] no secrets / unsafe ops(产品代码零改动;变异只打仓外副本,活仓由夹具拒绝)

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,收据行原样粘在这里。
🔴 **跑红的那几遍一份都没藏**,它们是这一单最值钱的部分:

```
runlog: full-regression rc=1 commit=c8fdb23 dirty=yes at=2026-09-21T00:51:44Z file=tracks/opendesign-b8-race-forensics/evidence/20260921T005144Z-01-full-regression.txt
```
↑ **红的**。红在死断言闸:我把三条断言写成了 `if …: self.fail(…)`,正常跑永远不执行。
这不是环境噪音,是本单自己造出来的回归(处置见 df83e6f)。

```
runlog: b8-x12-after-gate-shape rc=0 commit=a205077 dirty=yes at=2026-09-21T01:46:43Z file=tracks/opendesign-b8-race-forensics/evidence/20260921T014643Z-01-b8-x12-after-gate-shape.txt
runlog: full-regression-after-gate-shape rc=3 commit=a205077 dirty=yes at=2026-09-21T01:47:20Z file=tracks/opendesign-b8-race-forensics/evidence/20260921T014720Z-01-full-regression-after-gate-shape.txt
runlog: b8-x12-final rc=0 commit=06c25f0 dirty=yes at=2026-09-21T02:03:27Z file=tracks/opendesign-b8-race-forensics/evidence/20260921T020327Z-01-b8-x12-final.txt
runlog: full-regression-final rc=3 commit=06c25f0 dirty=yes final=yes at=2026-09-21T02:03:51Z file=tracks/opendesign-b8-race-forensics/evidence/20260921T020351Z-01-full-regression-final.txt
runlog: b8-x12-r2 rc=0 commit=570861f dirty=yes at=2026-09-21T02:39:57Z file=tracks/opendesign-b8-race-forensics/evidence/20260921T023957Z-01-b8-x12-r2.txt
runlog: full-regression-r2-final rc=3 commit=570861f dirty=yes final=yes at=2026-09-21T02:40:21Z file=tracks/opendesign-b8-race-forensics/evidence/20260921T024021Z-01-full-regression-r2-final.txt
runlog: b8-x12-r3 rc=0 commit=db567b0 dirty=yes at=2026-09-21T03:11:02Z file=tracks/opendesign-b8-race-forensics/evidence/20260921T031102Z-01-b8-x12-r3.txt
runlog: full-regression-r3-final rc=3 commit=db567b0 dirty=yes final=yes at=2026-09-21T03:11:26Z file=tracks/opendesign-b8-race-forensics/evidence/20260921T031126Z-01-full-regression-r3-final.txt
runlog: b8-x12-r4 rc=0 commit=4af7789 dirty=no at=2026-09-21T03:38:19Z file=tracks/opendesign-b8-race-forensics/evidence/20260921T033819Z-01-b8-x12-r4.txt
runlog: full-regression-r4-final rc=3 commit=4af7789 dirty=yes final=yes at=2026-09-21T03:38:43Z file=tracks/opendesign-b8-race-forensics/evidence/20260921T033843Z-01-full-regression-r4-final.txt
```
↑ **最后一遍是 `full-regression-r4-final`**(`source-stable: yes`):python 1800 跑过 / 1 跳过、
node 461、e2e 41 PASS / 0 FAIL / 2 SKIP、死断言闸不报。
(前面几份 `-final` 是各轮修复当时的最后一遍,一并留着 —— 结论依据的是最后那一份。)
`rc=3` = 3 条 SKIP(1 条 python + 2 条要活网关的 e2e),既有状态,没有红的。
`final=yes` 那一份 `source-stable: yes`。

**红检收据**(不走 runlog,直接落 evidence/,每份自带命令与副本路径):
- `baseline-old-b8-*.txt` —— 旧 b8 对四种病因:全红,读数逐字段同形 ⇒ 分不出病因。
- `oldb8-vs-shape-gate-*.txt` —— 旧 b8 对形状判据:四条全错(证明形状判定不是空转)。
- `before-s1-fix-r2d-no-ss.txt` —— 🔴 **红的**:没装 ss 时取证把本轮自己的两个赢家
  列成"环境残留"(S1)。修后 `after-s1-fix-*.txt` 全套 rc=0。
- `before-f1-fix-r2d-no-tools.txt` —— 🔴 **红的**:ss 与 lsof 都拿不到 pid 时,
  取证仍笃定地说"环境残留"(外审 F1)。
- `before-f1-fix-f3-mutant.txt` —— 🔴 **红的(对照实验)**:把分型结论句硬写成一支,
  补锚点前夹具照印"形状=对",补锚点后当场抓住(外审 F3)。
- `after-f1-fix-*.txt` —— 第 1 轮修复之后全套 8 情景 rc=0(r2d-no-tools 转绿)。
- `after-f1-fix-f2-probe.txt` —— F2 修复的当面对照:假 `ss`(rc=1)下修前说
  "这个端口上没有 LISTEN",修后正确回落到 `lsof`;两个工具都没有时说
  "<ss:没装;lsof:没装>" 且 `listener_pids -> None`。
- `before-f8-fix-r2d-flaky-lsof.txt` —— 🔴 **红的**:带警告的 `lsof`(有输出但 rc=1)
  被我按 rc 丢掉 ⇒ 明明查得到却说"查不出"(第 2 轮外审 F8,我自己修 F2 时修过头)。
- `before-f8-fix-revert-f2-control.txt` —— 🔴 **红的(对照实验)**:把 F2 整个 revert 掉,
  新加的 `r2d-broken-ss` 当场抓住那句假话 ⇒ 这条钉子不是空转。
- `after-f8-fix-*.txt` —— 修完之后全套 **10 个情景 rc=0**。
- `before-aggr-fix-grep-probe.txt` —— 🔴 **红的**:`run-redchecks.sh` 的聚合判定
  `grep -q "rc=0"` 命中取证正文里的「已退 rc=0」⇒ 形状错的情景被读成过(覆盖轮 L2)。
- `after-aggr-fix-*.txt` —— 行首锚定之后全套 10 情景 rc=0(这次是严格判定下的 rc=0)。

## Review

- 规格自查(读任何 panel 输出之前先答):design 的用户成功条件是「b8 红的时候我手里有
  分得出病因的现场」,不是「b8 变绿」。前提证据:② 在当前实现下不可达(`_acquire` 只有
  两条 `return False`,都要求逐字节 `OK`)、① 能造出 09-20 那条读数的确切形状。
  **本单不宣称 09-20 那次就是 ①** —— 那次 `40305` 上究竟是谁,证据已失。
  成立的是更小的两句:当时段内**确有**一个真 OpenDesign 应答者(两份 port 同值只可能
  来自扫描命中分支 `self.port = hit`,这是外审 subdeepseek 补给我的确定性推理,
  比我原来的概率论证硬);它是本用例自己的跨轮残留、还是机器上另一个真实例,分不出。
  实现符合规格不证明规格合理:这份考卷跑在 Linux/回环 socket 上,**不承诺** Windows
  双击两下的结果,也不拿本单的绿给真机背书。
- 腿的花名册:
  ```
  submimo=SKIP(rotation) subdeepseek=PASS(verdict=PASS) subglm=SKIP(health:dead:auth:3) subkimi=FAIL(rc=1) subgemini=SKIP(health:dead:FAIL:6) subgrok=SKIP(health:dead:FAIL:3) subcursor=PASS(verdict=PASS)
  ```
  impact-risk=high requested-budget=2 selected-count=3 escalation=failure snapshot=head:fc59f17

  第 2 轮:
  ```
  submimo=PASS(verdict=PASS) subdeepseek=SKIP(rotation) subglm=SKIP(health:dead:auth:3) subkimi=SKIP(health:cooldown:rate_limit) subgemini=SKIP(health:dead:FAIL:6) subgrok=SKIP(health:dead:FAIL:3) subcursor=PASS(verdict=PASS)
  ```
  impact-risk=high requested-budget=2 selected-count=2(xiaomi / xai 两个家族)

  覆盖轮(第 3 次派发):
  ```
  submimo=PASS(verdict=PASS) subdeepseek=SKIP(rotation) subglm=SKIP(health:dead:auth:3) subkimi=SKIP(health:cooldown:rate_limit) subgemini=SKIP(health:dead:FAIL:6) subgrok=SKIP(health:dead:FAIL:3) subcursor=PASS(verdict=PASS)
  ```
  覆盖轮(第 4 次派发,归档所绑的就是这一次):
  ```
  submimo=PASS(verdict=PASS) subdeepseek=SKIP(rotation) subglm=SKIP(health:dead:auth:3) subkimi=SKIP(health:cooldown:rate_limit) subgemini=SKIP(health:dead:FAIL:6) subgrok=SKIP(health:dead:FAIL:3) subcursor=PASS(verdict=PASS)
  ```
  两次都是 impact-risk=high requested-budget=2 selected-count=2(xiaomi / xai)
  subkimi 的 403 是**周额度未重置**(不是腿坏),工具自动补了 subcursor ⇒ 两个合格家族
  (deepseek / xai)覆盖满足。
- 轮次记录(每次派发一行;实质评审与基础设施重试分开):

  | 轮 | 类型 | 派发前 `track preflight` | 日志前缀 | 新增有效阻断 |
  |---|---|---|---|---|
  | 1 | 实质 | rc=3,BLOCK=0(PENDING=2:收据引用/裁决未写) | `panel-b8-forensics-20260921-0221` | 6 |
  | — | 基础设施(subkimi 403 周额度,rc=1;工具当轮自动补 subcursor,未另行派发) | 同上 | 同上 | 0 |
  | 2 | 实质(核验第 1 轮修复清单;**预算用尽**) | rc=3,BLOCK=0(PENDING=2 同上) | `panel-b8-forensics-r2-20260921-0245` | 3(F8/F9/F10) |
  | 3 | **覆盖轮(不是第 3 轮实质评审)** | rc=1,唯一 BLOCK 就是"要重跑 panel"本身 | `panel-b8-forensics-r3-20260921-0325` | 1(L2,我自己把它从 LOW 提成必须修) |
  | 4 | **覆盖轮(同上,机械门)** | rc=1,唯一 BLOCK 就是"要重跑 panel"本身 | `panel-b8-forensics-r4-20260921-0353` | 0(两腿都说没有必须修级别的发现) |

  > 第 3 次派发的**具体理由**(4b ④ 要求派发前写明):第 2 轮的三条一次修完之后,
  > 交付内容与第 2 轮 panel 绑定的那份不再一致,归档闸机械判 BLOCK
  > (`qualifying same-run review bound to this delivery; rerun panel-review after content changes`)。
  > **目的**:给修好之后的内容一个合格覆盖,顺带核验 F8/F9/F10 三条修复。
  > **新的有限预算**:1 次派发,不为"再确认一下"续轮。
  > 🔴 收尾决定 ≠ 归档资格:主裁写得再有理,也不会让旧覆盖重新有效 —— 这一轮是机械门,
  > 不是我改了主意。

- findings(**先处置、后动手**;一轮一份修复清单,一次修完再复审):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | F1 | **两腿独立命中(MEDIUM)**。`ss` 与 `lsof` 都拿不到 pid 时 `listener_pids` 返回空集,与"查不出"不可区分 ⇒ `foreign = 全部应答者` ⇒ 结论句把**真产品缺陷**写成"判据环境脏"。受害的正是"两份都赢"——b8 存在的理由。 | 我自己复现:`PATH=/nonexistent` 跑 r2d,取证把本轮 pid 3650136/3650137 列成环境残留,而同一份现场里 `who_listens` 已诚实地说"查不出是谁"。夹具版红收据 `before-f1-fix-r2d-no-tools.txt` | **必须修** | 与 S1 是同一个病,只换了触发条件;本单的交付承诺就是"当场分型",分型说反话 = 本次验收不成立。 |
  | F2 | **两腿命中(LOW)**。`who_listens` 只看 stdout、不看 returncode,第一支工具挂掉就返回"这个端口上没有 LISTEN",也不回落到 lsof ⇒ 笃定的假话。 | 我自己复现:假 `ss`(rc=1 + stderr)下 `who_listens -> <ss:这个端口上没有 LISTEN>`,而同端口 `listener_pids -> {3650251}` 是对的。 | **必须修** | design 明写"取不到就说清为什么取不到",这里说的是"没人";与 F1 同一处修复,成本几乎为零。 |
  | F3 | **subdeepseek(LOW)**。`SHAPES` 只对 r2d 钉了"开出两个窗口",0 份赢那三条一个分型锚点都没有 ⇒ 把结论句硬写成一支,全套红检照样"形状=对"。 | 我自己复现:变异后 r2a/r2b 印"形状=对";补 `ONE_WINDOW`/互禁锚点后当场抓住(`before-f1-fix-f3-mutant.txt`)。 | **必须修** | 这正是我题面第 5 问要的那种变异:**改坏了判据而夹具通过**。夹具是判据的判据,漏了它,本单其余收据的分量都要打折。 |
  | F4 | **两腿命中(LOW)**。design.md 写前置断言是 connect 探测"一个监听者都没有"、降级读 `/proc/net/tcp`;实现是**协议级握手**探测 + `ss`/`lsof`。 | design.md:53/65/68 对 `tests/test_ds_shell_core.py::lock_responders_in`、`who_listens`。 | **必须修** | 文档写的不是它跑的东西。实现这一版更好(陌生程序占位不误红),但**没写下来就等于下一个人会按旧文本改**;而 `/proc` 那句承诺的降级至今不存在,正是 F1 的成因之一。 |
  | F5a | **subdeepseek(LOW)**。没有任何红检会因为删掉"每轮收赢家"而变红;r3 靠跑 6 轮,而跨轮污染概率约 0.02%/轮,三遍根本抓不到。 | `probes/redcheck.py` 无对应情景;`crossround.py` E3 把 span 放到 3000 才稳定复现(放大模型)。 | **延期** | 它在下一个使用者那边长成:有人删掉 reap ⇒ b8 偶发红(~0.3%/次),**但红出来会落在前置断言上并当场说清"判据环境脏"** —— 前置断言本身就是 reap 失效的兜底,不再是 09-20 那种分不出病因的红。要钉它得造放大 span 的专用情景,那是"挡住任意未来的错误实现",按 4b 默认延期。 |
  | F5b | **subdeepseek(LOW)**。09-20 那条读数的同形来源不止"本用例跨轮残留",开发机上真在跑的 OpenDesign 实例同样造得出。 | `_acquire` 扫描命中分支 `self.port = hit` ⇒ 两份同值;该分支不关心应答者是谁起的。 | **必须修**(措辞) | 我的 design 前提 4 只写了"进程里任何还活着的赢家",少了"外来实例"这一支;收口时若照旧措辞,就成了一句证据不足的话。已改写为"段内确有一个真应答者;自留还是外来,证据已失"。 |
  | F6 | **subcursor(LOW)**。`redcheck.py` 注释断言 r2a"两份 port **不同值**",而 `after-s1-fix-r2a.txt` 里两份都是 46135。 | 收据 vs 注释;真实机制是后起的那份 `_scan` 命中了先起的那份 ⇒ 走扫描命中分支 ⇒ 同值。 | **必须修** | 这句假话就长在"同值/不同值能不能分辨病因"那条推理链上 —— 留着会污染下一次对同形读数的判读。 |
  | F7 | **subcursor(LOW)**。红检不在 `tests/run-all.sh` 里,只有人手动重跑 `run-redchecks.sh` 才会发现锚点措辞漂移。 | `tests/run-all.sh` 的六段里没有它。 | **延期** | 漂移是 **fail-closed**(rc=1),不是静默失效;把"判据的判据"常驻化是另一件事(本仓已有"泄漏闸自测"这一先例,可照着做),超出本单射程「b8 红的时候留下现场」。留在这里,不自动开单。 |

  | S12 | **我自己在写 r2 自审时发现的(记账,不修)**:`race_forensics` 的结论句让 `unknown` 压过 `foreign` —— 段内同时有"确认是外人"和"查不出"的格子时,明明已经够判"判据环境脏"了,它仍然说"先别下结论"。 | `tests/test_ds_shell_core.py` 结论句分支:`if unknown: … else: …`。 | **延期(过度保守,方向安全)** | 错的方向是**多跑一遍**(去装上工具再来),不是说反话;而造这个场景要同时摆一个外来真锁并藏掉两个工具,脚手架成本高于收益。写在这里,请第 2 轮的腿挑。 |

  **第 2 轮(核验修复清单)**:两腿(submimo / subcursor)都判 PASS 并逐条确认第 1 轮
  7 条处置无误(该修的没判成延期、该驳回的没被修),S12 / F5a / F7 三条延期两腿都认可。
  subcursor 另报 3 条,**其中一条是我自己这轮修出来的回归**:

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | F8 | **subcursor(MEDIUM)**。我修 F2 时**判得太宽**:`_tool_out` 只要 `rc≠0` 就把 stdout 丢掉,而 `lsof` 在"没有匹配"时**正常** exit 1,容器里还会一边报 `/proc` 警告一边照常打印结果 ⇒ 明明查得到 pid 却回 `None` ⇒ 取证退回"查不出、先别下结论"。**正好废掉 S1/F1 修出来的那条降级路径。** | 我自己实测:`lsof -t -nP -iTCP:59999 -sTCP:LISTEN` rc=1,`ss` 同情形 rc=0。它给的证据是我自己的收据:同一份 r2d-no-ss,修 F2 前印 `<lsof:这个端口上没有 LISTEN>`,修后变成 `<ss:没装;lsof:rc=1 >`。夹具版红收据 `before-f8-fix-r2d-flaky-lsof.txt`(形状=错) | **必须修** | **本次引入的回归**(4b 第一档)。判定改三档:有 stdout ⇒ 那就是答案;stdout 空 + rc≠0 + stderr 有话 ⇒ 工具挂了,问下一支;其余 ⇒ 确实没人。取舍写进代码注释:静默失败(rc≠0 且 stderr 也空)会被读成"没人",而两个工具都不这么失败。 |
  | F9 | **subcursor(LOW,覆盖洞)**。`r2a`/`r2d` 的 forbid 里没有 `NO_VERDICT` ⇒ 在正常分型句旁边**顺手也印一句"先别下结论"**,全套红检照样通过。 | `probes/redcheck.py` 的 SHAPES。 | **必须修** | 那会让"先别下结论"这个逃生口变成常驻装饰 —— 查得出归属的时候就得把型分出来。 |
  | F10 | **subcursor(LOW,覆盖洞)**。F2 只有一次性探针收据(`after-f1-fix-f2-probe.txt`),没有红检钉子:把 F2 整个 revert 掉,8 个情景照样 rc=0。 | 我自己复现:revert 掉 `_tool_out` 的 rc 检查,旧的 8 情景全绿。 | **必须修** | 补 `r2d-broken-ss`;🔴 **只钉分型的话它是空转的**(`listener_pids` 本来就会落到 lsof),所以锚点钉在**打印给人看的那句假话**上。对照收据 `before-f8-fix-revert-f2-control.txt`:变异树上当场抓住。 |
  | S13 | **记账(不是发现)**:submimo 的报告里写"全量回归 100 passed / 2 skipped"。 | 实际是 python 1800 / node 461 / e2e 41,收据在 evidence。 | **驳回(事实错误)** | **MiMo 第四次在 PASS 里带事实错误**(前三次 09-16、09-20 两单)。它的结论我一条都没直接引用;本轮它的价值在逐条确认处置,而那部分我自己复核过。 |

  **覆盖轮(第 3 次派发)**:两腿(submimo / subcursor)都 PASS,都确认 F8/F9/F10 三条修复
  到位、三条延期仍然成立。subcursor 另报 3 条 LOW + 1 条 nit,**其中一条我把定级提高了**:

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | L2 | **subcursor 报 LOW,我提成必须修**。`run-redchecks.sh` 用 `grep -q "rc=0"` 判每条情景过没过,而 r2a/r2b/r2c 的取证正文里印着子进程状态「已退 rc=0」⇒ **一条形状错的情景照样被读成过**,整套报「全套 rc=0」。 | 我自己用变异坐实(`evidence/before-aggr-fix-grep-probe.txt`):把分型结论句硬写 ⇒ r2a 那份末行明明是 `# rc=1`,而 `grep -q "rc=0"` 命中第 23/24 行的「已退 rc=0」;行首锚定版不命中。 | **必须修** | 两腿都说"不是本单必须修、是原有聚合层松匹配" —— **我驳回这个定级**:这行是本单自己造的(`6e68970` 引入),而且它正是本单题眼的同构:**判据的判据被自己的输出骗了**。我的主裁不依赖它(10 条形状行我逐条看过),但下一个只看汇总行的人会被骗。修法一行:`grep -q '^# rc=0'`。 |
  | L1 | **subcursor LOW = 我自审的 S14**:`FLAKY_LSOF` 硬编码 `/usr/bin/lsof`,换台机器这个情景会退化。 | 两腿独立确认失效是 **fail-closed**(夹具当场红,不是假绿)。 | **修了**(顺手) | 本来判"不修",但 L2 已经要动这两个文件、指纹反正要变;改成 `command -v lsof` 查一次,省下一次噪音。 |
  | L3 | **subcursor LOW**:`design.md` 的 oracle 段仍写"8 个情景",实际已是 10。 | design.md vs `run-redchecks.sh`。 | **修了** | 与 F4 同类(文档写的不是它跑的东西),而且是本轮刚加的两条造成的。 |
  | nit | **subcursor**:`who_listens` 里旁注还写"rc≠0 ⇒ 这不是答案",F8 之后"有 stdout 的 rc≠0"已经是答案。 | `tests/test_ds_shell_core.py`。 | **修了** | 留着会误导下一个人把第一档改回去 —— 那正好是 F8 那个回归的复发路径。 |
  | S15 | **记账**:submimo 的报告里又写"测试套件 100 passed / 2 skipped"。 | 实际 python 1800 / node 461 / e2e 41。 | **驳回(事实错误)** | 与第 2 轮同一句、同一个错 ⇒ **MiMo 第五次在 PASS 里带事实错误**。它这轮的实测部分(三档判定、F2 没被放回、假工具 fail-closed)我自己复核过才采信。 |

  **覆盖轮(第 4 次派发)**:两腿都 PASS,**没有必须修级别的发现**。
  subcursor 逐条核了四处改动没碰坏 10 个情景与 b8 本身,并指出聚合层剩下的缺口
  (不钉末行、`$` 不锚)要"以后再往正文里印一行 `# rc=0`"才骗得过 ⇒ 属于
  「挡不住任意未来的错误实现」那一类,不升必须修 —— 我同意。
  三条延期(S12 / F5a / F7)这一轮仍然成立,两腿各自对着现码复核过。
  submimo 这一轮引用的数字对上了(1800 / 461 / 41 / source-stable: yes)。

  > 两腿都给了 `Conclusion: PASS`,**我不拿它抬置信度**:F1 是两腿独立命中的同一条,
  > 而它恰好是本单核心承诺(当场分型)的反面 —— 全票 PASS 里藏着一条必须修的发现,
  > 正好是"一致 PASS 不等于题是对的"的实证。
- arbitrated verdict (主裁): **PASS**。
  - 交付承诺兑现:b8 红的那一刻能**当场分型**,10 个红检情景钉住了「红在哪条断言上」
    「取证认没认出自己」「分型结论句落在哪一支」三件事,全套 rc=0;
    修前的红收据一份没藏(`baseline-old-b8-*` / `before-s1-fix-*` / `before-f1-fix-*` / `before-f8-fix-*`)。
  - 断言**严格更强**(段内本来无人 **且** 恰好 1 份赢),四种真产品缺陷 + 第三种长相
    (两份都赢)全部仍然抓得住;两腿各自用独立变异复跑确认过检测力没丢。
  - 产品代码零改动,业主那边行为不变、不用装。
  - **轮次预算用尽(2 轮实质),不追加实质评审轮**;第 3、4 次派发是**覆盖轮**
    (归档闸要求:内容改了就得有一次绑得上的评审),不是我改了主意要再挑一遍。
    第 3 次覆盖轮抓到 L2 并被我提成必须修 —— 这说明覆盖轮不是走过场,但它**不改变**
    "不为再确认一下而续轮"这条纪律:修完之后,除非再出现必须修级别的发现,不再动任何东西:第 2 轮的三条(F8/F9/F10)已一次修完,
    修复面窄(一个函数的三档判定 + 夹具锚点),而且**每条都有新红检或对照实验钉住**,
    最后一遍 `--final` 总跑 `source-stable: yes`。按 4b ④「默认不续轮」,
    再审一轮就是 09-16 业主拍板的"没完没了"。
  - 未解决项如实留着:S12(结论句让 unknown 压过 foreign,过度保守)、F5a(reap 没钉子)、
    F7(红检不进总跑)—— 三条延期两腿都认可,**不自动开新单**。
  - 这份 oracle 是我自己写的、可能本身就错:它跑在 Linux/回环 socket 上,
    **不承诺** Windows 双击两下的结果,也不拿本单的绿给真机背书。

## Accepted deviations

- b8 不验证输家有没有把赢家叫到前台(marker 文件),b2/b4 验了。本单题面是"只许一份赢",
  不扩;记在这里(自审 S5)。
- `mine = {p.pid for p in procs}` 不按存活过滤:pid 复用理论上会把外人认成自己。
  概率极低,且加存活过滤会把"刚退出的自己"算成外来残留——方向反过来、概率更高(自审 S8)。

## 试行记录(review-convergence 试行,约五单)

- 总交付历时:开工 `36d9ddd`(2026-09-21 08:40 +0800)→ 归档 commit(待填)
- 每轮新增有效阻断:第 1 轮 6(F1/F2/F3/F4/F5b/F6);第 2 轮 3(F8/F9/F10,其中 F8 是我自己修 F2 时引入的回归)
- 基础设施等待:subkimi 1 次失败(403 周额度);第 1 轮 panel 约 11 分钟(10:18→10:29),第 2 轮约 6 分钟(11:00→11:06)
- 交付后返工:unknown
