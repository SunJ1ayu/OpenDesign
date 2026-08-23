# Verify: opendesign-native-frame

- Date: 2026-08-23

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

## Mechanical checks

- [x] tests pass(python 全量 1304 项,venv 解释器)
- [x] 红检:14 条变异,咬住 14、漏网 0
- [x] no secrets / unsafe ops(本单只动 bin/ds_shell.py 与 tests/)
- [ ] **真机** —— 只有业主答得了,见 `真机清单-方案B.md`

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
