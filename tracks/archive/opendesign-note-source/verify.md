# Verify: opendesign-note-source

- Date: 2026-08-11
- Verdict: PASS

> Panel hook —— 软判断走 panel-review;主 agent 先独立审并落 findings,再读腿的输出,主裁。

## Mechanical checks

- [x] build passes(`web` 重 build 后 `git status -- web/dist` 为空)
- [x] tests pass(node 350 / python 1023 跑过 0 跳过 / MCP 契约闸 / e2e 34 PASS 0 FAIL)
- [x] no secrets / unsafe ops(无新依赖、无新端口、无新落盘文件;写口只多了一条 400 分支)

**机器打印的**(不是我的转述)。**跑过的每一遍都在这儿,红的、假的一遍都不藏**(规矩 5b):

**判据先行,红过两轮**(实现之前):
```
runlog: oracle-red-before-impl rc=1 commit=5614905 dirty=yes at=2026-08-11T06:29:54Z file=tracks/opendesign-note-source/evidence/20260811T062954Z-01-oracle-red-before-impl.txt
runlog: oracle-red-after-attack rc=1 commit=c5855d9 dirty=yes at=2026-08-11T06:50:57Z file=tracks/opendesign-note-source/evidence/20260811T065057Z-01-oracle-red-after-attack.txt
```

**e2e 判据的红**(I 组,实现之前),四份,含**一份我自己造的假收据**:
```
runlog: e2e-I-red rc=0 commit=5614905 dirty=yes at=2026-08-11T06:30:46Z file=tracks/opendesign-note-source/evidence/20260811T063046Z-01-e2e-I-red.txt
runlog: e2e-I-red-honest-rc rc=1 commit=5614905 dirty=yes at=2026-08-11T06:32:50Z file=tracks/opendesign-note-source/evidence/20260811T063250Z-01-e2e-I-red-honest-rc.txt
runlog: e2e-I5-I6-red rc=1 commit=c5855d9 dirty=yes at=2026-08-11T06:51:49Z file=tracks/opendesign-note-source/evidence/20260811T065149Z-01-e2e-I5-I6-red.txt
runlog: e2e-I7-anchor rc=1 commit=6988bc7 dirty=yes at=2026-08-11T06:58:41Z file=tracks/opendesign-note-source/evidence/20260811T065841Z-01-e2e-I7-anchor.txt
runlog: e2e-I8-final rc=1 commit=6988bc7 dirty=yes at=2026-08-11T07:04:05Z file=tracks/opendesign-note-source/evidence/20260811T070405Z-01-e2e-I8-final.txt
```
> 这五份的 rc=1 都是**判据在旧实现下该红**;每一份里 A–H 全绿、红的只有 I 组
> (`e2e-I7-anchor` 那份里 I7 自己是绿的 —— 它是防坑锚不是红检证据,性质写在文件里)。
> **这份收据是 `track archive` 的 5b 闸替我找出来的**:我漏引了它,守卫拒绝归档。
> 它挡的正是"只贴好看的那几份"。
> ⚠️ 第一份 `rc=0` **是假的**:我给命令接了 `| tail -45`,管道把 e2e 的 `process.exit(1)`
> 吃掉了,收据正文里明明白白写着"6 条不通过"。留着不删。

**红检(形式版:把实现真退回本单之前)**,两份,**又是同一个错**:
```
runlog: redcheck rc=1 commit=0c3a6d0 dirty=yes at=2026-08-11T07:46:42Z file=tracks/opendesign-note-source/evidence/20260811T074642Z-01-redcheck.txt
runlog: redcheck-honest-rc rc=0 commit=0c3a6d0 dirty=yes at=2026-08-11T07:47:39Z file=tracks/opendesign-note-source/evidence/20260811T074739Z-01-redcheck-honest-rc.txt
```
> 第一份 `redcheck` 判"旧实现下判据仍然绿 ⇒ 这份判据证明不了任何事"——**它读到的是我
> 喂给它的假绿**:我传的 `--oracle` 里又接了 `| tail -3` 和 `| grep`,rc 被管道吃了。
> 去掉管道重跑(第二份):**红检通过,且红在 `changed_fields|note|parse_history` 上**。
> **同一个错误我今天犯了两次**,两次都是自己复查发现的 —— 记在这儿,见 findings M4。

**实现之后**:
```
runlog: e2e-after-impl rc=0 commit=6b41e58 dirty=yes at=2026-08-11T07:31:49Z file=tracks/opendesign-note-source/evidence/20260811T073149Z-01-e2e-after-impl.txt
runlog: full-suite rc=3 commit=0c3a6d0 dirty=no at=2026-08-11T07:38:22Z file=tracks/opendesign-note-source/evidence/20260811T073822Z-01-full-suite.txt
```

