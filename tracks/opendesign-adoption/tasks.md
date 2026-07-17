# Tasks: opendesign-adoption

- base-ref: (track A 合并后的 main,dispatch 时补)

> 工艺:模型分层试跑第二单。主 agent oracle 先行(tests/test_ds_adopt.py);
> Opus worktree 承包实现;oracle off-limits;verify full panel(采纳引擎=产品脊梁级)。

- [ ] T1 bin/ds_adopt.py:adopt_scan 只读盘点(结构识别/项目绑定状态/类目/散文件
      计数/双向未绑定);taxonomy.default.json 加 archiveDirs/sharedDirs(additive)
- [ ] T2 MCP 工具 adopt_workspace(挂 organize server;docstring 触发词:接管/盘点/
      采纳/首装/整理工作区)
- [ ] T3 stage_adoption(project_key):项目根散文件,auto→stage_plan(root=工作区根),
      suggest→advice,未知→skipped;复用 ds_intake.suggest_category/ds_organize
- [ ] T4 文档:install-windows.md 首装流程改"开聊说接管工作区";AGENTS.md 瘦路由;
      resolver eval 用例(不跑)
- [ ] T5 版本 0.26.0;py 全量回归;e2e 一条(散文件→采纳暂存→卡片可见→批准→落位)
- [ ] T6 verify full panel(主审+四腿)
