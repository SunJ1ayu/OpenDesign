# Verify: opendesign-e2e-guard-followup

- Date: 2026-09-16

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再按 impact-risk 预算跑 panel-review；只有特殊控制面
> 才显式 `--all` 做全池评审。最后仍由主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] build passes(外层总跑里 dist 新鲜度 + 类型检查段绿)
- [x] tests pass(最终 HEAD `d6ee329` 外层干净真跑:各段全绿,rc=3 = 只有跳过、没有红,见最后一份收据)
- [x] no secrets / unsafe ops(产品代码零改动;只动判据侧脚本、helpers、README 与判据)

**机器打印的**(不是我的转述):

判据先行(实现之前)—— **3 红 15 绿**,红的正是 bt4 / bt5 / ne11;旧 bt4 的位置上,旧实现把真实 3 次报成 **4 次**
(内层点名块表头也含那句话,F3 当场复现):

```
runlog: red-oracle-followup rc=1 commit=8b9f1b6 dirty=yes at=2026-09-16T09:28:55Z file=tracks/opendesign-e2e-guard-followup/evidence/20260916T092855Z-01-red-oracle-followup.txt
```

ne12 钉的 python 代码早已存在,判据写下去当场绿 ⇒ 红靠变异(删掉 python 回环块 ⇒ ne12 红):

```
runlog: mutate-ne12-python-lo rc=0 commit=7e2cdb1 dirty=yes at=2026-09-16T09:29:45Z file=tracks/opendesign-e2e-guard-followup/evidence/20260916T092945Z-01-mutate-ne12-python-lo.txt
```

实现之后:判据 **18/18**;红检(退回实现 ⇒ 正好 3 红,红在目标断言上);自攻 bt4 五种错改法全红:

```
runlog: oracle-after-impl rc=0 commit=7e2cdb1 dirty=yes at=2026-09-16T09:30:50Z file=tracks/opendesign-e2e-guard-followup/evidence/20260916T093050Z-01-oracle-after-impl.txt
runlog: redcheck-followup rc=0 commit=9121488 dirty=yes at=2026-09-16T09:31:12Z file=tracks/opendesign-e2e-guard-followup/evidence/20260916T093112Z-01-redcheck-followup.txt
runlog: mutate-bt4-selfattack rc=0 commit=9121488 dirty=yes at=2026-09-16T09:31:47Z file=tracks/opendesign-e2e-guard-followup/evidence/20260916T093147Z-01-mutate-bt4-selfattack.txt
```

外层真跑 + 临时注入一条会泄漏的 e2e(`zz_leakprobe.e2e.mjs`,一次性、没进仓)—— **rc=1,但红的不是本单要问的那一段**:
e2e 段汇总行写着 `41 PASS / 0 FAIL / 2 SKIP / ⚠️ 浏览器收容 1 次(已自动收掉):zz_leakprobe.e2e.mjs`
⇒ 「外层 export → run_seg 套泄漏闸 → 内层沿用 → helpers 写入 → 外层读」整条接缝真跑通过。
红的是 node 单测段 bt1 / bt2 / bt4(`browser has been closed`)—— 这一份撞出了 design ⑤ 的中途发现:

```
runlog: outer-run-injected-leak-probe rc=1 commit=a47bf31 dirty=yes at=2026-09-16T09:33:00Z file=tracks/opendesign-e2e-guard-followup/evidence/20260916T093300Z-01-outer-run-injected-leak-probe.txt
```

中途发现 ⑤(Chromium socket 路径超 107):判据先行 bt6,在泄漏闸包装下 **18 绿 1 红**(只红 bt6,且 bt1/bt2/bt4 夹具改短后已绿);
实现之后 **19/19**、无漏目录;红检通过(红在 bt6):

```
runlog: red-bt6-under-leak-gate rc=1 commit=a47bf31 dirty=yes at=2026-09-16T09:57:04Z file=tracks/opendesign-e2e-guard-followup/evidence/20260916T095704Z-01-red-bt6-under-leak-gate.txt
runlog: oracle-under-leak-gate-after-bt6 rc=0 commit=f146ed5 dirty=yes at=2026-09-16T09:57:31Z file=tracks/opendesign-e2e-guard-followup/evidence/20260916T095731Z-01-oracle-under-leak-gate-after-bt6.txt
runlog: redcheck-bt6 rc=0 commit=d6ee329 dirty=yes at=2026-09-16T09:57:52Z file=tracks/opendesign-e2e-guard-followup/evidence/20260916T095752Z-01-redcheck-bt6.txt
```

