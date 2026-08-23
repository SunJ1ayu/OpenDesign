# 前提攻击:方案 B 的每一条前提,谁真的这么干过、代码在哪一行

- 日期:2026-08-23
- 攻的前提:**要拿回最小化/最大化动画,必须把 `WS_CAPTION`(+`WS_THICKFRAME`)加回去,
  并且同时接管 `WM_NCCALCSIZE` 把标题栏那块非客户区吃掉。**
- 为什么必须攻:**上一单(opendesign-minimize-animation / 0.92.0)就是死在引用太松。**
  我引用了 Electron issue #751 里 `frankhale` 的一句评论(`WS_POPUP | WS_THICKFRAME`),
  当成"别人已经踩过了"写进 design.md,然后**砍掉 THICKFRAME 只贴三个位**发版 ——
  业主装完仍然没有动画。**讨论区的一句话 ≠ 合进去的代码。**这一份只收一手代码。

> 🔴 摘录,不是链接清单。URL 会 404,结论要活到下一个接手的人手里。

---

## 来源 1:Electron —— 2014 合的 PR,和 2026 还在跑的代码

### PR #800(MERGED 2014-11-12)`Fix Windows min/max animation on frameless windows`

`atom/browser/native_window_views.cc` 实际合进去的 diff:

```cpp
#if defined(OS_WIN)
  if (!has_frame_) {
    // Set Window style so that we get a minimize and maximize animation when
    // frameless.
    DWORD frame_style = WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX |
                        WS_CAPTION;
    ::SetWindowLong(GetAcceleratedWidget(), GWL_STYLE, frame_style);
  }
#endif
```

**四个位,带 `WS_CAPTION`。** 不是 issue 评论里那个 `WS_POPUP | WS_THICKFRAME`。

### 今天的 `shell/browser/native_window_views.cc:391-414`(2026,仍在)

```cpp
#if BUILDFLAG(IS_WIN)
  if (!has_frame()) {
    // Set Window style so that we get a minimize and maximize animation when
    // frameless.

    DWORD frame_style = WS_CAPTION | WS_OVERLAPPED;
    if (CanResize())              frame_style |= WS_THICKFRAME;
    if (minimizable_)             frame_style |= WS_MINIMIZEBOX;
    if (maximizable_&&CanResize())frame_style |= WS_MAXIMIZEBOX;

    // We should not show a frame for transparent window.
    if (!thick_frame_) {
      frame_style &= ~(WS_THICKFRAME | WS_CAPTION);
      rounded_corner_ = false;
    } else {
      options.Get(options::kRoundedCorners, &rounded_corner_);
    }

    ::SetWindowLong(GetAcceleratedWidget(), GWL_STYLE, frame_style);
    SetRoundedCorners(rounded_corner_);
  }
```

⇒ 三件事被这段代码钉死:
1. **`WS_CAPTION` 是打底的**(`= WS_CAPTION | WS_OVERLAPPED`),不是可选项;
2. 注释一字不差地说这是为了 **"minimize and maximize animation when frameless"**;
3. **要关就两个一起关**(`&= ~(WS_THICKFRAME | WS_CAPTION)`)—— 上游自己把
   CAPTION 与 THICKFRAME 当成不可分的一对。**没有"只加 THICKFRAME"这种配置。**

### ⛔ 本单据此**否决**的一条路

「只加 `WS_THICKFRAME`、不加 `WS_CAPTION`」—— **是我 08-23 自己推出来的,零先例。**
真机数据同向:业主机器上 5 个有动画的窗口(Edge/设置/PowerShell/ZCode/Oopz)
**CAPTION 与 THICKFRAME 全都同时有**,没有一个只有 THICKFRAME。

## 来源 2:WinFormedge —— 和我们**同栈**(WinForms + WebView2)

`XuanchenLin/WinFormedge`,`src/WinFormedge/Classes.Formedge/FormBase.cs:390`:

```csharp
case WM_NCCALCSIZE when wParam == 1 && ExtendsContentIntoTitleBar && !Popup && !Fullscreen:
    {
        var nccalc = Marshal.PtrToStructure<NCCALCSIZE_PARAMS>(lParam);
        if (!AdjustMaximizedClientRect((HWND)m.HWnd, ref nccalc.rgrc._0))
        {
            //OnNcResize(nccalc.rgrc._0.Width, nccalc.rgrc._0.Height);
        }
        Marshal.StructureToPtr(nccalc, m.LParam, false);
    }
    return;                    // ← 直接 return:不让默认处理去留标题栏那块地方

case WM_NCCALCSIZE when wParam == 0 && !OperatingSystem.IsWindowsVersionAtLeast(10, 0, 22000):
    { _shouldPatchBoundsSize = true; }
    break;
```

⇒ 对我们的意义:
1. **加位之后必须接管 `WM_NCCALCSIZE`**,否则 CAPTION 会真的把标题栏画出来 ——
   这就是"方案 B 是两件事"的那第二件;
2. `AdjustMaximizedClientRect` **正是我们现在用"假最大化"(直接设 Bounds)绕过去的那个坑**
   (无边框窗口 `WindowState.Maximized` 会盖住任务栏)⇒ 这一单有机会把假最大化一起拆掉;
3. `wParam == 0` 那条分支说明 **Win10 22000 以下还要另打补丁** —— 业主是 Win11,
   但这条提醒我:这一层有 **OS 版本分叉**,别假设一套写法通吃。

## 来源 3:业主真机对照数据(2026-08-23,PowerShell 只读探针)

同一台机器、同一时刻,`GetWindowLongW(hwnd, GWL_STYLE)`:

| 窗口 | STYLE | CAPTION | THICKFRAME | 有动画 |
|---|---|---|---|---|
| Microsoft Edge | `17CF0000` | ✅ | ✅ | 有 |
| 设置 | `94CF0000` | ✅ | ✅ | 有 |
| PowerShell | `14CF0000` | ✅ | ✅ | 有 |
| ZCode | `34C70000` | ✅ | ✅ | 有 |
| Oopz | `B4C70000` | ✅ | ✅ | 有 |
| **OpenDesign(0.92.0)** | **`360B0000`** | **❌** | **❌** | **没有** |

`0x000B0000` = SYSMENU + MINIMIZEBOX + MAXIMIZEBOX —— **正是 0.92.0 贴回去的那三个,
一个不多一个不少**。⇒ 0.92.0 的实现没问题,**是它的规格问错了问题**。

## 这份证据**没有**回答的(别当成已知)

- **加了 CAPTION 之后圆角/阴影还在不在。** Electron 有 `SetRoundedCorners()` 专门管,
  说明它不是自动的。我们现在的阴影来自 pywebview 的 `shadow=True`
  (`DwmExtendFrameIntoClientArea` + `DwmSetWindowAttribute`),两者会不会打架:**未知**。
- **pythonnet 里怎么挂 WndProc。** pywebview 不暴露 WndProc,要挂 `NativeWindow` 子类化 ——
  上面两个参考都是 C++/C#,**没有一个是 Python 的**。这是本单最大的未知。
- **我们自己那套"发原生消息拖边缘"和 THICKFRAME 自带的拖边缘会不会打架。**
- **1px 边框。** 两个参考都提到过要对,但都没给"怎么判定没有多出来"的机械判据。
