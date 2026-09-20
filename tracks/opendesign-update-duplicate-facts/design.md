# Design: opendesign-update-duplicate-facts

- Change: opendesign-update-duplicate-facts
- Status: draft

## Goal-to-design check

### 当前行为 → 拟改变的行为

业主可见行为:**不变**。全部改动落在 `bin/` 的两处注释、一处常量引用、一处函数签名,
以及本单自己的两个判据脚本。

### 检查深度与触发事实

**直接验证(我自己读代码逐条复核)+ 一次最小实验(探针重跑)**,不做方向探索。
理由指向行为与撤回代价:没有新写口、没有新的用户必经步骤、没有契约跨模块变化;
`prepare_update` 的签名是**模块内**契约,生产唯一调用点在同仓 `bin/ds_web.py:1357`;
全部改动一个 `git revert` 可撤。
🔴 但有**一处不轻量**:#25 要重写既有 pr 卷的 ~24 个调用点 —— 那是动判据本身,
是"调钝报警器"的高危面,所以它单独配了一道机械闸(见 oracle 第 4 条)。

### 关键前提(可证伪的主张 → 我的证据)

| # | 主张 | 证据 | 结论 |
|---|---|---|---|
| P1 | 5 条今天都还在代码里 | 逐条读:`ds_web.py:1209`(硬编码 `"attempted"`)、`:1198-1205`(注释称 `path_unsupported` 临时)、`ds_auto_update.py:100`(永久集含它)、`ds_update_startup.py:267-272`(`paths is not None` 分支)、`ds_web.py:911` 与 `:1342`(旧名)、`b8-probe.py:36`(`base+5`)vs `ds_shell_core.py:441-442`(`span+1`=6)、`mutants-eligibility.py:43-46`(E8 加的是 `no_shell`+`disabled`) | **全部成立** |
| P2 | #24 今天走不到(dormant) | `_update_startup` 里 `action=="install"` 后问 `why_not_auto`,任何 blocker 都改写成 `enter` ⇒ 永久否决下 apply 的 auto 分支进不去 | **成立**,但见 D1 |
| P3 | #24 改后不会误删业主的包 | 作废分支在 `if auto_request:` 内 ⇒ 手动更新不受影响(el6);新集合只比旧的多 `not_installed`/`path_unsupported`,两者都是"这一版在这台机器上再也不会自动装" | **成立**(待 el 卷重跑坐实) |
| P4 | #25 生产无洞 | 唯一生产调用点一定传 `paths`,且端点自己在 `ds_web.py:1339` 还有一道早闸 | **成立** ⇒ 这条修的是**形状与判据覆盖**,不是活 bug |
| P5 | `data_root` 与 `paths` 在生产调用里是同一个事实 | `ds_web.py:1325-1357`:`root = paths.get("data_root")`,然后 `prepare_update(info, root, paths=paths)` | **成立** ⇒ 见 A2 |
| P6 | 改归档里的脚本是不可接受的 | 归档 = 已 PASS 的历史收据;编辑它会让"当时量到什么"不可复现 | **成立** ⇒ 复制进本单再改 |

### 完全实现仍可能失败(用户目标落空的具体场景)

- **最可能的失败不是代码错,是我把判据改松了**:pr 卷 24 个调用点重写后全绿,
  但绿得比以前容易 —— 业主眼里一切正常,直到下一次真出事时那卷卷子接不住。
  接得住它的不是"断言写没写",是 oracle 第 4 条那份**变异红绿逐条对照表**。
- #24 把作废集合放宽后,如果 P2 哪天不再成立(有人把 startup 那道闸改了),
  业主可能在一个"其实条件会恢复"的情形下被删掉 46MB 要重下。el4/el13/el15 钉着临时条件不许删,
  但"哪些算永久"这个判断本身变成了单点 —— 这是**有意的取舍**(单点但唯一,好过两点且不一致)。
- #27 重跑后若读数变成"残留确实罩住了赢家",那 b8 的真因就指向题面;本单**不追**,只记录。

### 独立意见与核实

上一单第 4b 轮 subcursor 提的 5 条,我全部**自己读代码复核过**(P1),但**修法我改了 3 条**:

| 条 | 腿建议的修法 | 我的修法 | 为什么改 |
|---|---|---|---|
| #25 | 给 `prepare_update` 补参数校验 | **删掉 `data_root` 形参**,改成 `prepare_update(info, paths, ...)`,内部推导 | 腿看见的是"可选参数会静默失效";第一性问一层:这函数为什么同时收 `data_root` 和含 `data_root` 的 `paths`?**重复本身才是根**。只加校验是在重复之上再加一道 |
| #27 | 把 `base+5` 改成 `base+6` | 改成**从 `InstanceLock` 推导 span**,不写数字 | 改成 6 只是把抄错的数字抄对;下次 `span` 一改又错。同一种病 |
| #26 | 改 `ds_web.py:911` 一处 | 改 2 处(我全仓扫出 `:1342`) | 「修一处先扫同类」 |

