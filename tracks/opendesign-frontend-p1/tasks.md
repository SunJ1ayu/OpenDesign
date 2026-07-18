# Tasks: opendesign-frontend-p1

- [ ] T0(主 agent)oracle 亲写+红检+commit 进 main
- [ ] T1 后端②:ds_intake.amend_plan + ds_organize approve/apply 拒 superseded
      + ds_web _pending_plans 过滤 + 针孔⑧ /api/intake/amend
- [ ] T2 后端③:针孔⑨ /api/projects/bind(薄壳直调 ds_tools.bind_project)
- [ ] T3 前端:api.ts amendIntake/bindProject;InboxCard 行「跳过」;
      CompanionColumn unmapped 下拉+关联(新 props folders/onBound,App 接线);
      ChangesColumn 行正文就地编辑
- [ ] T4:VERSION 0.30.0 + ds_web 模块 docstring 针孔清单同步 + dist 重建
- [ ] T5(主 agent)收货三硬闸 + verify full 四审 + e2e + merge/push/归档

验收红线:
1. oracle 四文件 byte-diff 为空(对 T0 commit)
2. 全量 py+mjs 回归绿;npm build 绿
3. 未跳过的 POST 面仍 405(oracle 锁死)
4. 前端三处交互不破只读铁律(写全走针孔)
