# P0 探针真机结果(2026-08-23,业主机器)

## 逐字输出

```
装在:D:\AI\OpenDesign
================================================================
P0 探针:pythonnet 覆写 WndProc + 吃掉非客户区
================================================================
python : 3.12.10
exe    : D:\AI\OpenDesign\python\python.exe
clr    : ok
子类   : 定义成功(pythonnet 接受了这个覆写)
挂载   : AssignHandle 成功
----------------------------------------------------------------
WndProc 被调用次数 : 0
其中 WM_NCCALCSIZE : 0
ClientSize         : (384, 261)
Size               : (400, 300)
================================================================
结论:FAIL —— 子类定义了,但 WndProc 从没被叫到(挂载没生效)
================================================================
```

## 结论:`design.md` 未知 #1 = **这条路走不通**

`NativeWindow.WndProc` 是 `protected virtual`。pythonnet 3.0.5 默认不暴露
protected 成员 ⇒ Python 里那个 `def WndProc` **只是给 Python 对象加了个同名方法,
没有覆写到 .NET 那一侧**。所以:类定义不报错、`AssignHandle` 也成功
(它们都不检查覆写有没有生效),但消息一条都不会走到我们这儿。

**这正是"静默失败"最难查的形态:每一步都返回成功,只有计数器是 0。**
探针把它挡在了写实现之前 —— 这一条硬闸(tasks.md「P0 没绿不许写实现」)是划算的。

⇒ 转 P1:`probes/p1-ctypes-subclass.py`,用 ctypes 直接
`SetWindowLongPtrW(GWLP_WNDPROC)` 做经典 Win32 子类化,**完全绕开 pythonnet**。

## 顺带被证伪的两件事(都是我的)

### 1. 安装目录不是 nsi 里那个默认值

真实安装目录 = **`D:\AI\OpenDesign`**(注册表 `HKCU\Software\OpenDesign\InstallDir`)。

我一直按 `OpenDesign.nsi:49` 的 `InstallDir "$LOCALAPPDATA\Programs\${APP}"` 当事实,
**而它只是默认值** —— 下一行 `InstallDirRegKey` 就写着会优先用注册表里的旧位置,
**我读到了那一行却没想它的含义**。今天第二次栽在"拿默认值当运行时事实"上
(第一次:以为 pywebview 没关 ShowInTaskbar 就等于窗口在任务栏上)。

### 2. ⚠️ 我对 ZCode 那份报告的指控**不成立,要收回**

我在会话里说过「它说的 `D:\AI\OpenDesign` 是错的,安装器根本不装到那里」。
**那句话是错的:`D:\AI\OpenDesign` 就是真实安装目录。**
它当时说的「本机 D:\AI\OpenDesign 装的就是 0.92.0」在**目录这一点上是对的**。

仍然成立的部分:它的结论「修复已在」是错的(真机证伪),而且它把
Win+方向键同时列进"修了"和"没修"。**但目录那一条是我冤枉它的**,
理由还是同一个:我拿 nsi 的默认值去驳一个关于运行时的说法。
