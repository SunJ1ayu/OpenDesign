# Verify: opendesign-dist-freshness-gate

- Date: 2026-08-24

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

> 状态:**收口**。代码面 PASS,本单无产品面(不改产品行为、不进安装包)。

- [x] **P0 前提探针 PASS**:`vite build` 连续两次产物 `diff -r` 完全相同、各 3 个文件非空
      (`evidence/20260824T-P0-build-determinism.txt`)。build 若不确定,这道闸会随机红 ⇒
      前提塌了整个方案作废,所以先验。
- [x] tests pass:**8 条 oracle 全绿**(design 写的是六条,实做补了 O1b 与 O7)
- [x] 红检:**6 条变异咬住 6、漏网 0**(第一轮 5 咬 1 漏,两件真问题已修,见 findings)
- [x] `run-all.sh` 总跑 **36 PASS / 0 FAIL / 2 SKIP**(SKIP 是需要活 gateway 的两条,非本单造成)
- [x] python 全量回归 **1312 项 OK**(venv 解释器);死断言 0
- [x] no secrets / unsafe ops(只动 tests/ 与 docs/backlog.md,不碰产品代码)
- [x] 红检跑完**仓库零污染、零遗孤进程**(实测)

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,把它打印的收据行原样粘进来:

```
runlog -t opendesign-dist-freshness-gate -- <判据命令>
```

```
runlog: oracle-red-before-gate rc=1 commit=a433bf8 dirty=yes at=2026-08-24T01:28:17Z file=tracks/opendesign-dist-freshness-gate/evidence/20260824T012817Z-01-oracle-red-before-gate.txt
runlog: oracle-green rc=0 commit=4969559 dirty=yes at=2026-08-24T01:40:03Z file=tracks/opendesign-dist-freshness-gate/evidence/20260824T014003Z-01-oracle-green.txt
runlog: redcheck-mutation rc=1 commit=4969559 dirty=yes at=2026-08-24T01:41:24Z file=tracks/opendesign-dist-freshness-gate/evidence/20260824T014124Z-01-redcheck-mutation.txt
runlog: oracle-green-v2 rc=0 commit=4969559 dirty=yes at=2026-08-24T01:53:03Z file=tracks/opendesign-dist-freshness-gate/evidence/20260824T015303Z-01-oracle-green-v2.txt
runlog: redcheck-mutation-v2 rc=0 commit=4969559 dirty=yes at=2026-08-24T01:54:03Z file=tracks/opendesign-dist-freshness-gate/evidence/20260824T015403Z-01-redcheck-mutation-v2.txt
runlog: e2e-runall-final rc=0 commit=4b56e1a dirty=no final=yes at=2026-08-24T02:03:34Z file=tracks/opendesign-dist-freshness-gate/evidence/20260824T020334Z-01-e2e-runall-final.txt
runlog: python-regression-venv rc=0 commit=4b56e1a dirty=yes at=2026-08-24T02:08:00Z file=tracks/opendesign-dist-freshness-gate/evidence/20260824T020800Z-01-python-regression-venv.txt
runlog: e2e-runall-final rc=65 commit=a137db3 dirty=no final=yes at=2026-08-24T02:16:38Z file=tracks/opendesign-dist-freshness-gate/evidence/20260824T021638Z-01-e2e-runall-final.txt
runlog: e2e-runall-final rc=65 commit=c29093c dirty=no final=yes at=2026-08-24T02:23:36Z file=tracks/opendesign-dist-freshness-gate/evidence/20260824T022336Z-01-e2e-runall-final.txt
runlog: e2e-runall-final rc=0 commit=963e0c0 dirty=no final=yes at=2026-08-24T02:28:03Z file=tracks/opendesign-dist-freshness-gate/evidence/20260824T022803Z-01-e2e-runall-final.txt
```

**十份全在这儿,红的一份没藏**(规矩 5b)。逐份说明:

