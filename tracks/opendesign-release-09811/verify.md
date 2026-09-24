# Verify: opendesign-release-09811

- Date: 2026-09-24

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
runlog -t opendesign-release-09811 -- <判据命令>
```

```
runlog: run-all rc=3 commit=c7aee6f dirty=no final=yes at=2026-09-24T06:40:59Z file=tracks/opendesign-release-09811/evidence/20260924T064059Z-01-run-all.txt
runlog: cloud-e2e rc=0 commit=c7aee6f dirty=yes at=2026-09-24T07:02:52Z file=tracks/opendesign-release-09811/evidence/20260924T070252Z-01-cloud-e2e.txt
```
- run-all rc=3 = 六段全过(python 1507 / node 509 / e2e 41),3 条既有 SKIP 要起 gateway。
- cloud-e2e = run 35965656125(head `c7aee6f`,payload + e2e 两个 job 都 success):**141 OK / 0 FAIL**。
  quiet-start 移交的两条兑现:E2.connecting「后台没好时不挂横幅」、E2.noreload「就绪后整页不重载」;E4 应用内更新(0.98.11 → 替身 0.98.12)
  「重启以更新」→ 向导两下 → 自己重开、版本三方一致;E1r 出货版与被测版逐文件只差更新源。

## Review

- 规格自查:仓外 `/root/aiwork/tasks/opendesign-release-09811-review-my-review.md` [仓外不承重](派发前落盘,暂判 PASS)。
- 腿的花名册:

```
# panel-review 花名册(2026-09-24 15:08:42)task=opendesign-release-09811-review
# PASS = 进程 rc=0,**不等于给了裁决**;off = 这条腿压根没派(不许读成通过)。
# impact-risk=high requested-budget=2 selected-count=2
# selected=subdeepseek(deepseek/subdeepseek-agent),subcursor.grok-4.7-high(xai/subcursor)
# escalation=none
# snapshot=head:79ad4f5
# 日志:/root/aiwork/logs/panel-opendesign-release-09811-20260924-150332.*.log
subdeepseek=PASS(verdict=PASS) subcursor.grok-4.7-high=PASS(verdict=PASS)
```

- 轮次记录:

  | 轮 | 类型 | 派发前 `track preflight` | 日志前缀 | 新增有效阻断 |
  |---|---|---|---|---|
  | 1 | 实质 | rc=3,BLOCK 0 | `/root/aiwork/logs/panel-opendesign-release-09811-20260924-150332` | 0 |

- findings(两家都 PASS,照报项):

  | # | 发现 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | 1 | (两腿)`gh-command` 用 `--generate-notes`,不写中文四点(尤其「Kimi/GLM 模型名未经真 key 验证」) | `desktop/scripts/release-feed.mjs:54` | 本单流程内处理 | 发布后 `gh release edit --notes-file` 换中文说明(同 0.98.10 做法) |
  | 2 | (DeepSeek F3)老手动装法变了:install.ps1 不问端点/模型、合并器拒 `--api-base/--model` | kimi-glm 单的设计(业主「照 ZCode」) | 接受 | 业主走 Electron 安装/更新(`ds_provision` → 合并器无参数),够不到;git-pull/手动装的使用者看 docs/install-windows.md(已同步改) |
  | 3 | (DeepSeek F6)artifact 保留 14 天 | `.github/workflows/electron-e2e.yml` | 本单当天发布 | —— |

- arbitrated verdict (主裁): 发布前评审 PASS —— 两家族同一次 PASS、0 阻断;我核过:云 run 35965656125 141 OK / 0 FAIL、head = 被测 `c7aee6f`、版本三处一致。

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:<开工 commit 时刻 → 归档 commit 时刻>
- 每轮新增有效阻断:<第 1 轮 n / 第 2 轮 n>
- 基础设施等待:<重试次数;observations 里 panel-review 的 duration_ms 求和>
- 交付后返工:<归档后因本单再改过几次;不知道写 unknown>
