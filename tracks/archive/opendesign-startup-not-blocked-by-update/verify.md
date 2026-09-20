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
- 🔴 **但我原来的说法说大了(第 3 轮 subdeepseek 当场纠正,我接受)**:这两份收据
  **都在本单之后**,所以上面那段证明的是「最后两个 commit 行为相同」,**不是**
  「本单没有抬高 ㉜ 的抖动概率」。准确的一句话是:**没找到因果路径,且两份收据都在本单之后**。
  腿另补了一条我没做的核查:失败那趟约 31s,而最近的后台更新是 60s 单次(`App.tsx:408-415`)
  ⇒ 那时还没点火;`/api/update/startup` 是本地 200、上限 500ms、不联网,够不上 30s 的点击超时。
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
| 3 | 实质(**追加**,超出开工预算) | **读数又丢了**(见下注②) | panel-startup-not-blocked-r3-20260920-1345 | 1 条 HIGH(**本单引入的回归**)+ 1 条 MEDIUM + 2 条 LOW |
| 4 | **基础设施失败,不算实质轮** | BLOCK=1 PENDING=2(rc=1,**已落盘**) | panel-startup-not-blocked-r4-20260920-1646 | — (只有 1 条腿给出裁决,拿不到合格覆盖) |
| 4b | 实质(**追加,本单最后一次派发**) | **没为它单独跑**(见注③);派发前 `track-record validate --phase dispatch` = `status=valid` | panel-startup-not-blocked-r4b-20260920-1720 | **0 条阻断**(5 条 LOW,全部核实成立、全部延期) |

预算:2 轮实质评审(默认值,开工未另写)。**第 3 轮是追加**,理由与新预算写在下面「追加第 3 轮」。

- 🔴 **第 2 轮派发前的 `track preflight` 读数没有落盘,如实记账**:那一轮的控制器 stdout
  随会话断线一起丢了(12:38 派发,约 12:44 断线,13:0x 接手)。派发本身没受影响 ——
  `panel-review` 由 `setsid -f` 脱到 PID 1,三条腿全部跑完、`observations/20260920T045036Z-*.json`
  与 `.final` 都正常落盘。**但 preflight 那一次的读数我拿不回来了,不补跑冒充**
  (事后跑的 preflight 问的是"现在",不是"派发那一刻")。
  ⇒ 工艺账:控制器的 stdout 也该落盘,不能只活在会话里。归在本单的收尾记录,不改代码。

- 🔴 **注②:第 3 轮派发前的 `track preflight` 读数同样没有落盘。** 第 2 轮是断线丢的,
  这一轮是**没落盘**丢的 —— 上一轮我把它记成"工艺欠账"却没当场修,于是同一笔账吃了两次。
  **不补跑冒充**(事后跑的 preflight 问的是"现在")。⇒ 从第 4 轮起,preflight 与控制器
  stdout 一律 `tee` 进 `evidence/`,收据行进这份文件。这是本单收尾要还的第一笔账。

- 🔴 **注③:第 4b 轮派发前没有为它单独跑 `track preflight`,如实记账。** 第 4 轮那份
  (`evidence/20260920T084048Z-01-r4-preflight.txt`,16:40)与 4b 派发(17:14)之间只隔一个
  commit(`7eeef79`,内容是 r4 的花名册与记账),产品文件一个字没动;派发前跑的是
  `track-record validate --phase dispatch`(`status=valid`,收据在 `.dispatch.log` 第一行)。
  **不事后补跑一份冒充"派发前"** —— 那正是注①注②两次栽的地方。归档前的那一份另记(在下面)。

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


### 腿的花名册(第 3 轮,机器打印,不手写)

```
# impact-risk=high requested-budget=2 selected-count=3  escalation=conflict
# snapshot=head:e7f83ef
submimo=PASS(verdict=PASS) subdeepseek=PASS(verdict=BLOCK) subglm=FAIL(rc=1,降级:回落聊天腿也没成) subkimi=SKIP(rotation) subgemini=SKIP(health:dead:FAIL:6) subgrok=SKIP(rotation) subcursor=SKIP(rotation)
```
日志前缀 `/root/aiwork/logs/panel-startup-not-blocked-r3-20260920-1345.*`。
⚠️ **本轮只有两条腿给出裁决**(xiaomi / deepseek):冲突后追加的第三腿 subglm 两次都没起来
(agent 腿 rc=1 → 回落聊天腿也没成;根因是月度额度用光,见 [[glm-53-until-sub-expiry]])。
**这不算"三腿覆盖"**,`degraded=true` 已落在 observation 里,不许读成"全池看过了"。

### findings 处置表(第 3 轮)

| # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
|---|---|---|---|---|
| 17 | **HIGH(subdeepseek F1)** 第 2 轮我"收成单一判据"的其实只有**账本**那一维;完整资格的另外几维(`no_shell` / `not_installed` / `path_unsupported` / `disabled`)仍然只在 apply 被问 ⇒ startup 照样说 install、界面照样弹,而 apply 的 `auto_skipped` 在界面上**是静默的**;包又因 el4(临时条件不许删)留着 ⇒ **每次打开重复,永不收敛**。`disabled` 就是业主「关掉自动更新」那个开关 —— 关了照样弹、照样下 46MB | **成立,且比它报的更糟**。我自己跑探针(两种条件):`[no_shell] STARTUP -> install ; APPLY -> auto_skipped/no_shell ; 包还在盘上`、`[disabled] 同上`。腿另给了 base-ref 对照:修改前前端走 `shouldAutoUpdate` = `canApply && autoStatus().eligible`(**完整**资格),是**本单**把它换成了只问 `/api/update/startup` | **本单必须修**(见下面「第 3 轮的重做」) | **是我上一轮引入的回归**,不是既有洞;且它让业主的关闭开关形同虚设 |
| 18 | **MEDIUM(subdeepseek F2)** `bin/ds_web.py:916` 在 apply 侧把同一个判断**又拼了一遍**(`attempted_at(...) is not None`),而不是调用共用判据 ⇒ 正是本次重做要防的漂移,且漂移方向是"错判为没资格" | 成立(读代码) | **本单必须修** | 这一单立的规矩就是"同一个问题只写一处",留着它等于规矩自己不算数 |
| 19 | **LOW(subdeepseek F3)** `startup_decision(data_root=None)` 默认跳过资格检查;`_local_ready_install` 正是不传它的活调用者。腿**正面攻过**:今天构造不出误装(apply 侧 `_auto_update_status` 兜着),但"忘传就静默失效"是一步之遥,而理由里有一句是拿判据形状辩护的 | 成立。**这条打中的是我自己在派发前写明"最没把握"的那一处**(`-my-review.md` 点 1、点 2) | **本单修,但不是照它建议补一个参数** | 见下面「第 3 轮的重做」:参数整个拿掉,让"忘传"不再是一种可能 |
| 20 | **LOW(subdeepseek F4)** discard 收窄到 `why_not == "attempted"` 之后,`path_unsupported` 这种**永久**条件下那 46MB 没有任何人会清(`_sweep_installed` 故意放过比当前新的版本) | 成立(读代码,并由新判据 el14 当场复现) | **本单必须修** | 与 el9 同一类磁盘泄漏,换了个 reason code;业主磁盘被撑满过两次 |
| 21 | **INFO(subdeepseek F5)** 顺序/不许抛的契约完好 | — | 无需处置 | — |
| 22 | **subdeepseek 对我那条红 e2e 定性的反驳**:窄的成立(两份收据之间被测系统字节级相同),**宽的不成立** —— 两份收据**都在本单之后**,所以它证明的是"最后两个 commit 行为相同",不是"本单没有抬高 ㉜ 的抖动概率" | **我接受**。它另给了一条我没做的核查:失败那趟约 31s,而最近的后台更新是 60s 单次 ⇒ 那时还没点火;`/api/update/startup` 是本地 200、500ms 上限、不联网 ⇒ 够不上 30s 点击超时的成因 | **改我自己的措辞**(见上面那段已改成"没找到因果路径;两份收据都在本单之后") | 我原话把"没有证据"说成了"证明无关"。这是本单第三次:**我写的规格与我写的绿,互相证明不了对方** |
| 23 | **submimo 的 PASS** | — | **不采信为覆盖以外的任何东西** | 三轮三次孤票 PASS,而三轮各有一条经我核实成立的 HIGH。**全票不是护身符,孤腿 BLOCK 才是信号** —— 本单第三次实证 |

## 第 3 轮的重做:把"该不该自动装"做成**真正**的单一判据

第 2 轮我说"改的是抽象不是补丁",F1 证明那句话只兑现了一半:我把**账本**收成了一处,
却让**同一个问题的另一半**(这台机器现在装不装得上)继续留在末端。于是链条变成:
startup 问半个问题 → 说能装 → 界面弹出来 → apply 问另外半个 → 静默拒绝。**症状原样回来。**

重做(实现见 `bin/ds_auto_update.py` `why_not_auto`):

| 决策点 | 修前问什么 | 现在问什么 |
|---|---|---|
| `prepare`(要不要下 46MB) | 有新版吗 + 账本 | `why_not_auto`(账本 + 机器,**整个**问题) |
| `startup`(要不要弹更新界面) | 盘上有没有包 + 账本 | 盘上有没有包(纯事实)+ `why_not_auto` |
| `apply`(真装) | 自己又拼了一遍(F2) | `why_not_auto` |

