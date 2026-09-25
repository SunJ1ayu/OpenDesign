# Design: opendesign-chat-error-visible

- Change: opendesign-chat-error-visible
- Status: agreed(4c 挑战后定稿)

## Goal-to-design check

- 当前行为 → 拟改变的行为:
  事实(本单探针 `evidence/20260925-probe-gateway-errors.txt`,真 nanobot 网关 + 本机假厂商;厂商原文另用明显的假 key 打真厂商抓):
  五类出错实时序列一律 `goal_status(running)` → `stream_end`(无 delta)→ `message`(**无 kind**,整句原文)→ `turn_end`;
  `applyEvent` 只收 kind=progress/tool_hint ⇒ 实时整句丢;回放(webui-thread)里它**已是一条 assistant 行**,英文原文照登 ⇒ 切走再回来冒英文。
  改成:实时与回放都显示同一句中文说明(哪类问题 + 去哪儿)+ 原文小字(key 形状的串打码),气泡带出错样式。
- 检查深度与触发事实:**独立挑战**(一次,xAI Grok 读仓库)。触发:改变网关→网页的协议解读(跨模块契约:从此所有无 kind 的 message 都上屏)
  + 改变失败退路的呈现。不涉及数据写入、权限、撤回代价低(纯前端,下一版可改回)。QA 设计(DeepSeek + Grok 黑盒)同时派。
- 关键前提:
  - P1 无 kind 的 message 永不与流式正文重复 —— `channels/manager.py` `_send_once`:带 `_streamed` 的最终消息不走 `send()`;
    `agent/loop.py:1364` 只有 stop_reason ∈ {error, tool_error} 或本轮没开流才不打 `_streamed`。**已读代码核实**。
  - P2 分类靠原文关键词:四家真 401 原文已抓(MiMo `Invalid API Key` / DeepSeek `Authentication Fails` / Kimi `Invalid Authentication` /
    GLM `令牌已过期或验证不正确`),经网关后逐字见 evidence;欠费:网关只认英文 token/短语(`providers/base.py:208-240`),
    DeepSeek 402 会被换成网关固定英文句,GLM `余额不足…请充值`(1113)原样透传 ⇒ 分类表必须自带中文与各家写法。
    真厂商的欠费/限流原文**未抓全**(要真欠费账号)—— 分不出时落「通用说明 + 原文」,不许错指。
  - P3 行首 `Error: ` 的正常回复会被误判:室内设计助手极少;只认网关固定前缀/固定句,不做全文搜索。
- 完全实现仍可能失败:① 真厂商某种欠费原文不含任何已知词 → 通用说明(不致命,原文在);② 用户看不懂「输入框右下角那家」→ 下一单输入框会把厂商名写到按钮上
  (0.98.14 第 2 件);③ 出错气泡太长挤占 → 两行说明 + 一行小字。
- 独立意见与核实:见下「4c 挑战记录」。
- 未解决项:真厂商欠费/限流原文没抓全(要真欠费账号)—— 不改变方向:认不准就落通用说明(指去「测试」),不错指。

## 4c 挑战记录(派发前我的方向已落盘在仓外 /root/aiwork/tasks/opendesign-chat-error-visible-my-direction.md,未喂给腿)

一条外部腿:Grok 4.7 high(xAI,subcursor,读仓库),题面 `evidence/20260925-design-challenge-brief.md`,原文 `evidence/20260925-design-challenge-grok.md`,
花名册 `evidence/20260925-design-challenge.roster`(EXPLORE rc=0)。结论「需改」。逐条核实:

