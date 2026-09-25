# Verify: opendesign-composer-zcode

- Date: 2026-09-25

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

## Mechanical checks

- [x] build passes(`npm run build`,tsc 无错;产物新鲜度闸 `tests/e2e/check-dist-fresh.sh` 逐字节一致)
- [x] tests pass(最终总跑 `run-all-final` rc=3:只跳既有三条 —— 两条要真网关的 e2e + python 1 条;node 565、python 1553、e2e 44 全过)
- [x] no secrets / unsafe ops(纯前端;/stop 走网关自带命令;不改 nanobot)

**机器打印的收据行**(判据先行的红检、变异红检、修复前后):

```
runlog: oracle-unit-red-on-old rc=1 commit=3b1a9eb dirty=yes at=2026-09-25T08:55:01Z file=tracks/opendesign-composer-zcode/evidence/20260925T085501Z-01-oracle-unit-red-on-old.txt
runlog: e2e-composer-red-on-old rc=1 commit=3b1a9eb dirty=yes at=2026-09-25T08:55:02Z file=tracks/opendesign-composer-zcode/evidence/20260925T085502Z-01-e2e-composer-red-on-old.txt
runlog: e2e-model_picker-changed-red-on-old rc=1 commit=3b1a9eb dirty=yes at=2026-09-25T08:57:07Z file=tracks/opendesign-composer-zcode/evidence/20260925T085707Z-01-e2e-model_picker-changed-red-on-old.txt
runlog: e2e-frontend_p2_polish-changed-red-on-old rc=1 commit=3b1a9eb dirty=yes at=2026-09-25T09:00:59Z file=tracks/opendesign-composer-zcode/evidence/20260925T090059Z-01-e2e-frontend_p2_polish-changed-red-on-old.txt
runlog: e2e-chat_reconnect-changed-red-on-old rc=1 commit=3b1a9eb dirty=yes at=2026-09-25T09:01:02Z file=tracks/opendesign-composer-zcode/evidence/20260925T090102Z-01-e2e-chat_reconnect-changed-red-on-old.txt
runlog: oracle-rawlabel-red-on-old rc=1 commit=b8a7f85 dirty=yes at=2026-09-25T09:07:35Z file=tracks/opendesign-composer-zcode/evidence/20260925T090735Z-01-oracle-rawlabel-red-on-old.txt
runlog: mutation-composer-zcode rc=1 commit=4d57d9c dirty=yes at=2026-09-25T09:09:06Z file=tracks/opendesign-composer-zcode/evidence/20260925T090906Z-01-mutation-composer-zcode.txt
runlog: mutation-composer-zcode-r2 rc=0 commit=4d57d9c dirty=yes at=2026-09-25T09:12:40Z file=tracks/opendesign-composer-zcode/evidence/20260925T091240Z-01-mutation-composer-zcode-r2.txt
runlog: oracle-chip-vendor-misfiled-red rc=1 commit=52004ef dirty=yes at=2026-09-25T09:19:52Z file=tracks/opendesign-composer-zcode/evidence/20260925T091952Z-01-oracle-chip-vendor-misfiled-red.txt
runlog: mutation-composer-zcode-z19 rc=0 commit=a2b2bbf dirty=yes at=2026-09-25T09:20:46Z file=tracks/opendesign-composer-zcode/evidence/20260925T092046Z-01-mutation-composer-zcode-z19.txt
runlog: r1fix-oracle-unit-red rc=1 commit=58cf9c3 dirty=yes at=2026-09-25T09:39:30Z file=tracks/opendesign-composer-zcode/evidence/20260925T093930Z-01-r1fix-oracle-unit-red.txt
runlog: r1fix-oracle-e2e-red rc=1 commit=58cf9c3 dirty=yes at=2026-09-25T09:39:41Z file=tracks/opendesign-composer-zcode/evidence/20260925T093941Z-01-r1fix-oracle-e2e-red.txt
runlog: mutation-composer-zcode-r1fix rc=1 commit=dfb6aa7 dirty=yes at=2026-09-25T09:42:07Z file=tracks/opendesign-composer-zcode/evidence/20260925T094207Z-01-mutation-composer-zcode-r1fix.txt
runlog: mutation-composer-zcode-all-after-r1fix rc=0 commit=dfb6aa7 dirty=yes at=2026-09-25T09:43:06Z file=tracks/opendesign-composer-zcode/evidence/20260925T094306Z-01-mutation-composer-zcode-all-after-r1fix.txt
runlog: run-all-r1fix rc=1 commit=d1e263f dirty=no at=2026-09-25T09:49:04Z file=tracks/opendesign-composer-zcode/evidence/20260925T094904Z-01-run-all-r1fix.txt
runlog: e2e-narrow_window-after-locator rc=0 commit=d1e263f dirty=yes at=2026-09-25T10:03:36Z file=tracks/opendesign-composer-zcode/evidence/20260925T100336Z-01-e2e-narrow_window-after-locator.txt
runlog: run-all-final rc=3 commit=0f0bc49 dirty=no final=yes at=2026-09-25T10:09:53Z file=tracks/opendesign-composer-zcode/evidence/20260925T100953Z-01-run-all-final.txt
```

