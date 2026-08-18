# Verify: opendesign-tmpdir-leak

- Date: 2026-08-17 起,2026-08-18 收口(中间断过一次线)
- Verdict: **PASS**

## Mechanical checks

- [x] build passes(dist 新鲜度段绿)
- [x] tests pass(见最后一行收据)
- [x] no secrets / unsafe ops(产品代码 `bin/`、`web/` 一字未动)

**机器打印的**(不是我的转述,逐字节粘自 runlog):

### ① 闸的红检 + 对照组(commit ① 时,只有闸、没有修复)

```
runlog: redcheck-A-clean-must-pass rc=0 commit=5d8c991 dirty=yes at=2026-08-17T15:43:40Z file=tracks/opendesign-tmpdir-leak/evidence/20260817T154340Z-01-redcheck-A-clean-must-pass.txt
runlog: redcheck-B-leaky-must-fail rc=9 commit=5d8c991 dirty=yes at=2026-08-17T15:43:48Z file=tracks/opendesign-tmpdir-leak/evidence/20260817T154348Z-01-redcheck-B-leaky-must-fail.txt
runlog: gate-selftest rc=0 commit=5d8c991 dirty=yes at=2026-08-17T15:44:33Z file=tracks/opendesign-tmpdir-leak/evidence/20260817T154433Z-01-gate-selftest.txt
runlog: runall-final rc=1 commit=3228525 dirty=yes at=2026-08-17T15:53:28Z file=tracks/opendesign-tmpdir-leak/evidence/20260817T155328Z-01-runall-final.txt
```

A 是**对照组**:干净判据必须绿。只跑 B(红)不算红检 —— 一道见谁都红的闸,
和一道永远绿的闸一样没用。`runall-final` 那一行是 commit ① 时总跑真的是红的。

### ② 修复前的基准数字(事后判"有没有把判据改坏"的唯一依据)

- node 单测:376 用例 / 0 跳过 / 0 todo
- python 全量:1277 用例 / 0 跳过,一次跑漏 **945** 个临时目录
- e2e 总跑(不含 gateway):36 PASS / 0 FAIL / 2 SKIP,漏 4 个

### ③ 断线之后补的三道防线,各自的红检

```
runlog: gate-selftest-v2 rc=0 commit=3228525 dirty=yes at=2026-08-18T01:11:51Z file=tracks/opendesign-tmpdir-leak/evidence/20260818T011151Z-01-gate-selftest-v2.txt
runlog: redcheck-C-probe-retention rc=0 commit=3228525 dirty=yes at=2026-08-18T01:13:53Z file=tracks/opendesign-tmpdir-leak/evidence/20260818T011353Z-01-redcheck-C-probe-retention.txt
runlog: redcheck-D-allowlist-by-content rc=0 commit=1309b7e dirty=yes at=2026-08-18T01:35:24Z file=tracks/opendesign-tmpdir-leak/evidence/20260818T013524Z-01-redcheck-D-allowlist-by-content.txt
runlog: gate-of-gate-selftest rc=0 commit=d27a5c0 dirty=yes at=2026-08-18T01:47:52Z file=tracks/opendesign-tmpdir-leak/evidence/20260818T014752Z-01-gate-of-gate-selftest.txt
runlog: redcheck-E-gate-of-gate rc=0 commit=d27a5c0 dirty=yes at=2026-08-18T01:48:14Z file=tracks/opendesign-tmpdir-leak/evidence/20260818T014814Z-01-redcheck-E-gate-of-gate.txt
runlog: redcheck-F-gate-blindness rc=0 commit=04f97f2 dirty=yes at=2026-08-18T01:52:59Z file=tracks/opendesign-tmpdir-leak/evidence/20260818T015259Z-01-redcheck-F-gate-blindness.txt
```

每一份都带对照组,变异各咬各的、互不误报。**redcheck-F 是这一单最响的一份**:
把闸退回 `04f97f2`,⑫⑬ 两条实得 **rc=0(报绿)** —— 也就是说在"数不出台面"和
"台面没建起来"这两种情形下,旧闸会一路放行,而那正是盘要满时最可能发生的两种。

