# Proposal: opendesign-windows-prep

- Date: 2026-07-03
- Status: open

## Goal

Windows 部署预备包:把不依赖用户任何输入、又挡在 Windows 部署路上的活一次清掉——
ds-todo 特征化测试 + list_todos 双 bug 修复、organize/refs skill 手册(repo 内规范副本)、
凭证与边界方案文档、Windows 启动物草稿(ps1 + config 模板占位符化)。

## Motivation

下一大步 = 装到 Windows 机器(先自己的试跑再装别人的),目标机还没到手,但一批预备活
现在就能做。计划经 sub Claude 独立评审(PASS-with-changes,10 findings 全核实采纳)后
定稿:`/root/aiwork/tasks/opendesign-next-step-plan.md`(v2)。评审同时抓到两个现存真 bug
(list_todos 不查 returncode 静默假成功 / subprocess 无 encoding,Windows cp936 下 "▸" 必炸)
和一个过期前提(ds-todo 已是 Python,原"重写"任务不存在)。

## Scope

- in: 前置跨平台 sweep(路径/POSIX/编码三类清单)
- in: ① ds-todo today 注入点 + golden 特征化测试;list_todos 修 returncode/encoding
- in: ② skills/organize + skills/refs 的 SKILL.md(repo 内)+ AGENTS.md 瘦路由 + SkillsLoader 冒烟
- in: ③ docs/deploy-security.md(key 归属/云上行边界/信任模型/用户决策点)
- in: ④ bin/ds-nanobot.ps1 草稿 + config 模板占位符化(标 UNTESTED)

## Non-goals

- schema A/B(等用户课件)、真实数据替换、飞书上线、GitHub 分发
- resolver eval、rollback/回收站、纯本地模型
- 真机 Windows 验证(等目标机;④只做静态走查,不声称已验证)
