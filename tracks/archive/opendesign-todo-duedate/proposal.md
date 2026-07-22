# Proposal: opendesign-todo-duedate

- Date: 2026-07-22
- Status: open

## Goal

待办页重设计的**地基**:给每条变更加"截止日"数据模型 —— 能在项目工作区给一条变更**设/清截止日**
并**看到**它(超期红/今天/未来的着色)。这是后续「日历 / 需要今天跟进」(下一 track)的前提。

## Motivation

用户拍板做待办页重设计(多列 + 右栏日历 + 需要今天跟进)。日历/今日跟进依赖"每条变更有到期日",
而现模型里变更行日期=记录日期、"超期"是项目级「N 天没动静」,都不是单条到期日。故先立数据地基。
设截止日方式=两个都要但分期(用户选):**先做变更行日期选择器(确定性、可离线、可测)**,
聊天自然语言解析下一轮加。

## Scope

- in: 账本行**尾部** `⏳YYYY-MM-DD` token 存截止日(共享 helper `ds_common.split_due`,读写两侧同源,
  无 `⏳` 旧行零迁移、字节不变);读侧 `ds_todo.parse_change` 透出 due;写侧新 `ds_tools.set_due_date`
  (设/更新/清,保其余字节)+ `edit_change` 改正文时**保留截止日**;MCP `set_due_date_tool`;
  ds_web 新 POST 写针孔 `/api/changes/due` + `_changes`/`/api/todos` 透出 due;前端 `Change.due`/
  `OpenItem.due` + 纯函数 `dueStatus(due, today)` + **项目工作区变更行 📅 日期选择器(设/清)+ 截止日显示**;
  待办页行**只读显示** due(不加设置入口,triage 设置留下一 track)。

## Non-goals(明确挪到后续 track)

- **I.7 多列瀑布 / I.8 去限宽 / 共享折叠控件(按项目↔按时间一致)** = 紧接着的下一 track(纯前端)。
- **I.9 右栏(日历 / 需要今天跟进 / 项目助手)** = 再下一 track(消费本 track 的 due)。
- **聊天自然语言设截止日**(AI 日期解析)= 更后。
- 不改记录日期语义、不改【空间】、不动状态流转。