**两份不算数的收据,留着不删**(它们记录的是量具坏了,不是被测物的结论):

```
runlog: redcheck-D-allowlist-by-content rc=1 commit=1309b7e dirty=yes at=2026-08-18T01:34:55Z file=tracks/opendesign-tmpdir-leak/evidence/20260818T013455Z-01-redcheck-D-allowlist-by-content.txt
```

- 上面这一份 rc=1:**我那份红检脚本自己写了个语法错**(`def报(...)` 少个空格),
  一行被测代码都没跑到。它不算"红检红了",它算"量具还没上工就掉了"。
  重写后的那一份(rc=0,01:35:24)才是这条判据的红检结论。
- `20260818T014843Z-…-runall-final-0818-v2`(半截):我用 `pkill -f` 收上一轮时,
  模式把**我自己这条命令**也匹配进去了(仓库 README 写着的"自杀坑",我照着踩了一遍)。
  这一遍作废,重跑成 v3。

### ④ 中途两遍红的总跑(都不是修复本身的问题,但都算数)

```
runlog: runall-0818-with-gateway rc=1 commit=1309b7e dirty=yes at=2026-08-18T01:20:59Z file=tracks/opendesign-tmpdir-leak/evidence/20260818T012059Z-01-runall-0818-with-gateway.txt
runlog: runall-final-0818 rc=1 commit=d27a5c0 dirty=no at=2026-08-18T01:36:04Z file=tracks/opendesign-tmpdir-leak/evidence/20260818T013604Z-01-runall-final-0818.txt
```

第一遍红在 3 条"死断言"上 —— 那三条**本来就在放行清单里**、内容一个字没变,
是我加的 `import _tmpreg` 让行号漂了 +2,而清单按行号认(第四次漂)。
第二遍红在闸自己的判据上:我改了放行格式却没跑它的判据,它当场咬住我。
两次都不是"修复把判据改坏了",但两次都值得留在这儿。

### ⑤ 最终收据(最后一次编辑之后的那一遍,工作树干净)

```
runlog: runall-final-0818-v3 rc=0 commit=bdbf485 dirty=no at=2026-08-18T01:54:31Z file=tracks/opendesign-tmpdir-leak/evidence/20260818T015431Z-01-runall-final-0818-v3.txt
```

```
════ 总跑汇总 ════
  PASS  泄漏闸自测(判据的判据)   13 条全过
  PASS  node 单测(tests/*.mjs)           376 通过 / 0 跳过 / 0 todo
  PASS  python 全量 + 死断言闸            1280 跑过 / 0 跳过
  PASS  MCP 契约闸                        三条闸全绿
  PASS  dist 新鲜度                       与源码同步
  PASS  e2e 总跑(含 gateway)            38 PASS / 0 FAIL / 0 SKIP
6 段全跑,全绿。
跑后 /tmp 顶层条目数: 42205  ⇒ 净增 0
```

**与基准逐条对账(判"有没有把判据改坏"的唯一依据):**

| | 修改前 | 最终 | 说明 |
|---|---|---|---|
| node | 376 / 0 跳过 / 0 todo | 376 / 0 / 0 | 逐字一致 |
| python 用例 | 1277 / 0 跳过 | 1280 / 0 跳过 | **+3 = 我给死断言闸新加的三条判据**,别处一条没少 |
| e2e | 36 PASS / 0 FAIL / 2 SKIP | 38 PASS / 0 FAIL / **0 SKIP** | 两条要活 gateway 的这次真跑了 |
| 死断言 | (未记) | 0(放行 5 条,全部唯一命中) | |
| `--allow` | 2 条(全局 1 + e2e 段 1) | 2 条,理由都在调用处 | |
| **一轮总跑的 `/tmp` 净增** | **约 +17,000** | **0** | 业主问的是这一格 |

### ⑥ 盘面事实(业主的问题不是"判据绿了",是"盘还会不会满")

