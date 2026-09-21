# Tasks: opendesign-b8-race-forensics

- base-ref: cf6a626806b0473ac6d34e8fdca1afd5323becfd

> 本单**不派执行腿**:交付物就是判据本身(`test_b8`),而"oracle 永远由主 agent 亲自写,
> 绝不外包"。外包一条判据的加强 = 把"有没有放水"交给被查方自查。

- [x] T0 分辨 ① / ②:代码穷举 `acquired=False` 的返回路径 + 最小实验造 ①
      (`probes/crossround.py`,收据 `evidence/crossround-run1.txt`)
- [ ] T1 红检 R1/R2/R3 的夹具(在仓外副本里做变异,活仓零改动)
- [ ] T2 改 `test_b8`:每轮收赢家 + 段内无人前置断言 + 失败当场取证
- [ ] T3 跑 R1/R2/R3 红检,收据进 evidence/
- [ ] T4 b8 连跑多遍 + python 全量(确认没把别的判据改红)
- [ ] T5 外部评审(impact high ⇒ 2 条不同家族腿),主裁
