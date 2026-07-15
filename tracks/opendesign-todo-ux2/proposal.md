# Proposal: opendesign-todo-ux2(待办交互二轮 + 项目工作区回滚)

- Date: 2026-07-15
- Status: open

## Goal

v0.10.0(todo-ux)部署后用户三条反馈,收成一轮(v0.11.0,后端写口径仍不变):

- **#1 备注要能在原文上改**:现在编辑再进去备注框是空的,像要重打。→ 预填既有备注,没动就不重写。
- **#2 待办编辑框里的状态下拉多余了**:状态已经能在右边大 pill 上直接改。→ 删掉编辑框里的下拉。
- **#3 已完成不能只靠"撤销"**:撤销是瞬时的,用户要**随时**能恢复。→ 待办页仍只显示未办结;
  **项目工作区变更列(右上"全部")的每一行 pill 可点**,把已完成/已关闭改回待确认等 = 永久回滚的家。

## Motivation

第一轮把"改状态"从编辑里解放到 pill 上,但留了两处不一致(编辑框下拉冗余、备注不可续改)和一个
缺口(终态只能靠瞬时撤销)。用户真机用出来的,正是"最简/引导"没做透的地方。第 3 条与设计复核早先
结论一致:已办结项的"翻回"该落在项目级视图,不是待办页。

## Scope

- in: `web/src/StatusPicker.tsx`(新)—— 可点 pill + 快捷菜单,待办页与变更列共享。
- in: `web/src/todo.ts` —— `buildEditRequest` 加 `originalNote`(备注没变不重写)。
- in: `web/src/TodoPage.tsx` —— 备注预填、删状态下拉、statusCell 改用 StatusPicker、拔 menuFor。
- in: `web/src/workspace/ChangesColumn.tsx` —— 每行 pill 用 StatusPicker(含已完成/已关闭)可回滚;
  去掉冗余「✓ 标记完成→交 AI」按钮;pickStatus 直接改 + onEdited 重拉。
- in: `web/src/App.tsx` —— 删 onMarkDone/prefillCol,ChangesColumn 改收 onEdited(bump dataEpoch)。
- in: `web/src/app.css` —— 删死 .mark-done 样式(StatusPicker 复用既有 st-menu 等)。
- in: `tests/test_workbench_p4.mjs` —— originalNote 用例。

## Non-goals

- 不扩 `/api/todos` 带 note/history(延续 accepted deviation;备注预填靠本会话乐观值)。
- 不支持"清空/删除备注"(pre-existing 限制,用户未要求)。
- 不动后端写口径(复用 /api/changes/edit);变更列改状态直接走针孔,不再经 AI 预填。
