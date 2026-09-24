# Verify: opendesign-release-09810

- Date: 2026-09-23

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再按 impact-risk 预算跑 panel-review；只有特殊控制面
> 才显式 `--all` 做全池评审。最后仍由主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] build passes(云 run 35830315041 出货包)
- [x] tests pass(run-all rc=3 仅既有 SKIP;云 FAIL 0)
- [x] no secrets / unsafe ops

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,把它打印的收据行原样粘进来:

```
runlog -t opendesign-release-09810 -- <判据命令>
```

```
runlog: python rc=1 commit=485b83e dirty=yes at=2026-09-23T07:09:03Z file=tracks/opendesign-release-09810/evidence/20260923T070903Z-01-python.txt
runlog: python rc=1 commit=485b83e dirty=yes at=2026-09-23T07:09:08Z file=tracks/opendesign-release-09810/evidence/20260923T070908Z-01-python.txt
runlog: run-all rc=3 commit=e67c726 dirty=no final=yes at=2026-09-23T07:10:26Z file=tracks/opendesign-release-09810/evidence/20260923T071026Z-01-run-all.txt
runlog: bash rc=0 commit=e67c726 dirty=yes at=2026-09-23T07:33:25Z file=tracks/opendesign-release-09810/evidence/20260923T073325Z-01-bash.txt
runlog: prod-smoke-10 rc=0 commit=83d15f9 dirty=no at=2026-09-23T07:48:23Z file=tracks/opendesign-release-09810/evidence/20260923T074823Z-01-prod-smoke-10.txt
```

- 说明:07:09:03 那份 rc=1 是我把测试类名写错(C7Shell,报 errors=1,量具错);07:09:08 才是 C7d 的真红;run-all rc=3 = 各段全绿、3 条要网关的没跑;cloud 35830315041 FAIL 0;prod-smoke-10 = T5 发布后从 GitHub 取回逐字节比对 + 旧 blockmap(v0.98.9)在。

## Review

- 规格自查:仓外 `/root/aiwork/tasks/opendesign-release-09810-review-my-review.md` [仓外不承重](派发前落盘,暂判 PASS)。
- 腿的花名册:

```
# panel-review 花名册(2026-09-23 15:46:00)task=opendesign-release-09810-review
# PASS = 进程 rc=0,**不等于给了裁决**;off = 这条腿压根没派(不许读成通过)。
# impact-risk=high requested-budget=2 selected-count=2
# selected=subkimi(moonshot/subkimi),subcursor.grok-4.7-high(xai/subcursor)
# escalation=none
# snapshot=head:bd139c2
# 日志:/root/aiwork/logs/panel-opendesign-release-09810-20260923-1533.*.log
subkimi=PASS(verdict=PASS) subcursor.grok-4.7-high=PASS(verdict=PASS)
```

- 轮次记录:

  | 轮 | 类型 | 派发前 `track preflight` | 日志前缀 | 新增有效阻断 |
  |---|---|---|---|---|
  | 1 | 实质(CURSOR_TIMEOUT=1800) | rc=3,BLOCK 0 | `/root/aiwork/logs/panel-opendesign-release-09810-20260923-1533` | 0 |

- findings:

  | # | 发现 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | 1 | (两腿)`gh-command` 用 `--generate-notes`,不会写「三项偏好重置一次」 | `desktop/scripts/release-feed.mjs:54` | 本单流程内处理 | 发布后 `gh release edit --notes-file` 换成中文说明(T5 步骤);不动工具 |
  | 2 | (Kimi)云 E4 测的是 0.98.10→0.98.11 替身,生产第一跳要业主真机 | 验收边界已写 | 接受 | T6 真机回显兜底 |

- arbitrated verdict (主裁): 发布前评审 PASS —— 两家族同一次 PASS、0 阻断;我核过:云 run 35830315041 FAIL 0、出货三样同一次运行、版本三处一致。整体 outcome 等 T6 业主真机。
- **T6(09-24)业主真机**:业主原话「是软件自己提示的」—— 0.98.9 经生产源**应用内自动更新**到 0.98.10(Electron 更新器生产第一跳走通)。
  业主 09-23 晚用 0.98.10 时报了「头上显示正在启动后台还有一段话」⇒ 冷启动第一眼工作台 + 有 key 横幅在,都看到了(横幅随后在 quiet-start-icons 删掉,0.98.11 发)。
  「各页只转圈不报错」「窗口拖窄首页无横向滚动」业主没单独回报 ⇒ 记接受偏差,并入 0.98.11 的真机清单。
- **事实上已完成**(发布前评审 PASS + 生产源 smoke 全 OK + 业主真机自动更新回显),但**不能按 PASS 归档**:评审绑定的是仓库级交付,
  发布后仓库又走了 kimi-glm / quiet-start 等单 ⇒ `observation.review_delivery` BLOCK(要求对已发出的版本重审,无意义)。decision 保持 null,单子留着。
  教训(给 0.98.11 发版单):**发布 + smoke 当天就归档**,业主真机回显事后补进已归档的 verify.md(收尾记录允许原地补写)。

## Accepted deviations

- 真机清单里「各页只转圈不报错」「窄窗首页无横向滚动」业主未单独回报;两项云 e2e 已测(E2.noreload / narrow),并入 0.98.11 发版单的真机清单。

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:<开工 commit 时刻 → 归档 commit 时刻>
- 每轮新增有效阻断:<第 1 轮 n / 第 2 轮 n>
- 基础设施等待:<重试次数;observations 里 panel-review 的 duration_ms 求和>
- 交付后返工:<归档后因本单再改过几次;不知道写 unknown>
