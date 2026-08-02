# Proposal: opendesign-todo-ux(待办交互快修组)

- Date: 2026-07-15
- Status: open

## Goal

真机部署 v0.9.0 后用户反馈"待办页不好用、没引导"。本 track 收四条交互快修
(后端全支持,主要动前端 + 一点 AGENTS.md 文案):

- **#3 状态一键改**:最大的「待确认」pill 现在纯展示,改状态要先点「编辑」进下拉框;
  用户第一下都点在 pill 上却没反应。→ pill 可点,直接推进状态。
- **#4 完成可撤销**:状态设成 已完成/已关闭 → 该项离开 `/api/todos` → 从页面消失 → 够不到、
  改不回。手滑就没了。→ 终态变更后弹「撤销」toast。
- **#2 备注即时可见**:加的备注写进了 .md 变更历史段(没丢),但 `/api/todos` 不带 note,
  页面无反馈=对着空气输入。→ 保存后本会话乐观显示。
- **#1/#5 状态名副其实**:用户定义 待确认=球在业主(等业主确认)/ 进行中=球在我(在做);
  已关闭=作废。现在两开放态没传达含义。→ pill 加含义提示 + AGENTS.md 教 agent 按此设状态。

## Motivation

北极星是"帮设计师不忘事、到点主动问",但当前待办页把最常用动作(标记状态)埋在编辑里,
终态不可逆、备注无回显——违背"最简改法"与引导。用户反馈=真实使用场景撑腰,非"为完备"。

## Scope

- in: `web/src/TodoPage.tsx` —— pill 可点(快捷菜单直接改)、终态后撤销 toast、备注乐观回显、
  pill 含义提示。
- in: `web/src/todo.ts` —— 纯逻辑:`isTerminalStatus`、`STATUS_HINT`(oracle 直测)。
- in: `web/src/app.css` —— pill 按钮/状态菜单/toast/备注行样式。
- in: `workspace/AGENTS.md` —— 待确认/进行中 语义(球在谁)+ 已关闭=作废,教 agent 设状态。
- in: `tests/test_workbench_p4.mjs` —— 新纯逻辑用例(先红后绿)。

## Non-goals

- 「查看/翻回已办结项」= #7 第一刀(需项目级视图),不在本组。
- ChangesColumn(项目工作区变更列)同类交互暂不动。
- 后端写口径不变(复用 `/api/changes/edit`,不加端点)。
- 复核(sub claude)已过:A1 与 A2 强耦合同单元发;快捷菜单里 已完成/已关闭 不给和 进行中 同等显眼度。
