# Verify: opendesign-tmpdir-gate-followup

- Date: 2026-08-18
- Verdict: **PASS**

## Mechanical checks

- [x] build passes(`dist 新鲜度` 段:重新 build 后 git 无差异)
- [x] tests pass —— 六段里五段绿、e2e 段红;**红的 2 条与跳过的 1 类都是既有欠账,与本单无关**
      (逐条点名见下面的「逐段」表与 Accepted deviations)。**不写「五段全绿」**:那句话会把
      python 段里一条自称「SKIP 不算通过」的判据吞掉 —— 老教训「`pytest 全绿` 那句话里
      不含整块 SKIP 的闸」的复发形状。
- [x] no secrets / unsafe ops(只动 `tests/`,产品代码零改动)

**机器打印的**(不是我的转述)—— 全部收据逐字节:

```
runlog: redcheck-A-mapfile-blind rc=1 commit=a4e1e46 dirty=no at=2026-08-18T03:27:59Z file=tracks/opendesign-tmpdir-gate-followup/evidence/20260818T032759Z-01-redcheck-A-mapfile-blind.txt
runlog: redcheck-B-truncation-marker rc=1 commit=a4e1e46 dirty=yes at=2026-08-18T03:28:03Z file=tracks/opendesign-tmpdir-gate-followup/evidence/20260818T032803Z-01-redcheck-B-truncation-marker.txt
runlog: runall-after-fixes rc=1 commit=a4e1e46 dirty=yes at=2026-08-18T03:31:10Z file=tracks/opendesign-tmpdir-gate-followup/evidence/20260818T033110Z-01-runall-after-fixes.txt
runlog: runall-final rc=1 commit=b550dc5 dirty=yes at=2026-08-18T03:51:05Z file=tracks/opendesign-tmpdir-gate-followup/evidence/20260818T035105Z-01-runall-final.txt
runlog: redcheck-C-marker-overfix rc=1 commit=b550dc5 dirty=yes at=2026-08-18T04:03:23Z file=tracks/opendesign-tmpdir-gate-followup/evidence/20260818T040323Z-01-redcheck-C-marker-overfix.txt
```

**逐条交代(红的一份都不许藏,5b)**:

| 收据 | rc | 它是什么 |
|---|---|---|
| `redcheck-A-mapfile-blind` | 1 | **红检**。判据 ⑭ 在修之前**实得 rc=0** —— 闸在 `mapfile` 缺席时报绿。这是全单唯一的真洞,也是它的硬证据 |
| `redcheck-B-truncation-marker` | 1 | **红检**。截断记号那条在修之前红 |
| `runall-after-fixes` | 1 | 修完的第一遍总跑。五段绿,e2e 2 条红(网关欠账) |
| `runall-final` | 1 | **断线之后重跑的一遍** —— 上一份跑在 11:31,而判据文件 11:42 又被写过一遍才 commit,那份绿是**跑在最后一次编辑之前**的,作废。这一份跑在 `b550dc5` 上 |
| `redcheck-C-marker-overfix` | 1 | **变异红检**。把 `clip()` 改成无条件加记号 ⇒ 新补的反面判据当场红 = 它咬得动。变异已还原并复核(`git status` 干净、grep 无残留、判据回绿) |

**权威的那一遍(结论所依据的就是它)** —— 工件与收据全部入库之后、工作树干净时跑:

```
runlog: runall-authoritative rc=1 commit=7d6d132 dirty=no at=2026-08-18T05:26:59Z file=tracks/opendesign-tmpdir-gate-followup/evidence/20260818T052659Z-01-runall-authoritative.txt
```

逐段(**汇总会撒谎,细节不会** —— 每一段都去日志里点了名):

| 段 | 结果 | 细节 |
|---|---|---|
| 泄漏闸自测(判据的判据) | PASS | 14 条全过 |
| node 单测 | PASS | 376 通过 / 0 跳过 / 0 todo |
| python 全量 + 死断言闸 | PASS | 1282 跑过 / **1 跳过** —— 那 1 条的身份见 Accepted deviations |
| MCP 契约闸 | PASS | 三条闸全绿 |
| dist 新鲜度 | PASS | 重新 build 后 git 无差异 |
| e2e 总跑 | **FAIL** | 34 PASS / **2 FAIL** / 2 SKIP;rc=1 全部来自这里 |

