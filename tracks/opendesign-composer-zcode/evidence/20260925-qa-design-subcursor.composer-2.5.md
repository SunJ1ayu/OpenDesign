Reading the diff and exploring the repository to ground the test design.

The repository snapshot contains only `README.md` (“黑盒测试台 / 故意没有代码”); `review.diff` is empty. Claims below are grounded in the task brief only, not in source.

---

**Direction:** Treat the five input-box changes as one **interaction contract** per chat surface (首页 / 项目助手 / 待办助手), with **stop (■)** and **shared skill source** as the highest-risk axes; validate P0 on all three surfaces before deep P2 polish.

**Core bet:** Users experience one consistent “+ / / / 模型标签 / 发送→停止” model everywhere they chat; regressions will cluster at **IME + Enter**, **slash picker vs send**, and **stop timing vs partial stream**, not at copy-only greeting text.

**How it works:** Map each brief bullet to observable UI states (menu open, slash filter, `厂商 · 模型`, ■ vs ↑, time-based greeting, error footnote labels, Chinese system lines). Build cases as state transitions: idle → streaming → stopped/error → idle, including “stop then immediate resend.” Use the brief’s skill prefixes and vendor short-name rules as the oracle. Cross-check 发图/拖图/Ctrl+V (max 4), 技能页, and 模型菜单 as touchpoints, not separate products.

**Best at:** Catching user-visible wrong behavior (mis-send on `/`, stop not unlocking input, duplicate skill prefixes, English leaks, misleading「原文」) and **multi-pane** mistakes (stop one thread only).

**Sacrifices:** No automated UI harness or API-level stop semantics; no proof that background tasks actually finished after stop; no vendor API fault injection without a built app.

**Blind spots in the brief:** Exact time bands for 早上/中午/下午/晚上/夜深了; whether slash menu appears in 项目/待办 placeholders; Tab vs Enter for slash pick when both are specified; model button during stream; whether「+」menu stays usable while replying; definition of「后台改写」vs「厂商原话」for every error code.

**Smallest first step:** One P0 **主流程** matrix on **首页**: open「+」→ pick「记一下」→ confirm prefix + cursor; type `/参` → pick 找参考图; confirm model shows `短名 · 模型名`; send → ■ during「正在思考」→ gray「已停止」, input unlocked, no `/stop` bubble; resend once.

---

## 1. 用户故事 + 验收标准

### US-1「+」菜单与技能前缀
- **Given** 用户在任一聊天栏，输入框为空或已有任意文字（含已有图片缩略图）  
- **When** 用户点「+」并选「图片」或某一技能  
- **Then** 选图片：行为与现网一致（拖入/Ctrl+V 仍可用，最多 4 张）；选技能：输入框**最前**变为对应开头（记一下:`记一下:`；整理文件夹:`帮我扫描整理这个文件夹:`；找参考图:`找参考图:`），原文字保留在后，光标在开头后；若已是某技能开头则**替换**为新技能开头，不叠两层；「✎ 记一下」按钮不存在；菜单中技能与技能页列表一致（名称与三项齐全）。

### US-2 输入 `/` 选技能
- **Given** 输入框内容以 `/` 开头且 `/` 后尚无空格  
- **When** 用户继续输入筛选字或用 ↑↓/Enter(Tab)/Esc  
- **Then** 弹出与「+」相同的技能表；筛选缩小列表；Enter/Tab 应用选中技能（同 US-1 前缀规则）；Esc 关闭且不改动已有 `/` 除非用户自己删；无匹配技能时不弹层，Enter 将整句（含 `/`）作为普通消息发送；占位符为「聊设计、找参考;输入 / 选技能」（项目助手栏仍为项目向占位，若题面仅改首页则仅验收首页—见疑问）。

### US-3 模型按钮显示厂商短名
- **Given** 设置里已配置多家供应商与当前模型  
- **When** 用户看输入区模型按钮或切换模型/供应商  
- **Then** 按钮文案为「厂商短名 · 模型名」，短名规则：去掉设置名括号内后缀；自定义供应商名原样；切换后按钮立即更新，三处聊天栏各自显示**当前栏**所选模型。

### US-4 发送 ↑ / 停止 ■
- **Given** 用户已输入可发送内容（含仅图片）  
- **When** 点 ↑ 发送  
- **Then** 进入回复态：按钮变 ■，输入框按现网逻辑锁定（与「发送变灰」一致）；点 ■  
- **Then** 流式与「正在思考」均停止；已输出内容保留；出现灰色小字「已停止」；无 `/stop` 用户气泡；输入框可继续编辑并再次发送；重开应用或切换页再回，仍为中文「已停止」及已停内容。后台动作可能已完成但不继续汇报（不测砸墙，仅测 UI 不再刷出新助手内容）。

### US-5 首页时间问候
- **Given** 首页无对话内容，系统时间处于各时段  
- **When** 用户打开首页聊天  
- **Then** 大字问候为「{早上好|中午好|下午好|晚上好|夜深了},今天想聊点什么?」之一，与当前时间一致（时段边界见拍板）。

### US-6 出错说明与系统消息（顺带）
- **Given** 模型或后台返回错误/系统消息  
- **When** 聊天展示粉色错误条或系统提示  
- **Then** 后台改写类错误：小字**不**再标「原文」，用产品约定新标签；真厂商原文仍标「原文」；原英文系统句（如 Stopped 1 task(s). 等）改为中文展示。

---

## 2. 测试用例表（节选；完整表应扩至全编号）

