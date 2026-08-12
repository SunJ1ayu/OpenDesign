# Verify: opendesign-cnum-zeropad

- Date: 2026-08-12
- Verdict: **PASS**(主裁;四审 2/4 腿给了裁决,其中孤腿 BLOCK 成立并已修)

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] build passes(总跑第 4 段:重新 build 后 git 对 web/dist 无差异)
- [x] tests pass
- [x] no secrets / unsafe ops(diff 只动 `bin/ds_tools.py` / `bin/ds_todo.py` /
      `bin/ds_web.py` 一个错误码表项;无网络、无新依赖、无符号链接)

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,把它打印的收据行原样粘进来:

```
runlog: suite-final rc=3 commit=1454d6f dirty=yes at=2026-08-12T02:59:08Z file=tracks/opendesign-cnum-zeropad/evidence/20260812T025908Z-01-suite-final.txt
runlog: mutation-r4 rc=0 commit=1454d6f dirty=no at=2026-08-12T02:49:13Z file=tracks/opendesign-cnum-zeropad/evidence/20260812T024913Z-01-mutation-r4.txt
runlog: redcheck-v2 rc=0 commit=1454d6f dirty=yes at=2026-08-12T02:49:45Z file=tracks/opendesign-cnum-zeropad/evidence/20260812T024945Z-01-redcheck-v2.txt
runlog: oracle-merged rc=0 commit=0a6e943 dirty=yes at=2026-08-12T02:03:15Z file=tracks/opendesign-cnum-zeropad/evidence/20260812T020315Z-01-oracle-merged.txt
runlog: regress-tools rc=0 commit=0a6e943 dirty=yes at=2026-08-12T02:03:15Z file=tracks/opendesign-cnum-zeropad/evidence/20260812T020315Z-02-regress-tools.txt
runlog: regress-todo rc=0 commit=0a6e943 dirty=yes at=2026-08-12T02:03:15Z file=tracks/opendesign-cnum-zeropad/evidence/20260812T020315Z-03-regress-todo.txt
```

**`suite-final` 的 rc=3 不是红**:五段一段没红,但两条要活 gateway 的 e2e 记 SKIP,
总跑按"SKIP 不算 PASS"退 3。那两条是聊天链路(真 nanobot + 真模型),
本单 diff 一行没碰聊天/WS,**接受**(见 Accepted deviations)。

**跑红的那几遍,一份不藏**(全部是我自己的动作,不是判据的问题):

```
runlog: oracle rc=1 commit=02e0435 dirty=no at=2026-08-12T02:02:56Z file=tracks/opendesign-cnum-zeropad/evidence/20260812T020256Z-01-oracle.txt
runlog: mutation-test rc=9 commit=0a6e943 dirty=yes at=2026-08-12T02:05:45Z file=tracks/opendesign-cnum-zeropad/evidence/20260812T020545Z-01-mutation-test.txt
runlog: redcheck-final rc=2 commit=1b421a5 dirty=yes at=2026-08-12T02:22:06Z file=tracks/opendesign-cnum-zeropad/evidence/20260812T022206Z-01-redcheck-final.txt
runlog: mutation-r2 rc=0 commit=0a6e943 dirty=yes at=2026-08-12T02:06:43Z file=tracks/opendesign-cnum-zeropad/evidence/20260812T020643Z-01-mutation-r2.txt
runlog: mutation-r3 rc=0 commit=1b421a5 dirty=yes at=2026-08-12T02:21:46Z file=tracks/opendesign-cnum-zeropad/evidence/20260812T022146Z-01-mutation-r3.txt
runlog: suite-all rc=3 commit=0a6e943 dirty=yes at=2026-08-12T02:07:08Z file=tracks/opendesign-cnum-zeropad/evidence/20260812T020708Z-01-suite-all.txt
runlog: suite-all-final rc=3 commit=1b421a5 dirty=yes at=2026-08-12T02:22:06Z file=tracks/opendesign-cnum-zeropad/evidence/20260812T022206Z-02-suite-all-final.txt
runlog: suite-all-v2 rc=3 commit=1454d6f dirty=yes at=2026-08-12T02:49:45Z file=tracks/opendesign-cnum-zeropad/evidence/20260812T024945Z-02-suite-all-v2.txt
runlog: redcheck rc=0 commit=0a6e943 dirty=yes at=2026-08-12T02:03:58Z file=tracks/opendesign-cnum-zeropad/evidence/20260812T020358Z-01-redcheck.txt
runlog: redcheck-final rc=0 commit=a3b1e7d dirty=no at=2026-08-12T02:30:17Z file=tracks/opendesign-cnum-zeropad/evidence/20260812T023017Z-01-redcheck-final.txt
```

