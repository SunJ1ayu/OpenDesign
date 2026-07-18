# Proposal: opendesign-frontend-p1

- Date: 2026-07-18
- Status: open

## Goal
前端"直接点"P1 三项(roadmap docs/frontend-actions-roadmap.md):
①变更正文就地编辑 ②收件箱方案单条纠偏(跳过)③项目↔文件夹关联下拉。

## Motivation
07-18 真机反馈线第二批:P0 三项(记一条/建档/扫描按钮)已清,这三个是
次高频的"还得回聊天"摩擦点。

## Scope
- in: ChangesColumn 行正文就地编辑(复用 /api/changes/edit 的 new_text,后端零改动)
- in: 新针孔 POST /api/intake/amend——待确认 plan 单行"跳过",剩余行重新暂存,旧 plan 标 superseded
- in: 新针孔 POST /api/projects/bind——复用 ds_tools.bind_project 全部既有闸;CompanionColumn unmapped 态下拉选未建档文件夹
- in: ds-web 0.30.0

## Non-goals
- 纠偏"改目标"(仍走聊天;需项目/类目双下拉+dst 反向推导,成本/频次不成比例,留 v2)
- 图片上传、批量选择跳过、项目改名/删除 UI

## Lane
新写口两个(amend/bind)= 安全面 → verify full 四审(Tiered execution §4)。
执行腿 = Sonnet 5 worktree;oracle 主 agent 亲写先行、先 commit 再派活。
