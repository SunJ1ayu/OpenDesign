# Verify: e2e-gateway-dependency

- Date: 2026-08-18
- Verdict: **PASS**

## Mechanical checks

- [x] build passes(无 build:只改 `tests/e2e/`;变异用的是 dist,已 `git checkout` 还原并核对)
- [x] tests pass —— e2e 总跑 36 PASS / 0 FAIL / 2 SKIP(rc=0)
- [x] no secrets / unsafe ops(改动=一段 `page.route` + 注释,产品代码零改动)

**机器打印的**(不是我的转述)——四种条件的收据,逐字节:

```
runlog: redcheck-A-before-nogateway rc=1 commit=aafd008 dirty=yes at=2026-08-18T06:40:36Z file=tracks/e2e-gateway-dependency/evidence/20260818T064036Z-01-redcheck-A-before-nogateway.txt
runlog: green-nogateway rc=0 commit=aafd008 dirty=yes at=2026-08-18T06:42:26Z file=tracks/e2e-gateway-dependency/evidence/20260818T064226Z-01-green-nogateway.txt
runlog: redcheck-B-mutant-connectcard rc=1 commit=aafd008 dirty=yes at=2026-08-18T06:43:14Z file=tracks/e2e-gateway-dependency/evidence/20260818T064314Z-01-redcheck-B-mutant-connectcard.txt
runlog: green-after-mutation-restore rc=0 commit=aafd008 dirty=yes at=2026-08-18T06:43:52Z file=tracks/e2e-gateway-dependency/evidence/20260818T064352Z-01-green-after-mutation-restore.txt
runlog: green-with-gateway rc=0 commit=aafd008 dirty=yes at=2026-08-18T06:44:19Z file=tracks/e2e-gateway-dependency/evidence/20260818T064419Z-01-green-with-gateway.txt
runlog: green-after-findings rc=0 commit=6dabd15 dirty=yes at=2026-08-18T06:59:38Z file=tracks/e2e-gateway-dependency/evidence/20260818T065938Z-01-green-after-findings.txt
```

| 收据 | rc | 它证明什么 |
|---|---|---|
| `redcheck-A-before-nogateway` | 1 | **改之前**、无 gateway ⇒ 2 FAIL。病是真的 |
| `green-nogateway` | 0 | 改之后、无 gateway ⇒ 2 PASS。**病好了** |
| `redcheck-B-mutant-connectcard` | 1 | 把 dist 里 `data-ui="connect-card"` 改名 ⇒ 2 FAIL。**判据仍咬得动,不是永远绿** |
| `green-after-mutation-restore` | 0 | 变异还原后回绿(`git checkout` + grep 双查:原标记 1、变异残留 0) |
| `green-with-gateway` | 0 | 改之后、**有** gateway ⇒ 2 PASS。**不再受环境摆布** |
| `green-after-findings` | 0 | **收完两条腿的发现之后**重跑 ⇒ 2 PASS(改了 glob 就必须重跑,不能拿改之前的绿交差) |

**权威的那一遍(默认口径 e2e 总跑,不带 `--with-gateway`)**:

```
runlog: e2e-authoritative rc=0 commit=ccb3a5c dirty=no at=2026-08-18T06:46:41Z file=tracks/e2e-gateway-dependency/evidence/20260818T064641Z-01-e2e-authoritative.txt
```

**36 PASS / 0 FAIL / 2 SKIP**,跑在干净树上(`dirty=no`)。对比**同口径的改前**
(08-18 上午 tmpdir-gate-followup 那单的权威收据):**34 PASS / 2 FAIL / 2 SKIP**
—— 差的正是本单这两条,从红转绿,**没有靠跳过换来的**(SKIP 数没变,仍是 2)。

> 那 2 SKIP 是 `NEEDS_GATEWAY` 名单里的 `new_chat` / `project-thread`,设计上就跳过。
> 总跑汇总自己如实印了「没有红的,但有 2 条没跑 —— **不算通过**」。本单没有动这个名单,
> 也**没有**把自己这两条塞进去(那才是把报警器关掉)。

## Review

- lane: **fast**
  > 判据:full 的硬触发器(新写口 / 权限 / auth / 钱 / 数据一致性)一条没碰 ——
  > **产品代码零改动**,只在两条 e2e 里加了一段 `page.route`。
  > **不判 self**:模板里 self 限"纯前端/纯观感、后端一字未动、只新增已过审针孔的调用方",
  > 而本单改的是**判卷防线本身**,风险不在那一档 —— 改判据最该怕的是"改成永远绿",
  > 那是要有人复核的事,不该我自己说了算。(变异红检已经堵了这一条,但那是我自己的证据。)
- 派给: **主 agent 直接干** —— 改的是判据,硬规矩「oracle 永远由主 agent 亲自写,绝不外包」。
  改动一段 route + 注释,写任务书的成本远高于自己动手。
- 规格自查(读任何 panel 输出之前先答,原文保留):
  这单的"规格"= **「让 e2e 进入登录态的正确做法是拦 bootstrap 回 401」**。
  它最可能错在:**401 这条路是否真的等价于"业主机器上的未连接态"**。
  如果不等价,后果是这两条 e2e 从"依赖环境"变成"测了一个现实中不存在的状态" ——
  那比原来的假红更坏(假红至少吵,假绿不吵)。
  我的依据是因果链三段都读了源码(`ChatPage:753` / `reconnect:88` / `connection:93`),
  且**探针实测**了无 gateway 时的真实界面(8s 后「连接不上」提示,连接卡不出现)。
  **但我必须记账:今天我在同一件事上已经判错过两次** ——
  先把"依赖活网关"当成既成事实写进归档工件(其实从没验证过),
  又把它判成"产品 bug"并向业主提了产品方案(其实产品是对的)。
  两次都是**读得不够就下结论**。所以这一格我给自己的信心打折,请腿重点看这条。
