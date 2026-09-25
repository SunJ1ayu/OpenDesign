# Verify: opendesign-chat-error-visible

- Date: 2026-09-25

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

## Mechanical checks

- [x] build passes(`npm run build` = tsc -b + vite build;dist 新鲜度闸绿)
- [x] tests pass(见下收据;总跑 rc=3 只跳既有三条)
- [x] no secrets / unsafe ops(判据 / 录像全用假 key;零外网)

**机器打印的**:

判据先行,旧代码上红检(单测红在模块不存在 = 弱红,由下面的变异红检补强;e2e 前两遍红在**台面**上 —— 第 1 遍在空输入框上等发送键、第 2 遍没 key 被带去设置页,第 3 遍才红在正点上):

```
runlog: oracle-unit-red-on-old rc=1 commit=180782d dirty=yes at=2026-09-25T05:39:00Z file=tracks/opendesign-chat-error-visible/evidence/20260925T053900Z-01-oracle-unit-red-on-old.txt
runlog: oracle-settings-d7-red-on-old rc=1 commit=180782d dirty=yes at=2026-09-25T05:39:00Z file=tracks/opendesign-chat-error-visible/evidence/20260925T053900Z-02-oracle-settings-d7-red-on-old.txt
runlog: e2e-chat-model-error-red-on-old rc=1 commit=180782d dirty=yes at=2026-09-25T05:39:17Z file=tracks/opendesign-chat-error-visible/evidence/20260925T053917Z-01-e2e-chat-model-error-red-on-old.txt
runlog: e2e-chat-model-error-red-on-old-2 rc=1 commit=180782d dirty=yes at=2026-09-25T05:40:02Z file=tracks/opendesign-chat-error-visible/evidence/20260925T054002Z-01-e2e-chat-model-error-red-on-old-2.txt
runlog: e2e-chat-model-error-red-on-old-3 rc=1 commit=180782d dirty=yes at=2026-09-25T05:46:40Z file=tracks/opendesign-chat-error-visible/evidence/20260925T054640Z-01-e2e-chat-model-error-red-on-old-3.txt
```

变异红检(每条只弄坏一处、核对红在该红的那一问;前两遍 M12 是**变异本身**没编译过 —— `false ? (…)` / `m.modelError && false ? (…)` tsc 都报 possibly undefined —— 不是判据漏网):

```
runlog: mutation-chat-model-error rc=1 commit=50accdc dirty=yes at=2026-09-25T05:52:23Z file=tracks/opendesign-chat-error-visible/evidence/20260925T055223Z-01-mutation-chat-model-error.txt
runlog: mutation-chat-model-error-2 rc=1 commit=50accdc dirty=yes at=2026-09-25T05:53:03Z file=tracks/opendesign-chat-error-visible/evidence/20260925T055303Z-01-mutation-chat-model-error-2.txt
runlog: mutation-chat-model-error-3 rc=0 commit=50accdc dirty=yes at=2026-09-25T05:53:47Z file=tracks/opendesign-chat-error-visible/evidence/20260925T055347Z-01-mutation-chat-model-error-3.txt
```

总跑(第 1 轮评审前):

```
runlog: run-all rc=3 commit=ab86b21 dirty=no at=2026-09-25T05:55:25Z file=tracks/opendesign-chat-error-visible/evidence/20260925T055525Z-01-run-all.txt
```

## QA(测试员;不计评审轮)

- QA 设计(开发前,黑盒):Grok `evidence/20260925-qa-design-subcursor.grok-4.7-high.md`(26 条用例,采为执行底稿);DeepSeek `evidence/20260925-qa-design-subdeepseek.md`
  (违反黑盒读了代码、没按格式,只采两条:原文 key 打码、「看得出是出错」要可断言)。花名册 `evidence/20260925-qa-design.roster`。
- QA 执行第 1 遍:真管家 + 真 nanobot 网关 + 真工作台 + 真 chromium,假厂商按步骤切回法(报错体 = 探针真原文),17 步 `evidence/qa-exec/tour.md` + 截图。
  录像脚本自己栽过两次(只改 `#` 不重载 ⇒ 项目列表没刷新;待办栏是单行框不是 textarea)—— 都是脚本错,修了重录。
- QA 判卷(两家读录像 + e2e + 总跑,题面 `evidence/20260925-qa-exec-brief.md`):DeepSeek `evidence/20260925-qa-exec-subdeepseek.md`、
  Grok `evidence/20260925-qa-exec-subcursor.grok-4.7-high.md`,花名册 `evidence/20260925-qa-exec.roster`。P0:首页五类错误、切走回来、历史回放、项目栏 / 待办栏当场 都「已执行·通过」;
  缺口与缺陷见下表 Q 行。

## Review

