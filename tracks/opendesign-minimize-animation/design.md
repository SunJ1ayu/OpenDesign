# Design: opendesign-minimize-animation

- Change: opendesign-minimize-animation
- Status: 业主拍板做**方案 A**,已实现并收口(0.92.0,代码面主裁 PASS)。
  方案 B 那一族明确不做,留单独一单。**产品结论悬着,等真机 B1/B2。**

- 规划双出: 不适用 —— 立单时这一轮**只调查不实现**;业主拍板后落地的方案 A 是
  「往既有窗口补三个不参与绘制的样式位」,没有开新写面、方向也只有一个,
  不另花一次双出(uncertainty=high 花掉的那次是 premise attack)。真动手做方案 B 时,
  方案 B(接管 `WM_NCCALCSIZE`/`WM_NCHITTEST`)是新写面,那一单必须双出。

## 根因(一族,不是一条)

`bin/ds_shell.py` 用 `frameless=True` 建窗口 ⇒ pywebview 的 WinForms 后端执行
`self.FormBorderStyle = FormBorderStyle.None`(webview/platforms/winforms.py:237)。

WinForms 的 `Form.CreateParams` 里,`WS_SYSMENU / WS_MINIMIZEBOX / WS_MAXIMIZEBOX /
WS_THICKFRAME / WS_CAPTION` 全部挂在 `if (formBorderStyle != FormBorderStyle.None)`
这一支下面 ⇒ **无边框窗口一个都没有**。Windows 的一整套窗口待遇是按这些样式位发的:

| 缺的样式位 | 跟着丢的行为 |
|---|---|
| `WS_MINIMIZEBOX` | 最小化动画、还原动画;点任务栏图标能不能还原 |
| `WS_SYSMENU` | 右键任务栏图标 / Alt+空格 的系统菜单 |
| `WS_THICKFRAME` + `WS_MAXIMIZEBOX` | Aero Snap(拖到边缘分屏)、Win+方向键 |
| 自绘标题栏没报 `HTMAXBUTTON` | Win11 Snap Layouts(悬停最大化按钮的布局菜单) |

