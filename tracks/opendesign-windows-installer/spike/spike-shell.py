"""S1a 外壳探路 —— 回答一个价值 150MB 的问题:轻方案(pywebview)跑不跑得起来。

背景:S1 规划双出时,外部腿主张用 Electron(可靠,但多背一百多 MB 和一条 Node 工具链),
我主张 pywebview(留在现有 Python 里)。**两边都站得住,分歧点却是一个可测量的事实**:
`pythonnet` / `pywebview` / `pystray` 在 **embeddable Python + `._pth`** 下到底能不能用。
⇒ 不靠嘴仗定,用这张考卷在业主真机上跑一次。

判卷规则(与 S0 的 spike.py 同一套):
- **只读、不装、不改机器**:不写注册表、不进 PATH、不碰 %USERPROFILE%\\.nanobot;
  全部落在解压出来的这个文件夹里。删掉文件夹 = 完全消失。
- **每一问都要打印"凭什么"**,不许只打印 PASS —— 一张只会说 PASS 的考卷等于没考。
- **不许吞异常**:每一问失败时把真实报错和它的类型打出来,那才是我要的信息。
- **绝不能挂住**:开窗口那几问全部带超时,超时算 FAIL 并说明,不许让业主对着一个
  没反应的黑窗口等。

跑法:双击 `跑一下.bat`(它会调 python\\python.exe spike-shell.py)。
"""

from __future__ import annotations

import os
import sys
import threading
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
PASS = 0
FAIL = 0
SKIP = 0


def head(t: str) -> None:
    print(f"\n{'=' * 62}\n{t}\n{'=' * 62}")


def ok(q: str, why: str) -> None:
    global PASS
    PASS += 1
    print(f"  [PASS] {q}\n         凭据: {why}")


