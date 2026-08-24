# Verify: opendesign-native-frame

- Date: 2026-08-23

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

## Mechanical checks

- [x] tests pass(python 全量 1304 项,venv 解释器)
- [x] 红检:14 条变异,咬住 14、漏网 0
- [x] no secrets / unsafe ops(本单只动 bin/ds_shell.py 与 tests/)
- [ ] **真机** —— 只有业主答得了,见 `真机清单-方案B.md`

## 收口之后发现的(2026-08-24,断线重连后接手时查出)

**🔴 真机清单 A1 认的那行日志,字符串抄错了 —— 会当场作废整趟验收。**

- 清单原文:`[窗口] 已接管非客户区(WM_NCCALCSIZE)`
- 代码实际打的(`bin/ds_shell.py:527`):`[窗口] 非客户区接管已生效(收到第一条 WM_NCCALCSIZE)`

A1 是硬闸(「没有 = 停,别往下走」)⇒ 业主会在**第一条**就搜不到,22 条一条都走不成,
白装一趟。**失败形态与 0.92 同族**:清单认的那个信号给出假红。

根因是老病:收 panel F1(把日志从挂载处挪到"第一次真收到消息"处)时**顺手改了措辞**,
`ds_shell.py:522` 甚至特地留了注释「真机清单 A1 认的就是这一行,别把它挪回挂载处」,
**却没回头把清单里的字符串对一遍** —— 同一个事实存在两处,只更新了其中一处。
判据 n12 是结构性的(AST 查调用链),**结构上问不出字面量抄没抄对**。

已修(只动清单,实现不动),并加一句「搜『非客户区接管』六个字就够」降低抄错敏感度。
机械核对:清单里所有 `[窗口]` 开头的行必须在 `bin/ds_shell.py` 里逐字存在 —— 现 1/1 OK。

**顺带量出一笔仍敞着的账(未修,够一个独立 track):**

`tests/e2e/run-all.sh` 现为 **35 PASS / 1 FAIL / 2 SKIP,rc=1**
(收据:`evidence/20260824T003109Z-01-e2e-runall.txt`)。红的是 `llm_key.e2e.mjs`,
它红在自己那道新鲜度闸上(「web/dist 比 web/src 旧」)。

> ⚠️ **我第一版把它判成「假红」,那是错的 —— 已推翻。**
> 当时给的第二条理由是「`git log --since=2026-08-18 -- web/src` 为空 ⇒ src 内容自
> 08-17 起没变过」。这句**问错了区间**:该比的不是"某个日期之后",而是
> **dist 那次提交与 src 那次提交谁在后**。业主质疑「确定是误报吗」之后重查:

**闸报得对,不是误报。**(证据:`evidence/20260824T-02-dist-freshness-probe.txt`)

- `d704df8`(08-17 **22:10**)改 `WindowChrome.tsx` 时**一并重建并提交了 dist** ✓
- `c82dcbc`(08-17 **22:24**)改了 `web/src/app.css`,**之后再没有过 dist 的提交**
- `git merge-base --is-ancestor d704df8 c82dcbc` 成立 ⇒ **src 确实在 dist 之后改过**

**但产品面零影响**,这一层是实测不是推理:

- 那次 app.css 的改动是 **+5 行纯 CSS 注释**(说明右上角 6×6 把手为何点不到 ——
  它整块落在三个按钮底下),**零样式规则**,而 build 会剥注释;
- 重新 `npx vite build --outDir <仓外临时目录>`,产物与 `web/dist` **逐字节相同**
  (`index-DrDJWOTn.css` / `index-nULi_wUm.js` / `index.html` 三个全 IDENTICAL;
  vite 文件名即内容哈希,重建后哈希未变是独立佐证);
- 安装包内 `index-DrDJWOTn.css` 与仓库 dist **逐字节相同**
  ⇒ **0.93.0 的包里装的就是当前源码的正确产物,业主可以放心装。**

**这次由绿转红的直接触发,仍然是红检毁 mtime:**
`tests/mutation-window-chrome.sh:36` 恢复原状用 `cp` —— 还原内容却把 mtime 设成当前时间。
08-23 12:19 跑红检那下把两个前端文件顶新(在那之前 dist=08-18 比 src 新,闸是绿的)。
**8 个 `tests/mutation-*.sh` 全是不带 `-p` 的 cp。**

