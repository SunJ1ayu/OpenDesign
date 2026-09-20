# Verify: 打开软件不再被更新检查挡住

- Date: 2026-09-19 开工 / 2026-09-20 收口(中途断线一次,次日接手)

## Mechanical checks

- [x] build passes(`npm run build` + `tsc --noEmit` rc=0;dist 新鲜度闸绿)
- [x] tests pass(见下面的收据;**rc=3 那几遍不是全绿**,含义写在下面)
- [x] no secrets / unsafe ops(新增的只有本地读写盘与本机 HTTP;无新出网口)

**机器打印的收据(逐字节粘,红的一份没藏)**:

```
runlog: startup-block-baseline rc=0 commit=8746146 dirty=yes final=yes at=2026-09-19T15:29:00Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260919T152900Z-01-startup-block-baseline.txt
runlog: mutation-redcheck rc=1 commit=724f777 dirty=yes final=yes at=2026-09-19T15:48:39Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260919T154839Z-01-mutation-redcheck.txt
runlog: full-regression rc=1 commit=1b876fb dirty=yes final=yes at=2026-09-19T16:01:12Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260919T160112Z-01-full-regression.txt
runlog: startup-respec-redcheck rc=1 commit=287e7e8 dirty=yes at=2026-09-20T03:02:02Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T030202Z-01-startup-respec-redcheck.txt
runlog: startup-respec-redcheck-2 rc=1 commit=287e7e8 dirty=yes at=2026-09-20T03:07:09Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T030709Z-01-startup-respec-redcheck-2.txt
runlog: startup-respec-green rc=0 commit=569a452 dirty=yes at=2026-09-20T03:12:46Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T031246Z-01-startup-respec-green.txt
runlog: auto-install-local-redcheck rc=1 commit=569a452 dirty=yes at=2026-09-20T03:17:27Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T031727Z-01-auto-install-local-redcheck.txt
runlog: premise-move-probe rc=0 commit=4e73b27 dirty=yes at=2026-09-20T03:27:44Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T032744Z-01-premise-move-probe.txt
runlog: auto-install-local-green rc=0 commit=eb24724 dirty=yes at=2026-09-20T03:28:54Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T032854Z-01-auto-install-local-green.txt
runlog: pending-sweep-redcheck rc=1 commit=bca403d dirty=yes at=2026-09-20T03:30:26Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T033026Z-01-pending-sweep-redcheck.txt
runlog: pending-sweep-green rc=0 commit=0477219 dirty=yes at=2026-09-20T03:31:20Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T033120Z-01-pending-sweep-green.txt
runlog: full-regression-after-fix rc=3 commit=530f010 dirty=yes at=2026-09-20T03:31:31Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T033131Z-01-full-regression-after-fix.txt
runlog: startup-polish-redcheck rc=1 commit=530f010 dirty=yes at=2026-09-20T03:45:02Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T034502Z-01-startup-polish-redcheck.txt
runlog: full-regression-final rc=3 commit=93bd712 dirty=yes at=2026-09-20T03:47:43Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T034743Z-01-full-regression-final.txt
runlog: r1-fixlist-redcheck rc=1 commit=eb52d91 dirty=yes at=2026-09-20T04:17:45Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T041745Z-01-r1-fixlist-redcheck.txt
runlog: r1-fixlist-green rc=0 commit=8536391 dirty=yes at=2026-09-20T04:22:19Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T042219Z-01-r1-fixlist-green.txt
runlog: full-regression-r1fix rc=3 commit=72e20dd dirty=yes at=2026-09-20T04:23:31Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T042331Z-01-full-regression-r1fix.txt
runlog: r2-eligibility-redcheck rc=1 commit=181f960 dirty=yes at=2026-09-20T04:57:54Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T045754Z-01-r2-eligibility-redcheck.txt
runlog: r2-el9-redcheck rc=1 commit=141ed05 dirty=yes at=2026-09-20T05:04:34Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T050434Z-01-r2-el9-redcheck.txt
runlog: r2-full-regression rc=3 commit=ff478f2 dirty=yes final=yes at=2026-09-20T05:06:20Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T050620Z-01-r2-full-regression.txt
runlog: r2-full-regression-final rc=1 commit=3035b8d dirty=no final=yes at=2026-09-20T05:26:15Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T052615Z-01-r2-full-regression-final.txt
```

