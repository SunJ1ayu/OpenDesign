# Proposal: opendesign-workbench-p4

- Date: 2026-07-12
- Status: open
- base-ref: 7b61370

## Goal

照 Claude Design v3 交付包（`handoff/`,五画板定稿）补齐工作台的三个新页面/面板,
并捎带完成已排队的「模型显示」项:

1. **4a 待办事项页重排** — 现有朴素 TodoPage → 项目卡片 + 空间小节 + 超期标签 + 按项目/按时间切换
2. **5a 搜索命令面板(⌘K)** — 全局精确查找,首版覆盖 变更+图片,文件/对话 tab 置灰待上游
3. **5b 技能页壳** — 卡片网格 + 点卡预填对话;技能列表首版静态
4. **设置弹层扩充** — 照新稿加行,其中「AI 模型」= 已排队的 ①model 显示 + `bin/set_model.py`

## Motivation

- 用户 07-12 拿 Claude Design 新做了三页定稿(待办/搜索/技能),要求照稿实现。
- 待办事项是产品命根子(不忘业主需求)的**读侧主入口**,现版 TodoPage 是 P2 的临时朴素版。
- 搜索 = 不经过 AI 的精确查找,补上"找东西"这条腿。
- 队列 ①(model 显示+set_model)与新稿设置弹层「AI 模型」行天然合并,一举两得。

## Scope

- in: 后端(最小)= 变更行可选**空间**字段(schema 决定,见 design.md);`/api/health` 加 `model` 字段;`bin/set_model.py` 切换脚本。
- in: 前端 = TodoPage 重排、Search 浮层、SkillsPage、Sidebar 加「搜索」行、设置弹层扩充。
- in: dist 重构建进仓 + e2e + oracle。

## Non-goals

- 文件搜索(文件工作区未建,卡 D 盘结构)、对话搜索(T7 会话列表挂起)— tab 置灰。
- 「来源」字段(口头/现场/微信)— 递延,meta 行留位不填。
- 真技能接入(CAD 转 3D 等)— 本轮只做壳与预填机制。
- 浏览器写端点(set_model 走仓内脚本,ds-web 只读铁律不破)。
- 图墙页、start.ps1(队列②,另起小 track)。
- t1 早期探索画板(README 明说不实现)。
