# Design: opendesign-workspace-connect

- Change: opendesign-workspace-connect
- Status: done

> 权威 plan(98 行,主 agent 起草 + sub claude 独立读码复核 + 逐条合并):
> `/root/aiwork/tasks/opendesign-trackB-plan.md`。本文件是摘要,冲突以那份为准。
> 非开放架构分叉(方向已定),未跑 panel-explore。

## Approach

- **B1** `ds_tools.set_workspace(root, projects_dir="")`:写 `<DS_ROOT>/config/workspace.json`,
  保留已有 projects 映射;**真原子写**(tmp+`os.replace`);坏 JSON 先备份 `.bak` 再写全新;
  `os.path.isabs` 拒相对路径;root realpath+isdir;返回 folder_count。MCP 注册 set_workspace_tool。
- **B2** 未接入提醒放 **ds_tools.list_todos**(load_config is None → prepend 提示行),**不动
  ds_todo.render()**(被 golden 逐字节锁死)。agent 开场必跑 list_todos → 提示免费搭车。
- **B3** AGENTS.md 规则3 扩:见提醒→帮接入调 set_workspace;folder_count=0 说"没自动认出项目夹"
  不说"失败";盘符根软确认;写死不变量。
- **B4** CompanionColumn `!configured` 空态换「接入工作区」按钮 → 预填**工作区 ChatColumn**
  (App.tsx 重加 colPrefill setter/prefillCol)。

## Key trade-offs / risks

- **保留可选 projects_dir**(复核纠正 ux1 的"砍掉"):项目夹直接摊 root 一级会 folder_count=0,
  `projects_dir="."` 救。默认不传 = 只写 root 走自动发现。
- **安全:不挂 ds-approve**。root 只 scope 只读文件视图,不拓宽 LLM 上云面。铁律不变量:
  `workspace.json.root` ⟂ `DS_ORGANIZE_ROOTS` 永远独立(注释+AGENTS.md+oracle 三处守)。
  残余 = 信任非安全(被注入 agent 至多让本机浏览器看别的目录,folder_count 回显摆上台面)。

## Alternatives considered

- B2 放 render():否——golden 逐字节锁死,插行 5 测试全红。
- B4 预填主页 / 静态 how-to:否——主页跳脱上下文;预填同屏工作区聊天更顺。
- set_model.py 式直接覆写:否——非原子,崩溃留半文件。set_workspace 用 tmp+os.replace。

## Test strategy (oracle)

- py: SetWorkspaceOracle 12 例(保映射/isabs/坏JSON不崩/原子无残留/projects_dir="."认root级/
  folder_count/list_todos prepend/**不变量:不写 DS_ORGANIZE_ROOTS**)。red-check 双向咬。
- e2e: 真起 ds_web + 直调工具,未接入→提醒→set_workspace→免重启即时 configured+mapped。
- full panel-review(动 agent 能力 + 配置写入)。
