# Design: pywebview 5.4 → 6.2.1

- Date: 2026-08-24
- 业主指令:「先升级吧」(我建议过"动画刚好别动它",他坚持,按他的决定走)

## 为什么要升

我们锁在 **5.4(2025-01)**,最新 **6.2.1(2026-04)**,落后两个大版本。
0.96 的动画是在**旧后端上绕出来的**,不是上游认可的路。

## 前提核查(已做,不是推论)

**① 破坏性改动碰不到我们。** 6.0 的三条 BREAKING:
`FileDialog` 枚举取代旧常量、`window.get_element(s)` 移除、`DRAG_REGION_SELECTOR` 搬进 settings。
**我们用到的 pywebview API 只有 8 个**(机械列出来的,不是回忆):

    webview.create_window / webview.start
    window.events.shown / window.events.closing
    window.show / window.hide / window.restore / window.destroy
    (外加 window.native —— 拿 WinForms 的 Form 对象)

三条 BREAKING 一条都不沾。

**② 我们的动画挂在 WinForms 后端上,那部分没被动过。**
`git diff 5.4 6.2.1 -- webview/platforms/winforms.py` 共 273+/113-,
但按 `frameless|FormBorderStyle|WndProc|CreateParams` 过滤 **一行都没有**。
新增的是深色模式相关的 `DwmSetWindowAttribute(hwnd, 20/38, ...)`(6.0 的特性)。
⇒ 我们靠 `form.Handle` + `GWL_STYLE` + 窗口过程子类化做的那套,**接口面没变**。

⚠️ **但"接口面没变"不等于"行为没变"。** 6.x 新增的 Dwm 调用会改窗口的
深色模式/背景材质属性,那和我们的非客户区接管是**同一片地**。
这一层 Linux 上验不了 —— 属于证据边界,进真机清单。

## 判据要问什么

**问产物,不是问 pin 写没写对**(老教训:0.92/0.93 都栽在"问手段没问结果"):

- w1 包里装的 pywebview **版本号 == pin**(pip 解析可能给出别的版本)
- w2 我们用到的 8 个 API 在包里**真的存在**(升级把某个改名了就当场红)
- w3 WinForms 后端模块在包里(没有它整个外壳起不来)

## 回退路径(说清楚)

`SHELL_PINS` 改回 `pywebview==5.4` 重新打包即可,**代码零改动**。
业主那边:重装 0.96 的安装包就回到旧版。
