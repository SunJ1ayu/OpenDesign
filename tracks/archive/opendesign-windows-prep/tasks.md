# Tasks: opendesign-windows-prep

- base-ref: 8baa0e4c31957f6d04763c6b64b18ed965d7c1f3

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

- [x] T0 前置 sweep:全工具脚本三类清单(路径/POSIX/编码),落 `tracks/opendesign-windows-prep/sweep.md`
- [x] T1 ds-todo → `ds_todo.py` 改名 + `ds-todo` 薄入口 + `DS_TODAY` 注入点(默认行为不变)
- [x] T2 oracle:`tests/test_ds_todo.py` golden 三形态 + list_todos 错误路径(先写,先见红)
- [x] T3 `ds_tools.list_todos` 改 import 直调 + try/except 显式 error(修 returncode/encoding 双 bug)
- [x] T4 回归:45 条既有测试全绿
- [x] T5 skill 手册:`skills/organize/SKILL.md` + `skills/refs/SKILL.md`(repo 内)
- [x] T6 AGENTS.md 瘦路由两行 + SkillsLoader 机械化冒烟测试
- [x] T7 `docs/deploy-security.md`(key/云上行/信任模型/反向隐私/用户决策点)
- [x] T8 `bin/ds-nanobot.ps1` 草稿(UNTESTED,key 注入按 T7 方案)
- [x] T9 config 模板占位符化 + `DEFAULT_DS_ROOT` fallback 处理;sweep ④类修点清零
