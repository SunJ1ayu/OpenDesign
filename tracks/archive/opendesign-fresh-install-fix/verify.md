# Verify: opendesign-fresh-install-fix

- Date: 2026-08-25

## Mechanical checks

**机器打印的收据 —— 两份,最后一次编辑之后跑的:**

① 宽口(总跑六段):

```
runlog: run-all rc=3 commit=bddf85f dirty=no final=yes at=2026-08-25T05:27:41Z file=tracks/opendesign-fresh-install-fix/evidence/20260825T052741Z-01-run-all.txt
  PASS  泄漏闸自测                14 条全过
  PASS  node 单测                 376 通过 / 0 跳过 / 0 todo
  PASS  python 全量 + 死断言闸    1338 跑过 / 1 跳过
  PASS  MCP 契约闸                三条闸全绿
  PASS  dist 新鲜度 + 类型检查    与源码同步
  PASS  e2e 总跑                  36 PASS / 0 FAIL / 2 SKIP
```

🔴 **`rc=3` 不是红,是"3 条没跑",总跑自己就说了「不算通过」——别把跳过糊成通过。**
那 3 条是**同一个原因**:这台机器上没有活网关。
`tests/test_ws_protocol_smoke.py` 文件头写着「gateway 没在跑 → 整体 SKIP」(1 条),
另外 2 条是要 `--with-gateway` 的 e2e。**六段本身全 PASS,零红。**

② 窄口(本单自己的判据 + 邻近回归 + `.nsi` 静态闸),**rc=0**:

```
runlog: oracle-final rc=0 commit=bddf85f dirty=yes final=yes at=2026-08-25T05:39:29Z file=tracks/opendesign-fresh-install-fix/evidence/20260825T053929Z-01-oracle-final.txt
  tests/test_ds_provision.py       22 条(含 f1/f2/f3)
  tests/test_installer_silent.py    4 条(s1~s4)
  tests/test_ds_merge_config.py     9 条
  tests/test_no_console_window.py   3 条
  installer/check-installer.py static  23 条,0 条不合格
```

🔴 **跑红过的那四遍,收据行逐字节贴在这儿,旁边写明为什么不算数** ——
删掉才是造假,贴出来说清楚不是:

```
runlog: run-all rc=1 commit=da50f39 dirty=yes at=2026-08-25T03:02:59Z file=tracks/opendesign-fresh-install-fix/evidence/20260825T030259Z-01-run-all.txt
runlog: run-all rc=1 commit=ae72029 dirty=yes at=2026-08-25T03:14:25Z file=tracks/opendesign-fresh-install-fix/evidence/20260825T031425Z-01-run-all.txt
runlog: run-all rc=1 commit=98186e1 dirty=no final=yes at=2026-08-25T04:34:35Z file=tracks/opendesign-fresh-install-fix/evidence/20260825T043435Z-01-run-all.txt
runlog: run-all rc=1 commit=526e559 dirty=no final=yes at=2026-08-25T05:12:18Z file=tracks/opendesign-fresh-install-fix/evidence/20260825T051218Z-01-run-all.txt
```

逐份说清楚:

- `20260825T030259Z` —— **真红**:`test_no_console_window` 逮到我把
  `# no-console-exempt:` 注释和它守的 `subprocess.run` 之间插了说明 ⇒ 豁免当场失效。
  **闸干得对**,已修(注释挪回紧贴调用,并在那儿写明这一行必须紧贴)。
- `20260825T031425Z` —— **过期的绿**:跑在 `ae72029`,而之后 `7976633` 又改了
  `installer/OpenDesign.nsi` 和 `tests/test_installer_silent.py`。
  **绿是真的,但它证明不了当前这棵树** ⇒ 重跑。这是本项目栽过多次的
  「我给的绿是过期的」,这次是接手断线现场时自己抓住的。
- `20260825T043435Z` / `20260825T051218Z` —— 也过期:那之后才有 f3、解码侧修复,
  以及放行清单那一条。**它们那条红**是 `tests/test_installer_slim.py:216` 的死断言
  (归 `opendesign-installer-slim`,那一单至今零 run-all 收据),
  **本单一个字都没碰过那个文件**;三遍收据里它的位置和内容完全一样。
  归档闸要一份成功的 run-all,把这笔账催了出来 ⇒ 已按格式登记进
  `tests/dead_assertions.allow`(理由:同文件 g5 已在报同一件事,这是防御分支),
  见 `bddf85f`。**不是调钝报警器,是把冗余断言登记在案。**

**承重的是上面那两份(①②,都是 `final=yes`)。**

