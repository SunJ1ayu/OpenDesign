# Verify: opendesign-update-duplicate-facts

- base-ref: b688389efd2c231458e4c8c027a80e7bb9eb93b3
- 交付面:`bin/ds_web.py`、`bin/ds_update_startup.py`(产品);
  `tests/test_ds_update_eligibility.py`、`tests/test_ds_update_startup.py`、
  `tests/test_comment_references.py`(新)、`tests/mutation-update-eligibility.py`(新,搬家+扩充)
- **业主可见行为:零变化**(不 bump 版本、不发布、不用重装)

## 一句话结论(主裁,待外审)

上一单延期的 5 条 LOW 全部做掉。第一性原理复核改了其中 3 条的修法,
并发现 4 条是**同一种病**:同一个事实写在两处 —— 正是上一单第 2/3 轮外审连着打的那条。

## 开工前:唯一能改方向的未知(D1)已用探针回答

判读规则写在**看结果之前**(A/B/C 三档,写在 `t0-apply-discard-reachability.py` 文件头)。

读数 ⇒ **B 档**:前端只在 `/api/update/startup` 回 `install` 时才调 apply 的 auto 分支
(`web/src/App.tsx:398-402`),而 startup 已把任何 blocker 改写成 `enter`
⇒ 正常链路走不到 apply 的作废分支;但端点暴露,直接调时那段代码**是活的**,
且改之前 `attempted` 清包、`path_unsupported` 不清 —— **不一致可观测,不是纯理论**。

`evidence/t0-apply-discard-reachability.txt`

🔴 这份探针**自己错过两次**,都记在 design.md:
① 第一版四个场景共用一个 data_root,第一个场景记的账污染了第四个;
② 我让它和变异红检**并发**跑 —— 那套红检原地改 `bin/` 下的源文件,
   探针读到的是被 E4 改坏的代码(`no_shell` 场景回了 `install`)。
两次都是**两次采样不一致**才暴露的。已把"红检跑着时仓库里不许跑别的"写进
`tests/mutation-update-eligibility.py` 文件头。

## 判据先行(commit `4ba29e8`,早于修复 `468ce61`)

runlog: redcheck-before-fix rc=1 commit=3439097 dirty=yes at=2026-09-20T11:17:39Z file=tracks/opendesign-update-duplicate-facts/evidence/20260920T111739Z-01-redcheck-before-fix.txt

修复前 6 条红(el16 两个 subTest + el17 + el18 + 注释闸两条)。

## 逐条:腿报的是什么、我核出什么、最后怎么修

| # | 上一单腿的说法 | 我复核 | **修法(改动处已标)** |
|---|---|---|---|
| 24 | apply 侧硬编码 `attempted`,注释说 `path_unsupported` 是临时 | 成立;并用探针定性为**纵深**而非主防线 | 改用 `PERMANENT_BLOCKERS`;注释**整段重写**,不再自带成员清单(那是第三份重复),并写明"这是纵深,正常链路走不到" |
| 25 | `paths=None` 是"忘传就静默失效" | 成立;**更深一层**:`data_root` 与 `paths["data_root"]` 是同一个事实的两个入口 | 🔧 **改了修法**:不是补参数校验,而是删掉 `data_root` 形参、`paths` 必填 |
| 26 | `ds_web.py:911` 一处旧名 | 成立,**我扫出 2 处**(`:1342`) | 🔧 改 2 处 + 新建通用闸 `tests/test_comment_references.py` |
| 27 | 探针少扫一个锁位,把 5 改成 6 | 成立(`_ports` = `span+1` = 6) | 🔧 **改了修法**:不写数字,从 `InstanceLock._ports` 推导 |
| 28 | 变异集缺"只把 error 加进永久集" | 成立,**而且补上之后当场漏网** | 补 E8b + 新写 el19 咬住它;整套搬到 `tests/` |

## 机器证据

### T5 资格变异:11/11 全部咬住

`evidence/t5-before-eligibility-mutants.txt`(改前 9/9)→
`evidence/t5-after-eligibility-mutants.txt`(改后 11/11,新增 E8b/E10)

🔴 **E8b 第一次跑是漏网的** —— 这正是 #28 报的洞:把 `error` 加进永久集
= "资格这一刻算不出来就把业主已经下好的 46MB 删掉",而当时**整卷没有一条判据会红**。
补 el19 之后咬住。第二次仍报漏网,是**我在变异表里写错了期望判据名**(写成 el15),
工具的"只认点名"纪律把我拦下 —— 它没有因为"反正有题红了"就放过。

