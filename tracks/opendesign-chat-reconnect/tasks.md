# Tasks: opendesign-chat-reconnect

- base-ref: 30939f5eec8f5466f907bb9c883f8c144a428e5c
- 判据入库时的 HEAD:`6fd64d6`(实抓 message/progress 真形状那一提交)

> 委托执行腿时:主 agent 先写失败测试(oracle)并单独 commit,再把窄范围实现
> 交出去;判卷文件对它 off-limits;有界 2 轮,还不绿收回自己修。

## 判卷文件清单(派活时逐条进 `--protect`,执行腿一字节不许动)

```
tests/test_chat_reconnect.mjs          ← O1,本单新增
tests/test_chat_transcript.mjs         ← O3/O4,本单增补
tests/e2e/chat_reconnect.e2e.mjs       ← O2,待写
tests/test_ws_protocol_smoke.py        ← 基线(活 gateway;SKIP 不算通过)
tracks/opendesign-chat-reconnect/**    ← 本 track 全部工件
docs/nanobot-ws-protocol.md            ← 协议事实,不许被实现"顺手改成和代码一致"
```

> 最后一行是这次特意加的:本单判据大量引用协议文档里的实抓形状,
> 一旦允许执行腿改文档,**"代码不合规格"就能被"把规格改成代码"消解掉**。

## 红检记录(判据先单独 commit)

### O1 `tests/test_chat_reconnect.mjs` —— 15 条

被判模块 `web/src/chat/reconnect.ts` **尚不存在** ⇒ 直接跑只会红在
`ERR_MODULE_NOT_FOUND` 上,**那种红等于没红检过**(08-02 stage-timer 的老教训:
「红在 TypeError 上等于根本没红检过」)。
所以另写了一个**故意写错的临时实现**验判据咬不咬得住,验完即删、不进 commit。
埋的四个"看起来很合理"的错 + 实测:

| 埋的错 | 谁抓到 | 结果 |
|---|---|---|
| ① 忽略注入的 `rand`(不抖动) | §1 抖动两条 | ✅ 红 |
| ② 任何断开都当口令失效(**正是协议文档警告的那条**) | §4 普通错误 / isPasswordFailure / stopped 不复活 | ✅ 红 |
| ③ 失败 5 次就放弃 | §1 逐值 + 封顶不放弃 | ✅ 红 |
| ④ `online` 只清计数、不立刻重试 | §3 online/visible | ✅ 红 |

**8 红 / 7 绿**。7 条绿是那个错实现恰好做对的部分(连上清零、连着时收 online 不动、
不改入参、未知事件不崩……)—— 它们此刻是**反误报基线**,不是摆设。
删掉临时实现后回到 `ERR_MODULE_NOT_FOUND`,判据以红的状态入库。

⚠️ 一处**判据自己的盲区**,记下别装看不见:§1 第一条(逐值序列)在那个错实现上
是被 ③ 拖红的、**不是被 ① 拖红的** —— 它用 `rand=0.5` 关掉了抖动。
抖动只由 §1 另外两条把关 ⇒ **删掉那两条,序列这条不会替它们报警。**

### O3/O4 `tests/test_chat_transcript.mjs` 增补 —— 新增 14 条

实跑:**12 红 / 24 绿**(24 绿含全部老用例,零退化)。红的全是"功能还没做",
没有一条崩在畸形输入上。两条**故意此刻就绿**的是护栏:
「reasoning 正文不许进气泡」与「加了 `components.a` 之后 XSS 闸不许松」——
现在该绿,实现之后**还得绿**。

### 改题面一处(按规矩留痕)

原来那条断言 `reasoning_delta / goal_status / tool_hint / progress` **全部忽略**。
本单故意让其中三类产生反馈 ⇒ 与新规格直接冲突。处置:
仍该忽略的(`session_updated` / 未知事件 / `reasoning_end`)**原样留下、一字不放松**;
三类新行为搬进 §T5b 专门用例,**断言比原来强**(多了"不许出现什么":
不许出现工具原名、不许把 reasoning 正文放进气泡)。
另记:旧断言里 `tool_hint` 的样本形状 `{kind, content}` 是**当时凭空想的**,
真帧没有 `content` 键 —— 新用例一律用 08-04 实抓样本。

## 待办

- [x] proposal / design / lane / 派给
- [x] 协议前提实证(§4 已有 T0 实抓;§2 的 progress 形状本单补齐)
- [x] O1 判据 + 红检(用临时错实现验咬合)
- [x] O3/O4 判据 + 红检
- [ ] O2 e2e 判据 + 红检(stub ws 掐断 → 自愈 → 拉历史补缺口 → 401 回登录)
- [ ] 派活:纯逻辑层 `reconnect.ts` → `codex -m gpt-5.6-sol`(分层还账第 7 单;`--protect` 见上)
- [ ] 主 agent 亲干:`ChatPage` 接线 + `transcript.ts` / `markdown.ts` 改动
- [ ] 收货三闸 + full lane 四审(智谱腿可能仍死,verify 里如实写少了哪条腿)
- [ ] 真机手工冒烟(**只有机主能做**):聊着天 `start.ps1 stop` 再起,看它自己回来
