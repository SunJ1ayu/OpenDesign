# Proposal: opendesign-workspace-depth2

- Date: 2026-07-16
- Status: open

## Goal

项目工作区自动发现支持**两层结构**(分组/项目,如 `2026/0315 某项目`):
`workspace.json` 新增可选 `projectsDepth`(1|2,默认 1),depth=2 时所有分组下的
项目进同一个列表、带分组标签,不用来回切 `projectsDir`。

## Motivation

用户真机(公司电脑)接入 `D:\G2 DESIGN GROUP` 认出 0 个项目——真实结构是
**年份/项目** 两层(2022–2026),而 `project_folders()` 只认一级。当前只能
`projectsDir=2026` 一次看一年。这是首个真实 D 盘结构样本,正是文件工作区
一直缺的输入。

通用性约束(用户 07-16 点名担心):**不写死"年份"**。中间层是中性"分组"
(别的用户可能按客户/地区分,或压根扁平)。机制写死、结构可配;默认 depth=1
= 现行为,零迁移,不按年份分的用户完全不受影响。

## Scope

- in: `ds_workspace.py`(load_config 收 projectsDepth + project_folders 两层扫描)
- in: `ds_tools.set_workspace` 加可选 `projects_depth` 参数(对话里能设),AGENTS.md 工具用法同步
- in: `ds_web /api/projects` unregistered 条目带 `group` 字段;前端项目行显示分组标签
- in: `config/workspace.example.json` + install-windows.md 文档
- in: oracle(test_ds_workspace / test_ds_tools / test_ds_web_proxy 扩展 + red-check)

## Non-goals

- 不自动探测 depth(显式配置,拿不准=默认 1)
- 不支持 depth≥3(真实需求只有两层;要三层是另一个提案)
- 不做分组折叠/树状 UI(前端只加标签,重排 IA 是 #7 驾驶舱的事)
- 不迁移已有显式 projects 映射(本就支持任意深度,不动)
- 不碰 ds_organize / DS_ORGANIZE_ROOTS(铁律不变量,与 workspace root 永远独立)
