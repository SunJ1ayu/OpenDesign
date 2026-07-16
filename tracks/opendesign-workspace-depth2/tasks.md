# Tasks: opendesign-workspace-depth2

- base-ref: 6b9fb696a5c1201dcded9ea1de13b3cbaa364557

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

- [x] T1 oracle 先红(ws 4F + tools 4E 实测红;g03/g05/g07 为回归护栏本就绿):test_ds_workspace 扩 depth=2 用例(keyed 名单/过滤/直等/
      歧义不绑/config 校验)+ test_ds_tools set_workspace depth 用例 → 全红
- [x] T2 ds_workspace:load_config 收 projectsDepth(1|2 严格)+ project_folders
      两层扫描(key=`组:名`)→ T1 绿 + 既有全量回归绿
- [x] T3 ds_tools.set_workspace 加 projects_depth 参数 + MCP schema +
      workspace AGENTS.md 用法段(nanobot 侧部署文件同步提醒)
- [x] T4 ds_web /api/projects unregistered 带 group/纯 name + test_ds_web_proxy
      扩展(含 %3A URL 往返)
- [x] T5 前端:api.ts Project.group + Sidebar 分组标签;npm run build 绿;
      VERSION → 0.14.0
- [x] T6 文档:workspace.example.json 注释 + install-windows.md;红检突变验证
- [ ] T7 verify(fast lane:主审 + submimo review)→ verify.md 落 verdict