- 规格自查(读任何 panel 输出之前):自审正本在仓外 `/root/aiwork/tasks/opendesign-chat-error-visible-r1-my-review.md`(派发前落盘),结论 PASS,
  延期候选 = 代理 407 会被说成 key 错 / 整条以 `Error: ` 开头的正常回复会被改写 / 斜杠命令英文回复现在可见(下一单停止键要处理)。
  规格本身:「不点厂商名、指向右下角」是 design 里写的,**实现时把「输入框右下角」那半句漏了** —— 我的自审没发现,两家 QA 同指(Q2)。
- 腿的花名册(第 1 轮):`evidence/20260925-review-r1.roster` —— `subdeepseek=PASS(verdict=PASS)`(impact-risk=standard requested-budget=1 selected-count=1,snapshot=head:e88bed6)
- 轮次记录:

  | 轮 | 类型 | 派发前 `track preflight` | 日志前缀 | 新增有效阻断 |
  |---|---|---|---|---|
  | 1 | 实质 | rc=3,BLOCK 0(PENDING 2) | /root/aiwork/logs/panel-chaterr-r1-20260925-142541 | 0(PASS;3 条低风险,其中 2 条本单修) |

- findings(QA 判卷 + 第 1 轮评审,一份修复清单;**先处置、后动手**):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | Q1 | (QA 两家同指)认不出的错叫人去点「测试」并说「它会告诉你具体哪里不对」—— 图片被拒这类错,测试只会说连接成功 | 录像第 11 步;「测试」= 直连厂商发 hi(`bin/ds_credential.py` test_model),测不出图片/请求内容问题 | 本单必须修 | 说假话、把人指去白跑一趟;改成「先确认这家还能用」+ 带图先去图 |
  | Q2 | (QA 两家同指)key 错那句只说「发这句时用的那家」,没指到输入框右下角(屏上唯一能对号的线索) | 录像第 02 步 / 截图;design.md Approach 3 写了「输入框右下角是现在选的模型」,`modelError.ts` TEXT.auth 漏了 | 本单必须修 | 本单承诺 1(说清去哪儿)不成立一半;是实现偏离规格 |
  | Q3 | (QA DeepSeek)DeepSeek 欠费时小字标「原文」,其实是网关改写过的固定英文 | 探针 raw deepseek-402 vs mode=429q:网关只给前端那句固定英文 | 延期 | 在业主那边:他把小字截给我排查时我认得这句(网关源码 runner.py:60);他不会转给厂商。改名「原文」为别的词不增加信息 |
  | Q4 | (QA Grok)录像第 16 步「重开后点回最早那段」其实点进了待办那段;E8(开待办再回首页)、E10/E11(项目栏 / 待办栏切走再回)、D6(每类错误回放)没走 | `tour.mjs` 第 16 步按「不是项目那段」取第一行;侧栏历史只列 2 条 | 本单必须修(录像脚本,非产品) | 这几步是 QA 设计 P0,判据够不着;补进录像重录 |
  | Q5 | (QA Grok)重开后首页那段对话从侧栏历史不见了 | `web/src/workspace/Sidebar.tsx:99` 历史只显示最近 2 条,「全部」未实现 —— 与本单无关 | 驳回 | 老问题,正是 0.98.14 第三件(侧栏方案一)要改的 |
  | R1 | (评审 F1)斜杠命令英文回复(`/stop` 的 “Stopped N task(s).”)、子任务无正文时的 “Background task completed.”、fallback 熔断句现在会原样上屏 | nanobot `command/builtin.py:133`、`agent/loop.py:1228`(`_process_system_message`,子任务回报且助手一字没回时)| 延期 | 在业主那边:他不打斜杠命令;子任务空回报罕见。**下一单(输入框停止键用 `/stop`)必须把这几句译成中文** —— 写进交接 |
  | R2 | (评审 F2)代理 407「proxy authentication required」被说成 key 不对;厂商 502「failed to establish upstream connection」被说成查网络 | 评审用真函数跑出;`modelError.ts` RULES 顺序 | 本单必须修 | 指错门正是本单承诺里「不许错指」;修法有原则:厂商回了报错体 = 连得上,「连不上」只认网关自己的 `Error calling …` 壳;代理字眼先于 key |
  | R3 | (评审 F3)打码没覆盖 GLM `<id>.<secret>` 形状与 `api_key=` 写法 | `maskKeys` 只认 sk-/tp-/ak-/pk-/rk-/Bearer | 本单必须修 | key 进界面属安全面;修法便宜(两条正则) |

- arbitrated verdict (主裁): <第 2 轮后写>

## Accepted deviations

- <待写>

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:<待写>
- 每轮新增有效阻断:第 1 轮 0(PASS;另有 2 条低风险本单修)
- 基础设施等待:<待写>
- 交付后返工:unknown
