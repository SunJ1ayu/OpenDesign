# Design: opendesign-composer-zcode

- Change: opendesign-composer-zcode
- Status: agreed(4c 挑战 + 七家 QA 设计之后定稿)

## Goal-to-design check

- 当前行为 → 拟改变的行为:见 proposal「真问题」。事实:「+」只选图;「✎ 记一下」只补一句开头;模型按钮只写模型名;
  「发送」回复中置灰、**没有停止**;问候语固定。五条都是我提、业主 09-25「就按你建议的来吧」同意的(区分:原话只有这一句)。
- 检查深度与触发事实:**最小实验 + 独立挑战 + QA 设计**。触发:新增用户动作「停止」及其失败退路(停在什么时刻、停不下来怎么办);
  网页对网关协议的新解读(`/stop` 回 `goal_status:idle`、不发 `turn_end`);打 / 改变输入框按键行为(Enter 在菜单开着时不再发送)。
  撤回代价低(纯前端,不改 nanobot、不改数据)。
- 关键前提:
  - P1 `/stop` 走网关优先通道、按本聊天 session 取消、断开厂商流、不留用户行;回 `goal_status:idle` + 无 kind 英文句,**不发 turn_end**。
    **已实验**(`evidence/probe-stop.py`,输出 `evidence/20260925-probe-stop.txt`,三种时机:出字中 / 还在想 / 没在回复)。
  - P2 三个聊天栏各自一个 chat_id ⇒ 停一个不影响别的:`/stop` 按 effective session key 取消;`unified_session` 默认 false
    (`nanobot/config/schema.py:145`),我们的两份配置模板都没设(grep `config/`、`bin/` 无 unified)。已核实(代码),e2e 再钉。
  - P3 `goal_status:idle` 不能当成任意时刻的「本轮结束」:正常轮次靠 `turn_end` 收尾;**只在本栏已点过停止时**把 idle 当停止终态(4c 挑战 C2,采纳)。
  - P4 业主开着中文输入法:微软拼音中文标点模式下按 / 键打出「、」⇒ 只认 ASCII `/` 的话,业主可能**永远弹不出**技能表。
    ZCode 只给 `$` 做了 `¥/￥` 别名(`refs/zcode-ui-src/lib/promptInputTriggers.ts:42-49`),没管「、」。⇒ 我们把「、」「／」当 `/` 的别名。
    未在真 Windows 输入法上实验(本机无);QA 执行与业主真机清单各走一次。
- 完全实现仍可能失败:
  ① 回复进行中业主切到别的页面,那一栏的 ■ 看不见,只能切回去停(4c C1,延期到第 3 件侧栏:侧栏显示每段对话「回复中」);
  ② 停在工具中间(记账、挪文件)那一步可能已经做完,业主以为没做、重发一遍 ⇒ 停止提示明说「已经开始的那一步可能已做完」(QA Gemini);
  ③ 窄栏(项目右栏)里模型按钮加了厂商名更长,挤掉 ↑ 或折行(上一单 ⑯ 同类)⇒ 厂商名单独省略、判据按 ⑯ 量位置;
  ④ 自定义供应商名字本身带括号 / 很长(≤40 字)⇒ 只对内置五家用短名,自定义原样 + 省略号 + 悬停看全名(4c C5,采纳)。
- 独立意见与核实:见下「4c 挑战记录」「QA 设计」。
- 未解决项:P4 的真输入法行为(本机无 Windows 输入法)—— 不改变方向:别名只放宽触发,不影响其它输入。

## 4c 挑战记录(派发前我的方向已落盘在仓外 /root/aiwork/tasks/opendesign-composer-zcode-my-direction.md,未喂给腿)

一条外部腿:**GPT-5.6 sol high**(OpenAI,subcursor,读仓库),题面 `/root/aiwork/tasks/opendesign-composer-zcode-4c.md`(evidence 同名副本),
原文 `evidence/20260925-design-challenge-gpt.md`,花名册 `evidence/20260925-design-challenge.roster`。结论「需改」。选它:不同家族、能读仓库、推理强,本轮 Grok 在当 QA。
派发时报了一行 anchor leak(`tracks/opendesign-composer-zcode/verify.md`)—— 那是 `track new` 生成的空模板,当时没有我的任何结论,不影响独立性。

