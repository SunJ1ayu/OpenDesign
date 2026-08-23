# Design: opendesign-native-frame

- Change: opendesign-native-frame
- Status: **我的方向(第一版,commit 后再做双出/panel-explore,防锚定)**
- 规划双出:**待做** —— `design-uncertainty: high`,最大的未知是
  「pythonnet 里到底挂不挂得上 WndProc」,两个上游参考一个是 C++ 一个是 C#,
  **没有一个是 Python 的**。

## 根因(已定案,不再讨论)

见 `evidence/premise-attack-upstream-b.md`。一句话:动画归 `WS_CAPTION`/`WS_THICKFRAME`
这一族管,0.92.0 贴的 `MINIMIZEBOX|MAXIMIZEBOX|SYSMENU` 是**另一族**(系统菜单、
Win+方向键),两族都真实存在、0.92 只修了后一族。业主真机 `STYLE=0x360B0000` 逐位对上。

## 我的方向

### D1 —— 样式位:把 CAPTION + THICKFRAME 加进 needed

`_apply_native_styles_unsafe` 里的 `needed` 从三个位扩到五个:

```
WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU
```

- `WS_CAPTION`(0x00C00000)= `WS_BORDER|WS_DLGFRAME`,**照 Electron 打底那一份**。
- `WS_SYSMENU` 上游没加,我们**保留** —— 0.92 真机验过它带来的右键任务栏菜单,别丢。
- 仍然是**或上去**不是赋值(Electron 是建窗时赋值,我们是运行中改,情形不同)。
- ⚠️ **D1 单独上线 = 窗口会真的长出一条标题栏。** D1 和 D2 必须同一个版本发布,
  中间态不许出现在给业主的包里。

### D2 —— 接管 `WM_NCCALCSIZE`(本单的核心,也是最大未知)

pywebview 不暴露 WndProc ⇒ 用 pythonnet 挂 `System.Windows.Forms.NativeWindow`
子类化到 `form.Handle`:

- `wParam == TRUE` 时改 `NCCALCSIZE_PARAMS.rgrc[0]`:**不给标题栏留高度**,
  于是客户区铺满整个窗口 ⇒ 外观回到今天的样子,但样式位还在。
- 最大化时**必须修正**:带 THICKFRAME 的窗口最大化会向外溢出一圈边框宽度
  (`SM_CXSIZEFRAME + SM_CXPADDEDBORDER`),不修就会盖住任务栏、内容被切。
  WinFormedge 那份的 `AdjustMaximizedClientRect` 就是干这个的。
- ⚠️ **未知 #1**:`protected override void WndProc(ref Message m)` 带 `ref`,
  pythonnet 3.x 覆写虚方法的行为要**先写一个最小探针验证**,不许假设能成。
  探针失败的话整个 D2 要换路子(候选:`Application.AddMessageFilter` 够不着 NC 消息,
  多半不行;或退回 pywebview fork)。**这一条是双出要问的第一个问题。**

### D3 —— 拆掉"假最大化"

现在 `toggle_maximize` 是自己算工作区、直接设 `form.Bounds`,`WindowState` 永远 Normal
(`bin/ds_shell.py:493-507`)。有了 D1+D2 之后改回 `WindowState = Maximized`,
最大化动画随之而来,`_is_max` 也从"比坐标"改成读 `WindowState`。

⚠️ **连带影响**:`show_window()` 那句注释说"我们的最大化 WindowState 一直是 Normal ⇒
`restore()` 对最大化窗口幂等"—— **D3 之后这句话不再成立**,`restore()` 会把最大化的
窗口打回小窗。这条必须一起改,否则会退回 0.92 修好的那个 A1 bug。

### D4 —— 我们自己那套拖动/改大小怎么办

