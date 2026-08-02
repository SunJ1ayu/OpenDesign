# Tasks: opendesign-workbench-p4

- base-ref: 7b613704bbc445e95d36d1a11f388859e305df85

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

- [x] T1 后端:变更行可选【空间】字段 — oracle 先行(4 条 red-check)→ CHANGE_RE 加可选组
      + parse_change 加 space 键 + append_change 加 space 参数(消毒+剥括号+截长)
      + MCP schema + AGENTS.md 用法一句
- [x] T2 后端:/api/health 加 model 字段(读 ~/.nanobot/config.json,读不到=null)
      + bin/set_model.py(备份→改 agents.defaults.model→提示重启)+ oracle
- [x] T3 前端:待办事项页重排(项目卡/空间小节/超期标签/按项目·按时间切换/空态)
- [x] T4 前端:搜索命令面板 ⌘K(变更+图片,文件/对话置灰;<mark> 高亮;回车跳转)
      + 侧栏「搜索」行
- [x] T5 前端:技能页(真实能力卡+预填)+ 设置弹层扩充(外观/AI 模型=真值/数据与备份/
      快捷键/检查更新)
- [x] T6 收口:VERSION 0.5.0 + dist 重构建进仓 + 全量 py/mjs 零红 + e2e 真 gateway
      (panel 修复轮后复跑 9/9,verify.md PASS)
      + verify.md(full lane)
