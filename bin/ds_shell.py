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
import ds_diag  # noqa: E402  启动可观测性:run_id / 分阶段耗时 / 诊断包
import ds_shell_core as core  # noqa: E402

APP = "OpenDesign"
# 外壳打开页面时在地址里报的身份。前端靠它决定要不要画那条窗口栏
# (无边框之后三个按钮 + 拖动带 + 八个把手全是我们自己画的)。
# **唯一来源是 web/src/shellWindow.ts 的同名常量**,两边一字不差
# (tests/test_shell_window_contract.py x10 对表)。
# 为什么不用"pywebview 有没有把 api 注进页面"来判:它在 on_navigation_completed
# 之后才注入(页面脚本早跑完了)⇒ 前端首帧问它永远答 false,窗口栏整块不画。
# 0.89/0.90 两版就是这么发出去的(业主:「拖不动 / 右上角还是没有」)。
SHELL_MARK = "shell=1"


def window_url(port: int) -> str:
    """外壳打开的那个地址。**唯一来源** —— 开窗口和写日志都叫它。

    分开写两遍的代价已经付过一次:日志里印的地址少了标记,而那份
    `外壳.log` 正是业主报"没按钮"时我唯一的现场。
    (判据 x10 直接调它,不是去源码里 grep 字面量。)
    """
    return f"http://127.0.0.1:{port}/?{SHELL_MARK}"


# 锁位挑在一段不常用的高位端口上。它只是锁 + 唤醒通道,不承载数据。
LOCK_PORT = 18788
# 首选端口沿用现有部署(docs/install-windows.md / start.ps1),被占了会自动往后挪。
PREFERRED = {"gateway": 18790, "ws": 8765, "web": 8766}


# ---------------------------------------------------------------- 报错与日志
def _app_dir() -> Path:
    """这个软件在业主机器上自己的目录。日志和实验开关都住这儿。"""
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP


def _log_path() -> Path:
    d = _app_dir() / "Logs"
    d.mkdir(parents=True, exist_ok=True)
    return d / "外壳.log"


# ── 窗口动画开关(0.96.0 起**默认开**)──────────────────────────────
# 0.94/0.95 这里默认是**关**的,业主一句话点破了那个决定的自相矛盾:
#   「你为什么不直接给我做好动画的,要默认关闭动画」
# —— 我给 0.95 装了"不对就自动退回去"的保险,却又不敢依赖它。
#   要么保险可信、就该默认开;要么不可信、就不该把它当卖点。
#   我选了对自己最安全、对业主最麻烦的那一半:风险我躲了,力气他出。
#
# 而且 0.95 之后**「打开就白」在结构上已经没了**:开窗口时一个边框动作都不做,
# 方案 B 要等业主点缩小才装 ⇒ 就算真把画面搞坏,**重开软件就是好的**,
# 不像 0.93 那样一起来就是砖。既然最坏情况已经从"砖"降到"重开一下",
# 就没有理由再让业主自己去建文件。
DISABLE_FLAG = "关掉窗口动画.on"


def frame_animation_on() -> bool:
    """要不要接系统窗口框架(缩小/放大的动画靠它)。**默认开。**

    不想要就在 `%LOCALAPPDATA%\\OpenDesign\\` 里新建一个空文件,
    名字叫 `关掉窗口动画.on`,重开软件即可。删掉它就回到默认。

    🔴 **读不到环境时倒向"关"**(判据 f4 守着 except 必须 `return False`)。
    方向仍然是有讲究的,只是理由换了:这个逃生门是给"已经发现它坏了"的人用的。
    读不出文件系统时,把"可能已经关过"当成"关过"——
    让一个本来没事的人少一段动画(小),好过让一个已经被坑过的人再被坑一次(大)。
    """
    try:
        return not (_app_dir() / DISABLE_FLAG).is_file()
    except Exception:
        return False


def log(msg: str) -> None:
    """带时间戳写一行。

    🔴 时间戳是 08-14 那次真机红补上的:那份日志没有时间,于是「一起来就崩」和
    「等满 300s 超时」在事后长得一模一样,只能回头问业主等了多久。
    证据要自带能对账的东西 —— 一个 strftime 换的是一趟真机。

    🔴 2026-08-30(判据 s1):**补上日期** —— 上面那笔账只还了一半。
    业主 08-25 晚白屏、08-30 才回话,中间那几行属于哪一天,只有时分秒的日志答不了。
    续行缩进由 stamp 长度算出来,不写死数字(写死的那种迟早和格式对不上)。
    """
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    pad = " " * (len(stamp) + 1)
    try:
        with _log_path().open("a", encoding="utf-8") as f:
            for i, line in enumerate(msg.rstrip().splitlines() or [""]):
                # 多行文案(弹窗那种)只给第一行盖戳,其余缩进对齐 —— 免得每行都盖,
                # 反而看不出哪里是一条记录的开头。
                f.write(f"{stamp} {line}\n" if i == 0 else f"{pad}{line}\n")
    except OSError:
        pass


# 这一次启动的证据链。**在模块导入时就建**,不是在 main() 里 —— 那样 t0 才贴着
# 进程真正的起点(import 本身也可能慢,那段时间也该被量到)。
# 白屏和"打开好慢"都靠它留下的东西查(track opendesign-startup-observability)。
DIAG = ds_diag.StartupLog(emit=log)


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


# ── winuser.h 的几个常量 ──────────────────────────────────────────────
# 🔴 值抄错一位**不会报错**,只会安静地设成别的位 ⇒ 判据 s1 逐个对表 winuser.h。
#    GWL_STYLE 是负数,别写成 0x10。
GWL_STYLE = -16
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020

