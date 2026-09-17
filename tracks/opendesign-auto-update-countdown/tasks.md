# Tasks: opendesign-auto-update-countdown

- base-ref: bdad4222b9774505f7674fe3cc46a4ed7cdb4068

> 判据编号与问法只在 design.md 的 `## Test strategy (oracle)` 一处,这里只引用。

- [ ] 判据先行(主 agent):au1~au12、ac1~ac8、AC-A~F、aw1~aw3 + t9a 字段表加 `auto_update`;单独 commit,确认按预期红
- [ ] 攻题:第三方攻「哪条断言全绿了结果仍然错」,记录落仓外,盖 oracle 哈希
- [ ] 派活(delegate-codex,gpt-5.5):后端 `ds_web.py` / `ds_update_apply.py`(+ 可选新模块)、前端 `update.ts` / `App.tsx` / `Sidebar.tsx` / 样式 / `web/dist`
- [ ] 收货三闸:`--receive` / 亲跑 python+node+e2e+build / 亲读 diff
- [ ] Windows 真机 e2e(harness 与判定器由主 agent 改):推 `ci-update/*` 跑八场景,亲读事实
- [ ] 红检:退回基线 build 后判据必须红
- [ ] 全仓总跑收据
- [ ] 自审落盘 → `track preflight` → panel-review(high,两家)→ 仲裁 → 归档
- [ ] 问业主:bump / 发版
