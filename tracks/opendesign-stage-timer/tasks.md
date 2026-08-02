# Tasks: opendesign-stage-timer

- base-ref: 00337463c1748b84c92d634d35b4b73abf4847c2
- 交付到:**ds-web 0.70.0**

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

## 判据(主 agent 亲写,先单独 commit,再 commit 实现)

- [ ] O1 `tests/test_ds_stage_timer.py` 新建 —— D3 语义表四格 + 三个校验闸 +
      段补建落点 + `parse_stage_history` 坏行跳过 + `stage_timer` 诚实闸 + 旧档案零迁移
- [ ] O2 `tests/test_ds_web_stage.py` 扩 —— `since` 键放行/多余键仍拒/类型闸/三个新错误码
- [ ] O3 `tests/test_ds_lint.py` 扩 —— `bad_stage_history` + `stage_history_mismatch`
- [ ] O4 `tests/e2e/stage_timer.e2e.mjs` 新建 —— chip 显示天数 / 未记录不出现「天」/
      改起始日后天数当场变
- [ ] O5 **红检**:O1–O4 对着未改的实现全部跑一遍,确认**该红的真红**
      (没红过的 oracle 不算 oracle)
- [ ] O6 判据单独 commit + 更新哈希存档

## 实现(派出去)

- [ ] T1 `ds_tools`:`_history_bounds` → `_section_bounds(lines, header)` 最小泛化
      (既有调用点传 `_HISTORY_HEADER`,**零行为变化**)
- [ ] T2 `ds_tools`:`_STAGE_HISTORY_HEADER` + `parse_stage_history` + `stage_timer`
      (纯函数,读写同源)
- [ ] T3 `ds_tools.set_stage(project, stage, since=None)`:D3 语义表四格 + 三个校验闸;
      **段追加必须在既有 `locked_rw` 的同一个 `with` 内**
- [ ] T4 `ds_tools._PROJECT_TEMPLATE` + `create_project`:建档写 `## 阶段历史` 首条
- [ ] T5 `ds_tools.list_projects`(加 `today` 参数)/ `read_project`:透出
      `stage_since` / `stage_days`
- [ ] T6 `ds_web._projects`:同样两个字段,**调 `ds_tools.stage_timer`,不许第三份解析**
- [ ] T7 `ds_web` 写口⑩:`_STAGE_ALLOWED_KEYS` 加 `since` + 类型闸 + 三个错误码 → 400
- [ ] T8 `ds_tools.set_stage_tool(project, stage, since="")`:职责说明按 D6 三条
- [ ] T9 `ds_lint`:`bad_stage_history` + `stage_history_mismatch`
- [ ] T10 前端:`Project` 类型两字段 + ChangesColumn stage-chip 天数 + 下拉改起始日
      + 三条错误文案(D7)
- [ ] T11 `ds_web.VERSION` → `0.70.0`

## 收货(主 agent,一道都不省)

- [ ] G1 闸①:对 oracle commit 逐字节 diff = 空
- [ ] G2 闸②:亲跑 oracle + 全量 py + 全量 mjs + tsc + build + 相邻 e2e
- [ ] G3 闸③:亲读 diff(安全面逐行 + 盯 `create mode 120000`)
- [ ] G4 **真截图看 chip 那一行**(长项目名 + 「施工交底」+ 两位数天数;
      并确认它与「⛑ N 天没动静」不打架)—— design 里点名的"数字对结果错"面
- [ ] G5 lane full 四审 → 主裁
