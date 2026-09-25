# Verify: opendesign-key-restart

- Date: 2026-09-25

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再按 impact-risk 预算跑 panel-review；只有特殊控制面
> 才显式 `--all` 做全池评审。最后仍由主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [ ] build passes
- [ ] tests pass
- [ ] no secrets / unsafe ops

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,把它打印的收据行原样粘进来:

```
runlog -t opendesign-key-restart -- <判据命令>
```

```
runlog: oracle-red rc=1 commit=9296c63 dirty=yes at=2026-09-25T00:58:38Z file=tracks/opendesign-key-restart/evidence/20260925T005838Z-01-oracle-red.txt
runlog: oracle-d4-red rc=1 commit=8a641cf dirty=yes at=2026-09-25T01:01:50Z file=tracks/opendesign-key-restart/evidence/20260925T010150Z-01-oracle-d4-red.txt
runlog: rewritten-oracles-red-on-old rc=1 commit=e3fd5c5 dirty=yes at=2026-09-25T01:11:36Z file=tracks/opendesign-key-restart/evidence/20260925T011136Z-01-rewritten-oracles-red-on-old.txt
runlog: oracle-d5-red rc=1 commit=748b680 dirty=yes at=2026-09-25T01:13:06Z file=tracks/opendesign-key-restart/evidence/20260925T011306Z-01-oracle-d5-red.txt
runlog: e2e-model-settings-rewrite-red rc=1 commit=d093dda dirty=yes at=2026-09-25T01:16:50Z file=tracks/opendesign-key-restart/evidence/20260925T011650Z-01-e2e-model-settings-rewrite-red.txt
runlog: run-all rc=1 commit=57893fc dirty=no final=yes at=2026-09-25T01:24:05Z file=tracks/opendesign-key-restart/evidence/20260925T012405Z-01-run-all.txt
runlog: mutation-key-restart rc=0 commit=57893fc dirty=yes at=2026-09-25T01:37:38Z file=tracks/opendesign-key-restart/evidence/20260925T013738Z-01-mutation-key-restart.txt
runlog: e2e-per-vendor-rewrite-red-on-old rc=0 commit=57893fc dirty=yes at=2026-09-25T01:39:52Z file=tracks/opendesign-key-restart/evidence/20260925T013952Z-01-e2e-per-vendor-rewrite-red-on-old.txt
runlog: e2e-per-vendor-rewrite-red-on-25011a3 rc=1 commit=57893fc dirty=yes at=2026-09-25T01:40:14Z file=tracks/opendesign-key-restart/evidence/20260925T014014Z-01-e2e-per-vendor-rewrite-red-on-25011a3.txt
runlog: run-all rc=3 commit=c25ffb3 dirty=no final=yes at=2026-09-25T01:41:05Z file=tracks/opendesign-key-restart/evidence/20260925T014105Z-01-run-all.txt
runlog: r1-fix-oracle-red rc=1 commit=ce8f5fa dirty=yes at=2026-09-25T02:36:16Z file=tracks/opendesign-key-restart/evidence/20260925T023616Z-01-r1-fix-oracle-red.txt
runlog: r1-fix-oracle-red-2 rc=1 commit=ce8f5fa dirty=yes at=2026-09-25T02:37:08Z file=tracks/opendesign-key-restart/evidence/20260925T023708Z-01-r1-fix-oracle-red-2.txt
```

```
<粘收据行,逐字节,别改数。**每次提交**都会跟 evidence/ 里的收据逐字节比对(5a);
 **归档时**还要求:最后跑的那一遍必须在这儿、跑红的那几遍一份都不许藏(5b)、
 收据得进 git(5d)。一份收据都没有的话,写一行
 「- 无机器证据:<理由>」认账 —— 沉默不算理由(5c)。>
```

收据说明(机器行之外的人话,不改数):
- `run-all` 57893fc(final)rc=1 两段红:① 死断言闸点名 tests/test_key_live.py 的 `self.fail("网关 30 秒没开 websocket")`
  (只在出错时才跑)⇒ 改成循环外 assertIsNotNone;② e2e per_vendor_keys B2b 仍问「存完那一刻写着要等后台重启」—— 旧契约,已改写。
  两处都是判据,产品代码没动;改完重跑 final:c25ffb3 rc=3(只跳既有三条:两条要真网关的 e2e + 一条 python skip,同 0.98.12 发版单),无红。
- `e2e-per-vendor-rewrite-red-on-old`(rc=0)**名字是错的**:`runlog --repo` 在主仓里跑,那一遍其实是新 e2e 对新代码(绿),
  不是对旧实现;对旧实现的真红检是下一行 `…-red-on-25011a3`(用绝对路径跑旧提交临时检出里的那份,B2b/B6/B5 三条红)。
- 红检 `mutation-key-restart` 15/15 咬住。
- `r1-fix-oracle-red`:d6 红,但 e2e R1-1 **假绿** —— 禁用那一下的提示本来带「未启用」,检查读到旧提示就过了;
  改成先等「已保存」开头那句再判,`r1-fix-oracle-red-2` 里 R1-1 红在正确的那句上。
