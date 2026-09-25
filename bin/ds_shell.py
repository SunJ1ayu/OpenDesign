#!/usr/bin/env python3
"""OpenDesign 桌面外壳的**后台那一半**(track opendesign-electron-shell 起)。

2026-09-22 换 Electron:窗口、托盘、单实例、安装与更新都归 Electron 主进程(`desktop/`)。
这个文件只剩给管家 `bin/ds_host.py` 用的后台那一半:
  挑端口 → 改写配置 → 拉起网关和 ds-web → 读 key → 日志与诊断时间线。
窗口那一半(pywebview / pystray / WindowApi / 自绘窗口框架)随换壳退役,见 track 的判据迁移账。

这个文件仍守着原来的规矩:
  ① 每一步失败都要变成**业主看得懂的一句话**(`die()` / `alert()`)。
     换壳后这句话由管家接住、交给 Electron 弹框(同一个错只弹一个框);
     直接跑这个模块时照旧用 MessageBoxW 弹。
  ② 能判的逻辑都在 `ds_shell_core.py`,那一层有 `tests/test_ds_shell_core.py` 逐条锁着。
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ds_common  # noqa: E402
import ds_credential  # noqa: E402  变量名从配置的 apiKey 引用里读,不许写死
import ds_diag  # noqa: E402  启动可观测性:run_id / 分阶段耗时 / 诊断包
import ds_shell_core as core  # noqa: E402

APP = "OpenDesign"
# 锁位挑在一段不常用的高位端口上。它只是锁 + 唤醒通道,不承载数据。
LOCK_PORT = 18788
# 首选端口沿用现有部署(docs/install-windows.md / start.ps1),被占了会自动往后挪。
PREFERRED = {"gateway": 18790, "ws": 8765, "web": 8766}


# ---------------------------------------------------------------- 报错与日志
def _app_dir() -> Path:
    """这个软件在业主机器上自己的目录。日志和诊断包都住这儿。"""
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP


def _log_path() -> Path:
    d = _app_dir() / "Logs"
    d.mkdir(parents=True, exist_ok=True)
    return d / "外壳.log"


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


def web_ready_probe(port: int) -> bool:
    """工作台"就绪"的真正含义:`/api/health` 应答得了。

    🔴 **fail-closed**:任何异常都当成"还没就绪"。反过来写(拿不到就当好了)
    正是这个项目栽过的 fail-open 形状 —— 那样探针活着也等于没有。

    🔴 **绝不能走系统代理**(判据 s13;2026-08-30 四审孤腿 BLOCK 抓到、我实测坐实)。
    `urllib.request.urlopen` 对 127.0.0.1 **不绕过**代理:`proxy_bypass('127.0.0.1')`
    就是 False,而 Windows 上 `ProxyOverride` 里的 `<local>` 只匹配无点主机名。
    于是凡是配了系统代理的机器(公司代理、**以及 Clash 那类会设系统代理的 VPN 客户端**)
    上,这个探针对**健康**的工作台一律返回 False ⇒ `_wait_ready` 死等到 60s 超时
    ⇒ `StartupFailed` ⇒ **软件根本打不开**。
    观测层绝不能成为新的故障源 —— 这条红线是本单自己写的,第一版亲手违反了它。
    ⇒ 显式装一个空 `ProxyHandler`,任何环境里都直连。
    """
    import urllib.request
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(
                f"http://127.0.0.1:{int(port)}/api/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


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


# ---------------------------------------------------------------- 起后台
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
        # 🔴 第二家起的厂商(track opendesign-per-vendor-keys):配置里的额外条目与它们的 key
        #    **在这一处同时产生** —— prepare_gateway 写条目、返回 key,下面交给 service_envs。
        #    拆开的话「配置引用 ⊆ 网关手里的 key」就不再由结构保证,网关会悄悄用着旧厂商
        #    (真网关实验 p2)。它自己保证不抛:出错就退回只有主槽的样子。启动与重启都走这里。
        extra_keys = ds_credential.prepare_gateway(str(home), str(cfg))
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
            dsweb_port=web, ws_port=ws, key=key, key_var=key_var, lock_port=lock_port,
            extra_keys=extra_keys)

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
        # 经启动器起:网关每句前现读 key 文件 ⇒ 存 key 不用重启(track opendesign-key-restart)
        return core.Service(name="网关", argv=core.gateway_argv(str(python_exe()), str(install_root() / "ds")),
                            env=e, ready_port=ws, log_path=logs / "网关.log",
                            # 冷启动要连 3 个 MCP 子进程,S0 真机上见过接近 4 分钟
                            ready_timeout=300)

    def web_service(e):
        return core.Service(name="工作台", argv=[str(python_exe()),
                                                 str(install_root() / "ds" / "bin" / "ds_web.py")],
                            env=e, ready_port=web, log_path=logs / "工作台.log",
                            # 🔴 2026-08-30(判据 s11):就绪 = **它真的应答了**,
                            #    不是"端口有人监听"。`ready_probe` 这个机制一直都在,
                            #    只是工作台从没接上 ⇒ 时间线里的"后端就绪"是半真话,
                            #    而整条启动耗时都建在这句话上面。
                            ready_probe=web_ready_probe,
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
        """业主存完 key、ds-web 看到网关没在听 ⇒ 通过锁通道叫到这里。**只起没在跑的网关,活着的不碰。**

        网关现读 key 文件(bin/ds_gateway.py),在跑时存 key 不用它换进程 —— 09-25 业主真机的病
        正是「杀掉正在用的那个、新的没起来」(track opendesign-key-restart)。没在跑的情形:
        全新装机没 key ⇒ 开机只起了工作台,第一次存 key 从这里起网关。名字沿用锁通道的老动词。
        **现读**一遍 key 和配置(build_env)再起;界面那条腿一动不动 —— 他正看着的页面就是它发的。
        """
        k, fresh = build_env()      # fresh 是两条腿各自的 env,这里只起网关那条
        if not k:
            log("[起网关] 收到请求,但 key.txt 还是空的 —— 不动")
            return
        try:
            sup.ensure([gateway_service(fresh["网关"])])
            log("[起网关] 网关在跑")
        except Exception as exc:      # 回调跑在锁的线程里:炸出去会把那条线程带走
            log(f"[起网关] 失败:{exc}")
            alert(f"key 已经存好了,但后台没能自己启动:\n{exc}\n\n"
                  f"请退出 {APP} 再打开一次。")

    return sup, web, restart_gateway


# 🔴 模块体走完 = 所有 import 都办完了。这一条把"进程起来 → 拿到锁"那个
#    9.4 秒的黑块切开(判据 s17):云机器上它是全程最大的一块,而在 Linux 上
#    整条 import 链只要 130ms —— 差 70 倍,差的是 I/O 不是算力。
#    切开之后才知道到底是 import 慢、还是锁那一步慢。
DIAG.mark("shell.imports_done")