### T6 判据没被改松(本单最硬的一道)

pr 卷 17 个调用点被重写,所以必须证明它没变弱:

- 变异表逐条 diff:**13 咬住 → 13 咬住**,无一条由红转绿
  (`evidence/t6-before-prepare-mutants.txt` vs `evidence/t6-after-prepare-mutants.txt`)
- 用例总数与 error:**37 → 37,0 error**(改前那次在 `HEAD=4ba29e8` 的临时 worktree 上真跑)
  runlog: t6-suite-parity rc=0 commit=4ba29e8 dirty=yes at=2026-09-20T11:35:51Z file=tracks/opendesign-update-duplicate-facts/evidence/20260920T113551Z-01-t6-suite-parity.txt

🔴 **T6 的对照组本身先修过**:直接跑归档那份 `mutants.py` 是 **12 咬住 + 4 条锚点失效**
(`evidence/t6-before-archived-script-asis.txt`)。拿一把 25% 是哑弹的枪去证明"我没改松",
证据力不够 ⇒ 本单做了工作副本 `mutants-prepare.py`:B1 锚点撞 2 处(加上下文钉死);
B3/B7/B8 打的代码**已经不存在**(su8 搬走、轮询调度器整段删掉,`grep -rn JITTER bin/` 0 命中)
⇒ 删。**删变异是减少报警器,所以每条都给了机械查法**,而且删前删后没动任何一条判据。
**归档原件一个字没改。**

### #27 b8 探针(修正槽数后重跑)

runlog: b8-probe-corrected-span rc=0 commit=4ba29e8 dirty=yes at=2026-09-20T11:36:36Z file=tracks/opendesign-update-duplicate-facts/evidence/20260920T113636Z-01-b8-probe-corrected-span.txt

14 轮 0 异常,且**每轮"落在本轮 span 里的上几轮赢家"都是「无」** ⇒
补上第 6 个槽之后,上一单"残留不是 b8 的原因"这条排除**依然成立**(不再需要打折)。
b8 的真因仍未知,**不修不调判据,继续挂着待开单**。

### T7 全仓扫

- `prepare_update(` 生产调用点只剩 `bin/ds_web.py:1363`(新签名);测试全部传 `paths`
- `machine_blocker` 在 `bin/` 下 0 命中(track 文档与那道闸自己的说明除外)

## 已知不承诺

- 注释闸只查 `ds_模块.名字` 这种**限定引用**,不查裸名字(中文注释里概念词太多,
  会把人养成 `--no-verify` 的习惯)。所以"以后不会再出现过期名字"**不在承诺里**。
- `tests/mutation-update-eligibility.py` 搬进 `tests/` 只是让它**找得到**,
  `run-all.sh` 不跑这一批(全仓的 mutation-* 本来就都是手跑的)。
- `path_unsupported` / `not_installed` 这两条永久否决在业主真机上**没被走到过**;
  本单改的是"走到了也对",不是"业主今天遇到了"。

---

## 派发记录

| 轮 | 类型 | 花名册 | 结果 |
|---|---|---|---|
| 1 | **实质评审**(预算 2 轮之第 1 轮) | `panel-updupfacts-20260920-1953` | submimo(xiaomi)PASS + subcursor(xai)PASS,`escalation=none`,`snapshot=head:34319af` |

```
submimo=PASS(verdict=PASS) subdeepseek=SKIP(rotation) subglm=SKIP(health:dead:auth:3) subkimi=SKIP(health:cooldown:rate_limit) subgemini=SKIP(health:dead:FAIL:6) subgrok=SKIP(health:dead:FAIL:3) subcursor=PASS(verdict=PASS)
```

🔴 **覆盖有力与否另说**:健康池现在只剩 3 条腿(submimo / subdeepseek / subcursor),
GLM 死于 auth(连 3 轮)、Gemini 死于 FAIL(连 6 轮)、Grok-CLI 死于 FAIL(连 3 轮)、Kimi 额度冷却。
轮换选中的两条**正是上一单第 4b 轮看过这条链的同两家**。机械预算满足(2 个不同家族、
同一次 panel、同一 subject digest、都未降级),但**没有一双新眼睛**,不拿"两票 PASS"抬置信度。

🔴 **反锚定**:派发时报了 `anchor leak` —— `tracks/<t>/verify.md` 当时是 `track new` 的**空模板**
(只有占位符,没有任何自审内容),正本自审在仓外 `/root/aiwork/tasks/…-my-review.md`。
如实记账:泄漏的是模板,影响判为零;但这一行报警是真的,不粉饰。

