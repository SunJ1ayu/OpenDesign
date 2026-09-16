# Tasks: opendesign-e2e-guard-followup

- base-ref: c567a873fe6204f42984e2d9977414f3434c2648

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

- [x] 判据先行:`tests/test_e2e_harness_guard.mjs` 重写 bt4、新增 bt5 / ne11 / ne12;旧实现下 bt4 bt5 ne11 红,单独 commit
- [x] ne12 变异收据:删掉 python 回环块 ⇒ ne12 红(代码已存在,判据当场绿,红靠变异证明)
- [x] 实现 ①:外层 ⑥ 段读点名簿挂进汇总;内层尊重外面给的 `E2E_BROWSER_NOTES`
- [x] 实现 ②:helpers.mjs 回环判定改读 errno
- [x] README:无出口守卫一节
- [x] 红检(退回实现 ⇒ bt4 bt5 ne11 红)
- [x] e2e 总跑(40 PASS 不变)
- [x] 外层真跑 + 临时注入一条会泄漏的 e2e(一次性,不进仓)⇒ 汇总行带名字和次数
- [x] 中途发现 ⑤:判据先行 bt6 + 夹具目录改短(断言不动);实现 launchBrowser 起之前算 socket 路径;红检
- [x] 外层真跑(最终 HEAD,干净)
- [x] panel-review(impact high,上限 2 轮)→ 仲裁
