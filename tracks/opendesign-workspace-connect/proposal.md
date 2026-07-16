# Proposal: opendesign-workspace-connect

- Date: 2026-07-16
- Status: done

## Goal

让每个用户**不碰 JSON、不找开发者**就能把工作台接到自己电脑的项目文件夹;agent 发现
没接入会主动提醒并引导接入。

## Motivation

文件区/图墙靠 `config/workspace.json`(gitignored,每台机自配)。新机 `git pull` 没有它 →
`ds_workspace.load_config` 返回 None → 文件区降级空态,且旧空态文案让用户"去 config/workspace.json 填"
——非技术用户根本改不了。需要一条对话式、零 JSON 的接入路径。

## Scope

- in: 新工具 `set_workspace(root, projects_dir?)`;list_todos 未接入主动提醒;AGENTS.md 规则;
  工作台「接入工作区」按钮。

## Non-goals

- 不挂 ds-approve(root 只 scope 只读文件视图);不碰 ds_organize 写/搬面。
- 不做 #7 项目驾驶舱(真实文件/图墙上屏)——接通文件夹后另起。
- 浏览器不做原生选文件夹(拿不到真实磁盘路径,安全限制)——走对话接入。