## 第 1 轮发现的处置

🔴 **顺序如实交代**:本轮我是"逐条核实 → 修 → 落处置表",而 4b ② 要求"核实 → **先落处置表** → 再动手"。
核实用的是实测(下表每行都有),但处置表确实是修完才落盘的。记在这里,不当没发生。

| # | 发现(谁报的) | 我的核实 | 处置 | 理由 |
|---|---|---|---|---|
| F1 | **subcursor**:`bin/ds_update_startup.py:34` import 注释说"只借 `auto_eligible`",而本模块已改用 `why_not_auto` + `PERMANENT_BLOCKERS` | **成立,且比它说的重**:我读了全模块,`ds_auto_update.` 的引用只剩那两个 —— **最后一处 `auto_eligible` 调用正是本单删掉的**,这句假话是我在 `468ce61` 里亲手造的 | **本单必须修** | 本单的立意就是"注释不许说谎",在交付面上自己造一条,不修等于自废。🔴 连带暴露:我新开的注释闸**看不见它**(裸名 `auto_eligible` 在别处仍存在)⇒ 闸的射程边界是真的 |
| F2 | **subcursor**:setUp 里 `os.environ.pop("OPENDESIGN_AUTO_UPDATE")` 没还原,会渗给同进程后面的判据 | **不成立**。那句在 `env.start()` **之后**,`mock.patch.dict` 是整份存、整份还原。实测:`off → None → off` | **驳回**,但**补一句注释** | 有代码依据 + 实测。腿会报它,是因为我的代码没说清为什么安全 —— 那是我的问题,不是它的 |
| F3 | **subcursor + submimo 各自独立**:`paths` 缺 `data_root` 键 ⇒ `state_path(None)` 算出**相对路径** `"None/Logs/update-state.json"`,打扫/写状态/下载全落进**当前工作目录**,不报错不抛照常返回 | **成立,已复现**:在空目录里真跑一次,盘上多出 `./None/Logs/update-state.json` | **本单必须修** | 生产走不到(端点用 `paths_for_update` 造 paths),但这是**一条静默写错地方的路径**,而业主机器上 cwd = 安装目录。正是本单在治的形状:宁可响亮失败,不要静默做错。🔴 我今天红检时其实先踩过同一个坑(仓根建出 `{'data_root': '/…` 目录),当时只当红检副作用,**没意识到那是产品代码的真实路径** |
| F4 | **subcursor**:注释闸正则 `[a-z_]` 看不见 `ds_web.Handler` 这种大写开头的名字 | **成立**。实测把大写放进正则后全仓**仍然 0 误报** | **本单必须修**(白捡) | 0 成本扩覆盖面,没有理由留着 |
| F5 | **subcursor** 列的其余射程缺口:模块整个被删则 `ds_foo.bar` 仍绿;裸名字要单点钉;"defined" 取的是文件里出现过的任何名字 | 成立,**且文件头本来就写着这三条** | **延期(不开单)** | 它们是"宁可漏不可误"的**有意取舍**,不是疏漏。在业主那边长成什么样:长不成任何样子 —— 注释过期不影响运行,只影响下一个读代码的人 |
| F6 | **submimo** 报告里写"10 条资格变异" | 实际是 **11** 条(当时),现在 12 条 | **记账,不影响裁决** | 与 09-20 上一单同一形态:MiMo 的 PASS 带事实小错。它的结论方向与我核实一致,但**数字不能直接引用** |

**修复清单(一次改完,commit `f49025c`)**:F1 注释说真话;F3 加守卫 + 判据 el20 + 变异 E11;
F4 正则放宽到大写;F2 补一句"为什么安全"的注释。

### 第 1 轮之后的机器复核

- 资格变异 **12/12 全部咬住**(含新 E11)`evidence/t5-after-r2-eligibility-mutants.txt`
- T6 与**改前**逐条相同 `evidence/t6-after-r2-prepare-mutants.txt`(13 咬住,无一由红转绿)
- 总跑 6 段全 PASS(python 1800 / node 461 / e2e 41 PASS 0 FAIL)
  runlog: run-all-r2 rc=3 commit=34319af dirty=yes at=2026-09-20T12:07:54Z file=tracks/opendesign-update-duplicate-facts/evidence/20260920T120754Z-01-run-all-r2.txt

