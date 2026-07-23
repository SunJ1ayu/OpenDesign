# Proposal: opendesign-todo-layout

- Date: 2026-07-23
- Status: in-progress

## Goal

待办事项页布局收口:「按项目」改多列瀑布 + 卡排序 + 闲置项目占位卡,「按时间」去限宽保单列,
两视图用**同一个**折叠控件。

## Motivation

真机反馈 + 设计交付包 v4 第二轮,四条都落在待办页且互相耦合(布局一改折叠也得改),
合成一个 track 一次做完:

1. **I.7**「按项目」视图改多列瀑布 + 去居中限宽 + 卡排序 + 无未办结项目合并占位卡。
2. **I.8**「按时间」视图保持单列(时间轴要单一阅读顺序),只去限宽。
3. **07-22 反馈 #1**「按时间」的日期批次折叠按钮看不出能点(9px chev + 整行像纯标题)。
4. **07-22 反馈 #2**「按项目」的项目卡也要能整卡折叠。
   **用户硬约束:#3/#4 必须是同一个折叠控件(视觉 + 行为一致)。**

来源:`/root/aiwork/tasks/opendesign-feedback-20260721.md`(尾部 07-22 追加)+
`/root/aiwork/tasks/opendesign-feedback-20260722.md`;设计稿
`design_handoff_opendesign_workspace/优化修改单.md` §I.7/I.8 + `screenshots/11-待办双列.png`。

## Scope

- in: 只动前端(`web/src/todo.ts` / `TodoPage.tsx` / 新组件 `GroupToggle.tsx` / `app.css`)。
- in: **零后端改动、零新写口、零 schema 改动** —— 数据源仍是既有 `/api/todos`。

## Non-goals

- **不做 I.9 右栏**(日历 / 需要今天跟进 / 项目助手):下一个 track,单独做。
- 不动批量选择 / 行内编辑 / 状态 pill / 截止日 —— 只保证它们在新布局下不回归。
- 不引入 CSS 框架或布局库:多列用原生 `columns`,瀑布语义天然。
