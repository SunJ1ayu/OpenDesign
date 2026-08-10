# Verify: chat-busy-stuck

- Date: 2026-08-06
- Verdict: PASS(代码面;真机验收欠机主)

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] build passes(web/dist 已重建)
- [x] tests pass(仓库级总跑:node 342 / python 866 / MCP 闸绿 / e2e 32 PASS 0 FAIL 2 SKIP)
- [x] no secrets / unsafe ops

## Review

- lane: fast
  > **碰了新写口 / 权限 / auth / 钱 / 数据一致性 → full,针孔再薄也不打折**(硬规矩,别在这降档)。
  > fast = 主+1,中等风险;self = 主自审(闸③ + 截图 + 全量回归),
  > 限纯前端/纯观感、后端一字未动、只新增已过审针孔的调用方。
- 派给: 主 agent 直接干 —— 8 行的状态修复,判卷是已有的 e2e(要起 ds_web + 真 chromium),
  切碎外包比自己写贵;而且它就长在我刚读透的那段代码里。
- 规格自查(读任何 panel 输出之前先答):规格若错,最可能错成**在不该解锁的时候解锁** ——
  比如新一轮已经开始(用户重连后又发了一句)时,迟到的那次 404 回调把新一轮的 busy 也清掉,
  界面显示"空闲"但其实在等回复。我的写法只在"拉不到历史"这条路上清,且只在 reconcile 模式,
  但**判据没有覆盖这个竞态**(要造"pullThread 未决时用户又发一条")—— 如实记在这里,
  下次碰这块代码时补。另一种错法是 prepend(点历史会话)被误伤,这条判据有(⑤⑥ 那几幕仍绿)。
- 腿的花名册: fast lane 不跑 panel,只有一条:`submimo=PASS`
  (日志 `/root/aiwork/logs/chat-busy-submimo.log`;它的结论是 PASS,并提了一条可读性建议)
  > panel-review 收尾自己写这个文件(off / FAIL(rc) / 降级 都在里面)。
  > 08-06 立这条的理由:08-05 我在这里手写了"三条腿一致 PASS",而 Kimi 根本没出结论
  > (同一页第 90 行我自己还写着它没出报告)—— 手抄一份终端上的东西,抄错那次没人会发现。
- findings:
  - 主审自审:早退那一行把"有没有历史"和"要不要解锁输入"绑在一起判 —— 修法是拆成两段,
    并且只在 reconcile 模式清(prepend 是点历史会话的回放,不该动 busy)。
  - 主审自审:`setTranscript` 里加了"本来就不忙就原样返回"的短路,避免无谓重渲染。
  - submimo(fast lane):逐条核过"删掉新代码 ㉜ 必红"的因果链(`__silent` 挡住所有服务端
    事件、onclose 只走重连策略、attached 处理器不碰 busy)⇒ 判据有效、无假绿。**PASS**。
  - submimo 建议:㉜ 不要依赖上一幕留下的 `__threadStatus=404`,显式设一次。**已采纳**。
  > 只写发现。腿的身份/降级不在这儿抄第二遍:日志自带身份牌(降级横幅 + 视野边界),
  > 花名册在上一格,查工件不查自述。
- arbitrated verdict (主裁): **PASS(代码面)**。判据先红后绿、前置两条都绿(证明这一幕
  问的是对的东西);仓库级总跑全绿;fast lane 一致。**欠真机**:新会话发第一句时停 gateway,
  等它自己连回来,看发送键能不能再用 —— 只有机主能做。
  > **归档时这一条和顶部的 `Verdict:` 都不许还是占位符**,`track-guard` 规矩3 会挡;
  > 没归档但已经合并上线的,`track list` 会打 ⚠️(stage-timer 就这么漏了两个月)。

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>

---

## 归档说明(2026-08-10)

- 无机器证据:本单完工于 `runlog` 收据机制上线(2026-08-08)之前,判据结果是我手工转述进
  上面正文的。**不补跑也不追认** —— 今天补跑出来的收据对应今天的代码,证明不了当时那一遍。
- **归档时真机验收仍未做**,已移交 `docs/accept-0.81.0.md` **E 组**(断线之后发送键还能用)。
  归档 = 「我这边判完了」,**不等于**「已在机主机器上验过」。