有了 THICKFRAME,**系统自己管四边八角的拖拽** ⇒ `begin_resize` 与 `HIT` 里的
8 个方向码**大概率整段可以删**。但:
- 顶栏拖动(`begin_drag` → `HTCAPTION`)仍要保留,或改成在 `WM_NCHITTEST` 里报 `HTCAPTION`;
- **右上角那 6 像素斜角改不了大小(老问题 F4)有机会顺手消失** —— 那正是自绘热区的锅。
- ⚠️ 先别急着删:**同一件事两套实现同时在跑,是最容易出怪象的形态**。
  先加 D1/D2 真机看一遍系统的拖拽正不正常,确认了再删,分两个 commit。

### D5 —— 圆角与阴影

pywebview `shadow=True` 已经在建窗时做了 `DwmExtendFrameIntoClientArea(1,1,1,1)`
+ `DwmSetWindowAttribute(NCRENDERING_POLICY, ENABLED)`。加了 CAPTION 之后这两者
会不会打架 / 圆角要不要改用 `DWMWA_WINDOW_CORNER_PREFERENCE`:**未知 #2**。
Electron 有专门的 `SetRoundedCorners()`,说明它不是自动的。

## Test strategy (oracle) —— 主 agent 自己写,不外包

这一层 **Linux 上一行都跑不到**(WinForms + WebView2 + pythonnet 全是 Windows 独有),
判据只能问静态和真机两头。0.92 的教训是**七条静态判据全绿、产品照样是坏的**,
所以这次静态判据的定位要写死:**它们只证明"手段没写错",不证明"业主看得到动画"。**

1. **静态(Linux 跑得了)**
   - s1 样式位常量逐个对表 `winuser.h`(含新加的 `WS_CAPTION=0x00C00000`、
     `WS_THICKFRAME=0x00040000`)—— 抄错一位不报错,只会安静地设成别的。
   - s2 `needed` 必须同时含 CAPTION 与 THICKFRAME(**红检:去掉任一位都要红**)。
     这条直接钉死 0.92 那个错误规格,防止有人"为了外观安全"又把它砍回去。
   - s3 `WM_NCCALCSIZE` 分支必须区分 `wParam` 真假,且真分支必须**改 rgrc 并置 Result=0**。
   - s4 每个新增 `windll`/`ctypes` 调用点都声明 `argtypes` **和** `restype`
     (继承 `tests/test_win_ctypes_decls.py`;0.92 就是漏了 restype 那半边被 panel 逮到)。
   - s5 D3 连带:`show_window()` 不许在窗口最大化时无条件 `restore()`。
   - s6 D1/D2 同版本:样式位加了 CAPTION 就必须存在 NCCALCSIZE 处理(**结构判据,防中间态发版**)。
2. **探针(Windows,但不需要业主)** —— 见 D2 未知 #1,`NativeWindow` 覆写能不能成,
   必须先有一个能跑的最小探针,**探针没绿之前不写实现**。
3. **真机(只有业主答得了)**:缩小动画、放大动画、边缘有没有多出线、拖边缘分屏、
   Win11 分屏布局、最大化不盖任务栏、圆角阴影没劣化、右上角斜角。

### 这个 oracle 能被什么骗过?

- **和 0.92 一模一样的骗法**:静态全绿 + 真机没动画。这次的防线是 s2 直接把
  "CAPTION+THICKFRAME 必须在"写死,而这一条**有真机对照数据背书**(五个有动画的
  窗口全有这两位),不再是我推的。
- **新的骗法**:D2 挂上了但 `WndProc` 从没被调用到(挂错 handle / 挂在窗口重建之前),
  静态判据看不出来。⇒ 真机清单必须有一条"日志里有没有 `[窗口] NC 已接管`",
  且那行要打在**第一次真的收到 WM_NCCALCSIZE 时**,不是挂载时。
- **最阴的一种**:业主 Win11 上好了,但 Win10 那台(公司机 F:\)因为
  `wParam==0` 那条分支坏掉 —— WinFormedge 专门为 22000 以下打了补丁。
  ⇒ 真机清单要标明**两台机器都要走**。