⇒ 于是这里其实是**两件独立的事**,都成立:

1. **红检没恢复干净**(承诺"恢复原状"却漏了 mtime)—— 8 个脚本同病。修法看着是
   `cp` → `cp -p`,但与既有教训「红检会被字节码缓存骗」**方向相反**(那条讲 mtime
   **没变**导致复用旧 .pyc)⇒ **必须实测、不许推理**。
2. **闸问的问题与它想防的事有落差**:它比**时间戳**,而它真正要答的是
   「dist 是不是当前 src 的产物」。所以像这次"只改了注释"的情形它会照样报警,
   而时间戳还会被切分支/复制/解压等一堆无关动作刷新。根治要比**内容**
   (build 时把 src 的内容哈希落进 dist,闸比哈希),那要动打包流程。

两件都不在本单顺手做,单独起 track。

> 本单收口时没跑 e2e 总跑(verify 里也没有 e2e 收据)。这一单不碰前端,取舍成立;
> 但也正因为没跑,这个假红从 08-23 12:19 起就在,直到今天接手才被撞上。

**机器打印的**(不是我的转述):

```
runlog: python-regression-venv rc=0 commit=255324a dirty=no final=yes at=2026-08-23T16:37:15Z file=tracks/opendesign-native-frame/evidence/20260823T163715Z-01-python-regression-venv.txt
runlog: redcheck-mutation rc=0 commit=255324a dirty=yes final=yes at=2026-08-23T16:44:28Z file=tracks/opendesign-native-frame/evidence/20260823T164428Z-01-redcheck-mutation.txt
```

**跑红的那几遍,一份都不藏**(规矩 5b):

```
runlog: python-regression-venv rc=1 commit=771aceb dirty=yes final=yes at=2026-08-23T16:21:11Z file=tracks/opendesign-native-frame/evidence/20260823T162111Z-01-python-regression-venv.txt
runlog: python-regression-venv rc=65 commit=f9e787b dirty=yes final=yes at=2026-08-23T16:28:59Z file=tracks/opendesign-native-frame/evidence/20260823T162859Z-01-python-regression-venv.txt
```

- `rc=1` 那遍:**死断言闸红的,不是测试红的**。它抓到 n10/n13 里两条
  `self.fail(...)` 在正常路径上**从来不会被执行** —— 从没跑过的断言等于没写。
  已改成 `assertTrue` / 先收集再逐条断言。
- `rc=65` 那遍:测试本身 `command-rc: 0`(1304 项 OK),65 是 runlog 自己给的,
  因为 `source-stable: no`。真因是**后台 panel 任务在收尾时往 track 目录写了
  observation 文件**,正好落在这一遍跑的过程中。不是代码变了。工件提交后重跑即 rc=0。
- 更早两份(154134Z / 154847Z)跑在 `58b397e`,是**收 panel 发现之前**的代码,已过期不作数。

## Review

### 规格自查(在读任何 panel 输出之前答的)

**上一单就是死在规格上**:0.92 的实现完全合乎它自己的规格(贴三个位),
七条判据全绿,而业主按下去照样没有动画 —— **题问错了**。

这一单的规格如果还是错的,最可能错在哪:
1. **"加回 CAPTION+THICKFRAME 就会有动画"这个因果**。它有三条独立证据
   (Electron 两个时代的代码、WinFormedge、业主机器 5 个窗口的对照),
   比 0.92 那次(一条 2014 年的 issue 评论)强得多 —— **但仍然是相关,不是我亲手验的因果**。
   真正的证明只有一个:业主装上之后按下去有动画。
2. **P1 探针验的不是同一个窗口**。它用的是干净的 `Form`,而真实窗口已被
   WinForms subclass 过一层。挂第二层理论上一样,**没验**。
   ⇒ 这一条现在有闸了:`_wndproc` 收到第一条消息才打"接管已生效",
   真机清单 A1 认那一行(panel subdeepseek F1 逼出来的)。
3. 静态判据全是 AST 读源码。它们答得了"手段有没有写错",
   **答不了"窗口长什么样、有没有动画、卡不卡"**。

### 腿的花名册