| # | 挑战 | 核实 | 取舍 |
|---|---|---|---|
| C1 | 项目助手在回复时切到首页,项目栏隐藏但还在跑(`App.tsx:573-588` keep-mounted),首页只显示 ↑,看不到 ■,要切回去才能停;建议 App 级「运行中」提示 + 跨页停止 | 属实(三栏 keep-mounted、busy 各自) | **延期**:不是本单引入(现在根本没有停止);要做就是全局运行态,属侧栏(第 3 件)天然的位置 —— 侧栏每段对话显示「回复中」、点进去就是 ■。在业主那边的样子:切走后想停,要点回那一栏再停(一次点击) |
| C2 | `idle` 只在本栏 `stopPending` 时当停止终态,正常回复仍以 `turn_end` 收尾 | 与我的 P-a 担心一致;探针正常轮次没有 idle,但只测了无工具轮次 | **采纳** |
| C3 | 若启用 `unified_session`,一次 `/stop` 会停掉所有聊天 | 默认 false(`schema.py:145`);`config/*.jsonc`、`bin/` 均无 unified | **驳回**(不可达);P2 仍由 e2e 钉「停一栏另两栏照常」 |
| C4 | 待办页还有一个紧凑输入框(`TodoRail.tsx:222-236`)写着文字「发送」,且与聊天输入框共用占位字函数 | 属实:`inputPlaceholder("问待办")`;它是普通 `<input>`,没有技能表 ⇒ 占位字若改成「输入 / 选技能」**就是假话**。另:它的 Enter 不判输入法选字(`TodoRail.tsx:231`)—— 我读码时发现的旧毛病 | **采纳一半**:待办小框**一行不动** —— 它继续用原来的 `inputPlaceholder`(「问待办,或「记一下…」」在那个框里仍是真话),聊天输入框改用新的 `composerPlaceholder`。它的文字「发送」与 Enter 不判输入法的旧毛病**不在本单**(工作区规矩「只碰相关文件、不顺便改相邻代码」):记进 verify.md 延期,在业主那边的样子 = 在待办小框用拼音打字、按 Enter 选字时会把半截拼音发出去 |
| C5 | 自定义厂商名 ≤40 字、括号里可能正是身份,机械去括号会误导扣费方(`ds_credential.py:1220-1227`) | 属实 | **采纳**:短名只对内置五家(按 provider id 查表);自定义原样,过长省略,title 给全名 |

## QA 设计(测试员,开发前黑盒,不计评审轮)

题面 `/root/aiwork/tasks/opendesign-composer-zcode-qa-design.md`(evidence 同名副本)。**人选不固定,每个可用家族各一条**(业主 09-25:「不要固定吧」「所有可用的腿都用上」);
Claude 家族除外(我是作者兼主裁)。**黑盒机械化**:QA 腿的仓库参数给空目录 `/root/qa-blackbox-repo`(只有一个 README),读不到代码。
派了 8 家:DeepSeek(deepseek-flash)、Grok 4.7 high、GPT-5.6 terra high、Gemini 3.8 flash high、Kimi K3 high、GLM 5.2 high、Cursor Composer 2.5、MiMo v2.6 pro。
**MiMo 失败**(rc=1,`EROFS: read-only file system` —— mimocode 往只读目录写,基础设施问题,与题目无关;小米家族本轮无替补)。其余 7 份原文见 `evidence/20260925-qa-design-*.md`。

七家反复提的疑问,我逐条定(都是实现细节、不改业主同意的五条,不问业主):

| 疑问(提出者) | 定 |
|---|---|
| 问候语时间分界、窗口开着过分界要不要变(GPT / GLM / DeepSeek / Gemini / Composer) | **分档照 ZCode**:6 档,5 / 9 / 12 / 14 / 18 / 23 点换档,窗口开着到点自动换(`ConversationDraftEmptyState.tsx:14-36`)。**措辞照业主看过的对照图**「下午好,今天想聊点什么?」:早上好 / 上午好 / 中午好 / 下午好 / 晚上好 + 「,今天想聊点什么?」;23–5 点「夜深了,还在忙吗?」(ZCode 原句是它自己的口吻,不照抄) |
| 回复中能不能打字、开「+」、打 /(GLM / Kimi / Composer) | 能 —— 现状就是「锁发送不锁打字」;菜单和 / 只改草稿,不发送 |
| 停止和刚好说完撞上(GPT / GLM / Kimi) | 先到先得:`turn_end` 先到 ⇒ 正常结束,按钮已回 ↑;网关回「没有在进行的回复」⇒ 显示「这次回复已经说完了」小字,不改已完成的回答 |
| 改写过的英文小字标什么(全体) | 「聊天服务的说法:」;真透传仍「原文:」 |
| 旧历史里的英文系统句要不要变中文(GLM) | 要:回放时现译,新旧历史一样 |
| 项目助手占位字会不会被抹成首页那句(DeepSeek / Gemini) | 不会:每处保留自己的前半句(聊设计、找参考 / 问这个项目),只换后缀 |
| / 后能不能按拼音 / 近义词筛(DeepSeek) | 每个技能带关键词(照 ZCode `keywords`):名字、缩写字、几个常说的词(账本、变更、文件夹、参考、图);不做拼音首字母 |
| 多行草稿第二行打 / 触发吗(Gemini) | 不触发:只认**整段草稿**以 / 开头 |
| ↑ 图标没字、可发现性(DeepSeek) | `aria-label` + 悬停提示「发送(Enter)」「停止这次回复」 |
| 停在记账 / 挪文件中间,业主以为没做、重发(Gemini) | 停止提示写明「已经开始的那一步可能已做完」 |