- `oracle-red-before-gate rc=1` —— **先红后绿**的红:闸还不存在,7 条全红在 setUp 上。
  **这个红很弱**,只证明判据跑得起来,没证明任何一条断言咬得动 —— 那件事由红检证明。
- `redcheck-mutation rc=1`(第一轮,**5 咬住 1 漏网**)—— 漏的那条最值钱,
  查出 F-G(红检弄脏了被测仓库)与 F-H(变异本身没意义,该修的是实现)。见 findings。
- `e2e-runall-final rc=65` **两份** —— **e2e 本身都是 36 PASS/0 FAIL**(`command-rc: 0`),
  65 是 `runlog --final` 判定 `source-stable: no` 给的:收据跑的过程中有人写了这个仓库。
  第一次是我并行派 panel(它往仓内 `observations/` 写),第二次是我自己在编辑 verify.md。
  **闸没坏,是我用错了 —— 它两次都在正确报警。**
- `e2e-runall-final rc=0 ... source-stable: yes`(02:28:03)—— **这才是有效的最终收据**,
  跑在工作树干净、无并发写入的条件下。
- 其余四份(`oracle-green` / `oracle-green-v2` / `redcheck-mutation-v2` /
  `python-regression-venv`)全绿,数字见主裁。
- P0 前提探针另存 `evidence/20260824T-P0-build-determinism.txt`(非 runlog 格式,
  是我手写的探针脚本输出)。

## Review

- **规格自查(读任何 panel 输出之前先答)**

  这一单的规格是「闸该比产物,不该比时间戳」。**它最可能错的地方不是实现,是守错门** ——
  我保证了 `web/dist` 新鲜,可 e2e 真正加载的是那一份吗?若不是,这道闸再准也是白装,
  而且会给出**更自信的假绿**(比旧闸更坏)。这个项目栽过三次守错门。

  **已实证,不是推理**:`bin/ds_web.py:2473` 的 dist 路径可被 `DS_WEB_DIST` 覆盖,
  默认值来自 `DEFAULT_DIST`(:753)← `DEFAULT_DS_ROOT`(:752)。而 :752 是
  `os.path.dirname(os.path.dirname(os.path.realpath(__file__)))` —— **从脚本文件位置推导,
  不读环境变量**。真跑一次探针:把 `DS_ROOT` 设成不存在的路径,`DEFAULT_DIST` 仍然是
  `<仓库>/web/dist`。⇒ 36 个场景走这条默认路径,`llm_key.e2e.mjs:107` 显式设的
  `DS_WEB_DIST` 也指向同一处。**闸守的正是 e2e 真正加载的那份产物。**

  规格若仍是错的,还能错在哪(我目前答不死的):
  - **产物一致 ≠ e2e 结论可信**。这道闸只保证"验的是当前代码",不保证判据本身问对了问题。
    它把一类沉默的假绿变成了响的红,仅此而已 —— 别把它读成"e2e 现在可信了"。
  - **build 的确定性依赖这台机器的工具链**。换 node 版本 / 换机器,产物可能不同字节 ⇒
    闸会红在一件与源码无关的事上。本项目只有一台开发机,暂不构成问题;真要多机时
    这道闸得改成"记录 build 指纹"而不是当场重建。
- 腿的花名册(原样粘自 `.roster`,没手写):

  首轮(轮换选中 subkimi,失败):
  ```
  submimo=SKIP(rotation) subdeepseek=SKIP(rotation) subglm=SKIP(rotation) subkimi=FAIL(rc=1)
  ```
  失败原因**开日志确认过**,不是猜的:`provider managed:kimi-code has no credential configured`
  —— 这条腿本来就没配凭据,轮换却选了它。按协议追加一条健康 spare:

  ```
  submimo=PASS(verdict=UNKNOWN) subdeepseek=SKIP(rotation) subglm=SKIP(rotation) subkimi=SKIP(health:auth)
  ```
  > `PASS` 只是进程 rc=0,**不等于给了裁决**;`verdict=UNKNOWN` 是因为它没写独立结论行。
  > **已开日志逐条读过**(317 行),内容是实质性的,见下方 findings。

