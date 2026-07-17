# Tasks: opendesign-cockpit

- base-ref: a8a85ff(set-stage 归档后)
- 状态:DONE(verify PASS)

- [x] T1 latest_mtime DONE(oracle 先红 2 例→绿;capped→None)
- [x] T2 _projects owner/status_note/group DONE(oracle 先红 4 例→绿;405 重申)
- [x] T3 cockpit.ts DONE(mjs 9 例先红后绿;判卷用例「渲染输出」过)
- [x] T4 组件 DONE(四块重排/拔硬编码/图墙常驻入口/刷新门;build 绿)
- [x] T5 e2e DONE(真 chromium+真 ds_web 8/8 首跑全过;纯 GET 面无需 gateway,夹具含非模板类目)
- [x] T6 回归 330py+mjs 全绿;突变红检 3/3;dist 进仓;VERSION 0.24.0;verify fast lane 主审+submimo 双 PASS 零改动