(mutation-r2/r3、suite-all 那几遍是中间版本:靶子随实现移动重指过两次,总跑跑过四遍。)

- `oracle rc=1`:🔴 **执行腿没提交,那次 merge 是空的**(`Already up to date`),
  我在主树亲跑当场发现。**闸② 存在的全部意义就是这一下** —— 腿的自述写着"三条命令全绿"
  (它在自己那棵树里确实是绿的),而主树上一个字节都没变。
- `mutation-test rc=9`:变异脚本 W3 的替换串跟实际代码对不上 ⇒ **脚本硬失败**。
  这是设计好的行为(08-11 栽过三次"脚本自己坏了却报判据没咬住":假报警和假绿一样坏)。
- `redcheck-final rc=2`:红检**拒跑**,因为我的修复还没提交、实现路径是脏的。
  它不肯对着脏工作区下结论 —— 对的。

## Review

- lane: **full** —— 碰的是**受控写口的定位口径**(哪一行会被改写)+ **数据一致性**
  (读写两侧对同一行档案给出不同答案)。硬规矩上明写"针孔再薄也不打折",
  而且这次改的正是 0.83.0 刚对齐过的那对读/写正则,值一次独立的红检与四审。
  > **碰了新写口 / 权限 / auth / 钱 / 数据一致性 → full,针孔再薄也不打折**(硬规矩,别在这降档)。
  > fast = 主+1,中等风险;self = 主自审(闸③ + 截图 + 全量回归),
  > 限纯前端/纯观感、后端一字未动、只新增已过审针孔的调用方。
- 派给: **codex/gpt-5.5(隔离 worktree,`--track opendesign-cnum-zeropad`)** ——
  判卷**不用起服务**(纯 python 单元层,`tests/test_ds_cnum.py` 就能完整问出行为),
  改动面窄且已被 15 条判据钉死(四处锚点 + 入口归一),是执行腿的典型档位。
  oracle 我亲写并已先行单独 commit;实现文件不含判据文件,闸① 用 `--protect` 盯住。
  **不是"所以我自己干"** —— 07-31 那次四单全被我用同一句有洞的理由跳过分层,不再犯。
- 规格自查(读任何 panel 输出之前先答):**我的规格有两处可能就是错的**——
  ① **"备注行保前缀字节"**:这是攻题掰过来的,理由是"不擅自改业主档案"。但反过来说,
  业主真看到档案里留着 `- C03 备注:` 也可能觉得脏、希望工具顺手收拾。哪种对,
  **判据答不了,只有他自己看了才知道** ⇒ 真机清单里留一条问他。
  ② **`C03-1` 判成 3 号并且允许写**(N7):我选的是"读写两侧一致",不是"禁止这种写法"。
  如果他真拿 `C03-1`/`C03-2` 当子编号,那么改 3 号会改到"父"那条 —— 读侧本来就这么认
  (界面上早就显示成 C3),所以不是本单引入的,但**我确实在这条上做了选择而不是报警**。
  要报警得单开一单(lint 提示),得他点头。
