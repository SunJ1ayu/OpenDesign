# Proposal: opendesign-bind-project

- Date: 2026-07-16
- Status: open

## Goal

新 MCP 工具 `bind_project(project, folder)`:用户在对话里说"那个文件夹就是 XX 项目",
助手把显式映射写进 workspace.json,重复条目合一(建档项目 ↔ 工作区文件夹)。

## Motivation

用户真机(07-16,当天第五个实证断层):接入工作区后,自动绑定三级(显式映射/名字
直等/token 唯一命中)对不上真实命名 → 同名项目出现两行,而"没绑上"时唯一出口是
手改 JSON。保守不绑是对的(绑错比不绑重),缺的是对话里的合并动作。

## Scope

- in: `ds_tools.bind_project` + MCP 注册(写侧闸:项目必须已建档、folder 必须是
  系统已发现的文件夹 key)
- in: 原子写提取公共 helper(set_workspace 同款,不复制第二份)
- in: workspace/AGENTS.md 工具行+话术;CompanionColumn"未关联"文案从"改 JSON"
  改为指向对话;install-windows.md 提对话路径
- in: oracle(BindProjectOracle)+ red-check

## Non-goals

- 不做解绑(重绑=纠偏;删映射手改,极少发生)
- 不做浏览器端合并按钮(写只走 MCP=对话,405 铁律;UI 入口另议)
- 不接受任意相对路径作 folder(只认已发现的文件夹 key,杜绝第二条解析/逃逸面)