| # | Grok 的挑战 | 核实 | 取舍 |
|---|---|---|---|
| G1 | 网页拿不到 HTTP 码,只有 `Error: {body}` 前 500 字;按关键词分四类会把人指错门(`invalid_request_error` 也用于模型名错、图片被拒);探针里的 `Invalid API key` 是假厂商编的 | **成立一半**。`openai_compat_provider.py:1409` 确认只有正文;但我随后用明显的假 key 打了四家真厂商,真 401 原文都带明确字眼(MiMo `Invalid API Key`/`invalid_key`、DeepSeek `Authentication Fails`、Kimi `Invalid Authentication`、GLM `令牌已过期或验证不正确`),经网关后逐字见探针证据 | **改**:分类只认明确字眼,`invalid_request_error` 这个 type **永不**作为任何类的依据;认不准 ⇒ 通用说明并指去「测试」(即 Grok 的方向作为兜底)。不全盘改成「一律去测试」:四家真原文能分准,业主多点一次「测试」而且 402 在「测试」里只会说「厂商拒绝了这次请求」(`ds_credential.py:1361`),对欠费反而更含糊 |
| G2 | `runner.py:475` 工具崩溃 `Error: RuntimeError: …` 会被当成模型出错 | 主聊天的 runner 不开 `fail_on_tool_error`(`loop.py` 无此参数,默认 False,`runner.py:101`),这句只出现在子任务;但主循环未捕获异常会发 `Sorry, I encountered an error.`(`loop.py:1070`) | **改**:`Error: <XxxError|XxxException>: …`(Python 异常形状)与 `Sorry, I encountered an error.` 归「助手这边出错」,不说成厂商/key 问题 |
| G3 | 回放只有 content:模型原样引用那句欠费英文时,回来会被改写成「去充值」 | 成立(回放行无出错标记,探针核实) | **改**:只在**整条内容**就是网关的壳时才改写 —— 固定句要整句相等,`Error: ` 等前缀要在行首;正文中间出现不算 |
| G4 | 原文进 `renderMarkdown` 会把 `invalid_request_error` 的下划线当强调 | 成立(`ChatPage.tsx:1040` 助手气泡走 markdown) | **改**:出错气泡的说明与原文都按纯文本渲染 |
| G5 | 限流/500/连不上要等约 7 秒重试,期间只有思考动画 | 事实(探针);网关行为,不在本单改 | 保持:失败确定那一刻出中文;QA 设计 Grok 同样按此验收 |
| G6 | 无 kind 的 message 追加为气泡不会与流式正文重复 | Grok 独立读码确认(`loop.py:1364-1365`、`manager.py:393-394`),与我的 P1 一致 | 保持 |

QA 设计(测试员,开发前黑盒,不计评审轮):题面 `evidence/20260925-qa-test-design-brief.md`;Grok `evidence/20260925-qa-design-subcursor.grok-4.7-high.md`(26 条用例,采为 QA 执行底稿);
DeepSeek `evidence/20260925-qa-design-subdeepseek.md`(**违反黑盒读了代码、没按交付格式**,只采两条:原文小字给 key 形状的串打码;「看得出是出错」要落成可断言的标记)。
Grok 列的三个「待拍板」我判不需业主:① 重试那几秒继续转思考动画(现状,网关行为)② 措辞不依赖「当前」—— 改成「发这句时用的那家」
③ 定时提醒落在建它的那段对话里(网关按 chat_id 投递,本单不改路由)。

## Approach

1. `transcript.ts`:`message` 事件 kind ∉ {progress, tool_hint} 且 `text` 是非空字符串 ⇒ 追加一条**非流式** assistant 气泡、关「正在思考」;
   id = `note-<turn_id>-<turn_seq>`(缺则 `note-<序号>`),同 id 已在就不重复加。busy 不动(仍由 turn_end / error 解锁)。
2. 共用纯函数 `describeModelError(raw)`(新文件 `web/src/chat/modelError.ts`):**整条内容**是网关的壳才认
   (行首 `Error: ` / `Error calling LLM:` / `Error calling Azure OpenAI:`;整句相等:欠费固定句、`Sorry, I encountered an error calling the AI model.`、
   `Sorry, I encountered an error.`、空答固定句、`[Assistant reply unavailable due to model error.]`),
   只按**明确字眼**分:额度欠费 → key → 太频繁 → 太长 → 找不到模型 → 超时 → 连不上 → 厂商出错;Python 异常形状 / 两句 Sorry → 助手这边出错;
   空答句 → 没整理出回答;其余 → 通用(指去「测试」)。**欠费先于 key**(网关欠费固定句里含 “API key”);`invalid_request_error` 不作依据。
   输出 `{ text, raw }`,raw 里 key 形状的串(`sk-`/`tp-`… 长串、`Bearer …`)打码。
