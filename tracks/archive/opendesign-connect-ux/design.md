# Design: opendesign-connect-ux

- Change: opendesign-connect-ux
- Status: final(三处均为封闭修复,无开放分叉,不跑 panel-explore)

## Approach(每处从根因下手,不打补丁)

### ① 接入工作区:让按钮的承诺与行为一致
根因:按钮写「接入工作区」,行为是往聊天框填半句话——承诺与行为不匹配,用户
以为点了=接了。绕聊天是架构必然(ds_web 无写面,写只能走 MCP 工具=对话),
但"用户自己补完句子再回车"这个悬空步骤可以消掉:
- CompanionColumn 接入区:点「接入工作区」→ 就地展开路径输入(一行说明
  "工作台在浏览器里看不到你的磁盘,把项目文件夹路径贴给助手" + input +
  「发给助手」,空路径禁用)→ 确认 = 完整消息直接发进聊天。
- `onConnectWorkspace` 签名 `() => void` → `(path: string) => void`;App 组装
  完整消息 `把我的项目文件夹接进来,路径是:<path>`。

### ChatPage 新原语:dispatch(与 prefill 平行,不是特例补丁)
- `dispatch?: { text: string; nonce: number }`:nonce 变化 → 能发就直接发
  (连接中+不 busy),不能发 → 优雅降级为预填+聚焦(与 prefill 同终态,
  动作不丢)。nonce 消费用 ref 去重。
- send 路径收敛为单一 `sendText(content): boolean`(现 send=读 draft 的壳),
  dispatch/按钮/Enter 三入口共用一条发送真相源——不复制 envelope 逻辑。

### ② 思考中指示:补上"发出→首个 delta"之间的信号真空
根因:transcript.busy 已有(发出→turn_end),但 UI 只用它锁按钮。
- 派生态 `waiting = busy && 末条消息 role==="user"`(assistant 开始流式后
  末条变 assistant,指示自然消失——零新状态,纯派生)。
- waiting 时消息流尾部渲染三点跳动气泡(CSS animation,无 JS 定时器)。

### ③ AGENTS.md:folder_count=0 → 一个二选一问题
根因:话术给了背景没给剧本,弱模型自由发挥。收敛为固定一问:
"项目文件夹是直接放在这个目录下,还是先按年份/客户分了一层?"
①→ projects_dir="." ②→ projects_dir="." + projects_depth=2。

## Key trade-offs / risks

- dispatch 在未连接/busy 时降级为预填=动作不丢但不自动发;不做队列重发
  (队列引入时序复杂度,真机首用场景是"已连接后点接入",降级是罕见路径)。
- send 收敛为 sendText 触碰 p3 冻结过的路径——该冻结是 p3 任务约束(变体重构
  期防手滑),非永久法;单一真相源优于复制第二条 envelope 路径。回归护栏=
  既有 e2e 剧本 + mjs oracle。
- AGENTS.md 更新须随 install 拷贝才对运行 agent 生效(既有 deviation,工具
  先行话术滞后无害)。

## Test strategy (oracle)

- mjs:transcript 不动(零新状态);shouldSendOnEnter 不动。新纯逻辑仅
  waiting 派生——内联一行,不值得抽文件,由 e2e/组件层验证。
- e2e(真 gateway,enable_webui.py 起):①点「接入工作区」→ 填路径 → 确认 →
  聊天流出现完整用户消息(不是草稿);②发送后立即断言 thinking 气泡存在,
  turn_end 后消失。跑不了真 gateway 则降级为 build+人工验收,记 deviation。
- build 绿;VERSION 0.15.0;verify lane=fast(纯前端+话术,无 schema/钱/权限面)。
