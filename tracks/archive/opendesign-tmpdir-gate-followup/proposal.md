# 收掉 tmpdir 闸四审的 12 条发现

## 从哪来

`opendesign-tmpdir-leak` 归档后,我把「四审发现的**修复本身**」(`04f97f2..46fbbe8`
那 81 行)又送了一轮三腿评审 —— 因为那段是**主 agent 自审就上线的**,没有任何人看过。
三腿(submimo / subdeepseek / subkimi)全 PASS,共提 12 条,全部低危。
本 track 收这 12 条。

四审日志:`panel-tmpdirfixes-0818.{submimo,subdeepseek,subkimi}.log` `[仓外不承重]`

## 逐条仲裁(主 agent 亲判,不认腿的自述)

### 接受并修

| # | 位置 | 问题 | 谁提的 |
|---|---|---|---|
| A | `tests/tmpdir-leak-gate.sh:69` | `_selfcheck` 没初始化 ⇒ `mapfile` 一缺,这道闸**直接报绿(rc=0)** —— 不是低危可移植性问题,是**真的假绿** | subdeepseek 3 / submimo 建议;**红检把严重度顶到了顶** |
| B | `tests/tmpdir-leak-gate.sh:25` | 用法注释写「否则 rc=1」,同文件第 30 行和代码都是 **rc=9** | subkimi 2 |
| C | `tests/tmpdir-leak-gate.sh:68` | `mkdir` 哨兵失败时,诊断文案把锅甩给 find/mapfile,指错排查方向 | subkimi 6 |
| D | `tests/e2e/run-all.sh:76` | 陈旧注释:仍写「有跳过时会被留下给人看」,而这轮改成了**只跳过就收掉**;孪生说明 `run-all.sh:141-147` 改了,这份漏了 | subkimi 1 |
| E | `tests/dead_assertions.py:376` | 提示语「或者给每一处各写一条」对**逐字节相同**的两行不成立(各写一条还是盖住两行) | subdeepseek 2 + subkimi 4(**两腿独立命中**) |
| F | `tests/dead_assertions.py:371-374` | ALLOW_WIDE 红了却**不点名冲突在哪几行**,人只能自己 grep ⇒ 容易去改无辜的那行 | subdeepseek 1 + subkimi 5(**两腿独立命中**) |
| G | `tests/dead_assertions.py:169` | 截断记号只加在 `note()`(:77),`same_line_guarded` 仍**静默** `[:120]` ⇒ 从那一节复制长行进 allow 会落成「过期条目」红,而原因看不出来 | subkimi 3 |
| H | `tests/run-all.sh:97-139` | 段号注释与实际不符:新插的「泄漏闸自测」排第一却没编号,后面仍挂旧的 ①~⑤ | submimo F2 |

**A 这条,四个判断全错了 —— 包括我自己的。** 先是三腿:subdeepseek 说 rc=1(且以为
只在 bash<4.4 才有),subkimi 说「取长度在 set -u 下是安全的、rc=2 成立」,
submimo 说「两种情况都不是绿的」。我写这份 proposal 的第一版跟着 subdeepseek 写了 rc=1。

**然后我给它写判据(⑭),红检一跑,实得 rc=0。**

手工复现出的完整因果链:
```
line 69: mapfile: command not found        ← 内建不在
line 70: _selfcheck: unbound variable      ← 自检在这里报错了
line 96: mapfile: command not found        ← 可是脚本没停,继续往下跑
rc=0                                       ← 最后报绿
```
`${#_selfcheck[@]}` 的 unbound variable 长在 `if [ ... ]` 的条件里,**没能让脚本停下**,
只被当成「条件为假」;于是控制流穿过自检,落到正常流程第 102 行的 `mapfile`——
那里的 `${left[@]+"${left[@]}"}` 守卫**安静地把「数不出来」当成「台面上什么都没有」**,
于是 n=0 ⇒ 干净 ⇒ 绿。

也就是说:**这道闸的哨兵自检,在它号称要堵的两条路之一上完全失效,而失效的表现正是
它自己写在文件头上的那句「一道会无声瞎掉的闸比没有闸更坏」。** 上一轮四审说这个洞
「堵上了」,三腿一致 PASS —— 堵住的只是 `mktemp` 那条,`mapfile` 那条从来没堵住过。

### 接受分析、不改(写下理由,免得下轮再提)

- **subdeepseek 4 / submimo Q3(只跳过就收日志 ⇒ 丢审计线索)**:subkimi 的反驳成立且我复核过——
  改动**之前**这些目录从不打印路径,是不可发现的垃圾;跳过者的名字仍在控制台输出里。
  净信息损失 ≈ 0,取舍已写在代码注释里。
- **submimo F1(正常流程第 102 行 find 的 stderr 仍被吞)**:哨兵自检已经用**同一套数法**
  证明了这台机器上数得出来;再吞的概率极低。改它要动正常路径,不划算。
- **subkimi 5 的另一半(docstring 里复刻同样一行会误判)**:**不改判定逻辑**。
  按内容认是上一版「行号会漂」换来的,收窄匹配范围会重新打开漏放行的口子。
  F 把冲突行号印出来之后,这种情况一眼可诊断。

## 判据缺口(这轮补)

subkimi 3 顺带指出:**截断记号本身没有任何判据钉它**。A 那条 rc=2 的契约同样没被钉过
(⑫⑬ 钉的是 find 坏掉,没钉 mapfile 缺失)。两条判据先单独 commit、先跑红。