- **2 FAIL 逐条点名**:`frontend_p2_polish.e2e.mjs` / `todo_assistant.e2e.mjs` —— 与
  Accepted deviations 记的**完全一致,一条不多**(去 e2e.log 里逐行核过,不是读的汇总)。
- **2 SKIP 逐条点名**:`new_chat.e2e.mjs` / `project-thread.e2e.mjs`,原因栏明写
  "需要活 gateway,加 `--with-gateway` 才跑"。**这两条是诚实的 SKIP**(有前置检查、如实报告)
  —— 顺带印证了下面那条欠账的修法方向:FAIL 的两条缺的正是这个前置检查。
- **`1282 跑过` 比上一遍 `runall-final` 的 1281 多一条**:对得上 `208db51` 补的那条
  反面判据(短行不许挂截断记号)。数字不是白多的,来源查清了。

> **这一份是断线之后重跑的第二遍。** 08-18 12:08:04 起跑过一次,断线把它砍在第三段
> (收据 574 字节、无汇总行无 rc 行)。半截收据一律作废,已删,不入库 —— 留着它比没有更坏:
> 下一轮会有人把它当成一份绿收据读。同时清掉了那次被砍留下的 **676 个 `ds_consent_dist_*`
> 壳目录**(SIGTERM 让清理没跑成)。**这不是泄漏 bug 复发**:本遍跑完探针目录里
> `ds_consent_dist_*` 计数 = **0**,「一轮净增 0」的不变量成立。

## Review

- lane: **fast**
  > 判的是:这单**只动 `tests/`**,产品代码一字未改 —— full 的硬触发器(新写口 /
  > 权限 / auth / 钱 / 数据一致性)一条都没碰,所以不打 full。也不是 self:self 限
  > "纯前端/纯观感",而这里动的是**判卷防线本身**,风险不在那一档。
  > 另一个理由:这 12 条发现**本身就来自一轮三腿 full 审**,这是那一轮的收口,
  > 再开一次 full 是对同一份 diff 重复花钱。
- 派给: **主 agent 直接干** —— 改的东西**全是判据本身**(闸、闸的自测、死断言工具),
  本机硬规矩写死了「oracle 永远由主 agent 亲自写,绝不外包」,把判据交给执行腿
  = 让被查方改考卷。8 条也全是小手术,写任务书 + 收货三闸的成本高于自己动手。
- 规格自查(读任何 panel 输出之前先答,原文保留):这单的"规格"就是我对 12 条发现的
  **仲裁**,它最可能错在**我判「不改」的那三条**上,尤其是 ALLOW_WIDE 的匹配范围——
  subdeepseek 判它 MEDIUM、要求收窄到"只匹配断言行",我决定**不动判定逻辑**、
  只在报告里补出冲突行号。如果它是对的,后果是:某天一条 allow 的内容恰好和一条
  **活断言**逐字相同 ⇒ 硬红 ⇒ 人被逼去改那条无辜的断言。
  **另一件已经被证伪过一次的事**:上一轮四审三腿一致 PASS、说哨兵自检把洞"堵上了",
  而这一轮红检证明 `mapfile` 那条路根本没堵住(闸报绿)。**全票 PASS 不等于题是对的。**
  > 事后看,这一格押对了一半:两条腿都独立复核了 ALLOW_WIDE 那三条不改的判断并同意;
  > 但**它们抓到的两条我都没料到**,而且其中一条是我自审的**方法**漏了(见 findings F1)。
- 主 agent 自审(先于读任何腿的日志,仓外落盘):
  `/root/aiwork/tasks/tmpdir-gate-followup-my-review.md` → PASS + 1 自审发现 + 2 疑点
  `[仓外不承重]`
- 腿的花名册(原样粘自 `/root/aiwork/logs/panel-tmpdirgatefollowup-0818.roster`):
  `submimo=PASS subdeepseek=PASS subglm=off subkimi=off`
  > kimi 是我关的(`PANEL_KIMI_LEG=off`),不是它挂了:fast lane 要的是主+1,
  > 这里实际跑了 2 条。glm 是默认 off(欠费)。
  > **PASS = 进程 rc=0,不等于给了裁决** —— 两条腿的报告我都通读了,都真给了结论。
