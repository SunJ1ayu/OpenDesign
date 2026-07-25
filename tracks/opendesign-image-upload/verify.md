# Verify: opendesign-image-upload

- Date: 2026-07-26
- Verdict: <PASS | BLOCK | NEEDS_MORE_INFO>

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
- 规格自查(读任何 panel 输出之前先答):<如果规格本身就是错的,会错成什么样、我怎么发现?
  panel 只验"实现合不合规格",验不了"规格对不对" —— 四腿齐 PASS 不等于题是对的。>
- findings:
  - <...>
- arbitrated verdict (主裁): <...>

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>
