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

第 1 轮修复(处置表 Q1 Q2 R2 R3)—— 判据先行:4 条新断言在修复前的实现上红(红在正点上:Q1 / Q2 / R2 / R3 各一条),单独提交 `8417650`;
修复 `49a669a` 后变异补 M14–M18,整套 18/18 咬住:

```
runlog: r1-fix-oracle-red rc=1 commit=cb007f0 dirty=yes at=2026-09-25T06:33:57Z file=tracks/opendesign-chat-error-visible/evidence/20260925T063357Z-01-r1-fix-oracle-red.txt
runlog: mutation-chat-model-error-r1fix rc=0 commit=49a669a dirty=no at=2026-09-25T06:35:26Z file=tracks/opendesign-chat-error-visible/evidence/20260925T063526Z-01-mutation-chat-model-error-r1fix.txt
```

总跑(第 1 轮修复 + 录像第 2 遍之后,第 2 轮评审前;rc=3 只跳既有三条要真网关的,node 544 / python 1553 / e2e 43 PASS 0 FAIL):

```
runlog: run-all-r1fix rc=3 commit=5dc28d8 dirty=no at=2026-09-25T06:41:00Z file=tracks/opendesign-chat-error-visible/evidence/20260925T064100Z-01-run-all-r1fix.txt
```

## QA(测试员;不计评审轮)

- QA 设计(开发前,黑盒):Grok `evidence/20260925-qa-design-subcursor.grok-4.7-high.md`(26 条用例,采为执行底稿);DeepSeek `evidence/20260925-qa-design-subdeepseek.md`
  (违反黑盒读了代码、没按格式,只采两条:原文 key 打码、「看得出是出错」要可断言)。花名册 `evidence/20260925-qa-design.roster`。
- QA 执行第 1 遍:真管家 + 真 nanobot 网关 + 真工作台 + 真 chromium,假厂商按步骤切回法(报错体 = 探针真原文),17 步 `evidence/qa-exec/tour.md` + 截图。
  录像脚本自己栽过两次(只改 `#` 不重载 ⇒ 项目列表没刷新;待办栏是单行框不是 textarea)—— 都是脚本错,修了重录。
- QA 判卷(两家读录像 + e2e + 总跑,题面 `evidence/20260925-qa-exec-brief.md`):DeepSeek `evidence/20260925-qa-exec-subdeepseek.md`、
  Grok `evidence/20260925-qa-exec-subcursor.grok-4.7-high.md`,花名册 `evidence/20260925-qa-exec.roster`。P0:首页五类错误、切走回来、历史回放、项目栏 / 待办栏当场 都「已执行·通过」;
  缺口与缺陷见下表 Q 行。
- QA 执行第 2 遍(第 1 轮修复后,包 = `git archive 49a669a`;提交 `5dc28d8`):整份重录 20 步全过。补 Q4:第 14 步 E8(开待办再回首页 9→9 逐条相同)、
  第 15 步 E24·D6(真重载后从侧栏点回首页这段,回放 9 条与实时逐条相同、无英文原文当正文)、第 17 步 E10b、第 19 步 E11b;
  Q1 / Q2 的新说法在第 02 / 11 / 16 / 18 步原样可见。注意第 16 步「首页不许跟着冒」基线是 0(重载后首页是新会话),只证明项目栏出错不往首页冒。
  (这一遍是断线接手后跑的:上一会话改完 tour.mjs 还没来得及跑就断了;改动核过是完整的四段补步。)

## Review

- 规格自查(读任何 panel 输出之前):自审正本在仓外 `/root/aiwork/tasks/opendesign-chat-error-visible-r1-my-review.md`(派发前落盘),结论 PASS,
  延期候选 = 代理 407 会被说成 key 错 / 整条以 `Error: ` 开头的正常回复会被改写 / 斜杠命令英文回复现在可见(下一单停止键要处理)。
  规格本身:「不点厂商名、指向右下角」是 design 里写的,**实现时把「输入框右下角」那半句漏了** —— 我的自审没发现,两家 QA 同指(Q2)。