#24/#28 按腿的方向做,但 #24 的注释要**整段重写**(不是改一个词):那段话现在把
`path_unsupported` 列在"临时"里,而它已经是永久的 —— **注释里的清单本身就是第三份重复**,
重写后不再复述成员名单,只说"永久集由 `PERMANENT_BLOCKERS` 一家定"。

### 未解决项 → **D1 已用探针回答(2026-09-20,开工前)**

探针 `t0-apply-discard-reachability.py`,判读规则写在看结果之前(A/B/C 三档写在脚本文件头)。
收据 `evidence/t0-apply-discard-reachability.txt`。读数:

| 场景 | startup | 真实链路走到 apply? | 直接 POST apply | 进了作废分支 | 包 |
|---|---|---|---|---|---|
| attempted | enter(reason=attempted) | **否** | auto_skipped | **是** | 删掉 ✓ |
| path_unsupported(永久) | enter(reason=path_unsupported) | **否** | auto_skipped | **否** 🔴 | 留着 ✗ |
| no_shell(临时) | enter(reason=no_shell) | **否** | auto_skipped | 否 ✓ | 留着 ✓ |
| 干净 | **install**(reason=ready) | **是** | (busy,已在装) | 否 ✓ | 装了 ✓ |

**判定 = B 档**:前端只在 `startup` 回 `install` 时才调 `applyUpdate(true, …)`
(`web/src/App.tsx:398-402`,我读过),而 startup 已经把任何 blocker 改写成 `enter`
⇒ **正常链路走不到 apply 的作废分支**;但 apply 端点本身是暴露的,直接调时那段代码是**活的**,
且此刻 `attempted` 会清包、`path_unsupported` 不会 —— **#24 那条不一致在这里是可观测的,不是纯理论**。

⇒ #24 **按 B 档做**:改常量(`== "attempted"` → `in PERMANENT_BLOCKERS`),
注释改成明写"这是纵深:正常链路 startup 已经拦掉了",**不许再暗示它是主防线**。

🔴 探针第一版自己有 bug(四个场景共用一个 data_root,第一个场景记的账污染了第四个 ⇒
"干净"场景回 `reason=attempted`)。**是探针错不是产品错**,证据是那个 reason 正是上一场景写的值;
已改成一个场景一个 test 方法(一个全新 data_root)重跑。记在这里是因为本单的立意就是
"同一个事实别写两处"——而探针那版是"同一份状态被四个场景共用",同一种病的第六个样本。

🔴 **第二次采样又被污染了一次,原因不同,值得单独记**:我在变异红检**还在后台跑**的时候
重跑了探针。那套红检是**原地改 `bin/` 下的源文件、跑完再改回来**的 ——
于是探针读到的是被 E4(「资格判据漏掉 no_shell」)改坏的代码,`no_shell` 场景回了 `install`。
两次采样不一致才让我发现。**工艺规矩:变异红检跑着的时候,这个仓库里不许跑任何别的判据或探针。**
第三次在干净树上重采,读数与第一次(修好隔离后的那次)逐格相同,上表用的是它。

### 开工前的两张基线表(T6/T5 的"改之前")

- `evidence/t6-before-prepare-mutants.txt`:**13/13 全部咬住**。
  🔴 直接跑归档那份是 **12 咬住 + 4 条锚点失效**(B1 撞 2 处;B3/B7/B8 打的代码已被删)——
  收据 `evidence/t6-before-archived-script-asis.txt`。
  修锚点/删过期变异的全部理由写在 `mutants-prepare.py` 文件头,每条都给了机械查法。
  **归档那份一个字没动。**
- `evidence/t5-before-eligibility-mutants.txt`:资格卷变异的改前读数(T5 的对照组)。

## Approach

