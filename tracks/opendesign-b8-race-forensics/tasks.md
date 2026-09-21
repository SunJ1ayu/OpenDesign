# Tasks: opendesign-b8-race-forensics

- base-ref: cf6a626806b0473ac6d34e8fdca1afd5323becfd

> 本单**不派执行腿**:交付物就是判据本身(`test_b8`),而"oracle 永远由主 agent 亲自写,
> 绝不外包"。外包一条判据的加强 = 把"有没有放水"交给被查方自查。

- [x] T0 分辨 ① / ②:代码穷举 `acquired=False` 的返回路径 + 最小实验造 ①
      (`probes/crossround.py`,收据 `evidence/crossround-run1.txt`)
- [x] T1 红检 R1/R2/R3 的夹具(在仓外副本里做变异,活仓零改动)
      —— 实际造了 8 个情景,夹具还钉「红在哪条断言上」(`probes/redcheck.py`)
- [x] T2 改 `test_b8`:每轮收赢家 + 段内无人前置断言 + 失败当场取证
- [x] T3 跑 R1/R2/R3 红检,收据进 evidence/
- [x] T4 b8 连跑多遍 + python 全量(确认没把别的判据改红)
      🔴 **这一步红了,红得对**:我把三条断言写成了 `if …: self.fail(…)`,
      正常跑永远不执行 ⇒ 死断言闸当场逮住(红收据 `a205077`)。
- [x] T4b 修死断言:三条回语句位,取证走三元只在红时才算;
      `dead_assertions.allow` 净减一条,不新增豁免(`df83e6f`)
- [x] T4c 自审 S1(取证在没装 `ss` 的机器上会把自己报成"环境残留",
      等于把产品缺陷说成判据环境脏)⇒ **先造红检后修**:
      新增 r2d(两份都赢)/ r2d-no-ss 两个情景 + 红收据(`e826736`),再修(`06c25f0`)
- [ ] T5 外部评审(impact high ⇒ 2 条不同家族腿),主裁
