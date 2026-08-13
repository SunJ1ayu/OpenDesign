#!/usr/bin/env python3
"""ds_shell_core 的 oracle —— 桌面外壳(S1b)那些**在 Linux 上验得了**的部分。

跑法:  python3 tests/test_ds_shell_core.py
       DS_SHELL_E2E=1 python3 tests/test_ds_shell_core.py   # 连 G2 两腿真联跑也跑

## 为什么要有这个文件

外壳整体只能在 Windows 上跑(pywebview / pystray / WebView2 / .NET),而业主真机
每跑一趟都很贵(S0 用掉两趟、S1a 一趟)。所以设计上把外壳劈成两层:

  ds_shell_core.py  —— 平台无关的**逻辑**:端口选择、单实例锁与唤醒、子进程监管、
                        配置改写、子进程环境、窗口/托盘状态机。**本文件锁住它。**
  ds_shell.py       —— Windows 胶水:webview 开窗、pystray 托盘、Job 对象、错误提示。

劈开不是为了"好看",是为了**让真机那一趟只去回答真机才能回答的问题**。

## 这份考卷问得出什么、问不出什么(先说清楚,免得下次把它读过头)

问得出:上面六组逻辑,全用真 socket、真子进程、真文件、**真的第二个解释器**,不打桩。
问不出:窗口长什么样、托盘点得动不动、WebView2 在不在、.NET 挂不挂得上、
        Job 对象有没有真收掉整棵进程树(Linux 这边验的是 POSIX 进程组那条路)、
        pywebview 有没有把 closing 回调接到 ShellState 上。
        这些全部留给 Windows 考卷,**别拿本文件的绿去替它们背书**。

## 这份考卷被攻过一轮(2026-08-13,gpt-5.6-sol 只读)

第一版写完先请第三方攻「哪条断言全绿了结果外壳仍然是坏的」,13 条里 11 条 HIGH,
基本条条成立,其中两条是我自己写错的:G1 把 nanobot 的 workspace 当成了 DS 数据根;
B5 断言名(「不可偷」)比它实际问的(SO_REUSEADDR==0)强 —— 与 S1a 那处 overclaim 同病。
本版是攻完之后的。攻题记录:/root/aiwork/attack-logs/s1b-attack-stdout.txt(仓外不承重)
"""
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
sys.path.insert(0, BIN)
import ds_shell_core as core  # noqa: E402


def listen_on(port: int = 0) -> tuple[socket.socket, int]:
    """占住一个回环端口并真的 listen —— 返回 (socket, 端口)。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", port))
    s.listen(8)
    return s, s.getsockname()[1]


def bind_only(port: int) -> socket.socket:
    """只 bind、**不** listen —— 攻题第 1 条:拿 connect 探端口的实现会把这种占用看成空。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", port))
    return s


def free_port() -> int:
    s, p = listen_on(0)
    s.close()
    return p


# =========================================================== A 端口选择
class PickPort(unittest.TestCase):
    def test_a1_preferred_when_free(self):
        p = free_port()
        self.assertEqual(core.pick_port(p, span=5), p)

    def test_a2_moves_off_a_busy_port(self):
        busy, p = listen_on()
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
                s, _ = listen_on(base + i)
                held.append(s)
            except OSError:
                self.skipTest(f"借不到连续端口段 {base}..{base + 3}")
        for s in held:
            self.addCleanup(s.close)
        with self.assertRaises(core.PortBusy) as cm:
            core.pick_port(base, span=3)
        self.assertIn(str(base), str(cm.exception), "报错里没说是哪个端口段,业主看不懂")

    def test_a4_returned_port_is_actually_bindable(self):
        """焊点:探测"看着空"和"绑得住"是两件事。"""
        p = core.pick_port(free_port(), span=10)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(s.close)
        s.bind(("127.0.0.1", p))  # 绑不上就是红

    def test_a5_a_bound_but_not_listening_port_counts_as_busy(self):
        """攻题 HIGH#1:只用 connect 探测的实现,会把"已 bind 未 listen"看成空端口,
        于是两条腿拿到同一个端口 —— 而第二条腿起不来时业主只看到"打不开"。
        判"空"必须用 bind 亲自试,不许用 connect 猜。
        """
        p = free_port()
        holder = bind_only(p)
        self.addCleanup(holder.close)
        self.assertFalse(core.port_free(p), "已 bind 未 listen 的端口被判成了空")
        self.assertNotEqual(core.pick_port(p, span=10), p)

    def test_a6_group_allocation_never_hands_out_the_same_port_twice(self):
        """攻题 HIGH#1 的第二条路线:网关 / 通道 / ds-web 三个端口是**分别**挑的,
        首选端口一撞车,两条腿就会被发到同一个号上。必须成组分配。
        """
        a, b = free_port(), free_port()
        busy, _ = listen_on(a)
        self.addCleanup(busy.close)
        got = core.pick_ports([a, b, a + 1], span=10)
        self.assertEqual(len(set(got)), 3, f"成组分配发出了重复端口:{got}")
        self.assertNotIn(a, got, "被占的首选端口还是被发了出去")
        socks = []
        for p in got:  # 焊点:发出来的每一个都要当场绑得住
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", p))
            socks.append(s)
        for s in socks:
            s.close()


# =========================================================== B 单实例 + 唤醒
LOCK_CHILD = r"""
import json, os, sys, time
sys.path.insert(0, sys.argv[1])
import ds_shell_core as core
marker = sys.argv[4]
# argv[5] 是"发令枪":两个实例都先在这里等,等文件出现才一起冲 ——
# 没有它,Popen 是一前一后起的,永远撞不出并发那个窗口(=靠运气的绿)。
if len(sys.argv) > 5:
    while not os.path.exists(sys.argv[5]):
        time.sleep(0.002)
lock = core.InstanceLock(base_port=int(sys.argv[2]), span=int(sys.argv[3]),
                         on_show=lambda: open(marker, "w").write("SHOWN"))
got = lock.acquire()
print(json.dumps({"acquired": got, "port": lock.port}), flush=True)
if not got:
    sys.exit(0)
time.sleep(120)
"""