## 收据认账(5b/5c)

**跑红过的那几份,一份不落**:

runlog: redcheck-before-fix rc=1 commit=3439097 dirty=yes at=2026-09-20T11:17:39Z file=tracks/opendesign-update-duplicate-facts/evidence/20260920T111739Z-01-redcheck-before-fix.txt

^ **这份 rc=1 是应该红的**:判据先行,四条新判据在修复之前必须全红(实得 6 条红)。

runlog: run-all rc=3 commit=468ce61 dirty=no at=2026-09-20T11:37:29Z file=tracks/opendesign-update-duplicate-facts/evidence/20260920T113729Z-01-run-all.txt

^ **rc=3 不是红**:总跑的约定是"没有红的,但有没跑的 ⇒ 不算通过"。3 条 = 1 条 python skip
+ 2 条要活 gateway 的 e2e,与历史同形。**我不把它写成"全绿"。**

runlog: t6-suite-parity rc=0 commit=4ba29e8 dirty=yes at=2026-09-20T11:35:51Z file=tracks/opendesign-update-duplicate-facts/evidence/20260920T113551Z-01-t6-suite-parity.txt

runlog: b8-probe-corrected-span rc=0 commit=4ba29e8 dirty=yes at=2026-09-20T11:36:36Z file=tracks/opendesign-update-duplicate-facts/evidence/20260920T113636Z-01-b8-probe-corrected-span.txt

runlog: prepare-smoke-real-server rc=0 commit=468ce61 dirty=yes at=2026-09-20T11:52:18Z file=tracks/opendesign-update-duplicate-facts/evidence/20260920T115218Z-01-prepare-smoke-real-server.txt

runlog: run-all-r2 rc=3 commit=34319af dirty=yes at=2026-09-20T12:07:54Z file=tracks/opendesign-update-duplicate-facts/evidence/20260920T120754Z-01-run-all-r2.txt

^ **最后一份,结论就依据它**。同样 rc=3,同样不写成"全绿"。

---

## 第 2 轮(最后一轮)派发记录

| 轮 | 类型 | 花名册 | 结果 |
|---|---|---|---|
| — | **基础设施重试**(断线,零实质产出) | `panel-updupfacts-r2-20260920-2043` | 20:46 会话断线,**两条腿连同驱动被整组 SIGTERM 砍掉**。submimo 的报告其实已写完(结论 PASS)、subcursor 死在第 3 行。**不拿它充数**:证据不跨 run 拼接,整轮重派 |
| 2 | **实质评审**(预算 2 轮之第 2 轮) | `panel-updupfacts-r2b-20260920-2145` | submimo(xiaomi)PASS + subdeepseek(deepseek)PASS,`escalation=none`,`snapshot=head:0fcfb47` |

```
submimo=PASS(verdict=PASS) subdeepseek=PASS(verdict=PASS) subglm=SKIP(health:dead:auth:3) subkimi=SKIP(health:cooldown:rate_limit) subgemini=SKIP(health:dead:FAIL:6) subgrok=SKIP(health:dead:FAIL:3) subcursor=SKIP(rotation)
```

- `ORACLE: python -m unittest tests.test_ds_update_eligibility tests.test_ds_update_startup tests.test_comment_references rc=0`(派发**之前**跑的,收据 `panel-updupfacts-r2b-20260920-2145.oracle.log`)
- 🔴 **这一轮终于换到一双新眼睛**:轮换选中 subdeepseek —— 第 1 轮与上一单 4b 轮都没有它。
  上面第 1 轮我记的「没有一双新眼睛」这条,本轮兑现了,而且它当场挖出两条别人没看见的。
- 🔴 **断线教训(第二次栽同一个)**:`panel-review` 的腿虽然各自 `setsid --wait`,但驱动仍在会话进程组里,
  断线 SIGTERM 打到整组 ⇒ 连腿一起死。本轮改用 `setsid -f` 把**驱动**脱到 PID 1(核过 `ppid=1`),
  断线砍不着。记忆 [[panel-legs-survive-disconnect]] 09-15 就写过这条,我派活时没落实。
- 反锚定:本轮报 `anchor leak: verify.md` —— **复审轮属预期**(4b ②:处置表是复审腿的已知输入)。

## 第 2 轮发现的处置

