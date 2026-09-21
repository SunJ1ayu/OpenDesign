# Verify: opendesign-per-vendor-keys

- Date: 2026-09-21

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

## Mechanical checks

- [x] build passes(`npm run build` 含类型检查;dist 随提交)
- [ ] tests pass —— 最终一遍待第 2 轮修复后 `--final` 总跑
- [x] no secrets / unsafe ops(判据全用假 key、本机假服务器;活网关判据代理指向死端口)

**机器打印的**收据(逐字节):

```
runlog: red-py rc=1 commit=b01eb60 dirty=yes at=2026-09-21T12:35:04Z file=tracks/opendesign-per-vendor-keys/evidence/20260921T123504Z-01-red-py.txt
runlog: red-ui rc=1 commit=b01eb60 dirty=yes at=2026-09-21T12:35:06Z file=tracks/opendesign-per-vendor-keys/evidence/20260921T123506Z-01-red-ui.txt
runlog: red-e2e rc=1 commit=b01eb60 dirty=yes at=2026-09-21T12:35:06Z file=tracks/opendesign-per-vendor-keys/evidence/20260921T123506Z-02-red-e2e.txt
runlog: mutations rc=0 commit=83e2a3b dirty=yes at=2026-09-21T12:52:58Z file=tracks/opendesign-per-vendor-keys/evidence/20260921T125258Z-01-mutations.txt
```

- 三份 red 是**先红**收据(实现之前,判据单独提交于 `402d5fb`):红在缺 API / 外壳未接线 / 卡片无每家一行 —— 预期内。
- mutations:17 个定点变异 15 个咬住;M10、M10b 单拆是**等价变异**(prepare_gateway 早退与 ③ 的 `and wanted` 互为双保险,
  单拆任一行为不变),两道合拆 M10d 被 v12b 咬住。

## Review

- 规格自查(读 panel 输出之前,落盘于仓外 `/root/aiwork/tasks/opendesign-per-vendor-keys-review-my-review.md` [仓外不承重]):
  PASS;S23 已修(`789bd69`);S9 降级边界、S2 孤儿 key、S7 重启窗口记账;点名最不放心三处(live 判定、save 分支、⑤/④ 先后)。
  回看 design 用户成功条件:「不重粘 / 换回来照常 / 界面与真实一致 / 单家不比今天差」—— 前三条有 v1/v15/l1/e2e,第四条有 v3/v12/v12b/v13。
  第 1 轮外审暴露的 Grok-3 属「单家(无外壳)不比今天差」这一条的界面面,我自查漏了。
- 腿的花名册(第 1 轮,`/root/aiwork/logs/panel-pvk-r1.roster` 原样):
  `submimo=SKIP(health:cooldown:INCOMPLETE) subdeepseek=SKIP(health:cooldown:FAIL) subglm=SKIP(health:dead:auth:3) subkimi=PASS(verdict=BLOCK) subgemini=SKIP(health:dead:FAIL:6) subgrok=SKIP(health:dead:FAIL:3) subcursor=PASS(verdict=PASS)`
  > 反锚定警告点名的 `verify.md` 在派发时是**空白模板**(未含任何自审内容),记账不算泄漏。
  > subcursor 与方案挑战腿同为 Cursor/Grok —— 同一家族审了方案又审实现,独立性弱于换家族;健康池当时只剩这两家。
- 轮次记录:

  | 轮 | 类型 | 派发前 `track preflight` | 日志前缀 | 新增有效阻断 |
  |---|---|---|---|---|
  | 1 | 实质 | rc=3,BLOCK 0(PENDING 2:decision / receipts) | `/root/aiwork/logs/panel-pvk-r1` | 1(K1,测试侧竞态致判据红;另 5 条 MEDIUM/LOW 见下) |
  | 2 | 实质(核验修复) | rc=3,BLOCK 0(PENDING 2) | `/root/aiwork/logs/panel-pvk-r2` | 0(三腿 PASS;残余全 LOW,见第 2 轮表) |