```
# ⚠️ 评审期间 HEAD 从 78de449 移到 f9e787b —— 各腿未必评的同一棵树。
```

- subglm:agent 腿 opencode 跑满 900s 超时 → 回落 chat 腿 → 连撞 HTTP 503
  (`Upstream request failed: Endpoint is unavailable`),两段都没产出。
- subkimi:`provider managed:kimi-code has no credential configured`,长期问题。
- 成功两条、两个不同模型家族(mimo / deepseek);impact-risk=standard 要 1 条。

### findings(逐条对着代码验过,不是转述)

**我自己先查出并已修的(落盘于派发之前):**

- **F-A 真 bug**:`ensure_native_styles` 还指着改名前的 `_setup_native_frame`,
  窗口一 `shown` 就 AttributeError,且那句在 `_on_ui` 的 try **外面**。
  **10 条判据 + 1299 项回归全都没咬住它**(这层 Linux 跑不到)。已补 n9 + 变异 F10。
- **F-B** `_work_area` 成死代码,删。
- **F-C** `_wndproc` 末行原在 try 外。
- **F-E** `_install_wndproc` 幂等只看 hook 非空 ⇒ 句柄重建后永不重挂。已补 n10 + F11。

**submimo(3 条):**

- P1 [接受,已修] 窗口销毁前从不解挂 —— 回调随对象走而消息还在发。
  我自审时写了"从来没解挂过"却**没当成要修的**,它标成最高危是对的。已补 n11 + F12。
- P2 [**驳回**] 称 `style & needed == needed` 优先级错。**实测证伪**:Python 里
  `&` 优先级**高于** `==`(与 C 相反),`ast.parse` 出来就是 `Compare`;
  且红检 F2/F3(缺一个位必须红)能咬住,本身就反证这行是对的。
- P3 [不是 bug,顺手改] 同一个句柄有两条路各算一次,合并成一次。

**subdeepseek(7 条,BLOCK):**

- F1 [HIGH,接受,已修] "已接管"打在**挂载处**,而挂载成功证明不了回调被叫到。
  **design.md D2b 白纸黑字要求打在第一次收到消息时 —— 我写进了规格没写进实现。**
  这是本单最有价值的一条:真机清单 A1 认的就是这行,不修的话 A1 会给出假绿,
  而失败形态和 0.92 一模一样(日志说已接管、产品没有动画)。已改 + 补 n12/F13。
- F2 [MED-HIGH,接受,已修] `wParam` 为假那条漏回原 proc;那时 lParam 是裸 RECT,
  `DefWindowProc` 会按当前真实样式(现含 WS_CAPTION)扣掉标题栏 ⇒ 画出来一帧。
  已改成两种 wParam 都 `return 0`,补 n13/F14。
- F3 [MED,接受,已修] 转发失败静默返回 0。**我原注释写"返回 0 是同一个结果"是错的**:
  对 `WM_NCHITTEST` 意味着整窗口不可拖不可缩。已加 `_warn_once` 留痕。
- F4 [MED,接受为证据边界] 核心前提(动画会播)未验。属实,见上面规格自查第 1 条。
  F1 的修复把"接管到底生效没有"从假设变成了日志里可查的事实,是能做的最大缓解。
- F6 [LOW,接受,已修] NC 分支异常日志会被高频消息刷屏 ⇒ 同走 `_warn_once`。
- F5 / F7 见下方 Accepted deviations。

### arbitrated verdict(主裁)

**代码面 PASS。产品面不给结论。**

代码面的依据:1304 项回归 rc=0、14 条变异咬住 14 漏网 0、两个模型家族的评审发现
全部落地或有据驳回、我自己的四条自审发现全部已修。

产品面不给结论的依据**不是保守,是证据边界**:这一层 Linux 上一行都跑不到,
本单全部机器证据回答的都是"手段有没有写错"。**"业主按下去有没有动画"、
"窗口边缘会不会多一条线"、"拖起来卡不卡" —— 一条判据都答不了。**
0.92 就是在这儿把"手段对了"当成了"问题解决了",这次不重犯。

