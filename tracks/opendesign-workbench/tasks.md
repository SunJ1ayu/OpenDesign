# Tasks: opendesign-workbench

- base-ref: 83866b2b47241c6d15eaf01f4bc3780349e70544

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

## P0 实施顺序（等用户 go 后开工）

- [ ] T1 ds_todo 结构化重构（sub Claude F1，必须最先做）：拆
      `collect(root, stale_days, today) -> dict`（C 编号/日期提取，与 SCHEMA
      变更行格式同源），`render()` 改为格式化壳；**golden 文本逐字节不变**
      （现有 6 golden 测试继续绿），MCP `list_todos` 改吃 collect 行为不变
- [ ] T2 oracle 先行：`tests/test_ds_web.py` 9 条（design.md Test strategy，
      含 F2 非 UTF-8 fixture、F7 编码逃逸变体），先红（red-check）
- [ ] T3 `bin/ds_web.py`：stdlib 服务（静态 dist + /api/todos + /api/health），
      按 design D2 全部约束（127.0.0.1、DS_WEB_PORT、明确报错、UTF-8、
      每请求现读零缓存、读期 OSError 归 500 路径（F3）、POST 等 405、
      unquote→realpath→within）
- [ ] T4 `web/` 前端骨架：Vite + React + TS 初始化（.nvmrc=22，
      package-lock 进仓；**先加 .gitignore：`/web/node_modules/` +
      `/web/.vite/`，F5**），侧栏五项（待办/聊天占位外链 8765/图片规整
      占位/3D 占位/设置占位），视觉参考 nanobot WebUI（左侧栏+主区）
- [ ] T5 待办页：fetch /api/todos 渲染只读列表，未关闭/超期高亮
- [ ] T6 构建产物 `web/dist/` 进仓 + `.gitattributes`
      （`web/dist/** -diff linguist-generated`）
- [ ] T7 install.ps1:63 钉版本（`nanobot-ai==0.2.2`，mcp 顺手一起钉）
- [ ] T8 Windows 启动物（F4）：`bin/ds-web.ps1` 薄 wrapper +
      install-windows.md "工作台"小节（启动命令 / 127.0.0.1:8766 /
      装完跑一次 `python tests\test_ds_web.py`）；README 提一句工作台入口
- [ ] T9 全量回归：现有 80 测（含 golden 逐字节）+ 新 9 条全绿
- [ ] T10 verify.md 收口（改动面已含核心重构，lane 建议 full：主+三审）

## 不在 P0 的（防蔓延，见 proposal Non-goals）

聊天实现（P1）/ 日历+提醒（P2）/ 图片规整实现（P3）/ 3D 模块（P4）/
待办写操作 / Tauri 壳 / 动 nanobot 代码或配置。