- 腿的花名册(第 1 轮):`evidence/20260925-review-r1.roster` —— `subdeepseek=PASS(verdict=PASS)`(impact-risk=standard requested-budget=1 selected-count=1,snapshot=head:e88bed6)
- 轮次记录:

  | 轮 | 类型 | 派发前 `track preflight` | 日志前缀 | 新增有效阻断 |
  |---|---|---|---|---|
  | 1 | 实质 | rc=3,BLOCK 0(PENDING 2) | /root/aiwork/logs/panel-chaterr-r1-20260925-142541 | 0(PASS;3 条低风险,其中 2 条本单修) |
  | 2 | 实质(复审,核验修复清单;预算最后一轮)| rc=3,BLOCK 0(PENDING 1)| /root/aiwork/logs/panel-chaterr-r2-20260925-145443 | 0(PASS;Q1 Q2 Q4 R2 R3 逐条核验修好;新报 N1–N3 皆低风险)|

  第 2 轮自审(派发前落盘,仓外):`/root/aiwork/tasks/opendesign-chat-error-visible-r2-my-review.md`,结论 PASS。
  同时派 QA 复判两家(不计评审轮):`/root/aiwork/logs/explore-chaterr-qa-exec-r2-20260925-145443`。
- 腿的花名册(第 2 轮,原样):`subdeepseek=PASS(verdict=PASS)`(impact-risk=standard requested-budget=1 selected-count=1,snapshot=head:3c8e54e)
- QA 复判花名册(原样):`subdeepseek=EXPLORE(rc=0,coverage=none) subcursor.grok-4.7-high=EXPLORE(rc=0,coverage=none)`(snapshot=head:3c8e54e)。
  两家复判原文只留在 aiwork 日志(`….subdeepseek.log` / `….subcursor.grok-4.7-high.log`),**不拷进 evidence** —— 第 2 轮之后再往 evidence 加文件会作废这一轮的绑定。
  结论:Q1 Q2 Q4 两家都判「修好」(第 02 / 11 / 14 / 15 / 17 / 19 步原文为证);Q3 两家都判「没修好、不同意延期」;Q5 两家都判「录像看不出」、同意不在本单修但要有落点。

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