三条设计决定,逐条说明为什么:

1. **判据答的是整个问题,不是一维。** 名字从 `machine_blocker` 改成 `why_not_auto`,
   返回值与 `_auto_update_status` 同一套 `why_not` 枚举 —— 让"调用方自己再拼一遍"这件事
   连措辞上都没有借口(F2)。
2. **`startup_decision` 退回纯事实函数,`data_root` 参数整个删掉**(F3)。
   腿的建议是"在 `_local_ready_install` 那一处补传参数";我没照做,因为那还是同一个形状
   ——**可选参数 = 忘传就静默失效**,而纯函数判据(su1~su15)自己测自己、永远是绿的。
   删掉参数之后,"忘传"不再是一种可能;资格由端点那一处统一问。
   ⚠️ 这也顺带消掉了一处**重复**:重做前那条路上账本被问了两遍(函数里一遍、端点再一遍)。
3. **永久 / 临时分开**(F4 + el4):`PERMANENT_BLOCKERS`(试过 / 不是装出来的 / 路径不支持)
   才清包;`no_shell` / `disabled` / `error` 是临时的,**不许删业主的 46MB**,条件恢复就能装。

### 这一轮我自己抓到的(腿没报,记账)

🔴 **变异红检 E8 漏网 ⇒ 补判据 el15。** 重做之后我跑了一份新的变异红检
(`mutants-eligibility.py`,跨三个文件、9 个变异)。8 个咬住,**1 个漏网**:
把 `no_shell` / `disabled` 错加进 `PERMANENT_BLOCKERS`(= 临时条件也删包),
**一条判据都没红**。原因是规矩钉在了**旧的那个决策点**上:el4 钉的是 apply 侧,
而新的删包代码住在 prepare 侧。**同一条要求,两个决策点都要钉** —— 这正是 F1 那条 HIGH
的同款失败,只不过这次是我自己的红检先抓到的。补 el15 后重跑,9/9 全咬住。

> 这条也回答了"我凭什么认为这次的重做比上次结实":上次我只有"既有判据没红"作证据,
> 这次有**机械的反向证据** —— 把新设计逐处改坏,判据会点名叫红。

## 追加第 4 轮(派发前写明,按 panel SKILL ④)—— **本单最后一次派发**

- **具体阻断**:#17(HIGH,**本单引入的回归**)、#18(MEDIUM)、#20(LOW)成立且必须修;
  修法又一次是**方案层改动**(单一判据答整个问题、删掉 `startup_decision` 的可选参数),
  不是措辞修正 ⇒ 落在「先别改」豁免清单**之外**,第 3 轮的 subject digest 必然失效,
  机械上也拿不到归档覆盖。**不派这一轮,本单只能以 BLOCK 归档。**
- **追加目的**:只核验这次重做与其影响面。六个重点写在任务书里,其中三条是我自己不确定的:
  ① 还有没有**第五个**决策点(第 3 轮我以为收敛了,结果漏了四种否决条件);
  ② 我把资格闸放上了启动路径 —— 是不是在治这个病的同时又犯了同一个病(`why_not_auto`
  会调 `update_preflight_problem`;我判定纯读盘无网络,但**慢**不会被 try 兜住);
  ③ `not_installed` 我划成"永久否决"(会删包),可业主今天绿色版、明天装一份也可能。
- **新的有限预算**:**1 轮,且是本单最后一次派发。**
- 🔴 **再有阻断的处置,写死在派发前,不留给事后解释**:**不再续轮**,改**缩范围** ——
  把**自动**更新这一层整个退出本单(关掉后台备货与开机自动安装),只交付三轮评审都说
  站得住的那部分:**启动路径不再联网查更新 + 手动更新照旧**。那正是业主原话要的那件事
  (「每次打开都会弹出正在检测更新,这严重拖慢了开软件的速度」),而四轮里每一条 HIGH
  全部落在自动更新资格这一层。
- **为什么这不是"审到绿为止"**:预算用完时协议给的两条路是「缩范围」或「回头重看方案」。
  前三轮我选的都是后者(每轮都真的改了方案);这一轮**两条路都摆上**:先取一次覆盖,
  取不到就当场缩范围。判断依据不是感觉,是这一单的经验频率 —— **三轮三次**,
  每一轮外部腿都抓出一条经我核实成立的 HIGH,其中两条是我自己写错的。
  我自己那一遍审在这条链上的命中率是 0/3。

## 第 4 轮派发前的收据,以及**最终回归又红了一条**(不是上一条,是新的一条)

