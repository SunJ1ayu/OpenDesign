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
import ds_common  # noqa: E402
import ds_credential  # noqa: E402  变量名从配置的 apiKey 引用里读,不许写死
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
def start_backend(home: Path, lock_port: int | None = None):
    """挑端口 → 改配置 → 按计划拉起后台。返回 (supervisor, web_port, restart_gateway)。

    **缺 key 不再是死路**(track opendesign-key-onboarding):界面无条件起,
    网关等着 —— 业主要在界面里填 key,而那个界面正是 ds-web 发的。
    填完之后 ds-web 通过锁通道回来叫 `restart_gateway`。
    这一层只剩接线,"起哪几条"由 core.startup_plan 判(判据 d1/d2 咬着)。
    """
    cfg = home / ".nanobot" / "config.json"
    if not cfg.exists():
        die(f"还没装好:找不到配置文件\n{cfg}\n\n请重新运行安装程序。")

    try:
        gw, ws, web = core.pick_ports(
            [PREFERRED["gateway"], PREFERRED["ws"], PREFERRED["web"]], span=20)
    except core.PortBusy as e:
        die(f"找不到可用的端口:{e}\n\n多半是有别的程序占着这几段端口,重启电脑再试一次。")

    try:
        core.patch_config(cfg, gateway_port=gw, ws_port=ws, python_exe=str(python_exe()),
                          data_root=core.data_root_for(str(home)))
    except core.ConfigUnusable as e:
        die(f"配置没法用:{e}\n\n请重新运行安装程序。")
    except OSError as e:
        die(f"写配置失败:{e}")

    def build_env():
        """每次都**现读** key 和配置:重启网关那一下走的就是这里,
        读到的必须是业主刚填进去的那份,不是启动时缓存的。"""
        key = read_key(home)
        key_var = None
        if key:
            try:
                with cfg.open("r", encoding="utf-8") as f:
                    key_var = ds_credential.env_var_name(json.load(f))
            except (OSError, ValueError, ds_credential.CredentialError) as e:
                die(f"配置里没写清楚 key 该放进哪个变量({e})。\n\n请重新运行安装程序。")
        # 🔴 **key 只进网关那条腿**(core.service_envs)。上一版把同一份 env 给了
        #    两条腿,ds-web 也拿到 key ⇒ status() 把外壳自注入误判成"外部遮蔽" ⇒
        #    装好的应用重启后,设置里改 key 的卡片永久只读,还让业主去清一个他
        #    从没设过的变量。(2026-08-16 四审 BLOCK,判据 J 组钉住。)
        return key, core.service_envs(
            dict(os.environ), ds_root=str(install_root() / "ds"), user_home=str(home),
            dsweb_port=web, ws_port=ws, key=key, key_var=key_var, lock_port=lock_port)

    key, envs = build_env()

    # 🔴 08-14 业主真机红出来的那一条,别再写回去:
    # 上一版这里只 log 一句「没找到 key.txt,聊天会连不上大模型」就继续往下走,理由是
    # 「业主可能只是想看看待办,ds-web 是只读的、不需要 key」。**那句话是假的** ——
    # 配置里 "apiKey": "${DS_LLM_KEY}",nanobot 解析到没设的 ${VAR} 就整个拒绝启动,
    # 于是业主等来的是网关的一句英文 `Environment variable … is not set`。
    # (tests/test_ds_shell_core.py H5 真起了一次网关把这件事钉死,别再靠注释。)
    # 所以现在:起任何后台之前先扫一遍配置,缺什么当场说清楚、说该往哪儿放。
    plan = core.startup_plan(has_key=bool(key))

    # 缺 key **不再是错误**,是"该去填了" ⇒ 只有真要起网关时才拦缺变量。
    # (没有这个 if,业主永远走不到引导页:网关会死在缺变量上,而这一层直接 die。)
    if "网关" in plan["start"]:
        try:
            with cfg.open("r", encoding="utf-8") as f:
                # 拿**网关那条腿**的 env 去比,不是别的:key 只进它(service_envs),
                # 拿 ds-web 那份去比会说"DS_LLM_KEY 没设",而它本来就不该有。
                # (08-16 业主真机:这里写的是已经不存在的 `env` —— 有 key 的机器
                #  每次开机 NameError。判据 tests/test_shipped_names.py 咬着。)
                missing = core.missing_env_refs(json.load(f), envs["网关"])
        except (OSError, ValueError) as e:
            die(f"配置读不出来:{e}\n\n请重新运行安装程序。")
        # 说什么话在 core 里(判据 H6~H9 咬着);这一层只剩"有就弹"。
        trouble = core.missing_env_message(missing, app=APP, key_path=str(key_file(home)))
        if trouble:
            die(trouble)

    # 🔴 迁移必须在**起任何服务之前**(判据 h3)。网关是第一个起来的,它带着三个 MCP
    # 工具服务;老版本装过的机器上,档案还躺在安装目录里,而新的数据根是空的 ——
    # 那一刻业主问"我有哪些项目",助手会回"一个都没有",甚至在新根里建一个重名的。
    # ds_web 自己也会迁移一次(幂等),但它是**第二个**起来的,来不及。
    try:
        migration = core.prepare_data_root(user_home=str(home),
                                           ds_root=str(install_root() / "ds"))
    except ds_common.DataRootError as exc:
        die(f"数据目录不可用({exc})。\n\n请重新运行安装程序。")
    if migration["failed"]:
        die(f"你的资料从旧位置搬过来时出错了,先没有继续启动:\n{migration['failed']}\n\n"
            f"把这段发给我看看 —— 东西还在原处,没有丢。")

    logs = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP / "Logs"

    def gateway_service(e):
        return core.Service(name="网关", argv=[str(python_exe()), "-m", "nanobot", "gateway"],
                            env=e, ready_port=ws, log_path=logs / "网关.log",
                            # 冷启动要连 3 个 MCP 子进程,S0 真机上见过接近 4 分钟
                            ready_timeout=300)

    def web_service(e):
        return core.Service(name="工作台", argv=[str(python_exe()),
                                                 str(install_root() / "ds" / "bin" / "ds_web.py")],
                            env=e, ready_port=web, log_path=logs / "工作台.log",
                            ready_timeout=60)

    # plan 里那两个名字是 core 的说法("ds-web"/"网关");Service 名是业主看得见的
    # 中文名("工作台"),watchdog 和报错都用它。别把两套名字混着用。
    services = (([gateway_service(envs["网关"])] if "网关" in plan["start"] else [])
                + [web_service(envs["ds-web"])])

    sup = core.Supervisor()
    try:
        sup.start(services)
    except core.StartupFailed as e:
        sup.shutdown()
        die(f"{APP} 没能启动。\n\n{e}\n\n详细日志:{logs}")

    def restart_gateway():
        """业主在界面里填完 key ⇒ ds-web 通过锁通道叫到这里。

        **现读**一遍 key 和配置(build_env 就是干这个的),把网关换成新进程;
        界面那条腿一动不动 —— 他正看着的页面就是它发的。
        """
        k, fresh = build_env()      # fresh 是两条腿各自的 env,重启只换网关那条
        if not k:
            log("[重启网关] 收到请求,但 key.txt 还是空的 —— 不动")
            return
        try:
            sup.restart([gateway_service(fresh["网关"])])
            log("[重启网关] 完成")
        except Exception as exc:      # 回调跑在锁的线程里:炸出去会把那条线程带走
            log(f"[重启网关] 失败:{exc}")
            alert(f"key 已经存好了,但后台没能自己重启:\n{exc}\n\n"
                  f"请退出 {APP} 再打开一次。")

    return sup, web, restart_gateway


