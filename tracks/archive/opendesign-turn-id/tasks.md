# Tasks: opendesign-turn-id

- base-ref: 611dd49e839d7d9c3408d36ab83cb9ceb66a5221

> 委托执行腿时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现交给它;
> oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

## 判据(主 agent 亲写,先行 commit + 已红检)

- [x] O1 `tests/test_chat_transcript.mjs` 增 11 条(对账①–⑧ + hydrate/append 两条)
- [x] O2/O3 `tests/e2e/chat_reconnect.e2e.mjs` 增 ㉔–㉘ 五幕 + `__sendThrows` 夹具
- [x] **红检(两个方向都验过,不是"红在模块不存在上")**
      - 老语义桩(文本启发式)⇒ 对账① + hydrate + append 三条红
      - 只认 turnId、没有文本退路的桩 ⇒ 对账④⑤ + 那两条红
      - e2e 对着**现有实现**实跑 ⇒ ㉔ 红(实得 1 条)、㉗ 红(没有提示)、⑫ 红(未捕获异常)

## 实现

- [x] T1 `ChatMessage.turnId?` + `appendLocalUser` 收下它 + `hydrateFromThread` 读回来
- [x] T2 `reconcileThread` 提成纯函数进 `transcript.ts`,判定规则见 design.md
- [x] T3 `ChatPage` 改用 `reconcileThread`(行为等价,只换实现)
- [x] T4 `sendText`:`readyState !== OPEN` 或 `send()` 抛 ⇒ 不上屏、给一句人话提示、不锁死输入
- [x] T5 版本号 bump(ds-web 0.76.0)+ `docs/accept-0.76.0.md` 真机验收清单

## 四审之后又做的(findings F7–F10,详见 verify.md)

- [x] 对账"有 turnId"分支去掉文本兜底(三腿共同命中的规格错误,我自审时判错了取舍)
- [x] 判据 ⑤ 反写 + 新增 ⑤b;e2e 夹具改成真机形状;㉔ 补时序钉子(否则旧实现也能绿)
- [x] 新增 ㉙/㉙b(readyState 分支)与 ㉚(连上后失败提示要消失)
- [x] `docs/accept-0.76.0.md` B 组按"停 gateway / 拔网线"两种断法分开写
- [x] 探针加"原文逐字节一致";协议文档 §5 加"升级 nanobot 后复跑探针"

## 收口

- [x] 三道闸(oracle 逐字节 diff / 亲跑 / 亲读 diff)——外包才走前两道以外的那道,自己干也要走后两道
- [x] 全量回归:python + `tests/e2e/run-all.sh`(**含 `--with-gateway`**,08-05 起不许再留 SKIP)
- [x] verify.md 收口 + 四审(lane 与理由见 verify.md)

## 只有机主能做的真机验收(**没验完不许归档**)

- [ ] R1 断网前后各说一句话,重连后**两句都在**、没有重复、顺序看着不别扭
- [ ] R2 故意把同一句话说两遍(中间断一次网)—— 两条都在(本单主场景)
- [ ] R3 **停掉 gateway**再点发送:界面**不显示**那条消息,而是给一句看得懂的提示
      (⚠️ 四审 F8 更正:**拔网线**那种断法浏览器不知情、消息静默排队 ⇒ 气泡会照常上屏、
      没有提示,那是预期内的另一种结果,不是 bug;两种都要机主如实回报)
- [ ] R4 提示那句话是人话(不是 "InvalidStateError")—— 观感只有人眼接得住
- [ ] R5 连回来之后那句提示**自己消失**(F9 修的那条)