**外部佐证(不是我一个人推的)**:
- pywebview 作者 r0x0r 亲口承认 "frameless window limitations in Winforms",
  解法是 WinUI3 重写、准备当 7.0 发(issue #1825 / #1813;试过的人说新后端很卡)。
- issue #1749 列的三条正是我们的:改不了大小(我们 08-17 已自己修好)、
  **最小化动画消失**、**最小化后点任务栏图标叫不回窗口**。
- 微软 Q&A 1182399 专答"无边框怎么拿回最小化动画";Q&A 2120539 答"去掉标题栏
  但保住改大小和 snap";Snap Layouts 官方文档要求 `WM_NCHITTEST` 返回 `HTMAXBUTTON`。

## 清单(11 条,证据分级)

给业主看的可视化版本:https://claude.ai/code/artifact/9261b67c-0ea1-479f-a807-2f407eb22a24

**【代码里读出来的】**
- A1 缩小后托盘那条路可能叫不回窗口 —— `Shell.show_window()` → pywebview
  `show()` = `Form.Show() + Activate()`(winforms.py:399),**没有把 WindowState 改回
  Normal**。`SetForegroundWindow` 对最小化窗口不还原 ⇒ 可能永远回不来。
  ⚠️ **这条比动画严重**,而且任务栏那条路是好的(B4 上次验收走过)⇒ 极容易漏。
- C1 换显示器/改缩放后不重新铺满 —— `toggle_maximize` 只在点的那一刻设一次 Bounds。
- C2 最大化状态拖顶栏不缩回小窗 —— 我们发 `WM_NCLBUTTONDOWN`+HTCAPTION,而 Windows
  眼里窗口一直是 Normal,不触发"拖动最大化窗口即还原"。
- C3 `_is_max()` 靠比坐标猜 ⇒ 手动拖到刚好铺满就会显示"还原"图标。
  上次清单的已知偏差 **F2(贴边最大化后图标画反)就是它的症状**,不是独立小毛病。
- D1/D2 = 上次清单的 F4 / F3,原样待办。

**【上游作者/微软文档说的】**
- B1 最小化没动画(业主报的)、B4 无 Snap Layouts。

**【我按 Windows 规则推的 —— 真机一眼可判,没验过不许当结论】**
- B2 还原也没动画、B3 拖边缘不分屏、B5 无系统菜单、B6 Win+方向键无效、
  D3 阴影/圆角(pywebview `shadow` 默认 True 且我们没关,但 frameless 之后灵不灵没验过)。

## 🔴 一笔自己的账:「吸附也在」被我抄了三遍

`bin/ds_shell.py:302`、`WindowChrome.tsx:17`、`tracks/archive/opendesign-shell-chrome/
design.md:85` **三处都写着无边框之后"吸附也在"/"手感和系统边框一样"**,
而这句话我从来没有任何证据 —— 它是 08-16 我推出来的,一路被抄进了三份文档,
连真机清单 F1 都建立在"贴边最大化会发生"这个假设上。

按微软文档,Aero Snap 要 `WS_THICKFRAME | WS_MAXIMIZEBOX`,我们两个都没有 ⇒
**这句话很可能是假的**。同 [[memory: 这个「因为」是读来的还是推来的]]。
真机拖一次就定案。

## Approach(两条,待业主拍板)

### 方案 A —— 补样式位(推荐先做)
窗口建好后 `SetWindowLongPtrW(GWL_STYLE, ... | WS_MINIMIZEBOX | WS_SYSMENU)`
+ `SetWindowPos(SWP_FRAMECHANGED|SWP_NOMOVE|SWP_NOSIZE|SWP_NOZORDER|SWP_NOACTIVATE)`。
没有 `WS_CAPTION` ⇒ **外观零变化**(那两位只在有标题栏时才画东西)。
- 修:B1 B2 B5 B6,很可能连 A1;加上 `WS_THICKFRAME|WS_MAXIMIZEBOX` 还能带回 B3。
- 幂等 ensure:每次 `minimize()` 前先确保样式位在(pywebview 的 fullscreen 会改
  `FormBorderStyle`,那条路会重算 CreateParams 把我们加的位刷掉)。
- ⚠️ `tests/test_win_ctypes_decls.py` 会机械查新增的每个 windll 调用点有没有
  声明 argtypes —— `SetWindowLongPtrW` 的返回值和参数**必须**声明,不然 64 位
  句柄/样式值被截成 32 位,而且不报错。
- A1 另需单独一行修:`Shell.show_window()` 里先把 WindowState 还原再 Show/Activate。

### 方案 B —— 换成成熟产品的做法(单独一单)
保留完整的 `WS_OVERLAPPEDWINDOW`,接管 `WM_NCCALCSIZE` 把标题栏那 30px 吃掉、
`WM_NCHITTEST` 把顶栏报 `HTCAPTION`、最大化按钮报 `HTMAXBUTTON`。
VS Code / Electron(`titleBarStyle: 'hidden'`)/ WinFormedge(和我们同栈:
WinForms + WebView2)走的都是这条。
- 修:B 组 + C 组全部,拿回真最大化 + DPI 跟随 + Snap Layouts。
- 代价:pywebview 不暴露 WndProc ⇒ 要在 pythonnet 里挂 `NativeWindow`/子类化,
  容易带回 1px 边框,圆角和阴影要重新对;**必须真机反复调**。

## Alternatives considered

- **等 pywebview 7.0(WinUI3 后端)**:作者说会合,但试过的人报"incredibly laggy"
  且分支未发布 ⇒ 不押。
- **最小化前临时把 FormBorderStyle 改回 Sizable、之后改回 None**(微软 Q&A 的
  简易解法):会闪一下边框,而且改 FormBorderStyle 会重算窗口样式、跟我们自己的
  Bounds 最大化打架 ⇒ 不选。
- **自己用定时器逐帧缩小窗口**:掉帧、闪、和系统动画不同步 ⇒ 不选(已写进 non-goals)。

## Test strategy (oracle)

这一层在 Linux 上一行都跑不到,所以判据只能问**静态**的、和**真机**的两头:

1. 机械(Linux 跑得了):
   - `tests/test_win_ctypes_decls.py` —— 新增的 Windows API 调用点必须声明 argtypes
     (已有闸,新代码自动进射程)。
   - 新判据:样式位常量的值必须对(`WS_MINIMIZEBOX=0x00020000` 等),且**加**样式位
     用的是 `|=` 语义、不许整个覆盖(写成赋值就会把窗口现有样式全清掉 ⇒ 窗口变形)。
   - 新判据:`show_window()` 那条路里必须先还原 WindowState 再 Show(A1)。
   - 红检:把 `|` 改成 `=`、把常量改错一位,判据必须红。
2. 真机(只有业主答得了):最小化动画、托盘叫回、右键任务栏、Win+方向键、拖边分屏。

**这个 oracle 能被什么骗过?**

- 断言全绿 + 真机照样没动画 ⇒ 说明**根因判错了**(不是样式位),那时不许去调判据,
  要回到方案 B 或重新找根因。
- 更阴的一种:业主的 Windows 把「显示动画」总开关关了 ⇒ **任何**程序都没有动画,
  我改什么都白改。**真机清单第一条必须是拿记事本对照**,不然我会把系统设置
  当成我们的 bug 修一整天。
- 静态判据永远问不出"窗口有没有变形/多了一条边" ⇒ 只能靠真机截图,已进清单。