# ── 方案 B(track opendesign-native-frame)新增 ─────────────────────
# 0.92.0 只贴了上面那三个不参与绘制的位,真机证明**动画不归它们管** ——
# 归下面这两个。代价是它们会真的改变非客户区尺寸,所以必须同时接管
# WM_NCCALCSIZE 把那块地方吃掉。两件事同生共死(判据 n3)。
GWLP_WNDPROC = -4
WM_NCCALCSIZE = 0x0083
WS_CAPTION = 0x00C00000          # = WS_BORDER | WS_DLGFRAME,别拆开写
WS_THICKFRAME = 0x00040000
MONITOR_DEFAULTTONEAREST = 0x0002


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class NCCALCSIZE_PARAMS(ctypes.Structure):
    """WM_NCCALCSIZE 的 lParam。rgrc[0] 进来是"建议的窗口矩形",

    我们把它原样留下 = 客户区铺满整个窗口 = 不给标题栏留高度。
    """
    _fields_ = [("rgrc", RECT * 3), ("lppos", ctypes.c_void_p)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]


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
        # 🔴 这个引用必须活到解挂之后。ctypes 的回调对象一旦被 GC,
        #    Windows 之后每发一条消息都是往野内存里跳 —— 随机时刻崩,
        #    而且崩在别处,查不到这里。判据 n6 机械守着它必须挂在 self 上。
        self._wndproc_hook = None
        self._old_wndproc = 0
        self._hooked_hwnd = 0      # 挂在**哪个**句柄上 —— 见 _install_wndproc
        self._user32 = None
        self._nc_seen = False      # 收到过真的 WM_NCCALCSIZE 没有(D2b)
        self._wndproc_warned = False   # 窗口过程里的错只记一次,别刷满盘
        # 假最大化(开关关着时走的那条)还原前的位置。0.94.0 从 0.92 抄回来 ——
        # 真最大化在没有 WM_NCCALCSIZE 接管时会连任务栏一起盖住。
        self._restore = None
        # 方案 B 装上之后量出来不对、已经自动退回去了 ⇒ 这一轮别再试。
        # 不记住的话业主每点一次缩小就装一次、撤一次,每次闪一下,日志也刷满。
        self._frame_gave_up = False

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
        except Exception as exc:
            # 🔴 这里原来会"退而求其次"地在**当前线程**上再跑一遍 fn,注释写着
            # 「总比什么都不做强」—— 那句是错的(08-17 四审两腿各自命中)。
            # `ReleaseCapture()` 只对调用它的线程有效、改 `Bounds` 也只在 UI 线程上
            # 才算数:在工作线程上跑它们**安静地不生效**,而这正是本函数存在的理由。
            # 业主看到的是"点了没反应",日志里一个字都没有 —— 比什么都不做更难查。
            # 宁可留一句话。
            log(f"[窗口] 回不到 UI 线程,这次窗口操作没做:{exc.__class__.__name__}")
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
        """这块屏幕上"不含任务栏"的那个矩形。假最大化按它铺。

        0.94.0 从 0.92 抄回来(0.93 的 D3 把它当死代码删了,前提是真最大化
        成立 —— 而真机把那个前提推翻了)。
        """
        from System.Windows.Forms import Screen

        return Screen.FromHandle(form.Handle).WorkingArea

    def _is_max(self, form) -> bool:
        """窗口现在算不算"最大化" —— 两条路的答法不一样,必须跟着开关走。

        开关开(方案 B):最大化是**真的**,直接问窗口自己。
        开关关(默认):最大化是自己设 Bounds 铺满工作区的,`WindowState`
        从头到尾都是 `Normal` ⇒ 问它永远答"没最大化",前端那个图标就一直是错的。

        🔴 比坐标那条有个安静的错法(0.93 的 D3 就是为它改的):业主手动把窗口
        拖到正好铺满工作区,也会被判成"已最大化"。默认路径接受这个已知缺陷 ——
        它是 0.92 就有的、业主用了一版没提过,而"整个窗口白掉"不是。
        """
        if frame_animation_on():
            from System.Windows.Forms import FormWindowState

            return form.WindowState == FormWindowState.Maximized
        area = self._work_area(form)
        return (form.Left == area.X and form.Top == area.Y
                and form.Width == area.Width and form.Height == area.Height)

    # --- 让 Windows 认这个窗口是正经窗口 ---------------------------------
    def _apply_native_styles(self, form) -> None:
        """把 frameless 顺手拿走的几个样式位贴回去(**必须在 UI 线程上跑**)。

        2026-08-23 业主:「缩小按钮在页面上是直接消失,不会像成熟的产品一样有
        向下缩小的动画」。根因不是动画是**身份**:`FormBorderStyle = None` 之后,
        WinForms 的 `CreateParams` 把 `WS_SYSMENU / WS_MINIMIZEBOX /
        WS_MAXIMIZEBOX / WS_THICKFRAME / WS_CAPTION` 整批挂在
        `if (formBorderStyle != None)` 底下**一个都不发**,而 Windows 的窗口待遇
        (最小化动画、还原动画、系统菜单、Win+方向键)全是按这些位发的。

        Electron 2014 年踩的是同一个坑(electron#751),结论一字不差:
        「问题是这个窗口没有被加上正确的样式」;当时有人担心"加了会不会冒出真的
        边框",实测**不会**。摘录见 track 的 evidence/premise-attack-upstream.md。

        🔴 **这是方案 B 的那条路,贴五个位** —— 含 `WS_CAPTION` 与 `WS_THICKFRAME`。
        (2026-08-24 更正:这段话原来写着"只贴不影响绘制的三个位",那是 0.92 的
        事实;0.93 的 D1 把位扩到五个时**没有同步这段注释**,于是它在树上撒了一天谎。
        同一个事实存在两处、只更新其中一处 —— 这个项目的老毛病,又一次。)

        那两个位会真的改变窗口非客户区的尺寸,所以它们和 `WM_NCCALCSIZE` 接管
        **同生共死**(判据 n3)。而整条路现在挂在实验开关后面:
        0.93.0 默认走这里,业主真机「打开全是白的什么都没有了」。
        默认路径是 `_apply_safe_styles`(只贴三个不参与绘制的位)。

        🔴 **整个函数吞掉自己的异常**(判据 s7 机械守着)。理由不是"稳一点好":
        `minimize()` 会先叫它、再设 `WindowState = Minimized`。它要是把异常抛出去,
        那一行就跑不到了 —— **业主按下缩小按钮会毫无反应**。
        拿"缩小"这个功能本身去赌"缩小的动画",是这一单最不该犯的错。
        `_on_ui` 那层的 except 也接不住这件事:它印的是「回不到 UI 线程」,
        而这里失败的原因五花八门(缺 API、句柄没了、权限),那句话会把排查带偏。
        """
        try:
            self._apply_native_styles_unsafe(form)
        except Exception as exc:
            # 贴不上就算了,窗口该干什么还干什么 —— 只是没有那段动画。
            log(f"[窗口] 贴系统样式位失败(缩小照常,只是没动画):{exc!r}")

    def _apply_native_styles_unsafe(self, form) -> None:
        """真正干活的那半,调用者只有上面那个 —— 它负责兜异常。"""
        from ctypes import wintypes            # Windows 才有(同 _hit 的写法)

        user32 = ctypes.windll.user32
        # 不声明 argtypes 的话 HWND 和样式值都按 c_int 传,64 位上被静默截断 ——
        # 改了等于没改,而且哪儿都不报错(判据 tests/test_win_ctypes_decls.py)。
        user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int,
                                             ctypes.c_ssize_t]
        user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND,
                                        ctypes.c_int, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        user32.SetWindowPos.restype = wintypes.BOOL

        hwnd = wintypes.HWND(int(form.Handle.ToInt64()))
        style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
        needed = (WS_CAPTION | WS_THICKFRAME
                  | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)
        if style & needed == needed:
            return                       # 已经贴过了,别白发一次 FRAMECHANGED
        # 🔴 **或上去**,不是赋值。直接赋值会把窗口现有的样式全清掉 ⇒ 窗口当场变形。
        #    (Electron 是建窗时赋值,那是另一种情形 —— 它那时窗口还没有别的样式。)
        user32.SetWindowLongPtrW(hwnd, GWL_STYLE,
                                 style | WS_CAPTION | WS_THICKFRAME
                                 | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)
        # 改完样式必须通知一声,Windows 才会重算这个窗口的边框。四个 NO* 是保证
        # 它**只**重算边框:少一个就会顺手移动窗口 / 改大小 / 抢层级 / 抢焦点。
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                            SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE
                            | SWP_NOZORDER | SWP_NOACTIVATE)
        log("[窗口] 已把 CAPTION/THICKFRAME/MINIMIZEBOX/MAXIMIZEBOX/SYSMENU 贴回窗口")

    # --- 接管非客户区(方案 B 的另一半)---------------------------------
    def _wndproc(self, hwnd, msg, wparam, lparam):
        """装在 WinForms 那层**上面**的窗口过程。只接管一条消息。

        `WM_NCCALCSIZE` 问的是"这个窗口的客户区有多大"。默认答案会给标题栏和
        边框留出位置 —— 而我们要的是**客户区铺满整个窗口**(外观上看不见框,
        系统眼里框还在)⇒ 不动 `rgrc[0]`,直接 `return 0`。
        P1 探针实测:这一下之后 ClientSize 从 384 变成 400,正好等于 Size。

        🔴 **最大化要额外收一次边。** 带 `WS_THICKFRAME` 的窗口最大化时,
        Windows 给的 `rgrc[0]` 会向外溢出一圈边框宽度(它以为那圈要画边框)——
        不收回来就会**盖住任务栏**、右下角内容被切。收到显示器的工作区为止。
        WinFormedge 的 `AdjustMaximizedClientRect` 干的就是这件事。

        🔴 其余消息一律交回 `CallWindowProcW` —— 交回**我们替换掉的那个** proc,
        不是 `DefWindowProcW`。WinForms 自己那层还在下面,绕过去会让它负责的
        一大堆行为静默失效(判据 n5 守着)。
        """
        if msg == WM_NCCALCSIZE:
            try:
                if not self._nc_seen:
                    # 🔴 **这一行才是"接管真的生效了"的证据**(design.md D2b)。
                    #    挂载成功只证明 SetWindowLongPtrW 返回了非 0 ——
                    #    P0 探针那次每一步都"成功"而回调一次没被叫到。
                    #    真机清单 A1 认的就是这一行,别把它挪回挂载处。
                    self._nc_seen = True
                    log("[窗口] 非客户区接管已生效(收到第一条 WM_NCCALCSIZE)")
                # 🔴 只有 wParam 为真时 lParam 才是 NCCALCSIZE_PARAMS;
                #    为假时它是一个裸 RECT,碰不得。
                if wparam and self._user32.IsZoomed(hwnd):
                    self._fit_maximized_to_work_area(hwnd, lparam)
            except Exception as exc:
                self._warn_once(f"[窗口] 处理 WM_NCCALCSIZE 出错:{exc!r}")
            # 🔴 **只有 wParam 为真时才自己了断;为假时交回原 proc。**
            #
            #    2026-08-24 业主追问"别人做成了为什么我们做不成",我去扒了
            #    WinFormedge(同一套壳:WinForms + WebView2)的真实代码
            #    `src/WinFormedge/Classes.Formedge/FormBase.cs:390`:
            #
            #      case WM_NCCALCSIZE when wParam == 1 && ...:  ... return;
            #      case WM_NCCALCSIZE when wParam == 0 && ...:  ... break;  ← 落到 base.WndProc
            #
            #    **它在 wParam == 0 那条上从不短路,而是交回默认处理。**
            #
            #    而 0.93 我把这条改成了 `return 0`(收评审腿 subdeepseek F2 的建议),
            #    还在这里写下"WinFormedge 也为这条路单独打过补丁"——
            #    **那句话是我没读代码编的,而且和事实相反。**
            #    改之前(58b397e)的写法本来是对的、和参考实现一致;改之后
            #    (c09ad55)才进的 0.93,也就是业主唯一跑过、然后白屏的那一版。
            #
            #    机制上说得通:短路掉 wParam==0 那条,WinForms 自己那层
            #    就没法维护它的客户区记账,而 WebView2 是挂在它下面的子窗口 ——
            #    子窗口的布局/绘制正是靠这套记账。
            #    ⚠️ **这是最可疑的一条线索,不是已证实的根因。** 只有真机能定案。
            if wparam:
                return 0
        try:
            return self._user32.CallWindowProcW(self._old_wndproc, hwnd, msg,
                                                wparam, lparam)
        except Exception as exc:
            # 🔴 窗口过程里把异常抛出去 = 消息循环被带走 = 整个界面卡死。
            #    但**返回 0 绝不是"同一个结果"**:对 WM_NCHITTEST 它意味着
            #    整窗口都不可拖不可缩,对 WM_GETMINMAXINFO 意味着最大化约束失效
            #    (panel subdeepseek F3 —— 我原来的注释在这点上写错了)。
            #    所以这里必须留下痕迹,又不能每条消息都写盘 ⇒ 只记一次。
            self._warn_once(f"[窗口] 窗口过程转发失败,后续消息可能行为异常:{exc!r}")
            return 0

    def _warn_once(self, msg: str) -> None:
        """窗口过程里记日志:只记第一条。

        每秒可能有上百条消息,老老实实每条都写会把业主的盘写满
        (panel subdeepseek F6)。但一条都不留就没法查(F3)——所以留第一条。
        """
        if self._wndproc_warned:
            return
        self._wndproc_warned = True
        log(msg)

    def _fit_maximized_to_work_area(self, hwnd, lparam) -> None:
        """最大化时把客户区收回显示器工作区,否则溢出一圈、盖住任务栏。"""
        params = ctypes.cast(lparam,
                             ctypes.POINTER(NCCALCSIZE_PARAMS)).contents
        mon = self._user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not self._user32.GetMonitorInfoW(mon, ctypes.byref(info)):
            return          # 拿不到就别乱改 —— 溢出一圈,总比算错一个位置强
        params.rgrc[0] = info.rcWork

    def _install_wndproc(self, form) -> None:
        """把窗口过程装上去(幂等)。**必须在 UI 线程上跑。**

        整个函数吞异常,和 `_apply_native_styles` 同一个理由:装不上的时候
        窗口该干什么还干什么,只是没有动画。**不拿功能去赌观感。**
        """
        # 🔴 幂等要比**句柄**,不能只看"挂过没有"。改 FormBorderStyle 会让
        #    WinForms 重建窗口句柄(pywebview 的 fullscreen 就走这条),
        #    重建之后旧 hwnd 上那份挂载连同它的窗口一起没了,而 _wndproc_hook
        #    还非空 —— 只看它就会**再也不重挂**,业主看到的是"全屏切回来之后
        #    动画就没了"。这正是 0.92 里样式位被安静刷掉的同一种病。
        try:
            hwnd_now = int(form.Handle.ToInt64())
        except Exception as exc:
            log(f"[窗口] 拿不到窗口句柄,这次不接管:{exc.__class__.__name__}")
            return
        if self._wndproc_hook is not None and self._hooked_hwnd == hwnd_now:
            return
        try:
            self._install_wndproc_unsafe(form)
        except Exception as exc:
            self._wndproc_hook = None
            log(f"[窗口] 接管非客户区失败(窗口照常,只是没动画):{exc!r}")

    def _install_wndproc_unsafe(self, form) -> None:
        from ctypes import wintypes            # Windows 才有(同 _hit 的写法)

        # WINFUNCTYPE 只在 Windows 上存在 ⇒ 必须留在函数里,不能提到模块级,
        # 否则这个文件在 Linux 上连 import 都过不去(判据都是静态读源码的)。
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, ctypes.c_uint,
                                     ctypes.c_size_t, ctypes.c_ssize_t)

        user32 = ctypes.windll.user32
        # 不声明 argtypes/restype,64 位上句柄和返回值被静默截成 32 位 ——
        # "改了等于没改",而且哪儿都不报错(tests/test_win_ctypes_decls.py)。
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int,
                                             ctypes.c_ssize_t]
        user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        user32.CallWindowProcW.argtypes = [ctypes.c_ssize_t, wintypes.HWND,
                                           ctypes.c_uint, ctypes.c_size_t,
                                           ctypes.c_ssize_t]
        user32.CallWindowProcW.restype = LRESULT
        user32.IsZoomed.argtypes = [wintypes.HWND]
        user32.IsZoomed.restype = wintypes.BOOL
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, ctypes.c_ulong]
        user32.MonitorFromWindow.restype = ctypes.c_void_p
        user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p,
                                           ctypes.POINTER(MONITORINFO)]
        user32.GetMonitorInfoW.restype = wintypes.BOOL
        self._user32 = user32

        # 🔴 先存到 self 再挂:挂上之后 Windows 随时可能回调进来,
        #    那一刻这个对象必须已经有主。存成局部变量 = 被 GC = 崩(判据 n6)。
        self._wndproc_hook = WNDPROC(self._wndproc)
        # 句柄只从这一个地方取一次:原来这里 wintypes.HWND(...) 一次、
        # 记账时又 hwnd.value or 0 一次,两条路算同一个数 ——
        # panel(submimo P3)提的,不是 bug,但没理由留两条路。
        hwnd_int = int(form.Handle.ToInt64())
        self._old_wndproc = user32.SetWindowLongPtrW(
            wintypes.HWND(hwnd_int), GWLP_WNDPROC,
            ctypes.cast(self._wndproc_hook, ctypes.c_void_p).value)
        if not self._old_wndproc:
            self._wndproc_hook = None
            raise OSError("SetWindowLongPtrW(GWLP_WNDPROC) 返回 0 —— 没挂上")
        self._hooked_hwnd = hwnd_int
        # 只说"挂上了" —— **生效**要等 _wndproc 收到第一条消息才敢说(D2b)。
        log("[窗口] 窗口过程已挂上(尚未收到消息)")

    def uninstall_wndproc(self) -> None:
        """把窗口过程还回去。**窗口销毁之前必须叫。**

        不还的话:我们的回调对象随 Python 对象一起走,而 Windows 可能还在给
        这个 hwnd 发最后几条消息(`WM_DESTROY` / `WM_NCDESTROY`)——
        那时回调进的是一片已经没人管的内存。这一条静态判据问不出来,
        是 panel(submimo)标的 P1,我自审时也记了"从来没解挂过"。
        """
        if self._wndproc_hook is None or not self._old_wndproc:
            return
        try:
            from ctypes import wintypes

            self._user32.SetWindowLongPtrW(
                wintypes.HWND(self._hooked_hwnd), GWLP_WNDPROC,
                self._old_wndproc)
            log("[窗口] 已把窗口过程还回去")
        except Exception as exc:
            log(f"[窗口] 还原窗口过程失败:{exc!r}")
        finally:
            # 🔴 无论还成没还成都清干净:留着一个指向已销毁窗口的旧 proc,
            #    下次挂载时会被当成"还挂着"而跳过。
            self._wndproc_hook = None
            self._old_wndproc = 0
            self._hooked_hwnd = 0

    def _apply_native_styles_and_frame(self, form) -> None:
        """两件事一起做,**顺序要紧**。

        先接管非客户区、再加样式位:反过来的话,从加上 `WS_CAPTION` 到接管
        生效之间,窗口会闪一下**真的标题栏**。

        🔴 整个包在 try 里(判据 s7 机械守着)。里面那两个各自也吞异常,
        这一层是**给以后加第三件事的人**准备的:`minimize()` 先叫这里、
        再设 WindowState,这儿要是把异常抛出去,业主按下缩小会毫无反应 ——
        拿"缩小"这个功能去赌"缩小的动画",是这条路上最不该犯的错。
        """
        try:
            if frame_animation_on() and not self._frame_gave_up:
                # 方案 B 全套。**先接管非客户区,再贴位** —— 顺序见上面。
                self._install_wndproc(form)
                self._apply_native_styles(form)
                # 🔴 装完**当场量一次**,不对就自己退回去。
                #    0.93 那趟业主报"全白",而我手上一个数字都没有,只能再要一趟。
                info = self._log_frame_diagnostics(form)
                if not self._frame_looks_sane(info):
                    self._revert_native_frame(form)
            else:
                # 默认路径 = 0.92 那套(真机验过能用):只贴三个不参与绘制的位。
                self._apply_safe_styles(form)
        except Exception as exc:
            log(f"[窗口] 接系统框架失败(窗口照常,只是没动画):{exc!r}")

    def _apply_safe_styles(self, form) -> None:
        """默认路径:只贴 0.92 那三个**不参与绘制**的位。

        `WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX` 管的是系统菜单、
        Win+方向键、以及任务栏右键那个菜单 —— 0.92 真机验过它们确实回来了,
        而且**不改变窗口的非客户区尺寸**,所以不会挤到内容、不会冒出边框。

        动画不归它们管(0.92 那一版被业主当场证伪:「缩小和放大的动画还是没有」),
        动画归 `WS_CAPTION|WS_THICKFRAME` —— 那两个在实验开关后面。

        🔴 和 `_apply_native_styles` 一样吞掉自己的异常:`minimize()` 会先叫
        这里、再设 WindowState。抛出去 = 业主按下缩小毫无反应。
        """
        try:
            self._apply_safe_styles_unsafe(form)
        except Exception as exc:
            log(f"[窗口] 贴系统样式位失败(缩小照常,只是没动画):{exc!r}")

    def _apply_safe_styles_unsafe(self, form) -> None:
        """真正干活的那半,调用者只有上面那个 —— 它负责兜异常。"""
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        # 不声明 argtypes 的话 HWND 和样式值都按 c_int 传,64 位上被静默截断 ——
        # 改了等于没改,而且哪儿都不报错(判据 tests/test_win_ctypes_decls.py)。
        user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int,
                                             ctypes.c_ssize_t]
        user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND,
                                        ctypes.c_int, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        user32.SetWindowPos.restype = wintypes.BOOL

        hwnd = wintypes.HWND(int(form.Handle.ToInt64()))
        style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
        needed = WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU
        if style & needed == needed:
            return                       # 已经贴过了,别白发一次 FRAMECHANGED
        # 🔴 **或上去**,不是赋值。直接赋值会把窗口现有的样式全清掉 ⇒ 窗口当场变形。
        user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style | needed)
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                            SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE
                            | SWP_NOZORDER | SWP_NOACTIVATE)
        log("[窗口] 已把 MINIMIZEBOX/MAXIMIZEBOX/SYSMENU 贴回窗口(默认路径,不动边框)")

    def _log_frame_diagnostics(self, form) -> None:
        """开着实验开关时,把窗口的**实际几何**写进日志。

        由来:0.93.0 那趟真机业主报「全白」,而我手上一个数字都没有 ——
        窗口多大、客户区多大、WebView2 那个子窗口还在不在、它的矩形是什么,
        全不知道,只能再要一趟。这个函数就是不让那件事重演(判据 f9)。

        三样缺一不可:
          - `GetWindowRect` + `GetClientRect`:接管有没有把客户区铺满窗口。
            两者宽高相等 = 接管生效;客户区矮一个标题栏 = 接管没生效。
          - `EnumChildWindows`:WebView2 是**子窗口**。白屏最可能就死在这 ——
            子窗口没了、或者它的矩形是 0×0、或者跑到窗口外面去了。

        🔴 整段吞异常:诊断失败绝不能连累窗口。拿功能去赌日志是本末倒置。
        """
        try:
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            # 🔴 每一个都要声明 argtypes/restype。不声明的话 64 位上句柄被静默
            #    截成 32 位 —— 诊断会印出**看着像真的、其实是错的**数字,
            #    那比没有数字更坏:我会拿着它去查一个不存在的现象。
            #    (判据 tests/test_win_ctypes_decls.py 机械守着,这一版就是它抓的。)
            user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
            user32.GetWindowRect.restype = wintypes.BOOL
            user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
            user32.GetClientRect.restype = wintypes.BOOL
            user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR,
                                             ctypes.c_int]
            user32.GetClassNameW.restype = ctypes.c_int
            hwnd = wintypes.HWND(int(form.Handle.ToInt64()))

            win, cli = RECT(), RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(win))
            user32.GetClientRect(hwnd, ctypes.byref(cli))
            log(f"[诊断] 窗口矩形 {win.right - win.left}x{win.bottom - win.top} "
                f"@({win.left},{win.top})  "
                f"客户区 {cli.right - cli.left}x{cli.bottom - cli.top}")

            found = []

            ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND,
                                          ctypes.c_ssize_t)

            def _each(child, _lparam):
                try:
                    buf = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(child, buf, 256)
                    r = RECT()
                    user32.GetWindowRect(child, ctypes.byref(r))
                    found.append((buf.value, r.right - r.left, r.bottom - r.top))
                except Exception:
                    pass
                return True

            user32.EnumChildWindows.argtypes = [wintypes.HWND, ENUMPROC,
                                                ctypes.c_ssize_t]
            user32.EnumChildWindows.restype = wintypes.BOOL
            user32.EnumChildWindows(hwnd, ENUMPROC(_each), 0)
            log(f"[诊断] 子窗口 {len(found)} 个:" +
                ("; ".join(f"{n} {w}x{h}" for n, w, h in found)
                 if found else "**一个都没有**"))
            return found
        except Exception as exc:
            log(f"[诊断] 采集窗口几何失败(不影响窗口):{exc!r}")
            return None

    def _frame_looks_sane(self, info) -> bool:
        """刚装上的方案 B 有没有把画面弄没 —— 只回答"明显坏了没有"。

        判据很粗,**故意的**:WebView2 是窗口的子窗口,业主报的"全白"
        最可能的机器现象是**子窗口没了、或者被压成 0×0**。
        只咬这两种清清楚楚的坏状态。

        🔴 **拿不到数据一律当成"没问题"**(判据 h6 守着 except 必须 `return True`)。
        误撤的代价是白闪一下 + 没有动画,而它换不来任何好处;
        漏撤最多回到 0.93 那个已知状态,业主删掉开关文件就能退出来。

        ⚠️ **这一层抓不住"几何正常但就是不画"。** 真是那种,业主还会看到白屏 ——
        别把这个函数说成"保证不白",它不是。
        """
        try:
            if info is None:
                return True                  # 压根没量到,不做判断
            if not info:
                log("[诊断] 🔴 窗口里一个子窗口都没有 —— 画面多半没了,撤销方案 B")
                return False
            biggest = max(w * h for _n, w, h in info)
            if biggest <= 0:
                log("[诊断] 🔴 子窗口全被压成 0 大小 —— 画面多半没了,撤销方案 B")
                return False
            return True
        except Exception as exc:
            log(f"[诊断] 判断窗口是否正常时出错,按'正常'处理:{exc!r}")
            return True

    def _revert_native_frame(self, form) -> None:
        """把方案 B 整个退回去 —— **两头都要做**。

        🔴 只做一半是**比白屏更坏**的状态:样式位还在而没人接管 `WM_NCCALCSIZE`
        ⇒ 窗口会长出一条真的标题栏(判据 n3 讲的就是这对同生共死)。
        所以顺序是:先解挂窗口过程,再把两个位摘掉,最后 `SWP_FRAMECHANGED` 通知一声。

        退完记 `_frame_gave_up`,这一轮不再试(不然业主每点一次缩小就闪一下)。
        """
        self._frame_gave_up = True
        try:
            from ctypes import wintypes

            self.uninstall_wndproc()
            user32 = ctypes.windll.user32
            user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
            user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int,
                                                 ctypes.c_ssize_t]
            user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
            user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND,
                                            ctypes.c_int, ctypes.c_int,
                                            ctypes.c_int, ctypes.c_int,
                                            ctypes.c_uint]
            user32.SetWindowPos.restype = wintypes.BOOL

            hwnd = wintypes.HWND(int(form.Handle.ToInt64()))
            style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
            user32.SetWindowLongPtrW(hwnd, GWL_STYLE,
                                     style & ~(WS_CAPTION | WS_THICKFRAME))
            user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                                SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE
                                | SWP_NOZORDER | SWP_NOACTIVATE)
            log("[窗口] 已把方案 B 退回去(窗口该正常了,代价是这一轮没有动画)。"
                "请把 外壳.log 里 [诊断] 那几行发我。")
        except Exception as exc:
            log(f"[窗口] 🔴 退回方案 B 时出错,窗口可能不正常:{exc!r}\n"
                f"        请退出软件、在 %LOCALAPPDATA%\\OpenDesign 里建一个"
                f"空文件 {DISABLE_FLAG} 再打开,就不会再试了。")

    def ensure_native_styles(self):
        """窗口一出来就叫一次(main 里挂在 `shown` 上)。

        🔴 **0.95.0 起,这条路只贴不改变非客户区的三个安全位。**
        方案 B(会改变窗口边框计算的那半)挪到业主**第一次点缩小/最大化**时才装。

        为什么(2026-08-24 真机日志):

            17:54:47 窗口打开:http://127.0.0.1:8766/?shell=1
            17:54:48 [窗口] 非客户区接管已生效(收到第一条 WM_NCCALCSIZE)

        **窗口打开后一秒之内**就动了边框,而那正是 WebView2 还在初始化、
        还在算自己该多大的时候。业主答"打开就白"。
        0.92 同样早却没事 —— 因为它贴的三个位**不改变非客户区**。

        ⚠️ "时机撞车"是**假设**,不是结论。但挪晚这一下无论假设对不对都有收获:
        还白 ⇒ 是方案 B 和这套 WebView2 根本不兼容;好了 ⇒ 就是时机。

        安全位仍然要早贴:右键任务栏图标那个系统菜单、Win+方向键都归它们管,
        不早贴的话业主要点过一次缩小之后才有(0.92 就是为这个才挂在 shown 上的)。
        """
        self._on_ui(self._apply_safe_styles)

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

            # 🔴 每次都确保一遍,而不是只在开窗口时贴一次:pywebview 的 fullscreen
            #    那条路会改 `FormBorderStyle`,WinForms 会照 `CreateParams` 重算
            #    窗口样式 —— 我们贴的位会被**安静地刷掉**,而业主看到的是
            #    「有时有动画有时没有」。补位很便宜(贴过了就直接 return)。
            self._apply_native_styles_and_frame(form)
            form.WindowState = FormWindowState.Minimized
        self._on_ui(go)

    def toggle_maximize(self):
        """最大化/还原。**两条路,跟着实验开关走。**

        开关开(方案 B):**真**最大化 —— 系统知道发生了最大化,所以有放大动画,
        那正是业主点名的一半。溢出工作区的那一圈由 `_wndproc` 的
        `WM_NCCALCSIZE` 分支收回(`_fit_maximized_to_work_area`)。

        开关关(默认,0.92 的实现):自己算工作区设 `Bounds` 的"假最大化"。
        系统不知道发生了最大化 ⇒ **没有放大动画**,这是已知代价。
        🔴 为什么默认必须是这条:无边框窗口用真最大化会**连任务栏一起盖住**
        (`FormBorderStyle=None` 没有系统边框帮它留位置),而把那一圈收回来
        靠的正是方案 B 的接管 —— 0.93 真机证明接管这条路现在不能默认走。
        """
        def go(form):
            self._apply_native_styles_and_frame(form)
            if frame_animation_on():
                from System.Windows.Forms import FormWindowState

                if form.WindowState == FormWindowState.Maximized:
                    form.WindowState = FormWindowState.Normal
                    return False
                form.WindowState = FormWindowState.Maximized
                return True
            from System.Drawing import Rectangle

            if self._is_max(form) and self._restore:
                x, y, w, h = self._restore
                form.Bounds = Rectangle(x, y, w, h)
                return False
            self._restore = (form.Left, form.Top, form.Width, form.Height)
            area = self._work_area(form)
            form.Bounds = Rectangle(area.X, area.Y, area.Width, area.Height)
            return True
        return {"maximized": bool(self._on_ui(go))}

    def window_state(self):
        return {"maximized": bool(self._on_ui(self._is_max))}

    def close_window(self):
        """关 = 收进托盘,和以前点系统那个 × 一模一样(不是退出程序)。"""
        self._shell.state.on_close_requested()

    def report_startup(self, event: str, detail: str = ""):
        """前端报"我走到哪一步了"。**这是网页能写进日志的口子** ⇒ 当不可信输入处理。

        白名单 / 限长 / 去重全在 `ds_diag.report_from_ui` 里(判据 s7),
        这一层只负责把"首帧到了"这件事告诉看门狗、别让它误报。

        🔴 `frontend.frame_submitted` 只说明**浏览器提交了一帧**,不等于业主眼睛看见了
        —— 真实像素只有 Windows 那边的截图作得了准(双出那轮 GPT 把这条钉死的)。
        """
        accepted = DIAG.report_from_ui(str(event), str(detail))
        if event == "frontend.frame_submitted":
            self._shell.note_first_frame()
        return {"accepted": bool(accepted)}