🔴 **最后那份 `rc=1` 是红的,不藏**(判据红了先问是不是真 bug,不先怀疑判据):

- 红的是 **`chat_reconnect.e2e.mjs` 第 ㉜ 条**(断线时正忙 + 重连后拉历史 404 ⇒ 发送键恢复
  可用)。它钉的是**真 bug**(0.75.0 四审判 BLOCK 的那条 P1:重连回来能打字、发送键永久变灰
  只能刷新),不是一条可有可无的题。㉜a/㉜b 两个前置都过了,只有最后那步 8s 内没等到。
- **为什么判定"不是本单引入"——机械证据,不是推理**:上一趟 `ff478f2` 同一套 e2e 是
  41 PASS / 0 FAIL;`git diff ff478f2 3035b8d -- bin/ tests/ web/` 去掉注释行后**零改动**,
  `web/` 一个字节没动(那一趟与这一趟跑的是同一份 dist,两趟新鲜度闸都绿)。
  ⇒ **被测系统的行为字节级相同,同一输入两次不同结果**。这不是统计推断,是对照。
- 补量:当前 HEAD 单跑 `chat_reconnect` **5 遍 5 绿**(脚本在 scratchpad,`[仓外不承重]`)。
- **处置:本单不修**(聊天重连是另一个模块,不在本单范围),**也不重跑到绿**
  (那是挑收据)。两份收据都留着。**⇒ 记为待开单:e2e `chat_reconnect ㉜` 间歇失败,
  需要在总跑环境下量复现率并定位竞态。** 与既有账 [[opendesign-e2e-flaky-and-gateway-dep]] 同族。
- ⚠️ 因此本单的最终回归收据是 **rc=1**,不是绿。归档时这一条必须当面说清,不许用前一份
  `rc=3` 冒充最终收据。

**第 2 轮重做之后新增的三份**(上面 runlog 段落的后三行):
- 两份 `rc=1` 是**判据先行的红**:`r2-eligibility-redcheck`(el1~el8,8 红 4 绿 —— 反向题 el3
  此刻就绿,证明它不会假红)、`r2-el9-redcheck`(我自审补的那条,单独先红再修)。
- `r2-full-regression rc=3`:六段全 PASS(node 461 / **python 1787** / e2e 41 PASS 0 FAIL 2 SKIP /
  dist 新鲜),3 条要活网关的没跑。**不是红,但也不许说成全绿**,与历史同形。
  python 1787 对比第 2 轮腿跑的 1776:差的 11 条正是新卷 `test_ds_update_eligibility.py`。

**怎么读这些数**:
- `rc=1` 的六份是**判据先行的红**(每一份都对应一次"实现还没写/还没修,此刻应当红")
  加上昨晚那份变异红检(2 条漏网,当场补强了判据)。它们是这一单最值钱的部分。
- `rc=3` 的三份全量回归:**六段全 PASS,3 条要活网关的 e2e 没跑** ⇒ 不是红,
  但**也不许说成全绿**。与本仓历史同形。
- 最后一遍(`full-regression-r1fix`)是结论所依据的那一遍:
  node 461 / python 1776 / e2e 41 PASS 0 FAIL 2 SKIP / dist 新鲜。

## Review

### 规格自查(读任何 panel 输出之前先答)

规格若本身是错的,会错成什么样?我当时写下的答案:

> 最可能错在**"启动只读盘"这句话的边界**:我把"读盘"当成了毫秒级动作,
> 但盘上那个东西有 46MB。如果"读"变成"读满",这条规格就会在真机上悄悄失效。

