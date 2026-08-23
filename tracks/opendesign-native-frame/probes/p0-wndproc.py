# -*- coding: utf-8 -*-
"""P0 探针 —— 本单能不能做,全看这一条。

问的是一件事:**pythonnet 里,Python 能不能覆写 .NET 的
`protected override void WndProc(ref Message m)`,并且真的把非客户区吃掉?**

两个上游参考(Electron / WinFormedge)一个 C++ 一个 C#,没有一个是 Python 的
⇒ 这一步没有先例,只能实测。design.md 未知 #1。

判定完全机械,不靠肉眼:**非客户区被吃掉 ⇔ ClientSize == Size**
(普通窗口的 ClientSize 比 Size 小一圈,那一圈就是标题栏 + 边框)。

会闪出一个 400x300 的小窗口约一秒,然后自己关掉。**不碰 OpenDesign。**
"""
import sys, ctypes, traceback

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

WM_NCCALCSIZE = 0x0083
R = {"called": 0, "nccalc": 0, "client": None, "size": None, "err": None}

print("=" * 64)
print("P0 探针:pythonnet 覆写 WndProc + 吃掉非客户区")
print("=" * 64)
print("python :", sys.version.split()[0])
print("exe    :", sys.executable)

try:
    import clr
    print("clr    : ok")
except Exception as e:
    print("clr    : 失败 —", e)
    print("\n结论:FAIL(没有 pythonnet,环境不对 —— 多半是 python.exe 选错了)")
    sys.exit(2)

try:
    clr.AddReference("System.Windows.Forms")
    clr.AddReference("System.Drawing")
    from System import IntPtr
    from System.Drawing import Size
    from System.Windows.Forms import (Form, NativeWindow, Application,
                                      FormBorderStyle, FormStartPosition)

    class NcEater(NativeWindow):
        """把标题栏那块非客户区吃掉 —— 方案 B 的核心动作。"""

        def WndProc(self, m):
            R["called"] += 1
            if m.Msg == WM_NCCALCSIZE and m.WParam != IntPtr.Zero:
                R["nccalc"] += 1
                # rgrc[0] 原样不动 = 客户区铺满窗口 = 不给标题栏留高度
                m.Result = IntPtr.Zero
                return
            super(NcEater, self).WndProc(m)

    print("子类   : 定义成功(pythonnet 接受了这个覆写)")

    form = Form()
    form.Text = "P0 probe"
    form.FormBorderStyle = FormBorderStyle.Sizable   # 故意用带标题栏的普通窗口
    form.Size = Size(400, 300)
    form.ShowInTaskbar = False
    form.StartPosition = FormStartPosition.CenterScreen

    eater = NcEater()
    form.Show()
    Application.DoEvents()

    eater.AssignHandle(form.Handle)
    print("挂载   : AssignHandle 成功")

    # 逼窗口重算一次边框 —— 这会发 WM_NCCALCSIZE
    user32 = ctypes.windll.user32
    user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                    ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    user32.SetWindowPos.restype = ctypes.c_bool
    flags = 0x0020 | 0x0002 | 0x0001 | 0x0004 | 0x0010   # FRAMECHANGED|NOMOVE|NOSIZE|NOZORDER|NOACTIVATE
    user32.SetWindowPos(ctypes.c_void_p(int(form.Handle.ToInt64())), None,
                        0, 0, 0, 0, flags)

    for _ in range(40):
        Application.DoEvents()

    R["client"] = (form.ClientSize.Width, form.ClientSize.Height)
    R["size"] = (form.Size.Width, form.Size.Height)

    try:
        eater.ReleaseHandle()
    except Exception:
        pass
    form.Close()
    form.Dispose()

except Exception:
    R["err"] = traceback.format_exc()

print("-" * 64)
print("WndProc 被调用次数 :", R["called"])
print("其中 WM_NCCALCSIZE :", R["nccalc"])
print("ClientSize         :", R["client"])
print("Size               :", R["size"])
if R["err"]:
    print("\n异常:\n" + R["err"])

print("=" * 64)
if R["called"] == 0 and R["err"]:
    print("结论:FAIL —— 覆写这条路走不通,要另找路子(design.md 未知 #1)")
elif R["called"] == 0:
    print("结论:FAIL —— 子类定义了,但 WndProc 从没被叫到(挂载没生效)")
elif R["nccalc"] == 0:
    print("结论:PARTIAL —— WndProc 被叫到了,但没收到 WM_NCCALCSIZE(触发方式要改)")
elif R["client"] == R["size"]:
    print("结论:PASS —— 非客户区被吃掉了(ClientSize == Size),方案 B 在 Python 里可行")
else:
    print("结论:PARTIAL —— 消息收到了,但非客户区没吃掉")
    print("       ClientSize 仍小于 Size ⇒ m.Result / 返回时机的写法要调")
print("=" * 64)
