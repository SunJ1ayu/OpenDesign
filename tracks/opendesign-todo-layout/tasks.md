# Tasks: opendesign-todo-layout

- base-ref: 0a97f7f14063b302ff65553c79338598158d84dd
- oracle-commit: 10212c9(`tests/test_todo_layout.mjs` + `tests/e2e/todo_layout.e2e.mjs`,
  执行腿**逐字节 off-limits**)

> 执行腿 = Sonnet 5 worktree。判据由主 agent 拥有;不 push / 不 merge / 不归档。

- [ ] **T1 `web/src/todo.ts`**:新增 `ProjectCard` 类型 + `orderProjectCards` + `idleProjectKeys`
      两个纯函数(契约见 design.md §1 与 `tests/test_todo_layout.mjs`)。
- [ ] **T2 `web/src/GroupToggle.tsx`**:新共享折叠控件(`.grp-toggle` +
      `data-ui="group-toggle"` + `aria-expanded`),内含 chev + children + `.rule`(flex:1,
      使可点区横跨整行)。默认态策略由调用方给,组件不管。
- [ ] **T3 `TodoPage.tsx` 按时间视图**:日期批次头改用 `GroupToggle`,把原 `.rule` 挪进控件内,
      「全选本组」留在控件外;删掉 `.batch-toggle` 旧写法(不留两套)。
- [ ] **T4 `TodoPage.tsx` 按项目视图**:项目卡头改用 `GroupToggle`(包 dot/名字/条数/超期标签),
      「去项目 →」留在控件外;卡内正文按折叠态渲染;**默认全部展开**;
      折叠 key = `@proj|<projectKey>`,复用既有 `toggled` Set,不新增 state。
- [ ] **T5 `TodoPage.tsx` 卡序与占位卡**:项目卡改用 `orderProjectCards` 出序;
      新增末尾虚线占位卡 `[data-ui="todo-idle-card"]`(仅「按项目」视图),
      内容 = `idleProjectKeys(已建档项目 keys, 有卡 keys, stale keys)` 映射成项目名、顿号连接
      + 「没有未办结事项」;删掉旧的「其余 N 个项目没有未办结事项」行。
      `staleNoCard` 的「⛑ N 天没动静」独立行**保留不动**。
- [ ] **T6 `web/src/app.css`**:`.todo-cards.by-project`(columns:2 / ≥1600 三列 /
      column-gap:16px / 卡片 break-inside:avoid + margin-bottom:16px / 去 max-width 与居中)、
      `.todo-cards.by-time`(flex 单列 / 去 max-width 与居中)、`.todo-rest` 同步去限宽、
      `.grp-toggle`(chev ≥11px、hover 底色、cursor:pointer、rule flex:1)、
      占位卡虚线样式;删掉 `.batch-head .batch-toggle` 旧规则。
- [ ] **T7 自检**:`tests/test_todo_layout.mjs` 全绿 + 全量 mjs 回归 + `tsc -b` + `npm run build`
      + `tests/e2e/todo_layout.e2e.mjs` 全绿 + 相邻 e2e(`todo_batch_space` / `duedate`)不回归。
- [ ] **T8 VERSION**:`bin/ds_web.py` VERSION → `0.36.0`(唯一允许的后端改动)。