⚠️ **这一版的风险高于 0.92**:0.92 只贴不参与绘制的位、承诺外观零变化;
这一版接管了窗口的边框计算,失败形态是**外观当场坏掉**(多一条线 / 冒出标题栏 /
内容被挤)。真机清单为此单列 C 组,并把"拖窗口卡不卡"单列 E1 ——
那是 Python 回调处理每一条窗口消息带来的、我完全没法在这边测的风险。

## Accepted deviations

- **F5(subdeepseek,LOW)** `_on_ui` 失败时 `bool(None)` 被当成 `False`,
  `toggle_maximize`/`window_state` 会回一个"未最大化"。**不修**:要改前后端契约
  (前端得会处理"不知道"这个第三态),超出本单范围;影响是前端图标短暂画错,
  下一次操作即纠正。记入 backlog。
- **F7(subdeepseek,LOW)** `_hooked_hwnd` 存的是句柄**数值**,若窗口重建后新句柄
  恰好复用旧数值,幂等判断会早退 ⇒ 永不重挂。**不修**:这是"比句柄"方案的固有盲区,
  真要堵得引入代次号或弱引用表,复杂度不划算;发生概率极低。
- **方案 B 的 C 组能力**(拖边缘分屏 / Win11 Snap Layouts)本单**顺带**获得,
  但**没有为它们写任何判据** —— 它们是 THICKFRAME 的副产品,真机清单 B5/B6 只做观察。

---

# 0.94.0 —— 真机红之后的修复轮(2026-08-24)

## 这一轮修的是什么

业主真机:0.93.0「打开全是白的什么都没有了」。修法**不是猜一个机制去补**,
而是把方案 B 整套收进默认关闭的实验开关,默认路径退回 0.92 那套真机验过能用的行为。

理由写在 tasks.md 的「真机结果」一节(证据逐条)。一句话:
**从"看得见"到"全白",唯一的功能性差量就是方案 B**;而方案 B 的代码逐行读过没有笔误,
病在它与 WebView2 的运行时交互 —— 那一层 Linux 上一行都跑不到。
0.92/0.93 连着两版都死在"把推论当结论发出去",这一版不再赌。

## Mechanical checks

- [x] tests pass(python 全量 **1321 项 rc=0**,venv 解释器,3 跳过均为
      `DS_SHELL_E2E=1 才跑` 的 nanobot 联跑,与本轮无关)
- [x] 红检(新闸 f1~f9):**咬 9 漏 0**
- [x] 红检(老闸 n1~n13):**咬 14 漏 0**(F4/F8 锚点因实现缩进 +4 失效,已修)
- [x] 成品闸:安装包 7 条 0 不合格;包内 `ds_shell.py`/`ds_web.py`/`web/dist`
      与仓库**逐字节一致**
- [x] **在打好的包里实测开关**:默认 `False` → 放标志文件 `True` → 删掉 `False`
- [ ] **真机** —— 只有业主答得了,见 `真机清单-0.94.md`

**机器打印的**(不是我的转述):

```
runlog: python-regression-venv rc=0 commit=db144e1 dirty=yes final=yes at=2026-08-24T11:45:42Z file=tracks/opendesign-native-frame/evidence/20260824T114542Z-01-python-regression-venv.txt
runlog: redcheck-frame-experiment rc=0 commit=db144e1 dirty=yes final=yes at=2026-08-24T11:45:13Z file=tracks/opendesign-native-frame/evidence/20260824T114513Z-01-redcheck-frame-experiment.txt
runlog: redcheck-native-frame rc=0 commit=db144e1 dirty=yes final=yes at=2026-08-24T11:45:26Z file=tracks/opendesign-native-frame/evidence/20260824T114526Z-01-redcheck-native-frame.txt
```

> `dirty=yes` 三份都是同一个原因:收据文件本身还没入库(未跟踪)。
> 三份的 `source-stable` 全是 `yes` —— 跑的过程中源码没变过。

**跑红的那几遍,一份都不藏**(规矩 5b):

```
runlog: python-regression-venv rc=1 commit=2d791b9 dirty=no final=yes at=2026-08-24T11:21:51Z file=tracks/opendesign-native-frame/evidence/20260824T112151Z-01-python-regression-venv.txt
runlog: redcheck-frame-experiment rc=1 commit=b0ba271 dirty=yes final=yes at=2026-08-24T11:44:11Z file=tracks/opendesign-native-frame/evidence/20260824T114411Z-01-redcheck-frame-experiment.txt
```

