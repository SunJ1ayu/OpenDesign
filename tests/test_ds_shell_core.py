#!/usr/bin/env python3
"""ds_shell_core 的 oracle —— 桌面外壳(S1b)那些**在 Linux 上验得了**的部分。

跑法:  python3 tests/test_ds_shell_core.py

## 为什么要有这个文件

外壳整体只能在 Windows 上跑(pywebview / pystray / WebView2 / .NET),而业主真机
每跑一趟都很贵(S0 用掉两趟、S1a 一趟)。所以设计上把外壳劈成两层:

  ds_shell_core.py  —— 平台无关的**逻辑**:端口选择、单实例锁与唤醒、子进程监管、
                        配置改写、子进程环境、窗口/托盘状态机。**本文件锁住它。**
  ds_shell.py       —— Windows 胶水:webview 开窗、pystray 托盘、Job 对象、错误提示。

劈开不是为了"好看",是为了**让真机那一趟只去回答真机才能回答的问题**。

## 这份考卷问得出什么、问不出什么(先说清楚,免得下次把它读过头)

问得出:上面六组逻辑,全用真 socket、真子进程、真文件,不打桩。
问不出:窗口长什么样、托盘图标点得动不动、WebView2 在不在、.NET 挂不挂得上、
        关窗真的会不会隐藏(F 组只锁**状态机**,不锁 pywebview 有没有把回调接对)。
        这些全部留给 Windows 考卷,别拿本文件的绿去替它们背书。
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_shell_core as core  # noqa: E402


def occupy(port: int = 0) -> tuple[socket.socket, int]:
    """占住一个回环端口并真的 listen(不是只 bind)——返回 (socket, 端口)。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", port))
    s.listen(8)
    return s, s.getsockname()[1]


def free_port() -> int:
    """借一个当下空闲的端口号(借完立刻还)。"""
    s, p = occupy(0)
    s.close()
    return p


# =========================================================== A 端口选择
class PickPort(unittest.TestCase):
    def test_a1_preferred_when_free(self):
        p = free_port()
        self.assertEqual(core.pick_port(p, span=5), p)

    def test_a2_moves_off_a_busy_port(self):
        busy, p = occupy()
        self.addCleanup(busy.close)
        got = core.pick_port(p, span=10)
        self.assertNotEqual(got, p, "首选端口被占,却还是把它返回了")
        self.assertTrue(p < got <= p + 10, f"换到了段外:{got}")

    def test_a3_whole_span_busy_fails_loudly(self):
        """全段被占 ⇒ 必须抛人话异常,不许静默返回 0 / 随机端口。

        静默降级正是 S0/S1a 反复栽的那种病(pip 丢依赖不报错、.gitignore 吞证据不报错):
        **失败没有声音**。
        """
        base = free_port()
        held = []
        for i in range(4):
            try:
                s, _ = occupy(base + i)
                held.append(s)
            except OSError:
                self.skipTest(f"借不到连续端口段 {base}..{base + 3}")
        for s in held:
            self.addCleanup(s.close)
        with self.assertRaises(core.PortBusy) as cm:
            core.pick_port(base, span=3)
        self.assertIn(str(base), str(cm.exception), "报错里没说是哪个端口段,业主看不懂")

    def test_a4_returned_port_is_actually_bindable(self):
        """焊点:探测"看着空"和"绑得住"是两件事。选完必须当场绑一次证明。"""
        p = core.pick_port(free_port(), span=10)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(s.close)
        s.bind(("127.0.0.1", p))  # 绑不上就是红


