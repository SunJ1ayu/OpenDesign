# subdeepseek-agent explore log
time: 2026-09-25T14:23:48+08:00
mode: explore (agent base: claude-code headless -> deepseek)
base_url: https://api.deepseek.com/anthropic
model: deepseek-flash
repo: /root/.openclaw/workspace/projects/design-studio
task: /root/aiwork/logs/explore-chaterr-qa-exec-20260925-142347.task.md
视野: 底座腿 —— 自己读仓库(Read/Glob/Grep)+ 只读 git(自己跑 git diff/log/show)。

I'll start by exploring the evidence directory and reading the key documents.

  → Bash ls -la /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-chat-error-visible/evidence/ 2>/dev/null && echo "---QA-EXEC---" && ls -la /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-chat-error-visible/evidence/qa-exec/ 2>/dev/null

  → Bash git log --oneline -15 && echo "---" && ls

Let me read the two prior QA designs and the brief.

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-chat-error-visible/evidence/20260925-qa-test-design-brief.md

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-chat-error-visible/evidence/20260925-qa-design-subcursor.grok-4.7-high.md

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-chat-error-visible/evidence/20260925-qa-design-subdeepseek.md

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-chat-error-visible/evidence/qa-exec/tour.md

Now let me read the e2e test and the full run output.

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-chat-error-visible/evidence/20260925T055525Z-01-run-all.txt

  → Bash wc -l tests/e2e/chat_model_error.e2e.mjs && echo "---GREP CHECKS---" && grep -n "check(" tests/e2e/chat_model_error.e2e.mjs

  → Read /root/.openclaw/workspace/projects/design-studio/tests/e2e/chat_model_error.e2e.mjs

Let me read the tour script and check a few screenshots.

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-chat-error-visible/evidence/qa-exec/tour.mjs

Let me check the probe evidence and view key screenshots.

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-chat-error-visible/evidence/20260925-probe-gateway-errors.txt

Let me view key screenshots to check the visual treatment and layout.

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-chat-error-visible/evidence/qa-exec/08.jpg

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-chat-error-visible/evidence/qa-exec/11.jpg

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-chat-error-visible/evidence/qa-exec/17.jpg

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-chat-error-visible/evidence/qa-exec/15.jpg

I have enough. Here is my answer.

---

Direction: 本单验收要落到「**一条错误气泡 × 五种错 × 三个聊天栏**」的真机走查上,而唯一的 P0 是「这句话会不会把人指去一个解决不了问题的地方」

Core bet: 真正伤人的不是"没有气泡",而是气泡给了做不到的承诺(叫人去点一个答非所问的「测试」),或把不是原文的东西标成「原文」。而这两样,替身 e2e 天生看不见——它只有 MiMo 401 一种错、只看首页——所以它们只能靠"真厂商错 × 真界面 × 三个栏"的现场走查兜,不能再指望加断言。

How it works: 录像(tour.md,17 步)确实把五种错、三个栏都走了一遍,但它自己声明"**不是判据,不进 run-all**";自动判据 `tests/e2e/chat_model_error.e2e.mjs` 只有 13 条断言,全部压在 MiMo 401 + 首页一条路径上。于是对账结论是:**五类错都"跑过且人眼通过",但只有 key 错这一档有机器判据**;三栏中只有首页做了"切走再回来",项目栏/待办栏只做了"当场出现"。缺陷在"认不出的错"这条主句上(见下),它是录像里唯一一处把用户指去白跑一趟的地方。

Best at: 抓"指错门 / 标错名";一次真机走查同时过分类、持久化、跨栏隔离。

Sacrifices: 慢、要真机、要每家有真错 key;不覆盖实现层回归(那归 e2e / 单测)。

Blind spots in the brief:
- **自动判据的覆盖面被高估了**。`tests/e2e/chat_model_error.e2e.mjs:159-208` 的 13 条断言只喂一条 MiMo 401 帧、只查 `.home-pane`。Grok 的易混对(欠费 vs 限流、断网 vs 厂商故障)和 DeepSeek 的三栏重挂载,全靠人眼录像;将来任何一条坏了 **不会有红**。
- **「厂商原文」这个承诺在网关层可能已经失真**。探针里 DeepSeek 真报错体是 `{"message":"Insufficient Balance",...}`(probe 第 129 行),但网关发给前端的是一句固定英文转述(probe 第 132 行、"mode=429q" 段)。简报把"原文"当成 renderer 拿得到的东西,没问它是不是真原文。
- **简报没区分"当场不离开"和"切走再回来"是两条路**。录像只证明了首页的后者;项目栏/待办栏的后半段一步没走。
- **没要求覆盖别家厂商的 401/402 报错体**。探针抓到了 DeepSeek / Kimi / GLM 的真 401 原文(probe 96-127 行),但界面上一次都没走过——录像里假厂商回的是 MiMo 形状。
- 「出错时聊天里**马上**出现」与已知的 7~8 秒重试窗仍然对不上;简报一边把重试列为"已知行为、不用报",一边保留了"马上"这个词。

