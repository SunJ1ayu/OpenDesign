# Proposal: opendesign-workbench

- Date: 2026-07-06
- Status: open

## Goal

给 OpenDesign 建**自有前端工作台**（本地网页）：P0 交付 nanobot WebUI 风格的
多模块骨架 + 只读待办清单页；长期成为 OpenDesign 的主入口并最终替代
nanobot 自带 WebUI。

## Motivation

自带 WebUI 是 pip 包内编译好的 SPA，不可改、不可扩展（fork = 屎山，7-06 已裁定）；
而用户的 UI 需求会持续长出来：待办清单（将来升级日历+重要提醒）、图片规整
（统一宽度/分辨率给 PDF 排版）、将来 CAD→3D 查看（quicklook 继任者）、最终聊天
也收进来——"我们需要自己自由的工作台"（用户 2026-07-06 原话）。

## 用户需求拆解（2026-07-06 一口气版）

1. **多模块工作台**：不是待办小看板，是 OpenDesign 长期主入口。
2. **quicklook 不满意，可以不考虑它**——重写 vs 改造由主 agent 第一性判断，
   用户可接受重写，红线 = 与长期工作台适配、不出屎山。
3. **第一步交付 = 大致效果的前端骨架**，视觉参考 nanobot WebUI，不急做深。
4. **待办清单**先简单列出即可，但要有升级路径（对标 iPhone 日历：日历视图、
   重要提醒分级）。
5. **最终替代 nanobot WebUI**（聊天收进来）。
6. **记录需求（不实现）**：批量统一图片宽度/长度/分辨率（PDF 排版用），留导航位。

## Scope

- in: `web/` 前端骨架（侧栏导航+主区，nanobot WebUI 风格）；待办页读真实 PKB
  （只读）；`bin/ds_web.py` 本地服务；构建产物进仓（用户机免 Node）；oracle 测试。

## Non-goals

- 聊天模块（P1，另起 track；本 track 只留导航位+外链现有 WebUI）
- 图片规整实现、3D 查看模块（只留导航位）
- 待办写操作 / 日历视图 / 提醒分级（P0 只读；升级路径在 design 里钉死）
- Windows 桌面壳（Edge"安装为应用"白捡；Tauri 等真需要再说）
- 动 nanobot 任何代码/配置（工作台 = 旁路新进程，端口独立）

## 成功标准（P0）

- 浏览器打开本地页面：工作台骨架 + 待办页显示 PKB 真实待办（只读）。
- `git pull` 即更新，用户机不装 Node；oracle 全绿；现有 80 测不碰不破。