- 两份收据**作废、已删**(没进 git):09:00 前我单独跑 `frontend_p2_polish` / `chat_reconnect` 的红检时没给假家目录(总跑 `tests/e2e/run-all.sh` 会造 `E2E_HOME` 放一把假 key),
  两份都红在连接 / 项目列表这种与本单无关的地方;在干净副本里跑提交里的原版同样红 ⇒ 是我跑法错,不是产品或判据的红。带上假家目录重跑的两份(`…090059Z…` / `…090102Z…`)都只红在改的那一句。
- 第 1 轮修复后总跑(`…094904Z-01-run-all-r1fix…`)红 1 条:`narrow_window.e2e` 按按钮**文字**「发送」找发送键 —— 本单把它换成了 ↑ 图标(业主同意的第 4 条)。
  这是老判据锁住了被有意改掉的样子,不是产品红:我开工时排查受影响老判据只搜了 `.send-btn` / 「发送(Enter)」,漏了按文字找的这一处(全仓只此一处)。
  改成按名字「发送」(aria-label)找,断言一个字不动(1024 宽时发送键整个在窗口里);单跑收据 `…100336Z…` 全过。最终总跑在第 2 轮评审之后再跑一遍。
- 变异第 1 遍 14/18 漏 4 条,逐条分型:Z3 **判据真洞**(c8 两帧之后才断言,重复帧分支替第一帧补了收尾 → c8 补强);Z7 锚点没打上(脚本里 `\u3001` 被转成了真字);
  Z10 **等价变异**(改的那行永远走不到);Z18 变异没编译过(e2e 根本没跑)。修后 4/4;QA 执行抓到回归后补 Z19,1/1。

## Review

- 规格自查(读 panel 输出之前):design 的用户成功条件逐条有判据(c1–c18 + e2e 13 问);关键前提 P1 已实验(探针三时机)、P2 由 e2e 三栏钉住、
  P3 采纳 4c C2、P4(真中文输入法)本机做不了,进业主真机清单。自审(仓外,派发前落盘):`/root/aiwork/tasks/opendesign-composer-zcode-r1-my-review.md`,结论 PASS + 5 条低风险。
  **评审抓到的两条(R1 / R2)我自审都没看到** —— S1 我只想到「■ 一直灰」的一种来由(网关不回),没顺着 stopPending 的所有清除路径走一遍。
- 腿的花名册(第 1 轮代码评审,原样):`{roster_r1}`
- QA 设计花名册(开发前,原样):`{roster_qd}`
- QA 判卷花名册(第 1 遍录像,原样):`{roster_qa}`
- 轮次记录:

  | 轮 | 类型 | 派发前 `track preflight` | 日志前缀 | 新增有效阻断 |
  |---|---|---|---|---|
  | 1 | 实质 | rc=3,BLOCK 0(PENDING 2;先修了证据寿命 1 条) | /root/aiwork/logs/panel-composer-r1-20260925-173149 | 2(R1 / R2)|
  | 2 | 实质(复审,预算最后一轮) | rc=3,BLOCK 0(PENDING 1) | /root/aiwork/logs/panel-composer-r2-20260925-180424 | 0(腿判 BLOCK 两条,主裁核实:一条是改动前就有的收尾路径,一条是新的小毛病,均不阻断本单) |

