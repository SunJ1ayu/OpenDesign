# Proposal: opendesign-workbench-p7

- Date: 2026-07-13
- Status: open

## 背景(真机反馈,0.7.0 验收后)
1. 「历史对话无法删除」——p6 让历史对话可见可续聊,但没有删除入口;nanobot 原生支持
   (`/api/sessions/<key>/delete`,自带"绑定自动化任务先拒"保护),ds-web 没有代理面。
2. 「项目列表应该要直接能读取我的工作区文件夹」——侧栏项目列表只来自 PKB
   `projects/*.md`;p5 的 workspace.json 要逐项手工映射,D 盘真实项目夹不进列表。

## 范围
- ds_web 第二个受控 POST 针孔:`POST /api/chat/sessions/<key>/delete` → 代理 nanobot
  原生删除(闸门同 open-folder 先例:CT json + key 白名单;鉴权靠 Authorization 透传)。
- ds_workspace 项目夹自动发现:扫描 `<root>/01项目`(候选名/可配 projectsDir);
  project_dir 解析 = 显式映射 → 文件夹名直等 → key token 唯一命中;
  /api/projects 返回 PKB ∪ 未建档文件夹(unregistered 标记,只读联合,不自动建档)。
- 前端:历史行悬停 ✕ + 确认删除 + 刷新;未建档项目行(淡化+「未建档」标),
  选中未建档项目时变更列给建档引导;文件区/图墙经自动绑定直接可用。

## 非目标
- 不自动建档(PKB 写只走 ds_tools;收件箱认领/归类引擎 = 下一 track)。
- 不做批量删除/回收站;删除 = nanobot 语义(jsonl+thread 删,不可恢复,前端确认闸)。
- 不动 chat 逻辑层协议(仅 apiFetch 加可选 init 参数)。
