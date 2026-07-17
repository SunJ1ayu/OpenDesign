# Proposal: opendesign-set-stage

- Date: 2026-07-17
- Status: open

## Goal

补审计空格②(docs/tool-audit-20260716.md):`阶段:` 字段 create_project 后无工具
可改,全生命周期(洽谈→…→售后)的骨架字段被冻结。交付 `set_stage(project, stage)`。

## Motivation

"翡翠湾开始施工了"这类话现在无处落——agent 只能口头应付,项目档案的阶段永远停在
建档那天。阶段是超期提醒/全生命周期视图的骨架字段。

## Scope

- in: bin/ds_tools.py `PROJECT_STAGES` 词表常量(单一真相源,原只活在 AGENTS.md
  散文)+ `set_stage` 核心 + MCP 注册;AGENTS.md 工具表一行+阶段词表段指向工具;
  oracle 套件先红后绿;resolver eval 一条新断言;VERSION 0.23.0。

## Non-goals

- create_project 的 stage 参数补词表闸(存量行为,单独议);
- 阶段变更历史/留痕(阶段是"当前值"语义,历史可从对话/git 追);
- 阶段驱动的提醒策略(等真实使用)。

## Lane

full panel(新 MCP 写面,同 log_communication/bind_project/delete_project 先例)。