- findings(第 1 轮代码评审 + QA 执行七家判卷 + 我在 QA 执行里自己抓的;**先处置、后动手**,一份修复清单):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | T1 | (QA 执行第 1 遍,我看录像抓的)后台认不出当前模型属于哪家时兜底报「有 key 的第一家」,按钮写成「王工工作室(备用中转)线路 · mimo-v2.5」 | `evidence/qa-exec/tour-r0-before-fix.md` 第 01 步 + `r0-01-chip-misfiled.jpg`;`bin/ds_credential.py` models_status `active = live[0]` | **已修**(判据先行 `…091952Z…` 红 → `20797b6`) | 本单引入:以前按钮只写模型名,兜底错了看不出;带上厂商名就说错扣哪家的钱 |
  | T2 | (同上)窄栏里厂商名与模型名一起被压成「王工工作室(…· relay-…」 | 录像第 26 步截图 | **已修**(`0c4d302`,模型名先让位) | 「GLM 套餐 / 按量」只差后两个字,压了分不出 |
  | R1 | (评审)新对话首句就点 ■:网关不发 `turn_end`,而侧栏历史 / 项目数据只在 `turn_end` 时刷新 ⇒ 侧栏里没有这段、停之前工具已做完的改动页面不刷新 | 属实:`web/src/chat/ChatPage.tsx:539` 只在 `turn_end` 调 `onTurnEnd`;`web/src/App.tsx:357-362` 刷新只挂在它上 | **本单必须修** | 本单引入的新路径(停止)漏接既有刷新;业主停完切走,在侧栏找不到刚才那段 |
  | R2 | (评审)停止标记残留:点了 ■ 回话没到就出错收尾 / 断线且拉历史 404 / 下一句新消息,都原样带着 `stopPending` ⇒ 下一轮 ■ 一直灰 | 属实:`ChatPage.tsx:455-459` 展开保留、`transcript.ts:356` error 分支展开保留、`appendLocalUser` 展开保留;`ChatPage.tsx` ■ `disabled={{... || !!transcript.stopPending}}` | **本单必须修** | 停止键按不动 = 本单承诺 4 不成立 |
  | R3 | (评审初判)停止收尾只看「是不是系统小字」,不核对是不是**这次** /stop 的回话 ⇒ 等回话那一瞬来一句后台子任务回报就提前解锁 | 属实:`transcript.ts` appendNote `stopped = !!(state.stopPending && bubble.systemNote)` | **本单修**(便宜) | 提前解锁 = 业主能在网关还在停的时候再发一句;探针证实回话带着我们发的 turn_id |
  | Q1 | (QA Grok / Gemini)技能页点卡片,开头填进了**旧对话**的输入框,不是新开一段 | 录像第 30 步;本单只把技能表换成共用一份,`App.tsx` 点卡片的行为没动(`git diff 464b55a..HEAD -- web/src/App.tsx` 为空) | 延期 | 老行为,不是本单引入(工作区规矩:只碰相关文件)。在业主那边:从技能页点卡片后,输入框里有开头,但上面挂着上一段对话;要先点「新对话」。归档时告诉业主 |
  | Q2 | (QA Gemini)侧栏历史的标题是助手的回答(「我是 MiMo,正常回复」),不是业主问的那句 | 录像第 16 步;标题由网关生成,本单没碰 | 延期(落点:第 3 件侧栏单) | 老行为;在业主那边:侧栏里认不出哪段是哪段 —— 正是侧栏方案一要解决的,那一单开工把它列进验收 |
  | Q3 | (QA Grok / GLM / Kimi)选技能后光标在句末,两份测试设计预期在冒号后 | 录像第 03 步「光标 12/12」 | 驳回 | 对照图原话「光标停在后面等你接着打」两种读法都行;业主是先写了话、再想起要「记一下」,光标在句末直接发或接着写都顺;空草稿时两种一样 |
  | Q4 | (QA GPT-terra)首页第 01 步模型按钮没有厂商名,判「不通过」 | 录像台子把主槽地址指到本机假厂商,后台认不出是 MiMo(第 01 步事实里有接口原样);**真地址下是对的**:e2e 用出货模板的真 MiMo 地址,③ 断言「MiMo · mimo-v2.5」绿 | 驳回 | 台子造成;真地址的证据是 e2e ③ |
  | Q5 | (QA 七家)录像没走到:空框「+」→整理文件夹、↑↓/Tab、筛不到按 Enter 发送、带图选技能再发、待办栏里停止、厂商连不上时停止 | 各家对账表「没执行到」 | 本单补录(修完一起重录、复判) | 便宜,且多数判据里有、录像里没有 |
  | Q6 | (QA 多家)真中文输入法拼字时 Enter、另外五档问候语、三栏同时回复 | 录像结构上做不到(无 Windows 输入法);问候六档 c17 单测覆盖 | 进业主真机清单 | — |

- **第 1 轮修复之后不做测试员整份复判**(业主 09-25 17:5x 定:「测试员为什么要看两次…有必要再走一轮吗」):
  测试员这一轮没报出本单的真缺陷(Q1–Q4 延期 / 驳回、Q5 是没走到);要修的 R1–R3 来自代码评审,由判据 + 变异 + 第 2 轮评审兜。
  Q5 的补录由我对着第 2 遍录像逐条核(`evidence/qa-exec/tour.md`,包 = `git archive 239293f`):
  第 28 步空框「+」→ 整理文件夹 ⇒「帮我扫描整理这个文件夹:」;第 29–30 步 ↓↓ 高亮找参考图、↑ + Tab ⇒ 用上整理文件夹、表收起;
  第 31 步「/不存在的技能」不弹、Enter 当普通话发出并得到回答;第 32–33 步带图选技能 ⇒「找参考图:客厅」+ 1 张缩略图,发出后气泡里 1 张图、输入框清空;
  第 34–35 步厂商连不上、网关重试时点 ■ ⇒ 138 毫秒解锁、「已停止」、之后 8 秒没冒出错说明;第 36–37 步待办栏里点 ■ ⇒ 149 毫秒解锁、「已停止」。全过。
- 腿的花名册(第 2 轮,原样):`subcursor.gpt-5.6-sol-high=PASS(verdict=BLOCK)`
- findings(第 2 轮评审;预算已用完,只有真阻断才会让本单保持未完成):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | R2′ | (评审 High)点 ■ 后回话到达前 ① 收到 `error`:只解锁,思考动画 / 流式光标留着;② 断线重连拉历史 404:`releaseTurn` 不定稿流式正文;③ 拉历史请求直接抛错:空 catch 吞掉,这一轮不放(■ 灰着) | 三处**改动前逐字相同**:`git show 464b55a:web/src/chat/transcript.ts` error 分支只 `{ ...state, busy: false }`;`git show 464b55a:web/src/chat/ChatPage.tsx` 拉不到历史那条路只清 busy/thinking/activity、`.catch(() => {})` 同在。本单只是在它们上面多清了停止标记(R2 本身已修,评审也认) | 延期(原有的断线 / 出错收尾缺口) | 不是本单引入:改动前任何一轮在这些路径上都一样(③ 改动前是发送键永远灰,现在是 ■ 灰,同一个病);停止只多了一种要在点 ■ 后 0.1 秒内恰好出错 / 断线才碰得上的走法。在业主那边的样子:极少数情况下断线重连后半截回答的闪烁光标不消失,或要刷新一次才能继续 —— 与改动前一样 |
  | F2 | (评审 Medium)先打 / 弹出技能表,再点「+」⇒ 两个技能菜单叠在一起 | 属实:`ChatPage.tsx` 技能表只由草稿决定、点「+」不收它;两个菜单都向上弹、同一层级 | 延期(落点:「+」菜单第二步「引用项目 / 之前的对话」那一单) | 本单新做出来的小毛病,不影响验收承诺 1/2、不指错门:两个菜单点哪个都能用,选一项或再打字就收起一个。在业主那边的样子:偶尔看到两个一样的技能表叠着。那一单本来就要动「+」菜单,顺手让两个互斥 |
  | N1 | (评审附注)正常一轮若先 `turn_end` 后 `idle`,侧栏会多刷一次 | 上一单探针的出错轮就是 turn_end 后跟 idle | 接受 | 多一次本机请求,无害;换来的是停止后侧栏一定刷新 |

  评审对 Q1–Q6 的处置全部表态同意;R1、R3 核验修好;R2 的停止标记残留核验修好(上面 R2′ 是它顺着看到的原有收尾缺口)。

- arbitrated verdict (主裁): **PASS**。两轮实质评审(GPT-5.6 sol,第 1 轮 BLOCK 2 条已修,第 2 轮 BLOCK 两条经核实都不是本单阻断,理由见上表)+ 开发前七家 QA 设计 + 真界面录像两遍(第 1 遍 30 步七家判卷,第 2 遍 40 步补录由我逐条核)+ 判据先行红检 + 变异 24/24 + 最终总跑(收据见上)。
  不续第 3 轮:4b 规定预算用完只有真阻断才保持未完成;R2′ 改动前就在、F2 是不阻断的小毛病 —— 都记在这里、有落点,不自动开单。

## Accepted deviations

- R2′:断线 / 出错那几条原有收尾路径不完整(思考动画 / 流式光标可能留着,拉历史抛错时要刷新)—— 改动前就这样,本单没变坏。
- F2:先打 / 再点「+」时两个技能菜单会叠在一起(落点见上)。
- Q1:技能页点卡片把开头填进当前对话,不新开一段(老行为,归档时告诉业主)。
- Q2:侧栏历史标题是助手的回答(老行为,落点:侧栏单)。
- S1:点 ■ 之后若网关永远不回话,■ 一直灰到这一轮以别的方式结束(探针里回话 0.1 秒内到)。
- S2:「+」菜单不支持方向键(打 / 的技能表支持)。
- S3:停在工具执行中间时回放里会不会多出工具痕迹,没实验(停止提示已说明那一步可能已做完)。
- 停止键不做 Esc 快捷键(误触会打断回复);待办页右栏的小输入框不动(没有技能表)。
- 发送键改为 ↑ 图标推翻了 07-19 修改单「文字发送」:业主 09-25 同意对照图第 4 条;归档时再提醒他一次(他可以一句话改回文字)。

## 业主真机要亲自走的(录像与判据够不着的)

1. 开着中文输入法(中文标点)在输入框按 / 键:应弹出技能表(打出来的是「、」也算);用拼音打字按 Enter 选字时不会误选技能、不会发出去。
2. 让它讲一段长的,中途点 ■:一两秒内停下、留着半截、下面一行灰字「已停止…」;马上再问一句能正常回。
3. 看输入框右下角:写着「MiMo · mimo-v2.5」这样的厂商名;换到 GLM 套餐 / GLM 按量时两家分得清。
4. 早上 / 中午 / 晚上各打开一次首页,问候语跟着变。
5. 在「技能」页点一张卡片:开头填进的是当前这段对话(老行为,见 Q1),觉得别扭就说一声。

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:约 2 小时(16:3x 立单 → 18:3x 主裁)
- 每轮新增有效阻断:第 1 轮 2(R1 / R2);第 2 轮 0
- 基础设施等待:评审腿第 1 轮约 4 分钟、第 2 轮约 4 分钟;QA 设计八家约 1–7 分钟(MiMo 基础设施失败 EROFS)、QA 判卷七家约 2–7 分钟;总跑三次各约 13 分钟;变异全量约 10 分钟
- 交付后返工:unknown