class Shell:
    """把 core 的状态机接到 pywebview / pystray 上。"""

    def __init__(self, sup, web_port: int, lock: core.InstanceLock):
        self.sup = sup
        self.web_port = web_port
        self.lock = lock
        self.window = None
        self.icon = None
        # 窗口按钮走它,`shown` 那条线也要再叫它一次(贴系统样式位)⇒ 存一份,
        # 别在 main 里往实例上动态挂一个属性。
        self.window_api = WindowApi(self)
        self.state = core.ShellState(ui=self, on_stop=self.stop_backend)
        self._frame_watch = None

    # --- core.ShellState 要求的 UI 三件 -------------------------------
    # ⚠️ 这三个方法可能被**锁的监听线程**调到(第二次双击时)。pywebview 的
    # EdgeChromium 后端内部会把调用转到 UI 线程,但这一点我在 Linux 上验不了 ⇒
    # 已进 Windows 真机考卷(「开着的时候再双击一次图标」那一问)。
    def show_window(self):
        if not self.window:
            return
        # 🔴 先从最小化里捞出来,再 Show。pywebview 的 `show()` 是
        #    `Form.Show() + Activate()`,而 Activate 走的 `SetForegroundWindow`
        #    **对最小化的窗口不还原** ⇒ 业主点托盘图标、或再双击一次桌面图标,
        #    窗口都回不来(pywebview issue #1749 列的第三条,我们从没验过)。
        #    ⚠️ 2026-08-23(track opendesign-native-frame):这里原来写着
        #    「我们的最大化 WindowState 一直是 Normal ⇒ restore 幂等」——
        #    **D3 之后那句话不成立了**,最大化是真的,无条件 restore() 会把
        #    最大化的窗口打回小窗。所以先问一句它是不是真的最小化了。
        minimized = True
        try:
            from System.Windows.Forms import FormWindowState

            form = getattr(self.window, "native", None)
            if form is not None:
                minimized = (form.WindowState == FormWindowState.Minimized)
        except Exception as exc:
            # 读不到状态时**按最小化处理**:多还原一次顶多丢掉最大化状态,
            # 而漏还原会让窗口彻底回不来 —— 那才是 0.92 修掉的那个 bug。
            log(f"[窗口] 读不到窗口状态,按最小化处理:{exc.__class__.__name__}")
        if minimized:
            try:
                self.window.restore()
            except Exception as exc:
                log(f"[窗口] 从最小化还原失败,仍然试着 Show:{exc.__class__.__name__}")
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
            # 🔴 先把窗口过程还回去,再销毁窗口 —— 顺序反了的话,
            #    销毁过程中那几条消息会走进一个即将消失的 Python 回调。
            self.window_api.uninstall_wndproc()
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
    # --- 首帧看门 + 诊断导出 ------------------------------------------
    # 白屏那晚(0.98,08-25)我们手上一条线索都没有。这两件补的就是那笔账。

    FIRST_FRAME_TIMEOUT = 90.0
    """多少秒没等到前端画出第一帧,就写一次诊断快照。

    🔴 **这个数字不承重**(判据 s9):超时路径不弹框,定错了最多多写一段日志。
    取 90 是刻意取宽的 —— 已知唯一硬数据是云端冷启虚机 20~40 秒(08-25 分时段截图),
    **业主自己机器上要几秒,至今没有任何人量过**。等他发回第一份诊断包再谈收紧。
    """

    def start_first_frame_watch(self):
        self._frame_watch = ds_diag.FirstFrameWatch(
            timeout=self.FIRST_FRAME_TIMEOUT, on_timeout=self._first_frame_missing, emit=log)
        self._frame_watch.start()

    def note_first_frame(self):
        if self._frame_watch is not None:
            self._frame_watch.seen()

    def _first_frame_missing(self):
        """到点了前端还没报"我画出来了" ⇒ 把现场记下来。**不弹框。**

        🔴 不许在这里叫 `sup.poll_dead()` —— 它内部走 `take_dead()`,是**破坏性**的,
        问一次就把死因从名册里取走了,看门狗那边的弹窗就变成"原因是空的"
        (08-17 判据 c21 治的正是这个形状)。这里只看不碰。
        """
        log("[启动] 🔴 到点还没等到界面画出来 —— 下面是现场,不是报错弹窗。")
        for name, ms in DIAG.milestones():
            log(f"[启动]   已到达 +{ms:.0f}ms {name}")
        try:
            import urllib.request
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{self.web_port}/api/health", timeout=3) as r:
                log(f"[启动]   /api/health 通,HTTP {r.status}"
                    f" ⇒ 后端是活的,问题在网页那一层")
        except Exception as exc:
            log(f"[启动]   /api/health 不通:{exc!r} ⇒ 问题可能在后端")
        log(f"[启动]   右下角托盘 → 「导出本次启动诊断」可以把这些打包发出来。")

    def export_diagnostics(self):
        """托盘那一项。白屏时窗口是废的,**托盘还活着** —— 这是唯一还能操作的地方。"""
        try:
            out = _app_dir() / f"OpenDesign-诊断-{DIAG.run_id}.zip"
            DIAG.export_bundle(out, app_dir=_app_dir())
            log(f"[启动] 已导出诊断:{out}")
            # 复用既有的平台实现,别在这儿造第四种"打开文件夹"
            # (这个项目为同一个动作有过三种写法,已经统一到 ds_openfolder)。
            import ds_openfolder
            ds_openfolder._default_open_launcher(str(out.parent))
        except Exception as exc:
            log(f"[启动] 导出诊断失败:{exc!r}")
            alert(f"导出诊断没成功:{exc}\n\n日志在:\n{_log_path().parent}")

    def run_tray(self):
        import pystray

        menu = pystray.Menu(
            pystray.MenuItem("打开 OpenDesign", lambda *_: self.state.on_show(), default=True),
            # 白屏时业主唯一还点得动的地方 —— 一下打包,不用去文件夹里翻日志。
            pystray.MenuItem("导出本次启动诊断", lambda *_: self.export_diagnostics()),
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
    # 版本清单先写 —— 万一后面炸了,至少知道是哪一版、哪个内核上炸的。
    # (08-25 白屏那晚我们连内核版本都得靠业主去翻文件夹。)
    log(DIAG.manifest())
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
    DIAG.mark("lock.acquired")

    try:
        home = user_home()
        sup, web, restart_gateway = start_backend(home, lock_port=lock.port)
        DIAG.mark("backend.ready")
        restart_holder.append(restart_gateway)
        shell = Shell(sup, web, lock)
        shell_holder.append(shell)

        import webview

        shell.window = webview.create_window(
            # 地址带 SHELL_MARK = 外壳自报身份,前端第一帧就知道要画窗口栏
            # (window_url 是唯一来源,日志里印的也是它)。
            APP, window_url(web),
            width=1280, height=860, min_size=(960, 640),
            # 🔴 2026-08-16 业主:系统标题栏那个 "OpenDesign" 和我们前端自己的标题
            #    撞了 ⇒ 不要那个框,窗口按钮我们自己画在右上角(WindowChrome.tsx)。
            #    代价说清楚:frameless 之后 Windows 把"拖边缘改大小"也一起收走了,
            #    由 WindowApi 用原生窗口消息接回来。
            #    `easy_drag=False` 是关键:开着的话**整个页面**按哪儿都能拖窗口 ——
            #    选不了字、拖不动滚动条。拖动只认我们那条栏。
            frameless=True, easy_drag=False, js_api=shell.window_api,
        )
        # 关窗口 = 收进托盘。pywebview 的 closing 回调返回 False 表示"别关"。
        shell.window.events.closing += lambda: shell.state.on_close_requested()
        # 窗口一出来就把 frameless 拿走的那几个样式位贴回去(见
        # WindowApi._apply_native_styles)。挂 `shown` 而不是在这儿直接叫:
        # 这一刻窗口还没建出来,没有 Handle 可用。
        shell.window.events.shown += shell.window_api.ensure_native_styles
        # 🔴 2026-08-30(判据 s6):「窗口打开」这行原来写在 `webview.start()` **之前** ——
        #    它报的是"我要开了",不是"开了"。白屏那晚这行照样出现在日志里,
        #    于是它把"窗口真开了"这件根本没发生的事说成了既成事实。搬到 shown 里。
        shell.window.events.shown += lambda: DIAG.mark("window.shown")
        # 首帧看门:到点还没等到前端报"我画出来了",就写一次诊断快照。
        # **不弹框**(判据 s9)—— 阈值不承重,定错了最多多写一段日志。
        shell.window.events.shown += lambda: shell.start_first_frame_watch()

        shell.run_tray()
        shell.run_watchdog()
        DIAG.mark("window.create_returned", window_url(web))
        log(f"准备进入图形循环:{window_url(web)}")
        DIAG.mark("webview.loop_entered")
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
