# 工具层审计(2026-07-16)——覆盖矩阵 / 可达性 / DRY

> 对照 llm-wiki Skillify 纪律(Check-Resolvable + resolver eval + DRY 审计)做的一次
> 桌面审计。配套 resolver eval 脚本:`tests/evals/resolver_eval.py`。

## 一、工具面盘点(3 个 MCP server,18 工具)

| server | 工具 | 路由家 |
|---|---|---|
| ds_tools (11) | create_client / create_project / append_change / set_change_status / log_communication / read_project / delete_project / list_todos / set_workspace / rename_project / bind_project | AGENTS.md 工具表逐行 + docstring |
| ds_organize (3) | scan_dir / stage_plan / apply_plan | skills/organize(always)+ AGENTS.md 瘦指针 §文件整理 |
| ds_refs (4) | add_ref / find_refs / link_ref / add_style | skills/refs(always)+ AGENTS.md 瘦指针 |

**可达性结论:无暗工具**——18 个工具全部有路由家(AGENTS.md 行或 always-on skill),
无"存在但没注册说明"的 Skillify 式 15% 黑暗。

## 二、覆盖矩阵(动词 × 对象;✓=有工具,✖=空格)

| | 建 | 读 | 改 | 删 | 找/列 |
|---|---|---|---|---|---|
| 项目档案 | ✓create | ✓read | **✖字段(阶段/当前状态/地址)** | ✓delete(回收站) | ✓list_todos/侧栏 |
| 项目名 | — | — | ✓rename(五处齐动) | — | — |
| 业主档案 | ✓create_client | **✖(暗区)** | **✖(暗区)** | ✖(未规划,可接受) | ✖ |
| 变更 | ✓append | ✓read_project | ✓set_status + edit(web 针孔) | 铁律不删(已关闭代删) | ✓list_todos |
| 沟通原文 | ✓log_communication | ✓read_project | 只增不改(账本) | 不删(账本) | — |
| 参考图 | ✓add_ref | — | ✓link_ref/add_style | 铁律只写索引 | ✓find_refs |
| 工作区映射 | ✓set_workspace | list_todos 信号 | ✓bind/rename/delete 连带 | ✓delete 摘除 | ✓/api/projects |
| 机器文件 | — | ✓scan_dir | ✓move/rename(过 ds-approve) | **设计上无**(v1 拍板) | ✓scan_dir |
| index.md | ✖(create 不写) | — | rename 只改既有 [[链接]] | — | — |

### 空格裁定
1. **业主档案读/改暗区(最大空格,建 track)**:agent 能建业主却永远读不回、改不了
   (read_project 只解析 projects/,内置文件工具已关)。业主偏好/雷区/决策习惯是
   "记忆优先"产品的核心数据,现状=写入即失明。建议:`read_client(name)` +
   `update_client(name, field, value)`(白名单字段,同 ds_tools 姿势)。
2. **项目阶段推进(次大空格,建 track)**:`阶段:` 字段 create 后无工具可改,
   全生命周期(洽谈→量房→方案→深化→施工→竣工→售后)的骨架字段被冻结。
   建议:`set_stage(project, stage)`(词表闸,同 STATUSES 姿势)。
3. index.md 无人维护(create_project 不挂行,agent 无写面)→ 只影响人读的总表,
   /api/projects 不依赖它。记债不排队;做 1/2 时顺路评估要不要一起挂。
4. 业主档案删除:无工具=可接受(极低频,规则 7 兜底:做不了就明说)。

## 三、DRY / lane 审计

| 疑似重叠 | 裁定 |
|---|---|
| set_change_status vs edit_change | **两条 lane,有意设计**:agent 只有 set_change_status(窄);edit_change 是工作台待办页的 web 写针孔(带留痕/备注),不在 MCP 面上。无 LLM 路由冲突。 |
| organize 的"没有删除工具" vs delete_project | **需收窄措辞(本次已修)**:organize 说的是机器文件不能删(仍真);删"项目档案"走 delete_project。原措辞会让弱模型对"删掉重复档案"类请求误拒。 |
| set_workspace vs organize roots | 已有铁律不变量(root ⟂ DS_ORGANIZE_ROOTS),AGENTS.md §87 写死。无动作。 |
| bind_project vs set_workspace | 分工清晰(接根 vs 绑单夹),docstring 各自有"什么时候用"。无动作。 |

## 四、resolver eval(意图→工具路由)

- 脚本:`tests/evals/resolver_eval.py`(直连 MiMo,工具清单从三个 MCP 文件的
  docstring AST 抽取=与真部署同源;16 条真实说法断言 + 1 条暗区探针)。
- 跑法:`python3 tests/evals/resolver_eval.py`(需 mimocode auth.json 的 key;
  不进 pytest,网络依赖)。结果见脚本输出与本目录 resolver-eval 最新记录。
- 触发条件:新增工具、改 docstring、或真机出现误路由后必跑一次。