```
runlog: r3-full-eligibility-redcheck rc=1 commit=e7f83ef dirty=yes at=2026-09-20T05:56:41Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T055641Z-01-r3-full-eligibility-redcheck.txt
runlog: r4-eligibility-mutants rc=0 commit=57d35e3 dirty=yes at=2026-09-20T07:57:43Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T075743Z-01-r4-eligibility-mutants.txt
runlog: r4-full-regression-final rc=1 commit=f7b58db dirty=no final=yes at=2026-09-20T08:04:32Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T080432Z-01-r4-full-regression-final.txt
runlog: r4-full-regression-recheck rc=3 commit=f7b58db dirty=yes at=2026-09-20T08:27:10Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T082710Z-01-r4-full-regression-recheck.txt
```

**`r3-full-eligibility-redcheck` rc=1 是判据先行的红**:el10~el14 写完、实现还没动那一刻,
**6 条红**(no_shell / disabled 下 startup 仍说 install、后台照样下 46MB、临时状况过去不恢复、
path_unsupported 下 46MB 没人清)。它是第 3 轮那条 HIGH 在本仓里的机械复现,
**不是环境噪音,是这一轮最值钱的一份收据**(preflight 的 5b 提醒我它没被引用,已补)。

**`r4-eligibility-mutants` rc=0 = 9 个变异全部咬住**(含我补的 el15;它就是被第 8 个变异逼出来的)。

**`r4-full-regression-final` rc=1**,六段里五段绿,红的是 **python 全量的 1 条**
(1793 跑过 / 1 跳过 / 1 红)。🔴 **注意:上一轮那条红的 e2e(`chat_reconnect ㉜`)这一趟是绿的**
(e2e 41 PASS / 0 FAIL / 2 SKIP),dist 新鲜度与类型检查也绿。

### 红的是 `test_ds_shell_core.test_b8`(双击两下只许一份赢),不是本单的模块

```
AssertionError: 0 != 1 : 第 5 轮同时起两份,0 份都认为自己是唯一实例:
[{'acquired': False, 'port': 40305}, {'acquired': False, 'port': 40305}]
```

**先问"是不是真 bug",没先怀疑判据。** 我做的是:

1. **读实现定住"什么才能造出这个结果"**:`acquired=False` 只有两条路 ——
   第一轮扫描握手拿到 `LOCK_OK`(`_send_show` 要求**逐字节相等**的应答行),
   或绑上之后发现更靠前的锁位有人(`_someone_ahead_of`)。两条都要求
   **有一个真的 OpenDesign 锁在应答**。随便一个 HTTP 服务器冒充不了。
2. **因此本单的改动造不出它**(机械理由,不是推理):我的新判据把
   `DS_SHELL_LOCK_PORT` 写死成常量 `"47123"`(`test_ds_web_auto_update` 的夹具),
   **从不启动 InstanceLock**,一个锁服务都不起。
3. **隔离量了三组**(都在本次改动之上):b8 单跑 **8/8 绿**;
   b8 所在模块与我的新卷**同进程**跑 **5/5 绿**;
   另写探针 `tracks/<t>/b8-probe.py` 复刻它的循环并打印每轮 base / span / 上几轮留活的赢家,
   **25 轮 0 次异常**(顺带证伪了我自己的第一个假设:本机临时端口是**随机**发的,
   不是递增,所以"上一轮赢家落进下一轮 span"很罕见)。
4. **今天之前的四趟总跑里 python 全段都是绿的**(1771 / 1776 / 1787 / 1787 全过)。
5. **同一份代码(f7b58db)再跑一遍总跑:全绿**(`r4-full-regression-recheck`,
   python **1793 全过**、e2e 41 PASS / 0 FAIL / 2 SKIP;rc=3 是那 3 条要活网关的没跑,
   与历史同形,不是红)。⇒ **一红一绿,间歇性坐实**。
   ⚠️ **两份收据都留着,不许拿绿的那份当"最终"** —— 带 `final=yes` 的是红的那份。

🔴 **我明确说不出来的那一半,不糊过去**:这一次 `40305` 上到底是**谁**在应答,
证据已经没了(进程早退)。两种可能后果完全不同:
- ① 判据自己的残留:b8 每轮的赢家 `sleep(120)` 不退、要等整条用例结束才被 reap,
  万一落进后面某轮的 5 个锁位里,**两份都让位是产品的正确行为**,错的是断言;
- ② 真 bug:没有任何实例在跑,而两份都误判"已有一份" ⇒ 业主双击两下**一个窗口都不开**。
  这正是本项目栽过的那一类(`release()` 的注释里写着同款事故)。

**处置**:本单**不修、不重跑到绿、不改那条判据**(它不是本单的模块,而且②这个可能性
还在桌上 —— 调它就是调钝报警器)。**记为待开单**:给 b8 加一条**失败当场取证**的诊断
(红的时候把那几个锁位上谁在监听、PID 是谁打出来),下一次再红就能一眼分出 ①②。
探针已经留在本 track 里给下一个人用。⇒ 与 [[opendesign-e2e-flaky-and-gateway-dep]] 同族账。

