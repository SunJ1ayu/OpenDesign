# Verify: opendesign-bind-project

- Date: 2026-07-16
- Verdict: PASS

## Mechanical checks

- [x] build passes(tsc -b + vite)
- [x] tests pass(BindProjectOracle 11 例先红后绿;test_ds_tools 78 绿;
      受影响读侧 ds_workspace/ds_web_api/ds_web/ds_todo 全绿)
- [x] 突变红检:①去 folder 成员闸→b05 红 ②去项目存在闸→b03 红;还原绿
- [x] no secrets / unsafe ops(写面=workspace.json 单文件;不拓宽 LLM 读写域;
      DS_ORGANIZE_ROOTS 铁律隔离未动)

## Review

- lane: full(panel-review,PANEL_DIFF_BASE=8ee0ee2;my-review 闸命名踩坑一次:
  要求 `<task文件名>-my-review.md`,对齐后重发)
- 主审(先落盘 tasks/opendesign-bind-project-review-my-review.md):PASS,
  0 BLOCK/0 MUST;自查在 panel 前抓到并修掉真缺口=助手无文件夹枚举工具+侧栏
  把 `组:名` 拆两段展示 → 纯名唯一命中+失败/歧义带 folders 候选(自愈回路)。
- **subsense(DeepSeek agent 腿)**:PASS,5 NIT,全卷质量高。仲裁:
  - NIT-1 raw 顶层非 dict 崩 AttributeError → **收**(真代码级缺口主审漏,
    一行守卫对齐全库优雅报错惯例,已修);
  - NIT-3 同对重绑幂等无测试 → **收**(b02b 已补);
  - NIT-5 MCP docstring 缺纯名回退 → **收且加重**(AGENTS.md 要 install 拷贝,
    MCP docstring 是 git pull 即达、LLM 调用时真看的那份,必须齐;已改);
  - NIT-2 load_config/raw 重读竞态 → **拒**(MCP stdio 单线程顺序,无触发路径);
  - NIT-4 type hint 非强制 → **拒**(Python 惯例,调用方受控)。
- **submimo**:rc=0 但空转(invalid tool + doom_loop 自拒),无信号——底座
  schema 病复发(07-02 同型),记工具债。
- **subglm**:缺席(百炼 429 余额不足,需充值/换 key),记录。
- arbitrated verdict(主裁,实际=主审+subsense 双方独立核对一致): **PASS**

## Accepted deviations

- 单可用 employee(subsense)非三家齐;主审+subsense 在安全面(不拓宽读写域/
  rel 不可逃逸/纯名唯一不猜)独立核对结论一致,按单 reviewer fallback 规则记录。
- depth1 下 Linux 含 `:` 文件夹会被纯名分支按 `组:名` 拆(NTFS 禁字,真机
  不可能;subsense 判"correct behavior",主审记边缘)。
- 候选名单封顶 50,大工作区可能截断(助手可让用户报年份缩小)。
- 新 MCP 工具需 gateway 重启注册(验收流程 start.ps1 stop/start 顺路覆盖);
  AGENTS.md 话术照旧要 install 拷贝(MCP docstring 已自带同等引导,git pull 即达)。
