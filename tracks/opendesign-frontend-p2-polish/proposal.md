# Proposal: opendesign-frontend-p2-polish

- Date: 2026-07-19
- Status: done

## Goal
落地 Claude Design v4「质感收口」交付包(handoff/,优化修改单.md A–H + 6a 组件规范):
不动 IA 的纯前端打磨,ds-web 0.30.0 → 0.31.0。

## Motivation
v4 包对照 0.30.0 真实截图逐屏给了修改单:输入范式不统一(裸方角 input 混白底圆角卡)、
按钮无层级、「连接聊天服务」像报错页、伴随列信息过载、空态无动作。这是"差点意思"的
质感债,设计侧已给到像素级规格。

## Scope
- in:web/src + app.css + dist 重建;ds_web.py 仅 VERSION 号一行。
- **零新写口、零后端行为改动**;verify 走 fast lane(主审+submimo)。
- 两处拍板(用户未回,按主审倾向,评估时已告知用户):
  1. 发送按钮 = 文字「发送」(修改单全局原则原文;6a 画板 ↑ 圆钮视为画板未同步)。
  2. **砍掉** B 项「空间不选 AI 从内容猜」——要调 LLM 且【未分类】落盘更糟;
     维持现状:不选 = 无空间前缀。
- 澄清(主审定):D2「速览行删掉」= cockpit 速览块 row1(阶段+业主+相对时间);
  阶段 chip 并入中央列标题旁;status_note「当前状态」一句话保留(修改单未点名,
  且是 cockpit 核心价值)。

## Non-goals
- 不动 IA / 路由 / 数据流;不加图片上传(单独大件);不动聊天连接协议逻辑层
  (connection.ts / transcript.ts 及其 oracle);不做深色主题。
