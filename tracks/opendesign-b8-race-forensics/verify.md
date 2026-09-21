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
```
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
  subkimi 的 403 是**周额度未重置**(不是腿坏),工具自动补了 subcursor ⇒ 两个合格家族
  (deepseek / xai)覆盖满足。
- 轮次记录(每次派发一行;实质评审与基础设施重试分开):

  | 轮 | 类型 | 派发前 `track preflight` | 日志前缀 | 新增有效阻断 |
  |---|---|---|---|---|
  | 1 | 实质 | rc=3,BLOCK=0(PENDING=2:收据引用/裁决未写) | `panel-b8-forensics-20260921-0221` | 6 |
  | — | 基础设施(subkimi 403 周额度,rc=1;工具当轮自动补 subcursor,未另行派发) | 同上 | 同上 | 0 |

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

  > 两腿都给了 `Conclusion: PASS`,**我不拿它抬置信度**:F1 是两腿独立命中的同一条,
  > 而它恰好是本单核心承诺(当场分型)的反面 —— 全票 PASS 里藏着一条必须修的发现,
  > 正好是"一致 PASS 不等于题是对的"的实证。
- arbitrated verdict (主裁): <第 2 轮复审后写>

## Accepted deviations

- b8 不验证输家有没有把赢家叫到前台(marker 文件),b2/b4 验了。本单题面是"只许一份赢",
  不扩;记在这里(自审 S5)。
- `mine = {p.pid for p in procs}` 不按存活过滤:pid 复用理论上会把外人认成自己。
  概率极低,且加存活过滤会把"刚退出的自己"算成外来残留——方向反过来、概率更高(自审 S8)。

## 试行记录(review-convergence 试行,约五单)

- 总交付历时:开工 `36d9ddd`(2026-09-21 08:40 +0800)→ 归档 commit(待填)
- 每轮新增有效阻断:第 1 轮 6(F1/F2/F3/F4/F5b/F6);第 2 轮 <待填>
- 基础设施等待:subkimi 1 次失败(403 周额度);panel 总耗时约 11 分钟(10:18→10:29)
- 交付后返工:unknown