- ⚠️ **反锚定有泄漏,如实记账**:两轮派发都报了 `anchor leak — tracks/.../verify.md`。
  我在派发前已把 verify.md 回退到 HEAD(自审正本在仓外),但 `a433bf8..HEAD` 的 diff 里
  仍带着它前两个 commit 的内容(「判据先行已落/实现未写」+ 红收据 + 「这个红很弱」那句)。
  那些是工序信息与机器数据,**不含我的 findings**,但确实是我的判断口径 ⇒ 影响有限而非零。
  正确节奏仍是「先派发、后写 verify.md」,这一单只做到了一半。
  > panel-review 收尾自己写这个文件(off / FAIL(rc) / 降级 都在里面)。
  > **控制器没活到收尾时它压根不存在** —— 那时跑 `panel-roster <日志前缀>` 从盘上重建,
  > 与控制器自己写的**归一化后一致**(判据 R5b 守着;抬头有渲染时间戳,不是字面逐字节)。**一轮零记录的评审也粘得出这一行**,
  > 所以"那轮被砍了所以没有花名册"不再是理由(2026-08-23,track panel-roster-from-disk)。
  > 08-06 立这条的理由:08-05 我在这里手写了"三条腿一致 PASS",而 Kimi 根本没出结论
  > (同一页第 90 行我自己还写着它没出报告)—— 手抄一份终端上的东西,抄错那次没人会发现。
