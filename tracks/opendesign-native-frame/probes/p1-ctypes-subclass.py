# -*- coding: utf-8 -*-
"""P1 探针 —— P0 失败之后的第二条路。

P0(2026-08-23 真机)结论:**pythonnet 覆写 `NativeWindow.WndProc` 挂不上。**
子类定义成功、`AssignHandle` 成功,但 `WndProc` 被调用 **0 次** ——
`WndProc` 是 `protected virtual`,pythonnet 3.0.5 默认不暴露 protected 成员,
于是那个 `def WndProc` 只是给 Python 对象加了个同名方法,**没有覆写到 .NET 那一侧**。

P1 换一条**完全绕开 pythonnet** 的路:经典 Win32 子类化 ——
用 ctypes 把自己的窗口过程 `SetWindowLongPtrW(GWLP_WNDPROC)` 挂上去,
不接管的消息用 `CallWindowProcW` 交回原来那个(WinForms 自己那层)。

判定同 P0,机械:**非客户区被吃掉 ⇔ ClientSize == Size**。

会闪一个 400x300 的小窗口约一秒,然后自己关掉。**不碰 OpenDesign。**
"""
import sys, ctypes, traceback
from ctypes import wintypes

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GWLP_WNDPROC = -4
WM_NCCALCSIZE = 0x0083
R = {"called": 0, "nccalc": 0, "client": None, "size": None,
     "old": None, "err": None}

print("=" * 64)
print("P1 探针:ctypes 子类化(绕开 pythonnet)")
print("=" * 64)
print("python :", sys.version.split()[0])

try:
    import clr
    clr.AddReference("System.Windows.Forms")
    clr.AddReference("System.Drawing")
    from System.Drawing import Size
    from System.Windows.Forms import (Form, Application, FormBorderStyle,
                                      FormStartPosition)

    user32 = ctypes.windll.user32
    # 🔴 不声明 argtypes/restype,64 位上句柄和返回值被静默截成 32 位 ——
    #    改了等于没改,而且哪儿都不报错(项目既有判据 test_win_ctypes_decls.py)。
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, ctypes.c_uint,
                                 ctypes.c_size_t, ctypes.c_ssize_t)
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int,
                                         ctypes.c_ssize_t]
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.CallWindowProcW.argtypes = [ctypes.c_ssize_t, wintypes.HWND,
                                       ctypes.c_uint, ctypes.c_size_t,
                                       ctypes.c_ssize_t]
    user32.CallWindowProcW.restype = LRESULT
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND,
                                    ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    user32.SetWindowPos.restype = wintypes.BOOL

    def my_proc(hwnd, msg, wparam, lparam):
        R["called"] += 1
        if msg == WM_NCCALCSIZE and wparam:
            R["nccalc"] += 1
            return 0          # rgrc[0] 不动 = 客户区铺满 = 不给标题栏留高度
        return user32.CallWindowProcW(R["old"], hwnd, msg, wparam, lparam)

    # 🔴 这个引用必须活到解挂之后:被 GC 掉 = Windows 回调进一片野内存 = 崩。
    hook = WNDPROC(my_proc)

    form = Form()
    form.Text = "P1 probe"
    form.FormBorderStyle = FormBorderStyle.Sizable   # 故意用带标题栏的普通窗口
    form.Size = Size(400, 300)
    form.ShowInTaskbar = False
    form.StartPosition = FormStartPosition.CenterScreen
    form.Show()
    Application.DoEvents()

    hwnd = wintypes.HWND(int(form.Handle.ToInt64()))
    R["old"] = user32.SetWindowLongPtrW(
        hwnd, GWLP_WNDPROC, ctypes.cast(hook, ctypes.c_void_p).value)
    print("挂载   : SetWindowLongPtrW 返回原 proc =", hex(R["old"] or 0))
    if not R["old"]:
        print("         ⚠️ 返回 0 = 挂载失败")

    flags = 0x0020 | 0x0002 | 0x0001 | 0x0004 | 0x0010  # FRAMECHANGED|NOMOVE|NOSIZE|NOZORDER|NOACTIVATE
    user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, flags)
    for _ in range(40):
        Application.DoEvents()

    R["client"] = (form.ClientSize.Width, form.ClientSize.Height)
    R["size"] = (form.Size.Width, form.Size.Height)

    # 解挂再关窗口,别让 WinForms 在我们的 proc 上收尾
    if R["old"]:
        user32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC, R["old"])
    form.Close()
    form.Dispose()

except Exception:
    R["err"] = traceback.format_exc()

print("-" * 64)
print("窗口过程被调用次数 :", R["called"])
print("其中 WM_NCCALCSIZE :", R["nccalc"])
print("ClientSize         :", R["client"])
print("Size               :", R["size"])
if R["err"]:
    print("\n异常:\n" + R["err"])

print("=" * 64)
if R["called"] == 0:
    print("结论:FAIL —— 这条路也挂不上,两条都断了(要重新想办法)")
elif R["nccalc"] == 0:
    print("结论:PARTIAL —— 挂上了,但没收到 WM_NCCALCSIZE(触发方式要改)")
elif R["client"] == R["size"]:
    print("结论:PASS —— 非客户区被吃掉了(ClientSize == Size),方案 B 可行")
else:
    print("结论:PARTIAL —— 消息收到了,但非客户区没吃掉,返回值写法要调")
print("=" * 64)