class WindowApi:
    """前端那条窗口栏按下去之后走到的地方(pywebview 的 js_api)。

    2026-08-16 业主:「为什么不能不要外面那个框,只留我们原来的前端仅仅加上
    右上角的缩小放大和退出按钮」。窗口于是改成 frameless —— 而 Windows 把
    **拖边缘改大小**也一起收走了,所以这里除了三个按钮还得接回"拖动"和"改大小"。

    做法是给窗口发一条**原生**消息(`WM_NCLBUTTONDOWN` + 命中码):之后整个拖拽
    /缩放循环由 Windows 自己跑,手感与系统边框完全一致(吸附也在)。自己算坐标
    去 move 窗口是另一条路,那条会飘、会掉帧,而且没有吸附。

    ⚠️ **这整个类在 Linux 上一行都跑不到**(要 WebView2 + WinForms 窗口)。
    能判的都推到别处了:边名和前端那份名单对表在
    tests/test_shell_window_contract.py;剩下的"按下去到底动不动"只有真机答得了,
    已进真机清单。每个方法都吞异常 —— 窗口栏坏掉不该让业主的界面跟着炸,
    托盘的「退出」永远是保底出口。
    """

    # 名字必须和 web/src/shellWindow.ts 的 RESIZE_EDGES 一字不差(判据对表)。
    HIT = {
        "caption": 2,
        "left": 10, "right": 11, "top": 12,
        "topleft": 13, "topright": 14,
        "bottom": 15, "bottomleft": 16, "bottomright": 17,
    }
    _WM_NCLBUTTONDOWN = 0x00A1

    def __init__(self, shell: "Shell"):
        self._shell = shell
        self._restore = None       # 最大化之前的窗口位置/大小

    # --- 内部 ---------------------------------------------------------
    def _form(self):
        """pywebview 的 WinForms Form 本体(它在窗口建好之后挂上 `native`)。"""
        window = getattr(self._shell, "window", None)
        return getattr(window, "native", None) if window else None

    def _on_ui(self, fn):
        """回到**拥有窗口的那个线程**再动窗口。

        js_api 的调用跑在 pywebview 自己的工作线程上,而 `ReleaseCapture()`
        只对**调用它的线程**有效、改 Bounds 也只在 UI 线程上才算数 ——
        在别的线程上做这两件事会安静地不生效(最难查的那一类)。
        """
        form = self._form()
        if form is None:
            return None
        box: list = []
        try:
            from System import Action        # pythonnet(pywebview 的 Windows 依赖)

            form.Invoke(Action(lambda: box.append(fn(form))))
        except Exception:
            try:
                box.append(fn(form))         # 拿不到 .NET 就直接跑,总比什么都不做强
            except Exception:
                return None
        return box[0] if box else None

    def _hit(self, form, code: int) -> None:
        from ctypes import wintypes            # Windows 才有(core 那边同一写法)

        user32 = ctypes.windll.user32
        # 🔴 不声明 argtypes,ctypes 按 c_int(32 位)传 —— 64 位 Windows 上 HWND
        # 一旦超过 2³¹ 就被静默截断,消息发给一个不存在的窗口:**拖不动、改不了
        # 大小,而且哪儿都不报错**。`ds_shell_core` 里的 Job 句柄早为同一件事补过
        # 声明(那段注释还在),这里漏了同一处 —— 08-17 四审 subdeepseek F2,
        # 判据 tests/test_win_ctypes_decls.py 现在机械地查每一个 windll 调用点。
        user32.SendMessageW.argtypes = [wintypes.HWND, ctypes.c_uint,
                                        ctypes.c_size_t, ctypes.c_ssize_t]
        user32.SendMessageW.restype = ctypes.c_ssize_t
        user32.ReleaseCapture()
        user32.SendMessageW(wintypes.HWND(int(form.Handle.ToInt64())),
                            self._WM_NCLBUTTONDOWN, code, 0)

    def _work_area(self, form):
        from System.Windows.Forms import Screen

        return Screen.FromHandle(form.Handle).WorkingArea

    def _is_max(self, form) -> bool:
        area = self._work_area(form)
        return (form.Left == area.X and form.Top == area.Y
                and form.Width == area.Width and form.Height == area.Height)

    # --- 前端叫得到的 ---------------------------------------------------
    def begin_drag(self):
        self._on_ui(lambda form: self._hit(form, self.HIT["caption"]))

    def begin_resize(self, edge: str):
        code = self.HIT.get(str(edge))
        if code is None:
            log(f"[窗口] 不认识的方向:{edge}")     # 前后端名单对不上了,别静默
            return
        self._on_ui(lambda form: self._hit(form, code))

    def minimize(self):
        def go(form):
            from System.Windows.Forms import FormWindowState

            form.WindowState = FormWindowState.Minimized
        self._on_ui(go)

    def toggle_maximize(self):
        def go(form):
            from System.Drawing import Rectangle

            if self._is_max(form) and self._restore:
                x, y, w, h = self._restore
                form.Bounds = Rectangle(x, y, w, h)
                return False
            self._restore = (form.Left, form.Top, form.Width, form.Height)
            area = self._work_area(form)
            # 🔴 用**工作区**而不是 WindowState.Maximized:无边框窗口最大化会连
            #    任务栏一起盖住(FormBorderStyle=None 没有系统边框帮它留位置)。
            form.Bounds = Rectangle(area.X, area.Y, area.Width, area.Height)
            return True
        return {"maximized": bool(self._on_ui(go))}

    def window_state(self):
        return {"maximized": bool(self._on_ui(self._is_max))}

    def close_window(self):
        """关 = 收进托盘,和以前点系统那个 × 一模一样(不是退出程序)。"""
        self._shell.state.on_close_requested()


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
                # 🔴 2026-08-16:这里原来只打了一句 `[后台退出] ['网关']`。
                # 业主那晚网关死了,两份日志摆在我面前也答不了「是被杀的还是自己崩的」
                # —— 因为**退出码从来没被打印过**。现在每条腿都把退出码和它自己
                # 日志的尾巴写进外壳日志(判据 c20);弹窗仍然只说人话。
                #
                # 🔴 08-17(F5,判据 c21/w7):**只看一眼**。原来先问 `poll_dead()`
                # 拿名字、再问 `dead_reports()` 拿原因,两问之间业主若正好存了 key
                # 触发重启,名册就变了 ⇒ 弹窗照弹、原因是空的。
                found = self.sup.take_dead()
                if found:
                    dead = [name for name, _ in found]
                    for _, report in found:
                        log(f"[后台退出] {report}")
                    alert(f"{'、'.join(dead)} 意外退出了。\n\n"
                          f"请退出后重新打开 {APP};日志在:\n{_log_path().parent}\n\n"
                          f"（把 外壳.log 发给我,里面有它的退出码和最后几句话。）")
                    return
                self._stop_watch.wait(3.0)
        threading.Thread(target=loop, name="ds-shell-watchdog", daemon=True).start()


