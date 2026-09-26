# 方案挑战:OpenDesign「模型出错时聊天页什么都不显示」

你是独立的方案挑战者。仓库在当前目录(design-studio,产品名 OpenDesign:室内设计师用的本地桌面助手,
Electron 窗口里是 React 网页 `web/src`,聊天经 WebSocket 直连本机 nanobot 网关)。业主不是程序员,Windows 11 安装版。
**不要联网;不要改任何文件;不要读 `tracks/*/verify.md`、`tracks/*/design.md`、`tracks/*/proposal.md` 与任何 `*my-review*` / `*my-direction*` 文件。**
nanobot 源码在 `/root/.venvs/design-studio/lib/python3.12/site-packages/nanobot/`(读得到就读;读不到请明说,别猜)。

## 来由
上一单测试员看真界面录像时发现:API Key 填错后发一句话,聊天页「没反应」—— 没有回复、没有任何提示。
业主 09-25 同意下一版先修这个(「就按你建议的来吧」),原话里没有更多细节;「说人话、告诉他哪里不对」是我们的推导。

## 已核实的事实(真 nanobot 网关 + 本机假厂商,本单探针)
- 五种出错(key 错 401 / 欠费 429 insufficient_quota / 限流 429 / 厂商 500 / 地址连不上),网关实时发的序列**都一样**:
  `goal_status(running)` → `stream_end`(之前没有任何 `delta`)→ `message`(**没有 `kind` 字段**,`text` 是整句原文)→ `turn_end`。
- 各自的 `text` 原文:
  - `Error: {'message': 'Invalid API key', 'type': 'invalid_request_error'}`
  - `The AI provider rejected the request because the API key is out of quota or the account is in arrears. Please top up / check the billing status of your API key and try again.`
  - `Error: {'message': 'Rate limit reached for requests', 'type': 'rate_limit_error'}`(网关先自己重试约 7 秒)
  - `Error: {'message': 'internal server error', 'type': 'server_error'}`(同上约 7 秒)
  - `Error calling LLM: Connection error.`(同上约 7 秒)
- 网页端 `web/src/chat/transcript.ts` 的 `applyEvent`:`message` 事件只认 `kind` 为 `progress` / `tool_hint`,其余整条丢弃 ⇒ 实时什么都不显示。
- 切到别处再切回来(网页调 `webui-thread` 回放历史,`hydrateFromThread`):这条原文**已经是一条 assistant 行**,于是冒出上面的英文原文。
  回放行里没有「这句是哪个模型/哪家回的」字段。
- 设置页每个模型行有「测试」按钮(`bin/ds_credential.py` `test_model` / `_plain_http_reason`),失败时已经会说人话(带 HTTP 状态码)。
- 另有一条独立的现状文案错误要顺带改:`web/src/settings/modelSettings.ts` 里提示「在上面打开「启用」」,而开关旁实际显示的字是「未启用 / 已启用」。

## 拟议的改变(被挑战的对象)
用户层:模型出错时,聊天里出现一条助手回复,用中文说清是哪类问题、去哪里处理(key 不对 → 去模型设置重填并点「测试」;
额度/欠费 → 去厂商那边充值;太频繁 → 稍等再发;连不上/超时/厂商出错 → 稍后再试),原文以小字附在后面备查。
切走再切回来看到的是同一句中文。
机制:`applyEvent` 把**所有没有 kind 的 `message`**(不只是出错)当成一条完整的助手消息追加;出错原文由一个共用函数
按 nanobot 的固定前缀/固定句识别、再按厂商原文关键词分类成人话;回放 `hydrateFromThread` 走同一个函数。不点厂商名(回放里拿不到)。

## 请回答(先从业主目标推演,再挑机制;没有就说没有,不必凑)
1. 这个改变**完全照做**之后,业主的目标仍会怎样失败?(具体到操作步骤与会看到什么)
2. 哪个前提若为假,就得推倒重做?请尽量读代码核实,给出 `文件:行` 证据;核实不了的标「未核实」。
3. 有没有更简单或更稳的方向?用什么**最小实验**能分辨它和拟议方案?

输出:按 1/2/3 分节,每条一句结论 + 证据;最后一行写 `结论: 可行 / 需改 / 不可行`。