**四审之后**(判据 I9 先红,再修三条):
```
runlog: e2e-I9-red rc=1 commit=8f2737c dirty=no at=2026-08-11T08:09:35Z file=tracks/opendesign-note-source/evidence/20260811T080935Z-01-e2e-I9-red.txt
runlog: e2e-after-low-fixes rc=0 commit=8f2737c dirty=yes at=2026-08-11T08:10:39Z file=tracks/opendesign-note-source/evidence/20260811T081039Z-01-e2e-after-low-fixes.txt
```

**权威的一遍(工作树干净,覆盖真实 HEAD)** —— 五段全 PASS:
```
runlog: full-suite-final rc=3 commit=52cf830 dirty=no at=2026-08-11T08:11:29Z file=tracks/opendesign-note-source/evidence/20260811T081129Z-01-full-suite-final.txt
```
> `rc=3` **不是判据红了**:五段全 PASS,3 来自总跑自己的口径「有 2 条没跑 = 不算通过」。
> 那 2 条(`new_chat` / `project-thread`)要起活的 nanobot gateway,与本单无关
> (本单一行代码没碰对话面)。**照抄不四舍五入。**

汇总数字(以权威那遍为准,权威仍是收据文件本身):node **350** / python **1023 跑过 0 跳过**
(死断言闸 0 条从未执行)/ MCP 契约闸三条 / dist 与源码同步 / e2e **34 PASS 0 FAIL 2 SKIP**。
本单那份 e2e(`ws_change_note`)**A–I9 共 17 组全绿**。

oracle-first commit:`c5855d9`(零实现文件);攻题后补强 `6988bc7`、`3fe3aba`;
判据自己的漏 `6b41e58`;四审补的判据 `8f2737c` —— **五笔判据全部在对应实现之前**,git 里查得到。

## Review

- lane: full —— 数据一致性面(读模型换住址、写口契约改述、推翻六条既有断言),不降档。
- 派给: `delegate-codex --model gpt-5.5`(PR 级实现档)。**返工 0 轮;执行腿自身错误 0 处。**
  闸①(机械版 `--receive`):判卷逐字节没动、判卷路径下没有多出来的文件,
  它只碰了任务书允许的 7 个文件。**它交活时如实报了"我没跑哪些检查",并且**
  **在发现"任务书要求删掉的名字、判据却还在调"时没有偷偷加回别名让自己变绿,而是报回来**
  —— 那处冲突的根因在我的判据(已 `6b41e58` 单独修)。
  起端口的两层(HTTP/chromium)按抽屉的默认路由由我当测试机亲跑。
- 规格自查(读任何 panel 输出之前先答):

  这一单的核心赌注是 **"前端只报『用户碰没碰过这个框』,后端独判『到底变没变』"**。
  如果这条赌错了,最可能错成这样:**"碰过"这个概念本身在 UI 里不成立** ——
  比如某个输入框在渲染时就被 `onChange` 打过一次(受控组件的常见写法)、或者
  预填值经过一次 normalize 也算 touched,那么"没碰过的字段不发"就是句空话,
  覆盖窗口照样开着,而所有纯函数判据仍然全绿(它们自己构造 `draft`,前提是自证的)。

  我怎么发现:**判据 I5 是唯一能证伪它的东西** —— 它在真浏览器里开着编辑器、
  让别人从写口改掉那条备注,再只改正文保存,断言别人的新值没被盖回去。
  这条今天(旧实现下)是绿的,改完之后仍然绿,两头都验过。
  **第二条赌注**:`note=""` 当"没有备注"(而不是 `null` 当删除、`""` 回 400)。
  理由见 design §6;**我拿不准,专门写进任务书让四审盯**(结果见 F5)。

- 腿的花名册:
```
submimo=PASS subdeepseek=PASS subglm=off subkimi=FAIL(rc=1)
```
  > `PASS` 只是进程 rc=0。**实际给出裁决的是 2 条腿**(submimo / subdeepseek,均判 PASS)。
  > subglm 这次连派都没派(`off`,`PANEL_GLM_LEG=agent` 没开回来 —— 智谱欠费的后遗症),
  > subkimi 额度挂掉。**又是 2/4,不许读成"四审过了"。**

