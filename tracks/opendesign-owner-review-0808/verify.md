# Verify: opendesign-owner-review-0808

- Date: 2026-08-08
- Verdict: **PASS**(主 agent 亲自裁决,2026-08-08;依据见文末「主裁段」——
  五次变异测试 + 覆盖 HEAD 的收据 + 逐条读腿的原始日志,不采信执行方的转述)

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] build passes(`npm run build` 干净;总跑第②遍的「dist 新鲜度」段绿)
- [x] tests pass(node 342/342、python 949/949+死断言全绿、MCP 契约闸全绿、
  e2e 33 PASS/0 FAIL——2 条 SKIP 是需要活 gateway 的既有默认行为,与本 track
  改动无关,见下方 Accepted deviations)
- [x] no secrets / unsafe ops(本 track 未碰密钥/生产系统/依赖安装;所有改动
  在这个 git 仓库本地历史里,未 push)

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,收据行原样粘在这里:

```
runlog -t opendesign-owner-review-0808 --repo . -- tests/run-all.sh
```

**跑了三遍,一遍都不藏**(规矩 5b:跑红的那几遍一份都不许藏):

**第①遍**(实现代码已写完、但 `web/dist` 还没跟着重建/提交时跑的——**这一遍是红的**,
红的原因是"dist 新鲜度"段,其余四段当时已经绿):
```
runlog: run-all rc=1 commit=582ddea dirty=yes at=2026-08-08T14:08:22Z file=tracks/opendesign-owner-review-0808/evidence/20260808T140822Z-01-run-all.txt
```

**第②遍**(实现 commit `a0b15e4` 落盘之后重跑,五段全绿;rc=3 不是失败——是
`run-all.sh` 自己的"没跑的不算过"规矩:2 条需要活 gateway 的 e2e 按脚本默认行为
SKIP,不在本 track 改动范围内):
```
runlog: run-all rc=3 commit=a0b15e4 dirty=no at=2026-08-08T14:16:44Z file=tracks/opendesign-owner-review-0808/evidence/20260808T141644Z-01-run-all.txt
```

**第③遍(权威的一遍,覆盖真实 HEAD)**——四审 Kimi 的孤发现逼出来的:第②遍那份
收据停在 `a0b15e4`,而后来还有 `5d2cf86`(补 `test_dc10`)和 `e3460d4`(修文档漂移)
两个 commit **没有任何 machine-printed 运行覆盖过**;python 那个 949 里根本不含
`test_dc10`。补跑之后是 **950**,正是 Kimi 预测的数字:
```
runlog: run-all rc=3 commit=e3460d4 dirty=yes at=2026-08-08T14:49:10Z file=tracks/opendesign-owner-review-0808/evidence/20260808T144910Z-01-run-all.txt
```
(`dirty=yes` 的原因是跑的时候 evidence/ 里前两份收据和这份 verify.md 本身还没
commit —— 收据文件会弄脏工作树,是 runlog 的已知形状,不是有未提交的代码改动。)

三份完整输出都在 `tracks/opendesign-owner-review-0808/evidence/`。汇总数字
(以第③遍为准,供人眼核对,**权威仍是收据文件本身**):
node 342/342 · python **950/950**(死断言检查:0 条从未执行) · MCP 契约闸三条全绿 ·
dist 新鲜度绿 · e2e 33 PASS / 0 FAIL / 2 SKIP(new_chat.e2e.mjs、project-thread.e2e.mjs,
需要 `--with-gateway`,与本改动无关)。

> ⚠️ **我自己在这一格犯过的错,留痕**:这段原来写的是"两份完整输出都在 evidence/,
> **已进 git(commit `a0b15e4`)**" —— 假的。`a0b15e4` 只带进了第①遍那份收据,
> 第②遍是在那个 commit **之后**跑的,从来没被提交过。我写了一句关于"证据在不在
> 版本控制里"的陈述,而它本身没被核实。这正是 machine-evidence-gate 那一单要防的
> 形状,只不过这次犯在**元层**(不是判据结果造假,是"证据已归档"这句话造假)。
> 三份收据现在都在本 commit 里。