**⚠️ 所以本单的最终回归收据仍然是 rc=1,不是绿。** 归档时必须当面说清这一条,
不许拿上面那份 `r4-eligibility-mutants rc=0` 冒充"回归全绿"。

### 派发前的机械检查(第 4 轮,**这次落盘了**)

```
runlog: r4-preflight rc=1 commit=3dad391 dirty=no at=2026-09-20T08:40:48Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T084048Z-01-r4-preflight.txt
```
`BLOCK=1 PENDING=2 ERROR=0 OK=4`,逐条认账:
- **BLOCK views**(working 与 staged 不同):来自 preflight **自己刚写的那份收据**还没 `git add`。
  闸自己标了"(不需要重审)",已 add 并提交。
- **PENDING receipts 5b**:第 3 轮那份跑红的收据没被 verify.md 引用 —— **真账,已补**(见上)。
- **PENDING verdict**:`outcome.verdict=null`,正常 —— 主裁要等这一轮的报告读完才写。

🔴 **第 2、3 轮的 preflight 读数分别因断线和没落盘丢过两次;本轮起它走 runlog,
收据在上面这一行。** 这是本单要还的第一笔工艺账,今天还了。

### 第 4 次派发:**没拿到合格覆盖,记为基础设施重试**(并记我自己犯的一个错)

```
# impact-risk=high requested-budget=2 selected-count=3  escalation=failure  snapshot=head:d56fcad
submimo=PASS(verdict=PASS) subdeepseek=SKIP(rotation) subglm=SKIP(health:dead:auth:3) subkimi=FAIL(rc=1) subgemini=SKIP(health:dead:FAIL:6) subgrok=FAIL(rc=1) subcursor=SKIP(rotation)
```

两条腿死在基础设施上,原话在各自的 `.err` 里:
- **subkimi**:`403 You've reached your weekly (7-day) usage limit`(周额度,不是腿坏了)。
- **subgrok**:`Not signed in ... run: grok login --device-code`(**只有业主能做**)。
⇒ 只剩 submimo(xiaomi)一条给出裁决。high 要的是**同一次 panel、同一 subject digest 下
两个不同家族**的 coverage-eligible 腿 ⇒ **这一趟机械上拿不到覆盖**,按协议记为
**基础设施重试,不算实质评审轮**(预算未动)。

🔴 **我自己犯的错,记在这里**:我给 `panel-review` 传的是**相对**日志前缀,而当时 cwd 就是被审仓库
⇒ **22 个腿日志全被写进了被审仓库**(未跟踪)。引擎会把仓内未跟踪文件内联进评审 prompt
⇒ 反锚定被我自己破了(补进来的 submimo 起跑时,另两条腿的 `.err`、`.plan`、`.roster` 已在树上),
而且交付指纹里混进了这些日志。**这一趟因此双重不作数**:既没覆盖,树也不干净。
文件已全部移回 `/root/aiwork/logs/`,仓库复原干净后才重派。
⇒ 工艺账:日志前缀一律写绝对路径(这一条比"记得加"更稳的办法是下一单把它做成默认值)。

**submimo 这一份报告怎么处理**:留档(`/root/aiwork/logs/panel-startup-not-blocked-r4-20260920-1646.submimo.log`),
**不作为覆盖、也不作为"已被审过"的依据** —— 它是三轮三次孤票 PASS、且三次都被证明看漏了的那一家,
何况这一趟它读到的树是脏的。它报的 Q1~Q6 我会在下一趟的报告到齐后一并核。

## 第 4b 轮(重派,**本单最后一次派发**):两腿都 PASS,5 条 LOW

### 腿的花名册(机器打印,不手写)

```
# panel-review 花名册(2026-09-20 17:26:17)task=opendesign-startup-r4b-task
# impact-risk=high requested-budget=2 selected-count=2  escalation=none
# snapshot=head:7eeef79
submimo=PASS(verdict=PASS) subdeepseek=SKIP(rotation) subglm=SKIP(health:dead:auth:3) subkimi=SKIP(health:cooldown:rate_limit) subgemini=SKIP(health:dead:FAIL:6) subgrok=SKIP(health:dead:FAIL:3) subcursor=PASS(verdict=PASS)
```

机械覆盖**合格**:同一次 panel(`run_id=20260920-171426-1966509-panel-review`)、同一 subject
digest(`sha256:e920dfc4…`)、同一 delivery digest(`sha256:42853335…`)、同一 task 哈希;
两条腿 `rc=0`、`degraded=false`、`evidence.completeness=complete`、树干净
(`index_tree_oid == worktree_tree_oid == b9def4c8`);家族 **xiaomi + xai** = high 要的 2 个不同家族。

