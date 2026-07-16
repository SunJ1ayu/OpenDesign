# Proposal: opendesign-rename-project

- Date: 2026-07-16
- Status: open

## Goal

新 MCP 工具 `rename_project(old, new)`:一次性、一致地把项目改名——档案文件+内页
标题、业主档案 [[链接]]、refs 索引"用于:"段、index.md 链接、workspace.json 映射键
五处同步,返回改动清单。

## Motivation

断层#6(07-16 真机):用户拍板"项目名以文件夹为准对齐",助手无改名工具,建议
用户手改 md——那会让 workspace.json 映射键悬空(刚绑的 7 个映射再裂开)、refs/
业主链接断掉。改名牵五处一致性,正该是一只带闸的手。

## Scope

- in: ds_tools.rename_project + MCP 注册 + AGENTS.md 行
- in: oracle(RenameProjectOracle)+ red-check
- 五处引用:projects/<key>.md(名+首标题)、clients/*.md 与 index.md 的 [[old]]、
  refs-index.md 用于段精确项、workspace.json projects 键

## Non-goals

- 不改变更历史/沟通日志正文里散文提到的旧名(账本语义,不重写历史)
- 不做批量改名(一次一个,LLM 循环调)
- 不做业主改名(另一个动作,按需再起)
