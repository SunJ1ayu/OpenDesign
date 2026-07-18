# Verify: opendesign-clickable-actions (P0-1/2)

- Date: 2026-07-18
- Verdict: PASS
- 执行腿: **Sonnet 5**(模型分层试跑第三单,首次 Sonnet 5;主 agent 写 oracle+审+裁)

## Mechanical checks
- [x] build passes(tsc -b + vite;dist 进仓)
- [x] tests pass — oracle TestAddChangePinhole+TestCreateProjectPinhole 18/18;
      test_ds_web_api 全 63/63;test_ds_tools 129/129;mjs 无回归;**e2e
      tests/e2e/clickable_actions.e2e.py**(建档→记一条→GET 读回 + 重复 409)ALL PASS。
- [x] no secrets / unsafe ops(两针孔只读墙受控开口,posture 逐条同 _edit_change;
      核心校验 append_change/create_project 复用未绕过)

## Review
- lane: fast(主审 + submimo)
- oracle 完整性:worktree 基线早于主 agent oracle commit,执行腿自行 copy oracle 进 worktree
  → 主审对 eb4c2d7 逐字节 diff=空,**证实零篡改**("执行腿改考卷"最该防的洞,过关)。
- findings:
  - 主审(读 submimo 前独立落盘 opendesign-clickable-actions-my-review.md):PASS;抓 1 真 nit=
    记一条快捷输入无 project 切换重置(与建档表单不对称,会把 A 草稿记进 B)→ **已修**(补 reset
    effect,rebuild);2 接受偏差(Sidebar onNewProject 未改=task 授权 fallback;错误表补
    bad_name/path_escape→404=_resolve 真实返回诚实映射)。
  - submimo:PASS,独立复核闸序完全对齐/错误映射无泄露/前端只走针孔/核心校验未绕过;2 非阻塞
    观察(content 空串可提前拦=已由 append_change empty_content 正确处理;500 兜底可补=_edit_change
    模板本身也没有,保持一致不加)。
- arbitrated verdict(主裁):**PASS**。submimo 未推翻主审;唯一实修=主审自查的 nit。

## Accepted deviations
- Sidebar「+」仍 prefill 聊天(未改)——task 明示 fallback,ChangesColumn 建档表单硬要求已做,P1 统一。
- P0 #3(收件箱扫描按钮)不在本 track——需新核心函数(从建议自动组装方案),下一 track。
