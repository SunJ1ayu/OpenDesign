#!/usr/bin/env python3
"""OpenDesign 桌面外壳 —— Windows 胶水层(S1b)。

双击 OpenDesign.exe 走到的就是这里。它负责的事:
  拿单实例锁 → 挑端口 → 改写配置 → 拉起网关和 ds-web → 开一个桌面窗口装 ds-web
  → 关窗口收进托盘 → 托盘"退出"才真的收摊。

**这一层没有任何自动考卷验得了**(pywebview / pystray / WebView2 / .NET 全是 Windows 独有,
而且要有桌面会话)。所以它的所有**可判定逻辑**都被推到了 `ds_shell_core.py` 里,
那一层有 `tests/test_ds_shell_core.py` 逐条锁着。留在这个文件里的只剩"接线"。

接线接错了照样是坏的,所以这个文件的规矩是:
  ① 每一步失败都要变成**业主看得懂的一句话**,而且是**弹窗**——
     业主是双击图标进来的,没有终端可看,往 stderr 打等于没打。
  ② 弹窗用 ctypes 直接叫 MessageBoxW,**不依赖 pywebview/.NET**:
     偏偏最需要报错的时候(WebView2 缺失、.NET 挂不上)那些东西正好是坏的。
  ③ 每一处"我在 Linux 上验不了"的假设,都在注释里点名,并进 Windows 真机考卷。
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ds_shell_core as core  # noqa: E402

APP = "OpenDesign"
# 锁位挑在一段不常用的高位端口上。它只是锁 + 唤醒通道,不承载数据。
LOCK_PORT = 18788
# 首选端口沿用现有部署(docs/install-windows.md / start.ps1),被占了会自动往后挪。
PREFERRED = {"gateway": 18790, "ws": 8765, "web": 8766}


# ---------------------------------------------------------------- 报错与日志
def _log_path() -> Path:
    d = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP / "Logs"
    d.mkdir(parents=True, exist_ok=True)
    return d / "外壳.log"


def log(msg: str) -> None:
    """带时间戳写一行。

    🔴 时间戳是 08-14 那次真机红补上的:那份日志没有时间,于是「一起来就崩」和
    「等满 300s 超时」在事后长得一模一样,只能回头问业主等了多久。
    证据要自带能对账的东西 —— 一个 strftime 换的是一趟真机。
    """
    stamp = time.strftime("%H:%M:%S")
    try:
        with _log_path().open("a", encoding="utf-8") as f:
            for i, line in enumerate(msg.rstrip().splitlines() or [""]):
                # 多行文案(弹窗那种)只给第一行盖戳,其余缩进对齐 —— 免得每行都盖,
                # 反而看不出哪里是一条记录的开头。
                f.write(f"{stamp} {line}\n" if i == 0 else f"         {line}\n")
    except OSError:
        pass


def alert(msg: str, title: str = APP) -> None:
    """弹一个系统对话框。业主没有终端,这是唯一能被看见的出口。"""
    log(f"[提示] {msg}")
    try:
        ctypes.windll.user32.MessageBoxW(None, msg, title, 0x10)  # MB_ICONERROR
    except Exception:
        print(msg, file=sys.stderr)


def die(msg: str) -> None:
    alert(msg)
    sys.exit(1)


# ---------------------------------------------------------------- 路径
def install_root() -> Path:
    """包根:里面有 python\\ 和 ds\\。本文件在 <root>\\ds\\bin\\ 下。"""
    return HERE.parent.parent


def user_home() -> Path:
    """业主数据目录 —— **安装目录之外**(design:卸载/回滚不许碰数据)。

    这里同时是子进程眼里的 HOME/USERPROFILE,所以 nanobot 读的是
    <user_home>\\.nanobot\\config.json,而不是业主机器上原来那份。
    """
    d = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP / "UserData"
    d.mkdir(parents=True, exist_ok=True)
    return d


def python_exe() -> Path:
    return install_root() / "python" / "python.exe"


def key_file(home: Path) -> Path:
    """机主自备的 LLM key 放在哪儿(deploy-security D1:部署者不发 key)。

    路径与现有部署一致(ds-nanobot.ps1:20),只是 USERPROFILE 换成了应用自己的数据目录。
    **报错文案要把这个路径原样念给业主听**,所以它得是个能被引用的单一来源。
    """
    return home / ".openDesign" / "key.txt"


def read_key(home: Path) -> str | None:
    try:
        return key_file(home).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


# ---------------------------------------------------------------- 托盘图标
def tray_image():
    """托盘图标。装机时安装器会放一份 图标.png 进来;没有就画一个,不为图标崩掉。"""
    from PIL import Image, ImageDraw

    # 安装器铺的是 ds\assets\图标.png(仓库里的 assets/图标.png,由 installer/make-icon.py
    # 与程序图标 opendesign.ico **同一份形状**生成)。路径挑在 assets\ 下是因为包里的 ds\
    # 是仓库根的镜像 —— 组包时那道"ds/ 里每个文件都必须是仓库里的"闸按这个对应关系查。
    png = install_root() / "ds" / "assets" / "图标.png"
    if png.exists():
        try:
            return Image.open(png)
        except Exception:
            pass
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 4, 60, 60), radius=14, fill=(38, 70, 83, 255))
    d.rounded_rectangle((18, 18, 46, 46), radius=6, fill=(233, 196, 106, 255))
    return img


# ---------------------------------------------------------------- 主流程
def start_backend(home: Path):
    """挑端口 → 改配置 → 拉起两条腿。返回 (supervisor, web_port)。"""
    cfg = home / ".nanobot" / "config.json"
    if not cfg.exists():
        die(f"还没装好:找不到配置文件\n{cfg}\n\n请重新运行安装程序。")

    try:
        gw, ws, web = core.pick_ports(
            [PREFERRED["gateway"], PREFERRED["ws"], PREFERRED["web"]], span=20)
    except core.PortBusy as e:
        die(f"找不到可用的端口:{e}\n\n多半是有别的程序占着这几段端口,重启电脑再试一次。")

    try:
        core.patch_config(cfg, gateway_port=gw, ws_port=ws, python_exe=str(python_exe()))
    except core.ConfigUnusable as e:
        die(f"配置没法用:{e}\n\n请重新运行安装程序。")
    except OSError as e:
        die(f"写配置失败:{e}")

    env = core.child_env(dict(os.environ), ds_root=str(install_root() / "ds"),
                         user_home=str(home), dsweb_port=web, ws_port=ws, key=read_key(home))

    # 🔴 08-14 业主真机红出来的那一条,别再写回去:
    # 上一版这里只 log 一句「没找到 key.txt,聊天会连不上大模型」就继续往下走,理由是
    # 「业主可能只是想看看待办,ds-web 是只读的、不需要 key」。**那句话是假的** ——
    # 配置里 "apiKey": "${DS_LLM_KEY}",nanobot 解析到没设的 ${VAR} 就整个拒绝启动,
    # 于是业主等来的是网关的一句英文 `Environment variable … is not set`。
    # (tests/test_ds_shell_core.py H5 真起了一次网关把这件事钉死,别再靠注释。)
    # 所以现在:起任何后台之前先扫一遍配置,缺什么当场说清楚、说该往哪儿放。
    try:
        with cfg.open("r", encoding="utf-8") as f:
            missing = core.missing_env_refs(json.load(f), env)
    except (OSError, ValueError) as e:
        die(f"配置读不出来:{e}\n\n请重新运行安装程序。")
    # 说什么话在 core 里(判据 H6~H9 咬着);这一层只剩"有就弹"。
    trouble = core.missing_env_message(missing, app=APP, key_path=str(key_file(home)))
    if trouble:
        die(trouble)

    logs = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP / "Logs"
    sup = core.Supervisor()
    try:
        sup.start([
            core.Service(name="网关", argv=[str(python_exe()), "-m", "nanobot", "gateway"],
                         env=env, ready_port=ws, log_path=logs / "网关.log",
                         # 冷启动要连 3 个 MCP 子进程,S0 真机上见过接近 4 分钟
                         ready_timeout=300),
            core.Service(name="工作台", argv=[str(python_exe()),
                                              str(install_root() / "ds" / "bin" / "ds_web.py")],
                         env=env, ready_port=web, log_path=logs / "工作台.log",
                         ready_timeout=60),
        ])
    except core.StartupFailed as e:
        sup.shutdown()
        die(f"{APP} 没能启动。\n\n{e}\n\n详细日志:{logs}")
    return sup, web


class Shell:
    """把 core 的状态机接到 pywebview / pystray 上。"""

    def __init__(self, sup, web_port: int, lock: core.InstanceLock):
        self.sup = sup
        self.web_port = web_port
        self.lock = lock
        self.window = None
        self.icon = None
        self.state = core.ShellState(ui=self, on_stop=self.stop_backend)

    # --- core.ShellState 要求的 UI 三件 -------------------------------
    # ⚠️ 这三个方法可能被**锁的监听线程**调到(第二次双击时)。pywebview 的
    # EdgeChromium 后端内部会把调用转到 UI 线程,但这一点我在 Linux 上验不了 ⇒
    # 已进 Windows 真机考卷(「开着的时候再双击一次图标」那一问)。
    def show_window(self):
        if self.window:
            self.window.show()

    def hide_window(self):
        if self.window:
            self.window.hide()

    def destroy(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass

    # --- 收摊 ---------------------------------------------------------
    def stop_backend(self):
        log("收摊:停两条腿")
        try:
            self.sup.shutdown()
        finally:
            self.lock.release()

    # --- 托盘 ---------------------------------------------------------
    def run_tray(self):
        import pystray

        menu = pystray.Menu(
            pystray.MenuItem("打开 OpenDesign", lambda *_: self.state.on_show(), default=True),
            pystray.MenuItem("退出", lambda *_: self.state.on_quit()),
        )
        self.icon = pystray.Icon(APP, tray_image(), APP, menu)
        # run_detached 在没有主循环可挂靠时会失败 ⇒ 用自己的线程跑 run()
        threading.Thread(target=self.icon.run, name="ds-shell-tray", daemon=True).start()

    # --- 看门狗:哪条腿死了要说话,不能让界面一直转圈 -------------------
    def run_watchdog(self):
        self._stop_watch = threading.Event()

        def loop():
            while not self.state.exiting:
                dead = self.sup.poll_dead()
                if dead:
                    log(f"[后台退出] {dead}")
                    alert(f"{'、'.join(dead)} 意外退出了。\n\n"
                          f"请退出后重新打开 {APP};日志在:\n{_log_path().parent}")
                    return
                self._stop_watch.wait(3.0)
        threading.Thread(target=loop, name="ds-shell-watchdog", daemon=True).start()


def main() -> int:
    log(f"==== {APP} 外壳启动 ====")
    shell_holder: list[Shell] = []

    # ① 单实例。第二次双击走到这里就退出了,窗口由第一份自己叫到前台。
    lock = core.InstanceLock(
        base_port=LOCK_PORT, span=5,
        on_show=lambda: shell_holder and shell_holder[0].state.on_show())
    try:
        if not lock.acquire():
            log("已有一份在跑,把它叫到前台,自己退出")
            return 0
    except core.PortBusy as e:
        die(f"启动失败:{e}")

    try:
        home = user_home()
        sup, web = start_backend(home)
        shell = Shell(sup, web, lock)
        shell_holder.append(shell)

        import webview

        shell.window = webview.create_window(
            APP, f"http://127.0.0.1:{web}/",
            width=1280, height=860, min_size=(960, 640),
            # 自己的窗口边框(有最小化/最大化/关闭),**不是浏览器** ⇒ 没有地址栏。
            # S1a 那份考卷把"无地址栏"写进了断言名却没验,这里不重复那个错:
            # 这一条由 Windows 真机考卷用眼睛验(截图)。
            frameless=False, easy_drag=False,
        )
        # 关窗口 = 收进托盘。pywebview 的 closing 回调返回 False 表示"别关"。
        shell.window.events.closing += lambda: shell.state.on_close_requested()

        shell.run_tray()
        shell.run_watchdog()
        log(f"窗口打开:http://127.0.0.1:{web}/")
        webview.start()          # 阻塞,直到窗口 destroy
        shell.state.on_quit()    # 走正常关闭时也要把后台收干净
        return 0
    except ImportError as e:
        # 少了 pywebview / pythonnet / PIL —— 包被装坏了
        die(f"{APP} 少了运行所需的组件:{e}\n\n请重新运行安装程序。")
    except Exception as e:
        # .NET 挂不上、WebView2 缺失都会落到这里。**不许只抛 CLR 栈**:
        # 业主看到一堆英文栈只会来问我。原始栈进日志,弹窗给人话。
        log(traceback.format_exc())
        die(f"{APP} 启动时出错:{e}\n\n"
            f"如果是第一次在这台电脑上打开,多半是缺少微软的 WebView2 运行时,\n"
            f"请重新运行安装程序(它会自动补装)。\n\n详细日志:{_log_path()}")
    finally:
        lock.release()
    return 1


if __name__ == "__main__":
    sys.exit(main())
