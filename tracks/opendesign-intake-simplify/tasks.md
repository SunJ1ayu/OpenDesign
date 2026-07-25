# Tasks: opendesign-intake-simplify

- base-ref: b33c0c13f5c23d601e817c5da8327c40e9391cc4

> oracle 先行:下列判据文件先红检、先 commit,再动实现。
> oracle 文件对任何执行腿 off-limits。

## Oracle(先行,先红检)

- [ ] `tests/test_ds_tools.py` — 空业主可建档 + 不写 `[[]]` + 零 stub + 项目名仍必填;
      `test_c10_empty_name` 按新规格改写(过时考卷,主 agent 亲手)
- [ ] `tests/test_ds_lint.py` 或 test_ds_tools 内 — 空业主项目零 broken_link
- [ ] `tests/test_ds_web_api.py` — create 不带 client / client 空 → 200(原断 empty_name = 过时考卷);
      project 空仍 400;CT/键白名单/体积三闸回归不变
- [ ] `tests/test_ds_web_open_front.py`(新增)— `_pick_folder_window` 纯逻辑 4 例 +
      `_win_focus_folder` 三例(晚到/永不出现/enumerator 抛)+ `_open_windows` 时序 +
      `_spawn_win_focus` 不阻塞(<0.2s)且 daemon
- [ ] `tests/e2e/intake.e2e.mjs` — 建档表单只剩项目名一个框、页面无「业主名」、
      只填项目名建档**真成功**(不再 unregistered)、项目名框 Enter 提交

## 实现

- [ ] #3 核心:`ds_tools.create_project` client 默认空 + 必填闸只留 project +
      `client_link` 有名才写 + 空业主不建 stub;MCP 工具签名/docstring 同步(明说别猜业主名)
- [ ] #3 前端:`ChangesColumn.tsx` 删业主名 input 与 `cpClient`、按钮 disabled 改口、
      Enter 挂项目名框、`createProjectErrMsg("empty_name")` 改成"项目名要填。"
- [ ] #4 `ds_web.py`:`_pick_folder_window` / `_win_focus_folder` / `_open_windows` /
      `_spawn_win_focus`(daemon 线程,不阻塞);Windows-only glue(WINFUNCTYPE 枚举 +
      ShowWindow/SwitchToThisWindow/SetForegroundWindow 三连)薄壳隔离;
      `DS_OPEN_CMD` 与非 Windows 分支一字不动
- [ ] 版本号 0.44.0(ds_web.VERSION)

## 收货

- [ ] 全部 oracle 绿 + 回归(node --test / pytest / build / 真 chromium e2e 全套)
- [ ] **亲自截图看**:建档表单只剩一个框且能建成;空业主项目在 cockpit/项目列表里
      那格空白不难看
- [ ] verify.md(**full 四审**:主审 + submimo + subdeepseek + subglm + subkimi)——
      写路径 + PKB schema 触边,不打折
- [ ] 真机未验清单:#4 置顶效果只能用户在 Windows 上确认(deployment-target 铁律)
