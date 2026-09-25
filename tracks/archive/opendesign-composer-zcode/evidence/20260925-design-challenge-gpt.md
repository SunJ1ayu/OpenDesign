## 1. 业主目标仍会怎样失败
Direction: 将「停止」做成跨页面持续可见的运行控制，而不只是在当前 `ChatPage` 中把发送键换成 ■。

Core bet: 用户在项目助手发起长回复后切到首页，项目聊天仍因 keep-mounted 在隐藏处运行（`web/src/App.tsx:573-588`、`web/src/app.css:137-139`），但首页拥有独立 `busy` 状态，只会显示 ↑；用户看不到 ■，模型仍可能计费或调用工具，必须切回原页面才能停止。

## 2. 必须成立的机制前提
How it works: 当前 nanobot 确实把 `/stop` 作为优先命令，按 session key 取消任务（`nanobot/agent/loop.py:900-908,650-661`），取消后发 `goal_status:idle` 而不发 `turn_end`，且不记录 `/stop` 用户行（`nanobot/agent/loop.py:1080-1116`、`nanobot/webui/transcript.py:665-667`）；因此应仅在该聊天已进入 `stopPending` 时把 `idle` 当停止终态，正常回复仍以 `turn_end` 收尾。

Blind spots in the brief: 若 Windows 安装版启用 `unified_session`，一次 `/stop` 会按共享 effective key 取消其他聊天任务，方案必须重做；快照默认值为 false（`nanobot/config/schema.py:141-146`），但业主机器配置未核实；此外待办页还有未纳入五条的紧凑输入框，仍显示文字「发送」（`web/src/TodoRail.tsx:225-236`），而自定义厂商名最长 40 字且括号可能承载关键身份，机械去括号可能误报扣费方（`bin/ds_credential.py:1220-1227`）。

## 3. 更稳方向与最小实验
Best at: 让每个 `ChatPage` 向 `App` 登记 `{slot, busy, stop}`，除本地 ■ 外显示一条跨路由运行提示；点击后向原 chat_id 发送 `/stop`，不追加用户气泡，并由该 slot 的 `stopPending + idle` 定稿半截回复。

Sacrifices: 比单纯修改按钮多一层全局运行状态和并发聊天处理，但避免把无 `turn_id` 的任意 `idle` 当成本轮结束，也保证切页后仍能立即止损；其余四条仍可按原方案实施。

Smallest first step: 做一个仅覆盖“项目助手开始流式回复→切到首页→仍看到停止提示→点击后向项目 chat_id 发 `/stop`→保留半截并解锁”的假 WebSocket 交互实验；拟议方案会在切页后失去停止入口，本方向不会。快照 `review.diff` 为空，因此这是机制评估而非现成改动审查。

结论: 需改