| # | 发现(谁报的) | 我的核实 | 处置 | 理由 |
|---|---|---|---|---|
| G1 | **我自己 + subdeepseek 各自独立**:el20 的射程只够 `{}` 一种形状。把守卫换成 `if not paths:`(我)或 `if "data_root" not in paths:`(它),**整卷 61 条一条不红**,而真实行为回到 F3 的原样 | **成立,两条独立变异各复现一次**。我的读数:变异树返回 `ok:True/ready`、真下了包、cwd 里建出 `None/`;干净树 `prepare_failed`、0 下载、cwd 干净(判读规则写在看结果之前)。证据 `/root/aiwork/logs/q2-el20-gap-readout.txt` + 探针 `q2-el20-gap-probe.py` | **延期** | 产品代码**是对的**(生产 `data_root` 恒为非空 str,我实测四种入参 + 两条腿各自验过)。它挡不住的是**未来某次把守卫改窄** ⇒ 正落在 4b「测试挡不住任意未来的错误实现,不自动扩大承诺」那一格。在业主那边长成什么样:**长不成任何样子**;在下一个改这段代码的人那边:他把守卫收窄成只查键存在,整卷不会红。**补法很便宜**(el20 加 `{"data_root": None}` / `""` / 非 str 三个子例 + 一条 E11b),写在这里供下一单直接抄 |
| G2 | **subdeepseek**:同一形状隔壁没守 —— `discard_ready(data_root)` 拿到 `None` 时 `state_path(None)` 照样算相对路径 | **成立,我自己复现**:干净树上 `discard_ready(None)` 在 cwd 里建出 `None/Logs/update-state.json`。三个调用点(`ds_web.py:1216/1229/1352`)的 paths 都出自 `paths_for_update` ⇒ **今天走不到** | **延期** | 不是本单引入(`discard_ready` 本单一个字没动),今天不可达。与 G1 同批,补的时候一起补 |
| G3 | **subdeepseek**:守卫注释里「宁可**响亮**地失败」在生产调用点上不成立 —— `ds_web.py:1363` 把 `prepare_update` 的返回值丢了,而且跑在后台线程里,端点早就回了 `started: True` | **成立**,我读了 `:1358-1370` 确认:返回值无赋值、`work()` 在 daemon 线程里、`self._json(200, {"started": True})` 在起线程之后 | **延期(记账)** | 与 F1 有**实质区别**,不按 F1 那条"注释说谎必须修"处理:F1 说的是**一句可证伪的代码事实**("只借 auto_eligible",而那个调用已被我删掉);G3 那句是**取舍原则**("宁可 A 不要 B"),它选的那一侧是真的(失败时不写错地方),只是"响亮"这个词没人听得见。报它的腿自己也标了 informational。**不拿"立意是注释不许说谎"把原则句和事实句混成一档** —— 那样下次就会为了措辞再烧一轮 |
| G4 | **submimo** 对 Q2 答"**Yes,不存在 el20 绿而真实备货坏的情形**" | **这句是假的**,被 G1 的两条独立变异各证伪一次 | **记账,不影响裁决** | 🔴 **MiMo 的 PASS 第三次带事实错误**(09-16 一次、09-20 上一单一次),而且这次不是数字口误,是**我问的那个问题正中心的一句全称判断**。它的方向结论与我一致,但**它的断言一句都不能直接引用**。这也再次坐实:两票 PASS 不抬置信度 —— 真正有价值的是那条新眼睛独立跑出来的反例 |

### 更正:上面第 1 轮那段话说大了

第 1 轮我写「资格变异 12/12 全部咬住(含 E11 钉 F3 的守卫)」。**E11 钉的只是"守卫还在不在",不是"守卫问得对不对"**
(它整条删掉守卫)。G1 证明:守卫仍在、只是问错了问题时,E11 照样绿。
措辞更正就地做在 verify.md(本文件在交付投影的豁免清单里,改它不作废本轮评审绑定,也不花一轮)。

## 主裁最终裁决:**PASS**

- 交付面(`bin/ds_update_startup.py`、`bin/ds_web.py`)无真实阻断:三条发现全部"今天走不到",且产品行为经
  两条腿 + 我自己各自独立核实为正确。
- 机械门:high ⇒ 预算 2,同一次成功 panel(`r2b-20260920-2145`)、同一 subject digest 下
  两个 coverage-eligible 的不同家族腿(xiaomi + deepseek),无降级、无冲突。
- 轮次预算(开工时写的 2 轮实质评审)**用完即止**:G1~G3 均为延期项,按 4b ④「无真实阻断 + 机械门满足 ⇒ 结束」收口,
  **不追加第 3 轮**,也不自动开新单。
