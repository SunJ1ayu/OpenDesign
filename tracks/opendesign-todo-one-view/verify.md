# Verify: opendesign-todo-one-view

- Date: 2026-08-01
- Verdict: <PASS | BLOCK | NEEDS_MORE_INFO>

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [ ] build passes
- [ ] tests pass
- [ ] no secrets / unsafe ops

## Review

- lane: **self**
  > 现场判,不抄上一单的话:**纯前端 + 后端一字未动 + 零新写口**。
  > C 那条(徽标)刻意选了"前端从条目已有的 `date` 算",就是为了不去动 `ds_todo.py`
  > 的读写契约 —— 换句话说 lane 是被**设计选择**压下来的,不是被理由说下来的。
  > 不碰权限/auth/钱/数据一致性。风险集中在"排序对不对"(纯函数判据 20 条接住)
  > 与"观感"(判据接不住 ⇒ **收尾必须截图**,见下)。
- 派给: **codex gpt-5.5(worktree)**,主 agent 收货三闸 + 亲跑 e2e。
  > 判据分两截:纯函数那 20 条它自己能跑;e2e 要起 ds_web + chromium,
  > **但那不是"所以我自己干"的理由**(07-31 栽过:那句自述理由被我原样复制了四单)。
  > 按 delegate 抽屉的默认路线 = 主 agent 当测试机,有界 2 轮。
  > 这是模型分层还账的**第 3 单**(前两单返工率均为 0)。
- 规格自查(读任何 panel 输出之前先答):
  > **最可能错在"软轨该升序还是降序"。** 我选了升序(最久在前),依据是用户 08-01
  > 说的打开动机「看今天做什么,**还有有什么忘记的事情**」;GPT-5.6 建议的是降序。
  > 判据把升序钉死了 —— **所以如果我这条规格错了,判据会齐声说"对"**,四腿也一样。
  > 唯一能发现的方式:**用户真机看一眼列表顺序顺不顺手**。已写进待验清单。
  > 第二个可能错的:阈值 7 天沿用后端,但后端那个 7 天是给"档案 mtime"定的,
  > 换成"最近记录"后 7 天是否仍合适,**我没有依据**,只是没理由新造一个数。
- findings:
  - <待填>
- arbitrated verdict (主裁): <待填>

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>
