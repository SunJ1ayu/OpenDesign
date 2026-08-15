# Verify: opendesign-key-onboarding

- Date: 2026-08-15
- Verdict: <PASS | BLOCK | NEEDS_MORE_INFO>

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [ ] build passes
- [ ] tests pass
- [ ] no secrets / unsafe ops

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,把它打印的收据行原样粘进来:

```
runlog -t opendesign-key-onboarding -- <判据命令>
```

```
runlog: regression-http rc=1 commit=5acf226 dirty=no at=2026-08-15T15:03:05Z file=tracks/opendesign-key-onboarding/evidence/20260815T150305Z-01-regression-http.txt
runlog: regression-http-v2 rc=3 commit=89ca1e7 dirty=yes at=2026-08-15T15:26:02Z file=tracks/opendesign-key-onboarding/evidence/20260815T152602Z-01-regression-http-v2.txt
runlog: bash rc=1 commit=d05c37f dirty=no at=2026-08-15T16:28:33Z file=tracks/opendesign-key-onboarding/evidence/20260815T162833Z-01-bash.txt
runlog: bash rc=0 commit=d05c37f dirty=yes at=2026-08-15T16:31:47Z file=tracks/opendesign-key-onboarding/evidence/20260815T163147Z-01-bash.txt
runlog: bash rc=0 commit=1ff644a dirty=no at=2026-08-15T16:34:46Z file=tracks/opendesign-key-onboarding/evidence/20260815T163446Z-01-bash.txt
```

**T3(重启链路)**:
```
runlog: bash rc=1 commit=a044263 dirty=yes at=2026-08-15T17:16:41Z file=tracks/opendesign-key-onboarding/evidence/20260815T171641Z-01-bash.txt
runlog: bash rc=3 commit=0adc038 dirty=yes at=2026-08-15T17:28:01Z file=tracks/opendesign-key-onboarding/evidence/20260815T172801Z-01-bash.txt
```
- 红检 15 条定点变异 **15 咬住 / 0 漏网**(收据 `20260815T170745Z`)。
  首跑 13/2,两条"漏网"**都是等价变异**:M4 改的循环条件在同包到达时没有行为差异,
  M13 锚在 `create_connection` 的 timeout 上而真正管读超时的是 `recv_line` 的 deadline。
  M4 照出真洞 ⇒ 补 b14(动词晚到一个包)。
- `rc=1` 那遍是全量回归打红 a7 / g2 两条既有判据(T3 契约变更的连带,不是新 bug)。
  **g2 那条修得最值**:它原来把 apiKey 写死成假 key,等于绕开真机唯一走的那条路。
- `rc=3` 全绿(node 350 / python 1219 / MCP 契约 / dist 新鲜度 / e2e 34 PASS 0 FAIL),
  仍有 **2 条 e2e SKIP** ⇒ T5 收口必须带 `--with-gateway` 重跑。**SKIP 不是绿。**

**红检(接口层,前三份)**——断线砍掉的一步,补跑:

- `rc=1` 首跑 **7 咬住 / 3 漏网**,三条分两型:M1/M2 是**变异等价**(两道来源检查各自
  都挡得住,拆一道另一道接住);M10 是**真洞**(h2 只问"是那两个值之一",
  规格里"不假装成功"没进判据)。⇒ 补 i6 / i7 / h5 三条。
- 中间那份 `rc=0 dirty=yes` **不作数**:跑的是还没进 git 的脚本,复现不了。
  留着是因为 5b(跑过的不藏),**收口以最后那份为准**。
- `rc=0 commit=1ff644a dirty=no` **10 咬住 / 0 漏网** —— 这份才是收据。
  其中 M2 那次"漏网"最后查明是**红检脚本自己打错了位置**(锚点在两个函数里各有一处),
  已改成"锚点不唯一直接拒";加上这道闸之后其余 9 条一条没被拒 ⇒ 它们原先的绿是真的。

- 第一遍 `rc=1` **是真红**,不藏(5b):python 段红在 `test_ds_web_proxy` —— 代理注入
  Authorization 之后它不再是「纯管道」,是**判据题面旧了**,不是实现坏了。
  已在 `89ca1e7` 把断言改强(而不是删掉),并给那份判据加隔离。
- 第二遍 `rc=3` **也不算通过**:node 350 / python 1197 / MCP 契约 / dist 新鲜度 /
  e2e 34 PASS 0 FAIL 全绿,但**有 2 条 e2e 是 SKIP**(没带 `--with-gateway`)。
  ⇒ T5 收口时必须带开关重跑一遍,把这 2 条变成真跑。**SKIP 不是绿。**
- `dirty=yes` = 当时 evidence/ 两份收据还没进 git(本次提交补上,5d)。

## Review

- lane: **full**。命中 auth/凭据(业主的 LLM key 经我们的手落盘)+ **拿掉了一道现存的
  认证边界**(前端不再手输口令,改由 ds-web 代签)。S1d 规格里就写死"必须单独 full 审"。
  > **碰了新写口 / 权限 / auth / 钱 / 数据一致性 → full,针孔再薄也不打折**(硬规矩,别在这降档)。
  > fast = 主+1,中等风险;self = 主自审(闸③ + 截图 + 全量回归),
  > 限纯前端/纯观感、后端一字未动、只新增已过审针孔的调用方。
- 派给: **后端凭据面主 agent 自己写;前端模态框折完后端契约再评估(倾向 codex 腿)**。
  逐档问过:
  - **codex 腿**:这单的后端是**凭据面**——"哪里算漏"的判断成本远高于打字成本,
    而判断正是不可外包的那一半。**且今天 gpt-5.6-sol 两次挂死**(0 CPU、连 session
    文件都没建出来),规划双出的 B 卷都是换 subdeepseek 出的 ⇒ 把安全面押在一条
    今天不稳的腿上不划算。**前端那层不一样**(纯 React + 已有浮层先例,边界清楚),
    后端契约绿了之后再派它,值。
  - **submimo fix(微档)**:这单跨 bin/ 三个文件 + web/ 若干,不合档。
  - **Sonnet 腿**:后备,没有非用不可的理由。
  - **判卷要不要起服务**:要(HTTP 层的来源检查、跨站拒绝)。按抽屉规矩,
    真派前端腿时主 agent 当测试机,有界 2 轮。
- 规格自查(读任何 panel 输出之前先答):<如果规格本身就是错的,会错成什么样、我怎么发现?
  panel 只验"实现合不合规格",验不了"规格对不对" —— 四腿齐 PASS 不等于题是对的。>
- 腿的花名册: <把 `<日志前缀>.roster` 里那一行**原样粘过来**,别手写>
  > panel-review 收尾自己写这个文件(off / FAIL(rc) / 降级 都在里面)。
  > 08-06 立这条的理由:08-05 我在这里手写了"三条腿一致 PASS",而 Kimi 根本没出结论
  > (同一页第 90 行我自己还写着它没出报告)—— 手抄一份终端上的东西,抄错那次没人会发现。
- findings:
  - <...>
  > 只写发现。腿的身份/降级不在这儿抄第二遍:日志自带身份牌(降级横幅 + 视野边界),
  > 花名册在上一格,查工件不查自述。
- arbitrated verdict (主裁): <...>
  > **归档时这一条和顶部的 `Verdict:` 都不许还是占位符**,`track-guard` 规矩3 会挡;
  > 没归档但已经合并上线的,`track list` 会打 ⚠️(stage-timer 就这么漏了两个月)。

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>