- 腿的花名册(原样粘自 `/root/aiwork/logs/panel-e2egwdep-0818.roster`):
  `submimo=PASS subdeepseek=PASS subglm=off subkimi=off`
  > **PASS = 进程 rc=0,不等于给了裁决** —— 两条腿的报告我都通读了,都真给了结论。
  > glm 因智谱账号欠费缺席(业主已订 opencode GO,接法查清但 key 还没给全,见记忆);
  > kimi 是我关的(`PANEL_KIMI_LEG=off`,额度)。fast lane 要主+1,这里实跑 2 条。
- findings(逐条仲裁,不认腿的自述):
  - **[接受并修] subdeepseek:注释里「进入 login 的**唯一**路径」不严谨。**
    **已核实,成立,而且比它说的更该改**:`grep 'setView({ kind: "login" })'` 只报两处
    (`ChatPage.tsx:224` / `:464`),第三处在 `:287` 是**三元表达式**里
    (`mode === "stopped" ? { kind: "login" } : ...`)—— grep 抓不到,
    正说明我当初写"唯一"时没看全。三处里 `:287` 只在 PasswordRejected 之后可达、
    `:464` 是主动登出,都到不了本 e2e 的全新加载场景,**所以修法不受影响**,
    但"唯一"这个词本身是错的。已改成"本场景下的路径"并把另外两处点名。
    > 顺带:`:287` 那段的原注释直接写着「视图永久停在『正在连接聊天服务…』⇒ 业主
    > 再也看不到未连接横幅、找不到填 key 的入口」—— 和我今天绕了一大圈才想明白的
    > 场景是同一个。**答案本来就写在代码里,我没读到那儿。**
  - **[接受并修] subdeepseek:`**/api/chat/bootstrap` 不匹配带 query 的 URL。**
    playwright 的 glob 全串锚定,将来谁给这个请求加 `?x=1`,拦截会**静默**失效
    ⇒ 两条 e2e 悄悄退回"看机器上有没有 gateway",**症状和本单刚修掉的一模一样**。
    已改 `**/api/chat/bootstrap*`。
    > **证据强度要如实标**:我没能独立实测 glob 语义(本仓 playwright-core 被打包,
    > 取不到 `globToRegex`;`find` 也没找到)。依据是 subdeepseek **自己写脚本跑出来的**
    > 输出 + Playwright 全串匹配的文档语义。加一个 `*` 是纯增益、零风险,故照收 ——
    > **但这条我是信了腿,不是自己验的,记在这里。**
  - **[接受,不改] subdeepseek [Info]:变异只覆盖"卡片不渲染",不覆盖"卡片在所有状态下都渲染"。**
    成立,且是这类 e2e 的设计固有边界(它只观察 login 态)。不是本单引入的洞。
  - **[接受,已补] subdeepseek [Info]:`green-with-gateway` 收据本身没有机器证据证明 gateway 真的起着。**
    属实。我是在终端看到 `✅ gateway 已起(8765)` 之后才跑的,但**那句话不在收据里** ——
    按本机规矩(查工件不查自述),这条收据对"有 gateway"这个条件是**不自证的**。
    腿也指出:因为拦截使结果与 gateway 无关,这不影响结论。**记账不掩盖。**
  - **[两条腿都独立复核并同意] 因果链三段** —— submimo 与 subdeepseek 各自读了
    `ChatPage:753` / `reconnect:88` / `connection:93` 并确认 401 造出的 login 态
    是产品里真实可达的状态(第一次装完没填口令就是它)。与我自审一致。
  - **[腿给的新信息,我核过] `bin/ds_web.py` 的 `_proxy` 会从 `~/.nanobot/config.json`
    注入 `Authorization: Bearer <pw>`** ⇒ 此前"白拿的 401"只在那份 config 没 token 时成立
    (如 run-all 的隔离 `$E2E_HOME`)。这让因果解释比我原来写的更精确。
    `page.route` 拦在浏览器侧、早于代理,所以不受影响。
  - **[我的自审发现,记账不改] `page.route` 是 page 级不是 context 级。**
    两条 e2e 各只开一个 page,够用;但将来谁加 `newPage()`,新页面不受拦截 ⇒ 又变回
    依赖环境、且症状一样。已在注释点明因果,**没加机械防护**。两条腿都没提这条。
- arbitrated verdict (主裁): **PASS**。
  产品代码零改动;因果链三段两条腿独立复核一致;四条件收据矩阵齐全,其中**变异红检**
  证明判据仍咬得动(这是改判据最该怕的事,已堵)。两条 Low 发现都成立、都已修并重跑绿。
  **两条腿一致 PASS 不构成我降低标准的理由** —— 我自己的孤发现(page 级 route)照样记账。

## Accepted deviations

- **`redcheck-B` 变异的是 `web/dist` 而不是源码**:e2e 加载的就是 dist,变异它更贴近
  真实加载路径,也省掉一次 build。风险是 dist 被改脏 ⇒ 已用 `git checkout` 还原,
  并用 grep 双查(原标记 1 / 变异残留 0),`git status` 干净。