- 我自己的 findings(**落在读任何 panel 输出之前**):
  - 🔴 **F1(已修,a3b1e7d)**:执行腿只给 `edit_change` 保留了"非词表状态行"的回退,
    共用的 `_rewrite_change_status` 没保 ⇒ 手写的 `- [搁置] C3 …` 改动前删得掉、
    改动后删不掉。**同一次改动里三个写口容差自相矛盾,而收紧的正是"手写档案"这条路** ——
    本单要救的就是它。判据原先问不出来(我全用规范状态词造题)⇒ 补 N8 + 变异 W8。
  - **F2(接受)**:`set_change_status` 的入参从严格 `C(\d+)` 放宽成 `C?(\d+)`,
    现在裸 `"3"` 也认。这是我任务书里"入口归一"要求的副作用,方向一致、风险有界
    (MCP 侧那个调用方本来就按工具说明传 `C3`)。
  - **F3(不改,记账)**:`_upsert_note` 为了拿 `m.start(2)` 内联了一份 `HISTORY_NOTE_RE`
    匹配,于是 `history_note_line_cnum()` 只剩 `_delete_note` 一个用户。轻微重复,
    但两处口径同源(都是那一份读侧正则),不构成第二套定义。
- 腿的花名册(原样粘自 `/root/aiwork/logs/panel-cnum-zeropad.roster`):

```
submimo=PASS subdeepseek=PASS subglm=off subkimi=FAIL(rc=1)
```

  ⚠️ **仍是 2/4**(智谱欠费默认 off、Kimi 额度 rc=1)。**别读成"四审过了"** ——
  这是连续第四轮 2/4 了。
  ⚠️ **反锚定这次是破的,如实记账**:引擎报了 `WARNING: anchor leak` ——
  我把自审 findings 先 commit 进了 `verify.md`,而它落在评审范围 `ff519d0..HEAD` 里
  ⇒ 两条腿看得见我的自审。**正确节奏是先派发、后写 verify.md**,下次改过来。
  所以下面 subdeepseek 那条 BLOCK 的价值要打个折扣地看:**它提的东西我没写过**
  (我的自审里根本没有"改正文会毁行"这个方向),这一条仍然是独立发现。
  > panel-review 收尾自己写这个文件(off / FAIL(rc) / 降级 都在里面)。
  > 08-06 立这条的理由:08-05 我在这里手写了"三条腿一致 PASS",而 Kimi 根本没出结论
  > (同一页第 90 行我自己还写着它没出报告)—— 手抄一份终端上的东西,抄错那次没人会发现。