| 编号 | 优先级 | 前置条件 | 操作步骤 | 期望结果 | 类型 |
|------|--------|----------|----------|----------|------|
| TC-001 | P0 | 首页，输入框有字「业主说要改吊顶」 | 「+」→ 记一下 | 框内为「记一下:业主说要改吊顶」，光标在冒号后 | 主流程 |
| TC-002 | P0 | 框内已是「记一下:xxx」 | 「+」→ 找参考图 | 变为「找参考图:xxx」，无「记一下:找参考图:」 | 主流程 |
| TC-003 | P0 | 框内已有 2 张图 | 「+」→ 整理文件夹 | 前缀正确，图片仍在，可发送 | 组合 |
| TC-004 | P1 | 任意 | 查「+」菜单与技能页 | 三项技能名称一致 | 回归 |
| TC-005 | P0 | 空框 | 输入 `/` | 弹出完整技能表 | 主流程 |
| TC-006 | P0 | 已输入 `/参` | 观察列表 | 仅「找参考图」相关项 | 主流程 |
| TC-007 | P0 | `/zzz` 无匹配 | 按 Enter | 无弹层，消息以 `/zzz` 发出 | 边界 |
| TC-008 | P0 | `/记` 列表打开 | ↑↓ 选第二项，Enter | 应用对应技能前缀 | 主流程 |
| TC-009 | P1 | slash 列表打开 | Esc | 列表关闭，内容仍为 `/记` | 主流程 |
| TC-010 | P0 | 中文输入法拼「你好」未上屏 | 按 Enter | 选字上屏，**不**发送 | 回归 |
| TC-011 | P0 | 英文内容就绪 | Enter | 发送，与现网一致 | 回归 |
| TC-012 | P0 | 已选 MiMo(小米) + mimo-v2.5 | 看模型按钮 | 「MiMo · mimo-v2.5」 | 主流程 |
| TC-013 | P1 | 自定义供应商「张三 API」 | 选其下模型 | 「张三 API · {模型名}」 | 主流程 |
| TC-014 | P1 | 回复中 | 打开模型菜单换模型 | 按钮文案更新；不误触停止 | 组合 |
| TC-015 | P0 | 刚点 ↑ | 立即点 ■（仍在正在思考） | 思考停，无新字，「已停止」，可输入 | 失败路径 |
| TC-016 | P0 | 流式出字中 | 点 ■ | 半截回答保留，「已停止」，可再发 | 失败路径 |
| TC-017 | P0 | 流式将结束 | 最后一字刚出完瞬间点 ■ | 不崩溃；有「已停止」或自然结束二选一行为稳定且无重复气泡 | 失败路径 |
| TC-018 | P0 | 已停 | 立刻再点 ↑ | 新一条用户消息正常，按钮再变 ■ | 失败路径 |
| TC-019 | P1 | 回复中 | 点「+」 | 菜单可开；选技能只改输入框，不误发 | 组合 |
| TC-020 | P1 | 三栏同时回复 | 只停项目助手栏 | 仅该栏停，另两栏继续 | 组合 |
| TC-021 | P1 | 「+」菜单打开 | 拖入图片 | 图片进框，菜单关闭或不妨碍，最多 4 张 | 组合 |
| TC-022 | P1 | 网络断开且回复中 | 点 ■ | 停止 UI 仍出现，输入解锁；错误时另有粉色条 | 失败路径 |
| TC-023 | P0 | 粉色错误（欠费类改写） | 看小字 | 非「原文」标签 | 主流程 |
| TC-024 | P1 | 粉色错误（厂商原文） | 看小字 | 仍「原文:…」 | 主流程 |
| TC-025 | P1 | 触发原英文系统消息场景 | 看聊天 | 中文文案 | 回归 |
| TC-026 | P2 | 凌晨边界时间 | 开首页 | 问候与时段定义一致 | 边界 |
| TC-027 | P0 | 项目助手栏 | 重复 TC-001/015 | 同规则 | 回归 |
| TC-028 | P0 | 待办助手栏 | 重复 TC-001/015 | 同规则 | 回归 |
| TC-029 | P1 | 历史对话含「已停止」 | 滚动回看 | 文案仍为灰色「已停止」，中文 | 回归 |
| TC-030 | P1 | 出错后 | 看 ↑/■ 与输入框 | 可编辑可重发，不被永久锁死 | 失败路径 |

---

## 3. 探索式测试任务

1. **停止键「抢时机」**（30 min）：在同一对话里轮流在思考前 0.5s、首 token、中段、长按连续点 ■，记录是否出现双「已停止」、输入框假锁、或助手继续吐字。  
2. **Slash + IME 混打**（20 min）：先 `/` 再切搜狗/微软拼音输入「参考」，验证弹层、选字、发送三者不互相抢 Enter。  
3. **三栏并发**（25 min）：首页问长问题、项目栏「记一下」、待办栏发图，交替停一栏，看模型按钮与停止是否串栏。  
4. **技能与图片叠放**（15 min）：拖 4 图 →「+」换技能两次 → 手动改前缀 → 发送，看助手是否仍识别意图。  
5. **错误与停止交接**（20 min）：欠费/超时后立刻重选模型再发；流式中停后再发同内容，看按钮态与粉色条是否遮挡操作。

---

## 4. 需要产品负责人拍板的疑问

1. **问候时段**的具体时钟区间（例如 中午好 是 11:00–13:59 还是 10:00–14:00？夜深了 从几点起？是否跟系统时区/夏令时？）  
2. **项目助手 / 待办助手**占位符是否也改为含「输入 / 选技能」，还是仅首页？  
3. **回复过程中**模型按钮是否可点、是否允许换模型续聊？  
4. **后台改写类错误**的完整清单及小字新标签文案（是否统一为「说明」或其他一词）？  
5. **Tab** 与 **Enter** 在 slash 列表中是否完全等价；列表唯一一项时是否自动选中？

---

以上即基于题面黑盒、与空仓库一致的测试设计交付；开发完成后用真界面按 **Smallest first step** 扩成全量执行即可。