## Approach

1. **技能表一份**:新 `web/src/chat/composerSkills.ts` —— `SKILLS`(abbr / name / desc / flow / prefill / keywords),`SkillsPage.tsx` 改为 import。
   纯函数:`applySkillPrefill(draft, skill)`(已是任一技能开头 ⇒ 换开头;否则开头 + 原文)、`slashQuery(draft)`(整段以 `/`、`、`、`／` 开头且无空白 ⇒ 查询串,否则 null)、
   `filterSkills(query)`(名字 / 缩写 / 关键词包含,空串 = 全部)。
2. **输入卡**(`ChatPage.tsx`):「+」→ 小菜单(图片 / 技能三行),点外面或 Esc 关;去掉「✎ 记一下」;草稿满足 `slashQuery` 且有匹配 ⇒ 输入框上方弹技能表,
   ↑↓ 选、Enter/Tab 用、Esc 关(关了之后本段 / 查询不再弹,直到草稿不再以 / 开头);输入法拼字(`isComposing` / keyCode 229)时不接管按键。选中 ⇒ 草稿 = prefill,光标到末尾。
   占位符改用新的 `composerPlaceholder(scene)` =「<前半句>;输入 / 选技能」(首页「聊设计、找参考」/ 项目「问这个项目」前半句不变)。
3. **模型按钮**:`modelChipLabel` 返回 `{ vendor, model }`(或新函数),内置五家按 provider id 查短名(mimo→MiMo、deepseek→DeepSeek 官方、kimi→Kimi 按量、glm_plan→GLM 套餐、glm→GLM 按量),
   其余用 label 原文;模型列表拿不到 ⇒ 只写模型名(现状)。厂商名灰一点、单独省略,title = 「厂商全名 · 模型名」。
   出错说明 key 那句改成「(输入框右下角写着现在用的是哪家、哪个模型)」(D2)。
4. **发送 / 停止**:不在回复中 ⇒ `.send-btn`(↑,aria-label「发送」);回复中 ⇒ `.stop-btn`(■,aria-label「停止这次回复」),未连上时置灰。
   点 ■:往本栏 ws 发 `{type:"message", content:"/stop", turn_id:"stop-<uuid>"}`,**不** `appendLocalUser`;transcript 记 `stopPending = 该 turn_id`。
   `applyEvent`:`goal_status:idle` 且 `stopPending` ⇒ 按 turn_end 收尾(busy/thinking/activity 清、流式定稿);
   无 kind message 的 `text` 是停止回话(`Stopped N task(s).` / `No active task to stop.`)⇒ 追加**系统小字**(不是助手气泡),并清 `stopPending`、解锁。
   `Background task completed.` 同样译成系统小字。回放 `hydrateFromThread` 走同一个 `describeSystemNote(content)`。
   文案:停止 ⇒「已停止(已经开始的那一步可能已做完)」;没有在进行的 ⇒「这次回复已经说完了,没有要停的」;后台任务 ⇒「后台任务做完了」。
5. **问候语**:`greetingFor(date)` 六档(分界照 ZCode,措辞见上表);首页空态挂一个到下一个分界点的定时器(`nextGreetingDelayMs`),到点重算。
6. **Q3′**:`describeModelError` 输出多一个 `rawLabel`(FIXED 固定句 ⇒「聊天服务的说法」,其余「原文」),气泡小字用它。
7. **待办小框**(`TodoRail.tsx`):不动。`inputHint.ts` 保留 `RECORD_SUFFIX` / `inputPlaceholder` 给它用,新增 `composerPlaceholder` 给聊天输入框。

## Key trade-offs / risks

