# Proposal: opendesign-file-organizer

- Date: 2026-07-02
- Status: open

## Goal

给 OpenDesign(Nanobot+MiMo)新增"整理文件夹"能力:`bin/ds_organize.py` 三工具
(scan_dir / stage_plan / apply_plan)+ `bin/ds-approve` 人工确认硬闸。LLM 只能
提方案,**未经人工批准物理上无法执行**任何文件改动。

## Motivation

用户要把 OpenDesign 装到另一台电脑(Windows 优先),除设计记忆外还要能整理那台
机器的文件夹。安全模型用户已拍板:能力给足,但执行前必须人工确认,且确认闸做在
工具层(模型绕不过),不依赖前端。

## Scope

- in: `ds_organize.py`(纯 Python 核心 + stdio MCP 包装,零依赖可测,照 ds_tools.py 风格)
- in: MVP 原语 = **move / rename 两种**(归类/归档 = move 进子目录)
- in: `bin/ds-approve <plan_id>` 批准 CLI(模型无工具可造 `.approved` 标记)
- in: oracle 测试矩阵(tests/test_ds_organize.py,零依赖零网络)
- in: 安全层:root 白名单防逃逸、不覆盖、方案漂移检测(size+mtime 快照)、audit.log、批准单 plan 生效、不可重复 apply

## Non-goals

- **delete(用户 2026-07-02 拍板砍掉)**——连回收站/回滚逻辑一起不做;工具收到 delete 操作直接拒绝
- 自动分类逻辑(归类方案是大脑/LLM 的活,工具只校验+执行)
- Windows 移植与启动脚本(路线 B:Linux 测绿后最后套壳,另起任务)
- 漂亮的确认 UI(stock WebUI 文字 + ds-approve 够用,复选框面板以后再说)
- 查重/归档策略等更多原语(建立在 move 之上,按真实使用再加)
