# Proposal: opendesign-adoption

- Date: 2026-07-17
- Status: open

## Goal

采纳引擎 v1:首装(或任意时刻)对整个工作区做只读盘点(采纳=照现状认),
对"可安全整理"的项目内散文件给暂存建议(建议→确认走既有闸),补齐产品脊梁
「丢文件→自动归类→看到整理好的」的"存量"半边(intake 已覆盖"增量"半边)。

## Motivation

- onboarding 四步(07-09 定):采纳→建议→确认→才动手。intake 只管 00-收件箱新文件;
  存量世界(已有项目夹/散文件/未绑定项目)目前全靠人一个个 bind_project。
- taxonomy v1.0(docs/workspace-taxonomy.md,07-12 定稿)= 首装采纳标准,已解锁。
- 07-16 真机 7 个项目手动绑定,痛点实证。

## Scope(v1,最简)

- in: T1 bin/ds_adopt.py adopt_scan(只读全盘盘点报告);T2 MCP 工具 adopt_workspace
  (报告呈现,聊天大脑据此引导逐项绑定/暂存);T3 stage_adoption(项目根散文件按
  taxonomy auto 规则暂存搬运,复用 ds_organize.stage_plan;suggest 类目只给口头建议
  永不暂存);T4 文档/路由/eval;T5 版本+验证。
- **零 web 改动**:_pending_plans/approve 针孔本就通用(root 在工作区内即列即可批),
  采纳 plan 自动上既有确认卡片。

## Non-goals

- 不自动 apply、不加新写针孔、不动 DS_ORGANIZE_ROOTS 语义、不动 ds-approve。
- 不做深层错位文件搜寻(只认项目根一层散文件,镜像 intake 的认领语义)。
- 不做"缺模板类目就建夹"的文件操作(报告里 info 提示即止)。
- 不动被引用类目(CAD/SU/MAX/PSD=suggest,口头建议,连暂存都不暂存——比 intake 更保守,
  存量文件的引用风险不可知)。
- 归档/共享资源识别 = 报告展示用,不新增消费方。
