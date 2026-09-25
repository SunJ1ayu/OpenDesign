# 方案挑战:OpenDesign 聊天输入框照 ZCode 改五条(含「停止」键)

你是独立的方案挑战者。仓库在当前目录(design-studio,产品名 OpenDesign:室内设计师用的本地桌面助手,
Electron 窗口里是 React 网页 `web/src`,聊天经 WebSocket 直连本机 nanobot 网关)。业主不是程序员,Windows 11 安装版。
**不要联网;不要改任何文件;不要读 `tracks/*/verify.md`、`tracks/*/design.md`、`tracks/*/proposal.md` 与任何 `*my-review*` / `*my-direction*` 文件。**
nanobot 源码在 `/root/.venvs/design-studio/lib/python3.12/site-packages/nanobot/`(读得到就读;读不到请明说,别猜)。
可以读 `tracks/opendesign-composer-zcode/evidence/` 下的探针脚本与输出。

## 来由(区分业主原话和我们的推导)
- 业主 09-24 看了 ZCode(另一款 AI 桌面应用)的输入框,觉得我们的「✎ 记一下」按钮「有点笨」。我们出了对照图 + 五条建议,
  业主 09-25 原话:「可以，就按你建议的来吧」。**五条的具体内容是我们提的**,业主没有逐条改过:
  ① 「+」变成菜单:加图片 + 三个技能(记一下 / 整理文件夹 / 找参考图,点了在输入框里补好开头);去掉「✎ 记一下」按钮;
  ② 输入框里打 / 也弹出同一份技能表,手不用离开键盘;
  ③ 模型按钮前面带厂商名(如「MiMo · mimo-v2.5」),一眼看出扣哪家的钱;
  ④ 发送换成 ↑ 图标;回复时变成 ■ 停止 —— 说跑偏了能马上打断;
  ⑤ 问候语按时间变。
  不抄:ZCode 的模式、电脑操作、用量圆环、推理强度。「引用某个项目 / 之前的对话」以后再做。

## 现状(已核实)
- 输入卡在 `web/src/chat/ChatPage.tsx`(约 690–850 行):「+」只打开选图;「✎ 记一下」在草稿前补「记一下:」;模型按钮只写模型名
  (`web/src/chat/modelPicker.ts` `modelChipLabel`);「发送」是文字按钮,回复中置灰,**没有停止**。发送走 `sendText`,回复中(busy)拒发。
- 三个技能及各自补的开头在 `web/src/SkillsPage.tsx`(技能页,点卡片开新对话并预填)。
- 占位符 `web/src/chat/inputHint.ts`:「聊设计、找参考,或「记一下…」」。
- 首页问候语固定「今天想聊点什么?」(`ChatPage.tsx` 约 990 行)。
- 同一个网页里有三个聊天栏(首页 / 项目助手 / 待办右栏),各自一条 WebSocket、各自一个 chat_id;切页只隐藏不卸载。
- 厂商名来自 `bin/ds_credential.py` 的 `label`:「MiMo(小米)」「DeepSeek 官方」「Kimi 按量」「GLM 套餐(Coding Plan)」「GLM 按量」,
  业主还能「添加供应商」自己起名。`/api/llm/models` 回当前厂商的 label 与模型。
- 聊天事件归约在 `web/src/chat/transcript.ts` `applyEvent`:busy 只由 `turn_end` / `error` 解锁;`goal_status` 只用 running 开「正在思考」。
  没有 kind 的 `message` 显示成一条助手回复(上一单刚改的,出错壳由 `web/src/chat/modelError.ts` 换成中文)。
- 工具:助手的工具是三个独立进程的 MCP 服务(`bin/ds_mcp.py tools|organize|refs`),单次工具调用网关等 30 秒超时。

## 探针(真 nanobot 网关 + 本机假厂商,`evidence/probe-stop.py`,输出 `evidence/20260925-probe-stop.txt`)
回复进行中往同一个 chat_id 发一条内容为 `/stop` 的消息:
- 网关立即:`goal_status:running`(重发)→ `goal_status:idle` → `message`(无 kind)“Stopped 1 task(s).”;**不发 stream_end / turn_end**;
  假厂商那边的流被断开。还没出第一个字(模型在想)时停,序列相同。没有在回复时发 /stop:只回 “No active task to stop.”。
- 回放(`webui-thread`):已出来的半截回答是一条完整的助手行;“Stopped 1 task(s).” / “No active task to stop.” 各是一条助手行;
  `/stop` 本身不留用户行。之后再发一句,正常回复。

## 拟议的改变(被挑战的对象)
用户层:就是上面五条。「+」菜单 = 图片 + 三个技能,点技能在输入框补好开头(已有草稿就接在后面;已经是某个技能开头就换掉,不叠);
打 /:草稿以 / 开头且还没有空格时弹技能表,按 / 后的字筛,↑↓/Enter/Esc,筛不到就不弹、Enter 照常发送;
模型按钮「厂商短名 · 模型名」,短名 = 厂商名去掉括号部分(MiMo(小米)→ MiMo、GLM 套餐(Coding Plan)→ GLM 套餐);
■ 停止:点了在同一聊天发 `/stop`,不上屏用户气泡,出现一行中文小字「已停止」,半截回答保留;问候语早上好 / 中午好 / 下午好 / 晚上好。
机制:`goal_status:idle` 当作这一轮结束(解锁输入、收思考、定稿半截正文);“Stopped …” / “No active task …” / “Background task completed.”
实时和回放都换成中文系统小字(同一个函数)。技能表抽成一个模块,技能页和菜单共用。不改 nanobot。

## 请回答(先从业主目标推演,再挑机制;没有就说没有,不必凑)
1. 这个改变**完全照做**之后,业主的目标仍会怎样失败?(具体到操作步骤与会看到什么)
2. 哪个前提若为假,就得推倒重做?请尽量读代码核实,给出 `文件:行` 证据;核实不了的标「未核实」。
3. 有没有更简单或更稳的方向?用什么**最小实验**能分辨它和拟议方案?

输出:按 1/2/3 分节,每条一句结论 + 证据;最后一行写 `结论: 可行 / 需改 / 不可行`。