🔴 **但覆盖合格不等于覆盖有力,这一点我不粉饰**:这两家**正是前三轮已经看过这条链的两家**。
第 4 轮想换的 moonshot(周额度用光)与 xai-grok CLI(未登录)都死在基础设施上 ⇒
**这一轮没有一双新眼睛**。所以我不拿"两票 PASS"抬置信度 —— 本单的经验频率是
**submimo 三轮三次孤票 PASS、三次都被证明看漏**。这一轮真正有信息量的是 subcursor
那 5 条 LOW 和它对**我的探针**的那条纠正,不是它最后那个 PASS。

### findings 处置表(第 4b 轮)

| # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
|---|---|---|---|---|
| 24 | **LOW(subcursor)** apply 侧作废备货仍硬编码 `why_not == "attempted"`,而 prepare 侧用的是 `PERMANENT_BLOCKERS`;那段注释还写着 `no_shell / disabled / path_unsupported / asset / error` 都是**临时**条件 —— F4 之后这句话是假的(`path_unsupported` 已经是永久) | **成立**。我读了 `bin/ds_web.py:1198-1212` 与 `bin/ds_auto_update.py:100`:永久集含 `attempted / not_installed / path_unsupported`,apply 侧只认第一条,注释与之直接矛盾 | **延期**(后续单第一条) | 机械上是 dormant:startup 端点现在先问 `why_not_auto`,这两种永久否决下根本走不到 apply(el10/el12 钉住),业主遇不到。但**形状正是本单三轮反复栽的那一个**(同一个问题两处各答一遍),而且"注释不许说谎"是本单自己立的规矩 ⇒ 必须修,只是不在最后一轮动交付面 |
| 25 | **LOW(subcursor)** `prepare_update(..., paths=None)` 仍会回退成"只问账本那一维" —— F3 那个「可选参数 = 忘传就静默失效」的形状,我在 `startup_decision` 上删掉了,在这个函数上还留着 | **成立**。`bin/ds_update_startup.py:267-272`;生产唯一调用点 `bin/ds_web.py:1357` **一定**传 `paths`,且端点自己还有一道早闸(`:1339`)⇒ 生产无洞。漏的是**判据**:pr 卷那些调用不传 `paths`,因此测不到机器那一维 | **延期**(同一张单) | 改它要动既有 pr 判据的夹具(重写一批调用),不是最后一轮该做的事;腿自己也点明 E2 变异"两层闸一起拆才红"是纵深、不是摆样子 |
| 26 | **LOW(subcursor)** `bin/ds_web.py:911` 注释里的函数名 `machine_blocker` 已经不存在(第 3 轮改名成 `why_not_auto`) | **成立,且比它报的多一处**:我扫了全仓(`grep -rn machine_blocker`),代码里还有 `bin/ds_web.py:1342` 同样写着旧名字;verify.md 里那处是历史记述,正确 | **延期**(同一张单) | 「修一处先扫同类」这次兑现在我这一侧:腿报 1 处,我扫出 2 处 |
| 27 | **LOW(subcursor,打的是我自己的探针)** `b8-probe.py:36` 用 `range(base, base+5)` = 5 个槽,而 `InstanceLock._ports` 是 `range(base, base+span+1)`、`span=5` ⇒ **6 个槽**;落在 `base+5` 的"上几轮赢家"不会被我的残留统计看见 | **成立**。读 `bin/ds_shell_core.py:441-442` 与 `tracks/<t>/b8-probe.py:36`,差一个槽是实打实的 | **延期**(并进 b8 那张待开单) | 它削弱的是「残留不是原因」这一侧的排除力(我那句"25 轮 0 异常"要打个折),**但不动摇** b8「本单造不出它」的机械论证:本单全部代码没有任何 bind/listen,`DS_SHELL_LOCK_PORT` 在夹具里是写死的字符串常量 —— 这一条两条腿各自独立复核过 |
| 28 | **LOW(subcursor)** 变异集缺一个:没有"**只**把 `error` 加进 `PERMANENT_BLOCKERS`"的变异 | **成立**。`mutants-eligibility.py` 的 E8 加的是 `no_shell` + `disabled` | **延期** | E8 已经钉住"临时当永久"这一整类,缺的是同类里的一个成员;把它塞进最后一轮改判据的风险 > 收益 |

**没有 HIGH,没有 MEDIUM。** 六条重点里三条是我自己不确定的(第五个决策点 / 启动路径又被我挡住 /
`not_installed` 划永久),两腿**各自独立**给了同向的否定答案,且都给了可追的位置,不是"看起来没问题"。

### 这一轮我自己抓到的(腿没报,记账)

🔴 **`disabled` 不是业主的开关 —— 这话我在三处说错了,而且是我自己写进第 3 轮理由里的。**