最终 HEAD 外层干净真跑(**结论所依据的那一遍**):泄漏闸自测 14 条全过 / node 单测 **444 通过** / python 1695 跑过 1 跳过 /
MCP 三条闸全绿 / dist 与源码同步 / e2e **40 PASS / 0 FAIL / 2 SKIP**,汇总行没有「浏览器收容」(没注入就不误报)。
rc=3 = 「没有红的,但有 3 条没跑」:两条要活网关的 e2e(默认跑法必跳)+ python 原有的 1 条跳过,与上一单一致。

```
runlog: outer-run-final-clean rc=3 commit=d6ee329 dirty=yes at=2026-09-16T11:27:09Z file=tracks/opendesign-e2e-guard-followup/evidence/20260916T112709Z-01-outer-run-final-clean.txt
```

- ⚠️ `evidence/20260916T095817Z-01-outer-run-final-clean.txt` 是**断线砍掉的半截**(09-16 17:58 起跑,18:06 会话断线,
  后台任务被杀):只有收据头、**没有任何输出也没有收据行** ⇒ 它**不证明任何事**,归档闸也看不见它(闸只认带 `runlog:` 行的收据)。
  保留不删;同 slug 的那次重跑是脱离会话进程树起的(`setsid -f`,核过 ppid=1),就是上面那份。

## Review

- 规格自查(读任何 panel 输出之前先答,全文在仓外自审):**最可能错在「把接缝交给一次性收据」**。
  bt4 桩掉了 `run_seg`、bt5 只抽到内层 export 那一行 ⇒ 「环境变量一路传到场景进程」没有永久判据,
  只由 `outer-run-injected-leak-probe` 证明;核过 `git diff a47bf31..HEAD -- tests/run-all.sh tests/e2e/run-all.sh` 为空,
  那份收据对最终 HEAD 仍有效。哪天有人把某一层写成 `env -i`,三截判据全绿、汇总行**静默地永远不报名字**。
  - 断线后新会话亲读 diff 时更正了旧自审一句:「bt4 抓不到 export 挪到文件头」**不成立** ——
    仓外照 bt4 的桩逐字搭纯 bash 变异 [仓外不承重]:export 挪出 ⑥ 段 ⇒ `set -u` 下 unbound variable rc=127 ⇒ bt4 红;
    读侧再改成 `${E2E_BROWSER_NOTES:-}` ⇒ 汇总里没有「浏览器收容」⇒ bt4 红。仓内 `mutate-bt4.sh` 第一种变异本来就红过。
    派发前已把题面里这句错话改掉,没喂给腿。
- 腿的花名册:
  `submimo=PASS(verdict=PASS) subdeepseek=PASS(verdict=PASS) subglm=SKIP(health:cooldown:rate_limit) subkimi=SKIP(rotation) subgemini=SKIP(health:dead:FAIL:6) subgrok=SKIP(rotation)`
  (`/root/aiwork/logs/panel-opendesign-e2e-guard-followup-review-r1-20260916-1940.roster`;impact high、budget 2、escalation none、snapshot head `d6ee329`;
  派发前 `PANEL_ORACLE_CMD='node --test tests/test_e2e_harness_guard.mjs'` rc=0)
- 反锚定:派发时报 `anchor leak: tracks/opendesign-e2e-guard-followup/verify.md`。那一刻它是**未填的模板**(本文件是两腿交卷后才写的),
  自审正本在仓外 ⇒ 没有结论泄漏。如实记账。
