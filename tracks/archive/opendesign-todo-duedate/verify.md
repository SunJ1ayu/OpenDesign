# Verify: opendesign-todo-duedate

- Date: 2026-07-23
- Verdict: PASS

## Mechanical checks
- [x] build passes(tsc rc=0 · web build 成 · dist 重建)
- [x] tests pass(oracle 后端 16/16 + 前端 4/4 · 全量 mjs 164/164 · render golden test_ds_todo OK · e2e duedate 全绿;py 存量 ws_protocol_smoke rc=3 gateway-off skip)
- [x] no secrets / unsafe ops(新写针孔 /api/changes/due posture 照抄 _edit_change;写核心只动行尾 token)

## Review
- lane: **full**(新账本字段 + 新写针孔 + 写核心正则面 = 数据一致性)
- 三硬闸(主 agent 亲验):闸① oracle 逐字节零改动;闸② 亲跑全绿(render golden 保住=无 due 旧行字节不变);闸③ 逐行读写核心。
- findings(panel 3 腿 unanimous PASS,subkimi rc=1 基建失败缺席;主裁复核):
  - [gate③ 自查·已修 cc2f8eb] ChangesColumn 着色基准 today 用 toISOString()=UTC → UTC+8 午夜偏移误标;改本地日期,与 TodoPage data.today 对齐。
  - [subdeepseek·非问题] set_due_date `.rstrip()` 削整行尾空白:仅在真改 due 时触发、rstrip 只削空白、账本行无有意义尾空白 → 理论无害,主裁 code 核实接受不改。
  - [判据邻改·合法] test_ds_todo.py 给 collect 期望 open dict 加 `"due":None`(新契约字段,非弱化)。
- arbitrated verdict(主裁):**PASS**。3 腿一致 PASS 未降主审 code-verified 判断;gate③ 自查的真 bug 已修。

## Accepted deviations
- ChangesColumn 着色 today 用客户端本地日期(非服务端 DS_TODAY):纯展示分类,不写账本;TodoPage 用 data.today。可接受的口径差(都不影响写入)。
- subkimi 单腿基建失败缺席:3/4 腿出卷全 PASS,主审 full 独立审到位。
