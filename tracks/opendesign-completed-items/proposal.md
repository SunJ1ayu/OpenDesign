# Proposal: opendesign-completed-items

- Date: 2026-07-16
- Status: done

## Goal

给项目工作区一个**查看已办结项**的入口 + 项目进度一览——设计师能一眼看出某项目做到哪了、
翻回已完成/已关闭的变更(#7 非视觉半第一刀)。

## Motivation

当前 ChangesColumn 筛选只有 未办结/待确认/进行中/全部,**已完成和已关闭没有专属入口**,
只能混在"全部"里翻。A2 做了"翻回"(每行 pill 可点回滚),但"查看已办结项"这一刀没做——
正是 todo-ux proposal 里挂的 "#7 第一刀 = 查看/翻回已办结项(需项目级视图)"。

## Scope

- in: `web/src/workspace/changes.ts`(新,纯逻辑:计数/筛选分类)。
- in: `web/src/workspace/ChangesColumn.tsx`(改用纯逻辑 + 「已办结」pill + 进度一览行)。
- in: `web/src/app.css`(`.proj-progress`/`.prog-item` 样式)。
- in: `tests/test_completed_items.mjs`(纯逻辑 oracle)。

## Non-goals

- 后端零改动(复用 /api/changes,不加端点)。
- 视觉半(项目驾驶舱:真实文件/图墙上屏)不在本刀——依赖 Track B 接通 + 用户真实文件夹结构。
- 待办页(跨项目)仍只显示未办结,不动。