3. 实时(applyEvent)与回放(hydrateFromThread)都过同一个函数;`ChatMessage.modelError = { raw }`,content = 中文说明
   (对账、复制等老逻辑不受影响)。措辞不用「当前」:「发这句时用的那家(输入框右下角是现在选的模型)」。
4. `ChatPage.tsx`:`modelError` 气泡 `className="msg-ai msg-error" data-ui="chat-model-error"`,说明与小字「原文:…」都是纯文本(不走 markdown)。
5. `modelSettings.ts:252` 文案对上开关上的字。

## Key trade-offs / risks

- 不点厂商名:回放行没有模型字段(探针核实),实时点名会在切回后变样、换过模型后说错;改为指向「输入框右下角正在用的那家」。
- 所有无 kind 消息上屏:扩大可见面(message 工具主动发的话、定时提醒、斜杠命令回复)。依据 P1,不会重复;实时图片不在本单。

## Alternatives considered

- 只在「本轮没有流式正文」时显示那条 message(交接时的原想法):条件多余(P1 已保证不重复),而且会继续吞掉工具主动发的话。
- 出错时自动调「测试」接口给精确诊断:新增默认自动动作,多打厂商一次;没选。
- 用瞬态 `chat-turn-error` 横条显示:切走再回来就没了,而回放里那条 assistant 行还在 ⇒ 两处说法不一致;没选。

## Test strategy (oracle)

- 单测(`tests/test_chat_model_error.mjs` 新文件,node --test):
  a. 真抓序列(401)喂 applyEvent ⇒ 恰好一条 assistant 气泡、带 modelError、中文含「API Key」「设置」「测试」、正文不含 `Error:`;busy/thinking 收尾为 false。
  b. 抓到的每条真原文 → 对应类别的关键中文;**易混对互斥**:欠费句不含「稍等」、限流句不含「充值/余额」;连不上说「网络」、厂商出错不说「网络」。
  c. 认不出的 `Error: …` → 通用说明 + 原文;非网关前缀的正常文本(含行中 Error、正文里引用欠费句)→ 不当出错;
     Grok 的反例:`invalid_request_error` + 模型不存在 ⇒ 不许说成 key;`Error: RuntimeError: …` ⇒ 助手这边出错,不说 key/厂商。
  d. 普通无 kind 消息 → 原样一条普通气泡(无 modelError)。
  e. 正常流式一轮(delta…stream_end→turn_end)→ 不多气泡(回归);progress 帧仍只进活动行。
  f. 同一原文:hydrateFromThread 的结果 === applyEvent 的结果(实时与回放同句)。
  g. 原文里 `sk-…` / `tp-…` 形状的串打码。
  h. 同一 message 帧收两次 → 只一条。
- e2e(`tests/e2e/chat_model_error.e2e.mjs`,真 chromium + ws 替身重放**真抓帧**):看得见中文 + `data-ui=chat-model-error` + 原文小字;
  切到工作区再切回(走回放)⇒ 同一句中文、没有英文原文当正文;出错后输入框可发。
- 设置页文案:改 `tests/` 里钉那句的断言(若有)。
- QA 执行:真网关 + 假厂商(401 / 欠费 / 连不上)+ 真工作台 + 真 chromium 走一遍,每步截图 + 读屏文字。

**这个 oracle 能被什么骗过?**
- 替身帧是我抓的,但**真厂商欠费/限流原文**没抓全 ⇒ 单测全绿,真业主欠费时仍可能落到通用说明。接得住的只有:业主真机遇到时原文在小字里,可以补表。
- e2e 用替身不走真网关 ⇒ 序列若在别的出错路径不同(例如工具出错 tool_error)会漏;QA 执行用真网关补一类。
- 「看起来是出错」只断言了类名/data-ui ⇒ 样式没生效也全绿;QA 执行截图接。
