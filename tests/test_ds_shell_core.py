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
import shutil
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
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
sys.path.insert(0, BIN)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tests/ 自己
import _tmpreg  # noqa: E402  临时目录登记表,见 tests/_tmpreg.py
import ds_shell_core as core  # noqa: E402

# 🔴 跑这份判据的进程,不许够得着我这台机器的真家。理由与 tests/test_ds_provision.py
# 那道同名防线一样(2026-08-15 实证:红检把真机 gateway 口令换了),**但这份更贵**:
# 这里的 M12 变异专门打掉 HOME 接管,而一旦漏过去,起来的就是**拿我真配置的真网关** ——
# 那份配置里有真 key。同源账见 [[judging-must-have-no-egress]](判据自己会花钱)。
# 放 setUpModule 不放 import 时:全量跑是一个进程导入所有判据,import 期改 HOME
# 会让别的判据(test_ws_protocol_smoke 按 HOME 找 gateway 口令)整块 SKIP。
_JUDGE_HOME = None
_REAL_HOME = {}


def setUpModule():
    global _JUDGE_HOME
    _JUDGE_HOME = _tmpreg.mkdtemp("ds-shell-core-判据假家-")
    for k in ("HOME", "USERPROFILE"):
        _REAL_HOME[k] = os.environ.get(k)
        os.environ[k] = _JUDGE_HOME


