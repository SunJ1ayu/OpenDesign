# Verify: opendesign-workbench-p1

- Date: 2026-07-08
- Verdict: <PASS | BLOCK | NEEDS_MORE_INFO>

> **两段验收(2026-07-09 定,见 tasks.md 排期决定):**
> ① **最小可装机(T4 + 半个 T5)** —— 达到即装用户 Windows 取真实反馈,
>    这一段按 fast lane 验(聊天/连接是门面 + ds_web 出站面);
> ② **完整收口(T6–T10 做完后)** —— full lane。
> 部署目标规则:装机后须让**运行中的**工作台回显版本/状态,磁盘有文件 ≠ 已部署。

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 submimo/subsense/subglm,主 agent 主裁。
> build/test 跑通是机械检查。lane:full(主+3,高风险)/ fast(主+1,medium)/
> self(主自审,小改)。

## Mechanical checks

- [ ] build passes
- [ ] tests pass
- [ ] no secrets / unsafe ops

## Review

- lane: <full | fast | self>
- findings:
  - <...>
- arbitrated verdict (主裁): <...>

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>