- findings(第 2 轮评审 + QA 复判;预算已用完,只有真阻断才会让本单保持未完成):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | Q3′ | (QA 复判两家同指,DeepSeek 标 P1)Q3 的延期不成立:欠费那条小字标「原文」,内容却是网关换过的固定英文;同页 GLM 那条又是真原文,真假混在同一位置 | 属实:`modelError.ts` 的 FIXED 表就认得这句(`ARREARS`,nanobot `agent/runner.py:59-64`);探针 raw deepseek-402 厂商真回的是 `Insufficient Balance` | **维持延期(主裁否决两家意见),落点改成硬的** | 两家说的**属实**:标签确实名不副实,这是缺陷,不是规格允许的。(交接更正:断线前这里写过「design 第 12 行把原文定义成聊天服务交给界面的那句话」—— design.md 里**没有这句**,第 12 行只写「原文小字」;接手核对时删掉这条假引用,理由只剩下面三条。)不挡本单的理由:① 本单的承诺是「不许指错门」,这条主句把人指去看余额 / 充值,**方向对**;② 小字内容本身说清了是额度 / 欠费问题,业主不读英文小字,截给我或转给厂商都不会看反;③ 预算 2 轮已用完,修它要第 3 轮,按 4b 只有真阻断才开,它不是。落点:**下一单(输入框)必须改**(那单本来就动聊天页,且 R1 也要它把 `/stop` 等英文句译成中文):FIXED 表认出的固定句,小字标签不再叫「原文」(改成「聊天服务的说法」之类),真透传的仍叫「原文」;判据先行 |
  | D2 | (QA 复判 DeepSeek,P2)key 错那句写「右下角显示的是**现在**选的模型」,出错后换过模型再回看,右下角已不是当时那家;设置页写厂商名、右下角写模型名,对不上号 | 文本层面推演,录像没走「出错后换模型」 | 驳回 | 句子字面是对的(括号说明的正是「现在选的」,没冒充「当时那家」);厂商名与模型名对不上号正是 0.98.14 第二件(输入框)第 3 条「模型按钮前带厂商名」要改的 |
  | D3 | (QA 复判 DeepSeek,P2 文案)认不出的错那句对所有这类错都提「带了图的话先去掉图」,这轮没带图也提 | 第 11 步原文 | 驳回 | 条件句,不指错门;Q1 修复的本意就是给图片被拒这条最常见的路一个出口 |
  | N1 | (评审 N1)助手**整条**回复恰好就是 `Error: {…}` 形状时会被改写成出错说明 | `modelError.ts` 整条判等;第 1 轮自审已列延期候选 | 接受偏差(见下) | 要业主让助手「原样念一句报错」且整条就是壳形才碰到;代价是那一条显示成出错说明,原文仍在小字里 |
  | N2 | (评审 N2)代理侧超时(原文带 proxy)会说成「连不上」而不是「超时」 | `/proxy/` 排在 timeout 前 | 驳回 | 两句给业主的下一步几乎一样(查网络 / 稍后再试),不错指 |
  | N3 | (评审 N3)bedrock 连不上也拼 `Error: `、codex 的 `Error calling Codex (…)` 不在前缀里 | nanobot `bedrock_provider.py:641,661`、`openai_codex_provider.py:278`;我抽查 `providers/factory.py` 路由 + `config/nanobot.config.jsonc` 无 fallback | 驳回 | 业主可选的五家 + 自定义全走 openai_compat,这两条路径不可达 |
  | Q5′ | (QA 复判两家)Q5 驳回要有落点:侧栏历史只列 2 条,业主先聊了项目,首页那段就从侧栏挤掉、点不回去 | `web/src/workspace/Sidebar.tsx:99` | 维持驳回,**落点写明** | 0.98.14 第三件(侧栏方案一:历史看得全)就是它;那一单开工时把「出错说明要能从侧栏点回去」列进验收 |
  | 缺口 | (QA 复判两家)没执行到:E9 真走「设置 → 改 key → 测试 → 再发」;E5 超时(厂商一直不回);出错后换模型再发;带图发;转圈时切走 | tour.mjs 的回法与步骤 | 进发版真机清单 | E9 的设置页存 key / 测试是 0.98.13 已真机验过的旧路;「转圈时切走」:三个聊天栏切页只加 `route-hidden` 不卸载(`web/src/App.tsx:523/537/593`),事件照常落进同一个聊天,和留在原地同一条路 |

- arbitrated verdict (主裁): **PASS**。两轮实质评审(DeepSeek,均 PASS)+ QA 两遍录像与两次两家判卷;修复清单 Q1 Q2 Q4 R2 R3 全部落实
  (判据先行红过、变异 18/18、录像第 2 遍 20 步、修复后总跑 rc=3 只跳既有三条)。第 2 轮后没有「本单必须修」:Q3′ 两家测试员不同意延期,
  主裁否决、不挡本单(理由见上表:缺陷属实,但不指错门、小字意思对、再改就要第 3 轮;落点是下一单必须改);没有新增真实阻断,按 4b 结束。

## Accepted deviations

- N1:助手整条回复恰好是网关出错壳形(`Error: {…}` / `Error calling LLM: …`)时,会被显示成出错说明(原文仍在小字)。
- Q3 / Q3′:DeepSeek 欠费那条小字标「原文」,内容是聊天服务换过的固定英文(意思对:额度用完 / 欠费)。**下一单(输入框)必须改标签**,见上表。
- R1:无 kind 的英文系统句现在会原样上屏(`/stop` 的 “Stopped N task(s).”、子任务空回报 “Background task completed.”)。
  **下一单(输入框,停止键用 `/stop`)必须把这几句译成中文**。
- 不承诺的仍不承诺:真厂商没抓过的欠费 / 限流原文分不准时落「通用说明 + 原文」。

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:约 1 小时 45 分(13:18 立单 → 15:0x 主裁;含 14:37 断线、接手几乎无空档)
- 每轮新增有效阻断:第 1 轮 0(PASS;另有 2 条低风险本单修);第 2 轮 0(PASS)
- 基础设施等待:评审腿 第 1 轮约 6 分钟、第 2 轮约 4 分钟;QA 判卷约 8 分钟 + 复判约 5 分钟;总跑两次各约 13 分钟;无重试
- 交付后返工:unknown
