# Design: opendesign-workbench-p6

- Change: opendesign-workbench-p6
- Status: final

无开放架构分叉(协议/接口都是现成的,唯一站得住的路径 = attach + thread 回放),
不开 panel-explore。

## Approach

**D1 续聊 = attach,不是只读回看。** 点历史行:路由回 `#/`(首页聊天,keep-mounted
实例),ChatPage 收 `resume` prop(`{sessionKey, chatId, nonce}`)→ 连接 effect 重跑:
开新 ws → 收 `ready`(服务端默认新 chat_id,弃用)→ 发 `{type:"attach", chat_id}` →
收 `attached` 才置 connected(chatId = 恢复目标);并行 `apiFetch(…/thread)` 回放历史
进 transcript。之后 send 走既有代码路径(信封带恢复的 chatId)。
`新对话`/⌘N → resume 置 null,effect 依赖 `resume?.nonce ?? 0` 变化 → 重连拿全新
chat_id(现行为不变)。

**D2 回放解析 = transcript.ts 纯函数。** `hydrateFromThread(payload)`:取 `messages[]`,
只收 role∈{user,assistant} 且 content 为 string 的行,跳过 `kind:"trace"` 与空
assistant;id 用服务端的(缺则 `replay-<i>`);streaming=false,busy=false。
出站信封同样加纯函数 `attachEnvelope(chatId)`。都进 transcript.ts(node --test 直测)。

**D3 列表刷新 = turn_end 回调,不轮询。** ChatPage 加 `onTurnEnd`:onmessage 认出
`event==="turn_end"` 时调用(每轮恰一次)。App 接到既有 `sessionsEpoch` 递增(与
onConnected 同一根线);首页与 2a 右列两个实例都接。

## Key trade-offs / risks

- 回放失败(404/坏 payload)→ 静默降级:attach 仍成立,transcript 从空开始(与全库
  "失败静默为 null"哲学一致);attach 失败(error/断开)→ 走既有 error 视图。
- 恢复连接同时被服务端 attach 在默认新 chat_id 上;不向它发消息即无副作用。
- turn_end 在 fold 之外由 onmessage 直接识别:与节流缓冲并存,刷新最多晚 0ms(事件
  即回调),不依赖 fold 时序。

## Alternatives considered

- 只读回看(thread 渲染成静态页):多一套 UI 状态,且自废协议原生续聊能力,拒。
- 列表轮询/localStorage 广播:单人本地工具,turn_end 事件已是精确信号,拒。

## Test strategy (oracle)

- mjs:`hydrateFromThread`(畸形/trace/空 assistant/id 缺省/正常)+ `attachEnvelope`
  进 tests/test_chat_transcript.mjs,先红后绿;既有 47 用例不动全绿。
- py:全套回归(ds_web 零改动,守住不回归)。
- e2e 真 gateway(driver 在 scratchpad,结果进 verify.md):①聊一轮→列表无刷新
  出现;②点历史→旧消息回放;③续发→回复归同一会话(thread 增长)。

## 硬约束(继承 p3)

connection.ts 逻辑不动;transcript.ts 只加纯函数不改既有 fold;send/节流/Enter 判定
代码路径不动;Sidebar 零样式改动;ds_web.py 零改动;VERSION 0.6.1 → 0.7.0。
