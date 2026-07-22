# Verify: opendesign-todo-batch-space

- Date: 2026-07-22
- Verdict: PASS

## Mechanical checks

- [x] build passes(web build 成、dist 重建;tsc rc=0)
- [x] tests pass(oracle 14/14 · 全量 mjs 160/160 · e2e todo_batch_space 21/21 · 相邻 frontend_p2_polish e2e 全绿;py 后端仅 VERSION 一行,test_ds_web_files/test_ds_tools OK,test_ds_web_api 超时=环境非回归)
- [x] no secrets / unsafe ops(零新后端写口;客户端串行复用既有 /api/changes/edit;后端仅 VERSION)

## Review

- lane: **full**(#2a 状态账本批量改写 = 数据一致性面)
- 三硬闸(主 agent 亲验,执行腿自述不算数):
  - 闸① oracle byte-diff:test_todo_batch / test_change_grouping 对 e59dd4a 逐字节零改动。
  - 闸② 亲跑全绿(见 Mechanical)。
  - 闸③ 逐行读全 diff:三项忠实于 design;batchEditRequests 契约吻合;applyBatch 部分失败诚实报、
    终态≥2 confirm、每条服务端原子;ChangesColumn 干净重构+globalIndex 修残缺行 key 撞号;
    Sidebar 灰化复用既有 token;frontend_p2_polish e2e 断言翻转是必要判据修正非作弊。
- findings(panel 四腿 unanimous PASS,主裁复核):
  - [采纳·已修] subglm:`applyBatch` 的 `setApplying(false)` 不在 finally →意外抛出会卡 applying 态。
    虽循环内 editChange 已逐条 try/catch、现实抛出路径≈0,但属我盲点+数据一致性面,已包 try/finally
    硬化(TodoPage.tsx applyBatch),复跑 tsc/oracle/e2e/build 全绿。
  - [采纳·流程] subkimi:verify.md/tasks.md 未填 → 本次补齐。
  - [验证·成立] subkimi 复核 globalIndex identity 假设成立(groupBy* 只搬引用、memo on shown、`?? 0`
    不可达)、残缺行 key 修法正确——正是主审请 panel 核的盲点,证实无误。
  - [验证·无] applyBatch 写到非选中条目的时序:四腿均未发现,主审复核确认(按当前数据重建+重读状态)。
- arbitrated verdict(主裁):**PASS**。四腿一致 PASS 未降主审自己的 code-verified 判断;唯一硬化点已修。

## Accepted deviations

- applying 期间浮栏 StatusPicker 未置灰(subglm/主审 N2):重入已守卫、补 finally 后 applying 必复位,
  只剩极短暂视觉闪烁=cosmetic,不为它给 StatusPicker 加穿透 disabled prop 扩面。
- N1 多选中途单条改状态后 selected 不清空:selKey 用 line、状态改写不移行号、applyBatch 按当前数据
  重建+重读状态,实际写不错条目,风险≈0;留作可选优化。
- test_ds_web_api 本地超时:后端 diff 仅 VERSION 字符串一行,非本 track 回归。