class SingleInstance(unittest.TestCase):
    """攻题 HIGH#2:第一个实例必须是**真的另一个解释器**。

    同进程里造两个 InstanceLock,一个"把 on_show 存进模块全局表"的假实现就能全绿,
    而真机上第二次双击是另一个 exe、看不到那张表 ⇒ 会老老实实再开一份。
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.marker = Path(self.tmp.name) / "shown.txt"

    def reap(self, p):
        p.kill()
        p.wait(timeout=10)
        for f in (p.stdout, p.stderr):
            if f:
                f.close()

    def start_first(self, base, span=5):
        p = subprocess.Popen([sys.executable, "-c", LOCK_CHILD, BIN, str(base), str(span),
                              str(self.marker)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.reap, p)
        line = p.stdout.readline()
        # ⚠️ 别写成 assertTrue(line, f"...{p.stderr.read()}") —— 消息串是**先算后传**的,
        # 而 stderr.read() 要等子进程关掉管道才返回 ⇒ 每条用例白等到子进程 sleep 完。
        # 2026-08-13 第一次跑就栽在这:整份考卷卡死在 b 组,看着像实现挂了,其实是考卷自己。
        if not line.strip():
            self.fail(f"第一个实例没吭声就退了;stderr={p.stderr.read()[:800]}")
        return p, json.loads(line)

    def test_b1_first_instance_acquires(self):
        _, r = self.start_first(free_port())
        self.assertTrue(r["acquired"], "第一个实例居然没拿到锁")

    def test_b2_second_instance_is_refused_and_wakes_the_first(self):
        base = free_port()
        _, r = self.start_first(base)
        self.assertTrue(r["acquired"])

        second = core.InstanceLock(base_port=base, span=5)
        self.addCleanup(second.release)
        self.assertFalse(second.acquire(), "第二次双击又起了一份 ⇒ 单实例没做到")

        deadline = time.time() + 8
        while not self.marker.exists() and time.time() < deadline:
            time.sleep(0.05)
        self.assertTrue(self.marker.exists(),
                        "第二个实例退了,但没把已有窗口叫到前台 ⇒ 业主会以为程序坏了")

    def test_b3_a_stranger_on_the_port_is_not_mistaken_for_us(self):
        """陌生程序占了锁位 ⇒ 不许误判成"已有实例"而拒绝启动。

        没有这一条,业主机器上随便哪个程序占了那个端口,OpenDesign 就再也打不开,
        报错还会是"已经在运行了"—— 最难查的那种。握手就是为了分清这两件事。
        """
        stranger, base = listen_on()
        self.addCleanup(stranger.close)
        _, r = self.start_first(base)
        self.assertTrue(r["acquired"], "被陌生程序占了锁位就打不开了")
        self.assertNotEqual(r["port"], base)

    def test_b4_second_instance_finds_the_first_even_on_a_fallback_slot(self):
        """攻题 HIGH#2 的第二条路线:陌生程序占了 base,第一份落在 base+1;
        第二份如果只对 base 握手、失败就去绑 base+2,**两份就并存了**。
        第二份必须把整段扫完才允许认为"没有别人"。
        """
        stranger, base = listen_on()
        self.addCleanup(stranger.close)
        _, r = self.start_first(base)
        self.assertTrue(r["acquired"])
        # 落在段内哪一格无所谓(那格也可能被机器上别的程序占着);要紧的是它没落在 base
        self.assertTrue(base < r["port"] <= base + 5, f"第一份落在段外:{r['port']}")

        second = core.InstanceLock(base_port=base, span=5)
        self.addCleanup(second.release)
        self.assertFalse(second.acquire(),
                         "第一份在备用锁位上,第二份没找到它 ⇒ 两份 OpenDesign 并存")
        deadline = time.time() + 8
        while not self.marker.exists() and time.time() < deadline:
            time.sleep(0.05)
        self.assertTrue(self.marker.exists(), "备用锁位上的实例没被叫到前台")

    def test_b5_lock_is_released_on_exit(self):
        base = free_port()
        first = core.InstanceLock(base_port=base, span=5)
        self.assertTrue(first.acquire())
        first.release()
        second = core.InstanceLock(base_port=base, span=5)
        self.addCleanup(second.release)
        self.assertTrue(second.acquire(), "上一个实例退了,锁没放开")
        self.assertEqual(second.port, base, "锁放开了却没回到首选锁位")

    def test_b6_lock_socket_does_not_set_so_reuseaddr(self):
        """断言名只说它问得出的那件事(攻题 HIGH#3 把上一版的 overclaim 揪出来了)。

        Windows 上 SO_REUSEADDR 允许后来者**抢走**一个正在 listen 的端口 ⇒ 锁会被偷。
        这里只能证明"没开 SO_REUSEADDR",证明不了"Windows 上偷不走"——后者见 b7 与真机考卷。
        """
        base = free_port()
        lock = core.InstanceLock(base_port=base, span=5)
        self.addCleanup(lock.release)
        self.assertTrue(lock.acquire())
        self.assertEqual(lock._sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR), 0,
                         "锁 socket 开了 SO_REUSEADDR ⇒ Windows 上这把锁能被偷")

    def test_b8_two_instances_racing_at_the_same_moment_still_yield_one(self):
        """🔴 攻题二轮 HIGH#1:业主快速双击两下,两个实例**同时**起来。

        b2/b4 都是"等第一份完全监听好了才起第二份",漏掉的正是双击最典型的那个窗口:
        两份都先扫完整段、都认定"没有旧的",然后一个绑 base、一个绑 base+1,
        **两份都以为自己是唯一的**。真机上就是两个窗口、两套后台、抢同一批端口。
        """
        for round_no in range(6):     # 竞态要多打几遍才现形,单次绿说明不了什么
            base = free_port()
            go = self.marker.parent / f"发令枪{round_no}"
            procs = [subprocess.Popen(
                [sys.executable, "-c", LOCK_CHILD, BIN, str(base), "5",
                 str(self.marker.parent / f"shown{round_no}-{i}.txt"), str(go)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(2)]
            for p in procs:
                self.addCleanup(self.reap, p)
            time.sleep(0.3)           # 让两个解释器都起好、都堵在发令枪前
            go.write_text("go", encoding="utf-8")
            got = []
            for p in procs:
                line = p.stdout.readline()
                if not line.strip():
                    self.fail(f"实例没吭声就退了;stderr={p.stderr.read()[:500]}")
                got.append(json.loads(line))
            winners = [r for r in got if r["acquired"]]
            self.assertEqual(len(winners), 1,
                             f"第 {round_no} 轮同时起两份,{len(winners)} 份都认为自己是唯一实例:{got}")

    def test_b9_a_silent_client_cannot_wedge_the_lock(self):
        """攻题二轮 HIGH#2:端口扫描器(或任何连上就不说话的东西)连住锁位。

        如果服务端是单线程、且要为这个哑巴客户端阻塞 1 秒,而第二实例只等 0.35 秒 ⇒
        第二实例会**握手假失败**,把真实例当成陌生人,自己另占一格 ⇒ 两份并存。
        """
        base = free_port()
        first = core.InstanceLock(base_port=base, span=5, on_show=lambda: None)
        self.addCleanup(first.release)
        self.assertTrue(first.acquire())

        mute = socket.create_connection(("127.0.0.1", first.port), timeout=5)
        self.addCleanup(mute.close)
        time.sleep(0.2)  # 让服务端确实收下这条连接

        second = core.InstanceLock(base_port=base, span=5)
        self.addCleanup(second.release)
        self.assertFalse(second.acquire(),
                         "一个连上不说话的客户端就把锁堵住了 ⇒ 会开出第二份 OpenDesign")

    def test_b10_a_handshake_split_across_packets_is_still_recognised(self):
        """TCP 没有消息边界。握手被拆成两个包发,服务端若只 recv 一次就会认不出来 ——
        本机回环上很难拆包,所以这里**手动拆**,把这条路走一遍。"""
        base = free_port()
        woken = threading.Event()
        lock = core.InstanceLock(base_port=base, span=5, on_show=woken.set)
        self.addCleanup(lock.release)
        self.assertTrue(lock.acquire())

        with socket.create_connection(("127.0.0.1", lock.port), timeout=5) as s:
            s.settimeout(5)
            s.sendall(core.InstanceLock._HELLO[:10])
            time.sleep(0.15)
            s.sendall(core.InstanceLock._HELLO[10:] + core.InstanceLock._SHOW)
            self.assertEqual(s.recv(32), core.InstanceLock._OK, "分片握手没被认出来")
        self.assertTrue(woken.wait(5), "分片握手回了 OK,却没把窗口叫到前台")

    def test_b7_windows_branch_asks_for_exclusive_bind(self):
        """Windows 那条分支在 Linux 上跑不了,但"它打算设哪些 socket 选项"是纯数据,
        问得出来 —— 把"我以为它会设"变成一条会红的断言。
        真正的"抢不走"仍然只有 Windows 真机验得了(已进真机考卷)。
        """
        opts = core.lock_sockopts("win32")
        self.assertIn("SO_EXCLUSIVEADDRUSE", [name for name, _ in opts],
                      "Windows 分支没有申请独占绑定 ⇒ 单实例锁在真机上可能被抢走")
        self.assertEqual(core.lock_sockopts("linux"), [],
                         "非 Windows 平台不该乱设选项(SO_REUSEADDR 尤其不许)")


# =========================================================== C 子进程监管
BIND_AND_WAIT = (
    "import socket,sys,time\n"
    "s=socket.socket();s.bind(('127.0.0.1',int(sys.argv[1])));s.listen(4)\n"
    "print('listening',flush=True)\n"
    "time.sleep(300)\n"
)

# 孩子再生一个孙子,孙子占着哨兵端口 —— nanobot 就是这个形状(它自己拉起 3 个 MCP)。
#   %(sentinel)s = 孙子占的哨兵端口   %(live)s = **父进程**自己活多久
# ⚠️ 别用 str.replace 去改这里的 sleep:"time.sleep(300)" 在这段里出现两次
# (一次是孙子的、一次是父亲的),replace 会**两个一起改** ⇒ 孙子自己死掉,
# "孙进程有没有被收干净"那条考卷就变成了假绿。2026-08-13 我真写出过这个 bug。
SPAWN_GRANDCHILD = (
    "import socket,subprocess,sys,time\n"
    "g=subprocess.Popen([sys.executable,'-c',"
    "\"import socket,time;s=socket.socket();s.bind(('127.0.0.1',%(sentinel)s));"
    "s.listen(4);time.sleep(300)\"])\n"
    "s=socket.socket();s.bind(('127.0.0.1',int(sys.argv[1])));s.listen(4)\n"
    "print('listening',flush=True)\n"
    "time.sleep(%(live)s)\n"
)

# 赖着不走:忽略 SIGTERM(Windows 上等价形态是不响应 WM_CLOSE / CTRL_BREAK)
STUBBORN = (
    "import signal,socket,sys,time\n"
    "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
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

    def svc(self, name, code, port, timeout=20):
        return core.Service(
            name=name,
            argv=[sys.executable, "-c", code, str(port)],
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

    def test_c2_the_whole_process_tree_goes_down(self):
        """攻题 HIGH#5:nanobot 自己会拉起 3 个 MCP 子进程。只 terminate 直接子进程,
        孙子会留在机器上继续占端口 —— 业主下次打开就撞端口,而且看不见是谁占的。
        (Linux 这边验的是 POSIX 进程组;Windows 的 Job 对象只有真机验得了。)
        """
        port, sentinel = free_port(), free_port()
        self.sup.start([self.svc("有孙子的腿",
                                 SPAWN_GRANDCHILD % {"sentinel": sentinel, "live": 300},
                                 port)])
        deadline = time.time() + 10
        while not core.port_listening(sentinel) and time.time() < deadline:
            time.sleep(0.1)
        self.assertTrue(core.port_listening(sentinel), "孙进程没起来,这条考卷问不出东西")
        self.sup.shutdown()
        self.assertFalse(core.port_listening(port), "儿子还活着")
        self.assertFalse(core.port_listening(sentinel), "孙进程活了下来 ⇒ 整棵树没收干净")

    def test_c3_a_stubborn_child_gets_force_killed(self):
        """优雅退出要有期限,过期强杀。否则托盘点"退出"之后程序像卡死了。"""
        port = free_port()
        self.sup.start([self.svc("赖着不走的腿", STUBBORN, port)])
        t0 = time.time()
        self.sup.shutdown()
        took = time.time() - t0
        self.assertFalse(core.port_listening(port), "赖着不走的孩子没被强杀")
        self.assertLess(took, 20, f"收摊用了 {took:.1f}s ⇒ 业主会以为死机了")

    def test_c4_a_child_that_dies_is_reported_fast_and_readably(self):
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

    def test_c5_a_slow_leg_is_not_killed_early(self):
        """攻题 HIGH#4:真网关冷启动要好几秒。"先短轮询、没开口就报超时"的实现
        在原来那条 1.5s 的腿上照样绿,却会在业主机器上把网关误杀。
        """
        port = free_port()
        code = "import socket,sys,time\ntime.sleep(4)\n" + BIND_AND_WAIT
        self.sup.start([self.svc("慢腿", code, port, timeout=12)])
        self.assertTrue(core.port_listening(port))

    def test_c6_timeout_is_not_reported_before_the_deadline(self):
        port = free_port()
        code = "import sys,time;print('我起来了但就是不开端口',flush=True);time.sleep(60)"
        t0 = time.time()
        with self.assertRaises(core.StartupFailed) as cm:
            self.sup.start([self.svc("legD", code, port, timeout=4)])
        took = time.time() - t0
        self.assertGreaterEqual(took, 3.5, f"约好等 4s,{took:.1f}s 就报超时了")
        self.assertIn("我起来了但就是不开端口", str(cm.exception), "超时报错没带日志尾巴")

    def test_c7_a_port_someone_else_already_holds_is_not_our_green(self):
        """攻题 HIGH#4 的另一半:先查端口再查死活的实现,会把**陌生进程**的监听
        当成自己就绪了 —— 然后自己的孩子早就崩了。开跑前端口必须是空的。
        (同一条焊点 S0 探路包里叫 S5-pre。)
        """
        stranger, port = listen_on()
        self.addCleanup(stranger.close)
        with self.assertRaises(core.StartupFailed) as cm:
            self.sup.start([self.svc("撞车腿", BIND_AND_WAIT, port, timeout=8)])
        self.assertIn(str(port), str(cm.exception), "报错没说是哪个端口被占了")

    def test_c8_shutdown_is_idempotent(self):
        port = free_port()
        self.sup.start([self.svc("legE", BIND_AND_WAIT, port)])
        self.sup.shutdown()
        self.sup.shutdown()  # 托盘退出 + 进程退出会各调一次,不许炸

    def test_c9_a_failed_start_takes_its_siblings_down_before_it_returns(self):
        """第二条腿起不来 ⇒ 已经起好的第一条腿必须**在异常抛出之前**收掉。

        攻题 HIGH#5:靠考卷自己的 addCleanup 去收尸,会把真实的泄漏盖住 ——
        业主那边没有 addCleanup,留下的是"看着没开、其实后台有个孤儿在听 8766"。
        """
        good, bad = free_port(), free_port()
        with self.assertRaises(core.StartupFailed):
            self.sup.start([
                self.svc("好腿", BIND_AND_WAIT, good),
                self.svc("坏腿", "import sys;sys.exit(9)", bad, timeout=10),
            ])
        self.assertFalse(core.port_listening(good),
                         "起失败了却先把异常抛了,好腿变成孤儿进程")

    def test_c11_a_leg_that_dies_while_the_next_one_boots_fails_the_whole_start(self):
        """🔴 攻题二轮 HIGH#3:网关先就绪、随后崩掉,而这时监管者只盯着第二条腿。

        ds-web 一就绪 start() 就高高兴兴返回,窗口照开 —— 业主看到界面正常,
        但聊天**永远连不上**,而且没有任何报错。启动这件事必须是"全体活着"才算成。
        """
        first, second = free_port(), free_port()
        die_soon = BIND_AND_WAIT.replace("time.sleep(300)", "time.sleep(1.0)")
        slow = "import socket,sys,time\ntime.sleep(4)\n" + BIND_AND_WAIT
        with self.assertRaises(core.StartupFailed) as cm:
            self.sup.start([
                self.svc("先就绪后崩的腿", die_soon, first, timeout=20),
                self.svc("慢腿", slow, second, timeout=20),
            ])
        self.assertIn("先就绪后崩的腿", str(cm.exception), "报错没点名是哪条腿掉的")

    def test_c12_a_non_startupfailed_error_also_rolls_back(self):
        """攻题二轮 HIGH#4:第二条腿连日志都开不出来(路径不可用)会抛 OSError,
        它不是 StartupFailed ⇒ 回滚那段 except 接不住 ⇒ 第一条腿变成孤儿。
        任何异常都得先把兄弟腿收掉再往外抛。
        """
        good = free_port()
        bad = core.Service(name="日志开不出来的腿", argv=[sys.executable, "-c", "pass"],
                           env=dict(os.environ), ready_port=free_port(),
                           # 拿一个**文件**当目录用 ⇒ 建日志目录必然失败
                           log_path=self.dir / "我是文件" / "x.log", ready_timeout=5)
        (self.dir / "我是文件").write_text("不是目录", encoding="utf-8")
        with self.assertRaises(core.StartupFailed):
            self.sup.start([self.svc("好腿", BIND_AND_WAIT, good), bad])
        self.assertFalse(core.port_listening(good), "第二条腿抛了别的异常,好腿被丢在那儿没人收")

    def test_c13_grandchildren_are_reaped_even_if_the_parent_died_first(self):
        """攻题二轮 HIGH#4 的第二条:nanobot 父进程自己先崩了,3 个 MCP 孙进程还活着。

        收摊时若看到 `poll() != None` 就直接 return,那整个进程组永远没人杀 ——
        业主机器上从此躺着几个占着端口的孤儿,而且看不出是谁。
        """
        port, sentinel = free_port(), free_port()
        # 父进程:拉起孙子 → 开自己的端口 → 2 秒后自己退掉(**孙子继续活 300 秒**)
        code = SPAWN_GRANDCHILD % {"sentinel": sentinel, "live": 2.0}
        self.sup.start([self.svc("会先走的父进程", code, port)])
        deadline = time.time() + 10
        while not core.port_listening(sentinel) and time.time() < deadline:
            time.sleep(0.1)
        self.assertTrue(core.port_listening(sentinel), "孙进程没起来,这条考卷问不出东西")
        deadline = time.time() + 10
        while self.sup.poll_dead() != ["会先走的父进程"] and time.time() < deadline:
            time.sleep(0.1)
        self.sup.shutdown()
        self.assertFalse(core.port_listening(sentinel),
                         "父进程先死了,孙进程就没人收 ⇒ 机器上留下占着端口的孤儿")

    def test_c14_readiness_can_demand_an_identity_not_just_a_listener(self):
        """攻题二轮 HIGH#5:开跑前端口是空的,不代表就绪那一刻听端口的是**我们的孩子**。

        给 Service 一个可选的身份探针:端口在听 **且** 探针认账才算就绪。
        (ds-web 用 /api/health 自报版本 —— "让运行中的目标自己打印身份"那条规矩。)
        """
        port = free_port()
        svc = self.svc("冒牌腿", BIND_AND_WAIT, port, timeout=4)
        svc.ready_probe = lambda p: False       # 端口在听,但身份对不上
        with self.assertRaises(core.StartupFailed):
            self.sup.start([svc])

        port2 = free_port()
        ok = self.svc("正牌腿", BIND_AND_WAIT, port2, timeout=12)
        ok.ready_probe = lambda p: core.port_listening(p)
        self.sup.start([ok])                     # 探针认账 ⇒ 正常起

    def test_c10_poll_dead_names_the_leg_and_keeps_saying_so(self):
        port = free_port()
        code = BIND_AND_WAIT.replace("time.sleep(300)", "time.sleep(1.0)")
        self.sup.start([self.svc("短命腿", code, port)])
        self.assertEqual(self.sup.poll_dead(), [], "刚起来就说死了")
        dead, deadline = [], time.time() + 10
        while time.time() < deadline and not dead:
            dead = self.sup.poll_dead()
            time.sleep(0.2)
        self.assertEqual(dead, ["短命腿"], "腿死了没人发现 ⇒ 界面会一直转圈")
        # 契约:poll_dead 是"当前谁是死的",可重复问,不是一次性通知
        self.assertEqual(self.sup.poll_dead(), ["短命腿"], "同一个问题问第二遍答案变了")


# =========================================================== D 配置改写
# 夹具照抄真实形状(config/nanobot.config.windows.jsonc + enable_webui.py 写出来的样子):
# 3 个 MCP、model_presets、channels.websocket 的四个字段、以及一个"我不认识的扩展字段"。
BASE_CFG = {
    "providers": {"custom": {"apiKey": "${DS_LLM_KEY}", "apiBase": "https://example/v1"}},
    "model_presets": {
        "mimo-v2.5": {"label": "mimo-v2.5", "provider": "custom", "model": "mimo-v2.5",
                      "maxTokens": 8192, "contextWindowTokens": 128000, "temperature": 0.1},
        "mimo-v2.5-pro": {"label": "mimo-v2.5-pro", "provider": "custom",
                          "model": "mimo-v2.5-pro", "maxTokens": 8192},
    },
    "agents": {"defaults": {"modelPreset": "mimo-v2.5"}},
    "channels": {"websocket": {"enabled": True, "token": "业主的口令",
                               "host": "127.0.0.1", "port": 8765}},
    "gateway": {"port": 18790},
    "tools": {
        "file": {"enable": False},
        "exec": {"enable": False},
        "mcpServers": {
            # OpenDesign 自己的三个(名字照抄 config/nanobot.config.windows.jsonc)
            "design-studio": {"command": "${USERPROFILE}/.venvs/x/Scripts/python.exe",
                              "args": ["a.py"], "env": {"DS_ROOT": "${DS_ROOT}"}},
            "design-studio-refs": {"command": "${USERPROFILE}/.venvs/x/Scripts/python.exe",
                                   "args": ["b.py"]},
            "design-studio-organize": {"command": "${USERPROFILE}/.venvs/x/Scripts/python.exe",
                                       "args": ["c.py"], "env": {}},
            # 机主自己装的第三方 MCP —— 不是我们的,一个字都不许动
            "某个别人家的工具": {"command": "npx", "args": ["-y", "@someone/mcp"]},
        },
    },
    "以后版本加的我不认识的字段": {"随便": [1, 2, {"深": "值"}]},
}
OURS = ("design-studio", "design-studio-refs", "design-studio-organize")


def flatten(obj, prefix=""):
    """把一棵 JSON 摊成 {JSON 指针: 叶子值},用来做整棵差分。"""
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}/{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(flatten(v, f"{prefix}/{i}"))
    else:
        out[prefix] = obj
    return out


class PatchConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.cfg = self.dir / "config.json"
        self.write(BASE_CFG)

    def write(self, d):
        self.cfg.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

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

    def test_d2_our_own_mcps_point_into_the_package(self):
        exe = r"C:\OD\python\python.exe"
        d = self.patched(python_exe=exe)
        cmds = {n: s["command"] for n, s in d["tools"]["mcpServers"].items()}
        for name in OURS:
            self.assertEqual(cmds[name], exe, f"{name} 还指着机器上别的 python")
        self.assertEqual(len(cmds), 4, "改写时把某个 MCP 弄丢了")

    def test_d3_a_third_party_mcp_is_left_completely_alone(self):
        """攻题二轮 MED#8:上一版写的是"every MCP 都要改成包内 python",
        于是**把机主自己装的第三方 MCP(npx/别的 exe)一起改坏**,而断言反过来
        把这个 bug 写成了契约。只许动我们自己那三个。
        """
        d = self.patched()
        self.assertEqual(d["tools"]["mcpServers"]["某个别人家的工具"],
                         BASE_CFG["tools"]["mcpServers"]["某个别人家的工具"],
                         "把机主自己装的第三方 MCP 改坏了")

    def test_d3b_a_missing_own_mcp_is_refused(self):
        """三个自有 MCP 少一个 ⇒ 装出来的东西是残的(工具调不动、界面报错很难懂),
        必须当场拒绝,而不是安安静静放行。"""
        cfg = json.loads(json.dumps(BASE_CFG))
        del cfg["tools"]["mcpServers"]["design-studio-refs"]
        self.write(cfg)
        with self.assertRaises(core.ConfigUnusable):
            self.patched()

    def test_d3c_only_the_ports_and_our_mcp_commands_may_change(self):
        """攻题 HIGH#6:上一版只点名查了五片叶子 ⇒ 一个"重建一份最小 JSON"的实现
        能把 apiBase、model_presets、通道口令、MCP 的 env/args 全冲掉而照样全绿。
        改成**整棵差分**:只允许这几个位置变,别的一个字都不许动。
        """
        before = flatten(json.loads(self.cfg.read_text(encoding="utf-8")))
        after = flatten(self.patched(gateway_port=18801, ws_port=18802))
        changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        # 允许集合是**写死的三个自有 server**,不是"夹具里所有 server" ——
        # 后者会让"把第三方 MCP 也改掉"这个 bug 自动合法(攻题二轮 MED#8)。
        allowed = {"/gateway/port", "/channels/websocket/port"} | {
            f"/tools/mcpServers/{n}/command" for n in OURS}
        self.assertEqual(changed - allowed, set(), f"动了不该动的地方:{sorted(changed - allowed)}")
        self.assertEqual(allowed - changed, set(), f"该改的没改到:{sorted(allowed - changed)}")

    def test_d4_is_idempotent(self):
        once = self.patched()
        twice = self.patched()
        self.assertEqual(once, twice, "跑两遍结果不一样 ⇒ 每次启动都会把配置改一点")

    def test_d5_refuses_a_config_whose_channel_is_off(self):
        """攻题 HIGH#8:通道没开(或没口令),网关会起来但聊天永远连不上,
        而业主看到的只是"发不出去"。必须**当场拒绝并说人话**。

        注意方向:是拒绝,不是"顺手替它打开" —— 没口令就打开通道 = 开了一个不要密码的
        本地入口,那是把可用性问题换成安全问题(deploy-security §1)。
        """
        cases = (
            ({"enabled": False, "token": "abc", "host": "127.0.0.1", "port": 8765}, "没开"),
            ({"enabled": True, "token": "", "host": "127.0.0.1", "port": 8765}, "没口令"),
            # 🔴 中文口令(攻题二轮 HIGH#7):网关会正常起来、两条腿全绿,而业主的
            # 第一句话永远发不出去 —— 前端 web/src/chat/connection.ts:85 明确拒收
            # 非 Latin-1 口令(fetch 的 header 值只收 Latin-1)。装机时不拦,
            # 业主就会带着一个"看起来装好了"的机器来问我为什么不能聊天。
            ({"enabled": True, "token": "我的口令", "host": "127.0.0.1", "port": 8765}, "口令是中文"),
        )
        for broken, why in cases:
            cfg = json.loads(json.dumps(BASE_CFG))
            cfg["channels"] = {"websocket": broken}
            self.write(cfg)
            with self.assertRaises(core.ConfigUnusable, msg=f"通道{why}却放行了") as cm:
                self.patched()
            # 上一版写的是 r"[通道口令登录]" —— 那是**字符类**,报错里只要有一个"通"字
            # 就算过(攻题二轮自己揪出来的)。要的是整词。
            self.assertTrue(re.search(r"(通道|口令|登录)", str(cm.exception)),
                            f"报错不说人话:{cm.exception}")

    def test_d6_a_reader_never_sees_a_half_written_config(self):
        """断言名只说它问得出的那件事(攻题二轮 MED#10 把上一版"证明了原子替换"
        这个过大的名字揪出来了 —— `unlink` 再 `write_text` 同样能让 inode 变)。

        这里真正问的是**外部可观测的那条**:改写全程,另一个读者要么读到完整的旧的、
        要么读到完整的新的,**永远不会读到半份或读不到**。断电/被杀留下半份 JSON 的话,
        业主从此双击就打不开,而且查不出原因。
        """
        stop = threading.Event()
        seen: list[str] = []

        def reader():
            while not stop.is_set():
                try:
                    json.loads(self.cfg.read_text(encoding="utf-8"))
                except FileNotFoundError:
                    seen.append("文件一度不存在")
                except json.JSONDecodeError:
                    seen.append("读到半份 JSON")
                except OSError:
                    pass

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        try:
            for i in range(30):
                self.patched(gateway_port=18800 + i, ws_port=18900 + i)
        finally:
            stop.set()
            t.join(timeout=5)
        self.assertEqual(seen, [], f"改写过程中被外部读者撞见了中间状态:{set(seen)}")
        leftovers = [p.name for p in self.dir.iterdir() if p.name != "config.json"]
        self.assertEqual(leftovers, [], f"改完留了垃圾文件:{leftovers}")


# =========================================================== E 子进程环境
class ChildEnv(unittest.TestCase):
    #  base_env 里同时塞两类东西:必须留下的系统键,和必须被清掉的污染键。
    DIRTY = {
        "SystemRoot": r"C:\Windows", "TEMP": r"C:\Temp", "PATH": r"C:\Windows\System32",
        "LOCALAPPDATA": r"C:\Users\业主\AppData\Local", "COMSPEC": r"C:\Windows\cmd.exe",
        "PYTHONPATH": "/机器上别人的路径", "PYTHONHOME": r"C:\Python311",
        "DS_LLM_KEY": "sk-业主上一次装的旧key", "DS_ROOT": r"D:\旧的\OpenDesign",
        "DS_WEB_PORT": "9999",
    }

    def env(self, **kw):
        kw.setdefault("base_env", dict(self.DIRTY))
        kw.setdefault("ds_root", r"C:\OD\ds")
        kw.setdefault("user_home", r"C:\Users\业主\AppData\Local\OpenDesign\UserData")
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

    def test_e2_host_python_paths_do_not_leak_in(self):
        """业主机器上很可能本来就装着 Python。PYTHONPATH/PYTHONHOME 漏进来 ⇒ 包内
        Python 会去加载机器上那套包,而且**多半还能跑**——最难看的那种假绿(S0 焊点2 同源)。"""
        e = self.env()
        self.assertNotIn("PYTHONPATH", e)
        self.assertNotIn("PYTHONHOME", e)

    def test_e3_system_keys_survive(self):
        """攻题 HIGH#9 的反方向:一个"只返回三个 DS_ 键"的实现能过 E1/E2/E4,
        但 Windows 子进程缺 SystemRoot / TEMP / PATH 会以莫名其妙的方式坏掉。"""
        e = self.env()
        for k in ("SystemRoot", "TEMP", "PATH", "LOCALAPPDATA", "COMSPEC"):
            self.assertEqual(e.get(k), self.DIRTY[k], f"系统键 {k} 被弄丢了")

    def test_e4_inherited_ds_keys_are_wiped_not_inherited(self):
        """攻题 HIGH#9:业主机器上**已经装过**老版 OpenDesign ⇒ 环境里可能有旧的
        DS_LLM_KEY / DS_ROOT。只做加法的实现会让它们漏进来,于是包内程序读的是旧配置,
        而且"能跑",查起来要命。受控键必须由参数唯一决定。"""
        e = self.env(key=None)
        self.assertNotIn("DS_LLM_KEY", e, "继承了业主环境里的旧 key")
        self.assertEqual(e["DS_ROOT"], r"C:\OD\ds", "DS_ROOT 被环境里的旧值盖住了")
        self.assertEqual(e["DS_WEB_PORT"], "8766", "DS_WEB_PORT 被环境里的旧值盖住了")

    def test_e5_home_points_at_our_own_data_dir(self):
        """攻题 HIGH#8:nanobot 从 ~/.nanobot/config.json 读配置。HOME/USERPROFILE
        不接管的话,包内网关读的是**业主原来那份**配置 —— 我们刚改的那份根本没人看。
        Windows 上 os.path.expanduser 认 USERPROFILE,POSIX 认 HOME,两个都得设。
        """
        home = r"C:\Users\业主\AppData\Local\OpenDesign\UserData"
        e = self.env(user_home=home)
        self.assertEqual(e["USERPROFILE"], home)
        self.assertEqual(e["HOME"], home)

    def test_e6_key_is_passed_only_when_there_is_one(self):
        self.assertNotIn("DS_LLM_KEY", self.env(key=None))
        self.assertNotIn("DS_LLM_KEY", self.env(key=""))
        self.assertEqual(self.env(key="sk-abc")["DS_LLM_KEY"], "sk-abc")

    def test_e7_every_value_is_a_string(self):
        """焊点:env 里混进 int,subprocess 在 Windows 上会直接 TypeError ——
        而这份代码的所有真跑都在 Windows。"""
        self.assertEqual([k for k, v in self.env().items() if not isinstance(v, str)], [])


# =========================================================== F 窗口/托盘状态机
class FakeUI:
    """替身 UI:自己维护**真实状态**(攻题 HIGH#12:只记调用名会被
    "hide 完再 show" 骗过 —— 记录里有 hide、布尔值也对,窗口却还在)。"""

    def __init__(self):
        self.calls = []
        self.visible = True
        self.destroyed = False

    def show_window(self):
        assert not self.destroyed, "对着已经销毁的窗口调 show ⇒ 真机上是崩溃"
        self.calls.append("show")
        self.visible = True

    def hide_window(self):
        assert not self.destroyed, "对着已经销毁的窗口调 hide"
        self.calls.append("hide")
        self.visible = False

    def destroy(self):
        self.calls.append("destroy")
        self.destroyed = True
        self.visible = False


class ShellState(unittest.TestCase):
    def setUp(self):
        self.ui = FakeUI()
        self.stopped = []
        self.st = core.ShellState(ui=self.ui, on_stop=lambda: self.stopped.append(1))

    def test_f1_closing_the_window_hides_instead_of_quitting(self):
        """业主明确要的常驻式(像 openclaw):关窗口 ≠ 退出。"""
        allow_close = self.st.on_close_requested()
        self.assertFalse(allow_close, "关窗口把整个程序退了 ⇒ 后台聊天/提醒全断")
        self.assertEqual(self.ui.calls, ["hide"], f"关窗做了多余动作:{self.ui.calls}")
        self.assertFalse(self.ui.visible, "喊了 hide,窗口最后却还是显示着")
        self.assertEqual(self.stopped, [], "关个窗口就把两个服务收了")
        self.assertFalse(self.st.exiting)

    def test_f2_tray_open_shows_it_again(self):
        self.st.on_close_requested()
        self.st.on_show()
        self.assertTrue(self.ui.visible)
        self.assertTrue(self.st.visible)

    def test_f3_tray_quit_is_the_only_real_exit(self):
        self.st.on_quit()
        self.assertTrue(self.st.exiting)
        self.assertEqual(self.stopped, [1], "托盘退出没有收掉后台服务 ⇒ 留下孤儿进程")
        self.assertTrue(self.ui.destroyed)

    def test_f4_second_launch_raises_a_hidden_window(self):
        self.st.on_close_requested()
        self.assertFalse(self.ui.visible)
        self.st.on_show()  # ← InstanceLock 收到 SHOW 时走的就是这条路
        self.assertTrue(self.ui.visible)

    def test_f5_quit_is_idempotent(self):
        self.st.on_quit()
        self.st.on_quit()
        self.assertEqual(self.stopped, [1], "退出走了两遍 ⇒ 收服务的动作被重复执行")
        self.assertEqual(self.ui.calls.count("destroy"), 1)

    def test_f6_close_after_quit_does_not_resurrect(self):
        """退出过程中 pywebview 还会再发一次 closing ⇒ 那一次必须放行,否则关不掉。"""
        self.st.on_quit()
        self.assertTrue(self.st.on_close_requested(), "已经在退出了,还拦着不让关 ⇒ 窗口关不掉")

    def test_f8_two_threads_quitting_at_once_only_stop_the_backend_once(self):
        """攻题二轮 MED#9:真实事件来自三个线程(锁的监听线程、托盘线程、UI 线程)。
        两个 `on_quit()` 同时越过 `if self.exiting` ⇒ 后台被收两遍、窗口被销毁两遍。
        用一个"慢 UI"把那个窗口撑开,让竞态真的发生。
        """
        slow = FakeUI()
        real_destroy = slow.destroy

        def lazy_destroy():
            time.sleep(0.3)     # 撑开临界区
            real_destroy()

        slow.destroy = lazy_destroy
        stopped = []
        st = core.ShellState(ui=slow, on_stop=lambda: stopped.append(1))
        ready = threading.Barrier(4)

        def quit_now():
            ready.wait(timeout=10)
            st.on_quit()

        ts = [threading.Thread(target=quit_now) for _ in range(4)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(timeout=15)
        self.assertEqual(stopped, [1], "多个线程同时点退出,后台被收了不止一遍")
        self.assertEqual(slow.calls.count("destroy"), 1, "窗口被销毁了不止一遍")

    def test_f9_the_check_and_set_in_on_quit_is_not_two_steps(self):
        """f8 打的是真线程,但"检查 exiting"和"置位 exiting"之间那条缝极窄,
        真线程未必每次都插得进去 —— **单次绿说明不了什么**。这里把那条缝直接撑开:
        让 on_stop 自己再叫一次 on_quit(重入),没有原子性的实现会当场收两遍。
        """
        ui = FakeUI()
        stopped = []
        st = None

        def on_stop():
            stopped.append(1)
            st.on_quit()          # 重入:真机上托盘线程和 UI 线程就会这样打架
        st = core.ShellState(ui=ui, on_stop=on_stop)
        st.on_quit()
        self.assertEqual(stopped, [1], "on_quit 可重入 ⇒ 后台被收两遍")
        self.assertEqual(ui.calls.count("destroy"), 1, "窗口被销毁两遍")

    def test_f7_a_late_show_after_quit_is_a_no_op(self):
        """攻题 HIGH#12:退出途中第二个实例发来的 SHOW 会打在已销毁的窗口上。
        FakeUI 的 assert 会当场炸 —— 真机上那是崩溃,业主看到的是"点了退出反而报错"。"""
        self.st.on_quit()
        self.st.on_show()  # 不许炸,也不许把窗口"救活"
        self.assertFalse(self.st.visible)


# =========================================================== G 真后端
def make_ds_root(base: Path) -> Path:
    """造一个最小但**真**的 DS 数据根,里面放一个独一无二的 canary 项目。"""
    root = base / "数据根"
    (root / "projects").mkdir(parents=True)
    (root / "projects" / "坎那利-CANARY.md").write_text(  # 形状照 ds_tools._PROJECT_TEMPLATE
        "# 坎那利-CANARY\n\n- 业主: 考卷\n- 阶段: 方案\n- 地址/户型: 无\n"
        "- 开始日期: 2026-08-13\n\n## 阶段历史\n\n- 2026-08-13 方案\n\n"
        "## 变更记录\n\n## 沟通日志\n\n---\n最后更新: 2026-08-13\n", encoding="utf-8")
    return root


class RealBackend(unittest.TestCase):
    """用外壳**自己那套**监管 + env,真把后端起起来,让它自己报身份。

    S1a 的外壳考卷故意只喂自带 HTML,"外壳 + 真实后端"这个组合到现在没跑过一次。
    窗口那半只有 Windows 验得了,但**监管/env/端口/数据根这半在 Linux 上就能验**。
    "在使用现场验证":让运行中的目标自己打印,不看我怎么想。
    """

    def test_g1_ds_web_smoke_and_it_reads_the_data_root_we_gave_it(self):
        """名字只说它问得出的那件事:这是 **ds-web 启动冒烟**,不是"两腿联跑"
        (攻题 HIGH#11 把上一版那个过大的名字揪出来了;真联跑见 G2)。

        攻题 HIGH#10:上一版把 nanobot 的 workspace 当成了 DS 数据根传进去,而考卷只比
        version ⇒ **数据根接错也照绿**。现在用一个带 canary 项目的临时数据根,
        并要求运行中的 ds-web 把 ds_root 原样报回来、且真的读到了那个 canary。
        """
        ds_web = Path(BIN) / "ds_web.py"
        version = re.search(r'^VERSION\s*=\s*"([^"]+)"',
                            ds_web.read_text(encoding="utf-8"), re.M).group(1)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = make_ds_root(Path(tmp.name))
        port = core.pick_port(free_port(), span=10)
        sup = core.Supervisor()
        self.addCleanup(sup.shutdown)

        sup.start([core.Service(
            name="ds-web",
            argv=[sys.executable, str(ds_web)],
            env=core.child_env(base_env=dict(os.environ), ds_root=str(root),
                               user_home=str(Path(tmp.name) / "home"),
                               dsweb_port=port, ws_port=free_port()),
            ready_port=port,
            log_path=Path(tmp.name) / "ds-web.log",
            ready_timeout=40,
        )])

        def get(p):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{p}", timeout=10) as r:
                return json.loads(r.read().decode("utf-8"))

        health = get("/api/health")
        self.assertEqual(health.get("version"), version,
                         f"起来的这个 ds-web 自报 {health.get('version')!r},"
                         f"而仓库里是 {version!r} ⇒ 跑的不是我们这一份")
        self.assertEqual(os.path.realpath(health.get("ds_root") or ""), os.path.realpath(root),
                         f"ds-web 用的数据根是 {health.get('ds_root')!r},不是我们给的那个")
        keys = [p["key"] for p in get("/api/projects")["projects"]]
        self.assertIn("坎那利-CANARY", keys,
                      f"运行中的 ds-web 没读到我们放的 canary 项目:{keys}")
        sup.shutdown()
        self.assertFalse(core.port_listening(port), "外壳收摊后 ds-web 还在听端口")

    @unittest.skipUnless(os.environ.get("DS_SHELL_E2E") == "1",
                         "两腿真联跑要起 nanobot(慢、要装 nanobot):DS_SHELL_E2E=1 才跑")
    def test_g2_gateway_and_ds_web_really_talk_to_each_other(self):
        """攻题 HIGH#8 + HIGH#11 的正面回答:同一套 Supervisor / child_env / 落盘配置,
        真起 **gateway + ds-web 两条腿**,再经 ds-web 去够上游通道。

        这条问得出上一版整块问不出的东西:配置改写有没有被网关真的读到、
        HOME 接管有没有生效(不然它读的是本机 ~/.nanobot 那份)、通道端口接没接对。
        默认 SKIP —— **SKIP 不是 PASS**,收据里如实记账。
        """
        try:
            from nanobot.config.schema import Config
        except ImportError:
            self.skipTest("这个解释器没装 nanobot")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        root = make_ds_root(base)
        home = base / "home"
        (home / ".nanobot").mkdir(parents=True)
        cfg = home / ".nanobot" / "config.json"

        gw_port, ws_port, web_port = core.pick_ports([free_port(), free_port(), free_port()])
        d = Config().model_dump(mode="json", by_alias=True, exclude_none=True)
        cfg.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        # 从**真实模板**合并出配置(装机时走的就是这条路),而不是自己捏一份 ——
        # 攻题二轮 HIGH#6:空白 Config() 里根本没有那三个 MCP,却照样能让两条腿全绿。
        merged = subprocess.run(
            [sys.executable, str(Path(BIN) / "ds_merge_config.py"),
             str(Path(ROOT) / "config" / "nanobot.config.windows.jsonc"), str(cfg)],
            capture_output=True, text=True)
        self.assertEqual(merged.returncode, 0, f"合并真实模板失败:{merged.stderr[:600]}")
        d = json.loads(cfg.read_text(encoding="utf-8"))
        # 口令必须是**前端发得出去的** ASCII(connection.ts:85 拒收非 Latin-1)
        d.setdefault("channels", {}).setdefault("websocket", {}).update(
            {"enabled": True, "token": "kaojuan-pass", "host": "127.0.0.1", "port": 1})
        d.setdefault("providers", {})["custom"] = {"apiKey": "sk-考卷用的假key",
                                                   "apiBase": "http://127.0.0.1:1/v1"}
        cfg.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        core.patch_config(cfg, gateway_port=gw_port, ws_port=ws_port,
                          python_exe=sys.executable)

        env = core.child_env(base_env=dict(os.environ), ds_root=str(root), user_home=str(home),
                             dsweb_port=web_port, ws_port=ws_port, key="sk-考卷用的假key")
        sup = core.Supervisor()
        self.addCleanup(sup.shutdown)
        sup.start([
            core.Service(name="gateway", argv=[sys.executable, "-m", "nanobot", "gateway"],
                         env=env, ready_port=ws_port, log_path=base / "gateway.log",
                         ready_timeout=180),
            core.Service(name="ds-web", argv=[sys.executable, str(Path(BIN) / "ds_web.py")],
                         env=env, ready_port=web_port, log_path=base / "ds-web.log",
                         ready_timeout=60),
        ])
        # 网关真的在我们改写的那个通道端口上 ⇒ 证明它读的是我们刚落盘的配置
        self.assertTrue(core.port_listening(ws_port))
        # 经 ds-web 代理去够上游通道,**带上口令**(前端就是这么发的)。
        # 攻题二轮 HIGH#7:上一版没带 Authorization 且只排除 502 ⇒ 401/404/500 全绿,
        # 等于什么都没问。这里要的是真的 200 + bootstrap 该有的字段。
        req = urllib.request.Request(f"http://127.0.0.1:{web_port}/api/chat/bootstrap",
                                     headers={"Authorization": "Bearer kaojuan-pass"})
        with urllib.request.urlopen(req, timeout=30) as r:
            self.assertEqual(r.status, 200)
            info = json.loads(r.read().decode("utf-8"))
        self.assertTrue(info, f"bootstrap 回了个空的:{info!r}")
        sup.shutdown()
        for p in (gw_port, ws_port, web_port):
            self.assertFalse(core.port_listening(p), f"收摊后 {p} 还有人听")


if __name__ == "__main__":
    unittest.main(verbosity=2)
