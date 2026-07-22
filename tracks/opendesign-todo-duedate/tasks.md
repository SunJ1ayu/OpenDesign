# Tasks: opendesign-todo-duedate

- base-ref: 9b4417ce28878b19daff8163e20dd4537ddc940a

> oracle 已先行 commit,对执行腿逐字节 off-limits:
> `tests/test_ds_duedate.py` / `tests/test_todo_duedate.mjs`。

- [x] T1 `ds_common`:`DUE_SUFFIX_RE` + `split_due` + `format_due_suffix`
- [x] T2 `ds_todo.parse_change`:命中后 split_due,返回 dict 加 `due`;collect open_items 加 `due`
- [x] T3 `ds_tools.set_due_date`(设/更新/清,保其余字节,invalid_due/change_not_found/no-op)+ edit_change 改正文保留截止日
- [x] T4 `ds_tools` MCP `set_due_date_tool`
- [x] T5 `ds_web`:`_changes` 透出 due + 新 POST 写针孔 `/api/changes/due`(posture 照抄 _edit_change)
- [x] T6 前端:`api.ts` Change.due + setDueDate;`todo.ts` OpenItem.due + `dueStatus`;ChangesColumn 行 📅 设/清 + 显示;TodoPage 行只读显示
- [x] T7 e2e `tests/e2e/duedate.e2e.mjs`:真 ds_web set→读回→清→改正文保留 due
- [x] T8 自检:两 oracle + 全量 py(render golden 必绿)+ 全量 mjs + build + tsc 全绿;VERSION → 0.35.0