一句话:**把这 4 份重复各自收成一处,第 5 条(#28)给报警器补上缺的那一发子弹。**

1. **#24** `ds_web.py`:`auto.get("why_not") == "attempted"` → `in ds_auto_update.PERMANENT_BLOCKERS`;
   注释整段重写,不再自带成员清单。
2. **#25** `ds_update_startup.py`:签名 `prepare_update(info, paths, download=None, now=None)`,
   内部 `data_root = paths.get("data_root")`;删掉 `elif auto_eligible(...)` 那条半维回退。
   两卷 pr 判据的调用点改为传一个 `paths` 夹具(默认让机器那一维放行),行为断言一字不改。
3. **#26** 两处注释旧名 → `why_not_auto`;并全仓扫一遍"注释提到但 `bin/` 里不存在的标识符"这一类。
4. **#27** 探针复制进本单,`span` 从 `ds_shell_core.InstanceLock` 推导;重跑取正确读数。
5. **#28** 变异集复制进本单,补 `("E8b", 只把 error 加进 PERMANENT_BLOCKERS)`;**整套对改后代码重跑**。

## Key trade-offs / risks

- **单点判断**:"哪些否决是永久的"收成唯一一处后,那一处错 = 三个决策点一起错。
  取舍理由:上一单的血账正是"两处不一致"连着造了两轮回归;单点且唯一 > 两点且漂移。
- **动判据**:#25 要重写 ~24 个调用点。用变异红绿对照表兜住(oracle 第 4 条)。
- **#24 放宽的是一条删文件的路径**。dormant + 只在 auto 分支 + el 卷钉着临时条件不许删。

## Alternatives considered

- **#24 直接删掉 apply 侧的作废分支**(让 prepare 一家管):否决 —— el4b 钉着
  "attempted 必须作废包",删了它就得把那条判据也改,那是在动判据迁就实现。
- **给"注释里的过期标识符"做机械守卫**(pre-commit 扫注释里的 snake_case token 是否存在于 `bin/`):
  否决 —— 中文注释里大量出现的是概念词不是标识符,误报率高到会被养成"一律 --no-verify"的习惯,
  那比没有守卫更坏。本单只做一次性清扫 + 在承诺里明说不承诺"以后不会再出现"。
- **把 5 条拆成 5 张小单**:否决 —— 它们是同一种病,合在一起才看得见共同根因。

## Test strategy (oracle)

主 agent 亲写,**先单独 commit,再 commit 修复**。

- **T0(开工前先答 D1)**:一卷"apply 侧作废分支到底还走不走得到"的探针 —— 直接调端点,
  分别在 `attempted` / `path_unsupported` 下走 auto 链,打印**是否进入 apply 的作废分支**。
  结论决定 #24 是改常量还是改结构。**判读规则写在看结果之前**:
  `attempted` 能进 ⇒ 是活的纵深,改常量;两个都进不去 ⇒ 死代码,本单改为明写纵深意图 + 加一条钉住
  "startup 拦住了它"的判据,而不是给死分支抛光。
- **T1(#24)**:新增 el 判据 —— 在 `path_unsupported` 下走到 apply 的 auto 分支时,包必须被清掉;
  在 `no_shell` / `disabled` 下必须留着。红检:改回 `== "attempted"` 必须红。
- **T2(#25)**:① `prepare_update` 少传 `paths` 必须**立刻报错**,不许静默少做检查
  (红检:把参数改回可选必须红);② 新增一条"机器那一维在 prepare 里真的被问了"的判据
  —— 这是旧夹具**测不到**的那一半。
- **T3(#26)**:一条机械判据:`grep -rn machine_blocker bin/` 必须 0 命中。
- **T4(#27)**:探针自己打印 `span` 的来源与长度,且断言 `len(span) == InstanceLock(...)._ports` 长度。
- **T5(#28)**:变异集整套对改后代码重跑,**每一条都必须红**(包括新补的 E8b)。
- **T6(第 4 条承诺,本单最硬的一道)**:pr 卷夹具重写**前**先跑一次全套变异、存下红绿表;
  重写**后**再跑一次;**逐条 diff**。任何一条由红转绿 ⇒ 本单失败,不许用"那条本来就弱"解释过去。

**这个 oracle 能被什么骗过?**

- 业主眼里的成功是"一切照旧"。我的断言全绿、而自动更新在真机上坏了,会错成:
  `prepare_update` 签名改了,但某个我没扫到的调用点(打包脚本/别的入口)还在按老签名调
  ⇒ 后台备货整条静默死掉,**业主要到下一次发版才发现更新不来了**。
  接住它的不是单测:是 **T7 —— 全仓 `grep -rn "prepare_update("` 必须 0 个老签名调用点**,
  外加本地真起一次 ds-web 走一遍 `/api/update/prepare` 看它真的备货(不是 mock)。
- 第二种骗法:T6 的对照表我**只跑了变异、没跑"夹具改错导致整卷 error"**。
  一卷 24 个用例集体 error 也叫"没有由红转绿"。所以 T6 的通过条件写成
  **红绿表逐条相同 + 两次的用例总数相同 + 0 error**。
