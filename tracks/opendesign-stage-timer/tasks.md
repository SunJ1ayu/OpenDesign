# Tasks: opendesign-stage-timer

- base-ref: 00337463c1748b84c92d634d35b4b73abf4847c2
- 交付到:**ds-web 0.70.0**

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

## 判据(主 agent 亲写,先单独 commit,再 commit 实现)

- [x] O1 `tests/test_ds_stage_timer.py` 新建 —— D3 语义表四格 + 三个校验闸 +
      段补建落点 + `parse_stage_history` 坏行跳过 + `stage_timer` 诚实闸 + 旧档案零迁移
      ✅ 已写、已红检(34 例,仅 1 例天然绿=护栏题)
- [x] O1b **规划双出后的补强**(gpt-5.6-sol 点出,design 已收):
      严格 no-op 那格改断**整个文件**逐字节不变(不止段)+ 跨月/跨年/闰日/当天 6 个边界
- [x] O2 `tests/test_ds_web_stage.py` 扩 —— `since` 键放行/多余键仍拒/类型闸/三个新错误码
      ⚠️ 写的时候抓到自己两处**假绿**:①只断 400 会被"多余键"闸顶替 ⇒ 改断具体错误码;
      ②`.get()` 让"字段没实现"和"字段是 null"分不开 ⇒ 先断键存在
- [x] O3 `tests/test_ds_lint.py` 扩 —— `bad_stage_history` + `stage_history_mismatch`
      (5 条「该报」全红;4 条「不该报」是护栏,天然绿,已在类 docstring 里声明)
- [x] O4 `tests/e2e/stage_timer.e2e.mjs` 新建 —— 工作区 chip 天数 / 未记录不出现「天」/
      改起始日后当场变 + **整页刷新仍在**;**待办页卡头天数 / 未记录时该元素不渲染**
      ⚠️ 写的时候撞出**设计错误**:原 D7 把「· 12 天」塞进 chip,会撞既有判据
      `stage_history.e2e.mjs:121`(断言 chip 文字**精确等于**阶段名)⇒ design 已改成
      chip 外的兄弟元素 `[data-ui=stage-days]`
- [x] O4b `tests/evals/resolver_eval.py` 扩 —— **参数级**四题。现状只判工具名,D6 全靠它
      ⚠️ **实测抓到真问题**:MiMo 对「下周准备进效果图」直接选 `set_stage`
      ⇒ 会把没发生的阶段变更写进档案。已写进 D6 第 4 条
- [x] O5 **红检**:全部跑过,该红的真红
      - `test_ds_stage_timer.py` 40 例 → 仅 1 条护栏题绿
      - `test_ds_web_stage.py` 31 例 → 新增两组仅 2 条声明过的护栏题绿
      - `test_ds_lint.py` → 5 条「该报」全红
      - `stage_timer.e2e.mjs` → A/C/D/E 全红(元素不存在),B 护栏绿
      - `resolver_eval.py` → 参数级 4 题红 3(第 4 题是护栏);既有 27 题仍 ALL PASS
      - 其余 29 个 py 套件回归全绿;`test_ws_protocol_smoke` 是**跳过**
        (要 gateway 在跑),单独跑一样,与本单无关
- [x] O6 判据单独 commit(`3735942`)+ 哈希存档
      `/root/aiwork/logs/stage-timer-oracle-hashes.txt`(aiwork `0eb50dc`,5 份全列)

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
- [ ] T10 前端①:`Project` 类型两字段 + ChangesColumn stage-chip 天数 + 下拉改起始日
      + 三条错误文案(D7①)
- [ ] T10b 前端②:**TodoPage 项目卡头 `card-stage` 旁加只读天数**(D7②);
      `stage_days == null` ⇒ 整个元素不渲染;**不许改 `[data-ui=card-stage]` 节点本身**
      (既有 e2e 锁着它)
- [ ] T11 `ds_web.VERSION` → `0.70.0`

## 收货(主 agent,一道都不省)

- [ ] G1 闸①:对 oracle commit 逐字节 diff = 空
- [ ] G2 闸②:亲跑 oracle + 全量 py + 全量 mjs + tsc + build + 相邻 e2e
- [ ] G3 闸③:亲读 diff(安全面逐行 + 盯 `create mode 120000`)
- [ ] G4 **真截图看两处**:①工作区 chip 那一行(长项目名 + 「施工交底」+ 两位数天数;
      确认它与「⛑ N 天没动静」不打架);②**待办页项目卡头**(一屏多卡,确认天数不挤、
      未记录的卡不留空洞)—— design 里点名的"数字对结果错"面
- [ ] G5 lane full 四审 → 主裁
- [ ] G6 **部署验证**:装机后 `/api/health` 回显 `0.70.0`,且**待办页真的看到天数**
      (盘上和运行时对不上 = BLOCK)