- **反锚定的实际状况(必须记账)**:派发时 `PANEL_DIFF_BASE=46fbbe8` 把 `a4e1e46` 整个
  包了进去,而那个 commit 里就有本 track 的 `proposal.md`(我的逐条仲裁)和 `verify.md`。
  引擎也报了 `WARNING: anchor leak`。subdeepseek 的日志显示它**确实读了** proposal.md
  和 verify.md。所以这一轮两条腿的"独立性"是**打了折扣的** —— 它们看得见我的答案。
  这削弱的是"它们同意我"的分量,**不削弱它们提出的反对**(那两条我自己跑过、都成立)。
  下次同形状的收口单:diff 基线只给代码 commit,或者把 track 工件留到派发之后再 commit。

### findings(逐条仲裁,不认腿的自述)

- **[接受并修] subdeepseek:`tests/run-all.sh:93` 段号重排留下重复的旧 ⓪ 标题。**
  已核:第一段同时挂着 `⓪ 泄漏闸自己的判据` 和 `① 泄漏闸自测(判据的判据)`,
  两段重复的"为什么放最前"理由并排。**这条我自审时漏了 —— 而且是方法漏的**:
  我 grep 的是 `①|②|③|④|⑤|⑥|⑦`,**没把 ⓪ 放进去**,于是那一行结构上不可能被我看见。
  修法:并成一个 ① 标题,旧块里"08-05 孤儿脚本"那段历史并进来(有价值,不删)。`7cecd00`
- **[接受并修] submimo:`tests/e2e/README.md:7` 还写着「四段一条命令…其中第四段」。**
  已核属实(总跑早就是六段、e2e 是第六段)。**没有改成"第六段"**:改序号治不了病,
  下次插段它照样过期(同一天已栽三次同类)。换成按名字指 **e2e 那一段**。`7cecd00`
- **[接受并修] subdeepseek [INFO]:截断记号的判据只钉「长行有记号」,不钉「短行没有」。**
  成立:一个无条件给每行加记号的实现能全绿,而记号一泛滥,真被截断的那行反而认不出。
  已补反面判据 + **变异红检**证明它咬得动。`208db51`
- **[驳回] subdeepseek:「`runall-final` 收据是截断的,只有 14 行」。**
  **不成立,但它没说谎**:它 11:58 读那个文件时我的总跑(11:51 起)还在跑,读到的是
  半截。现在 33 行完整、汇总和收据行都在(已复核)。
  > 值得记一笔的不是这条错了,是**评审腿读的是活文件**:证据目录在跑的时候不是不动的。
- **[我的自审发现,不改] `tests/run-all.sh:119`「文件头列的第 ③ 次复发」。**
  文件头明写"假绿的**两种**已知形态"(①②),没有 ③。但另一种读法说得通
  (=指"存在的理由"里第 ③ 条 08-05「孤儿脚本没人调」的复发,而这确实是同一种病)。
  `git blame` 确认 08-15 `d0ab8b6` 写的,**不在本单 diff 内**。判:不改,记在这儿免得下轮重提。
- **[两条腿都独立复核并同意的三条]** ALLOW_WIDE 不收窄 / 只跳过就收日志 / 正常路径 find
  的 stderr —— 均维持不改,理由在 proposal。**但见上面那条反锚定记账:它们看得见我的答案,
  这份"同意"要打折。**
- **[两条腿都独立命中我最担心的那一处并证伪了风险]** `clip()` 会不会污染放行**匹配**:
  两条腿各自读了 `load_allow:304`,都确认比的是源文件原始行、`clip()` 只进报告显示。
  与我自审的结论一致。

- arbitrated verdict (主裁):**PASS**。
  A 是真洞、有红检收据,修法两条腿独立重推并确认;其余七条是"别让闸指错门",
  全部只动注释/文案/报告。本轮两条腿提了 4 条,**3 条成立已修、1 条驳回并写明为什么**;
  我自审漏的那条(⓪)正是 panel 该抓的东西 —— 不是我不知道要查,是**我查的方法有洞**。

## Accepted deviations