**那一条红不是本单改出来的,证据在下面 —— 但也不许拿它当"绿"用。**

- python 用例本身 **`OK (skipped=1)`**(1338 条),红的是**死断言闸**:
  `tests/test_installer_slim.py:216 self.fail("SLIM_DROP 是空的 …")` 一次都没执行过。
- 溯源:`git log -S` ⇒ 该断言来自 **`393ab8f`(track `opendesign-installer-slim`,08-24)**,
  本单一个字都没碰过那个文件。而那一单**至今没有任何 run-all 收据**——
  **它是"加了一段没人跑的判据"留下的账,归它**,已写进后续单
  `opendesign-nsi-gate-in-run-all` 的第 3 条。
- 三遍收据里这条红的**位置和内容完全一样**(1336→1337→1338 只是我这单在加判据),
  所以它不是被本单动出来的。

**本单自己的判据(逐条亲跑)**:

- `tests/test_ds_provision.py TestNonChineseWindows`
  - f1/f2 —— 2 条,绿(修之前红,见 `da50f39`)
  - **f3 —— 绿(修之前红,见 `520c969`)**:panel 抓到的解码侧洞,判据先红后绿
- `tests/test_installer_silent.py` s1~s4 —— 4 条,绿(修之前 s2/s3 红)
- 邻近回归:`test_ds_merge_config` 9 条、`test_no_console_window` 3 条,全绿
- `.nsi` 静态闸 `check-installer.py static` 23 条,0 条不合格
  (它**不在总跑里** —— 这正是 finding #2,已开后续单)

🔴 **f3 的题面自己先错过一版**:桩脚本里我往 `bytes` 字面量塞了中文 ⇒ **语法错**,
它压根没跑到"写非 UTF-8 字节"那一步,而判据**照样绿**。
**红在别处 = 等于没红检过。** 改对之后才真红(栈是 `UnicodeDecodeError` 从
`subprocess` 解码层甩出来的),注释已留在判据里。

## Review

- **规格自查**(在任何外部评审之前):这一单的规格如果错了,最可能错在
  **"把输出编码改成永不失败"会不会掩盖真正的失败**。我的判断是不会:
  `errors="replace"` 只作用在**打印**上,合并/写盘的成败仍由返回码和文件本身决定;
  而原来的行为是**成功的合并被一句提示判成失败**,方向正好相反。
  ⇒ 两条腿都独立复核了这一条,均判不掩盖;subglm 还实际复现了修前/修后两侧。

  🔴 **我自审写下的第二条是错的,已被实测推翻。原文留在这儿,不许悄悄改掉:**
  > 「第二个可能错的地方:`/SD IDCANCEL` 让"目录非空"这条在静默安装下**直接中止安装**
  > —— 无人值守时这是保守侧……**这是有意的**,写在判据 s3 的注释里。」

  实测(云机器 run 32811517481,`evidence/20260825-云机器-静默装进非空目录-*.txt`;
  判读规则写死在探针脚本头部、**看结果之前**):

  ```
  /S /D=一个非空目录  →  退出码 0、40s **装进去了**,没有任何拦截
  装完                →  业主原有的文件还在、内容没变
  静默卸载            →  **业主的文件没了**(哨兵认门通过 ⇒ RMDir /r 整棵删)
  ```

  原因:`CheckDirEmpty` 挂在 MUI 目录页的 **leave 回调**上(`OpenDesign.nsi:82`),
  NSIS 在 `/S` 下跳过所有页面 ⇒ 它根本没被调用;而 `/SD` 只在静默下起作用
  ⇒ 那句 `/SD IDCANCEL` **在它唯一生效的模式里是惰性的**。
  这是**存量**口子(0.98 之前也一样,不是本单引入),已开后续单
  `opendesign-silent-install-dir-guard`,收口标准写死为"再跑一次探针看到
  PHASE 3 拒装、PHASE 7 业主文件还在",不是本机判据绿。

- **腿的花名册**(机器写的,别手抄):

  ```
  # impact-risk=high requested-budget=2 selected-count=3 escalation=failure
  # selected=submimo(xiaomi/submimo),subglm(zhipu/subglm-agent),subkimi(moonshot/subkimi)
  # snapshot=head:2626df1
  submimo=PASS(verdict=UNKNOWN) subdeepseek=SKIP(rotation) subglm=PASS(verdict=PASS) subkimi=FAIL(rc=1)
  ```

  成功的外部腿:**submimo(xiaomi)+ subglm(zhipu),两个不同家族** ⇒ 满足 high=2。
  submimo 的 `verdict=UNKNOWN` 是**匹配不上结论行**,不是没给结论 —— 开日志确认它
  写的是"通过,附两条建议"。subkimi 挂在**凭证没配**
  (`provider managed:kimi-code has no credential configured`),日志 517 字节、
  无实质内容 —— **这条腿现在等于不存在**,记在敞账里。

- **反锚定:这一轮泄漏了,如实记账。** `verify.md` 在派发之前就已 commit 在树上
  (`98186e1`),底座腿自己读仓库就够得着,`git checkout` 堵不住。唯一没泄漏的是
  **结论**(verdict 当时是空的)。而 finding #5 恰好说明这个泄漏是有代价的:
  submimo 复述了我写错的理由。下一单按抽屉里的节奏:**先派发、后落工件**。

- **findings(逐条对账,每条都给依据)**

  | # | 来源与内容 | 我的处置 |
  |---|---|---|
  | 1 | **subglm MED**:`/SD IDCANCEL` 在 `/S` 下不可达,verify 的自查基于错误的 NSIS 行为模型 | **接受,并已实测坐实,而且比它说的更狠**——不只是"防线没兑现",是卸载会**真的把业主的文件删掉**。它诚实声明了自己按文档判读、环境里没有 makensis,所以我去量了一次。已开后续单。 |
  | 2 | **subglm MED + submimo 第 5 点(两腿独立命中)**:`.nsi` 语法在 `run-all.sh` 里没有任何闸 | **接受**。已核:六段零命中;`installer/check-installer.py` 的 17 条静态闸是纯 Python、不需要 makensis,却**从没被总跑叫起来过**。已开后续单 `opendesign-nsi-gate-in-run-all`。 |
  | 3 | **subglm LOW**:`ds_provision.py` 解码侧仍是 strict ⇒ `UnicodeDecodeError` 甩栈 | **接受并已修**(补 `errors="replace"`,判据 f3 先红后绿)。**这是我自审两遍没看见的,而且它就在我这一单亲手改过的那一行上**——同一条管道两个方向,我只修了一个方向。 |
  | 4 | **subglm INFO**:`launcher.nsi` 那两个不带 `/SD` 的框是**故意的**,别顺手补齐 | **接受**,已核(`launcher.nsi:24 SilentInstall silent`,:39/:45 两个框是业主唯一的报错出口)。写进 s2 注释当墓碑。 |
  | 5 | **submimo**:四处 `/SD` 默认值"全部正确" | **驳回一处**。它把 `CheckDirEmpty` 那条判成"✅ 正确。唯一涉及数据风险的,静默时选保守侧"——**那正是我自己写错的理由,它复述了一遍**。这就是复核复核不出来的那一类:它用了和我同一个错误模型。(同族旧账:0.89 那单「另一条腿用和我同一个错误模型复核我的判据」。) |
  | 6 | **submimo**:f2 若有人删掉 `_talk_utf8()` 但留下环境变量,仍会绿 | **属实,接受为边界,不改**。两道保险的设计就是"任一道都兜得住",所以单点删除不产生真失败;subglm 实测了"新 provision + 盘上留旧合并脚本"这一路,确认第二道单独兜得住。 |
  | 7 | **submimo**:`_talk_utf8` docstring 补一句"不影响退出码" | **不改**。docstring 里"输出通道是给人看的,**它有权难看,没权杀进程**"说的就是这件事,再加一句是重复。 |
  | 8 | **submimo**:`_talk_utf8` 两份逐字重复 | **不改**,理由同它自己给的、也同我自审 F-D 的结论:两道保险的价值正在于**不同步更新时各自仍成立**,提取公共模块反而制造单点。 |
  | 9 | **我自审 F-C**:首次打开路径(英文 Windows)没测 | **两腿独立回答,且我逐处复核过**:`ds_shell_core.py:1007 child_env` 给网关和 ds-web 两个子进程都钉了 `PYTHONIOENCODING=utf-8`(:1052/:1053);外壳自己由 **pythonw** 拉起(`launcher.nsi:39`),`sys.stdout=None` 时 `print` 是**静默空操作**(我实跑验过,不是查文档)。⇒ 从"没测过"降为"机制上已覆盖",**但仍不是真机实测**,记敞账。 |
  | 10 | **我自审 F-E**:判据续行拼接靠 `endswith("\\")`,路径末尾反斜杠会误吞下一行 | **不改,记账**。当前 4 条都不触发。 |
  | 11 | **我自审 F-B / F-A** | 已分别转成 finding #2 / #1。 |

- **arbitrated verdict(主裁):PASS**

  依据:①两处修复的真因链完整、判据**先红后绿**(f1/f2 见 `da50f39`,f3 见 `520c969`),
  且 subglm **独立复现了修前的病与修后的效果**,含"盘上留着旧合并脚本"的覆盖安装路径;
  ②端到端不是本机绿说了算——0.98.0 在云 Windows 机器上真装过,版本号由**运行中的软件
  自己报**;③评审的 4 条发现:1 条已修(#3)、2 条转后续单(#1/#2)、1 条落成墓碑(#4);
  ④两腿正面冲突的那一条**没有靠投票收场,而是去量了一次**,而量出来的结论
  推翻的是**我自己**写的那句话。

  **PASS 不等于这条链没洞了** —— 见下面的敞账,其中 #1 是一条真的数据损失路径。

## Accepted deviations / 敞着的账

- **端到端未验(已还)**:原文是「本单的修复还没进任何发布版」——
  0.98.0 发出去之后云机器真装了一遍,见下面那一节。**这条已结清。**

🔴 **下面这几笔仍然敞着,PASS 不覆盖它们:**

1. **静默安装装进非空目录无拦截,卸载会删掉业主原有的文件** —— **实测**,
   见 Review 第一条。**存量**口子,业主双击安装不受影响。
   已开单 `opendesign-silent-install-dir-guard`,**未开工**。
2. **`.nsi` 语法/静态闸没接进总跑** —— 改坏它可以带绿通过 `run-all`。
   已开单 `opendesign-nsi-gate-in-run-all`,**未开工**。
3. **`test_installer_slim.py:216` 那条死断言仍红**,归 `opendesign-installer-slim`
   (那一单至今零 run-all 收据)。
4. **首次打开路径(英文 Windows)仍不是实测**:机制上已覆盖(`child_env` 钉编码 +
   pythonw 下 print 是空操作,两处我都亲自核过),但没有一台英文 Windows 真开过它。
5. **subkimi 这条腿等于不存在**:`provider managed:kimi-code has no credential configured`。
   要么重新授权,要么把它从健康池里摘掉——**现在它每轮都占一个名额然后失败**。
6. **判据脆点**:`test_installer_silent.py` 的续行拼接靠 `endswith("\\")`,
   NSIS 正文末尾的反斜杠会误吞下一行。当前 4 条都不触发。
7. **本轮反锚定是打折的**(verify.md 派发前已在树上),已在 Review 里记账。

## 端到端:云机器装 0.98.0(2026-08-25,run 32806271389)

**上面那条"端到端未验"已经补上了。** 发布 0.98.0 之后让云 Windows 机器真装一遍:

| 相 | 0.97(修之前) | **0.98(修之后)** |
|---|---|---|
| 静默安装 | **3 分钟不退出(卡在弹框上)** | **退出码 0,46s** |
| 配置初始化 | **rc=2** | **rc=0,「配置就绪」** |
| /api/health | **3 分钟不通** | **通,`version=0.98.0`** |
| 外壳.log | 「还没装好:找不到配置文件」 | 「窗口打开 … 样式贴回」,零报错 |

**版本号是运行中的软件自己报的**,不是我说的(本机规矩:盘上和运行时对不上 = BLOCK)。

### 白屏那一惊:是我截早了,不是 0.93 那个病

第一趟(run 32806024548)截到的是**整块白**(颜色 1 种 / 近白 100%),
和 0.93「打开全是白的」同一个形状。**当时两种可能分不开(还在加载 vs 真的白),
所以一个字都没往下写**,改成隔一段拍一张:

```
启动后  19s: 颜色 1 种  / 近白 100%     ← 我第一趟截的就是这个时刻
启动后  39s: 颜色 57 种 / 近白 35.9%    ← 界面出来了
启动后  69s: 颜色 70 种 / 近白 35.9%
启动后  99s: 颜色 70 种 / 近白 35.9%
启动后 159s: 颜色 70 种 / 近白 35.9%    ← 之后完全稳定
```

**亲眼看图确认**(`evidence/20260825-云机器-0.98-界面-159s.png`):左栏(新对话/搜索/
待办事项/技能/项目)、正文、以及**首次填 key 的弹窗**全在 —— 那正是全新机器上该有的样子。

⇒ **这台冷启的云虚机上,界面要 20~40 秒才画出来。** 判读规则是**看结果之前就写死的**
(一路白到底 = 真病;中途有东西 = 我截早了),所以这个结论不是事后往有利方向解释出来的。

### 顺带记一笔,不下结论

那张图上有一条提示:「连接不上 gateway,可能没在跑,还在后台继续重试」。
全新机器上没有 key、gateway 起不来,**大概率是正常的**,但我**没验证过**,
所以只记观察,不写成结论。