第 1 轮 subcursor 报的 HIGH-1 正好命中这一条(startup_decision 对整个包算 sha256),
**而我自己那一遍审没看见它** —— 我写下了正确的怀疑方向,却没顺着它去量一遍。

另外两条 HIGH 我完全没想到:数据根不一致(subdeepseek)、装失败后备货不清(subcursor)。
其中数据根那条**结构上问不出来**:全仓判据没有一处设过 `DS_DATA_ROOT`,
而单测里两个根恰好相等。这不是"没想到",是**考卷的形状不对**。

### 腿的花名册(从盘上重建,`panel-roster`)

```
submimo=PASS(verdict=PASS) subdeepseek=PASS(verdict=BLOCK) subglm=off subkimi=off subgemini=off subgrok=off subcursor=PASS(verdict=BLOCK)
```
```
# impact-risk=high requested-budget=2 selected-count=2(派发前快照)
escalation=conflict    selected-count=3(PASS/BLOCK 冲突 ⇒ 自动追加第三腿)
```
日志前缀 `/root/aiwork/logs/panel-startup-not-blocked-r1-20260920-1201.*`

### 轮次记录

| 轮 | 类型 | 派发前 `track preflight` | 日志前缀 | 新增有效阻断 |
|---|---|---|---|---|
| 1 | 实质 | BLOCK=0 PENDING=2(rc=3) | panel-startup-not-blocked-r1-20260920-1201 | 3 条 HIGH + 3 条 MEDIUM |
| 2 | 实质(复审修复清单) | **收据丢失**(见下注) | panel-startup-not-blocked-r2-20260920-1238 | 1 条 HIGH(两腿独立命中)+ 1 条 MEDIUM + 3 条 LOW |
| 3 | 实质(**追加**,超出开工预算) | 待填 | 待填 | 待填 |

预算:2 轮实质评审(默认值,开工未另写)。**第 3 轮是追加**,理由与新预算写在下面「追加第 3 轮」。

- 🔴 **第 2 轮派发前的 `track preflight` 读数没有落盘,如实记账**:那一轮的控制器 stdout
  随会话断线一起丢了(12:38 派发,约 12:44 断线,13:0x 接手)。派发本身没受影响 ——
  `panel-review` 由 `setsid -f` 脱到 PID 1,三条腿全部跑完、`observations/20260920T045036Z-*.json`
  与 `.final` 都正常落盘。**但 preflight 那一次的读数我拿不回来了,不补跑冒充**
  (事后跑的 preflight 问的是"现在",不是"派发那一刻")。
  ⇒ 工艺账:控制器的 stdout 也该落盘,不能只活在会话里。归在本单的收尾记录,不改代码。

- GLM / Kimi / Gemini / Grok 四条腿本轮显式 off:额度用光 / 周限额 / 地区被拒(连败 6 轮已判死)/ 连败 2 轮。
  健康池实际只剩 xiaomi 与 xai 两个家族,冲突后追加的 deepseek 是第三个。
- 🔴 **反锚定泄漏(如实记账)**:闸报了 `verify.md` 在树上。那一刻它是模板 + 昨晚的红检记录,
  **不含我的裁决与发现**(自审正本在仓外 `/root/aiwork/tasks/...-my-review.md`)。
  影响有限但不是零:腿能看到昨晚"这份考卷防的两种作弊"那段。

### findings 处置表(第 1 轮)

| # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
|---|---|---|---|---|
| 1 | **HIGH(subdeepseek)** 备货/启动接口用 `ds_common.data_root()`(外壳注 `…\OpenDesign\Data`),安装侧用 `paths_for_update()` 默认层(`%LOCALAPPDATA%\OpenDesign`)⇒ 真机上写的人和读的人各看各的文件,每次打开弹更新界面、apply 静默 `auto_skipped`,那一版永远装不上 | **成立**。我亲自读了 `ds_common.data_root` / `paths_for_update` / `ds_shell_core.data_root_for` 三处;新写的端点级判据 ur1/ur3 当场复现(状态落 `Data\Logs`、记账在 `Logs`) | **已修**(`_update_data_root()` 单一来源) | 本单核心承诺在真机上失效 |
| 2 | **HIGH(subcursor)** `record_attempt` 在 apply 之前写,失败后没人清 `update-state.json` ⇒ 之后每次打开都空演一遍更新界面,而 `auto_skipped` 在界面上静默 | **成立**。读 `autoFailureText`:对 `auto_skipped` 故意返回空串;`probeStartup` 在 install 分支直接 return ⇒ 那次会话也不再查更新 | **已修**(`discard_ready()`;判据 ai7/ai8) | 业主每次打开都会看见,且无任何解释 |
| 3 | **HIGH(subcursor)** `startup_decision` 对整个包算 sha256,而前端上限写死 500ms;超时后单向永久失效(前端不重试、`already_ready` 不重备) | **成立但本机未复现超时**:我量了 46.8MB —— 热缓存 37ms、丢缓存 117ms,**没超**。判成立的理由是机制:开销 O(包大小)、上限写死、失败静默且单向 | **已修**(启动不再哈希;校验留在 pr3/pr9 与 t4/ai9) | 余量未知(业主机器有 Defender 实时扫新下载的 .exe),而失败悄无声息 |
| 4 | **MEDIUM(subcursor #3 + subdeepseek #3)** `already_ready` 只比版本+大小 ⇒ 等长坏包被两边一起放过,死循环永不自愈 | 成立(读代码) | **已修**(pr9:`already_ready` 验到字节) | 与 #3 同根,不修则 #3 的修法会留一个新洞 |
| 5 | **MEDIUM(两腿都报)** `pending/` 下半截包与被跳过版本的孤儿没人清,每份 46MB | 成立 | **已修**(`_sweep_orphans`;判据 pr10) | 业主磁盘被撑满过两次 |
| 6 | **LOW(subdeepseek #5)** `/api/update/prepare` 宣称"立刻返回",却在返回前同步跑那次最坏 20s 的联网查 | 成立(读代码) | **已修**(挪进线程,一行) | 与 #1 同一处改动,顺手且零风险 |
| 7 | **LOW(subcursor #7 + submimo)** 启动那 0~500ms 是一块只有品牌名的画面,真机上可能"闪一下" | 成立,但那正是 sg10 要的形状;不是白屏(有 `--paper` 底色与 WindowChrome) | **延期** | 业主真机验收时看一眼;它在他那儿最坏是"打开时闪一下品牌名",不影响可用性 |
| 8 | **LOW(submimo)** `_update_decision_for_auto` 起的后台线程不设超时 | **驳回**:`check_for_update` 每跳自带 `TIMEOUT_S=10`,两跳有界;线程是 daemon,关软件即走 | 驳回 | 有代码依据 |
| 9 | **LOW(subcursor #5)** premise-move-probe 撤的是 HEAD 那一版而不是 base-ref `8746146` | **驳回**:探针要问的是"**这一次的实现**有没有让旧考卷放水",撤到 base-ref 会把整单实现一起撤掉,那问的是另一件事 | 驳回 | 有依据 |
| 10 | **自查(无腿报)** 装失败的那一次会话里,不再有后台查更新/备货(`probeStartup` 在 install 分支 return) | 成立 | **延期** | 备货状态已在后端清掉 ⇒ **下一次打开**一切正常;代价只是"失败的那一次会话内拿不到更新提示"。改它要动前端调度,不属于本轮阻断 |

### 腿的花名册(第 2 轮,从盘上重建 `panel-roster`)

```
# impact-risk=high requested-budget=2 selected-count=3  escalation=conflict
# snapshot=head:e766279
submimo=PASS(verdict=PASS) subdeepseek=PASS(verdict=BLOCK) subglm=off subkimi=off subgemini=off subgrok=off subcursor=PASS(verdict=BLOCK)
```
日志前缀 `/root/aiwork/logs/panel-startup-not-blocked-r2-20260920-1238.*`;
三条腿 `exit_code=0`、`degraded=false`、`evidence.completeness=complete`(没有一条是被砍的半截)。
家族:xiaomi / xai / deepseek 三个不同家族;冲突后追加第三腿同第 1 轮,是协议内升级不是重试。

### findings 处置表(第 2 轮)

| # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
|---|---|---|---|---|
| 11 | **HIGH(subcursor + subdeepseek 各自独立命中)** `discard_ready` 不收敛:被记过 `attempted` 的版本会被下一轮后台 prepare 原样下回来。序列:打开 A(enter)→ 开着满 60s 后台备好 → 打开 B:startup 说 install、弹「正在更新到 X」→ apply 判 `attempted` → `auto_skipped`(界面**静默**)+ discard → 打开 C:enter → 后台**重下 46MB** → 打开 D:又弹一次…… 第 1 轮 HIGH-2 的症状只被**减半**(每两次打开一次),另**新增每轮 46MB 流量** | **成立,我逐跳核过代码**:`_update_decision_for_auto` = `ds_update.check_cached(VERSION)`(`bin/ds_web.py:1331-1336`),不经 `_auto_update_status`;全仓 `attempted_at` 只在 `:916` 被问;`startup_decision`(`bin/ds_update_startup.py:99-148`)只看状态文件;前端 `web/src/App.tsx:412` 在 60s 后**无条件** POST prepare(只受开关约束);`autoFailureText` 对 `auto_skipped` 返回空串(`web/src/update.ts:317`)。subdeepseek 另跑探针实证:记上 attempted 后再调 `prepare_update` 仍 `ok=True`,download calls 1→2 | **本单必须修;按 4c 停手查设计后重做**(见下) | 业主每两次打开看见一次无解释的更新界面,且每轮白下 46MB |
| 12 | **MEDIUM(subdeepseek,subcursor 同向)** 作废条件过宽:`bin/ds_web.py:1204-1211` 只要 `eligible=False` 就 `discard_ready`,而 `why_not` 还包括 `no_shell` / `disabled` / `path_unsupported` / `asset` / `error` —— 这些**一行账都没记**,本可在条件恢复后自动装,46MB 却被白删 | **成立**。我读了 `_auto_update_status`(`:903-923`)全部返回分支与 `:1204-1211` 调用点;代码注释写的是"多半是已经试过一次"——"多半"二字本身就是它没分清的自供。subdeepseek 走端点实证:`OPENDESIGN_AUTO_UPDATE=off` 与 `DS_SHELL_LOCK_PORT=""` 两种情况下包被删、状态回 `idle`,而记账文件不存在 | **本单必须修**(与 #11 同一处重做) | 不是失败,是"无效地丢了业主的 46MB";`path_unsupported` 这类永久条件下会变成"下载→作废→再下载"持久空转 |
| 13 | **LOW(subdeepseek)** 三处注释仍声称 `startup_decision` 逐字节校验,su15 之后已不成立:`web/src/update.ts:242`「大小 + sha256 都对得上才算」、`:391`「逐字节校验过盘上那个包之后才带上它的」、`web/src/App.tsx:280`「大小 + sha256,后端 startup_decision」 | **成立**,我逐行核过三处原文 | **本单必须修** | 本单立的规矩正是"界面/注释不许说谎",这三句是下一个人会当真的假话;真实防线在 pr3/pr9 与 t4/ai9 |
| 14 | **LOW(subdeepseek)** `_update_prepare` 先置 `_PREPARE_STATE["running"]=True`,再在 `try` 外算 `root`(`bin/ds_web.py:1310-1316`);一旦抛出,本会话之后所有 prepare 永远回 `already_running`,自动更新整条静默死掉 | **成立**(读代码)。`paths_for_update` 实际不会抛,概率极低 | **本单修**(挪进 try,零风险) | 失败形态是"静默永久死",与本单"不许静默单向失效"的立意同类 |
| 15 | **LOW(subdeepseek)** `_discard` 第一个 try 只 `except OSError`,而 `os.path.isfile(None)` 抛 `TypeError`(subdeepseek 实测),与其 docstring「自己也不许抛」不符 | **成立**。当前三个调用方各自包了更宽的 `except Exception` ⇒ 暂无实际后果 | **本单修**(一行) | 契约靠调用方兜着,下一个调用方不兜就漏 |
| 16 | **submimo 的 PASS** | — | **不采信为覆盖以外的任何东西** | 第 1 轮它也给 PASS 且在数据根那条上明确写"接缝无问题"(错的);这一轮它又是唯一的 PASS。**全票不是护身符,孤腿 BLOCK 才是信号**——本单第二次实证 |

## 4c 停手:这是同一类问题连续第二次打补丁

panel SKILL 4c:「**同一类问题连续第二次打补丁 ⇒ 停手**,先查抽象、数据关系、共同根因、验收边界」。

- 第 1 轮:症状「装失败后每次打开空演一遍更新界面」⇒ 我的补丁:在 apply 侧 `discard_ready` 删包。
- 第 2 轮:症状**同一个**,只是周期从 1 变成 2,外加 46MB/轮 ⇒ 再补就是第三个补丁。**停。**

**共同根因(两条腿各自独立指到同一处,我核实同意)**:
「**这一版还够不够格自动更新**」这本账(`auto-update-attempts.json`)在整条链上**只有一个决策点在读**——
`apply`(真装那一刻,`_auto_update_status`)。而链上实际有**三个**决策点:

| 决策点 | 问的问题 | 读不读这本账(修复前) |
|---|---|---|
| `prepare`(后台要不要下) | 有新版吗 | ❌ 只问 `check_cached` |
| `startup`(打开时要不要弹界面装) | 盘上有没有校验得过的包 | ❌ 只看 `update-state.json` |
| `apply`(真装) | 这一版够格自动装吗 | ✅ 唯一读的一处 |

⇒ 末端删文件永远追不上前端重下。**正确的抽象是把"这一版够不够格自动更新"做成单一判据,
链上三处共用**,而不是在末端补救。这也解释了第 1 轮我把"失败会话内不再查更新"判成延期时
写下的那句理由(「备货状态已在后端清掉 ⇒ 下一次打开一切正常」)**为什么站不住**:
它只往前看了一步,没看第三步会被后台重新备货。**我的延期定性是错的,不是腿挑刺。**

## 追加第 3 轮(派发前写明,按 panel SKILL ④)

- **具体阻断**:#11(HIGH)、#12(MEDIUM)成立且本单必须修;修法是**方案层重做**(单一资格判据,
  三处共用),不是措辞修正 ⇒ 落在「先别改」的豁免清单**之外**,第 2 轮的 subject digest 必然失效,
  机械上也拿不到归档覆盖。
- **追加目的**:只核验 #11~#15 的重做与其影响面(尤其"资格判据下沉后,手动更新那条路有没有被误伤")。
- **新的有限预算**:**1 轮**。再有阻断 ⇒ 本单保持未完成、缩范围,不再续轮。
- 这不是"多审一轮碰运气":预算用完时协议给的两条路是「缩范围」或「回头重看方案」,
  我选的是后者 + 为重做取一次覆盖。

## Accepted deviations

- **「60 秒后后台那一趟点火时重新问一次开关」没有自动判据。** 那 60 秒的延迟让 e2e 问不出它,
  而为了可测在产品代码里开一个测试专用旋钮不值得。只做了代码级自查。**不冒充有覆盖。**
- 3 条要活网关的 e2e 本轮没跑(与历史同形)。
- 上面第 7、第 10 两条延期项。

## 试行记录(review-convergence 试行)

- 总交付历时:2026-09-19 22:27(开工 commit)→ 待填(归档 commit)
- 每轮新增有效阻断:第 1 轮 3 HIGH + 3 MEDIUM(另 2 条驳回、2 条延期);
  第 2 轮 1 HIGH + 1 MEDIUM + 3 LOW(**其中 HIGH 正是第 1 轮第 10 条我判"延期"的那一条的第二步**)
- 🔴 **第 2 轮最值钱的一条不是腿发现了新 bug,是它推翻了我上一轮的定性**:
  我写"备货已清 ⇒ 下一次打开一切正常"时只验了一步。这与 09-19 那单
  (我自己六条判据全绿而改动是坏的)是同一种失败:**我写的规格与我写的绿,互相证明不了对方。**
- 基础设施等待:0 次重试(三条腿一次成功;冲突追加第三腿是协议内的升级,不是重试)
- 交付后返工:待填

## arbitrated verdict(主裁)

**第 2 轮主裁:BLOCK**(2026-09-20 13:0x,断线后接手判)。
submimo=PASS / subcursor=BLOCK / subdeepseek=BLOCK。两条 BLOCK 来自**两个不同家族**
(xai、deepseek),**各自独立**落在同一条 HIGH 上,且 subdeepseek 另跑探针给了执行证据
(download calls 1→2)。我没有采信任何一份自述:#11~#15 五条我逐条读了实现原文才判成立。
本单**保持未完成**,按 4c 停手重做方案,再追加 1 轮(理由见上)。

第 1 轮主裁:**BLOCK** —— 两条 BLOCK 腿的三条 HIGH 全部核实成立,
其中两条是我自己那一遍审没看见的;MiMo 的 PASS(并明确写"接缝无问题")在第 1 条上是错的。
**全票不是护身符,孤腿 BLOCK 才是信号** —— 这一轮是三次里最干脆的一次实证。

## 判据先行:实现之前的红(基线 34b0805)

`python -m unittest tests.test_ds_update_startup` ⇒ **Ran 25 tests, FAILED (failures=24, errors=1)**

红的原因逐条核过,都对(`ds_update_startup` 整个模块还不存在):
- **su1**(唯一该装的那条路)+ **su2~su12**(缺文件/非对象/半写/schema 不认/phase 不对/
  包不见了/摘要对不上/大小对不上/版本不新/版本号读不出/path 是目录或符号链接)⇒ 一律该进工作区
- **su13** 永远不许抛 —— 本项目四次"打不开"前科的机械防线
- **su14** reason 必须是稳定枚举,不是自由散文
- **su_net1~3** 🔴 本卷核心:决策期间创建 socket 算失败;读状态文件也不许联网;
  把 ds_update 的取数函数全换成"一调用就炸"后,启动决策仍须正常返回
- **sw1~sw4** 原子写(用 `os.replace` 被调用那一刻目标路径的内容来验半写窗口)、坏文件读成 None
- **sc1~sc4** 首次检查有延迟、轮询带抖动、失败退避且有上限、间隔不许为负
  (sc1 是 error 不是 failure:它读常量 `FIRST_CHECK_DELAY_S`,桩返回的是函数 ⇒ TypeError。原因同样是"还不存在"。)

**这份考卷防的两种作弊**(写在文件头):
① 把超时从 35s 改小就宣称修好 —— 照样在启动路径上联网,网一慢照样等。su_net 段钉它,
   且**故意不用"量耗时"来验**(耗时判据会被"把 35s 调成 3s"骗过,还会因机器快慢变 flaky)。
② 状态文件一有问题就抛,把"不更新"变成"打不开"。su4~su13 钉它。
