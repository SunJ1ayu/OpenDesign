# Verify: opendesign-completed-items

- Date: 2026-07-16
- Verdict: PASS

## Mechanical checks

- [x] build passes（`cd web && npm run build` tsc -b + vite 绿,297 modules)
- [x] tests pass（test_completed_items.mjs 11 例 + 全套 mjs 回归绿:chat 15+22 / gallery 7 /
      workbench_p4 21 / completed_items 11)
- [x] red-check（DONE_SET 缺 已关闭 → 4 例红:计数/互补/done筛选/常量;还原全绿)
- [x] 真起 ds_web /api/changes 契约对齐（状态串 = 待确认/进行中/已完成/已关闭,open=3 done=3 all=6
      与纯逻辑一致)
- [x] no secrets / unsafe ops（纯前端,后端仅 VERSION bump 0.12.0→0.13.0)

## Review

- lane: **fast**（主 agent + submimo;纯呈现层 medium 风险)
- 主 agent 独立评审(先于读 submimo):`/root/aiwork/tasks/opendesign-completed-items-my-review.md` → PASS。
- submimo:5 项审查全 PASS,2 nits。裁决:
  1. **track 脚手架未填**(nit#1):有效 → 本次已填 proposal/design/tasks/verify。**接受并修**。
  2. **`Record<StatusKey,number>` 带隐式 string 索引**(nit#2):**证伪并拒**。核实 `Record<K,V>` 对
     字面量联合 K 只产出这些键、**无** string 索引签名(`counts["草稿"]` 实际会报错);且
     `Record<StatusKey,number>` 与建议的 `{[K in StatusKey]:number}` 定义等价(Record 就是该映射类型)。
     tsc -b 通过佐证 `counts[s]` 类型安全。**不改**。
- **arbitrated verdict(主裁):PASS。** submimo 无发现主 agent 漏报的真缺陷;逻辑 oracle+red-check
  双向咬,数据契约实测对齐,回滚能力保留,后端未动。

## Accepted deviations

- 未办结/已办结聚合与 待确认/进行中 子项计数重叠(子项计入未办结):沿用既有聚合+子项模式,非新困惑。
- 进度一览只显 count>0 的状态(非固定四格):更简洁,空态由 head 兜。

## 部署要点

- dist 已提交:用户 Windows `git pull` + 重启 ds-web(不必 build)。
- 验收:浏览器 Ctrl+F5 页脚 / `/api/health` version 显 **0.13.0**;进项目工作区 →
  标题下出现进度一览行 + 筛选栏多「已办结」pill,点它只看已完成/已关闭,每行 pill 仍可回滚。
