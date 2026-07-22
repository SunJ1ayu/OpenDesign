# Tasks: opendesign-todo-batch-space

- base-ref: 2cd8d33cf4d041323f9a4e27ba297b83364424ab

> oracle 已先行 commit,对执行腿逐字节 off-limits:
> `tests/test_todo_batch.mjs` / `tests/test_change_grouping.mjs`。

- [x] T1 `todo.ts::batchEditRequests` 实现 → 绿 `tests/test_todo_batch.mjs`(7 例)
- [x] T2 `workspace/changes.ts::groupByDate` + `groupBySpace` 实现 → 绿 `tests/test_change_grouping.mjs`(7 例)
- [x] T3 #2a TodoPage 批量:复选框(两视图)+ 分组头「全选本组」+ 浮动操作栏 + 串行应用/计数/toast/终态 confirm
- [x] T4 #2c ChangesColumn 「按时间/按空间」分组切换(默认按时间,filter 后分组分节)
- [x] T5 #3 Sidebar 删「建档 →」「未建档」两 span + app.css `.proj-row.unregistered .nm` 灰色
- [x] T6 e2e `tests/e2e/todo_batch_space.e2e.mjs`(真 chromium+真 ds_web):两视图批量改状态落盘、单项目空间分节、侧栏无建档标+灰色
- [x] T7 自检:两 oracle + 全量 mjs + py 套件 + build 全绿;/api/health 版本 bump 0.34.0