- 事实:`OPENDESIGN_AUTO_UPDATE` 是**判据用的旋钮**,`tracks/archive/opendesign-auto-update-countdown/design.md:60,143`
  白纸黑字写着"只给判据用,不是业主设置"「业主机器上没人设它」。
- 业主界面上的那个开关是前端的 `update.autoCheck`(localStorage,`web/src/update.ts:84`、
  `web/src/App.tsx:120-121`)。关掉它之后 `probeStartup` **根本不跑**(`App.tsx:423`),
  60 秒那趟后台备货也不会被排上(它排在 `probeStartup` 的 ready 分支里,`App.tsx:383-416`)
  ⇒ **不会"照样弹、照样下 46MB"**。
- 我错在哪:`bin/ds_auto_update.py:68`、`bin/ds_web.py:1336-1339` 两处注释,以及我写给
  第 4 轮腿的任务书前情,都把这个测试旋钮说成"业主关掉自动更新的开关"。
- 影响:**产品行为没错**(两条路各自都对,`disabled` 该拒也拒了)。错的是我给 F1 写的
  **严重性描述** —— 我把一条只影响判据的维度,说成了"业主会亲眼看见的病"。
  F1 本身仍然成立:`no_shell` / `not_installed` / `path_unsupported` 这三种**真实**机器条件,
  改之前确实只在 apply 被问。
- 处置:**延期**,并进 #26 那张注释单(注释说谎是本单自己立的规矩,得一起修干净)。

> 记在这里的理由:这是本单**第四次**"我自己的规格/描述先错"(前三次:第 1 轮数据根、
> 第 2 轮"备货已清所以下次正常"、第 3 轮"资格收成一处"其实只收了一半)。
> 四次里有三次是外部腿或我自己的探针先抓到的,**没有一次是"我又读了一遍代码"读出来的**。

### 归档前的机械检查(第 4b 轮)

```
runlog: r4b-archive-preflight rc=1 commit=7eeef79 dirty=yes at=2026-09-20T09:29:34Z file=tracks/opendesign-startup-not-blocked-by-update/evidence/20260920T092934Z-01-r4b-archive-preflight.txt
```

🔴 **这一份 rc=1(BLOCK=2)。我贴出来,并且说得出它为什么不算数 —— 靠复现,不靠解释。**
两条 BLOCK 都是 **`runlog` 自己制造的**,不是交付内容出了问题:

- `runlog` 用 noclobber **先占位**建好收据文件并写入头部,**跑完命令才追加那行 `runlog: …`**
  (`/root/aiwork/bin/runlog:138-166`);
- 而交付投影跳过收据要**同时**满足两条:以 `# runlog receipt ` 开头 **且** 含一行 `runlog: `
  (`/root/aiwork/bin/_review_delivery.py:85-88`)。跑命令的那一刻只满足第一条 ⇒ 这份**半写**收据
  被当成普通内容计进交付 ⇒ working 的 delivery digest 变了 ⇒ 评审绑定判 BLOCK,
  `views` 也跟着判 working≠staged。

**复现(我量的,不是推的)**:

| 树的状态 | working delivery digest |
|---|---|
| 半写收据(只有头)在树上 | `sha256:4c526532…` ⇒ 与腿绑定的对不上 |
| 给**同一份**收据补上 `runlog: ` 行 | `sha256:42853335…` ⇒ **与两条腿绑定的完全一致** |
| 删掉探针文件 | `sha256:42853335…` |

并且**不经 runlog** 直接跑 `track preflight`:`decision: OK`
(`status=preflight-clear phase=preflight verdict=PASS`)、`views: OK(同一份交付内容)`,
只剩 5b 那条 PENDING —— 它要求的正是"把这份红收据引用出来并认账",也就是现在这一段。

⇒ **工艺账(归 aiwork 仓,不在本单动工具)**:用 `runlog` 包任何会读 working 交付视图的检查
(`track preflight` / `track-record validate --phase dispatch`),**必然自判两条假 BLOCK**。
两个修法方向:① 投影把"有头、还没有收据行"的半写收据也按收据跳过(那一刻它显然是本次 runlog 自己的);
② runlog 把占位文件建在仓外,跑完再落盘。**先记账**,第 4b 轮之后不再动工具面。

> 这条也是第 4 轮那份 `r4-preflight rc=1` 的真因。当时我把它记成"preflight 自己刚写的收据
> 还没 `git add`"——那只解释了 `views` 那一半,`decision` 那条我没看穿机制就放过去了。

## Accepted deviations

- **「60 秒后后台那一趟点火时重新问一次开关」没有自动判据。** 那 60 秒的延迟让 e2e 问不出它,
  而为了可测在产品代码里开一个测试专用旋钮不值得。只做了代码级自查。**不冒充有覆盖。**
