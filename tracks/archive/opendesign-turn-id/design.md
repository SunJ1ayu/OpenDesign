# Design: opendesign-turn-id

- Change: opendesign-turn-id
- Status: draft

- 规划双出: **不适用** —— 不是新写面、不是开放方向:协议里已经有现成身份
  (`turn_id` 出站 / `turnId` 回放),本单只是"用上它"。方向唯一,双出问不出新东西。
  (触发条件的另一半是"这单要外包给执行腿" —— 见 verify.md `派给:`;若外包,
  派活 brief 里仍要带那句"顺手攻一遍我的 oracle",漏洞清单只回给我。)

## 协议地基(实抓,不是推测)

`scratchpad/probe_turnid.py` 08-05 对活 gateway 实跑一轮(证据抄进 evidence/):

```
我发出去的 turn_id = 6b7f6c72-741f-4fdd-8377-76b20e475616
回放 messages:
  {"id":"u-0-5172a6cf","role":"user","turnId":"6b7f6c72-…","turnPhase":"user","turnSeq":1}
  {"id":"as-1-9efa16ee","role":"assistant","turnId":"6b7f6c72-…","turnPhase":"answer","turnSeq":9}
结论:回放 user.turnId == 我发的 turn_id ✅
```

两条推论,后面全部设计都压在它们上:

1. **user 消息的身份是我们自己给的** ⇒ 本地存一份即可对账,不需要服务端另发 id。
2. **同一 turn 的 assistant 消息带同一个 turnId** ⇒ turnId **不是消息级唯一键**,
   一个 turn 至少两条。所以对账只用它匹配 **user 侧**(与四审 P3「助手侧一律以
   服务端为准」的既有结论一致,不冲突)。

## Approach

三处小改 + 一次提纯:

1. `ChatMessage` 增可选 `turnId?: string`。
   - `appendLocalUser(state, content, id, media, turnId?)` 存下发出去的那个;
   - `hydrateFromThread` 从回放行的 `turnId`(字符串且非空才收)读回来。
2. 把 ChatPage 里 `mode === "reconcile"` 那段**原样提成纯函数**
   `reconcileThread(local: ChatMessage[], replay: ChatMessage[]): ChatMessage[]`
   放进 `transcript.ts`,判定规则升级为:
   - 服务端已有的 turnId 集合 = `replay` 里 role==="user" 且 turnId 非空的那些;
   - 本地一条 user 消息算"服务端已有" ⇔ **它有 turnId 且 turnId ∈ 该集合**;
   - **turnId 缺失时**(老会话前插进来的本地消息、任何拿不到 id 的路径)
     退回原来的 `role\0content` 启发式 —— 只在这条路径上保留旧行为,不做行为倒退;
   - assistant 侧一律以服务端为准(既有结论,原样保留)。
3. 发送口收口:`sendText` 里先查 `ws.readyState === WebSocket.OPEN`,
   并把 `ws.send` 包进 try/catch;发不出去就**不 append 本地气泡**、
   不清附件、给一句 `turnError` 人话("没发出去,正在重连,稍后再试")。

## Key trade-offs / risks

- **提纯 vs 少动代码**(workspace CLAUDE.md「不重构没坏的东西」):这段逻辑本单必须改,
  而它现在长在 `setTranscript` 回调里、单测咬不住 —— 上一单它出过两个 HIGH,
  全靠 e2e 才照见。提纯是**为了让判据够得着**,不是顺手美化;搬运范围严格限制在这段。
- **turnId 缺失的退路**:留启发式 = 留着那个已知的误判口子,但只在"本来就没有身份"
  的路径上。全删会让老路径直接丢消息,更糟。
- **`crypto.randomUUID` 一份变两用**:现在信封的 turn_id 与本地气泡 id 是两次独立
  `randomUUID()`。改后本地消息的 `turnId` 必须与信封里那个**同一个值** ——
  写成两次调用就是一个静默的假实现(判据钉死:e2e 从 `window.__sent` 里读真信封比对)。
- **发送口收口的反向风险**:判"没连上"判严了,会把本来能发出去的消息拦下来
  (用户眼里=按了没反应)。所以只拦 `readyState !== OPEN` 与 `send()` 真抛异常
  这两种确定失败,不加任何"我觉得网络不好"的猜测。

## Alternatives considered

- **按 (role, content, 出现次序) 计数配对**:纯前端不加字段就能修"同句两遍"。
  没选:它只是把猜法变复杂,断线时服务端少记一条,次序照样错位;而真身份是现成的。
- **给本地消息用服务端 id**:服务端 id(`u-0-…`)只有回放时才有,发的那一刻拿不到 ——
  正好是需要身份的那一刻。不可行。
- **等做"发送状态角标"时一起改**:那要用户先拍板产品形状,而丢消息是现在就在的伤。

## Test strategy (oracle)

主 agent 亲写,执行腿逐字节 off-limits。三层:

- **O1 纯逻辑**(`tests/test_chat_transcript.mjs` 增一组):`reconcileThread` 判定表 ——
  ① 同句两遍、服务端只记上第一遍 ⇒ 两条都还在,且顺序是"服务端的在前、本地独有的在后";
  ② 服务端记上了的不重复追加;③ 本地 assistant 半截气泡一律丢弃;
  ④ 本地消息没有 turnId ⇒ 退回文本启发式(老行为不倒退);
  ⑤ 服务端行没有 turnId(老会话)⇒ 也退回文本启发式,不把本地消息误判成"服务端没有";
  ⑥ `hydrateFromThread` 读得到 turnId、`appendLocalUser` 存得住 turnId。
- **O2 端到端**(`tests/e2e/chat_reconnect.e2e.mjs` 增一幕):同一句话发两遍、
  第二遍服务端"没记上"(`__silent`),掐断 → 重连 → 断言**两条气泡都在**
  (旧实现在这里必红:文本相同 ⇒ 第二条被吃掉)。夹具从 `window.__sent` 里取
  **真信封的 turn_id** 塞进 stub 历史 —— 这样"实现把信封 turn_id 和本地 turnId
  写成两个不同 uuid"会被照出来。
- **O3 发送失败**(同 e2e 增一幕):`__sendThrows` 时 stub 的 `send()` 抛异常 ⇒
  断言**不出现**那条用户气泡、且屏上有一句提示(不是静默吞掉,也不是假装成功)。

**这个 oracle 能被什么骗过?**

- 全绿而用户仍丢字的最可能形状:**本单根本不是丢字的主因**。真机上更常见的是
  "网页整个刷新了"(本地 state 全丢,与对账无关)。O1/O2 对这种一无所知。
  接得住它的只有真机:用户在断网前后各说一句,重连后自己看两句在不在。
  ⇒ 已进 tasks.md 真机待验。
- 第二种:turnId 存住了、对账也对了,但**顺序**看着不对(自己刚说的那句被排到很后面)。
  断言只锁了"两条都在 + 本地独有的在尾部",顺不顺手判据接不住 ⇒ 同样进真机待验。
- 第三种:O3 只证明"没上屏 + 有提示",证明不了那句提示**说人话**
  ⇒ 收尾截图看一眼(自审闸)。