- findings(第 1 轮;K = subkimi,G = subcursor):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | K1 | e2e C1:点开菜单先用旧 state 渲染一组,打开时的 fetch 落地后才变两组;判据读在中间 ⇒ 时序性红(Kimi 环境 2/2 红,我方 2/2 绿) | `tests/e2e/per_vendor_keys.e2e.mjs` groupsInMenu 一次读;`web/src/chat/ChatPage.tsx` 打开即渲染 `models` 再 `loadModels()` | 必须修 | 判据的读法有竞态 = 判据本身不可信;修成等打开那次 `/api/llm/models` 回包落地再读(等真实状态,不是放宽) |
  | G3 | 没外壳(git-pull/Linux):卡片照样显示每家一行、提示「粘贴这一家的 key」,而保存按单把语义**覆盖**另一家 | `bin/ds_web.py` `_llm_credential_get` 无条件透出 `vendors`;`LlmKeyCard.tsx` `vendors.length > 1` 即显示 | 必须修 | 违反 proposal「单家不比今天差」的界面面;修法:没外壳时接口不给 `vendors`,界面退回原样 |
  | K2 | 早先的「想换过去」标记盖掉后来「存主槽那家 key」的结果(今天是后存者赢) | `save()` 主槽路径不清标记;`_synced_config` ④ 兑现旧标记 | 必须修 | 小改、可测;行为回到「最后一次保存为准」 |
  | K3 | 存第二家时先写 key 后写标记;标记写失败 ⇒ key 已落盘、报错、不重启,下次起网关悄悄激活 | `save()` multi 分支写序 | 必须修 | 改成先标记后 key,key 失败撤标记 |
  | G4 | w10 只查「写了 extra_keys=」不查值来自 prepare_gateway;l1 手拼 env 不经 service_envs | `tests/test_ds_shell_wiring.py` w10;`tests/test_per_vendor_live.py` setUp | 必须修 | 判据加强(我自己的判据写窄了);与 v4 的夹具修正同一类 |
  | G5 | 卡片存完第二家只刷新一次,之后一直显示「等重启」直到重开 | `LlmKeyCard.tsx` save 后单次 `fetchKeyStatus` | 必须修 | 待重启期间定时刷新(有上限),显示与真实一致 |
  | G1 | 外壳 prepare_gateway 写完配置到旧网关被杀之间,菜单已列 DeepSeek、旧网关无变量 | `ds_shell.py` restart_gateway:build_env → `sup.restart`(先 terminate,最多等 4s) | 驳回(降 LOW,接受) | 窗口 = 写配置到 terminate 旧进程,毫秒到 ≤4s;此刻业主人在卡片里刚点保存,发不出消息;design S7 已记。结构性消除要拆 Supervisor.restart 加钩子,动 Windows 独有层,风险大于收益 |
  | G2 | 换已活的第二家的 key:卡片立刻显示新末四位「在用」,网关到重启完成前仍是旧 key | `_vendor_rows` live 判定 | 驳回(接受) | 与今天换主槽 key 完全同形(hint 立刻变、同时请求重启、提示说正在重启);不比今天差 |
  | K4 | `restart_gateway` 的 `if not k: return` 经 UI 到不了 | `ds_shell.py` | 驳回 | 保留的防御,无害 |
  | K5 | verify.md 空、无绿收据 | — | 必须修(流程) | 本文件;最终 `--final` 总跑收据归档前补 |
  | S0 | (自查)`.github/workflows/windows-package-probe.yml` 四处默认值未随 0.98.9 同步 | `installer/RELEASE.md` 第 1 步 | 必须修 | 发版清单要求;与本轮修复同一提交,由第 2 轮核验 |

- 腿的花名册(第 2 轮,`/root/aiwork/logs/panel-pvk-r2.roster` 原样):
  `submimo=PASS(verdict=UNKNOWN) subdeepseek=PASS(verdict=PASS) subglm=SKIP(health:dead:auth:3) subkimi=SKIP(rotation) subgemini=SKIP(health:dead:FAIL:6) subgrok=SKIP(health:dead:FAIL:3) subcursor=PASS(verdict=PASS)`
  > submimo 的 UNKNOWN:它的结论写成「## 结论 / PASS」两行,裁决行匹配不上;开日志核过原文是 PASS,
  > 但**机器不认的就不算覆盖**,控制器随即补派 subdeepseek(PASS)。submimo 环境缺 nanobot,
  > 依赖它的 4 条判据在它那边 ERROR(环境问题,它自己也这么写),不影响它对修复的逐条核验。
- findings(第 2 轮;M = submimo,D = subdeepseek,C = subcursor)—— 第 1 轮「必须修」7 项三腿逐条核为已修;驳回 3 项三腿均认为理由站得住:

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | D2 | 自动重启没成时标记还在;业主**亲手**在菜单点了 MiMo,之后一重启又被拽回 DeepSeek(K2 同类,只修了主槽保存那条路) | `select_model` 不清标记;复现 v18 红(`r2-red-py`) | 必须修(`6258c99`) | select_model(home=) 成功后清标记,ds_web 传 home |
  | C1 | 无外壳时保存接口的回包仍带完整 vendors(GET 已清) | `ds_web._llm_credential_post` | 必须修(`6258c99`) | 与 GET 同规矩;防以后有人拿回包渲染时 G3 复发 |
  | D1/C2 | 卡片轮询上限 120s,慢机重启 >2 分钟后停在「等重启」 | `LlmKeyCard.tsx` | 必须修(`6258c99`) | 放到约 10 分钟(冷启动见过近 4 分钟) |
  | D3/M | e2e「等两帧」是启发式,回包头到 ≠ 页面画好 | e2e groupsInMenu | 必须修(`63ca266`) | 改成等「菜单组数 = 这次回包的组数」 |
  | D4 | B7 若存完那次刷新落在假外壳 1.5s 之后,不靠轮询也绿 | e2e B7 | 必须修(`63ca266`) | 加 B2b:先钉住存完那一刻在「等重启」 |
  | 自查 | 死断言闸:l1 两处只在出错时才跑的 `self.fail` | run-all-r2 收据 py-full 段 | 必须修(`63ca266`) | 改成每次都执行的 assertTrue |
  | C3 | w10 仍抓不到「接住 prepare_gateway 的返回值后又改成 {}」 | `test_ds_shell_wiring.py` w10 | 驳回(接受) | 静态闸的天花板;当前源码不是那样,真正的接线由 l1(经 service_envs)与真机兜 |
  | M2 | 删标记失败(权限)被吞 ⇒ 残留标记下次重启兑现 | `save` 主槽路径 / `select_model` | 驳回(接受) | 需要 keys/ 目录权限异常;与 key.txt 写不进去同一类环境故障,不为它加状态 |

- arbitrated verdict (主裁): 待最终总跑与覆盖轮。

## Accepted deviations

- G1 / G2 见上表。

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:`b01eb60`(2026-09-21 20:30)→ 归档 commit(待填)
- 每轮新增有效阻断:第 1 轮 1(K1)
- 基础设施等待:第 1 轮无重试;duration 见 observations
- 交付后返工:unknown