- **e2e 两条红:`frontend_p2_polish.e2e.mjs` / `todo_assistant.e2e.mjs`。**
  两条都卡在等 `[data-ui="connect-card"]` —— 它们**悄悄依赖这台机器上有没有活 gateway**,
  本机没起。上一单归档时挖出来的既有欠账,**与本单零关系**(本单只动 `tests/` 里的
  闸与注释,碰不到前端)。总跑的 rc=1 全部来自这里。**这一单不修**:修它是单独一单
  (要么给它们加 gateway 前置检查并如实记 SKIP,要么让总跑带 `--with-gateway` 跑)。
  > **补一笔诚实账(08-18 收口时才发现)**:「它们依赖活 gateway」这个定性,在今天之前
  > **从来没有被验证过** —— 是我从报错现象推出来的。今天我试着起 gateway 去证实它,
  > **没起成**:`bin/ds-nanobot gateway` 报 `Environment variable 'DS_LLM_KEY' … is not set`。
  > **⚠️ 我第一遍把这条判错了,当场更正(留着错判的过程,因为它本身是教训)。**
  > 我原先写的是"这不是 bug,两套 config 形状不同而已"。**错。** `bin/ds_credential.py:10-11`
  > 写死了这条不变量:**Windows 那份引用 `${DS_LLM_KEY}`,Linux 那份引用 `${MIMO_TP_KEY}`**。
  > 而本机 `~/.nanobot/config.json` 实测引用的是 `${DS_LLM_KEY}`,MCP server 的路径还是
  > `${USERPROFILE}/.venvs/design-studio/Scripts/python.exe`(Windows 路径),mtime 停在
  > **08-15 13:24**。也就是说:**这台 Linux 机上装着的是 Windows 那一份配置** —— 这是
  > 上一单归档时就记下、至今**没有根因**的一笔敞着的账(疑似判据改了我的机器,
  > 见 tmpdir-leak 那单的「还敞着的两笔账」)。gateway 在这台机器上起不来是**那笔账的后果**,
  > 不是正常状态。**这个区别很要紧**:照我第一遍的错判,下一轮会以为"Linux 起不来天经地义"
  > 而不去查那份被换掉的配置。
  > **我就此停手,没有去给它凑 key** —— 那等于给判据接一个真 LLM 后端,
  > 正撞上更硬的那条规矩(判据不许有外网出口;08-10 判据自己去叫 kimi、一上午烧光额度)。
  > 所以到今天为止,这条定性仍是**未经实测的假设**。那"单独一单"要做的第一件事是**先证实它**,
  > 别直接照着假设去改判据 —— 而证实它的**前置条件**已经清楚了:先把本机那份被换成 Windows
  > 形状的 `~/.nanobot/config.json` 恢复成 Linux 那份(引用 `${MIMO_TP_KEY}`),gateway 才起得来。

- **python 段那 `1 跳过` 的身份:`tests/test_ws_protocol_smoke.py`(整类 SKIP,连带 16 条断言没被问到)。**
  跳过原因:`gateway 未在 127.0.0.1:8765 运行`。**必须点名的理由**:这个文件头自己写着
  「**SKIP 不算通过**:verify 收口与升级 nanobot 前,必须见到实跑绿」—— 而本 verify 原先
  只写「六段里五段全绿」,读起来像"除 e2e 外无事",**把这条自我声明不算通过的判据静默吞掉了**。
  这正是老教训「`pytest 全绿` 那句话里不含整块 SKIP 的闸」的复发形状,所以在这里点名记账。
  **本单接受它继续 SKIP**,理由三条:① 它测的是 nanobot WebUI 协议,本单只动 `tests/` 里的
  闸与注释、产品代码一字未改,碰不到它;② 要它实跑绿就得给判据接真 LLM key,与「判据不许有
  外网出口」直接冲突,两条规矩撞车时防花钱那条优先。③ 它在本 track **全部**收据里都是
  `1 跳过`(不是本单引入的新状态)。
  > 死断言闸这里表现是对的:它没把这 16 条算成"死断言",而是单列成「在被跳过的判据里」并
  > 逐条打印。**是它让我查出了这条 SKIP 的身份** —— 没有它,`OK (skipped=1)` 里什么都看不出来。
- **`_selfcheck=()` 的 bash 版本前提**:见 design.md「Key trade-offs」。本机 bash 5.x,
  判据绿;更老的 bash 上这个洞可能原样复活。已知边界,本轮不改。
- **本轮两条腿的独立性打折**(反锚定泄漏,见上)。已写下下次的做法。
