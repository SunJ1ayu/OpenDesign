# Proposal: opendesign-todo-rail

- Date: 2026-07-23
- Status: in-progress

## Goal

待办事项页加 320px 右栏,落地设计交付包 v4 §I.9 的前两段:**日程月历**(消费 0.35.0 的
`due` 字段,点日期过滤主列表)+ **需要今天跟进**(超期 + 今天到期的跨项目卡片)。

## Motivation

0.35.0 给每条变更加了截止日,但目前只在变更行/待办行显示一个 tag —— **有了数据没有视图**。
§I.9 的月历与跟进区正是这份数据的消费面:让设计师一眼看到「哪天有事」「今天必须处理什么」。

## Scope

- in: `web/src/schedule.ts`(新,三个纯函数)、`web/src/TodoRail.tsx`(新,右栏)、
  `TodoPage.tsx`(接右栏 + 日期过滤)、`app.css`、`ds_web.py` VERSION → 0.37.0。
- in: **零后端改动、零新写口**(数据全部来自既有 `/api/todos`)。

## Non-goals

- **§I.9 第三段「项目助手」不在本单**:待办页当前不是 keep-mounted 路由,挂聊天进去会
  切页丢对话;需先做路由改造 + session 管线 → 紧接着的下一单 `opendesign-todo-assistant`。
  详见 design.md「为什么拆」。
- 设计稿说的「删除今日待办」「替换任务统计环形图」= **空操作**,我们代码里从来没有这两个
  元素(那是设计方自己旧稿的组件)。
- 不动主列表的完整性:跟进区与主列表有交集是对的,不从主列表剔除。
