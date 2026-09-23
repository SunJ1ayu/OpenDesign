# Verify: opendesign-instant-ui

- Date: 2026-09-23

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
runlog -t opendesign-instant-ui -- <判据命令>
```

```
runlog: node rc=1 commit=f32b817 dirty=yes at=2026-09-23T04:57:30Z file=tracks/opendesign-instant-ui/evidence/20260923T045730Z-01-node.txt
runlog: run-all rc=1 commit=384a7ef dirty=yes final=yes at=2026-09-23T04:59:58Z file=tracks/opendesign-instant-ui/evidence/20260923T045958Z-01-run-all.txt
runlog: run-all rc=3 commit=7452f32 dirty=no final=yes at=2026-09-23T05:13:11Z file=tracks/opendesign-instant-ui/evidence/20260923T051311Z-01-run-all.txt
runlog: bash rc=0 commit=7452f32 dirty=yes at=2026-09-23T05:35:19Z file=tracks/opendesign-instant-ui/evidence/20260923T053519Z-01-bash.txt
```

- 说明:node rc=1 = 判据先行红跑(29 条,实现前);第一次 run-all rc=1 = C6 抓到 OdShell 类型没登记 backend(真漏,已补)+ dist 未提交;
  第二次 run-all rc=3 = 全绿 + 3 条老的没跑(要网关);cloud = run 35821491722 FAIL 0。

## Review

- 规格自查:派评审前落盘于仓外 `/root/aiwork/tasks/opendesign-instant-ui-review-my-review.md` [仓外不承重](暂判 PASS;疑点 S1 corsEnabled、localStorage 一次性丢失、有 key 长挂起未测)。
- 腿的花名册(第 1 次派发):

```
# panel-review 花名册(2026-09-23 13:50:51)task=opendesign-instant-ui-review
# PASS = 进程 rc=0,**不等于给了裁决**;off = 这条腿压根没派(不许读成通过)。
# impact-risk=high requested-budget=2 selected-count=2
# selected=subkimi(moonshot/subkimi),subcursor.grok-4.7-high(xai/subcursor)
# escalation=none
# snapshot=head:81fbe19
# 日志:/root/aiwork/logs/panel-opendesign-instant-ui-review-20260923-1335.*.log
subkimi=PASS(verdict=PASS) subcursor.grok-4.7-high=FAIL(rc=124)
```

- 轮次记录:

  | 轮 | 类型(实质 / 重试) | 派发前 `track preflight` | 日志前缀 | 新增有效阻断 |
  |---|---|---|---|---|
  | 1 | 实质(但 Grok 腿 rc=124 超时,**不构成两家族覆盖**) | rc=3,BLOCK 0 | `/root/aiwork/logs/panel-opendesign-instant-ui-review-20260923-1335` | 0 |
  | — | 附加(不绑 track,standard):MiMo 单腿,MIMO_CLI_TIMEOUT=2100,业主「mimo也可以试试」 | 同上 | `/root/aiwork/logs/panel-opendesign-instant-ui-review-mimo-20260923-1351b` | 待交卷 |

  - 反锚定记账:第 1 次派发时 verify.md 已含收据行 + 一句「C6 抓到 OdShell 没登记 backend」,不含结论/疑点;影响小。
  - Grok 超时:15 分钟只读代码未落一字(stream 仅 266 字);按基础设施失败计,重派时 `CURSOR_TIMEOUT=1800`。

- findings:

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | 1 | (Kimi)E2.connecting 在窗口栏出现那一刻就查横幅,横幅要等 IPC 回包 + 二次渲染 ⇒ 慢机偶发假红 | `e2-drive.mjs` bannerAtUi;`App.tsx` backend effect | 延期 | 云上跑过一次为真;产品侧不是缺陷(横幅晚几十毫秒出现)。下一个使用者:某次 CI 假红时,按 design.md「红了先看数字」处理,别放宽判读 |
  | 2 | (Kimi)有 key 时后台长挂,各页只转圈的观感 CI 量不到 | design.md oracle 小节 | 延期 → T5 真机清单 | 结构上就绪前请求不失败;观感只有业主有 key 的机器答得了 |
  | 3 | (Kimi)localStorage 一次性丢失,含 `ds-chat-password` | `web/src/chat/connection.ts:10,81`;`bin/ds_web.py _proxy` 缺 Authorization 时服务端自注入口令 | 驳回(对口令)/ 已认账(其余三项) | 口令丢了也不用重输:ds-web 代理自己补;对话映射/图库列数/侧栏折叠丢一次,发版说明写明 |
  | 4 | (主裁 S1)`corsEnabled: true` 非必需 | `desktop/main.js` registerSchemesAsPrivileged | 驳回 | Kimi 指出它是更严的取向(跨源读 app:// 要走 CORS);本应用内也没有别的源的页面 |

- 业主追加(同单):「顺手修」窄窗横向滚动条(0.98.9 起就有,`.workspace { min-width:1260px }` 加在所有页)。
  判据 `tests/e2e/narrow_window.e2e.mjs` 先红;第一版量具量 `documentElement` 假绿过四条,改量 `.workspace` 实宽后正确红(内容 1260 / 窗口 1024)。

- arbitrated verdict (主裁): <待第 2 次派发(两家族同一次成功)>

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:<开工 commit 时刻 → 归档 commit 时刻>
- 每轮新增有效阻断:<第 1 轮 n / 第 2 轮 n>
- 基础设施等待:<重试次数;observations 里 panel-review 的 duration_ms 求和>
- 交付后返工:<归档后因本单再改过几次;不知道写 unknown>