- findings(逐条仲裁;我自己的 F1–F3 在上一格,是**读评审输出之前**落的):
  - 🔴 **[subdeepseek 孤腿 BLOCK,成立,已修 `1454d6f`]** `edit_change(new_text=…)` 打在
    `- [待确认] C03-1 …` 这种带后缀的行上会**静默毁行**。我发探针查证:**比它说的更狠** ——
    它说"丢 `-1` 后缀+日期",实际是替换后 C 号与正文之间的分隔被吃掉,变成
    `- [待确认] C03客厅刷米白`,**读回来 `cnum` 是 None ⇒ 这条变更从此没有编号、
    任何工具再也定位不到它**。改动前这条路是安全拒写的(旧锚够不着),是**本单放开的**。
    ⇒ 修法不是给这种形状打补丁,而是钉一条通用不变量:**重写正文的写入,写完之后
    这一行必须还能被定位口径读成同一条变更**;保证不了就 `malformed_change_line` 拒写、
    档案逐字节不动(ds_web 登记 409)。判据 N9 + N9b,变异 W9 + W10。
    **它同时点破我判据是瞎的**:N7 只对后缀行测了 `new_status`(走另一条不重写正文的路),
    没测 `new_text` —— 这正是"全绿但结果仍错"的口子。属实。
  - **[subdeepseek finding 2,LOW,成立,已修]** `delete_change` 的 docstring 还写着
    "不是照抄 set_change_status 那套严格 `C<n>` 校验" —— 本单之后这句话是假的
    (两者现在共用 `_parse_target_cnum`)。已改写。
  - **[subdeepseek 记的 by-design 后果,采纳为已知边界 + 真机一格]** 档案里若同时有
    软删的 `- [已删除] C03` 和存活的 `- [待确认] C3`,两行都读成 3 号 ⇒ **全部写口被
    `ambiguous_change` 挡住**(改动前旧锚还能改到 `C3` 那条)。这是 fail-closed 有意为之,
    但意味着业主得手工清重号。已写进 `docs/backlog.md` 和验收清单 J5b。
  - **[submimo LOW-1,查证后驳回]** 它说 `_upsert_note` 拼规范行时 `note` 里若含 `\n`
    会插成多行。**已核 `bin/ds_tools.py:527`:`edit_change` 入口就 `sanitize_field(note)`
    折了换行**,而 `_upsert_note` 是私有函数、唯一调用方就是它。这条路走不通。
  - **[submimo 其余]** 五个写口共用一个定义 ✅、六项数据安全逐条 ✅、判据覆盖 ✅、
    ds_web/MCP/ds_lint 无回归 ✅ —— 与我自审一致,但**它给的是 PASS,没抓到 BLOCK 那条**。
    两腿一 PASS 一 BLOCK,**我按 BLOCK 走**:孤腿 BLOCK 才是信号(而且这次它是对的)。
  - **[我自己的 F1,腿都没提]** 见上一格:五个写口容差自相矛盾(闸③亲读 diff 抓到)。
    **两条腿都没提这条** —— 再一次印证"全票 PASS 也不许降标准"。
  > 只写发现。腿的身份/降级不在这儿抄第二遍:日志自带身份牌(降级横幅 + 视野边界),
  > 花名册在上一格,查工件不查自述。
- arbitrated verdict (主裁): **PASS**。
  两腿的发现逐条对着代码/探针验过:subdeepseek 两条全成立(一条 HIGH 已修、一条 LOW 已修),
  submimo 唯一的 LOW 查证不成立、驳回。加上我自己抓的 F1(腿都没提),本轮一共修了
  **3 处**:执行腿的容差不一致、写完读不回来的毁行路径、过期 docstring。
  最终判据 29 条全绿、变异 10/10 咬住 0 漏网、红检红在目标断言、总跑五段无红。
  **本轮最值钱的一件事**:事前攻题(4 条,改了修法本身)与事后四审(1 条 HIGH)
  抓到的东西**完全不重叠** —— 两头都得做,这条在 08-11 记过一次,今天又验了一次。
  > **归档时这一条和顶部的 `Verdict:` 都不许还是占位符**,`track-guard` 规矩3 会挡;
  > 没归档但已经合并上线的,`track list` 会打 ⚠️(stage-timer 就这么漏了两个月)。

## Accepted deviations

- **两条要活 gateway 的 e2e 记 SKIP**(总跑 rc=3)。它们跑真 nanobot + 真模型,
  断的是协议/UI 事实,不断 LLM 内容;本单 diff 一行没碰聊天/WS 链路。**SKIP 不是 PASS,
  这里是明账不是遮掩。**
- **四审只有 2/4 腿**(智谱欠费 / Kimi 额度)。连续第四轮。
- **反锚定这轮是破的**(verify.md 的自审进了评审范围)。判断影响时已经打折看,
  且 BLOCK 那条方向我自审里根本没有。**下次先派发后写 verify.md。**
- **`C03-1` 这类后缀行"改正文"现在拒写**:选的是 fail closed。要支持得先定
  "`-1` 算编号还是正文",**产品问题,得业主点头**。已进 backlog + 验收清单 J5a。
- **不修其它手写歪法**(`- C3备注:` 少空格、全角 `Ｃ`、`C 3` 中间带空格):
  没有证据说业主真会那么写,要做另起一单。判据全绿 ≠ 他的档案能用 ⇒ 验收 J3 那一格
  就是专门问这个的(**只有他能答**)。
