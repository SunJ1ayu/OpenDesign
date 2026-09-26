# Tasks: opendesign-sidebar-history

- base-ref: 4c40fbcbbe89ffc4823d6a976c16e1a24e346003

> 主 agent 自己实现(decision execution_plan = main);判据先单独 commit。

- [x] T1 判据:tests/test_sidebar_history.mjs(纯逻辑)+ tests/test_sidebar_history_api.py(ds_sessions + ds_web 针孔)+ tests/e2e/sidebar_history.e2e.mjs;旧代码上红检收据
- [x] T2 bin/ds_sessions.py:workspace_dir / session_projects(mtime 缓存、别名)/ patch_sidebar / forget_session / clean_title
- [x] T3 bin/ds_web.py:GET session-projects、GET sidebar-state(只回两字段)、POST pin / rename(锁内读 - 改 - 写)、删除成功后清置顶改名
- [x] T4 web/src/workspace/sidebarModel.ts 纯逻辑
- [x] T5 App.tsx:不拼 limit;拉 session-projects / sidebar-state;置顶 / 改名 / 删除后刷新
- [x] T6 Sidebar.tsx + app.css:置顶区、按时间 | 按项目、⋯ 菜单、显示更多、中间整块滚动
- [x] T7 变异测试 + 总跑 + 构建 dist
- [x] T8 QA 执行(真管家 + 真网关 + 假厂商录像)+ 判卷
- [x] T9 评审(high,每轮两家不同家族,上限 2 轮)+ 主裁 + 归档
