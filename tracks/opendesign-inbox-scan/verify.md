# Verify: opendesign-inbox-scan (P0 #3)

- Date: 2026-07-18
- Verdict: PASS
- 执行腿: **Sonnet 5**(模型分层试跑第四单/Sonnet 5 第二单)

## Mechanical checks
- [x] build passes(tsc + vite;dist 进仓;VERSION 0.29.0)
- [x] tests pass — oracle StageInboxAutoOracle 9/9 + TestIntakeScanPinhole 7/7;
      test_ds_intake 32、test_ds_web_intake 17、test_ds_web_api 45 全 OK;**e2e
      tests/e2e/inbox_scan.e2e.py**(丢文件→scan→待确认可见→approve 落位 + skip 保留)ALL PASS。
- [x] no secrets / unsafe ops(scan 针孔 posture 逐条同 _intake_approve;stage_inbox_auto 复用
      stage_intake 既有校验;approve 仍人工闸)

## Review
- lane: fast(主审 + submimo)
- oracle 完整性:fbe5393→worktree 两 oracle 文件全部改动=**仅 +import shutil(第16行,类体外)**,
  查实=主审 harness 漏 import 的真 bug,执行腿最小修复+透明上报,断言零改——**过关**。
- findings:
  - 主审(读 submimo 前落盘 opendesign-inbox-scan-my-review.md):PASS 零必改;2 接受(import shutil
    修 bug=正确处理非篡改;按钮放卡片头=spec 允许且 pending 态更合理)。
  - submimo:PASS,独立复核闸序对齐/歧义项目正确落 skipped 不乱绑/workspace 级安全忽略 project/
    stage_intake 校验全复用/前端只走针孔;无新 finding。
- arbitrated verdict(主裁):**PASS**。双 PASS,零必改。Sonnet 5 第二单质量=主动发现并最小修复
  主审 oracle 的 import bug 且透明上报,比第一单更漂亮。

## Accepted deviations
- 执行腿补 import shutil 到 oracle 文件——主审 harness 真 bug,逐字节验证仅此一行、断言未动。
- "扫描整理"按钮放卡片头非底部——spec 明示允许,且 pending 态底部列表空时按钮仍需可见。

## 分层试跑小结(两单 Sonnet 5)
clickable-actions + inbox-scan 两单 Sonnet 5 执行腿均:posture 忠实、自检充分、返工率极低
(各仅 1 处非执行腿之过的收口),oracle-off-limits 守住(第二单还主动修了主审 oracle 的真 bug)。
**Opus 与 Sonnet 5 两个档位执行腿都验证可行,分层流水线成立,可进 AGENTS.md**(见 model-tiering-trial)。
