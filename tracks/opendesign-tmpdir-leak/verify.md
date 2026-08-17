# Verify: opendesign-tmpdir-leak

- Date: 2026-08-17
- Verdict: <PASS | BLOCK | NEEDS_MORE_INFO>

## Mechanical checks

- [ ] build passes
- [ ] tests pass
- [ ] no secrets / unsafe ops

**机器打印的**(不是我的转述):

### 红检 + 对照组(commit ① 时,只有闸、没有修复)

```
runlog: redcheck-A-clean-must-pass rc=0 commit=5d8c991 dirty=yes at=2026-08-17T15:43:40Z file=tracks/opendesign-tmpdir-leak/evidence/20260817T154340Z-01-redcheck-A-clean-must-pass.txt
runlog: redcheck-B-leaky-must-fail rc=9 commit=5d8c991 dirty=yes at=2026-08-17T15:43:48Z file=tracks/opendesign-tmpdir-leak/evidence/20260817T154348Z-01-redcheck-B-leaky-must-fail.txt
runlog: gate-selftest rc=0 commit=5d8c991 dirty=yes at=2026-08-17T15:44:33Z file=tracks/opendesign-tmpdir-leak/evidence/20260817T154433Z-01-gate-selftest.txt
```

A 是**对照组**:干净判据必须绿。只跑 B(红)不算红检 —— 一道见谁都红的闸,
和一道永远绿的闸一样没用。

### 修复前的基准数字(事后判"有没有把判据改坏"的唯一依据)

- node 单测:376 用例 / 0 跳过 / 0 todo
- python 全量:1277 用例 / 0 跳过,一次跑漏 **945** 个临时目录
- e2e 总跑(不含 gateway):36 PASS / 0 FAIL / 2 SKIP,漏 4 个

### 修复后的总跑

```
<待填 —— commit ② 之后跑 tests/run-all.sh --with-gateway 的收据行>
```

## Review

- lane: full
  > 不是因为撞了那条硬规矩(新写口/权限/auth/钱/数据一致性 —— 这单一条没碰,
  > 产品代码 `bin/`、`web/` 一字未动)。选 full 是因为**改动面 100% 在判卷层**、
  > 铺开 24 个文件,而这一类最危险的坏法是「判据还是绿的,只是测得更少了」——
  > 那正是本机最忌讳的"改考卷让自己及格",哪怕不是故意的。
  > 本仓库反复的史料是:**真漏的根因几乎每次都是我自己的判据/夹具错**,
  > 而那种错我自审照不到(0.89.0 那单:另一条腿用和我同一个错误模型复核我的判据,
  > 当然复核不出来)。这单花得起这个 panel。
- 派给: 主 agent 直接干
  > **不是"排除了 codex 就跳到我自己干"**(07-31 栽过这个,四单原样复制同一句有洞的理由)。
  > 逐档答:
  > · codex / submimo fix / Sonnet 腿 —— 派活规矩里「oracle / 判据文件对执行腿
  >   off-limits」在这单**直接失效**:要改的就是判据文件本身,闸①「它有没有动判卷」
  >   问不出任何东西,因为它碰的每个文件都是判卷。
  > · Sonnet 腿**技术上仍可行**(拿"用例数/断言数不许变"当收货闸能罩住),
  >   没派的实际理由是:47 处的改法我已经**逐处**知道了(前缀→调用点的映射是
  >   实测出来的,不是猜的),写任务书 + 走三道闸的开销大于活本身。
- 规格自查(读任何 panel 输出之前先答):
  > **规格错了会错成什么样**:我把业主的「磁盘满了」翻译成「修判据的临时目录泄漏」。
  > 这一步转译要是错的(大头其实不是判据),后面全白做。
  > 怎么发现的:没靠读代码猜 —— 做了实测普查(evidence/…census.txt),
  > 用 `/tmp` 各前缀的**实际堆积数**对账,39 个前缀在漏、60 个干净、
  > **中间地带 0 个**。断崖干净到没有解释空间。
  >
  > **规格没覆盖到的那一面**:闸绿只证明"判据自己跑完收干净了",
  > 不等于业主要的"盘不会再满"。别的东西(gateway / playwright / 别的项目)照样可能漏。
  > 所以收口必须额外给一条**盘面事实**:跑完一整轮总跑后 `/tmp` 的净增量 ≈ 0。
  > (0.87.0 那单栽过 20 条「判据全绿但业主照样丢东西」的路线。)
- 腿的花名册: <待填 —— panel-review 收尾自己写的那一行,原样粘>
- findings:
  - <待填:主 agent 先独立审并落 findings,再读 panel 输出>
- arbitrated verdict (主裁): <待填>

## Accepted deviations

- <待填,或 None>
