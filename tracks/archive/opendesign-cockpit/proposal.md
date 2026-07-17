# Proposal: opendesign-cockpit

- Date: 2026-07-17
- Status: open(plan 已合并冻结,待用户 go 开工)

## Goal

#7 视觉半:把四列工作区的伴随列(290px)升级成**项目驾驶舱列**——项目速览
(阶段/业主/当前状态/最近更新)+ 图片带 + 类目活跃度 + 最近文件,并偿还三笔
在案的债(硬编码类目名/depth2 group 缺字段/伴随列无刷新链)。

## Motivation

P5 已把"能看到文件"做完,本 track 的真实增量是"从能看到升级为驾驶舱":
设计师进项目第一眼回答"这项目在哪个阶段、最近在动什么、图片长什么样"。
同时 CompanionColumn 写死 `includes("效果图")` 违反"照用户现状认"原则
(用户类目叫"渲染"就永远空)——今天用户再次强调分类方式每人不同,这笔债必须还。

## Plan 工艺(本 track 特有)

主 agent 先独立落 plan(仓外 /root/aiwork/tasks/opendesign-dashboard-myplan.md)
→ sub Claude 读仓独立规划(未见主 plan)→ 合并。合并中 sub 推翻主 plan 三处
(见 design.md「合并记录」),主 plan 的交付快照块被 sub 论证推迟。

## Scope

- in:bin/ds_workspace.py(overview 加 latest_mtime)、bin/ds_web.py(_projects 加
  owner/status_note/group)、web/src/workspace/cockpit.ts(新纯逻辑)+
  CompanionColumn 重排 + GalleryPage 文案 + App/api.ts 接线、e2e、VERSION 0.24.0。

## Non-goals

- 不动 ChangesColumn(C 位铁律);不做中央区驾驶舱态;不开新页面/路由。
- 零新写面、零新 POST;405 不变量原样回归。
- **不做交付快照块**(需类目名启发式,猜错比不做糟;等首装采纳引擎给类目真相);
- 不做任何模板类目名匹配/排序(名序天然吃到用户自己的 01- 02- 前缀);
- 不做文件树浏览器/缩略图服务/侧栏分组折叠/fs watch(既有拒绝延续);
- 图墙项目维度预选=follow-up(gallery 现无项目维,另议)。

## Lane

fast(主审+submimo):只读 UI+读 API 加性字段,无新写面(todo-v3/p6 先例)。