- findings:

  **主 agent 自审(落盘于派 panel 之前,仓外 `/root/aiwork/tasks/dist-freshness-gate-my-review.md`):**

  - **F-A [已改] 判据弱断言**:O3 原本只断言输出 `len > 40`,它想问「闸有没有把 build 的
    报错原文带出来」,实际问的是「输出够不够长」—— 凑 40 个字符太容易,闸多打两行套话
    就能骗过它。改成断言报错**可溯源到具体文件**。同族:这个项目栽过的「一条永远绿的瞎断言」。
  - **F-B [已知边界,靠动态兜住]** O6 的**静态**那半截咬不住 M4 那种变异:
    我查的是行尾是不是 `;` 和有没有 `|`,而 `check-dist-fresh.sh; if false; then`
    以 `then` 结尾 ⇒ 静态放行。**由动态那半截(真跑一次)咬住,红检 M4 就是它的证据。**
    记在这是因为:哪天有人嫌慢把动态半截删了,静态部分会给出假绿。
  - **F-C [边界,不改]** `--web-dir` 传相对路径时 `DIST` 相对调用者 cwd,而 build 在
    子 shell 里 `cd "$WEB_DIR"`。判据一律传绝对路径、run-all.sh 走默认值,现在没问题。
  - **F-D [取舍,接受]** 只跑三条 python 场景时闸照样 build 一次(3s)。要免掉就得先算
    「这次 filter 会跑到哪些场景、哪些依赖 dist」—— **旧闸正是死在这个判断上**
    (它认定"只有 llm_key 需要",于是漏掉 36 个)。宁可一律 build,3 秒买简单和一致。
  - **F-E [观察,已记 backlog]** build 确定性依赖本机工具链;换 node 版本/换机器可能
    产物不同字节 ⇒ 闸红在与源码无关的事上。本项目只有一台开发机,暂不构成问题。

  **第一轮红检查出的(5 咬 1 漏,漏的那条反而最值钱):**

  - **F-G [已修] 我的红检弄脏了被测仓库**:M5 变异让闸往**真的** `web/dist` 写
    `judge-probe.txt`(靶子 O4 确实咬住了),但 restore 只还原两个脚本、没收拾这个副产物。
    它留在仓库里,接着污染了 M6 那一轮 —— 判据造副本时把它一并复制过去,
    于是 O2 红在了别处。**一条变异的副作用让另一条变异的结论失真。**
    已修:restore 用 `comm` 比对 dist 清单删多余的。
    > 查到它靠的是「靶子红在别处」这个信号 —— 红检只报"漏网 N 条"而不报**红在哪**的话,
    > 这条线索就没了。
  - **F-H [已修,而且修的是实现不是判据] M6 漏网是对的:变异本身没意义。**
    那时 build 不写盘就连 `$OUT` 目录都不建,`diff` 撞「目录不存在」替它红了
    ⇒ 拆掉一条防线而程序行为没变。**这正是 native-frame 那单记过的形状:
    为了让变异"咬住"去改判据,就是把报警器调过敏。** 正确处置是让实现把职责说清楚:
    闸补一行 `mkdir -p "$OUT"` ⇒ ①那行难看的 `find: No such file or directory` 消失,
    ②「两边都空 ⇒ 比对恒过」这个真实场景造得出来,③这条变异才真的咬得到东西。
    **实测确认**:补 mkdir 前后跑同一个 O7 场景,闸都红在「产物数」那条上。
  - **F-I [已修] 红检自己吞掉了线索**:`[BAD]` 那支只打 4 行摘要,详细输出在 `$WORK`
    里被 trap 删了 ⇒ 查 M6 只能整轮重跑。已改成把前 40 行吐进收据。

  **panel submimo 的四条(逐条对账,接受/驳回都给依据):**

  - **[接受]** O4/O6 跑在真仓库上,Ctrl+C 砍在 O6 中间会把 `<!-- judge-probe -->`
    留在 `web/dist/index.html`。已写进判据文件头(含收拾命令)。
  - **[驳回·实测]** 它称 O6 动态半截「靠 bash 语法错误兜底,碰巧有效而非精确命中」,
    依据是变异后 `; if false; then` 缺 `fi`。**核实不成立**:变异只替换第一行,
    `fi` 仍在原处,对变异后的副本跑 `bash -n` **完全通过**(实测)。M4 咬住 O6 走的正是
    「闸红 → rc 被吞 → 场景照跑 → 90s timeout → self.fail」这条路,是精确命中。
    ⚠️ **方向对、例子错** —— 这条腿的老毛病,记账时别抄它的例子。
  - **[驳回]** 它担心 `--emptyOutDir` 没生效 + `$OUT` 有旧残留 ⇒ 比到旧产物。
    不成立:`OUT="$TMP/out"` 而 `TMP=$(mktemp -d)`,每次都是全新目录(它自己也标了风险低)。
  - **[接受为已知边界]** diff 输出 `head -40` 在差异文件很多时会截断。取舍,已有提示语。

  它逐项验证后的结论:比对逻辑对称、trap 覆盖所有退出路径、rc 无吞掉路径、参数校验完备
  ⇒ **无假绿路径**;旧闸退场"做得很干净"。

  **我知道但没解决的(已在自审里摆给评审员打):**

  - 这道闸**只把一类沉默的假绿变成了响的红**,它不让 e2e 变可信 —— 判据自己问没问对问题,
    它一个字都答不了。别让它成为「e2e 现在可信了」的借口。
  - **它真正的软肋**:闸红时给的指示是「build 一下再提交」,而"该 build"和"忘了 build"
    的正确动作是同一个 ⇒ **工具层面区分不了**。有人图省事直接 build 过关,
    正是它想拦的情形被合法化。
  - `web/dist` 入库这个前提本身没被质疑过(安装包直接打 dist)。前提若该变,闸的形状也该变。
  > 只写发现。腿的身份/降级不在这儿抄第二遍:日志自带身份牌(降级横幅 + 视野边界),
  > 花名册在上一格,查工件不查自述。