- findings:
  - **M1(我自审,已修)**:`changed_fields` 从 `set` 直接 `list()` ⇒ 顺序跨进程会变。
    语义是集合没错(判据按集合比),但 API 每次跑出不同顺序会让日志/回归对不上。
    已固定成 `status→text→note`。
  - **M2(我自审,已修)**:搬家之后 `_section_bounds` 在 `ds_todo`/`ds_tools` 各留一份 ——
    **一件事两处定义,正是这一单要消灭的形状,而且是我的设计造成的**。
    已收进 `ds_common.section_bounds`。
  - **M3(我自审,已修)**:我的判据自己漏改了两处旧名字(见"派给"那格)。
  - 🔴 **M4(过程,记给我自己)**:**同一个低级错误今天犯了两次** —— 命令后面接管道,
    把失败的 rc 吃掉,于是收据显示"通过"而正文写着失败。第二次更糟:它让 `redcheck`
    对着假绿判出"这份判据证明不了任何事",**差一点让我去改一份其实没问题的判据**。
    两次都是自己复查抓到的,坏收据都留着。**下次写 runlog/redcheck 的命令,
    管道之前先想清楚 rc 从哪来。**
  - **F1(攻题,已折进判据)**:`changed_fields` 只考了生产者、没考消费者 ⇒ 补 I6;
    I6 只是负向锚(把「改过·看原文」删掉它也绿)⇒ 补 I7;两条仍不能逼前端真看
    `changed_fields` ⇒ 补 I8(让前端手里的过期旧值与档案现值打架)。
  - **F2(攻题,已折进判据)**:I1 原来走 HTTP 写入,**进程内缓存也能让它全绿** ⇒
    改成绕开服务直接写磁盘。
  - **F3(攻题,已删)**:`test_n08` 用猴补丁数 `parse_history` 调用次数 ——
    测的是函数接缝不是复杂度,**会误伤"一次线性扫"的合理实现**。删掉,
    "每文件只解析一次"退回 design 当实现指引。
  - **F4(攻题,抓到我判据自己的两个 bug)**:I8 的"不许留痕"断言**必然失败**
    (别人改成 X 那一次本来就会合法留痕);I8 保存后只等 300ms 就 `count()===0`,
    行没渲染出来也会绿。都已修成"业主保存前后档案逐字节不变"+"先等行出现"。
  - **F5(四审 submimo,回答了我最不确定的那格)**:`note=""` 当删除的先例
    (`ds_refs.update_ref`)**本身站得住** —— 它逐行核了 `ds_refs_server` 的
    `style=""/space=""` 转 `None` 而 `note=""` 透传,指出这是**有意的不对称**
    (多值字段 vs 单值文本),不是随手写的。**保持一致不是抄错。**
  - **F6(四审 subdeepseek,LOW-3 → 已修,判据 I9 先红过)**:手写的 `- Cn 备注:`
    (冒号后为空)读出来是空串,`note !== undefined` 的渲染条件会长出**一个空的
    「备注:」标签**。工作区一直有这毛病,而**本单刚给待办页新开了这个面** ——
    上一单(0.83.0 H 组)才刚在待办页消灭过空标签。两个页面一起堵。
  - **F7(四审 subdeepseek,INFO → 已改)**:`ChangesColumn.pickStatus` 还留着
    `next === c.status` 的前端同值跳过 = 第二个判官。已去掉。
    **老实说清:这处可观察行为不变**(以前不发请求,现在发一次、后端不写盘),
    **没有任何判据能咬它**,它是靠闸③人读的纪律性清理 —— 不装作它被判据保着。
  - **F8(四审 subdeepseek,LOW → 已修)**:`collect` 的 docstring 没写可选 `note`。
- arbitrated verdict (主裁): **PASS**。

  两条给了裁决的腿都判 PASS,我逐条对代码验过,不是采信自述。四审提的四条:
  两条修了(F6 判据先行 + F8)、一条改了并如实标注它没有判据(F7)、一条是替我
  回答不确定项(F5)。我自己的 M1–M3 在读它们之前就已经改完并写在 my-review 里。
  机械面:权威那遍五段全 PASS,红检(真退回实现)红在目标断言上。

  **全票不降标准**:这轮 2/4 腿,而且**最值钱的发现全部来自"派活前攻自己的题"那一步**
  (F1–F4,含我判据自己的两个 bug),不是来自事后评审。这与上一单相反
  (上一单是四审抓到我人眼漏掉的死锁)—— **两头都得做**。

  **仍然只有真机能答的那格**:业主机器上那份两年的老档案,备注行格式可能比判据里
  造的更歪(全角冒号已覆盖、手写前导零 `C03` 已知不覆盖且记了账)。
  验收清单让他**挑一条很久以前写的备注**看还在不在,并**换台电脑**再看一次
  (e2e 只能证明刷新后还在,证不了换机器)。

## Accepted deviations

- **陈旧编辑保护仍然没有**:业主打开编辑器期间别人改了他**碰过**的那个字段,
  他保存仍会盖掉。业主明确说这一单先不做,在 `docs/backlog.md` 排队。
  本单只保证**不把窗口开大**(没碰过的字段不回发,判据 I5 钉住)。
- **手写前导零 cnum**(`- C03 备注:`)读写两侧仍不齐 —— 上一单记的账,没搭车改。
- **e2e 的天花板**(攻题指出、我接受):即便有 I8,"保存前先重新 GET 一次再比较"的实现
  也能全绿 —— e2e 锁的是行为,证明不了内部读了哪个字段。
- **`ds_tools._section_bounds` 名字留成薄壳**(`ds_lint` 按这个名字调它),
  真身在 `ds_common.section_bounds`。下次动 `ds_lint` 时顺手改掉调用点。
