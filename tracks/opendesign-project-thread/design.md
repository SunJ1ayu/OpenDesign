# Track E plan — opendesign-project-thread(项目级对话上下文,ds-web 0.20.0)

用户反馈 #2:A 项目里跟项目助手说的话,切到 B 项目应是全新上下文;并要求梳理
单项目上下文管理 + 与历史对话窗口的关系。方案 07-16 已与用户对齐(每项目一条
工作对话/localStorage 映射/历史页管全部)。

## 现状(读码坐实)
- 工作区右列 ChatColumn 单实例常驻(keep-mounted),所有项目共用一条 ws 会话
  =上下文串项目。ChatPage 已有 resume(attach 信封+thread 回放,p6)与
  dispatch/prefill 机制;协议每连接默认新 chat_id(ready 事件带回)。
- 侧栏历史对话列表=nanobot /api/chat/sessions(key=websocket:<chat_id>)。

## E1 纯逻辑 web/src/chat/projectThread.ts(oracle 直测)
- `loadThreadMap(raw)` 容错解析 localStorage JSON(坏/null→{};值非 string 剔除)。
- `threadFor(map, key)` / `withThread(map, key, chatId)` / `withoutThread(map, key)`
  (immutable,返回新对象)。
- `sessionLabels(map, projects)`:反查 sessionKey(websocket:<chatId>)→项目显示名,
  供侧栏历史行打项目小标。
- `projectPrefix(name)` = `【当前项目:<name>】`(与 AGENTS.md 规则同源的单一真相源)。
- 存储 key = `odw.projectThreads`。App 层读写 localStorage,纯函数不碰 DOM。

## E2 ChatPage 两个窄改动
- resume 目标判定:`const target = resume && resume.chatId ? resume : null;`
  ——chatId 为空串的 resume = **强制新会话**(nonce 驱动重连,不 attach)。
  现有语义(null=不重连、有 chatId=attach)逐字不变。
- 新可选 prop `onChatId?: (chatId: string) => void`:连上(ready 新会话/attached
  均)回调真实 chat_id —— App 借此把新会话记进项目映射(幂等)。
- 新可选 prop `onAttachFailed?: () => void`:attach 报 error 时回调(自愈:App 清
  该项目映射并强制新会话重连,映射指向已删会话时不再卡死在错误页)。
- 新可选 prop `firstSendPrefix?: string`:sendText 时若 transcript.messages 为空
  (本会话第一句、且无回放内容)→ content 前拼前缀。回放晚到竞态=前缀重复一次,
  无害(agent 多看到一次项目名)。前缀对用户可见(诚实,消息气泡里能看到)。
- home 实例不传这三个 prop,行为零变化。

## E3 App/ChatColumn/Sidebar 接线
- App 状态 `projThreads`(init=localStorage,变更即持久化);
  `colResume` = selectedKey 变化时派生:有映射→attach 目标,无→`chatId:""` 强制
  新会话;nonce 每次切项目自增。连接发起时用 ref 记住"这条连接属于哪个项目",
  onChatId 回来按 ref 记映射(防切换竞态记错项目)。
- ChatColumn 头部加「+ 新对话」:清当前项目映射+强制新会话;旧会话自然退回
  全局历史(可从历史页点回,那是 home 实例的续聊,现有 p6 行为)。
- 未选中项目/未建档项目:列照常可聊,key 即 selectedKey(未建档 key 也稳定)。
- deleteSession(历史页删除):同时清掉指向该会话的项目映射(防悬空 attach)。
- Sidebar 历史行:命中项目映射的会话加项目名小标(sessionLabels)。
- 首页 3a 实例:完全不动(不绑项目的自由入口)。

## E4 AGENTS.md
- 规则:消息以 `【当前项目:X】` 开头 = 工作台项目页发来,本对话默认项目=X;
  记变更/待办/读项目默认落 X,除非设计师明确点名其他项目。

## E5 验证
- oracle mjs:projectThread 纯函数全覆盖(容错/immutable/反查/前缀)。
- e2e 真 gateway+真 MiMo(driver 沉淀进 tests/=还 O1 工具债):
  ①选项目A发消息(断言带前缀)→②切项目B=新上下文(transcript 清空、chat_id 变)
  →③切回A=attach 回放(A 的消息还在)→④映射 localStorage 持久。
- verify lane:fast(纯前端+AGENTS.md;协议面复用 p6 已审机制)+ e2e 实证。
- 版本 0.19.0 → 0.20.0。
