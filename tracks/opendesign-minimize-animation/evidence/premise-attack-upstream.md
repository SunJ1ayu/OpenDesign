# 前提攻击:「补样式位就能拿回最小化动画」这句话站不站得住

- 日期:2026-08-23
- 攻的前提:**无边框窗口没有最小化动画,是因为它缺 `WS_MINIMIZEBOX` 等样式位;
  补回去就有,而且外观不变。**
- 为什么必须攻:这一层在 Linux 上一行都跑不到,判据只问得了静态。**前提错了 =
  业主白装一趟**,而他的真机验收是这个项目最贵的资源(已经欠了好几趟)。
- 结论:**前提成立**,且不是我一个人推的 —— 三个互相独立的来源指向同一件事,
  其中一个是十年前把同一个坑踩平并公开修法的项目。

> 🔴 这份文件是**摘录**,不是链接清单。URL 会 404、issue 会被删,而结论要活到
> 下一个接手的人手里。原文按当日读到的样子抄在下面。

---

## 来源 1:Electron issue #751(2014)——**和业主今天报的一字不差**

标题:`No animation when minimizing and restoring frameless window`(状态:CLOSED)

正文:
> When minimizing or restoring a window on both OS X and Windows, you see an
> animation as it moves to the dock or task bar. However if the window is set to
> frameless, then the animation doesn't happen and the window just dissapears...

`frankhale` 的根因结论:
> Okay, I've figured this out on Windows. **The issue is that the window does not
> have the correct styles applied to it.** … The simplest window style I got the
> shadow to work with was `WS_POPUP | WS_THICKFRAME`, to also get aero snap,
> maximizing, …

**最值钱的一问一答**(正是我这一单的风险):
> `anaisbetts`: Won't adding those styles also give you a real window frame
> (i.e. no longer be frameless)? …some of them might show an ugly frame
>
> `frankhale`: On my Windows 8.1 box **it does not add a frame but it does fix the
> animation.** I've tested with and without the patch to isolate the change.

收口:`PR #800 resolved this on Windows`。

⇒ 对我们的意义:① 根因判断被独立复现;② 「加了会不会冒出边框」这个我最担心的
问题,十年前有人替我们实测过了。**但注意他实测的是 Win8.1、且带了 `WS_THICKFRAME`**
—— 我这一单**不加** THICKFRAME(它会改非客户区尺寸),所以我的外观风险**比他更小**,
不是更大。

## 来源 2:pywebview issue #1749 —— 上游承认这是一族,不是一条

> Currently, enabling `Frameless=True` leads to several issues, including but not
> limited to:
> - Inability to resize the window
> - **Disappearance of the minimize animation**
> - **Failure to restore the window by clicking the taskbar icon after minimizing**

三条里第一条我们 08-17 已自己修好;第二条是业主今天报的;**第三条我们从来没验过**
(⇒ 清单 A1,本单一并修)。

作者 `r0x0r` 在 #1825 / #1813 的回应:
> There is now a winui3 implementation that **tackles the frameless window
> limitations in Winforms**. … It will be released as 7.0

试用者 `Solaranlage1` 对 winui3 分支:
> It does work, and provides the features I thought of. But is **incredibly
> laggy/slow**, making it not a good fit for an actual programm.

⇒ 「等上游 7.0」这条路当前不可用,自己补位是对的。

## 来源 3:VS Code issue #158065 —— 成熟产品的「无边框」根本没丢样式

排查日志里 Chromium 建窗口时打印的样式:
> `CreateWindowEx hwnd … style 06cc0000`
> `WS_CLIPCHILDREN | WS_CLIPSIBLINGS | WS_CAPTION | WS_THICKFRAME | WS_SYSMENU`

⇒ **Electron/Chromium 的 frameless ≠ WinForms 的 `FormBorderStyle=None`**。
前者保留整套系统样式、只是不去画;后者是真的一个都不发。这条证实了我给业主的
「三档」分类不是修辞,是两种不同的实现。

## 来源 4:微软自己的两处

- Q&A 1182399(专答无边框怎么拿回最小化动画):给的两条路是 **CreateParams 补
  `WS_MINIMIZEBOX` 等样式**,或临时把 FormBorderStyle 换回 Sizable 再换回来
  (后者会闪,已在 design.md 里否掉)。
- Q&A 2120539 / Snap Layouts 文档:**Aero Snap 要 `WS_THICKFRAME | WS_MAXIMIZEBOX`**;
  Win11 的分屏布局菜单还要 `WM_NCHITTEST` 返回 `HTMAXBUTTON`。
  ⇒ 这两条是我把 B3/B4 划出本单、留给方案 B 的**依据**,不是我图省事。

---

## 这次攻题**没有**推翻、但必须写下来的三条剩余风险

1. **业主的 Windows 可能把「显示动画」总开关关了** ⇒ 任何程序都没有这段动画,
   我改什么都白改。**真机清单第一条必须是拿记事本对照。**
2. 上面所有实测都在别人的机器/别的框架上。我们这一份**没有任何人跑过**,
   Linux 上也跑不了 ⇒ 静态判据 + 一趟真机是唯一的验收路径。
3. `SetWindowLongPtrW` 只在 64 位上导出。本仓库随包的解释器已核实是
   `PE32+ … x86-64`(`file pkg/python/python.exe`),所以不做 32 位回退 ——
   **这条要是哪天变了,补位会静默失败。**