- findings(逐条对代码/探针核过;接受/驳回都给依据):
  1. **[DeepSeek,Low,成立 —— 记账不修] 回环检查会被 `NODE_OPTIONS` 污染 stdout 而放行**,且这是本单新引入的(旧实现走 bash,不吃 NODE_OPTIONS)。
     我亲自复现:`unshare -n` 里(lo 没起)照 `helpers.mjs` 原样起子进程,干净环境 stdout=`ENETUNREACH` ⇒ 拒跑;
     `NODE_OPTIONS=--require <会往 stdout 写字的模块>` ⇒ stdout=`noise:ENETUNREACH` ⇒ `includes` 精确比较不中 ⇒ **放行**。
     **在业主那边长成什么样:什么都没有** —— 业主不跑 e2e,产品代码零改动。
     在下一个跑 e2e 的人那边:要同时满足「NODE_OPTIONS 带一个会往 stdout 打字的预加载」+「`ip link set lo up` 失败」,
     结果是 e2e **照样红**(自起的 ds_web 连不上),只是红成「连接失败」而不是「🔴 回环没起来」横幅 —— 响亮、不是假绿,
     出口闸(后面的 `noEgressOpen` 实测)不受影响。⇒ 不属于「业主可见行为出错 / 考卷假绿」,按 panel 4b② 记账。
     修法很便宜(按行找 errno,或子进程 env 里去掉 NODE_OPTIONS;`lo.error` 时拒跑),排进下一单。
  2. **[MiMo,驳回] 「NODE_OPTIONS 带奇怪东西 ⇒ 不比原版更糟」**:与上一条的亲跑复现相反。它给的理由「原版 bash 同样会被 BASH_ENV 干扰」
     是没跑过的类比,而本机此刻就设着 `NODE_OPTIONS=--max-old-space-size=1800`(这条通道是共用的)。信任校准数据点:MiMo 又一次把没验证的判断写成结论。
  3. **[DeepSeek + 我,Low,成立 —— 记账不修] bt6 只钉了「必拒」一侧,没钉「107 必须放行」一侧**。阈值写成 `> 100` 或 `>= 107`,bt6(约 143)照样绿。
     边界本身 DeepSeek 用真 chromium 独立量过:给 chromium 的 TMPDIR 长 62 能起、63 崩;运行时列目录确认 socket 是
     `TMPDIR/org.chromium.Chromium.XXXXXX/SingletonSocket`(无前导点)⇒ 62+45=107,与旧会话实验(外层 40 过 41 崩)两次独立一致 ⇒ 当前常量是对的。
     我自己没能从 chromium 二进制里 grep 到那个字面串,所以「目录名」这一项采信 DeepSeek 的运行时实测。
     **业主侧零影响**;阈值写错时:过严 ⇒ 泄漏闸下(102)bt1/bt2 红成「TMPDIR 太深」,过松 ⇒ 回到无线索崩溃 —— 两个方向都是红,不是假绿。
  4. **[DeepSeek + 我,Low,成立 —— 记账不修] 接缝没有永久判据**(见规格自查)。DeepSeek 点得更细:内层 `run_one` 的 `run_env=(env HOME=…)`
     全仓没有判据碰;建议照 bt5 的抽段手法再加一条。**业主侧零影响**;下一个人那边长成:某天改成 `env -i`,汇总行静默不再点名(不红)——
     这是本单唯一的**静默**缝,排进下一单优先做。
  5. **[DeepSeek + MiMo + 我,Low,记账] `_bn_who` 边角**:脚本名含空格/冒号会被截断,空行会产生空名字。
     `helpers.mjs:190` 只写 `<basename>: <what>\n`,构造不出空行;本仓 e2e 文件名无空格无冒号。业主侧零影响。
     MiMo 建议 `_bn_n` 改用 `wc -l` —— **驳回**:`wc -l` 不数末行无换行的那一行,计数和名字反而在另一个方向上对不齐。
  6. **[DeepSeek,Info,记账] README「`run-all.sh` 会沿用它」指代略含糊**:那一节同时提到两个 run-all;README 在 `tests/e2e/` 下,
     本意是 `tests/e2e/run-all.sh`(仓库级那个会覆盖并 `unset`)。不改(改了要作废本轮绑定,且不影响行为)。
  7. **[MiMo,记账] 建议内层 `run-all.sh` 注释里也提醒 unset**:内层那行上方已有三行注释说明「外面给了就沿用」;可选,不改。
  8. **[两腿一致,核过] 夹具改短不是放水**:只动了 `outer = tmp(...)` 前缀,断言逐行未变(我与 DeepSeek 各自 `git diff` 核过)。
     我补一层两腿都没说到的:**bt3 那一处是必须改的** —— bt3 只断言「rc=0 + 不留 ds-e2e-browser-*」,不改短时在泄漏闸下 119 > 107,
     bt6 的新检查先抛「TMPDIR 太深」⇒ bt3 **照样绿、却根本没走到假 chrome 启动失败的收尾路径**,那才是假绿。
- arbitrated verdict (主裁): **PASS**。
  本单要交付的四件(名字进汇总行且计数对 / 回环读 errno / python 回环有判据 / README)加中途发现 ⑤,
  都有「先红后绿 + 红检 + 变异」的机器证据,最终 HEAD 外层真跑全绿,接缝由注入收据真跑证明且其后脚本未变。
  两腿 PASS 不是我判 PASS 的理由:我独立读了全部代码 diff、复现了唯一一条「本单引入的退步」(finding 1)并按 4b② 判定它不值得返工。
  轮次:第 1 轮 / 上限 2 轮,没开第 2 轮(没有值得返工的发现,且上面的记录都落在豁免清单内,不作废本轮绑定)。

## Accepted deviations

- finding 1 / 3 / 4 / 5 / 6 均为判据侧工具的诊断强度问题,业主侧零影响,排进下一单(优先 4 —— 唯一静默的缝,其次 1 —— 本单引入的退步)。
