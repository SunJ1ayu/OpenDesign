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
  | — | 附加(不绑 track,standard):MiMo 单腿,MIMO_CLI_TIMEOUT=2100,业主「mimo也可以试试」;17.5 分钟交卷 BLOCK;**评审期间 HEAD 81fbe19→901f0c5**(我在它审的时候提交了窄窗修复) | 同上 | `/root/aiwork/logs/panel-opendesign-instant-ui-review-mimo-20260923-1351b` | 1(F1) |

  - 反锚定记账:第 1 次派发时 verify.md 已含收据行 + 一句「C6 抓到 OdShell 没登记 backend」,不含结论/疑点;影响小。
  - Grok 超时:15 分钟只读代码未落一字(stream 仅 266 字);按基础设施失败计,重派时 `CURSOR_TIMEOUT=1800`。

- findings:

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | 1 | (Kimi)E2.connecting 在窗口栏出现那一刻就查横幅,横幅要等 IPC 回包 + 二次渲染 ⇒ 慢机偶发假红 | `e2-drive.mjs` bannerAtUi;`App.tsx` backend effect | 延期 | 云上跑过一次为真;产品侧不是缺陷(横幅晚几十毫秒出现)。下一个使用者:某次 CI 假红时,按 design.md「红了先看数字」处理,别放宽判读 |
  | 2 | (Kimi)有 key 时后台长挂,各页只转圈的观感 CI 量不到 | design.md oracle 小节 | 延期 → T5 真机清单 | 结构上就绪前请求不失败;观感只有业主有 key 的机器答得了 |
  | 3 | (Kimi)localStorage 一次性丢失,含 `ds-chat-password` | `web/src/chat/connection.ts:10,81`;`bin/ds_web.py _proxy` 缺 Authorization 时服务端自注入口令 | 驳回(对口令)/ 已认账(其余三项) | 口令丢了也不用重输:ds-web 代理自己补;对话映射/图库列数/侧栏折叠丢一次,发版说明写明 |
  | 4 | (主裁 S1)`corsEnabled: true` 非必需 | `desktop/main.js` registerSchemesAsPrivileged | 驳回 | Kimi 指出它是更严的取向(跨源读 app:// 要走 CORS);本应用内也没有别的源的页面 |

- MiMo 附加意见逐条核实(`…-mimo-20260923-1351b.submimo.log` [仓外不承重]):

  | # | 发现 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | M1 | 管家在 ready 前硬崩 ⇒ 只弹「请从托盘退出」不退,窗口永远「正在启动后台」 | `controller.js hostExit` 只 showError;旧版同样挂在 loading 页(`384a7ef~1`)—— 旧病,但落在本单承诺④里 | **必须修** | 管家一死整棵后台没了,前后都没法用 ⇒ 意外退出一律 giveUp(减一个分支,不加特例)。判据 bs4~6 `312044b` 先红 |
  | M2 | 去掉 Origin 后 ds-web 同站检查在代理路径上不再参与 | `_same_site_ok` 防的是「别的网站让浏览器带副作用请求」;app:// 代理只有本窗口的页面进得来(冒名主机 404、外链交系统浏览器、window.open 全拒) | 驳回 | 实际能到达后台的来源没变多;Kimi 同判 |
  | M3 | `corsEnabled: true` 多给特权 | Electron 文档:corsEnabled = 允许该协议被跨源读取;页面全同源用不着。**Kimi 说「更严」是说反了**,MiMo 对 | **必须修** | 最小特权;判据 s1b 先红;删后由云 E2 证明界面照常(模块脚本同源不需要它) |
  | M4 | 就绪后后台死掉 ⇒ 502、不自愈 | `backend-died` 弹框、页面 502;旧版同样(旧页也是 ds-web 发的) | 延期 | 非本单引入;业主那边:后台中途崩会看到提示框 + 页面红字,按提示重开即可。若之后真硌到人再开单做「自动重连」 |
  | M5 | 端口只认一次,ds-web 换端口则永久 502 | ds-web 端口一次运行内不变,重启网关不动它(`ds_shell.py restart_gateway`) | 驳回 | 契约如此;将来改 ds-web 重启方式的人要同时改这里 —— 已写在 `appProtocol.js` 头注释 |
  | M6 | attach 后 stdin 不可写时丢命令 | 那时管家已死,丢命令无后果(与旧版一致) | 驳回 | |
  | M7 | 横幅「马上就好」在数分钟冷启动里是假话 | `ds_shell.py` 网关 ready_timeout=300 | **必须修** | 文案改成「有时要一两分钟」;判据 fb3 |
  | M11 | 「本地总跑全绿」措辞 vs 收据 rc=3(3 条要网关的没跑) | 收据原文 | 接受 | 以后写「各段全绿、3 条要网关的没跑」 |

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