- 排查当天:50G 盘用到 45G(94%),`/tmp` 205,666 个条目 / 6.5G。
- 现在:36G / 50G(77%),最后一轮总跑 `/tmp` **净增 0**。
- 跑前跑后核过 `~/.nanobot/config.json` 的 sha256(`8ab64eae…e823f4`),零字节改动 ——
  08-15 栽过"判据自己会改我的机器",从此每轮对一次。

## Review

- lane: full
  > 不是因为撞了那条硬规矩(新写口/权限/auth/钱/数据一致性 —— 这单一条没碰,
  > 产品代码 `bin/`、`web/` 一字未动)。选 full 是因为**改动面 100% 在判卷层**、
  > 铺开 24 个文件,而这一类最危险的坏法是「判据还是绿的,只是测得更少了」——
  > 那正是本机最忌讳的"改考卷让自己及格",哪怕不是故意的。
  > 事后看这个 lane 选对了:三条腿里有两条各自独立指到同一处**闸会无声瞎掉**,
  > 而那一处我自审两遍都没看见。
- 派给: 主 agent 直接干
  > **不是"排除了 codex 就跳到我自己干"**(07-31 栽过这个)。逐档答:
  > · codex / submimo fix / Sonnet 腿 —— 派活规矩里「oracle / 判据文件对执行腿
  >   off-limits」在这单**直接失效**:要改的就是判据文件本身,闸①「它有没有动判卷」
  >   问不出任何东西,因为它碰的每个文件都是判卷。
  > · Sonnet 腿技术上仍可行(拿"用例数/断言数不许变"当收货闸能罩住),没派的实际理由是:
  >   47 处的改法我已经**逐处**知道了(前缀→调用点的映射是实测出来的,不是猜的),
  >   写任务书 + 走三道闸的开销大于活本身。
- 规格自查(读任何 panel 输出之前答的):
  > **规格错了会错成什么样**:我把业主的「磁盘满了」翻译成「修判据的临时目录泄漏」。
  > 这一步转译要是错的(大头其实不是判据),后面全白做。
  > 怎么发现的:没靠读代码猜 —— 做了实测普查(evidence/…census.txt),用 `/tmp` 各前缀的
  > **实际堆积数**对账,39 个前缀在漏、60 个干净、**中间地带 0 个**,断崖干净到没有解释空间。
  >
  > **规格没覆盖到的那一面**:闸绿只证明"判据自己跑完收干净了",不等于业主要的"盘不会再满"。
  > 所以收口额外给一条**盘面事实**:跑完一整轮总跑后 `/tmp` 的净增量。
- 腿的花名册:
  ```
  panel-review: done. submimo rc=0  subdeepseek rc=0  subglm=off(PANEL_GLM_LEG=agent 开回来)  subkimi rc=0
  ```
  三腿有结论(智谱那腿在本机是关着的,不是崩了)。任务书 `/root/aiwork/tasks/tmpdir-leak.md`,
  自审 `/root/aiwork/tasks/tmpdir-leak-my-review.md`(先写完才派发)。
  **反锚定有一处瑕疵**:本 track 的 `verify.md` 在 commit ① 就进了仓,里面有我的规格自查;
  任务书里明写了"不要读它",但挡不住腿真去读。下次:先派发,后写 verify.md。