# =========================================================== B 单实例 + 唤醒
class SingleInstance(unittest.TestCase):
    def test_b1_first_instance_acquires(self):
        base = free_port()
        lock = core.InstanceLock(base_port=base, span=5)
        self.addCleanup(lock.release)
        self.assertTrue(lock.acquire(), "第一个实例居然没拿到锁")

    def test_b2_second_instance_is_refused_and_wakes_the_first(self):
        base = free_port()
        woken = []
        first = core.InstanceLock(base_port=base, span=5, on_show=lambda: woken.append(1))
        self.addCleanup(first.release)
        self.assertTrue(first.acquire())

        second = core.InstanceLock(base_port=base, span=5)
        self.addCleanup(second.release)
        self.assertFalse(second.acquire(), "第二次双击又起了一份 ⇒ 单实例没做到")

        deadline = time.time() + 5
        while not woken and time.time() < deadline:
            time.sleep(0.05)
        self.assertTrue(woken, "第二个实例退了,但没把已有窗口叫到前台 ⇒ 业主会以为程序坏了")

    def test_b3_a_stranger_on_the_port_is_not_mistaken_for_us(self):
        """陌生程序占了锁位 ⇒ 不许误判成"已有实例"而拒绝启动。

        没有这一条,业主机器上随便哪个程序占了那个端口,OpenDesign 就再也打不开,
        而且报错会是"已经在运行了"——最难查的那种。握手就是为了分清这两件事。
        """
        stranger, base = occupy()
        self.addCleanup(stranger.close)
        lock = core.InstanceLock(base_port=base, span=5)
        self.addCleanup(lock.release)
        self.assertTrue(lock.acquire(), "被陌生程序占了锁位就打不开了")
        self.assertNotEqual(lock.port, base)

    def test_b4_lock_is_released_on_exit(self):
        base = free_port()
        first = core.InstanceLock(base_port=base, span=5)
        self.assertTrue(first.acquire())
        first.release()
        second = core.InstanceLock(base_port=base, span=5)
        self.addCleanup(second.release)
        self.assertTrue(second.acquire(), "上一个实例退了,锁没放开")
        self.assertEqual(second.port, base, "锁放开了却没回到首选锁位")

    def test_b5_lock_socket_must_not_be_stealable(self):
        """焊点(只在 Linux 上问得出、但防的是 Windows 的坑)。

        Windows 上 SO_REUSEADDR 的语义和 Linux **不一样**:它允许后来者**抢走**一个
        正在 listen 的端口 ⇒ 单实例锁会被直接偷掉,两份 OpenDesign 同时在跑。
        所以这把锁的 socket 一律不许开 SO_REUSEADDR(Windows 侧应改用
        SO_EXCLUSIVEADDRUSE,那条只有真机验得了)。
        """
        base = free_port()
        lock = core.InstanceLock(base_port=base, span=5)
        self.addCleanup(lock.release)
        self.assertTrue(lock.acquire())
        opt = lock._sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
        self.assertEqual(opt, 0, "锁 socket 开了 SO_REUSEADDR ⇒ Windows 上这把锁能被偷")


# =========================================================== C 子进程监管
def py_child(code: str) -> list[str]:
    return [sys.executable, "-c", code]


BIND_AND_WAIT = (
    "import socket,sys,time\n"
    "s=socket.socket();s.bind(('127.0.0.1',int(sys.argv[1])));s.listen(4)\n"
    "print('listening',flush=True)\n"
    "time.sleep(300)\n"
)