oracle-first commit:`b8e5114`(byte-diff 核对见下方 findings F3)。

## Review

- lane: full
  > delete_change 是全新的写操作(单条变更软删除),碰了新写口 —— 硬规矩,不降档。
- 派给: 主 agent 直接干(偏离了 tasks.md 原定的「codex/gpt-5.5」)。
  > 原因:开工前设计阶段(design.md)已经把每个改动的确切文件/函数/行为逐条钉死
  > (定位复用 set_change_status 的 line_re、展示层要改哪两处、前端按钮插在
  > TodoPage.tsx 哪一行),写一份能让 codex 独立干活的任务书,信息量已经约等于
  > 直接实现——"切碎反而更贵"(delegate skill 原话)。执行这段的是同一个已经
  > 带着完整上下文的 agent(fork),不存在"省 Claude 额度给规划"的取舍前提
  > (那是主会话调外部腿才有的量)。收货仍按三道硬闸走(diff/亲跑/亲读),
  > 只是没有"外部腿"这一环,直接对着 oracle 自己实现自己核对。
- 规格自查(读任何 panel 输出之前先答):
  design.md 的核心赌注是"软删除 = 状态位改成『已删除』,展示层各自过滤"这条路线
  比"物理删行"或"另建 trash 文件"更省事、更贴合现有账本语义。**如果这条赌注本身
  是错的**,最可能错成这样:某处扫描变更行的代码,以后新增功能时忘了排除"已删除"
  (design.md 已经预见到这点,靠的是"让它对解析器可见、由每个读侧自己过滤"而不是
  "让它对解析器隐形"——但"每个读侧自己过滤"这句话本身就意味着**过滤点不止一处、
  容易漏改一处**)。我怎么发现:目前只有两个读侧(`ds_todo.OPEN_STATUS` 天然不含它、
  `ds_web._changes` 显式排除),`grep -rn 'parse_change\|CHANGE_RE' bin/` 能拉出全部
  调用点,以后新增第三个读侧时**必须过一遍这张清单**——这件事现在只写在代码注释里,
  没有机械闸守着,是个真实的、留给未来的手工纪律,不是这次能一次性堵死的。
  另一处赌注:5b 那条新规矩("工具够不着就必须先问")会不会和已有的规矩 7
  ("缺工具的操作别硬凑,先讲清残局")重叠——如果重叠,规矩集只是又厚了一条,
  没有新增约束力。这条我没有把握说规格是对的,留给 panel/主 agent 判断,见下方 findings。
- 腿的花名册(原样粘自 `/root/aiwork/logs/panel-opendesign-owner-review-0808.roster`):
```
submimo=PASS subdeepseek=PASS subglm=off subkimi=PASS
```
  > `PASS` = 进程 rc=0 且给出了 `Conclusion: PASS`(三腿都真给了裁决,不是只跑完没结论);
  > `subglm=off` = 这条腿**压根没派**(欠费期间默认 off),不许读成"它也通过了" —— 所以
  > 本轮实际是**三腿**,不是四腿。
  > `ORACLE: ... rc=0` 也记在 `.oracle.log`(派发前先跑,防"三家一起给坏 oracle 判 PASS")。