- 云 Windows QA 执行 probe-5(run 36081788020,修好的包):live / fresh 两组全 ok,时间线 evidence/20260925-windows-probe-5.txt。

## Review

- 规格自查(读任何 panel 输出之前,2026-09-25 09:5x,原文在 /root/aiwork/tasks/opendesign-key-restart-r1-my-review.md):
  用户成功条件 = 聊天连着存 key 不断、下一句用上;全新装机第一把 key 网关被起起来;Windows 不再卡。前提 P0~P3 都有证据(design.md);
  没有能推翻方向的未知。自审 PASS,带 3 条低风险已知项(K-a/K-b/K-c,见下表)。
- 反锚定记账:第 1 轮派发时 verify.md 只有收据行与「收据说明」(判据怎么红、怎么改),没有自审结论与处置;工具照例报 anchor leak 指的是它。
- 腿的花名册(第 1 轮):
  `submimo=FAIL(rc=124) subdeepseek=PASS(verdict=PASS)`
- 轮次记录:

  | 轮 | 类型(实质 / 重试) | 派发前 `track preflight` | 日志前缀 | 新增有效阻断 |
  |---|---|---|---|---|
  | 1 | 实质(MiMo 35 分钟超时 rc=124、无结论 = 基础设施失败;DeepSeek 有效) | rc=3,BLOCK 0(只待评审) | /root/aiwork/logs/panel-keyrestart-r1-20260925-095516 | 0(1 条 LOW 必须修) |
  | 2 | 实质(核验修复 + 补足两家覆盖:DeepSeek + Grok) | 待填 | 待填 | 待填 |

- QA(测试员,非评审、不计轮):QA-设计 DeepSeek + Grok(evidence/20260925-qa-design-*.md);QA-执行 两家判卷(evidence/20260925-qa-exec-*.md,
  对账:DeepSeek 9 通过 / 0 不通过 / 14 没执行到;Grok 缺陷无)+ 主裁补录真界面 14 步(evidence/qa-exec/tour.md,真管家+真网关+真工作台+真 chromium)。
- findings(先处置、后动手;一轮一份修复清单):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | R1-1 | (第 1 轮 DeepSeek LOW)未启用的那家存 key,提示说「右下角就能换」,菜单里却藏着它 | bin/ds_credential.py:511(菜单只列启用的);ModelSettings 保存键不看 enabled;e2e R1-1 红收据 …-r1-fix-oracle-red-2 | 必须修 | 假话提示,修法小;82c252a 修,d6 / e2e R1-1 / 红检 M16 |
  | Q-1 | (QA 执行录像第 9 步)模型调用出错(key 填错 / 欠费 / 超时 / 限流)时聊天页**什么都不显示**:网关发了整句错误消息(event=message,无 kind),web/src/chat/transcript.ts:243 只认 progress/tool_hint,整句丢掉 | evidence/qa-exec/09.jpg;evidence/qa-exec/wrongkey-repro.py 真网关复现(stream_end 后一条 message「Error: Invalid API key」) | 延期(发版后另开单) | **不是本单引入**(0.98.12 及以前同样);本单只让 key 生效更快,没碰聊天显示。在业主那边长成:填错 key 或额度用完后发消息「没反应」,以为又坏了。发 0.98.13 后紧接着开单修(修法:本轮没有流式正文时把这条 message 显示出来,并说人话) |
  | Q-2 | (QA DeepSeek ①)第一次存 key 后若网关起不来,提示叫他「退出再打开」 | modelSettings.ts requested 那句 | 驳回 | 网关真起不来时,聊天页「立即重试」只重连、救不了;外壳同时会弹「没能自己启动…请退出再打开」—— 那就是对的出路 |
  | Q-3 | (QA DeepSeek ②)保存本身失败(写盘失败)时说什么 | — | 驳回 | 要人为造 IO 故障(锤子砸墙);现有路径把后端那句人话原样显示,未改 |
  | K-a | (自审)额外厂商 key 文件写成、配置写不进 ⇒ 回包 live 但这家没进菜单 | 自审文件 | 延期 | 要配置目录不可写而 keys 可写(手改权限);下次开软件 build_env 会补上 |
  | K-b | (自审)网关没在跑时连存两次,第二次等不到锁应答 ⇒ 「请手动重启」 | 自审文件 | 延期 | 老版本重启同形;本单后只在全新装机 / 网关挂了才走 |
  | K-c | (自审)钩子每句读十来次小配置 | — | 延期 | 毫秒级,不优化 |

- arbitrated verdict (主裁): 待第 2 轮

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:<开工 commit 时刻 → 归档 commit 时刻>
- 每轮新增有效阻断:<第 1 轮 n / 第 2 轮 n>
- 基础设施等待:<重试次数;observations 里 panel-review 的 duration_ms 求和>
- 交付后返工:<归档后因本单再改过几次;不知道写 unknown>