- findings(我的 → 腿的,逐条对账):

  **我自审就有的(腿看不看得见都成立)**
  - F1 闸新加的"红了留现场"没有任何判据在问 → 已补 ⑨⑩⑪ + 变异红检。**成立,已修。**
  - F2 闸自己的判据是孤儿脚本,总跑从没叫过 → 已接成第 ⓪ 段。**成立,已修。**
  - F3 事前的前缀普查有结构性盲区(裸 `mkdtemp()` 没前缀,归不了类)→ 那处漏是**闸自己抓的**。
    **成立,已修。** 三条腿没有一条独立提到这一条。
  - F4 闸只看得见 TMPDIR 里的东西 → 认账不修。**两腿独立核过盲区当前是空的**
    (subkimi 逐项 grep:无 `mkdtemp(dir=)`、无 `/var/tmp`、`expanduser("~")` 只在变异脚本的
    载荷串里),结论与我一致。
  - F5 SIGKILL 时 `atexit` 不跑 ⇒ 那一轮留残渣 → 已写进 `_tmpreg.py` 文件头。三腿均认可有界。
  - F6 死断言放行清单按行号认、被我的 import 顶漂 → 已改成按内容认。**是我自己的总跑先抓到的**,
    subkimi 独立以 BLOCK 指到同一处(它读的是修之前那棵树)。

  **腿标了、我漏了(panel 的主要价值就在这里)**
  - ✅ **接受(subdeepseek + subkimi 各自独立命中)闸会无声地瞎掉。**
    已核 `tests/tmpdir-leak-gate.sh:53`(mktemp 失败无检查)与 `:78`(`find -printf`/`mapfile`
    是 GNU+bash≥4 扩展、stderr 被吞),两条都通向"数出 0 个 ⇒ 报干净"。
    **红检实测旧闸在这两种情形下 rc=0**(收据 redcheck-F)。已修成开工先放哨兵、数不出就拒跑。
    > 这条最该记的不是 bug 本身,是它的形状:**这道闸最安静的时候,正是盘要满的时候**。
  - ✅ 接受(subdeepseek + subkimi)放行清单"一条盖住多行"只告警不进退出码,
    而总跑汇总只抠"N 条死断言" ⇒ 那行告警在总跑里不可见 = 等于静默放行。已改成拦。
  - ✅ 接受(subdeepseek D3 + subkimi F4)只有跳过、没有红时,总跑和 e2e 总跑都留着日志目录 ——
    默认跑法必有 2 条 gateway e2e 跳过 ⇒ **每跑一次往 /tmp 留一个**。
    这正是前两份收据里那个"净增 1"。已改成:红了留(唯一的排查线索),只跳过就收。
  - ✅ 接受(subdeepseek)死断言报告把源码截断到 120 字符却不留记号 ⇒ 有人从报告里复制一行
    进放行清单会对不上 ⇒ 误红 ⇒ 他会去改那条无辜的断言。已加截断记号。
  - ✅ 接受(subkimi F5)`tests/run-all.sh` 里有两个"第 ④ 段"。装饰性,已改成 ④/⑤。

  **腿标了但我驳回**
  - ❌ submimo「test 方法体内的调用可考虑改用 `self.addCleanup` 获得更精确的清理时机」。
    已核 `test_ds_web.py:217` 等处:那几处拿到的目录会被**模块级夹具**继续引用,
    改成按用例收正是 `_tmpreg.py` 文件头那条"缩短存活期 = 改隔离语义"要避免的动作。
    非阻塞建议,不采纳。
  - ❌ subkimi F1(BLOCK 的那条)判据与新格式对不上 —— **成立,但在它读的那棵树上**;
    我自己的总跑先一步抓到并已在 `04f97f2` 修掉(报告尾部也自带了"HEAD 移动过"的提示)。
    不作为未决发现。

  **我标了、腿没标 —— 依然成立**
  - F3(裸 `mkdtemp()` 那处)三腿都没独立发现;它证明的是**行为闸看得见静态扫描看不见的东西**,
    这条结论不因为没人附议而变弱。

- arbitrated verdict (主裁): **PASS**
  > 三腿两 PASS 一 BLOCK,而那条 BLOCK 指的是我自己的总跑已经先抓到并修掉的东西
  > (它读的是修之前那棵树)。**但全票与否不改变标准**:这一单真正的收获是
  > 两腿各自独立命中的"闸会无声瞎掉",那一处我自审两遍都没看见,而红检实测旧闸
  > 在两种情形下都 **rc=0**。所有接受的发现都已落地并各自带红检,最终总跑
  > 6 段全绿 / 0 跳过 / 盘面净增 0。产品代码一字未动,业主侧无行为变化。

## Accepted deviations

