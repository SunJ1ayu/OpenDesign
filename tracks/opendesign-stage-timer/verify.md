# Verify: opendesign-stage-timer

- Date: 2026-08-02
- Verdict: <PASS | BLOCK | NEEDS_MORE_INFO>

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [ ] build passes
- [ ] tests pass
- [ ] no secrets / unsafe ops

## Review

- lane: **full**
  > 硬规矩命中两条:**动档案格式(数据一致性)** + **既有写口 `set_stage` 语义扩张**。
  > 针孔再薄也不打折,不在这降档。
- 派给: **codex `-m gpt-5.5`,主 agent 当测试机** —— 方向、格式、语义表、错误码全部
  已由我在 design.md 钉死,剩下的是照着一份红 oracle 把实现写绿 = 典型 PR 级实现档,
  不必升 `gpt-5.6-sol`(架构判断已经做完了,不是它要做的)。
  **判卷要起服务**(O2 走真 ds_web、O4 走真 chromium + 真端口),沙箱禁网它跑不了
  —— 按抽屉的默认路子:**GPT 照写,跑不了的考卷我来跑**,红了把失败输出原样退回去,
  **有界 2 轮**,还不绿收回自己修。**网络开关一律不动。**
  这是分层还账的**第 3 单**(第 1 单 0.67.0 / 第 2 单 0.68.0,codex 自身错误均 0 处);
  本单结果照记进 [[model-tiering-trial]] 的返工率账。
- 规格自查(读任何 panel 输出之前先答):
  **规格最可能错在哪 = D3 语义表第三格「阶段相同 + 无 since ⇒ 流水账不动」。**
  我把它定成"防误点重置计时",但它同时意味着:**用户真的重新进了一次同一个阶段
  (返工回炉,比如效果图打回重做),计时不会重来** —— 这在设计业务里完全可能发生,
  而我的判据会把我这个选择**钉死成"正确"**,四腿也只会验实现合不合它。
  怎么发现:**只能靠真机**。装机后如果他说「这个项目返工重做效果图了,天数怎么没归零」,
  就是这条规格错了。已写进待验清单当抽查项。**现在不改** —— 反过来做(重复点就重置)
  会让一次误点静默毁掉数据,那个代价不可逆,而这个代价只是数字偏大且看得见。
  次可能错的:`since_in_future` 拒绝未来日期。若他习惯"提前登记下周进施工图",
  这条闸会挡他的路。真机上撞到就放开(改成允许并显示 0 天)。
- findings:
  - <...>
- arbitrated verdict (主裁): <...>

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>