class Supervise(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.sup = core.Supervisor()
        self.addCleanup(self.sup.shutdown)

    def svc(self, name, code, port, timeout=20, args=()):
        return core.Service(
            name=name,
            argv=py_child(code) + [str(port)] + list(args),
            env=dict(os.environ),
            ready_port=port,
            log_path=self.dir / f"{name}.log",
            ready_timeout=timeout,
        )

    def test_c1_started_children_are_really_killed(self):
        port = free_port()
        self.sup.start([self.svc("legA", BIND_AND_WAIT, port)])
        self.assertTrue(core.port_listening(port), "说就绪了,端口却没人听")
        self.sup.shutdown()
        self.assertFalse(core.port_listening(port), "shutdown 之后端口还有人听 ⇒ 子进程没收干净")

    def test_c2_a_child_that_dies_is_reported_fast_and_readably(self):
        """子进程自己崩了 ⇒ 立刻报"谁崩了 / 退出码 / 日志尾巴",不许傻等到超时。"""
        port = free_port()
        code = "import sys;print('炸了:配置文件读不出来',flush=True);sys.exit(3)"
        t0 = time.time()
        with self.assertRaises(core.StartupFailed) as cm:
            self.sup.start([self.svc("legB", code, port, timeout=25)])
        took = time.time() - t0
        self.assertLess(took, 15, f"等了 {took:.1f}s 才报 ⇒ 没在盯进程死活,只在数秒")
        msg = str(cm.exception)
        self.assertIn("legB", msg, "报错没说是哪条腿")
        self.assertIn("3", msg, "报错没带退出码")
        self.assertIn("炸了:配置文件读不出来", msg, "报错没带日志尾巴,业主拿不到线索")

    def test_c3_readiness_waits_for_the_port_not_a_sleep(self):
        port = free_port()
        code = "import socket,sys,time\ntime.sleep(1.5)\n" + BIND_AND_WAIT
        self.sup.start([self.svc("legC", code, port)])
        self.assertTrue(core.port_listening(port))

    def test_c4_timeout_carries_the_log_tail(self):
        port = free_port()
        code = "import sys,time;print('我起来了但就是不开端口',flush=True);time.sleep(60)"
        with self.assertRaises(core.StartupFailed) as cm:
            self.sup.start([self.svc("legD", code, port, timeout=3)])
        self.assertIn("我起来了但就是不开端口", str(cm.exception))

    def test_c5_shutdown_is_idempotent(self):
        port = free_port()
        self.sup.start([self.svc("legE", BIND_AND_WAIT, port)])
        self.sup.shutdown()
        self.sup.shutdown()  # 再来一次不许炸(托盘退出 + 进程退出会各调一次)

    def test_c6_a_failed_start_takes_its_siblings_down_with_it(self):
        """第二条腿起不来 ⇒ 已经起好的第一条腿必须一起收掉。

        否则业主会得到一个"看着没开、其实后台有个孤儿在听 8766"的机器,
        下次再打开就撞端口 —— 这是最难自愈的一种残局。
        """
        good, bad = free_port(), free_port()
        with self.assertRaises(core.StartupFailed):
            self.sup.start([
                self.svc("好腿", BIND_AND_WAIT, good),
                self.svc("坏腿", "import sys;sys.exit(9)", bad, timeout=10),
            ])
        self.assertFalse(core.port_listening(good), "起失败了,先起好的那条腿变成孤儿进程")

    def test_c7_poll_dead_names_the_leg_that_died(self):
        port = free_port()
        code = "import socket,sys,time\n" + BIND_AND_WAIT.replace("time.sleep(300)", "time.sleep(1.0)")
        self.sup.start([self.svc("短命腿", code, port)])
        self.assertEqual(self.sup.poll_dead(), [], "刚起来就说死了")
        deadline = time.time() + 10
        while time.time() < deadline and not self.sup.poll_dead():
            time.sleep(0.2)
        self.assertEqual(self.sup.poll_dead(), ["短命腿"], "腿死了没人发现 ⇒ 界面会一直转圈")


# =========================================================== D 配置改写
BASE_CFG = {
    "providers": {"custom": {"apiKey": "${DS_LLM_KEY}", "apiBase": "https://example/v1"}},
    "agents": {"defaults": {"modelPreset": "mimo-v2.5"}},
    "tools": {
        "file": {"enable": False},
        "exec": {"enable": False},
        "mcpServers": {
            "design-studio": {"command": "${USERPROFILE}/.venvs/x/Scripts/python.exe",
                              "args": ["a.py"]},
            "ds-refs": {"command": "${USERPROFILE}/.venvs/x/Scripts/python.exe",
                        "args": ["b.py"]},
        },
    },
}


class PatchConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = Path(self.tmp.name) / "config.json"
        self.cfg.write_text(json.dumps(BASE_CFG, ensure_ascii=False, indent=2), encoding="utf-8")

    def patched(self, **kw):
        kw.setdefault("gateway_port", 18790)
        kw.setdefault("ws_port", 8765)
        kw.setdefault("python_exe", r"C:\OD\python\python.exe")
        core.patch_config(self.cfg, **kw)
        return json.loads(self.cfg.read_text(encoding="utf-8"))

    def test_d1_ports_are_written(self):
        d = self.patched(gateway_port=18801, ws_port=18802)
        self.assertEqual(d["gateway"]["port"], 18801)
        self.assertEqual(d["channels"]["websocket"]["port"], 18802)

    def test_d2_every_mcp_command_points_into_the_package(self):
        exe = r"C:\OD\python\python.exe"
        d = self.patched(python_exe=exe)
        cmds = {n: s["command"] for n, s in d["tools"]["mcpServers"].items()}
        self.assertEqual(set(cmds.values()), {exe}, f"还有 MCP 指着机器上别的 python:{cmds}")
        self.assertEqual(len(cmds), 2, "改写时把某个 MCP 弄丢了")

    def test_d3_nothing_else_is_lost(self):
        """焊点:防"整份重写"式实现 —— 那会把 key 引用、关掉的内置工具一起冲掉,
        而 tools.exec.enable=false 是 deploy-security 那条"物理绕不过"的承重墙。
        """
        d = self.patched()
        self.assertEqual(d["providers"]["custom"]["apiKey"], "${DS_LLM_KEY}")
        self.assertIs(d["tools"]["exec"]["enable"], False)
        self.assertIs(d["tools"]["file"]["enable"], False)
        self.assertEqual(d["agents"]["defaults"]["modelPreset"], "mimo-v2.5")
        self.assertEqual(d["tools"]["mcpServers"]["ds-refs"]["args"], ["b.py"])

    def test_d4_is_idempotent(self):
        once = self.patched()
        twice = self.patched()
        self.assertEqual(once, twice, "跑两遍结果不一样 ⇒ 每次启动都会把配置改一点")


# =========================================================== E 子进程环境
class ChildEnv(unittest.TestCase):
    def env(self, **kw):
        kw.setdefault("base_env", {"PATH": "/usr/bin", "PYTHONPATH": "/机器上别人的路径"})
        kw.setdefault("ds_root", r"C:\OD\ds")
        kw.setdefault("dsweb_port", 8766)
        kw.setdefault("ws_port", 8765)
        return core.child_env(**kw)

    def test_e1_dsweb_talks_to_the_websocket_port_not_the_gateway_port(self):
        """🔴 这一条来自读代码时抓到的真坑。

        ds_web.py:2266 把 DS_NANOBOT_PORT 当作**聊天代理的上游**,默认 8765 ——
        那是 channels.websocket.port,**不是** gateway.port(18790)。
        S0 探路包里两者被设成了同一个值(网关 18795 / 通道 18797,DS_NANOBOT_PORT=18795),
        它没红只是因为那趟根本没点开聊天。外壳要是照抄,业主装完第一句话就发不出去。
        """
        e = self.env(dsweb_port=18796, ws_port=18797)
        self.assertEqual(e["DS_WEB_PORT"], "18796")
        self.assertEqual(e["DS_NANOBOT_PORT"], "18797")

    def test_e2_host_pythonpath_does_not_leak_in(self):
        """业主机器上很可能本来就装着 Python。PYTHONPATH 漏进来 ⇒ 包内 Python 会去
        加载机器上那套包,而且**多半还能跑**——最难看的那种假绿(S0 焊点2 同源)。"""
        self.assertNotIn("PYTHONPATH", self.env())

    def test_e3_ds_root_points_into_the_package(self):
        self.assertEqual(self.env(ds_root=r"C:\OD\ds")["DS_ROOT"], r"C:\OD\ds")

    def test_e4_key_is_passed_only_when_there_is_one(self):
        self.assertNotIn("DS_LLM_KEY", self.env(key=None))
        self.assertNotIn("DS_LLM_KEY", self.env(key=""))
        self.assertEqual(self.env(key="sk-abc")["DS_LLM_KEY"], "sk-abc")

    def test_e5_every_value_is_a_string(self):
        """焊点:env 里混进 int,subprocess 在 Windows 上会直接 TypeError ——
        而这份代码的所有真跑都在 Windows。"""
        bad = [k for k, v in self.env().items() if not isinstance(v, str)]
        self.assertEqual(bad, [])


# =========================================================== F 窗口/托盘状态机
class FakeUI:
    """替身 UI:只记账,不画东西。锁的是"外壳该做什么",不是"pywebview 怎么做"。"""

    def __init__(self):
        self.calls = []

    def show_window(self):
        self.calls.append("show")

    def hide_window(self):
        self.calls.append("hide")

    def destroy(self):
        self.calls.append("destroy")


class ShellState(unittest.TestCase):
    def setUp(self):
        self.ui = FakeUI()
        self.stopped = []
        self.st = core.ShellState(ui=self.ui, on_stop=lambda: self.stopped.append(1))

    def test_f1_closing_the_window_hides_instead_of_quitting(self):
        """业主明确要的常驻式(像 openclaw):关窗口 ≠ 退出。"""
        allow_close = self.st.on_close_requested()
        self.assertFalse(allow_close, "关窗口把整个程序退了 ⇒ 后台聊天/提醒全断")
        self.assertIn("hide", self.ui.calls)
        self.assertEqual(self.stopped, [], "关个窗口就把两个服务收了")
        self.assertFalse(self.st.exiting)

    def test_f2_tray_open_shows_it_again(self):
        self.st.on_close_requested()
        self.st.on_show()
        self.assertEqual(self.ui.calls[-1], "show")
        self.assertTrue(self.st.visible)

    def test_f3_tray_quit_is_the_only_real_exit(self):
        self.st.on_quit()
        self.assertTrue(self.st.exiting)
        self.assertEqual(self.stopped, [1], "托盘退出没有收掉后台服务 ⇒ 留下孤儿进程")
        self.assertIn("destroy", self.ui.calls)

    def test_f4_second_launch_raises_a_hidden_window(self):
        self.st.on_close_requested()
        self.assertFalse(self.st.visible)
        self.st.on_show()  # ← InstanceLock 收到 SHOW 时走的就是这条路
        self.assertTrue(self.st.visible)

    def test_f5_quit_is_idempotent(self):
        self.st.on_quit()
        self.st.on_quit()
        self.assertEqual(self.stopped, [1], "退出走了两遍 ⇒ 收服务的动作被重复执行")

    def test_f6_close_after_quit_does_not_resurrect(self):
        """退出过程中 pywebview 还会再发一次 closing ⇒ 那一次必须放行,否则关不掉。"""
        self.st.on_quit()
        self.assertTrue(self.st.on_close_requested(), "已经在退出了,还拦着不让关 ⇒ 窗口关不掉")


# =========================================================== G 真后端联跑
class RealBackend(unittest.TestCase):
    """用外壳**自己那套**监管 + env,真把 ds-web 起起来,让它自己报版本号。

    为什么值得写:S1a 的外壳考卷故意只喂自带 HTML,"外壳 + 真实后端"这个组合到现在
    没跑过一次。窗口那半只有 Windows 验得了,但**监管/env/端口这半在 Linux 上就能验**,
    而且这半才是最容易接错线的地方(见 E1 那个 DS_NANOBOT_PORT 的坑)。
    "在使用现场验证":让运行中的目标自己打印版本,不看我怎么想。
    """

    def test_g1_ds_web_comes_up_under_the_shell_supervisor(self):
        import re
        import urllib.request

        ds_web = Path(ROOT) / "bin" / "ds_web.py"
        version = re.search(r'^VERSION\s*=\s*"([^"]+)"',
                            ds_web.read_text(encoding="utf-8"), re.M).group(1)
        port = core.pick_port(free_port(), span=10)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        sup = core.Supervisor()
        self.addCleanup(sup.shutdown)

        sup.start([core.Service(
            name="ds-web",
            argv=[sys.executable, str(ds_web)],
            env=core.child_env(base_env=dict(os.environ), ds_root=str(Path(ROOT) / "workspace"),
                               dsweb_port=port, ws_port=free_port()),
            ready_port=port,
            log_path=Path(tmp.name) / "ds-web.log",
            ready_timeout=40,
        )])
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=10) as r:
            health = json.loads(r.read().decode("utf-8"))
        self.assertEqual(health.get("version"), version,
                         f"起来的这个 ds-web 自报 {health.get('version')!r},"
                         f"而仓库里是 {version!r} ⇒ 跑的不是我们这一份")
        sup.shutdown()
        self.assertFalse(core.port_listening(port), "外壳收摊后 ds-web 还在听端口")


if __name__ == "__main__":
    unittest.main(verbosity=2)