- **两条要活 gateway 的 e2e 是在一个"MCP 工具一个都没连上"的 gateway 上跑的。**
  本机 `~/.nanobot/config.json` 现在是 **Windows 形状**的(`${USERPROFILE}/.venvs/…/Scripts/python.exe`),
  Linux 上那三个 MCP server 全部 FileNotFoundError。gateway 本体起得来、websocket 通,
  两条 e2e 断的是协议与 UI 事实(不断言 LLM 回复内容),所以结论有效。
  **但这条环境损坏本身是另一笔账**(配置 mtime 停在 08-15 13:24,疑似 08-15 那类
  "判据改了我的机器"),本单不修它、也不为它改判据。跑前跑后核过
  `~/.nanobot/config.json` 的 sha256:`8ab64eae…e823f4`,零字节改动。
- **`--allow` 现在是两条**:全局 `node-compile-`(Node 自己的编译缓存,固定名复用、不累积)
  + e2e 那一段的 `ds-e2e-log-`(红了故意留现场)。两条都在调用处写了理由。
  tasks.md 里写的"清单仍只有 1 条"是当时的说法,以这里为准。

## 归档之后的补账(2026-08-18,业主一句「都是第一性原理吗 没有埋下屎山吧」逼出来的)

业主问完之后我把这一单重新过了一遍,查出**三件我自己漏掉的**,都在这儿:

**补1. 一条 `--allow` 的理由过期了。** `tests/run-all.sh` 里写着 e2e 的日志目录
"在**红或有跳过**时故意留着给人看" —— 而这一单我刚把 e2e 改成**只跳过就收掉**。
改动和描述它的注释没同步 ⇒ 那句话变成假的。已改正,并写清这条放行现在**只为红那条路存在**。

**补2. 我改的"只跳过就收拾"那条路,最终那份绿收据根本没走过。**
最终收据是 `--with-gateway` 跑的、**0 跳过** ⇒ 走的是全绿那条分支。
而"只有跳过、没有红"正是业主平时最常走的默认路径。补跑两遍:

```
runlog: runall-default-skip-path rc=1 commit=367143e dirty=yes at=2026-08-18T02:16:54Z file=tracks/archive/opendesign-tmpdir-leak/evidence/20260818T021654Z-01-runall-default-skip-path.txt
runlog: runall-skiponly-path rc=3 commit=367143e dirty=yes at=2026-08-18T02:29:36Z file=tracks/archive/opendesign-tmpdir-leak/evidence/20260818T022936Z-01-runall-skiponly-path.txt
```

第一遍(网关没起)红在 e2e 两条上 ⇒ 走的是**红**那条路,没验到目标(见补3)。
第二遍(网关活着、但不带 `--with-gateway`)拿到了要的那条:
**没有红的 / 2 条跳过 / rc=3 / `/tmp` 净增 0** —— 日志目录在只跳过时确实被收掉了。

**补3.(不是这一单的问题,但是这一单挖出来的)两条 e2e 悄悄依赖"机器上有没有活网关"。**
`frontend_p2_polish.e2e.mjs` 与 `todo_assistant.e2e.mjs` 都在等
`[data-ui="connect-card"]`(未连接提示卡)出现;网关没起时这张卡不出现 ⇒ 两条超时红,
**而红的原因和它们要测的东西毫无关系**。它们**不在 `NEEDS_GATEWAY` 名单里**,
所以默认跑法照跑不误 ⇒ 谁的机器上没开网关,谁就见两条假红。

- **不是本单改坏的,已证**:把树退回 base `5d8c991`(独立 worktree)、同样条件跑,
  两条**照样红,报错一字不差**。
- 这也解释了 08-17 那两遍红:那会儿网关刚死(`DS_LLM_KEY` 起不来),我一度以为是修复的锅。
- 反向印证:网关活着时 e2e 是 36 PASS / 0 FAIL / 2 SKIP,与本单记录的**修改前基准逐字一致**。
- **不在本单修**(它是判卷层的另一处独立缺陷,该单独走一单)。修法方向不是把它们塞进
  `NEEDS_GATEWAY`(那等于默认少测两条),而是让它们别再依赖机器上碰巧有什么 ——
  同仓已有先例:`chat_image.e2e.mjs` 用 `addInitScript` 把 WebSocket 和 bootstrap 都 stub 掉。
