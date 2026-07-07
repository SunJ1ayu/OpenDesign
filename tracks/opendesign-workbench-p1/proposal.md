# Proposal: opendesign-workbench-p1 — 前端改版(nanobot 视觉 + 聊天首屏 + 新 IA)

- Date: 2026-07-08
- Status: open(**plan v2 已冻结**:sub Claude 评审 PASS-with-changes,11 findings 全采纳,仲裁记录在 design.md 尾部;等用户 go)
- 上一期:tracks/opendesign-workbench(P0,commit 1d5b87c,verify PASS)

## Goal

把工作台从"P0 骨架+待办页"升级为用户日用的门面:nanobot 同款视觉、
首屏聊天、侧栏新 IA(聊天/待办/日历/工具箱),聊天直连本机 nanobot gateway。

## Motivation

用户对 P0 的三点反馈(7-06)+ 一点 IA 拍板(7-07):

1. P0 自创视觉(墨/纸/石青)被否——要**像素级抄 nanobot WebUI**。
2. **首屏 = 聊天窗口**,和 nanobot 一样;聊天从"以后收进来"变成工作台门面。
3. 用户可能发前端意向图;没图先抄 token 打底(已同意)。
4. IA 定型:侧栏固定项 = **聊天 / 待办 / 日历 / 工具箱**;一次性动作类功能
   (图片规整等)全进"工具箱"一页卡片,常驻视图才配独立页面。

## Scope

- in-A **视觉重皮肤**:nanobot token 全套替换(已提取:
  `tracks/opendesign-workbench/nanobot-tokens.md`),浅/深两套变量,
  基准 13/14px,零阴影 1px 边框分区,侧栏半档色差。
- in-B **IA 重排**:侧栏 = 聊天(首屏)/ 待办 / 日历(占位)/ 工具箱(占位页
  +图片规整占位卡)/ 设置(占位);待办页保留功能只换皮。
- in-C **聊天模块**(本期工程主体):浏览器直连 nanobot ws(8765)+
  ds_web 同源代理 token 签发与会话 HTTP API(8765 全模块零 CORS 是硬约束,
  已核实源码);开工第一件事 = 协议基线快照 + 冒烟测试(上期 design 已定)。
- in-D **Windows 物料**:ds-nanobot.ps1 顺手拉起 ds_web(双端口整合,
  上期递延项);docs 更新。

## Non-goals

日历实现(P2)/ 图片规整实现(P3,本期只有工具箱占位卡)/ 3D(P4)/
PKB 写端点 / 动 nanobot 代码或 fork 其编译产物 / Tauri 壳 / 移动端 /
katex 数学渲染(设计师聊天用不上)。stock WebUI(8765)保底不下线,
聊天达日用水平前不宣布替代。

## 成功标准

用户 Windows 机 `git pull` + `ds-nanobot.ps1` 后:浏览器开 8766,首屏是
聊天窗口,视觉与 nanobot 同 token 系;能新建会话、发消息、收到 MiMo 回复、
看历史会话;待办页在侧栏第二项照常工作;全量 oracle 绿。