def main() -> int:
    log(f"==== {APP} 外壳启动 ====")
    shell_holder: list[Shell] = []

    # ① 单实例。第二次双击走到这里就退出了,窗口由第一份自己叫到前台。
    #    这把锁同时是 ds-web 回来找我们的**唯一通道**(填完 key 请求重启网关)——
    #    所以它必须在起后台之前就位:锁端口要随 env 交给 ds-web。
    restart_holder: list = []
    lock = core.InstanceLock(
        base_port=LOCK_PORT, span=5,
        on_show=lambda: shell_holder and shell_holder[0].state.on_show(),
        on_restart=lambda: restart_holder and restart_holder[0]())
    try:
        if not lock.acquire():
            log("已有一份在跑,把它叫到前台,自己退出")
            return 0
    except core.PortBusy as e:
        die(f"启动失败:{e}")

    try:
        home = user_home()
        sup, web, restart_gateway = start_backend(home, lock_port=lock.port)
        restart_holder.append(restart_gateway)
        shell = Shell(sup, web, lock)
        shell_holder.append(shell)

        import webview

        shell.window = webview.create_window(
            APP, f"http://127.0.0.1:{web}/",
            width=1280, height=860, min_size=(960, 640),
            # 🔴 2026-08-16 业主:系统标题栏那个 "OpenDesign" 和我们前端自己的标题
            #    撞了 ⇒ 不要那个框,窗口按钮我们自己画在右上角(WindowChrome.tsx)。
            #    代价说清楚:frameless 之后 Windows 把"拖边缘改大小"也一起收走了,
            #    由 WindowApi 用原生窗口消息接回来。
            #    `easy_drag=False` 是关键:开着的话**整个页面**按哪儿都能拖窗口 ——
            #    选不了字、拖不动滚动条。拖动只认我们那条栏。
            frameless=True, easy_drag=False, js_api=WindowApi(shell),
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
