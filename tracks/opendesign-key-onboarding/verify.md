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

---

# lane=full 四审(2026-08-16 收口)

```
submimo=PASS subdeepseek=PASS subglm=off subkimi=PASS
```
> 花名册里的 `PASS` 是**进程 rc=0,不等于给了通过裁决**;`off` = 这条腿压根没派。
> subglm 两条腿都挂:agent 腿 `[claude-code:unrecognized_model] {"model":"glm-4.6v"}`
> (**模型名失效,不是欠费** —— 我一度凭记忆说成欠费,是错的),chat 腿被反锚定闸挡下。
> ⚠️ 评审期间我提交了三笔(收据 / backlog / 真机清单),HEAD 从 `2606f90` 移到 `3795d42`
> ⇒ 各腿未必读的同一棵树。**这是我的操作失误**(工具明确警告过);好在那三笔都不是
> 代码,代码面全程没动。

**主 agent 自审在派发之前写好并放在仓外**(`/root/aiwork/tasks/keyonb-full-review-my-review.md`),
裁决是**代码面 PASS**。⇒ **我错了,两腿的 BLOCK 成立。**

## 逐条对账

| # | 来源 | 结论 | 依据 |
|---|------|------|------|
| 1 | deepseek B / kimi 1 | **接受·已修** | 外壳把同一份 env 给两条腿 ⇒ ds-web 也拿到 key ⇒ `status()` 把**自注入**误判成外部遮蔽 ⇒ 装好的应用重启后改 key 卡片**永久只读**,还让业主去清一个他没设过的变量。核实属实(`ds_shell.py:235`)。修:`core.service_envs()` 只给网关(`2dba7ec`),判据 J 组先行(`4cc8f6d`)+ 红检 Q1/Q2 咬住。 |
| 2 | kimi 3 | **接受·已修** | `OK` 在动词分派**之前**发出 ⇒ 老外壳回 OK 后去唤醒窗口,ds-web 却报 `requested`。核实属实(`ds_shell_core.py:302`)。修:应答点名动词 + `_restart_verdict()` 只认它(`b051c3f`),判据 K 组 + k3b(老外壳必须降级)。 |
| 3 | kimi 4 / deepseek 注记 | **接受·已修** | 「已经自动应用新配置」超出 `requested` 的定义(帧送达+认了动词 ≠ 重启成功),与外壳失败告警互相打脸。改成"正在自动重启…若仍连不上请手动重启"。 |
| 4 | deepseek A / kimi 2 | **接受·不修(主裁)** | Linux 的 `ds-nanobot` 从 auth.json 取 key、只导给子进程 ⇒ 本模块两层都够不着,界面在开发机上会撒谎。**属实**。但业主机器是 Windows(装好的 `ds_shell` 注入 / git-pull 的 `ds-nanobot.ps1`)两条路都在管辖内;为开发机引入"去读 auth.json"的平台特化探测,风险大于收益。⇒ **把边界写死进模块头 + backlog**(`8b84bdb`),并写明将来的正确形状是给 `status()` 第三种回答 `source="unmanaged"`,而不是继续在 `configured` 上撒谎。 |
| 5 | kimi 6 | **接受·记账** | `save()` 两次原子写之间有半成品窗口(新端点 + 旧 key)。窗口窄、两个方向都存在,现顺序是刻意选的。记 backlog。 |
| 6 | kimi 5 / submimo LOW2 / 我自审 | **接受·记账** | `slot` 身份"三个挂载点不重建"只是注释,无机械闸。三方一致(我自审也写了)。 |
| 7 | submimo LOW1 | **部分驳回** | 它说 `null` 会变成 `"None"` 字符串并通过空检查 —— **实测不成立**(`None or ""` 得空串,被拒)。但**方向对**:`{"key": 123}` 会被写成 `"123"`。⇒ 驳回其例证,接受其结论,记 backlog(LOW,可恢复)。 |
| 8 | submimo LOW3 | **接受·不修** | `LlmKeyCard` 的 effect 依赖稳定 `onStatus`(靠调用方 `useCallback`),脆弱。我自审里也列了同款(F1)。不阻断。 |

## 🔴 这次四审最值钱的不是任何单条发现

**submimo 判五个不变量全 PASS / 0 BLOCK,而另两腿各自独立判 BLOCK。**
差别在问法:submimo 问的是「代码合不合规格」,deepseek/kimi 问的是「规格在真实形状下
成立吗」。而**真漏的两条都在后者**——它们打的都是我写的规格本身(我假定"env 里有 key
就是业主设的",而外壳自己会注入;我假定"回了 OK 就是认了重启",而老外壳也回 OK)。

⇒ 又一次印证:**过审只证明合乎规格,不证明规格对**;以及**别把腿的结论取平均**。
若按票数(1 PASS vs 2 BLOCK)或按"最详细的那份"(submimo 的表格最漂亮)来判,都会错。
