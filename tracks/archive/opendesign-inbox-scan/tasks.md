# Tasks: opendesign-inbox-scan(P0 #3:收件箱"扫描整理"按钮)

- base-ref: (立项 commit)

> 模型分层试跑第四单,执行腿再验 Sonnet 5(confirm)。主 agent 写 oracle 先行
> (test_ds_intake StageInboxAutoOracle 9 例 + test_ds_web_intake TestIntakeScanPinhole 7 例,已红)。
> Sonnet 5 worktree 承包;oracle off-limits;verify fast lane。roadmap 见 docs/frontend-actions-roadmap.md。

- [x] T1 核心 ds_intake.stage_inbox_auto(allowed_roots, ds_root):list_inbox → 采纳确定性建议
      (文件+有类目;project 级需唯一项目建议、workspace 级无需)→ stage_intake;其余进 skipped
      (reason: not_a_file/unknown_type/ambiguous_project);返回 {ok,plan_id|None,staged,skipped}
- [x] T2 针孔 POST /api/intake/scan(空 body {},键白名单=空)→ stage_inbox_auto(allowed_roots=
      [cfg root]);posture 同 _intake_approve;错误映射 workspace_not_configured→409 inbox_not_found→404
- [x] T3 前端:InboxCard 底部"扫描整理"按钮 → scanInbox()(api.ts 新增)→ 成功 localEpoch 自刷新
      (新暂存的 plan 出现在待确认区,复用现有"确认执行");busy 禁用;skipped 提示可选
- [x] T4 版本 0.29.0;py 回归(两 oracle 全绿 + 全套)+ build;e2e 一条(丢文件→scan→pending 见→approve 落位)
- [x] T5 verify fast lane(主审 + submimo)