- 停止只认本栏自己点过的停止:别处发来的 idle(理论上不该有)不解锁 —— 宁可多等 turn_end,也不提前解锁让业主在回复中途插话。
- 「、」当 / 的别名:业主极少以顿号开头打字;就算打了,筛不到或按 Esc 后照常发送。
- `.send-btn` 回复中不再渲染(换成 `.stop-btn`):老 e2e 用「`.send-btn` 置灰」判「正在回复」,要改成「出现 `.stop-btn`」—— 判据改动单独 commit、写理由。

## Alternatives considered

- 按 ZCode 做成**同一个按钮**换图标:DOM 上 send/stop 共用一个元素,e2e 与读屏难分「能不能发」;分两颗按钮语义清楚。没选。
- 停止后立刻本地解锁(不等网关回话):网关回话在 0.1 秒内到(探针);本地先解锁会让「停止失败」(连接刚断)时业主以为停了。没选;
  但连接断开时靠现有重连收尾逻辑解锁(不新增)。
- App 级跨页停止(4c C1 建议):见上,延期到侧栏。
- 菜单顶部搜索框(对照图画了):只有 4 项;要按字筛就打 /。没做,proposal 写明。

## Test strategy (oracle)

- 单测(`tests/test_composer_zcode.mjs` 新文件,node --test):
  a. `applySkillPrefill`:空草稿 / 有字 / 已是别的技能开头 ⇒ 不叠两个开头,原文保留;三个技能的 prefill 与技能页同源(import 同一个 SKILLS)。
  b. `slashQuery` / `filterSkills`:`/`、`、`、`／` 开头触发;第二行的 / 不触发;有空格不触发;`/参考` 只剩找参考图;`/账本` 命中记一下;`/xyz` 空表。
  c. 厂商短名:五家内置 id ⇒ 短名(GLM 套餐 ≠ GLM 按量);自定义「王工(测试)中转」原样;列表拿不到 ⇒ 只写模型名(旧 mp 断言语义保留)。
  d. 停止归约:busy + 流式中 ⇒ 记 stopPending ⇒ `goal_status:idle` ⇒ busy/thinking 清、半截定稿;**没点过停止时 idle 不解锁**;
     停止回话 ⇒ 系统小字(不是助手气泡、不含英文);`No active task` ⇒「已经说完了」;回放同一 content ⇒ 同一句中文(实时 = 回放)。
  e. `Background task completed.` 实时 / 回放都是中文小字。
  f. Q3′:欠费固定句 ⇒ rawLabel「聊天服务的说法」;GLM 1113 真透传 ⇒「原文」。
  g. `greetingFor`:4:59 / 5:00 / 8:59 / 9:00 / 11:59 / 12:00 / 13:59 / 14:00 / 17:59 / 18:00 / 22:59 / 23:00 各落对档。
- e2e(`tests/e2e/composer_zcode.e2e.mjs` 新文件,真 chromium + ws 替身):「+」菜单四项、点技能补开头、「记一下」按钮不在;打 / 弹表、Enter 选中不发送、筛不到 Enter 发送;
  模型按钮「MiMo · mimo-v2.5」;回复中出现 ■、点了替身收到 `/stop`(且页面上没有 “/stop” 气泡)、替身回 idle + Stopped ⇒ 解锁、半截在、「已停止」中文;
  切走再回来(回放)仍是中文;三栏:只停首页,项目栏照常收到替身的后续 delta。待办小框占位字不变。
- 老判据要改的(判据先行 commit 里逐条写理由):`frontend_p2_polish`「发送按钮=文字发送」→ aria-label「发送」;`model_picker` ⑯ 去掉「记一下」那一项、保留「↑ 整个在卡里 + 模型按钮不压 ↑」;
  `chat_reconnect` ㉜a/㉜ 等「`.send-btn` 置灰 = 忙」→「出现 `.stop-btn` = 忙 / `.send-btn` 回来且可点 = 不忙」(`helpers.mjs` 加一个判忙函数,语义不放宽);
  `test_model_picker` mp 按钮文字断言改成新函数的形状,原「拿不到 ⇒ 网关报的模型名 / 选择模型」两条保留。

**这个 oracle 能被什么骗过?**
- 替身回的 idle / Stopped 帧是我按探针抄的;真网关的时序(idle 早于 / 晚于那句话)变了,单测照绿 ⇒ QA 执行用**真网关 + 假厂商慢流**真按一次 ■(tour 脚本)。
- 「、」别名在 e2e 里是 `fill("、")`,不是真输入法按键 ⇒ 真输入法只能靠业主真机清单一条。
- 窄栏布局 e2e 量的是 bounding box;长自定义厂商名的省略号要看截图 ⇒ QA 录像里放一步「换到长名字的自定义供应商」。