def no(q: str, why: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {q}\n         凭据: {why}")


def skip(q: str, why: str) -> None:
    global SKIP
    SKIP += 1
    print(f"  [SKIP] {q}\n         原因: {why}")


def err_detail(e: BaseException) -> str:
    """把真实报错原样带出来 —— 「导入失败」这四个字对我毫无用处。"""
    return f"{type(e).__name__}: {e}"


# ─────────────────────────────────────────────────────────── 0. 现场
head("0. 现场(先证明这是我以为的那个运行时,不是机器上别的 Python)")

print(f"  python  : {sys.version.split()[0]}")
print(f"  可执行  : {sys.executable}")
print(f"  工作目录: {os.getcwd()}")

exe = Path(sys.executable).resolve()
if HERE in exe.parents or str(exe).lower().startswith(str(HERE).lower()):
    ok("跑的是包内的免装 Python", f"{exe} 在包目录 {HERE} 下")
else:
    no("跑的是包内的免装 Python",
       f"{exe} 不在包目录 {HERE} 下 —— 这一跑的结论对成品无效,先弄清为什么")

pth = list(Path(sys.executable).parent.glob("python*._pth"))
if pth:
    ok("`._pth` 在起作用", f"{pth[0].name};sys.path 前三项 = {sys.path[:3]}")
else:
    no("`._pth` 在起作用", "找不到 ._pth —— 这不是 embeddable 形态,结论不可移植")


# ─────────────────────────────────────────────────────────── 1. 导入
head("1. 三个外壳组件在 embeddable 下导不导得进来(最可能死在这)")

mods = {}
for name, why_it_matters in [
    ("clr_loader", "pythonnet 的加载器,它找不到 .NET 运行时就整条路线作废"),
    ("pythonnet", "pywebview 的 Windows(EdgeChromium)后端靠它调 .NET"),
    ("webview", "窗口本体"),
    ("pystray", "托盘"),
    ("PIL", "托盘图标要用它画位图"),
]:
    try:
        mods[name] = __import__(name)
        v = getattr(mods[name], "__version__", "(无版本号)")
        ok(f"import {name}", f"版本 {v};来自 {getattr(mods[name], '__file__', '?')}")
    except BaseException as e:  # noqa: BLE001 —— 连 SystemExit 都要看见
        mods[name] = None
        no(f"import {name}", f"{err_detail(e)}  <- 它管:{why_it_matters}")


# ─────────────────────────────────────────────────────────── 2. .NET / WebView2
head("2. 这台机器上有没有 pywebview 需要的东西(缺了要靠安装器补)")

if mods.get("clr_loader"):
    try:
        import clr  # noqa: F401  (pythonnet 装好后才有这个名字)
        ok("能挂上 .NET 运行时", "import clr 成功 ⇒ pythonnet 找到了 CLR")
    except BaseException as e:  # noqa: BLE001
        no("能挂上 .NET 运行时",
           f"{err_detail(e)} —— Win10/11 自带 .NET Framework,这条红了要查 pythonnet 版本")
else:
    skip("能挂上 .NET 运行时", "clr_loader 没导进来")

# WebView2 运行时:Win11 与更新过的 Win10 自带(随 Edge),但不保证。
# 查注册表比查文件靠谱(微软官方推荐的检测方式就是查这个键)。
try:
    import winreg

    found = []
    for hive, path in [
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients"
         r"\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
        (winreg.HKEY_CURRENT_USER,
         r"Software\Microsoft\EdgeUpdate\Clients"
         r"\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
    ]:
        try:
            with winreg.OpenKey(hive, path) as k:
                found.append(winreg.QueryValueEx(k, "pv")[0])
        except OSError:
            pass
    if found:
        ok("WebView2 运行时在", f"注册表报版本 {', '.join(found)}")
    else:
        no("WebView2 运行时在",
           "两个注册表位置都没有 ⇒ 安装器必须带微软的 Evergreen 引导程序兜底")
except BaseException as e:  # noqa: BLE001
    no("WebView2 运行时在", err_detail(e))


# ─────────────────────────────────────────────────────────── 3. 真开一个窗口
head("3. 真开一个无地址栏窗口(带超时,绝不挂住)")

WINDOW_SECONDS = 6

if mods.get("webview"):
    outcome: dict[str, str] = {}

    def _probe() -> None:
        """窗口起来之后自己关掉 —— 业主不需要动手,也不许等。"""
        try:
            import webview
            w = webview.windows[0]
            outcome["title"] = w.title
            outcome["ok"] = "yes"
        except BaseException as e:  # noqa: BLE001
            outcome["err"] = err_detail(e)
        finally:
            try:
                import webview
                webview.windows[0].destroy()
            except BaseException:  # noqa: BLE001
                pass

    try:
        import webview

        # 故意加载一段自带的 HTML 而不是 127.0.0.1 —— 这一问只考"窗口起不起得来",
        # 不考后端。把两件事混在一问里,红了会分不清是谁的锅。
        webview.create_window(
            "OpenDesign 外壳探路", html="<h1 style='font-family:sans-serif'>窗口起来了</h1>",
            width=520, height=320,
        )
        t = threading.Timer(3.0, _probe)
        t.daemon = True
        t.start()
        # start() 会阻塞到窗口关闭;_probe 会在 3 秒后把它关掉
        webview.start(debug=False)
        if outcome.get("ok"):
            ok("能开出一个无地址栏窗口", f"窗口标题 = {outcome.get('title')!r},已自动关闭")
        else:
            no("能开出一个无地址栏窗口", outcome.get("err", "窗口没起来,且没有报错可看"))
    except BaseException as e:  # noqa: BLE001
        no("能开出一个无地址栏窗口", f"{err_detail(e)}\n{traceback.format_exc(limit=3)}")
else:
    skip("能开出一个无地址栏窗口", "webview 没导进来")


# ─────────────────────────────────────────────────────────── 4. 托盘
head("4. 托盘图标能不能常驻(关窗不退出全靠它)")

if mods.get("pystray") and mods.get("PIL"):
    try:
        import pystray
        from PIL import Image

        img = Image.new("RGB", (32, 32), (40, 90, 200))
        icon = pystray.Icon("opendesign-spike", img, "OpenDesign 探路")

        state: dict[str, str] = {}

        def _setup(ic: "pystray.Icon") -> None:
            try:
                ic.visible = True
                state["ok"] = "yes"
            except BaseException as e:  # noqa: BLE001
                state["err"] = err_detail(e)
            finally:
                threading.Timer(2.0, ic.stop).start()

        icon.run(setup=_setup)   # 阻塞到 stop()
        if state.get("ok"):
            ok("托盘图标能创建并显示", "pystray 报告 visible=True,2 秒后自动收掉")
        else:
            no("托盘图标能创建并显示", state.get("err", "没显示出来,且没有报错可看"))
    except BaseException as e:  # noqa: BLE001
        no("托盘图标能创建并显示", f"{err_detail(e)}\n{traceback.format_exc(limit=3)}")
else:
    skip("托盘图标能创建并显示", "pystray 或 PIL 没导进来")


# ─────────────────────────────────────────────────────────── 收据
head("收据")
print(f"  PASS {PASS}   FAIL {FAIL}   SKIP {SKIP}")
print()
if FAIL == 0 and SKIP == 0:
    print("  ⇒ 轻方案(pywebview + pystray)在这台机器上成立。")
    print("    省下 ~150MB 与一条 Node 工具链;安装器按这条路走。")
else:
    print("  ⇒ 有红或跳过的项。**这不代表项目卡住** —— 规划双出时已经把 Electron 那条路")
    print("    完整设计好了(design.md「对差异」第 8 条),红了就直接落那一条,不返工。")
    print("    把上面的报错原样发回来,我据此定。")
print()
print("  注:这一跑不写注册表、不改 PATH、不碰你已装的 OpenDesign。删掉这个文件夹即可清除。")

sys.exit(1 if FAIL else 0)