- 3 条要活网关的 e2e 本轮没跑(与历史同形)。
- 上面第 7、第 10 两条延期项。

## 试行记录(review-convergence 试行)

- 总交付历时:2026-09-19 22:27(开工 commit)→ 2026-09-20 17:5x(归档 commit),约 19.5 小时(含一次断线接手与一次整轮重派)
- 每轮新增有效阻断:第 1 轮 3 HIGH + 3 MEDIUM(另 2 条驳回、2 条延期);
  第 2 轮 1 HIGH + 1 MEDIUM + 3 LOW(**其中 HIGH 正是第 1 轮第 10 条我判"延期"的那一条的第二步**);
  第 3 轮 1 HIGH(**本单引入的回归,打的是我第 2 轮那次"改抽象"本身**)+ 1 MEDIUM + 2 LOW;
  第 4 轮 —— 基础设施失败,无裁决;第 4b 轮 **0 条阻断 + 5 条 LOW**(全部核实成立、全部延期)。
  **曲线是收敛的**:HIGH 3 → 1 → 1 → 0,而且最后一轮的 5 条 LOW 里有 2 条打的是
  文档/探针而不是产品代码。
- 🔴 **第 2 轮最值钱的一条不是腿发现了新 bug,是它推翻了我上一轮的定性**:
  我写"备货已清 ⇒ 下一次打开一切正常"时只验了一步。这与 09-19 那单
  (我自己六条判据全绿而改动是坏的)是同一种失败:**我写的规格与我写的绿,互相证明不了对方。**
- 基础设施等待:**1 次整轮重派**(第 4 轮:subkimi 周额度 403 + subgrok 未登录 ⇒ 只剩 1 条腿,
  机械上拿不到 high 的两家族覆盖;记为基础设施重试,不计入轮次预算)。
  前三轮 0 次重试(冲突追加第三腿是协议内升级,不是重试)。
- 交付后返工:待填(业主真机之后)
- 🔴 **这一单最贵的一条**:连续两轮我都在**同一个问题**上判错 ——「这个问题该在哪一处答」。
  第 2 轮我把资格"收成一处"、实际只收了账本那一维;第 3 轮的 HIGH 打的就是那次重做本身。
  补丁打在末端、判据钉在旧的决策点,症状就原样回来(E8 那个漏网变异是同一个病的第三次现形,
  只不过那次是我自己的红检先抓到的)。

## arbitrated verdict(主裁)

**最终主裁:PASS**(2026-09-20 17:3x,第 4b 轮读完两份报告并逐条核实之后)。

- **机械门**:同一次 panel、同一 subject digest 下 2 条 coverage-eligible 腿、
  2 个不同家族(xiaomi / xai)、都 `rc=0` `degraded=false` `evidence=complete`、树干净
  ⇒ high 要的 0/1/2 预算里的 2 满足(花名册与 observation 收据在上面)。
- **我自己那一遍**(先过一遍再读腿的结论):四个决策点 —— `prepare` 早闸(`ds_web.py:1339`)、
  `prepare_update`(`ds_update_startup.py:268`)、`startup`(`ds_web.py:1394`)、
  `apply`(`ds_web.py:912` via `_auto_update_status`)—— 我**逐处读了原文**,确认都只问
  `why_not_auto`;前端没有第五处(`shouldAutoUpdate` 全仓只剩判据在调,`autoCheck` 问的是
  另一个问题:要不要走这条流程);启动路径新增的读盘有 **500ms 硬上界**
  (`STARTUP_LOCAL_TIMEOUT_MS`,超时一律进工作区),`update_preflight_problem` 我读完全文
  = 2 次 `isfile` + 纯字符串检查(+Windows 一次 `GetOEMCP`),**无网络、无子进程、不算哈希**。
- 🔴 **PASS 的依据不是"两票"**,是上面这一遍核实 + `mutants-eligibility.py` 的 **9/9 反向证据**
  (把新设计逐处改坏,判据会点名叫红)。本单三轮的教训正相反:全票不是护身符,
  submimo 三次孤票 PASS 三次都被证明看漏。
- **5 条 LOW 全部延期**,没有一条落在业主走得到的路径上;后续单的内容已经写死在上面的处置表里
  (注释/命名漂移 3 处、`prepare_update` 可选参数接缝、b8 取证 + 探针槽位、变异缺口)。
- **本单的承诺是否兑现**:启动路径不再联网查更新(sg1/sg5 钉死)、没有可装的新版就直接进工作区、
  只有盘上已下好且校验得过的新版才显示进度条。业主原话那件事(「每次打开都弹正在检测更新」)
  在代码面已经不成立。**欠的只剩真机回显** —— 这一条按本机规矩不算做完(见下面「交付状态」)。


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
