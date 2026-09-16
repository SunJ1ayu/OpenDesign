# Tasks: opendesign-e2e-no-egress-browser-tmp

- base-ref: 34d4155a6d925210c9ea22086be56bc2d4334285

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

- [x] 判据先行:`tests/test_e2e_harness_guard.mjs`(ne0~ne8、bt1~bt3),在现有代码上跑出红,单独 commit
- [x] 实现 ①:helpers.mjs 无出口守卫 + `NEEDS_LIVE_GATEWAY`;`tests/e2e/_no_egress.py` + 3 个 `.e2e.py` 导入
- [x] 实现 ②:launchBrowser 自有 TMPDIR + 退出收掉 + 点名;run-all.sh 汇总打印 notes
- [x] 红检(变异咬住 ne/bt 关键断言)
- [x] e2e 总跑(隔离后 40 条仍全过)+ 全量总跑 --with-gateway
- [x] panel-review(impact high:判卷/沙箱控制面)→ 仲裁