Smallest first step: 主 agent 亲自(不经执行腿),在一台真机上用一家真厂商的真错 key,在**待办页右栏**发一句 → 切到工作区 → 切回待办页,确认还是同一句中文。这一条同时验证"首页之外还有第二个栏"和"重挂载不丢",成本最低,而今天录像里恰好没走。

---

## 1. 用例对账表(P0)

**Grok 设计(`20260925-qa-design-subcursor.grok-4.7-high.md`)的 P0 = E1–E11。**

| 编号 | 判定 | 证据(文件 + 步骤号 / 断言原文) |
|---|---|---|
| E1 key 不对(首页) | 已执行·通过 | 录像 `qa-exec/tour.md` §02 / `02.jpg`;`chat_model_error.e2e.mjs:164`「恰好一条出错说明」、`:166`「说明里带着去哪儿、做什么」;主句无厂商名(截图) |
| E2 额度用完 / 欠费 | 已执行·通过 | 录像 §05、§06 / `05.jpg`、`06.jpg`;主句含"余额、充值",不含"稍等" |
| E3 太频繁 | 已执行·通过 | 录像 §07(转圈)→ §08 等 7841ms「发得太频繁…稍等一两分钟再发一次」;不含"充值" |
| E4 连不上 | 已执行·通过 | 录像 §09 / `09.jpg`「连不上模型厂商 / 先看看电脑能不能上网」;等 7871ms |
| E5 超时或厂商出错 | 已执行·通过(**只走了厂商 500 一档**) | 录像 §10 / `10.jpg`「模型厂商那边出错了(不是你这边的问题)」;**纯"请求超时"档没走** |
| E6 认不出的错 | 已执行·通过(**但下一步指错门,见缺陷 1**) | 录像 §11 / `11.jpg`「模型那边出错了」+ 原文小字 |
| E7 开设置再回来 | 已执行·通过 | 录像 §03 / `03.jpg`;文字与 §02 逐字同 |
| E8 切待办/别的项目再回来 | **部分**(机制不同) | 录像 §04 走的是"侧栏『历史对话』点回"(网关回放),**不是** E8 写的"打开待办页再回到首页 / 打开另一个项目再回到原项目助手";`04.jpg` 证明回放这句是中文 |
| E9 改好再发就正常 | **部分** | 录像 §12 / `12.jpg`:出错后再发恢复正常、出错条数 7→7 不变。**没走**"去设置把 key 改对 → 点该行「测试」看到可用 → 回来再发"这条用户路径(只是把假厂商拨回 ok) |
| E10 项目助手栏 | **部分** | 录像 §14 / `14.jpg` 项目栏出现同一句中文;同一步要求的"首页和待办栏不冒出这条"**没查**;"项目栏切走再回来"**没走** |
| E11 待办助手栏 | **部分** | 录像 §15 / `15.jpg` 待办栏当场出现中文;同一步要求的"再切到待办列表别处后回到助手栏"**没走** |

**DeepSeek 设计(`20260925-qa-design-subdeepseek.md`)没有编号用例表**——它是一份方案(方向/Core bet/…),P0 以"判据形状"的形式散在正文。按其自列的 P0 逐条对:

| 条目(出处) | 判定 | 证据 |
|---|---|---|
| D1 欠费 vs 限流(同为 429):额度必须有"余额/充值"且不得有"稍等";限流必须相反(该文 67-68 行) | 已执行·通过(**人工读文本,无自动判据**) | §06 / `06.jpg` 额度:有"余额、充值",无"稍等";§08 / `08.jpg` 限流:有"稍等",无"充值" |
| D2 断网 vs 厂商故障:断网必须说"检查网络",厂商故障不得(69 行) | 已执行·通过(**人工读文本,无自动判据**) | §09 有"能不能上网";§10 通篇无"网络"字样 |
| D3 key 错:必须指向「设置 → 模型设置」并提到「测试」(70 行) | 已执行·通过 | §02 + e2e `:166`。**"指向右下角当前那家"没机械断言**;主句只写"找到发这句时用的那家",没指向右下角那个模型按钮(见缺陷 3) |
| D4 唯一性/持久化:重挂载后逐字不变、不与旧 `chat-turn-error` 同现(71 行) | 已执行·通过(**仅首页**) | e2e `:205`「回放与实时是同一句」;§03 / §04 / §16(`03/04/16.jpg`)都是同一句;§02 全屏只有一处错误表述 |
| D5 回归:正常一轮仍只有一条助手气泡,`reasoning_*`/`goal_status`/`session_updated`/`trace` 一个都不许冒,灰色「查了待办清单」照旧(72 行) | **部分** | e2e `:193`「助手气泡 = 出错说明 1 + 正常回复 1」——只覆盖了气泡数;`session_updated`/`trace` 逐个不冒、灰色工具行,**既无断言、录像里也没有一轮带工具调用的正常对话** |
| D6 三个聊天栏各走一遍"切页重挂载"(73 行) | **没执行到**(项目栏 / 待办栏) | 首页已覆盖(e2e `:197-208` + §03/§04);项目栏(§14)、待办栏(§15)只做了"当场出现"。**缺的是**:真机手动切页再回来——判据够不着,录像脚本也没走 |

