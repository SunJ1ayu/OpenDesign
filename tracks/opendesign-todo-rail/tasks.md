# Tasks: opendesign-todo-rail

- base-ref: e494432ffb31bab422c865fea0b92f00ee624020(main,ds-web 0.36.0)
- oracle:`tests/test_schedule.mjs` + `tests/e2e/todo_rail.e2e.mjs`,
  执行腿**逐字节 off-limits**

> 执行腿 = Sonnet 5 worktree。判据由主 agent 拥有;不 push / 不 merge / 不归档。

- [x] **T1 `web/src/schedule.ts`(新)**:`CalCell` 类型 + `monthGrid` / `dueDates` /
      `followUpItems` 三个纯函数(契约见 design.md §1 与 `tests/test_schedule.mjs`)。
      **不要新造日期分类** —— 红/琥珀由既有 `todo.ts::dueStatus` 判。
- [x] **T2 `web/src/TodoRail.tsx`(新)**:320px 右栏,两段。
      ① 日程概览:月份头 `[data-ui="cal-month"]` + `[data-ui="cal-prev"]`/`[data-ui="cal-next"]`
      翻月 + 表头 一二三四五六日 + 42 个 `[data-ui="cal-cell"][data-date="YYYY-MM-DD"]`
      (本月格 `.in-month`、今天 `.today`、被选 `.sel`);有到期事项的格内一个
      `.cal-dot.dot-<dueStatus>`(overdue/today/upcoming),**邻月补格照样带点**。
      ② 需要今天跟进:`[data-ui="follow-card"]` 每条 = 编号 + 正文 + 项目·空间·
      (`超期 N 天` / `今天到期`);无事项时渲染 `[data-ui="follow-empty"]`,文案含
      「今天没有到期事项」。
      状态边界:当前月份自己持有;选中日期由 props 上提(受控)。
- [x] **T3 `TodoPage.tsx`**:接入右栏;新增 `dateFilter` 状态;过滤谓词 `it.due === dateFilter`
      **两个视图都生效**;再点同一日期取消;过滤态显示 `[data-ui="todo-date-filter"]`
      过滤条(带清除)。批量选择/编辑/折叠等既有交互不回归。
- [x] **T4 `web/src/app.css`**:`.todo-page` 转 flex(主区 `flex:1;min-width:0`,
      右栏 `flex:none;width:320px`);月历网格 7 列;圆点三色(超期=红陶 `#a04f2e`、
      今天=主色、未来=琥珀);跟进卡样式;过滤条样式。**既有多列瀑布规则不动。**
- [x] **T5 自检**:`tests/test_schedule.mjs` 19/19 绿 + 全量 mjs 回归 199/199 绿 + `tsc -b`
      rc=0 + `npm run build` 成功 + `tests/e2e/todo_rail.e2e.mjs` ALL PASS +
      `todo_batch_space`/`duedate` 不回归(ALL PASS)。**`todo_layout.e2e.mjs` 回归
      1 例失败**(880 居中限宽断言)——执行腿判断这是本单(320px 右栏)与该断言
      的结构性数学冲突,而非实现 bug,详见交付报告,已如实报告未掩盖。
- [x] **T6 VERSION**:`bin/ds_web.py` VERSION → `0.37.0`(唯一允许的后端改动)。