- ⚠️ **反锚定泄漏,实锤发生了(方法论缺陷,记账)**:派发时控制台就报了
  `WARNING: anchor leak — tracks/opendesign-owner-review-0808/verify.md`,
  而 Kimi 的日志里**直接引用了我的自审原文**("verify.md:64-67 自己也承认
  『未来新增读侧没有机械闸』属实")。也就是说这一轮至少 Kimi 那条腿**看得见我的
  findings**,它的"独立"打了折扣 —— 它可能只是在复述我的怀疑,而不是独立发现。
  panel skill 明写过正确节奏是"**先派发、后写 verify.md**",我做反了。
  **这不影响本轮结论**(三腿的实质发现都是我 verify.md 里**没有**写过的东西 ——
  design/tasks 三处文档漂移、HEAD 没有收据,全是新的),但下一单必须先派发再写 verify。
- findings:

  **我自己先审出来的(写在读任何 panel 输出之前)**
  - **F1 AGENTS.md 新规矩 5b 与既有规矩 7 可能语义重叠**——我自己判断不了,主动交出去。
    → **三腿全部独立回答了这条,且结论一致:该保留两条,不冗余。** 而且两腿给出的
    区分理由**比我自己写的更准**:我只说了"5b 更窄",DeepSeek 指出真正的区别是
    「7 管替代方案的**后果卫生**(可以提替代,但要讲清残局),5b 管替代前的**许可边界**
    (换不换由用户定)」;Kimi 更进一步、给了我没想到的一刀:**08-08 那次顶替
    (拿"标完结"冒充"删除")是干净可逆的,按规矩 7 的字面"会留下清不掉的东西才默认不做"
    根本没被禁止 —— 那个漏洞正是 5b 存在的理由**。我接受这条,并接受两腿的编辑建议:
    在规矩 7 末尾加一句交叉引用(**未做**,见下方"留给主 agent"）。
  - **F2 proposal.md 的 Non-goals 没显式写"只在待办页加删除按钮"**——范围边界是在
    design 的执行细节里默认划定的,不是显式确认的。功能无 bug(工作区变更栏没有删除
    按钮,但已删除条目照样从那里消失,因为共享同一个被过滤的端点)。三腿都没提这条,
    **但它依然成立**(腿的沉默不是放行)——这是我一个人替设计师做的范围判断。
  - **F3 `_rewrite_change_status` 重构未改变 `set_change_status` 既有行为**(核实通过)。
    oracle byte-diff:`git diff b8e5114 HEAD -- tests/` 只有一处新增(`test_dc10`,
    见 `5d2cf86` 的自曝说明),其余判据文件逐字节未动;`git status --porcelain -- tests/`
    也为空(闸①的"未跟踪文件"那半边)。
    → **Kimi 补了我没想到的一个角落**:重构把 `change_id` 格式校验挪到了
    `_resolve`+存在性检查**之后**,所以"项目不存在 + change_id 畸形"双重非法时,
    返回的是 `project_not_found` 而不是 `change_not_found`,而**没有任何判据钉这个组合**。
    我核了:两种顺序都不写文件、都回 error,且与 `set_due_date` 既有顺序一致 ⇒
    影响为零,接受不补判据。但这是一条真实的"回归覆盖不到的角落",记在这里。

  **腿抓到、我漏了的(panel 的主要价值:暴露我的盲点)**
  - **F4 design.md 自相矛盾**(DeepSeek + Kimi **双腿独立命中**):同一份 design.md
    里"`STATUSES` 加 `已删除`"与"不加"并存,实现跟了后者并有 `test_dc06` 锁死 ⇒
    **照文档去改代码会当场被判据打脸**。我写 design 时自己没读出来。已修(`e3460d4`)。
  - **F5 design.md 承诺的返回形状与实现不符**(Kimi 孤发现):写的是
    `{ok, project, change_id}`,实际是 `{ok, old_status, new_status, line, cnum}`。
    实现的形状与相邻写口同族、更自洽 ⇒ 是设计稿写岔。已修(`e3460d4`)。
  - **F6 tasks.md T3 基于一个错误假设**(DeepSeek):原文"会弹前端二次确认,agent 只管
    调工具,不用自己再问一遍" —— **前端弹窗只覆盖网页点按钮那条路径,agent 走 MCP
    聊天路径时根本没有弹窗**。实现选了更安全的一侧(要求 agent 先复述确认),
    是任务书错了。已修(`e3460d4`)。
  - **F7 最后两个 commit 没有任何机器证据覆盖**(Kimi **孤发现**,本轮最值钱的一条):
    第②遍收据停在 `a0b15e4`,而 `5d2cf86`(补 test_dc10)和 `e3460d4` 之后再没跑过;
    "python 949/949"这个数**根本不含 test_dc10**(加上它应是 950)。
    → 我补跑了第③遍,**实测 950**,与 Kimi 的推算逐个数字吻合。这条如果没被抓到,
    我就会拿一个不覆盖 HEAD 的数字去交付。**这正是 machine-evidence-gate 那一单
    要防的形状,而我在同一天、同一个仓库里又踩了一次它的变体。**

  **我自己在写 verify.md 时犯的错(不是腿抓的,是补跑第③遍时自己撞见的)**
  - **F8 "证据已进 git"这句话是假的**:我写"两份收据都已进 git(`a0b15e4`)",
    但第②遍那份是在该 commit **之后**才跑的,从未被提交。详见上方 Mechanical checks
    段的留痕框。三份收据在本 commit 里补齐。

  **驳回 / 不采纳的**
  - 无。三腿的实质发现(F4/F5/F6/F7)逐条核实**全部成立**,没有一条需要驳回。
    Kimi 那条 Q2 的"文档口径不统一"(`delete_change_tool` docstring 只写 "C3",
    而 `set_due_date_tool` 两种都写)属实但为 Info 级,**本轮不改** ——
    改 docstring 会动 MCP 工具表基线,为一句措辞再刷一次基线不划算;记在这里,
    下次动那个文件时顺手统一。

- arbitrated verdict (主裁): **PASS** —— 见下方「主裁段」。

## Accepted deviations

- **派给从 codex/gpt-5.5 改成主 agent 直接干**——见上方"派给"字段的完整理由,
  这里不重复。影响范围:少了"外部腿独立视角"这一环,收货三闸(diff/亲跑/亲读)
  仍然照走,只是全部由同一个 agent 完成,不构成独立交叉验证。
- **2 条 e2e(`new_chat.e2e.mjs`、`project-thread.e2e.mjs`)本轮 SKIP**——它们测的是
  聊天/gateway 集成,需要起活的 nanobot gateway,与 `delete_change` 无关;
  `tests/run-all.sh` 默认就不跑它们(要 `--with-gateway` 才跑),不是本 track 刻意
  回避。影响范围:零(这两条测的功能面本 track 一个字节没碰)。
- **真机验证(Windows 装机,真的点一下删除按钮)不在本轮范围内**——只有业主能做,
  留给收尾阶段。⚠️ 注意本单**改了助手契约**(`workspace/AGENTS.md` 两条新规矩 +
  工具表新增一行),按 [[opendesign-assistant-brain-0804]] 的教训,**光 `git pull`
  不生效** —— 真机要跑 `bin\start.ps1` 同步助手契约,看到"已同步助手契约"才算到位。
- **`delete_change_tool` 的 docstring 只写了 `"C3"` 一种 cnum 形式**(实际两种都收),
  与 `set_due_date_tool` 的写法不统一(Kimi Info 级发现)。本轮不改:改它要重刷 MCP
  工具表基线,为一句措辞不划算。下次动那个文件时顺手统一。
- **本轮是三腿不是四腿**:`subglm` 默认 off(欠费期间的既定配置,不是本单关掉的)。
  三腿全 PASS ≠ 四腿全 PASS,记在这里防止以后读成"全票通过"。

---

## 主裁段(主 agent 亲自做的,2026-08-08)

**背景:本轮的派活形状本身是错的。** 我(主 agent)把整个 track 丢给了一个 fork,
包括**判据**和**最终裁决**这两件 CLAUDE.md 明写"绝不外包"的事。中途收回了裁决权
(fork 遵守了,Verdict 留 PENDING 没自己盖章),但判据与实现已经由**同一个 agent**
完成 —— 这正是"改考卷让自己及格"最典型的结构。所以本轮主裁不能只读工件,
必须自己造独立证据。

### 一、变异测试(独立证据,fork 没做过这件事)

判据"看着硬"不算数,要证明它**红得起来**。逐个把实现改坏,看判据抓不抓得住:

| 变异 | 判据反应 | 还原后 |
|---|---|---|
| `delete_change` 写 `已完成` 而非 `已删除`(= 复刻 08-08 那次顶替动作) | `DeleteChangeOracle` 3 条红 | 复绿 |
| 行定位去掉 `\b` 锚(C2 误伤 C12/C20) | 1 条红(error) | 复绿 |
| `_changes` 端点不再过滤 `已删除` | `test_ds_web_api` 2 条红 | 复绿(87 OK) |
| 前端 `window.confirm` 恒真(点取消照删) | `todo_delete.e2e.mjs` **4 条红** | 复绿(ALL PASS) |
| `ds_todo` 解析器不认 `已删除`(退回实现前) | `test_ds_todo` 1 条红 | 复绿 |

**五次全部咬住。** 尤其第四条 —— 业主本轮唯一明确要的交互(确定/取消防误触)
是被真正焊死的,不是只写在代码里。
> 注:dist 重建后产物名回到 `index-BA4B_4xl.js`,与实现 commit `a0b15e4` 提交的
> 产物同名,是"我改的东西已经全部还原"的旁证。

### 二、闸①(判卷有没有被动过)—— 主 agent 亲验

- `b8e5114`(oracle-first):`--stat` 只有 `tests/` 四个文件,**零实现文件**。✅
- `a0b15e4`(实现)里确实动了 `tests/test_mcp_surface.py` + `mcp_surface_baseline.json`
  —— **逐行读过:是工具数 32→33 的沿革记账**,而防作弊那条 `test_04_基线自身没被改小`
  仍在、且门槛是**升**的(32→33)。合法,不是放水。✅
- `5d2cf86` 把 `test_dc10` 与 AGENTS.md 一句话放在同一 commit,违反"判据先单独 commit"
  的通常顺序 —— commit message 自曝了,且锁的是**既有能力**(不是追认未经判据的实现)。
  接受,但记在这里:这是一次真实的顺序偏离。

### 三、腿的原始日志 —— 主 agent 逐条读过,不看 fork 的合议摘要

读了 `subkimi.log` / `subdeepseek.log` / `submimo.log` 原文:
- Kimi 那条 F7(最后两个 commit 无机器证据覆盖、949 不含 `test_dc10`、应为 950)
  在原始日志 373/488/550 行确有其文,**且它自己推算出 950 这个数** —— 与后来实测吻合。
  verify.md 的转述**忠实**,没有夸大。
- DeepSeek 独立做了一遍死判据审计,并指出 `test_dc02` 单独看"空实现也会绿"、
  但与 `dc01` 配对后健全 —— 这个判断与我变异测试的结果一致(变异1 时 dc01 红了)。
- submimo 逐条对了新写口与 `_set_due_date` 的七项安全 posture。
- 三腿全 PASS。**但 `subglm=off`,本轮是三腿不是四腿,不许读成"全票"。**

### 四、主 agent 的孤发现(三腿都没抓到)

**AGENTS.md 新写的 5b 里,举例本身是一句假话。** 原文用**现在时**说
"你只有改状态的工具、没有真正的删除工具" —— 而 `delete_change` 正是本单加的,
就列在同一份文件的工具表里。助手每轮都读这份契约,等于契约自带一条与工具表打架的
陈述,与 F5/F6(文档对助手撒谎)**同类**,只是发生在这一单新写的规矩自己身上。
已改:换成不依赖已消失前提的说法 + 一个**当前仍成立**的例子(建档留空的「业主」
行补不回来)。修在 `51a0668`。

### 五、F1 主裁结论

采纳两腿建议:规矩 7 末尾加交叉引用,点明 **7 管后果(残局)、5b 管许可(换不换由
设计师定)**,并明写"干净可逆的替代动作本条拦不住,拦它的是 5b"。
> 理由取自 Kimi 那一刀:08-08 那次顶替(拿"标完结"冒充"删除")是干净可逆的,
> 按规矩 7 的字面根本没被禁止 —— 这正是 5b 必须存在、且两条不冗余的证明。

### 六、覆盖 HEAD 的收据(粘贴逐字节,不改数)

```
runlog: run-all rc=3 commit=51a0668 dirty=yes at=2026-08-08T15:12:17Z file=tracks/opendesign-owner-review-0808/evidence/20260808T151217Z-01-run-all.txt
```
node 342/342 · python **950/950**(死断言 0 条) · MCP 契约闸三条全绿 ·
dist 新鲜度绿 · e2e 33 PASS / 0 FAIL / 2 SKIP(`new_chat`/`project-thread`,需活 gateway,
与本改动无关)。`dirty=yes` = 未跟踪的收据文件,非未提交代码。
> ⚠️ 本 verify.md 的收口 commit 自身不被任何收据覆盖(纯文档,无代码)——
> 这个"最后一跳"的缺口是结构性的,记在这里,不假装它不存在。

### 七、本轮流程事故(必须留痕,否则下次还犯)

1. **我把 oracle + 裁决一起外包了。** 这是硬规矩里明写不许的,fork 没有错,
   是我派活越界。中途收回,靠"变异测试 + 亲读原始日志"补救。
2. **fork 反锚定泄漏**:它先写 verify.md 再派发 panel,Kimi 日志里直接引用了它的
   自审原文。三腿的实质发现都是它没写过的,结论不受影响,但下一单必须先派发再写。
3. **fork 把主 agent 正在做的变异测试误判成"评审腿篡改",恢复了文件并 kill 了
   我的判据进程**(`150525Z` 那份收据因此残缺,已重跑为 `151217Z`)。
   > 这是本轮最有信息量的一条:**两个都认为自己是"唯一控制者"的 agent 在同一个
   > 仓库里会互相执法。** fork 继承了主 agent 的全部上下文与角色认知,看到无法解释的
   > 改动时,它的第一反应是"入侵"而不是"先查 git log 看是不是别人在干活"。
   > fork 自己的复盘点破了最讽刺的一层:**它这一轮刚写完两条"别自己脑补一个答案
   > 就行动"的契约规矩,然后自己违反了同一条。**
   > 代码面未受影响:坏改动从未进入任何 commit,`window.confirm` 完好。
4. **教训归档方向**(不进 CLAUDE.md 硬规矩,进 delegate 抽屉):
   **fork 不是执行腿的任何一档** —— 执行腿是"窄口子 + 交活给老板验";fork 是
   "带着老板的上下文和老板的自我认知"。把整单交给 fork,等于把三道闸搬进黑箱里
   由被查方自己执行,工件链看着完整、每一条却都是自述。

## 留给业主的唯一动作

**Windows 真机验收**(只有机主能做):
1. `git pull` 之后**必须**跑 `bin\start.ps1`,看到「已同步助手契约」才算到位 ——
   本单改了 `workspace/AGENTS.md`(助手契约),光 pull 不生效
   (教训来源:[[opendesign-assistant-brain-0804]])。
2. 打开待办页 → 每条待办右侧应有删除按钮。
3. 点删除 → 应弹确定/取消。
4. **点取消 → 那条必须还在**(这条是业主本轮唯一明确要求的防误触)。
5. 点确定 → 那条消失;刷新页面 → 仍不见(证明真落盘了)。
6. 顺带验规矩 A:提一个**已建档**项目的新需求,看助手会不会再建重复项目。