def tearDownModule():
    for k, v in _REAL_HOME.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


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

        # 放**多条**哑巴连接:只放一条的话,第二实例复扫锁位时会自己重试成功,
        # 于是串行处理的实现照样全绿(红检 M5 抓到的洞)。多条会把串行的那条路彻底堵死。
        mutes = [socket.create_connection(("127.0.0.1", first.port), timeout=5)
                 for _ in range(4)]
        for m in mutes:
            self.addCleanup(m.close)
        time.sleep(0.3)  # 让服务端确实收下这些连接

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

    # ---- 动词分派(track opendesign-key-onboarding T3)----------------------
    # 业主在界面里填完 key,网关必须重来一次才认(它只在启动时读一次 env)。
    # 通道**复用这把锁**:不新开端口、不新造 IPC(design 第三节)。
    # 🔴 今天 _handle 只读第一行就回 OK ——**第二行 SHOW 从来没被读过**,
    # "协议里有个动词"一直只是我以为。加动词之前先把这三条钉住。

    def _send_frame(self, port: int, verb: bytes) -> bytes:
        with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
            s.settimeout(5)
            s.sendall(core.InstanceLock._HELLO + verb)
            return s.recv(32)

    def test_b11_the_restart_verb_restarts_and_does_not_raise_the_window(self):
        """业主点"保存 key"时不该顺带被弹一个窗口到前台 —— 他人就在窗口里。"""
        base = free_port()
        shown, restarted = threading.Event(), threading.Event()
        lock = core.InstanceLock(base_port=base, span=5,
                                 on_show=shown.set, on_restart=restarted.set)
        self.addCleanup(lock.release)
        self.assertTrue(lock.acquire())

        # 2026-08-16:应答改成**点名动词**(K 组)。这里跟着搬,而且比原来强 ——
        # 原来只问"回了个 OK",现在问"它回的是**认了重启**的那个 OK"。
        self.assertEqual(self._send_frame(lock.port, b"RESTART-BACKEND\n"),
                         core.InstanceLock._OK_RESTART, "重启动词没被认出来")
        self.assertTrue(restarted.wait(5), "发了重启动词,后端却没被叫起来")
        self.assertFalse(shown.wait(0.5), "重启顺带把窗口弹到了前台 —— 他正在里面填 key")

    def test_b12_a_frame_without_a_verb_still_means_show(self):
        """兼容:今天在跑的那份(以及任何只发 HELLO 的老实例)必须照旧唤醒窗口。
        **加动词不许把双击图标弄坏** —— 那是这把锁本来的活。"""
        base = free_port()
        shown, restarted = threading.Event(), threading.Event()
        lock = core.InstanceLock(base_port=base, span=5,
                                 on_show=shown.set, on_restart=restarted.set)
        self.addCleanup(lock.release)
        self.assertTrue(lock.acquire())

        self.assertEqual(self._send_frame(lock.port, b""), core.InstanceLock._OK)
        self.assertTrue(shown.wait(5), "没有动词的老握手不再唤醒窗口了 ⇒ 双击图标没反应")
        self.assertFalse(restarted.is_set(), "没有动词却重启了后端 —— 聊天会平白断一次")

    def test_b13_an_unknown_verb_never_means_restart(self):
        """陌生动词退回 SHOW(**不是**重启)。重启会掐断聊天 ⇒ 拿不准时选那个不伤人的。"""
        base = free_port()
        shown, restarted = threading.Event(), threading.Event()
        lock = core.InstanceLock(base_port=base, span=5,
                                 on_show=shown.set, on_restart=restarted.set)
        self.addCleanup(lock.release)
        self.assertTrue(lock.acquire())

        self.assertEqual(self._send_frame(lock.port, b"RESTART\n"), core.InstanceLock._OK,
                         "认不出的动词不该把连接搞崩")
        self.assertTrue(shown.wait(5))
        self.assertFalse(restarted.is_set(),
                         "'RESTART' 这种近似词被当成了重启 —— 动词必须精确匹配")

    def test_b14_a_verb_in_a_second_packet_is_still_read(self):
        """🔴 红检 M4 逼出来的。b10 对 HELLO 验过分片,**没人对动词验过** ——
        于是把"读满两行"改成"读满一行"照样全绿:同包到达时缓冲里本来就有第二行,
        只有分片分得出来。而分片正是 TCP 的常态(b10 的注释已经写过一遍)。"""
        base = free_port()
        shown, restarted = threading.Event(), threading.Event()
        lock = core.InstanceLock(base_port=base, span=5,
                                 on_show=shown.set, on_restart=restarted.set)
        self.addCleanup(lock.release)
        self.assertTrue(lock.acquire())

        with socket.create_connection(("127.0.0.1", lock.port), timeout=5) as s:
            s.settimeout(5)
            s.sendall(core.InstanceLock._HELLO)
            time.sleep(0.15)                      # 在 _recv_frame 的宽限之内
            s.sendall(core.InstanceLock._RESTART)
            # 应答点名动词(K 组):动词分两个包到达时,认出来的仍然要点名
            self.assertEqual(s.recv(32), core.InstanceLock._OK_RESTART)
        self.assertTrue(restarted.wait(5), "动词晚到一个包就被丢了 ⇒ 填完 key 不会重启")
        self.assertFalse(shown.is_set(), "退回成了唤醒窗口 —— 窗口闪一下,key 却没生效")

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

    # ---- 只换掉一条腿(track opendesign-key-onboarding T3)---------------------
    # 业主填完 key ⇒ 网关必须重来一次才认新 env。但**ds-web 不能跟着断** ——
    # 他正看着的那个页面就是 ds-web 发的,一起重启的话他会看见界面白掉。
    # Supervisor 今天只有 start / shutdown(design 硬约束 2),这是新写口。

    ECHO_AND_WAIT = (
        "import os,socket,sys,time\n"
        "open(sys.argv[2],'a',encoding='utf-8')"
        ".write(f\"{os.getpid()} {os.environ.get('DS_TEST_TOKEN','')}\\n\")\n"
        "s=socket.socket();s.bind(('127.0.0.1',int(sys.argv[1])));s.listen(4)\n"
        "print('listening',flush=True)\n"
        "time.sleep(300)\n"
    )

    def echo_svc(self, name, port, token, trace):
        env = dict(os.environ)
        env["DS_TEST_TOKEN"] = token
        return core.Service(
            name=name,
            argv=[sys.executable, "-c", self.ECHO_AND_WAIT, str(port), str(trace)],
            env=env, ready_port=port, log_path=self.dir / f"{name}.log",
            ready_timeout=20,
        )

    def read_trace(self, trace):
        return [ln.split(" ", 1) for ln in
                Path(trace).read_text(encoding="utf-8").strip().splitlines()]

    def test_c15_restart_replaces_only_the_named_leg(self):
        ga, wa = free_port(), free_port()
        tg, tw = self.dir / "网关.trace", self.dir / "web.trace"
        self.sup.start([self.echo_svc("网关", ga, "old", tg),
                        self.echo_svc("工作台", wa, "web", tw)])

        self.sup.restart([self.echo_svc("网关", ga, "old", tg)])

        g = self.read_trace(tg)
        self.assertEqual(len(g), 2, "网关没被换掉")
        self.assertNotEqual(g[0][0], g[1][0], "换上来的还是同一个进程 ⇒ 它不会重读 env")
        self.assertEqual(len(self.read_trace(tw)), 1,
                         "工作台跟着重启了 —— 业主正看着的页面会白掉")
        self.assertTrue(core.port_listening(wa), "工作台被顺手带走了")

    def test_c16_the_replacement_really_gets_the_new_env(self):
        """🔴 本单的命门。重启网关的**唯一目的**就是让它读到新 key;
        新进程要是继承了老 env,业主填完 key 照样不能聊天,而判据全是绿的。"""
        ga = free_port()
        tg = self.dir / "网关.trace"
        self.sup.start([self.echo_svc("网关", ga, "还没填key", tg)])
        self.sup.restart([self.echo_svc("网关", ga, "sk-业主刚填的", tg)])

        rows = self.read_trace(tg)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][1], "sk-业主刚填的",
                         "新进程拿的还是老 env ⇒ 填了 key 也白填")

    def test_c17_a_failed_restart_does_not_take_the_others_down(self):
        """重启失败要响,但**不许连坐**:界面还在,他才看得到"重启失败,请手动重开"。
        (start() 那条路是失败就 shutdown 全部 —— 这里故意不一样,别照抄。)"""
        ga, wa = free_port(), free_port()
        tg, tw = self.dir / "网关.trace", self.dir / "web.trace"
        self.sup.start([self.echo_svc("网关", ga, "old", tg),
                        self.echo_svc("工作台", wa, "web", tw)])

        bad = core.Service(name="网关", argv=[sys.executable, "-c", "raise SystemExit(3)"],
                           env=dict(os.environ), ready_port=ga,
                           log_path=self.dir / "网关.log", ready_timeout=5)
        with self.assertRaises(core.StartupFailed):
            self.sup.restart([bad])

        self.assertTrue(core.port_listening(wa), "一条腿重启失败,把业主的界面也带走了")
        self.assertEqual(len(self.read_trace(tw)), 1, "工作台被重启了")

    # ── 2026-08-16 业主真机那一晚挖出来的三条 ────────────────────────────
    # 现场:填完 key → 外壳重启网关两次(都"完成")→ 26 秒后弹「网关意外退出了」。
    # 网关自己的日志最后一句是 `Agent loop started`,**之后什么都没有** ——
    # 它有能力打异常栈(同一份日志里就有两条完整的 traceback),所以它不是自己崩的。
    # 而外壳那句 `[后台退出] ['网关']` 连退出码都没有 ⇒ **没人答得了"谁杀的"**。
    # 下面三条:c18 收树、c19 别误报、c20 死了要说清楚。

    def test_c18_restarting_a_leg_reaps_its_whole_old_tree(self):
        """重启只 terminate 了直接子进程 ⇒ 它的 3 个 MCP 孙进程活了下来。

        c2 已经证明 **shutdown** 会收整棵树。重启走的是另一条路(`restart`),
        它没有复用那套收尸,于是业主每按一次"保存 key"就在机器上留下 3 个孤儿。
        同一件事在两条路上要各问一遍 —— 这正是 c2 全绿而现场出事的原因。
        """
        port, old_sentinel = free_port(), free_port()
        self.sup.start([self.svc("网关",
                                 SPAWN_GRANDCHILD % {"sentinel": old_sentinel, "live": 300},
                                 port)])
        deadline = time.time() + 10
        while not core.port_listening(old_sentinel) and time.time() < deadline:
            time.sleep(0.1)
        self.assertTrue(core.port_listening(old_sentinel), "孙进程没起来,这条考卷问不出东西")

        new_sentinel = free_port()
        # 🔴 **这条 assert 在 Linux 上问不出真 bug,别被它的绿骗了。**
        # POSIX 上 `_terminate_tree` 打的是整个进程组(killpg),孙子跟着一起走;
        # 而现场那台是 Windows —— 那边 `_terminate_tree` 只有 `proc.terminate()`,
        # 收整棵树靠的是**关 Job**(`_kill_tree` → `_close_job`,KILL_ON_JOB_CLOSE)。
        # 所以真正要问的是下面那句:重启收旧腿,走没走和 shutdown 同一套强杀。
        forced: list[str] = []
        with mock.patch.object(core.Supervisor, "_kill_tree",
                               lambda sup_self, child: forced.append(child.service.name)):
            self.sup.restart([self.svc("网关",
                                       SPAWN_GRANDCHILD % {"sentinel": new_sentinel, "live": 300},
                                       port)])
        self.assertTrue(core.port_listening(port), "新网关没起来,这条考卷问不出东西")
        self.assertFalse(core.port_listening(old_sentinel),
                         "旧网关的孙进程活了下来 ⇒ 每重启一次,机器上多 3 个孤儿工具服务")
        self.assertEqual(["网关"], forced,
                         "重启没走强杀那一步 ⇒ **Windows 上 Job 不会被关**,"
                         "旧网关的 3 个 MCP 全变成孤儿(Linux 这边被进程组盖住了,看不出来)")

    def test_c19_a_leg_being_restarted_is_never_reported_as_a_crash(self):
        """看门狗每 3 秒问一次 `poll_dead()`;它答"网关死了",业主就会收到
        「网关意外退出了,请退出后重新打开」。

        重启时旧腿本来就该死 —— 但它在被杀之后、被移出名册之前还挂在名册上,
        那一刻问过去,答案是"网关死了"。**正常重启被报成崩溃**,而且给的指令
        (退出后重开)恰好会打断正在进行的重启。
        这里用探针把"看门狗刚好在最坏的时刻问了一次"变成确定性的:
        真杀完、等它死透,立刻替看门狗问一次。
        """
        seen: list = []
        original = core.Supervisor._terminate_tree

        def spy(sup_self, child):
            original(sup_self, child)
            try:
                child.proc.wait(timeout=5)       # 等它真的死透 = 最坏的那一刻
            except Exception:
                pass
            seen.append(sup_self.poll_dead())
            return None

        ga = free_port()
        self.sup.start([self.svc("网关", BIND_AND_WAIT, ga)])
        with mock.patch.object(core.Supervisor, "_terminate_tree", spy):
            self.sup.restart([self.svc("网关", BIND_AND_WAIT, ga)])

        self.assertTrue(seen, "探针没被调到,这条考卷问不出东西")
        self.assertEqual([[]], seen,
                         f"重启途中看门狗会看到 {seen} ⇒ 弹「网关意外退出了」,而一切正常")

    def test_c20_a_dead_leg_says_why_not_just_that_it_died(self):
        """08-16 现场卡死在这里:网关死了,而外壳只说了"它退出了"。

        退出码分得清"被人杀的"和"自己崩的";日志尾巴给的是崩在哪。
        两样都没有 ⇒ 业主把日志发过来,我也答不了,只能猜。
        """
        port = free_port()
        code = (
            "import socket,sys,time\n"
            "s=socket.socket();s.bind(('127.0.0.1',int(sys.argv[1])));s.listen(4)\n"
            "print('listening',flush=True)\n"
            "time.sleep(0.5)\n"
            "print('我崩在这一句上',flush=True)\n"
            "sys.exit(7)\n"
        )
        self.sup.start([self.svc("网关", code, port)])
        deadline = time.time() + 10
        while self.sup.poll_dead() != ["网关"] and time.time() < deadline:
            time.sleep(0.1)
        self.assertEqual(["网关"], self.sup.poll_dead(), "腿死了没人发现")

        reports = self.sup.dead_reports()
        self.assertEqual(1, len(reports), "死了一条腿,却不是一条报告")
        said = reports[0]
        self.assertIn("网关", said, "没说是哪条腿")
        self.assertIn("7", said, "**没带退出码** —— 分不出是被杀的还是自己崩的")
        self.assertIn("我崩在这一句上", said, "没带日志尾巴,业主拿到的还是一句没线索的话")

    def test_c21_who_died_and_why_come_from_one_look(self):
        """"谁死了"和"它为什么死"必须是**同一眼看到的**。

        08-17 四审(subdeepseek F5):看门狗先问 `poll_dead()` → 答「网关」,
        再问 `dead_reports()` → 答空(业主恰好在这两句中间存了 key,重启
        把网关移出了名册)。于是弹窗照弹「网关意外退出了」,日志里却一个
        原因都没有 —— **c20 刚消灭掉的那种没线索的弹窗,换个入口又长出来了。**

        修法不是加锁(shutdown 也持那把锁,重启途中互等的风险更大),
        是只看一眼:`take_dead()` 一次遍历同时给出名字和原因。

        考卷怎么把"问了两遍"变成确定性的:把那条腿的 `poll()` 换成
        **第一次答 7、之后答 None** —— 问一遍的实现看到的是一具带退出码的
        尸体;问两遍的实现第二遍会看到"它还活着",于是名字有、原因没了。
        """
        port = free_port()
        code = ("import socket,sys,time\n"
                "s=socket.socket();s.bind(('127.0.0.1',int(sys.argv[1])));s.listen(4)\n"
                "print('listening',flush=True)\n"
                "time.sleep(0.3)\n"
                "print('我崩在这一句上',flush=True)\n"
                "sys.exit(7)\n")
        self.sup.start([self.svc("网关", code, port)])
        deadline = time.time() + 10
        while self.sup.poll_dead() != ["网关"] and time.time() < deadline:
            time.sleep(0.1)
        self.assertEqual(["网关"], self.sup.poll_dead(), "腿死了没人发现")

        child = self.sup._children[0]
        answers = iter([7])

        def poll_once_then_alive():
            return next(answers, None)     # 第一次 7,之后 None(= 名册在两问之间变了)

        with mock.patch.object(child.proc, "poll", poll_once_then_alive):
            pairs = self.sup.take_dead()

        self.assertEqual(1, len(pairs),
                         f"一条腿死了,take_dead 给了 {len(pairs)} 条 ⇒ 它问了不止一遍")
        name, said = pairs[0]
        self.assertEqual("网关", name, "没说是哪条腿")
        self.assertIn("7", said,
                      "**名字有、原因没了** ⇒ 两次问答案不一致,业主拿到的又是一句没线索的话")
        self.assertIn("我崩在这一句上", said, "没带日志尾巴")

    def test_c22_a_new_leg_that_cannot_come_up_is_reaped_the_same_way(self):
        """重启时**新**腿起不来 ⇒ 它也得走和 shutdown 同一套收尸。

        c18 钉的是 `restart()` 的前一半(收**旧**腿)。同一个函数的后一半 ——
        新腿 `_wait_ready` 失败的那条路 —— 只做了 `_terminate_tree`,
        **没有 `_kill_tree` / `_close_job` / 关日志句柄**。
        Windows 上那等于只杀了 nanobot 本尊,它带的 3 个 MCP 留在 Job 里没人收
        (KILL_ON_JOB_CLOSE 不触发),外壳进程里每失败一次还漏一个日志句柄。
        触发条件是真实的:新网关起来了但没在超时内就绪,或者启动途中自己崩掉。
        (08-17 四审 subkimi F-2 —— **两腿里只有它看见**。)

        考卷用 spy 记录"谁被强杀过":旧腿必须在里面(c18 已有),
        **新腿也必须在里面**(这一条问的就是它)。
        """
        port = free_port()
        self.sup.start([self.svc("网关", BIND_AND_WAIT, port)])

        killed: list[str] = []
        closed: list[str] = []
        kill_orig, close_orig = core.Supervisor._kill_tree, core.Supervisor._close_job

        def kill_spy(sup_self, child):
            killed.append(child.service.name)
            return kill_orig(sup_self, child)

        def close_spy(sup_self, child):
            closed.append(child.service.name)
            return close_orig(sup_self, child)

        # 起得来、但永远不监听那个端口 ⇒ 走 _wait_ready 超时那条失败路
        never_ready = "import time\ntime.sleep(300)\n"
        with mock.patch.object(core.Supervisor, "_kill_tree", kill_spy), \
             mock.patch.object(core.Supervisor, "_close_job", close_spy):
            with self.assertRaises(core.StartupFailed):
                self.sup.restart([self.svc("网关", never_ready, port, timeout=2)])

        self.assertEqual(2, len(killed),
                         f"强杀了 {killed} —— 旧腿和新腿各该有一次;"
                         "少的那次就是**新腿起不来时它的 MCP 孙子没人收**")
        self.assertEqual(2, len(closed),
                         f"关 Job 只发生了 {len(closed)} 次 ⇒ Windows 上 "
                         "KILL_ON_JOB_CLOSE 不触发,那条腿的整棵树留在机器上")
        self.assertFalse(core.port_listening(port), "失败的新腿把端口占着走了")

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

    def test_c23_a_child_on_windows_never_pops_a_console_window(self):
        """业主真机 0.89.0 实撞:打开软件冒出**两个黑窗口**(网关一个、工作台一个),
        而且**关掉一个就等于杀掉一条腿** —— 他关掉网关那个,界面当场报"断开连接"。

        根因:外壳自己是没有控制台的 `pythonw.exe`,却用 `python.exe`(控制台程序)起腿。
        **没有控制台的进程去起控制台程序,Windows 会为它新开一个控制台窗口。**

        🔴 问的是那个**唯一来源**的纯函数,不是把全局 `os.name` 顶成 "nt" 再跑一遍
        `_spawn`。第一版就是那么写的,结果 `pathlib` 跟着切成 WindowsPath、
        当场 NotImplementedError —— **红在了它自己身上,一个断言都没跑到**
        (「红在 TypeError 上等于没红检过」)。函数纯了,这道闸才问得干净。

        🔴 两个数值**写死在判据里**,不从被测模块导入:导入的话,实现把常量改成 0、
        判据跟着读到 0,**两边一起错还全绿**(08-12 栽过这个形状)。
        """
        CREATE_NEW_PROCESS_GROUP, CREATE_NO_WINDOW = 0x00000200, 0x08000000

        win = core.spawn_kwargs("nt")
        flags = win.get("creationflags")
        self.assertIsNotNone(flags, "Windows 上起子进程根本没给 creationflags")
        self.assertTrue(flags & CREATE_NO_WINDOW,
                        f"creationflags={flags:#x} 里没有 CREATE_NO_WINDOW ⇒ "
                        "业主每开一次软件就多一个黑窗口,而且关掉它就杀掉这条腿")
        self.assertTrue(flags & CREATE_NEW_PROCESS_GROUP,
                        f"creationflags={flags:#x} 里没有 CREATE_NEW_PROCESS_GROUP ⇒ "
                        "这一位原来是对的,别修坏")

        posix = core.spawn_kwargs("posix")
        self.assertTrue(posix.get("start_new_session"),
                        "POSIX 那半边被改坏了 —— 进程组没了,收尸就收不干净")
        self.assertNotIn("creationflags", posix,
                         "POSIX 上传 creationflags,Popen 会直接抛 ValueError")

    def test_c23b_the_spawn_really_uses_that_one_source(self):
        """光有那个纯函数不够 —— `_spawn` 得真的用它。

        这条问的是**接线**:在 Linux 上起一条真腿,它拿到的 kwargs 必须和
        `spawn_kwargs("posix")` 说的一致。(Windows 那半边只有静态闸和真机管得了,
        见 tests/test_no_console_window.py 和真机清单。)
        """
        seen: dict = {}
        real = core.subprocess.Popen

        def spy(argv, **kwargs):
            seen.update(kwargs)
            return real(argv, **kwargs)

        port = free_port()
        with mock.patch.object(core.subprocess, "Popen", spy):
            self.sup.start([self.svc("legA", BIND_AND_WAIT, port)])
        for key, want in core.spawn_kwargs("posix").items():
            self.assertEqual(want, seen.get(key),
                             f"_spawn 没有把 spawn_kwargs 的 {key} 传下去 ⇒ "
                             "那个'唯一来源'是摆设,真机上照样弹黑窗口")

    def test_c24_the_taskkill_fallback_never_pops_a_console_window(self):
        """收尸的兜底路 `taskkill /T /F` 也是控制台程序 —— 同一个病:
        每兜底一次闪一个黑窗口。只在没挂上 Job 时才走,但**一类病要一次修完**。
        """
        CREATE_NO_WINDOW = 0x08000000
        seen: dict = {}

        def fake_run(argv, **kwargs):
            seen["argv"] = argv
            seen.update(kwargs)

        class FakeProc:
            pid = 4242

            def poll(self):
                return None

            def kill(self):
                pass

        child = core._Managed(service=self.svc("网关", "pass", 0),
                              proc=FakeProc(), log_file=None, job_handle=None)
        with mock.patch.object(core.os, "name", "nt"), \
             mock.patch.object(core.subprocess, "run", fake_run):
            self.sup._kill_tree(child)

        self.assertEqual("taskkill", seen.get("argv", [None])[0],
                         "没走到 taskkill 那条兜底路 ⇒ 这道闸问不出东西")
        self.assertTrue((seen.get("creationflags") or 0) & CREATE_NO_WINDOW,
                        f"taskkill 的 creationflags={seen.get('creationflags')} ⇒ "
                        "每收一次尸闪一个黑窗口")

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
    # 口令用 ASCII —— 中文口令是**产品明确要拒绝**的(见 d5),夹具不能拿它当正常值
    "channels": {"websocket": {"enabled": True, "token": "yezhu-de-kouling",
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
        # 业主机器上这两个**一定**是有值的 —— 少了它们,一个"有就沿用继承值"的
        # 实现会照样全绿(红检 M12 抓到的洞:网关会去读业主原来那份 ~/.nanobot)
        "HOME": r"C:\Users\业主", "USERPROFILE": r"C:\Users\业主",
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
        # 题面随契约变更(T3):变量名从写死变成显式参数,断言本身没放松 ——
        # "有 key 才设、设的值原样" 三条一条没少,只是现在得说清设的是**哪个**变量。
        self.assertNotIn("DS_LLM_KEY", self.env(key=None))
        self.assertNotIn("DS_LLM_KEY", self.env(key=""))
        self.assertEqual(self.env(key="sk-abc", key_var="DS_LLM_KEY")["DS_LLM_KEY"], "sk-abc")

    def test_e8_the_variable_name_comes_from_the_config_not_from_this_file(self):
        """🔴 规划双出 B 卷抓到的那条,第二次露头:配置引用的**不一定**叫 DS_LLM_KEY
        (Linux 那份就是 ${MIMO_TP_KEY})。写死的话,变量名一改,网关拿不到 key ——
        而它的症状是"填了 key 还是不能聊天",最难往这儿查。
        ds_credential.env_var_name() 已经会从配置读出来了,这里必须真用上它给的值。"""
        e = self.env(key="sk-abc", key_var="MIMO_TP_KEY")
        self.assertEqual(e["MIMO_TP_KEY"], "sk-abc")
        self.assertNotIn("DS_LLM_KEY", e, "另设了一个写死的名字 ⇒ 两个来源迟早对不上")

    def test_e10_the_web_is_told_where_the_lock_is(self):
        """🔴 这条防的是"接线测试证明不了接上了"。

        k 组(ds-web 那侧)自己往 env 里塞了 DS_SHELL_LOCK_PORT,于是它们全绿 ——
        但**没有一条问过外壳到底有没有把这个号告诉 ds-web**。不告诉的话,
        整条重启链路空转,而两侧判据都是绿的。
        同款事故已经吃过两次:data-outside 那单的三个 MCP 拿不到 DS_DATA_ROOT,
        47 处改动等于没改;h3 看得见调用、看不见空转。
        """
        e = self.env(lock_port=18788)
        self.assertEqual(e["DS_SHELL_LOCK_PORT"], "18788")
        self.assertNotIn("DS_SHELL_LOCK_PORT", self.env(),
                         "没有锁的时候不许留一个假号 —— ds-web 会拿它去连别人")

    def test_e9_forgetting_the_variable_name_is_loud(self):
        """有 key 却没说设哪个变量 ⇒ 抛,不许悄悄退回写死的默认名。
        **失败没有声音**是这个项目栽过最多次的病(pip 静默丢依赖、git add 静默跳过)。"""
        with self.assertRaises(ValueError):
            self.env(key="sk-abc")

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
        # 2026-08-15(track opendesign-data-outside-install):业主的档案从此不住在
        # 代码根里,而在外壳指定的**数据根**下 —— 所以 canary 要放在外壳真会用的那个
        # 位置(child_env 把它设成 <user_home 的上一级>/Data),否则这条问的是空气。
        # 这一改**加强**了它:现在它证明的是"运行中的 ds-web 真的从安装目录之外读档案"。
        seeded = make_ds_root(Path(tmp.name) / "seed")
        shutil.copytree(seeded, Path(tmp.name) / "Data", dirs_exist_ok=True)
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
        # apiKey 保持 **${变量} 形态**(模板里本来就是这样),只把 apiBase 指到死地址。
        # 上一版这里写死成 "sk-考卷用的假key",等于绕开了真机唯一走的那条路:
        # 配置引用变量 → child_env 设那个变量 → 网关启动时解析。T3 之后这条链路
        # 多了一环(变量名从配置读),写死的话它整段都不会被走到。
        d.setdefault("providers", {})["custom"] = {"apiKey": "${DS_LLM_KEY}",
                                                   "apiBase": "http://127.0.0.1:1/v1"}
        cfg.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        core.patch_config(cfg, gateway_port=gw_port, ws_port=ws_port,
                          python_exe=sys.executable)

        import ds_credential   # 变量名从刚 patch 完的真配置读(T3 起不许写死)
        env = core.child_env(base_env=dict(os.environ), ds_root=str(root), user_home=str(home),
                             dsweb_port=web_port, ws_port=ws_port, key="sk-考卷用的假key",
                             key_var=ds_credential.env_var_name(
                                 json.loads(cfg.read_text(encoding="utf-8"))))
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


# =========================================================== H 配置里的环境变量引用
class MissingEnvRefs(unittest.TestCase):
    """🔴 这一组是 **2026-08-14 业主真机红出来的那一条**,不是推演。

    真机收据:第 1 问红,外壳 rc=1,日志里是
        `网关 启动失败: 退出码 1 … Error: Environment variable 'DS_LLM_KEY'
         referenced in config is not set`

    根因不在代码,在**我写在 ds_shell.py 里的一句话**:「没找到 key 也不当场退出,
    业主可能只是想看看待办(ds-web 是只读的,不需要 key)」。
    这句话是假的 —— 配置里写着 `"apiKey": "${DS_LLM_KEY}"`,而 nanobot 解析到
    任何一个没设的 `${VAR}` 就**整个网关拒绝启动**(loader.py:143-149)。
    ⇒ 业主看到的是:等 5 分钟,然后一句英文。

    为什么两张考卷都没问出来(这才是要记住的):
      · Linux 的 G2 **给了假 key**(`key="sk-考卷用的假key"`);
      · Windows 的 S1b 考卷**故意不给 key**(「这一跑不考聊天」)。
      两张卷子对同一个前提做了**相反的假设**,而**没有一张去问那个前提本身**。
      同类:[[behavior-evals-are-sampling]] —— 红了先问是不是真 bug。

    所以这一组问的是那个前提:**配置引用了、而 env 里没有的变量,必须在起任何
    子进程之前就被点名**。H4 是真机那次的复现,H5 让"没 key 网关就是起不来"这件事
    有据可查(而不是再靠我记忆里的一句注释)。
    """

    def test_h1_a_referenced_but_unset_variable_is_named(self):
        self.assertEqual(
            core.missing_env_refs({"providers": {"custom": {"apiKey": "${DS_LLM_KEY}"}}}, {}),
            ["DS_LLM_KEY"])

    def test_h2_a_variable_that_is_set_is_not_reported(self):
        cfg = {"a": "${FOO}"}
        self.assertEqual(core.missing_env_refs(cfg, {"FOO": "x"}), [])
        # 空串**也算设了** —— nanobot 判的是 os.environ.get() is None(loader.py:145)。
        # 这里写死成"空串算缺"就会造出一个假红:配置本来跑得起来,外壳却拒绝启动。
        self.assertEqual(core.missing_env_refs(cfg, {"FOO": ""}), [])

    def test_h3_it_looks_all_the_way_down_and_says_each_name_once(self):
        cfg = {"tools": {"mcpServers": {
            "a": {"args": ["${DS_ROOT}/bin/x.py", "--home=${USERPROFILE}"]},
            "b": {"args": ["${DS_ROOT}/bin/y.py"]}}}}
        self.assertEqual(core.missing_env_refs(cfg, {}), ["DS_ROOT", "USERPROFILE"])

    # ---- 缺了之后**跟业主怎么说** ------------------------------------------
    # H1~H4 只管"点得出名字",而业主真正看见的是那段话。上一版这段话写在
    # ds_shell.py 里 —— 那一层在 Linux 上一条考卷都跑不了(要 pywebview/.NET),
    # 于是**业主唯一会看见的输出零判据**。真机一趟很贵(S0 用掉两趟),不值得
    # 拿一趟去验一个 f-string。⇒ 文案下沉到 core,由下面三条咬住。
    #
    # 咬的是"两种缺法要给两种指令",不是遣词造句:
    #   · 缺 key      = 业主自己补得上(放个文件)⇒ 必须报出那个文件的完整路径
    #   · 缺别的      = 装机没装好          ⇒ 必须让他重跑安装程序
    # 把两者说反或说成同一句,业主就会去做错的那件事 —— 那正是这一单的病根。

    def test_h6_a_missing_key_tells_him_the_file_to_put_it_in(self):
        msg = core.missing_env_message(["DS_LLM_KEY"], app="OpenDesign",
                                       key_path=r"C:\OD\UserData\.openDesign\key.txt")
        self.assertIn(r"C:\OD\UserData\.openDesign\key.txt", msg,
                      "缺 key 必须把那个文件的完整路径念给他听,不能只说'缺 key'")
        self.assertNotIn("重新运行安装程序", msg,
                         "只缺 key 时让他重装 = 支使他做一件解决不了问题的事")

    def test_h7_anything_else_missing_means_the_install_is_broken(self):
        msg = core.missing_env_message(["DS_ROOT"], app="OpenDesign",
                                       key_path=r"C:\OD\UserData\.openDesign\key.txt")
        self.assertIn("DS_ROOT", msg, "缺的东西必须点名,否则我事后也查不出是哪个")
        self.assertIn("重新运行安装程序", msg)
        self.assertNotIn("key.txt", msg,
                         "不缺 key 却让他去建 key.txt = 把他支去改一个没坏的东西")

    def test_h8_both_kinds_get_both_instructions_and_nothing_is_dropped(self):
        msg = core.missing_env_message(["DS_LLM_KEY", "DS_ROOT"], app="OpenDesign",
                                       key_path=r"C:\OD\UserData\.openDesign\key.txt")
        for expected in (r"C:\OD\UserData\.openDesign\key.txt", "DS_ROOT",
                         "重新运行安装程序"):
            self.assertIn(expected, msg, f"两种缺法同时出现时漏了:{expected}")

    def test_h9_nothing_missing_says_nothing(self):
        """焊点:没缺东西时它必须闭嘴。

        少了这条,一个"永远返回一段话"的实现能过 H6~H8,而外壳只要照着
        `if msg: die(msg)` 接线,**每次启动都会弹一个错误框**——业主永远打不开。
        """
        self.assertFalse(core.missing_env_message([], app="OpenDesign",
                                                  key_path=r"C:\x\key.txt"))

    def test_h4_the_real_windows_config_after_patching_lacks_exactly_the_key(self):
        """真机那次的复现:**真模板 → 真 patch_config → 真 child_env**,不捏假配置。

        断言写成"恰好等于 [DS_LLM_KEY]"而不是 assertIn:
        多点名一个变量 = 一次假红 = 业主装好的机器打不开,那和漏判一样坏。
        """
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cfg_path = Path(tmp.name) / "config.json"
        cfg_path.write_text("{}", encoding="utf-8")
        merged = subprocess.run(
            [sys.executable, str(Path(BIN) / "ds_merge_config.py"),
             str(Path(ROOT) / "config" / "nanobot.config.windows.jsonc"), str(cfg_path)],
            capture_output=True, text=True)
        self.assertEqual(merged.returncode, 0, f"合并真实模板失败:{merged.stderr[:600]}")
        d = json.loads(cfg_path.read_text(encoding="utf-8"))
        d.setdefault("channels", {}).setdefault("websocket", {}).update(
            {"enabled": True, "token": "kaojuan-pass"})
        cfg_path.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        core.patch_config(cfg_path, gateway_port=18790, ws_port=8765,
                          python_exe=r"C:\OD\python\python.exe")
        final = json.loads(cfg_path.read_text(encoding="utf-8"))

        def env(key):
            # 变量名**从这份真配置里读**(不是照抄字面量)。这样这条判据顺带回答了
            # e8 问不到的那半:env_var_name() 读出来的,和真 Windows 模板引用的,
            # 是不是同一个名字 —— 对不上的话下面那条 assert 会当场红。
            import ds_credential
            return core.child_env(base_env={}, ds_root=r"C:\OD\ds",
                                  user_home=r"C:\OD\UserData", dsweb_port=8766,
                                  ws_port=8765, key=key,
                                  key_var=ds_credential.env_var_name(final) if key else None)

        self.assertEqual(core.missing_env_refs(final, env(key=None)), ["DS_LLM_KEY"],
                         "没放 key 时,必须**在起网关之前**就点名 DS_LLM_KEY")
        self.assertEqual(core.missing_env_refs(final, env(key="sk-x")), [],
                         "放了 key 还报缺 = 假红,业主会被挡在门外")

    @unittest.skipUnless(os.environ.get("DS_SHELL_E2E") == "1",
                         "要真起 nanobot(慢、要装 nanobot):DS_SHELL_E2E=1 才跑")
    def test_h5_the_gateway_really_refuses_to_start_without_the_key(self):
        """把「没 key 也能起来看待办」这句话**证伪一次并留下证据**。

        H1~H4 只证明"我们点得出这个名字";这一条证明**点名是必要的** ——
        真起一次网关、不给 key,它必须死。少了这条,下次又会有人(我)在注释里
        写一句"没 key 应该也能跑吧",而没有任何机器拦得住。
        默认 SKIP —— **SKIP 不是 PASS**。
        """
        try:
            from nanobot.config.schema import Config
        except ImportError:
            self.skipTest("这个解释器没装 nanobot")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        home = base / "home"
        (home / ".nanobot").mkdir(parents=True)
        cfg = home / ".nanobot" / "config.json"
        cfg.write_text(json.dumps(Config().model_dump(mode="json", by_alias=True,
                                                      exclude_none=True)), encoding="utf-8")
        merged = subprocess.run(
            [sys.executable, str(Path(BIN) / "ds_merge_config.py"),
             str(Path(ROOT) / "config" / "nanobot.config.windows.jsonc"), str(cfg)],
            capture_output=True, text=True)
        self.assertEqual(merged.returncode, 0, f"合并真实模板失败:{merged.stderr[:600]}")
        d = json.loads(cfg.read_text(encoding="utf-8"))
        d.setdefault("channels", {}).setdefault("websocket", {}).update(
            {"enabled": True, "token": "kaojuan-pass", "host": "127.0.0.1", "port": 1})
        cfg.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        gw_port, ws_port = core.pick_ports([free_port(), free_port()])
        core.patch_config(cfg, gateway_port=gw_port, ws_port=ws_port, python_exe=sys.executable)

        env = core.child_env(base_env=dict(os.environ), ds_root=str(make_ds_root(base)),
                             user_home=str(home), dsweb_port=free_port(), ws_port=ws_port,
                             key=None)          # ← 就是真机那一跑的样子
        self.assertNotIn("DS_LLM_KEY", env)
        sup = core.Supervisor()
        self.addCleanup(sup.shutdown)
        with self.assertRaises(core.StartupFailed) as caught:
            sup.start([core.Service(name="gateway",
                                    argv=[sys.executable, "-m", "nanobot", "gateway"],
                                    env=env, ready_port=ws_port,
                                    log_path=base / "gateway.log", ready_timeout=90)])
        # 死法也要对上:必须是**它自己退出**,不是我们等超时 ——
        # "超时"会把这条证据变成"可能只是慢",而那正是我这次差点走的岔路。
        self.assertIn("退出码", str(caught.exception), f"死法不对:{caught.exception}")
        self.assertIn("DS_LLM_KEY", (base / "gateway.log").read_text(encoding="utf-8"))


class TestOnlyTheGatewayGetsTheKey(unittest.TestCase):
    """J 组:**key 只进网关那条腿的环境,不进 ds-web 的**(2026-08-16 四审 BLOCK)。

    两条评审腿各自独立命中同一处:装好的应用第一次重启之后,设置里那张改 key 的卡片
    会**永久变成只读**,并且提示业主「请先清掉那个环境变量」—— 而那个变量是**外壳
    自己注入的**,业主从来没设过。

    链条:`ds_shell.py` 把 `child_env(...key=...)` 造出来的**同一份 env** 同时交给
    网关和 ds-web ⇒ ds-web 自己的 `os.environ` 里就有了 key 变量 ⇒
    `ds_credential.status()` 判成 `source="env" / writable=False` ⇒ 卡片锁死、
    `save()` 永远拒绝。**改 key / 换厂商这个 in-scope 功能在主形状上直接死亡。**

    🔴 更难看的一点(kimi 腿指出):e2e 的 G1「换 key」之所以是绿的,只因为它**直接
    起 ds-web** 且那个变量是空的 —— **装好的那套接线从来没有判据走过**。

    ⇒ ds-web 是代理,它**不消费**这把 key(只有网关按配置里的 `${VAR}` 解析它)。
    把 key 塞进 ds-web 的 env 是这次误判的唯一来源,拿掉它,H1 的只读态就回到它
    该有的语义:只有**业主自己真设过**的环境变量才会让那一格变灰。
    """

    BASE = {"PATH": "/usr/bin", "HOME": "/home/x"}

    def _envs(self, key):
        return core.service_envs(
            self.BASE, ds_root="/ds", user_home="/home/x",
            dsweb_port=8766, ws_port=8765,
            key=key, key_var="DS_LLM_KEY" if key else None, lock_port=18800)

    def test_j1_gateway_gets_the_key(self):
        envs = self._envs("sk-real-key")
        self.assertEqual(envs["网关"].get("DS_LLM_KEY"), "sk-real-key",
                         "网关拿不到 key ⇒ 它会拒绝启动(配置里是 ${DS_LLM_KEY})")

    def test_j2_ds_web_does_not(self):
        """🔴 本组的全部理由。ds-web 拿到它,业主就再也改不了 key。"""
        envs = self._envs("sk-real-key")
        self.assertNotIn("DS_LLM_KEY", envs["ds-web"],
                         "ds-web 的 env 里有 key ⇒ status() 会把外壳自注入误判成外部遮蔽 "
                         "⇒ 设置里那张卡片永久只读,而它让业主去清一个自己没设过的变量")

    def test_j3_no_key_means_neither_leg_has_it(self):
        envs = self._envs(None)
        for leg in ("网关", "ds-web"):
            self.assertNotIn("DS_LLM_KEY", envs[leg])

    def test_j4_both_legs_still_get_the_rest(self):
        """只拿掉 key,别把别的也一起拿掉 —— 两条腿仍然要拿到端口/根目录/锁端口。"""
        envs = self._envs("sk-real-key")
        for leg in ("网关", "ds-web"):
            self.assertEqual(envs[leg].get("DS_WEB_PORT"), "8766", f"{leg} 少了 DS_WEB_PORT")
            self.assertTrue(envs[leg].get("DS_ROOT"), f"{leg} 少了 DS_ROOT")

    def test_j5_the_shell_really_uses_it(self):
        """接线闸:`ds_shell.py` 必须**通过 service_envs 分发**,不能自己再拼一份 env
        交给两条腿 —— 否则上面四条全绿而真机照样锁死(「接线测试证明不了接上了」)。"""
        body = open(os.path.join(ROOT, "bin", "ds_shell.py"), encoding="utf-8").read()
        self.assertIn("service_envs", body, "ds_shell 没用 service_envs ⇒ J 组等于没接电")
        # 🔴 **正向**断言:必须把 ds-web 那份交给 ds-web。
        #    第一版写的是「不含 `web_service(env)`」—— 那是"没找到坏东西"型断言,
        #    换个写法(`web_service(envs["网关"])`)就绕过去了,红检 Q2 当场漏网。
        #    负向断言挡不住变形,正向的才钉得住。
        self.assertIn('web_service(envs["ds-web"])', body,
                      "ds-web 拿的不是它自己那份 env ⇒ 逻辑层全绿而真机照样锁死")
        self.assertIn('gateway_service(envs["网关"])', body,
                      "网关拿的不是带 key 的那份 ⇒ 它会拒绝启动")


class TestTheAckNamesTheVerb(unittest.TestCase):
    """K 组:**应答要点名动词** —— 否则"已重启"会撒谎(2026-08-16 四审 kimi 腿)。

    旧形状:`conn.sendall(self._OK)` 发生在**动词分派之前**,任何一帧都回同一个 `OK`。
    于是**认不出 RESTART 的老外壳**(它只会把窗口叫到前台)也回 `OK` ⇒ ds-web 判成
    `restart="requested"` ⇒ 界面告诉业主"已经自动应用新配置",而网关**一动没动**,
    他填的新 key 根本没生效。这正面违反本单的不变量 4「不许撒谎的重启」。

    ⇒ 应答带上动词:认出重启回 `OK RESTART-BACKEND`,其余照旧回 `OK`。
    新 ds-web 只认前者 ⇒ 碰上老外壳时**正确降级**成"请手动重启",而不是撒谎。
    (老 ds-web 碰上新外壳:它只比对 `OK` 前缀,`startswith` 仍成立,不弄坏双击图标。)
    """

    def _send(self, port: int, tail: bytes) -> bytes:
        with socket.create_connection(("127.0.0.1", port), timeout=3) as c:
            c.sendall(core.InstanceLock._HELLO + tail)
            return core.recv_line(c, deadline=time.monotonic() + 3)

    def test_k1_restart_ack_names_the_verb(self):
        base = free_port()
        restarted = threading.Event()
        lock = core.InstanceLock(base_port=base, span=5,
                                 on_show=lambda: None, on_restart=restarted.set)
        self.addCleanup(lock.release)
        self.assertTrue(lock.acquire())
        ack = self._send(lock.port, b"RESTART-BACKEND\n")
        self.assertEqual(ack, b"OK RESTART-BACKEND",
                         "应答没点名动词 ⇒ 分不出「它真认了重启」和「它只是回了个 OK」")
        self.assertTrue(restarted.wait(5))

    def test_k2_plain_show_still_gets_a_bare_ok(self):
        """双击图标那条路一个字都不许变(老实例只发 HELLO,也只该收到 OK)。"""
        base = free_port()
        shown = threading.Event()
        lock = core.InstanceLock(base_port=base, span=5,
                                 on_show=shown.set, on_restart=lambda: None)
        self.addCleanup(lock.release)
        self.assertTrue(lock.acquire())
        self.assertEqual(self._send(lock.port, b""), b"OK")
        self.assertTrue(shown.wait(5))

    def test_k3_ds_web_only_believes_the_named_ack(self):
        """ds-web 侧:只有点名动词的应答才算 requested;裸 OK(老外壳)必须回 manual。

        这条是不变量 4 的机械化:**宁可让他多点一下,也不要一句会撒谎的"已生效"**。
        """
        import ds_web
        for reply, want in ((b"OK RESTART-BACKEND", "requested"),
                            (b"OK", "manual"),
                            (b"", "manual"),
                            (b"NOPE", "manual")):
            with self.subTest(reply=reply):
                self.assertEqual(ds_web._restart_verdict(reply), want)


# ============================================== L 拿这把锁要花多久(2026-09-01)
class LockScanCost(unittest.TestCase):
    """业主真机第一次带回启动诊断:`manifest.done` 到 `lock.acquired` 之间 **9047ms**,
    而那段里只有 `InstanceLock.acquire()` 一件事。9047 / 6 个锁位 = 1507.8ms,
    写死的超时是 1500ms ⇒ **6 次握手每一次都干等到超时**(同样的扫描在 Linux 上 4.4ms)。

    B 组十几条判据把这把锁的**语义**问遍了(单实例、备用锁位、并发双击、协议分片),
    **没有一条问过它要花多久** —— 而业主感受到的、让他说"直接没反应了十几秒"的,
    正好就是这个没人问的维度。这一组补的是"代价"这一问。
    """

    def _mute_stranger(self, port: int = 0):
        """一个"连得上、但永远不回话"的监听者 —— 逼实现把**读**超时耗满。

        用 listen(8) 但不 accept:内核自己完成三次握手放进 backlog ⇒ connect 立刻成功,
        随后 recv 干等。这正是真机上每个锁位的代价形状(耗满超时),而且不用 mock。
        """
        s, p = listen_on(port)
        self.addCleanup(s.close)
        return s, p

    def test_l1_scanning_the_slots_is_concurrent_not_serial(self):
        """5 个锁位都"连得上不回话",第 6 个空着 ⇒ 仍要拿到锁,而且**别把超时挨个加起来**。

        串行实现在这里要付两轮 5×读超时(扫一遍 + 绑完再 `_someone_ahead_of` 扫一遍)
        ≈ 15s;并发实现 ≈ 一个读超时。断言 4s 是留了两倍余量的**行为**上限,
        不是掐着实现写的数字。

        ⚠️ 这条**不能靠调小读超时来满足** —— l2 把读超时钉在 ≥1.0s。两条一起才咬得住。
        """
        base = free_port()
        for off in range(5):                      # base..base+4 全是哑巴监听者
            try:
                self._mute_stranger(base + off)
            except OSError:
                self.skipTest(f"锁位 {base + off} 被本机别的程序占了,这条没法摆场子")
        lock = core.InstanceLock(base_port=base, span=5)
        self.addCleanup(lock.release)

        t0 = time.monotonic()
        got = lock.acquire()
        spent = time.monotonic() - t0

        self.assertTrue(got, "5 个锁位是陌生程序、第 6 个空着,居然没拿到锁")
        self.assertEqual(lock.port, base + 5, "没落在唯一空着的那一格")
        self.assertLess(spent, 4.0,
                        f"拿一把没人跟你抢的锁花了 {spent:.1f}s ⇒ 业主双击后就是在等这个")

    def test_l2_connect_deadline_is_short_but_the_reply_deadline_is_not(self):
        """两个超时必须**分开**,而且方向相反 —— 这是本单的核心主张,写成判据。

        · 连接可以很短:对面**活着**时,三次握手是内核在 backlog 里完成的,
          它的应用线程忙不忙、卡没卡,都不影响 connect 成功 ⇒ 短超时**漏判不了活实例**。
        · 回话不能短:那一步要对面的 `_serve` 线程真的醒过来跑一趟 ⇒ 留够。

        把两个都调小 = 用"更容易把活实例看成不存在"换速度,后果是业主开出第二份、
        两个后台抢同一份档案。所以下限和上限一起钉。
        """
        t = core.lock_timeouts()
        self.assertLessEqual(t["connect"], 0.3,
                             "连接超时还是大到要业主等 ⇒ 6 个锁位又会加起来")
        self.assertGreaterEqual(t["read"], 1.0,
                                "回话超时被顺手调小了 ⇒ 对面忙一下就被当成不存在 ⇒ 开出两份")

    def test_l3_the_implementation_actually_uses_those_numbers(self):
        """防"考卷读常量、代码写字面量":改了 `lock_timeouts()` 的返回值,握手耗时必须跟着变。

        没有这一条,l2 问的只是一个没人用的字典。
        """
        _, port = self._mute_stranger()
        lock = core.InstanceLock(base_port=port, span=0)
        real = core.lock_timeouts()

        with mock.patch.object(core, "lock_timeouts",
                               return_value={**real, "read": 0.2}):
            t0 = time.monotonic()
            lock._send_show(port)
            spent = time.monotonic() - t0
        self.assertLess(spent, 1.0,
                        f"把读超时改成 0.2s,握手还是花了 {spent:.1f}s ⇒ 实现没在读 lock_timeouts()")

    def test_l4_the_lock_records_what_it_cost(self):
        """下一趟真机不该再靠我拿两个时间戳相减、再除以 6。

        这把锁自己要说得出:扫了几个口、花了多久、最后占的是哪个。
        (`lock.acquired` 那条 mark 的 detail 就取这里。)
        """
        base = free_port()
        lock = core.InstanceLock(base_port=base, span=5)
        self.addCleanup(lock.release)
        self.assertTrue(lock.acquire())
        self.assertIsInstance(lock.scan_ms, float)
        self.assertGreaterEqual(lock.scan_ms, 0.0)
        self.assertEqual(lock.scanned, 6, "扫了几个锁位说不出来 ⇒ 诊断里那个除法还得我来做")

    def test_l5_a_missed_fast_scan_must_not_produce_a_second_instance(self):
        """快扫漏掉了活实例,也**不许**开出第二份 —— "首选锁位绑不上"是最后一道证据。

        🔴 这条不是假想出来的风险,是**量出来的**(2026-09-01,本机 200 次回环 connect,
        对面是一个正常 accept 的监听者):

            中位 0.049ms   p99 1023.510ms   最大 1060.341ms

        中位数支持"短超时够用"(0.25s 是中位的五千倍),**但那条尾巴不支持**:
        backlog 一瞬间满掉就会丢 SYN,TCP 要等约 1 秒才重传 ⇒ 0.25s 的快扫在那一刻
        看见的是"没人"。而漏判的代价是两份 OpenDesign 同时改业主一份档案。

        所以快扫不能是唯一证据。这条钉的是兜底那一层:快扫全瞎时,
        第二份**绑不到首选锁位**(第一份用 SO_EXCLUSIVEADDRUSE 占着),
        它必须据此把整段**耐心地**再问一遍,而不是径直宣布自己是唯一的。

        注入:把 connect 期限压成 0 ⇒ 实测 BlockingIOError、20 次一次都连不上,
        快扫必然全瞎。第一份在打补丁**之前**就位,所以它自己不受影响。
        """
        base = free_port()
        first = core.InstanceLock(base_port=base, span=5)
        self.addCleanup(first.release)
        self.assertTrue(first.acquire(), "场子没摆起来:第一份就没拿到锁")
        self.assertEqual(first.port, base)

        real = core.lock_timeouts()
        with mock.patch.object(core, "lock_timeouts",
                               return_value={**real, "connect": 0}):
            second = core.InstanceLock(base_port=base, span=5)
            self.addCleanup(second.release)
            self.assertFalse(
                second.acquire(),
                "快扫漏判 + 首选锁位绑不上,它还是认为自己唯一 ⇒ 业主会开出两份 OpenDesign")


if __name__ == "__main__":
    unittest.main(verbosity=2)
