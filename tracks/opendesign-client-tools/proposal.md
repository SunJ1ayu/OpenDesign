# Proposal: opendesign-client-tools

- Date: 2026-07-17
- Status: open

## Goal

补上工具层审计(docs/tool-audit-20260716.md)裁定的最大空格:**业主档案读/改暗区**。
交付 `read_client(name)` + `update_client(name, field, value)` 两个 MCP 工具。

## Motivation

agent 能 `create_client` 建业主档案,却永远读不回、改不了(read_project 只解析
projects/,内置文件工具已关)。业主偏好/雷区/决策习惯是"记忆优先"产品的核心数据,
现状 = **写入即失明**:

- 设计师说"张伟预算调到 40 万"→ agent 没有任何工具能落进档案;
- 设计师问"张伟忌讳什么来着?"→ agent 读不到 clients/张伟.md,只能装傻或臆造。

## Scope

- in: bin/ds_tools.py 两个核心函数 + MCP 注册(docstring=路由家);
  workspace/AGENTS.md 工具表两行;tests/test_ds_tools.py 两个 oracle 套件(先红后绿);
  tests/evals/resolver_eval.py 补路由断言(暗区探针要翻转);ds-web VERSION bump。

## Non-goals

- index.md 挂行(审计裁定记债不排队;本 track 顺路评估,结论写 verify.md);
- 业主档案删除(审计裁定可接受,规则 7 兜底);
- `关联项目` 字段开放写(机器管理字段,rename/delete_project 连带维护,
  LLM 自由改写会打断五处一致改名的记账);
- set_stage(审计空格 #2,下一个 track);
- 前端业主档案页(等真实使用反馈)。

## Lane

full panel(新增 MCP 写面,同 Track D log_communication 先例)。
