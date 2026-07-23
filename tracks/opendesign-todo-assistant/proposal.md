# Proposal: opendesign-todo-assistant

- Date: 2026-07-23
- Status: in-progress

## Goal

补齐设计交付包 v4 §I.9 的第三段:待办页右栏加**项目助手**(跨项目问答 / 记一条),
并完成它的前置地基 —— **把待办页从"每次进入重建"改成常驻路由**。

## Motivation

上一单 `opendesign-todo-rail` 把 §I.9 的月历与跟进区做完时,第三段被拆了出来,
理由是结构性的:`App.tsx` 里待办页是 `{route === "todos" && <TodoPage/>}`,离开即卸载;
把 `ChatPage` 挂进去 = **切页丢对话**,正是 track p3 花一整单治好的真机 bug。
本单先补地基再装助手。

价值面:待办页是"看全局"的地方,跨项目的问题(「C7 业主上次怎么说的」)和随手记
(「记一下 XX 项目…」)现在都要切回聊天页才能问。

## Scope

- in: `App.tsx`(待办路由常驻化 + 透传 session/active/dataEpoch)、`TodoPage.tsx`
  (取数改 active 门控 + 透传 session)、`TodoRail.tsx`(助手段 + 挂 ChatPage)、
  `app.css`、`ds_web.py` VERSION → 0.38.0。
- in: **零后端改动、零新写口**。

## Non-goals

- **不自写聊天 UI**:展开态直接挂 `ChatPage` 真身。
- **不改 skills / gallery 两个路由**(它们仍是条件渲染,不在本单范围)。
- **不做「记一下」的项目名识别/追问**:那是 agent 侧行为,前端只负责不传项目前缀 +
  在说明文案里提示带项目名。该行为**无真 gateway 无法验证**,记入 verify。
- **不做「展开对话 →」跳转到别处**:按设计稿它就在助手段标题旁,语义是就地展开;
  跳到新对话页会展示另一条 thread = 撒谎。
