# Proposal: opendesign-intake

- Date: 2026-07-17
- Status: open

## Goal

收件箱认领的日常闭环:`00-收件箱` 里丢文件 → agent 给出"归到哪个项目哪个类目"的
确定性建议(staged plan,零改动)→ 用户在工作台里看到预览、点确认 → 才真正移动。
补齐"丢文件→自动归类→看到整理好的"产品脊梁的最后半截。

## Motivation

- 变更记录(打字记事)闭环早已可用;文件侧至今只有 ds_organize 三工具裸内核
  (07-02 PASS)+ taxonomy v1.0 模板(07-12 定稿),从没接到用户日常动线上。
- 用户真实动线:新文件(参考图/业主资料/量房照片)进收件箱后,现在没有任何
  引擎认领,收件箱=约定存在但功能为零。
- cockpit(0.24.0)的"交付快照块" follow-up 也等归类引擎的类目真相。

## Scope

- in: 类目规则表(taxonomy v1.0 的机读版,扩展名→类目,默认模板+可配)
- in: 收件箱清单 + 确定性归类建议(新 MCP 工具,agent 聊天里可用)
- in: staged plan 的预览与人工确认面(工作台收件箱卡片 + ds_web 受控 POST 针孔,
  posture 同 open-folder/session-delete/edit-change 三个先例)
- in: 确认后执行走既有 ds_organize.apply_plan(快照复验/审计/锁全复用)

## Non-goals

- 首装全盘"采纳现状→优化建议"扫描(onboarding 大件,单独 track;本 track 只做
  收件箱日常 loop)
- 移动 CAD/SU/MAX 及其贴图等被引用文件(v1 只动无引用文件的既有决定不变;
  规则表把这些类目标成 suggest-only)
- 图片内容识别自动分类(效果图 vs 参考图靠入口约定,分不清就问,不上视觉模型)
- 回滚组/移动清单一键还原(07-02 已裁决不做,审计可查)
- MCP 面加 approve 工具(硬闸设计:模型永远不能批准自己的 plan)