- arbitrated verdict (主裁): **PASS(代码面)。这一单没有产品面** ——
  它不改产品行为、不进安装包、业主一点感觉不到,是纯判卷防线。

  依据(都是机器写的收据,不是我的转述):
  - python 全量回归 **1312 项 OK**(skipped=1);死断言检查 55 个判据文件 3168 条断言,
    **没有从没跑过的**。(1312 = 原 1304 + 本单新增 8 条 oracle。)
  - 8 条 oracle 全绿;**红检 6 条变异咬住 6、漏网 0**,含新旧闸**对照组** M3
    (把闸退回比 mtime ⇒ O2「只改注释」必红 —— 这一条才证明这次收紧真的有意义)。
  - e2e 总跑 **36 PASS / 0 FAIL / 2 SKIP**(2 SKIP 是需要活 gateway 的两条,一直如此,
    非本单造成;**SKIP 不算通过**)。
  - 红检跑完**仓库零污染、零遗孤进程**(都实测过,不是推断)。
  - panel 一条外部腿(submimo,xiaomi 家族)逐项验证后给出"无假绿路径";
    它四条发现我接受 2 条、驳回 2 条,**两条驳回都有实测依据**。

  **我自己对这道闸的保留(压过任何腿的 PASS):**
  它只把**一类**沉默的假绿变成了响的红 —— 「e2e 验的不是你改的那份代码」。
  它**不让 e2e 变得可信**:判据自己问没问对问题,它一个字都答不了。
  别把它读成「e2e 现在可信了」。

## Accepted deviations

- **闸红时的指示是「build 一下再提交」,而"该 build"和"忘了 build"的正确动作是同一个**
  ⇒ 工具层面区分不了。有人图省事直接 build 过关,正是它想拦的情形被合法化。
  **这是这道闸真正的软肋**,submimo 也独立指出、同样给不出更好的形状。接受。
- **只跑三条 python 场景时闸照样 build 一次(约 3s)**。要免掉就得先算「这次 filter 会跑到
  哪些场景、哪些依赖 dist」—— **旧闸正是死在这个判断上**(它认定"只有 llm_key 需要",
  于是漏掉 36 个)。宁可一律 build,3 秒买简单和一致。
- **build 确定性依赖本机工具链**:换 node 版本 / 换机器,产物可能不同字节 ⇒ 闸会红在
  与源码无关的事上。本项目只有一台开发机,暂不构成问题;真要多机时这道闸得改成
  「记录 build 指纹」而不是当场重建。已记 backlog。
- **diff 输出 `head -40` 在差异文件很多时会截断**。取舍,已有提示语。
- **`--web-dir` 传相对路径时 `DIST` 相对调用者 cwd**,而 build 在子 shell 里 cd。
  判据一律传绝对路径、run-all.sh 走默认值,现在没问题;换个调用方式会错,记在这。
- **判据 O4/O6 跑在真仓库上**,O6 被 Ctrl+C 砍在中间会在 `web/dist/index.html` 留一行
  `<!-- judge-probe -->`。git status 当场看得见,一行 `git checkout` 收拾。已写进文件头。
- **不修 8 个 `mutation-*.sh` 的 `cp` → `cp -p`**(本单 non-goal)。新闸不看 mtime ⇒
  已无已知危害;它与「红检会被字节码缓存骗」方向相反、必须实测才敢动。已记 backlog,
  连同查这单时**新挖出来的一笔**:`mutation-ds-shell-core.sh` 变异 python 却不清
  `__pycache__`(同类另 6 个都清了)—— 那个直接影响红检结论的可信度,比前者值钱。

## 这一单自己踩的坑(工艺账,写下来防止再犯)

- **最终收据被"跑的过程中有人写仓库"废掉两次**,`runlog --final` 两次给 rc=65
  (`command-rc: 0` + `source-stable: no` —— e2e 本身都是 36 PASS/0 FAIL)。
  第一次是我**并行派了 panel**(它往仓内 `observations/` 写);第二次是**我自己**
  在收据跑的过程中编辑 verify.md。
  ⇒ 老规矩「最终收据必须是最后一次编辑之后那一遍」有个我以前没写出来的半边:
  **收据跑的那段时间里,任何人都不能写这个仓库,包括我自己、包括后台任务。**
  这道闸做对了它该做的事,两次都是它在报警,不是它坏了。
  > 这里写理由；最终枚举写进 `decision.json.outcome.verdict`。归档时仍为空会被
  > `track-record validate --phase archive` 挡住，`track list` 也会打 ⚠️。

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>