- `rc=1` 那遍回归:**老闸抓到我一个真 bug**。`_log_frame_diagnostics` 里
  `GetWindowRect`/`GetClientRect`/`GetClassNameW`/`EnumChildWindows` 四个都是裸调,
  没声明 argtypes/restype ⇒ 64 位上句柄被静默截成 32 位,**诊断会印出看着像真的、
  其实是错的数字**。那比没有数字更坏 —— 这个函数存在的全部理由就是给我可信的数字。
  1321 项里就这一条红。已修(`b0ba271`)。
- `rc=1` 那遍红检:**我自己那笔 argtypes 修复把 f9 弄瞎了**。补上
  `user32.EnumChildWindows.argtypes = [...]` 之后,就算把调用整个删掉,
  这个名字照样在源码里,f9 的子串匹配就绿了 ⇒ M9 漏网。
  **加一道防线顺手拆掉另一道**,这个项目的老形状。
  f9 已改成认 `ast.Call` 的被调方名字(属性赋值不算数),红检回到 9 咬 0 漏。

## Review

### 判据的洞 —— 和 0.91 同一个形状(本轮最该记的一条)

0.93 那一单**判据全绿、四审 PASS、主裁代码面 PASS**,而业主打开是一片白。
逐条核实后(tasks.md 有全文),原因不是"漏判":

- **主裁当时就写了「产品面不给结论」**,而且写明失败形态是"外观当场坏掉";
  subdeepseek F4 也标了"核心前提未验"。**它答不了,而我知道它答不了,包照发。**
- 那轮实际只有**两条腿**成功(subglm 超时+503、subkimi 无额度)。但这不是主因 ——
  **四条腿一样查不出来**:没有任何一条腿能在 Windows 上把窗口画出来。
- 同一单的 F-A 已经现过这个盲区:`ensure_native_styles` 指着改名前的函数、
  窗口一 `shown` 就崩,**10 条判据 + 1299 项回归全没咬住**,靠我肉眼看出来。
  同一个洞在同一单里现过形,我没把它的份量看够。
- 🔴 **真机清单自己也犯了同一个病**:C 组五条全在问"退化"(多一条线 / 冒标题栏 /
  内容被挤掉一点 / 圆角 / 盖任务栏),**没有一条问"界面还在不在"**;
  而 A 组硬闸让业主打开就去翻日志文件。「全白」从中间直接漏过去。

⇒ 修法不是"多加一条评审腿"(腿再多也读不了屏幕),是把最粗的问题放到最前面。
`真机清单-0.94.md` 的第一条现在是 **A0「界面出来了吗?一片白就停」**。

### 这一版的判据能保证什么、不能保证什么

- **不能**保证"页面画得出来" —— 那一层只有 Windows 答得了,和 0.93 一样。
- **能**机械保证:默认路径**一个边框计算都不碰**(f5~f7 各自有红检咬着),
  所以默认路径的行为就是 0.92 的行为,而 0.92 在业主机器上是好的。
  这是一条更弱、但**真的成立**的保证 —— 0.92/0.93 两版的错就是把
  "手段写对了"当成了"问题解决了"。

### arbitrated verdict(主裁)

**代码面 PASS。产品面照旧不给结论**,但这一版的产品风险与前两版**不是一个量级**:
默认路径不是新写的代码,是 0.92 那份**业主已经跑过一版**的实现搬回来。
真正的新代码只有开关本身和诊断日志,两者都在"关"的一侧不生效。

⚠️ 仍然敞着的:**白屏的机制至今不知道**。这一版只做了两件事 ——
让业主能用,以及让下一趟真机能带回数字。不许把"绕开了"写成"修好了"。

## 未做 / 敞着的账

- **白屏根因未定案**。要等业主走 `真机清单-0.94.md` 的 D 组(可选)带回 `[诊断]` 那几行。
- 方案 B 的 C/E/F 组(拖边缘分屏、Win11 Snap、拖动跟不跟手、全屏后接管掉不掉)
  **一条都没验过**,现在全在关着的开关后面,等根因定案再说。
- 0.93 的 `真机清单-方案B.md` 保留不删:它的 C 组问法是本轮的反面教材。
