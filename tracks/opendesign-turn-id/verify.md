# Verify: opendesign-turn-id

- Date: 2026-08-05
- Verdict: <PASS | BLOCK | NEEDS_MORE_INFO>

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [ ] build passes(`npm run build` in web/ + `tsc`)
- [ ] tests pass(python 全量 + `tests/e2e/run-all.sh --with-gateway`,**不许留 SKIP**)
- [ ] no secrets / unsafe ops

## Review

- lane: **full**
  > 判据:这段代码决定**用户说过的话在断线后还在不在** = 数据一致性面,硬规矩不打折。
  > 佐证不是我的感觉:同一段代码上一单(chat-reconnect)走 full,四审判过 BLOCK、
  > 两条 HIGH 都出在这里(P1 busy 永久锁死、P3 半截 assistant 气泡),
  > 而它们**纯逻辑判据全绿**照样漏。本单动的正是那段。
  > (智谱腿欠费默认关闭 ⇒ 实际三腿;这是腿的现状,不是降档。)
- 派给: **codex / gpt-5.5**(worktree) —— 规格已经写死到判定表级别、判据先行且红检过两个
  方向,剩下的是"照着红考卷写绿",不需要 frontier 脑;Claude 额度留给判卷/四审/仲裁。
  判卷要不要起服务:**要**(O2/O3 是 chromium + 本机端口),按 delegate 抽屉的默认路子
  **主 agent 当测试机**(有界 2 轮),不为一个本地端口给它开网络。
  O1(`node --test`)它自己就能跑,交货前必须自己跑绿。
  > 分层还账账本:本单是 GPT 腿第 ? 单 —— 数字**收货时从工件数,不从记忆抄**;
  > 返工轮数与自身错误数在下面 findings 段据实记。
- 规格自查(读任何 panel 输出之前先答):
  1. **规格可能错在"以为丢字的主因是对账"**。真机上更常见的是整页刷新(本地 state 全丢),
     那和 turnId 一点关系没有。若真是它,本单全绿而用户照样说"我的话没了" ——
     发现方式只有真机 R1/R2,已列进 tasks.md。
  2. **规格可能错在退路留反了**:我让"本地无 turnId ⇒ 退回文本启发式"以求不倒退,
     但老会话混排时这条退路会把**真正独有的一句**误判成"服务端已有"而丢掉 ——
     这是我明知留下的口子(design.md 记账)。判据⑤锁的是"不误判成没有",
     反方向(误判成有)判据接不住,只能靠真机 R1 顺带看。
  3. **规格可能错在发送口判太严**:把"能发出去的"拦下来,用户眼里=按了没反应。
     所以只认 `readyState !== OPEN` 和 `send()` 真抛两种确定失败,不加任何猜测;
     判据㉘ 锁"失败之后不许锁死输入"。真机 R3 兜。
- findings:
  - <待填>
  > 腿死了/降级了不用在这里再抄一遍:每份评审日志自带身份牌(降级横幅 + 视野边界),
  > 查日志不查自述。这里只写发现。
- arbitrated verdict (主裁): <待填>
  > **归档时这一条和顶部的 `Verdict:` 都不许还是占位符**,`track-guard` 规矩3 会挡。

## Accepted deviations

- <待填>
