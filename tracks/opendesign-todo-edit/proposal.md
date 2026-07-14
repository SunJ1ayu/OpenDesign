# Proposal: opendesign-todo-edit

- Date: 2026-07-14
- Status: open

## Goal

待办事项支持在工作台**直接编辑**(不必回头跟 agent 说):
- 改**状态**(待确认/进行中/已完成/已关闭)——最常用的"标记完成/进行中"
- 改**正文**(修措辞/细节)——**改正文必须留痕**(见下),防日后与业主"我明明说过 X"扯皮
- 加**备注**(设计师自己的批注,与业主原话分开)

(用户拍板:范围=正文+备注+状态,不含空间;改正文=留痕。)

## Motivation

待办目前纯只读(TodoPage 只摆不改)。日常里"这条其实已经做完了""业主口误我记错一个字"
"补一句自己的判断"这类**快速修正**,现在要绕回聊天让 agent 改,慢。直接改更顺手。

关键约束:agent 与工作台**共用同一份真相**(项目 .md 的「变更记录」行)。所以直接改
**对 agent 无害的前提是:改必须走保格式的受控写入口**(像现有 open-folder/session-delete
针孔),而不是放开改 .md 原文——格式一坏,那条待办在 agent 眼里就消失/读错(与 H1/M2 同类雷)。

## Scope

- in: **ds_tools.edit_change(project, cnum, new_status?, new_text?, note?)** —— 按 (项目, C编号)
  定位变更行(复用 set_change_status 定位逻辑),ds_lock 锁内保格式改写,经 _resolve 名字闸。
  - new_status:改主行状态(同 set_change_status)。
  - new_text:**先把旧正文留痕**(在该变更行下插一条缩进子行 `  ↳ 改于 {date},原:{旧正文}`),
    再更新主行正文。留痕子行不以 `- [状态]` 开头 ⇒ parse_change 天然不认 ⇒ 不成新待办、不扰 collect;
    agent read_project 能看到=有益上下文。
  - note:在该变更行下插/更新一条 `  · 备注: {内容}` 子行(同样被 parse_change 忽略)。
- in: **ds_web POST 针孔 `/api/changes/edit`** —— 精确匹配 + CT json 闸 + body 键白名单,鉴权同现有
  针孔 posture;调 edit_change。其余 POST 维持 405(只读铁律的又一个受控开口)。
- in: **/api/projects/<key>/changes 端点扩展** —— 每条变更附带其 note / 编辑历史子行,供前端展示。
- in: **前端 TodoPage** —— 每行改状态(点选)、改正文(内联编辑)、加备注(输入框);改正文后显示
  "改过 · 看原文";编辑成功后 bump dataEpoch(复用 M5)即时刷新。
- in: **workspace/AGENTS.md + skills** —— 告知 agent 变更行下可能有 `  ↳原:`/`  · 备注:` 子行:
  读项目时当上下文,append_change 插新行时跳过尾随子行。
- in: **测试**(先红后绿):edit_change 保格式/留痕/子行不成待办/并发锁;针孔鉴权与 405 不变量;
  changes 端点带回历史;前端 mjs;真 ds_web roundtrip。

## Non-goals

- 不做空间重标(用户本轮排除)。
- 不做删除整条变更(删=丢历史,与"留痕"背道;要删走 agent 或后续单独议)。
- 不做批量编辑 / 撤销栈(v1 单条即时改)。
- 不做独立 audit.log 文件(选"同文件子行"方案:更可见、利于扯皮取证、零新存储)。
- **打破只读铁律**是有意为之的第一个内容写口;缓解=受控针孔+保格式+ds_lock+名字闸,
  与既有针孔同 posture,verify 走 full lane 三审。