---

## 2. 缺陷

**缺陷 1(P0)——「认不出的错」把人指去点一个答非所问的「测试」。**
触发步骤:录像 §11,厂商返回一个非 key 类的 400(用的真厂商原文 `{'message': 'Invalid image data', 'type': 'invalid_request_error'}`)。
用户看到:`「模型那边出错了。再发一次试试;一直这样的话,到「设置 → 模型设置」点这家模型旁的「测试」,它会告诉你具体哪里不对。」`
问题:照简报定义,「测试」只回答"key 对不对"。这类错跟 key 无关,用户走过去点「测试」只会得到"这把 key 可用",拿不到半句"具体哪里不对";而"再发一次"对同一张被拒的图也仍然会错。这正是 P0 定义里"被误导去做错的事":绕一圈、更糊。
证据:`qa-exec/tour.md` §11 / `11.jpg`;对照简报对「测试」的定义(「会说人话告诉你 key 对不对」)。

**缺陷 2(P1)——标着「原文」的那行小字,对 DeepSeek 欠费并不是厂商原文。**
触发步骤:录像 §05,DeepSeek 欠费(402)。
用户看到:`原文:The AI provider rejected the request because the API key is out of quota or the account is in arrears. Please top up / check the billing status of your API key and try again.`
问题:DeepSeek 真正回的是 `{"message":"Insufficient Balance","type":"unknown_error","param":null,"code":"invalid_request_error"}`;界面上这行是**网关转述出来的固定英文**,不是厂商说过的话,没有 code、没有 request_id。简报说这行小字的作用是"方便发给别人看",而发出去的东西厂商认不出来。(同页 GLM 1113 那档是真原文透传,所以问题只在被网关改写的那条路径上。)
证据:`tour.md` §05 / `08.jpg`(第二个气泡)vs 探针 `20260925-probe-gateway-errors.txt` 的 `raw deepseek-402`(第 129 行)与 `mode=429q`(第 19-20 行)。

**缺陷 3(P2)——出错主句没有指向眼前唯一能对号的那个线索。**
触发步骤:任何一档出错(录像 §02 / §05)。
用户看到:`「…到「设置 → 模型设置」找到发这句时用的那家…」`,而屏幕上能对上号的只有输入框右下角的模型名 `mimo-v2.5`。
问题:同时开着好几家、每家一把 key 的设计师,得自己把"mimo-v2.5"翻译成"MiMo(小米)"才能找到该改哪一行;简报原本要求"指向「输入框右下角当前用的那家」",这条主句没把右下角那个按钮点出来(e2e 也没断言这一句)。
证据:`tour.md` §02、§05 页面文字 vs 右下角 `mimo-v2.5`。

其余检查过、**没有**问题的:未启用厂商存 key 的提示已改成和开关一致(§17 / `17.jpg`「这家现在是「未启用」…把上面「未启用」旁边的开关打开」);出错气泡有区别于正常回复的底色 + 左边框(`08.jpg`、`11.jpg` 一眼能分);跨栏不串话(§14 项目栏 / §15 待办栏各留自己的一条);重开软件后仍是中文(§16);全程页面级 JS 报错为 0。

---

## 3. 需要业主在真机上亲自走的几步(按用户的话)

1. **每家真错 key 各发一句。** 把 DeepSeek、Kimi、GLM 的 key 故意填错,各在首页发一句话 —— 看是不是**都**告诉你"到设置改 key",有没有哪家被误判成"欠费"或"限流"。(录像里假厂商回的都是 MiMo 形状的报错,别家的真报错体在界面上一次没走过。)
2. **项目助手切走再回来。** 在项目里用错的 key 发一句,等那句中文出错出来;切到「待办事项」,再切回这个项目 —— 看还是不是**同一句中文**(不是空白、不是英文)。
3. **待办页右栏切走再回来。** 在待办页右边的"项目助手"里用错的 key 发一句;出错后切到工作区/设置,再回待办页 —— 看还是不是同一句中文。
4. **完整走一遍"改好再发"。** 设置 → 模型设置,把出错那家的 key 改对,**点那行的「测试」看到它说能用**,回聊天再发一句 —— 看是否正常回复、上面那条出错说明还在、也没多冒出一条英文。
5. **认不出的错 + 转圈时切走。** ①让厂商回一个不是 key 的错(例如发一张它不认的图),顺着提示去点「测试」,看那句话兑不兑现(验缺陷 1);②用限流或断网那类(要等约 8 秒),在还转着"正在思考"的时候切到设置、停几秒再回来,看是中文出错说明,还是空白/英文。

------------------------------------------------------------
turns: 32 / 上限 200
(原始 stream-json:/root/aiwork/logs/explore-chaterr-qa-exec-20260925-142347.subdeepseek.stream.jsonl)
