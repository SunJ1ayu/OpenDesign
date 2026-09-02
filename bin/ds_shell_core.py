#!/usr/bin/env python3
"""OpenDesign 桌面外壳的平台无关内核。"""

from __future__ import annotations

import concurrent.futures
import functools
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
from dataclasses import dataclass
from pathlib import Path

import ds_common
from typing import Any


# ── 子进程创建的平台参数:唯一来源 ──────────────────────────────────────
#
# 业主 2026-08-17 装完 0.89.0:「为什么打开这个软件还会跳出命令行呢」——
# 两个黑窗口(网关一个、工作台一个),而且**关掉一个就等于杀掉一条腿**。
# 外壳自己是没有控制台的 `pythonw.exe`,却用 `python.exe`(控制台程序)起腿:
# **没有控制台的进程去起控制台程序,Windows 会为它新开一个控制台窗口。**
#
# 🔴 数值写死,不用 `getattr(subprocess, "CREATE_NO_WINDOW", 0)`:
#    Linux 的 subprocess **没有**这两个常量,getattr 会退化成 0,
#    而 0 和"没设"一模一样 ⇒ 本机判据永远问不出东西(假绿)。
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
WINDOWS_SPAWN_FLAGS = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW


def spawn_kwargs(os_name: str = "") -> dict[str, Any]:
    """起子进程时要额外传给 `subprocess` 的平台参数 —— **唯一来源**。

    调用点不许自己拼:漏一位的代价是真机上冒一个业主关得掉的黑窗口,
    而本机一条判据都不会红(那一位只在 Windows 上有意义)。
    `tests/test_no_console_window.py` 机械地查"每个创建点是不是走了这儿"。
    """
    name = os_name or os.name
    if name == "posix":
        # 自成会话 ⇒ 收尸时按进程组收,孙进程跑不掉(c1/c2/c13 咬的就是它)
        return {"start_new_session": True}
    if name == "nt":
        return {"creationflags": WINDOWS_SPAWN_FLAGS}
    return {}


class PortBusy(RuntimeError):
    """端口段全被占。"""


class StartupFailed(RuntimeError):
    """子进程启动失败。"""


class ConfigUnusable(RuntimeError):
    """配置本身无法安全使用。"""


def port_free(port: int, host: str = "127.0.0.1") -> bool:
    """端口是否可以被当前进程绑定。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, int(port)))
        return True
    except OSError:
        return False
    finally:
        s.close()


def port_listening(port: int, host: str = "127.0.0.1") -> bool:
    """端口上是否有 TCP 服务正在接受连接。"""
    try:
        with socket.create_connection((host, int(port)), timeout=0.25):
            return True
    except OSError:
        return False


def pick_port(preferred: int, *, span: int = 20) -> int:
    start = int(preferred)
    for port in range(start, start + int(span) + 1):
        if port_free(port):
            return port
    raise PortBusy(f"端口段 {start}..{start + int(span)} 全部被占")


def pick_ports(preferred: list[int], *, span: int = 20) -> list[int]:
    chosen: list[int] = []
    used: set[int] = set()
    for wanted in preferred:
        start = int(wanted)
        for port in range(start, start + int(span) + 1):
            if port not in used and port_free(port):
                chosen.append(port)
                used.add(port)
                break
        else:
            raise PortBusy(f"端口段 {start}..{start + int(span)} 没有可用端口")
    return chosen


def lock_sockopts(platform: str) -> list[tuple[str, int]]:
    """这个平台上,单实例锁的 socket 该设哪些选项。纯数据 —— 好让考卷问得出来。

    ⚠️ 兜底值必须是 Windows 上的真值 `-5`(= ~SO_REUSEADDR),**不能随手写 4**:
    4 在 Linux 上正好是 SO_REUSEADDR —— 恰恰是这把锁一辈子都不许设的那一个
    (Windows 上它允许后来者抢走监听端口 ⇒ 锁会被偷)。兜底写错方向 = 埋雷。
    """
    if platform.startswith("win"):
        return [("SO_EXCLUSIVEADDRUSE", int(getattr(socket, "SO_EXCLUSIVEADDRUSE", -5)))]
    return []


def lock_timeouts() -> dict[str, float]:
    """握手的两个期限。纯数据 —— 和 `lock_sockopts` 一个用意:好让考卷问得出来。

    **两个都是 1.5s,而且都不许再往下调。** 考卷 l2 钉着这条下限。

    🔴 这里曾经写着相反的话("connect 可以很短,因为对面活着时握手由内核在 backlog
    里完成"),并据此把 connect 缩到 0.25s。**那半句是错的,而且错法是可量的**
    (2026-09-01,三条评审腿里两条 BLOCK,加我自己共四次独立复现):

        本机 200 次回环 connect(对面**正常 accept**),见
        tracks/opendesign-slow-lock-scan/probes/connect_latency.py:
            中位 0.056ms   p99 1022.975ms   max 1023.173ms

    内核确实在 backlog 里完成握手 —— 但 backlog 一瞬间满掉就会丢 SYN,
    TCP 要等约 1 秒才重传。所以"对面活着 ⇒ connect 一定快"只在中位数上成立,
    **尾巴上不成立**。1.5s 罩得住整条实测尾巴,0.25s 罩不住 ⇒ 每次触发条件成立时
    约 1~3% 的概率把**活着的**第一份看成不存在 ⇒ 业主开出两份、两个后台对着
    同一个 data_root(评审腿查过:`pick_ports(span=20)` 会让第二份换端口照跑,
    没有第二层保护)。

    **那 9 秒是靠并发省下来的,不是靠缩这个期限:**
        串行 1.5s            9001ms   ← 探针模型,对上业主真机 9047ms
        并发 + connect=1.5   1501ms   快 6.0 倍,省 7.5s
        并发 + connect=0.25   252ms   只多省 1.25s
    为那 1.25s 把数据面赌进去不划算,所以这一单**只要并发那一份收益**。

    由来:2026-09-01 业主真机第一份启动诊断。此前两个期限都是 1.5s,而且**串行**扫
    6 个锁位;他那台机器上每个锁位都耗满 ⇒ `manifest.done` 到 `lock.acquired`
    干等 **9047ms**,占整趟启动 11031ms 的 82%。他的原话是"直接没反应了十几秒"。
    (同样的扫描在本机 Linux 上是**毫秒级**:20 次扫 6 个空锁位,中位 0.9ms、max 4.0ms,
     收据 evidence/20260902T010857Z-01-empty-range-baseline-and-blackhole.txt;
     单遍会跳,另一遍是 1.1 / 4.6 —— 别引用具体值,量级才是结论。
     空端口瞬间被拒;Windows 上为什么耗满,
    见 tracks/opendesign-slow-lock-scan/proposal.md 的"还不知道的"。)

    ⚠️ 想把 connect 调回去,先在**那台 Windows** 上量一遍 connect_latency ——
    上面这组数来自 Linux,而那台机器的回环行为已经被证明和 Linux 不一样。
    """
    return {"connect": 1.5, "read": 1.5}


# 锁通道的线上协议。**公开常量,因为 ds_web 也要发这个帧** ——
# 两处各抄一份的代价我付过(见 ports_for 那段注释),这里只留一个真相源。
LOCK_HELLO = b"OpenDesign.ds_shell_core.lock.v1\n"
LOCK_SHOW = b"SHOW\n"
LOCK_RESTART = b"RESTART-BACKEND\n"     # 业主填完 key ⇒ 网关得重来一次才认新 env
LOCK_OK = b"OK\n"
# 🔴 应答**点名动词**:老外壳认不出 RESTART 也会回裸 OK,ds-web 就会把
#    "什么都没重启"报成 requested,界面对业主说「已自动应用新配置」——
#    正面违反「不许撒谎的重启」。带上动词,新 ds-web 碰上老外壳时才能
#    **正确降级**成"请手动重启"。(老 ds-web 碰上新外壳无碍:它比对的是前缀。)
LOCK_OK_RESTART = b"OK RESTART-BACKEND\n"


def recv_line(sock: socket.socket, deadline: float, limit: int = 4096) -> bytes:
    """读到第一个换行为止(不含换行);超时或对端关闭就返回已经读到的。

    模块级是因为 ds_web 那侧发完重启帧也要读这一行应答 —— 收发行的规矩只留一份。
    """
    buf = b""
    while b"\n" not in buf and len(buf) < limit:
        remain = deadline - time.monotonic()
        if remain <= 0:
            break
        sock.settimeout(remain)
        try:
            chunk = sock.recv(limit)
        except OSError:
            break
        if not chunk:
            break
        buf += chunk
    return buf.split(b"\n", 1)[0]


class InstanceLock:
    _HELLO = LOCK_HELLO
    _SHOW = LOCK_SHOW
    _RESTART = LOCK_RESTART
    _OK = LOCK_OK
    _OK_RESTART = LOCK_OK_RESTART

    port: int | None
    _sock: socket.socket | None

    def __init__(self, base_port: int, span: int = 5, on_show=None, on_restart=None):
        self.base_port = int(base_port)
        self.span = int(span)
        self.on_show = on_show
        self.on_restart = on_restart
        self.port = None
        self._sock = None
        self._thread: threading.Thread | None = None
        self._released = threading.Event()
        # 这把锁自己花了多少 —— 下一趟真机不该再靠人拿两个时间戳相减、再除以锁位数。
        # `scanned` 是**握手总次数**(两轮就是两轮之和),好让 `scan_ms / scanned`
        # 真的等于每格代价;`scan_ms` 是整个 `acquire()` 的墙钟。
        self.scan_ms: float = 0.0
        self.scanned: int = 0

    def acquire(self) -> bool:
        """True = 我是唯一实例(并已开始监听);False = 已有实例(SHOW 已送到)。"""
        t0 = time.monotonic()
        try:
            return self._acquire()
        finally:
            self.scan_ms = (time.monotonic() - t0) * 1000.0

    def _acquire(self) -> bool:
        # 第一份可能落在备用锁位上,所以先扫完整段握手,再尝试占新锁。
        hit = self._scan(self._ports())
        if hit is not None:
            self.port = hit
            return False

        for port in self._ports():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                for name, value in lock_sockopts(sys.platform):
                    opt = getattr(socket, name, None)
                    if opt is not None:
                        sock.setsockopt(socket.SOL_SOCKET, opt, value)
                sock.bind(("127.0.0.1", port))
                sock.listen(8)
            except OSError:
                sock.close()
                continue
            self._sock = sock
            self.port = port
            self._thread = threading.Thread(target=self._serve, name="ds-shell-lock", daemon=True)
            self._thread.start()

            # 🔴 并发裁决(业主快速双击两下走的就是这里)。
            # 上面那轮扫描解决不了同时启动:两份都会扫到"没人",然后一个绑 base、
            # 一个绑 base+1,**两份都以为自己是唯一的**。
            # 绑完再回头扫一次比自己**更靠前**的锁位:能应答的说明有人比我先站住了,
            # 我让位。因为"最靠前的那一格"只可能被一个人占住,所以恰好活下来一个,
            # 也不会两边互相让(让位只朝一个方向)。
            if self._someone_ahead_of(port):
                self.release()
                self.port = port
                return False
            return True

        raise PortBusy(f"单实例锁端口段 {self.base_port}..{self.base_port + self.span} 全部被占")

    def _someone_ahead_of(self, mine: int) -> bool:
        """我前面还有人吗 —— 并发启动时的**让位仲裁**。

        🔴 **它不是"快扫漏判"的兜底,别再这么用了**(2026-09-01 评审推翻的第二句话)。
        我曾在这里写"它是快扫漏判时的唯一兜底",三条评审腿里两条独立指出这是错的,
        而且拓扑摆在那儿:这一问只看 `p < mine`,所以**先起的那份落在比我更高的锁位时,
        这里一个口都不会问**。漏判最脆的那条路正好长这样 ——
        陌生程序占着 base ⇒ 第一份落到 base+1 ⇒ 陌生程序退出 ⇒
        第二份漏判、绑上 base ⇒ 走到这里前面没有锁位 ⇒ 放行 ⇒ **两份并存**。

        改成"整段都问"是不行的 —— **两份同时启动时会双向让位**:我问你、你问我,
        两边都让,业主双击后一个窗口都不开,比开两份更难看。
        (让位方向必须唯一,这正是"只问更靠前的"存在的理由。)

        🔴 这个数以前是"3 轮里有 1 轮",而**仓库里复现不出来** —— 2026-09-02 第二轮
        评审的两条腿各自独立指出:它是驳回这条修法的全部依据,却只活在这句注释里。
        补了探针 `tracks/opendesign-slow-lock-scan/probes/yield_race.py`,量的是一笔
        **取舍**(盲区堵不堵得住 × 同时启动活下来几份),三组实现、每组 30 轮:

            A 只问 p < mine(树上这个) 盲区**放行**   0 存活 0/30(三遍都是 0)
            B 绑完问整段(评审建议的)  盲区堵住      0 存活 18/30、10/30、9/30
            C 只让 base 上那份回头问   盲区堵住      0 存活 13/30、9/30

        C 是我自己构造来攻"B 是不是稻草人"的最强变体 —— **它确实更强**(盲区照堵,
        而非 base 一侧的让位方向仍唯一),**但照样出现 0 存活**。
        ⇒ 结论不是"某个数是多少",是**结构性的**:光靠"问谁在监听"分不出
        "对面已经站住了" 和 "对面正和我同时启动",所以三组都做不到两件事兼得。
        真修法要给锁协议加先来后到字段 —— track `opendesign-lock-seniority-field`。

        ⚠️ **别引用其中任何一个比例**:同一支探针三遍给出 60% / 33% / 30%,方差很大
        (我 2026-09-02 上午一度把 18/30 写成"实测 60%、比原话严重一倍",下一遍就 30% ——
        单次抽样当结论,那是我自己规矩里禁的那件事)。**稳的是三件定性事实**:
        A 从没出现过 0 存活;B/C 每一遍都出现;盲区那一格三组的结果每遍都一样。
        探针还是同进程两线程 + Linux 回环,竞争窗口宽度和业主那台 Windows 上的两个进程
        不一样,所以这些比例更不能当成他那台机器上的概率。
        要真堵那条路,得给锁协议加一个先来后到的判据字段 —— 那是另一单。

        **所以现在防线在前面:快扫的 connect 期限必须罩得住实测尾巴(l2 钉着下限)**,
        让"漏判"这个前提本身够不着。`patient` 保留:它在 connect 被调短时自动重新
        生效(l5 靠注入 connect=0 钉着它),今天两个期限一样宽,它是空操作。

        代价只落在**罕见**分支上:绑到首选锁位时这里一个口都不用问(前面没有锁位),
        业主每次启动付的仍然只有一轮快扫。
        """
        # 这是**第二轮**整段扫描 —— 串行时代业主为一次启动付的是两轮超时
        # (考卷 l1 量到 15.0s,正是 5 个哑巴锁位 × 1.5s × 两轮)。
        return self._scan((p for p in self._ports() if p < mine), patient=True) is not None

    def _scan(self, ports, patient: bool = False) -> int | None:
        """并发对一段锁位握手,返回**最靠前**那个应答 OK 的锁位(没有就 None)。

        为什么必须并发:每个锁位在最坏情况下都要耗满超时,而**串行会把它们加起来**。
        业主真机上 6 个锁位一个都不肯快速失败 ⇒ 9047ms,他看到的就是"双击了没反应"。
        并发之后整段的代价 = **一个**超时,不再随锁位数量增长。

        顺序语义保持不变:`pool.map` 按入参顺序返回,所以仍然是"最靠前的那个赢" ——
        并发裁决(绑完回头看有没有人比我更靠前)靠的就是这个方向唯一。

        ⚠️ 与串行的唯一行为差异:串行遇到第一个应答就不再往下问,并发是整段都问一遍
        ⇒ 万一真有两份在跑(那本身是 bug),两份都会被叫到前台。已知且可接受:
        单实例世界里最多只有一份,而"多叫醒一个窗口"不伤数据。
        """
        ports = list(ports)
        # 🔴 **累加,不是取最大**:第二轮(`_someone_ahead_of`)扫的永远是第一轮的子集,
        #    取 max 会让这个字段恒等于 span+1、把兜底那一轮整个吞掉 —— 而 `scan_ms`
        #    是含两轮的墙钟 ⇒ 业主拿它一除,每格代价放大 1.5 倍。判据 l6 钉住
        #    "字段 == 握手函数真被调用的次数"(2026-09-01 接手复核)。
        self.scanned += len(ports)
        if not ports:
            return None
        probe = functools.partial(self._send_show, patient=patient)
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=len(ports), thread_name_prefix="ds-shell-lock-scan") as pool:
            answered = list(pool.map(probe, ports))
        for port, ok in zip(ports, answered):
            if ok:
                return port
        return None

    def release(self) -> None:
        """放开锁,并且**立刻**不再应答握手。

        只 close() 是不够的:服务线程这时正阻塞在旧 socket 的 accept() 里,而关掉一个
        正被 accept 阻塞的 socket 并不保证把它叫醒(Linux 实测不醒,Windows 同样不保证)。
        于是下一次握手连进来时 accept 才返回、线程照样回了个 OK ⇒ **锁已经放开了,
        新实例却被告知"已有一份在跑"**,业主看到的是双击图标没反应。

        叫醒的办法:先 shutdown() 断开监听,再自连一次把可能仍阻塞的 accept 顶出来。
        """
        self._released.set()
        sock = self._sock
        port = self.port
        self._sock = None
        self.port = None
        if sock is None:
            return
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass          # 监听 socket 上 shutdown 在有的平台直接报错,不影响下一步
        if port:
            try:          # 自连一次:把仍卡在 accept 里的线程顶出来(它一醒就看见 _released)
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    pass
            except OSError:
                pass
        try:
            sock.close()
        except OSError:
            pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _ports(self):
        return range(self.base_port, self.base_port + self.span + 1)

    def _send_show(self, port: int, patient: bool = False) -> bool:
        """连上去握一次手。对上了 = 那边是另一份 OpenDesign(SHOW 已送到)。

        收发都**循环读到整行**:TCP 没有消息边界,一次 recv 恰好等于整帧只是回环上的
        运气;分片就把真实例认成陌生人 ⇒ 开出第二份。
        """
        t = lock_timeouts()
        # patient=True:连接也用回话那个宽期限。只有 `_someone_ahead_of` 走这条 ——
        # 那一刻我们已经知道"锁位被占而快扫没问出来",短期限不该再被信任。
        connect_deadline = t["read"] if patient else t["connect"]
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=connect_deadline) as s:
                s.settimeout(t["read"])
                s.sendall(self._HELLO + self._SHOW)
                return self._recv_line(
                    s, deadline=time.monotonic() + t["read"]) == self._OK.strip()
        except OSError:
            return False

    _recv_line = staticmethod(recv_line)

    def _serve(self) -> None:
        # 捞一份本地引用:release() 会把 self._sock 置 None,再用 self._sock 就是 AttributeError。
        sock = self._sock
        if sock is None:
            return
        while not self._released.is_set():
            try:
                conn, _ = sock.accept()
            except OSError:
                break
            # 醒来之后**再问一次**:release() 的自连就是来顶醒我的,
            # 而这一刻锁已经放开了 —— 这时候还回 OK,就等于替一把不存在的锁挡人。
            if self._released.is_set():
                conn.close()
                break
            # 每条连接单独一个线程处理。**不许在主循环里同步处理**:
            # 端口扫描器(或任何连上就不说话的东西)会把这个循环堵住,而这段时间里
            # 第二个实例握手会超时、把真实例当成陌生人 ⇒ 开出第二份 OpenDesign。
            threading.Thread(target=self._handle, args=(conn,),
                             name="ds-shell-lock-conn", daemon=True).start()

    @classmethod
    def _recv_frame(cls, sock: socket.socket, deadline: float,
                    settle: float = 0.35, limit: int = 4096) -> tuple[bytes, bytes]:
        """读一整帧:第一行 HELLO,第二行动词(**可能没有**)。

        🔴 为什么不能连着调两次 `_recv_line`:那个函数每次都从 socket 重新读,
        **把同一个包里多出来的部分丢掉**。而 HELLO 和动词几乎总在同一个包里到达
        ⇒ 分两次读会把动词连缓冲一起扔了,然后干等第二行到超时。

        只发了 HELLO 的老实例(以及升级瞬间还在跑的那份)必须照常工作:
        第一行到手后只再宽限 `settle`,拿不到动词就按"没有动词"处理。
        """
        buf = b""
        grace: float | None = None
        while len(buf) < limit and buf.count(b"\n") < 2:
            now = time.monotonic()
            if buf.count(b"\n") >= 1 and grace is None:
                grace = now + settle
            remain = (min(deadline, grace) if grace is not None else deadline) - now
            if remain <= 0:
                break
            sock.settimeout(remain)
            try:
                chunk = sock.recv(limit)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
        parts = buf.split(b"\n")
        return parts[0], (parts[1] if len(parts) > 1 else b"")

    def _handle(self, conn: socket.socket) -> None:
        verb = b""
        with conn:
            try:
                head, verb = self._recv_frame(conn, deadline=time.monotonic() + 2.0)
                if not head.startswith(self._HELLO.strip()):
                    return
                if self._released.is_set():
                    return
                # 先认动词再决定回什么 —— 回裸 OK 就等于说"我收到了"而不说"我认了什么"
                is_restart = verb.strip() == self._RESTART.strip()
                conn.sendall(self._OK_RESTART if is_restart else self._OK)
            except OSError:
                return
        # 动词分派。**认不出的一律退回 SHOW**:重启会掐断他正在进行的对话,
        # 而把窗口叫到前台最多是打扰一下 ⇒ 拿不准时选那个不伤人的。
        cb = self.on_restart if is_restart else self.on_show
        if cb is not None:
            cb()


@dataclass
class Service:
    name: str
    argv: list[str]
    env: dict
    ready_port: int
    log_path: Path
    ready_timeout: float = 60.0
    # 可选的身份探针:收到 ready_port 后再问一句"听这个端口的真是你吗"。
    # "端口有人听"只说明有人听 —— 陌生进程抢在中间那一瞬占了端口,一样是绿的。
    # ds-web 用 /api/health 自报版本;不给探针就退化成只看端口。
    ready_probe: Any = None


@dataclass
class _Managed:
    service: Service
    proc: subprocess.Popen
    log_file: Any
    job_handle: Any = None
    pgid: int | None = None      # POSIX:开跑时记下进程组,别等父进程死了才去问


class Supervisor:
    def __init__(self):
        self._children: list[_Managed] = []
        self._shutdown_lock = threading.Lock()

    def start(self, services: list[Service]) -> None:
        ports = [int(s.ready_port) for s in services]
        if len(set(ports)) != len(ports):
            raise StartupFailed(f"服务端口重复: {ports}")
        for svc in services:
            if not port_free(int(svc.ready_port)):
                raise StartupFailed(f"{svc.name} 的端口 {svc.ready_port} 已被占用")

        try:
            for svc in services:
                child = self._spawn(svc)
                self._children.append(child)
                self._wait_ready(child)
            # 全部就绪之后再点一次名:等后面那条腿的这段时间里,前面的可能已经崩了。
            # 少了这一下,业主看到的是"窗口正常打开、聊天永远连不上、而且没有任何报错"。
            dead = self.poll_dead()
            if dead:
                raise StartupFailed(self._failure_message(
                    self._by_name(dead[0]).service, "起来之后又退出了",
                    self._by_name(dead[0]).proc.poll()))
        except BaseException:
            # 不只接 StartupFailed:建日志目录失败之类会抛 OSError,
            # 接不住就把已经起好的腿丢在那儿变成孤儿(业主下次打开撞端口,还查不出是谁)。
            self.shutdown()
            raise

    def restart(self, services: list[Service]) -> None:
        """把点名的几条腿换成新的(通常只是换了 env),**其余腿一动不动**。

        业主填完 key 之后要走的就是这条路:网关只在启动时读一次环境变量,
        不换一个新进程就永远认不到新 key。而 ds-web **不能**跟着换 ——
        他正看着的那个页面就是 ds-web 发的。

        与 `start()` 的差别是故意的,别照抄那边:start 半路失败会把已起的全停掉
        (半拉子启动没有意义);这里失败**不许连坐** —— 界面没有理由陪葬,
        而且他得看得见"重启失败"这句话。
        
        🔴 **不持 `_shutdown_lock` 是有意的取舍**(08-17 四审两腿都提):
        托盘"退出"和这里交错时,新起的网关可能落在 `shutdown()` 的名册快照之后
        ⇒ 理论上留一个孤儿。没加锁是因为 `shutdown()` 持的是同一把,重启途中
        点退出会让业主干等到 300s 超时 —— 这个仓库有过"重入即永久挂死"的先例。
        Windows 上外壳退出时 Job 的 KILL_ON_JOB_CLOSE 会兜底,窗口只有毫秒宽。
        **下一个想加锁的人:先把 shutdown 那侧的等待改成可中断的,再动这里。**
        """
        names = {s.name for s in services}
        old = [c for c in self._children if c.service.name in names]
        # 🔴 **先除名,再动手**(判据 c19)。反过来写会留下一个窗口:旧腿已经被杀、
        # 却还挂在名册上 —— 看门狗每 3 秒问一次 `poll_dead()`,问在这个窗口里就会
        # 弹「网关意外退出了,请退出后重新打开」,而那一刻其实是**正常重启**,
        # 而且那句指令(退出后重开)恰好会打断正在进行的重启。
        self._children = [c for c in self._children if c not in old]
        for child in old:
            self._terminate_tree(child)
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline:
            if all(c.proc.poll() is not None for c in old):
                break
            time.sleep(0.05)
        # 🔴 收尸要走**和 shutdown 同一套**(判据 c18)。少了这一步,Windows 上
        # `_terminate_tree` 只 terminate 了 nanobot 本尊,它带的 3 个 MCP 工具服务
        # 留在 Job 里没人收 —— 关 Job(KILL_ON_JOB_CLOSE)才是那边收整棵树的机制。
        # Linux 看不出来:那边 `_terminate_tree` 打的是整个进程组,孙子跟着一起走。
        # 业主每按一次"保存 key",机器上就多 3 个孤儿。
        for child in old:
            self._kill_tree(child)
            self._close_job(child)
            try:
                child.log_file.close()
            except Exception:
                pass

        for svc in services:
            # 端口得**真的还回来**再起新的。少这一步,新进程 bind 失败,
            # 而业主看到的症状是"点了保存,什么也没发生"。
            port_deadline = time.monotonic() + 5.0
            while not port_free(int(svc.ready_port)):
                if time.monotonic() > port_deadline:
                    raise StartupFailed(
                        f"{svc.name} 的端口 {svc.ready_port} 一直没释放,没能重启")
                time.sleep(0.05)
            child = self._spawn(svc)
            self._children.append(child)
            try:
                self._wait_ready(child)
            except BaseException:
                # 只收自己这一条,别动别人(上面那段 docstring 的"不连坐"就在这儿落地)。
                # 🔴 08-17(四审 subkimi F-2,判据 c22):收尸要走**和上面收旧腿
                # 完全同一套**。这里原来只有 `_terminate_tree` —— Windows 上那等于
                # 只杀了 nanobot 本尊,它带的 3 个 MCP 留在 Job 里没人收
                # (KILL_ON_JOB_CLOSE 不触发),外壳里每失败一次还漏一个日志句柄。
                # 同一个函数里两条路不一致,c18 只钉住了旧腿那一半。
                self._kill_tree(child)
                self._close_job(child)
                try:
                    child.log_file.close()
                except Exception:
                    pass
                self._children = [c for c in self._children if c is not child]
                raise

    def shutdown(self) -> None:
        with self._shutdown_lock:
            children = list(self._children)
            if not children:
                return

            for child in children:
                self._terminate_tree(child)

            deadline = time.monotonic() + 4.0
            while time.monotonic() < deadline:
                if all(child.proc.poll() is not None for child in children):
                    break
                time.sleep(0.05)

            for child in children:
                # posix 上即使父进程已经死了也要再 KILL 一遍进程组:
                # 活着的可能只剩孙进程,而 poll() 问的只是父进程。
                if child.proc.poll() is None or child.pgid or child.job_handle:
                    self._kill_tree(child)

            final_deadline = time.monotonic() + 4.0
            for child in children:
                remaining = max(0.0, final_deadline - time.monotonic())
                try:
                    child.proc.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    pass

            # 直接子进程死了 ≠ 收干净了:孙进程(nanobot 的 3 个 MCP)还要一会儿才落地,
            # 而它们手里攥着端口。这里等**整个进程组**真的空掉再返回 ——
            # 否则业主点完"退出"马上再双击,新的一份会撞在还没放开的端口上。
            group_deadline = time.monotonic() + 3.0
            while time.monotonic() < group_deadline:
                if all(self._group_gone(c) for c in children):
                    break
                time.sleep(0.05)

            for child in children:
                self._close_job(child)
                try:
                    child.log_file.close()
                except Exception:
                    pass
            self._children.clear()

    def take_dead(self) -> list[tuple[str, str]]:
        """死掉的腿:**名字和死因一次拿全**(判据 c21)。

        看门狗以前分两眼看 —— 先 `poll_dead()` 问"谁死了",再 `dead_reports()`
        问"为什么"。两眼之间名册会变(业主恰好在这一刻存了 key、触发重启),
        于是第一眼有名字、第二眼没了原因 ⇒ 弹窗照弹「网关意外退出了」,
        日志里一个原因都没有 —— **c20 刚消灭掉的那种没线索的弹窗,换个入口又长回来。**
        (08-17 四审 subdeepseek F5。)

        修法不是加锁:`shutdown()` 持的是 `_shutdown_lock`,重启途中再互等
        风险更大。一次遍历、一份快照就够 —— 名册的**那一瞬**是自洽的。
        `list(...)` 是同一件事的另一半:遍历途中被 restart 改名册不许抛。
        """
        out = []
        for child in list(self._children):
            code = child.proc.poll()
            if code is None:
                continue
            out.append((child.service.name,
                        self._failure_message(child.service, "", code, what="意外退出了")))
        return out

    def poll_dead(self) -> list[str]:
        return [name for name, _ in self.take_dead()]

    def dead_reports(self) -> list[str]:
        """死掉的腿**为什么**死 —— 每条一段人话:退出码 + 那条腿日志的尾巴。

        🔴 2026-08-16 业主真机欠的就是这个。当时外壳只说了一句
        「网关 意外退出了。请退出后重新打开」,而网关自己的日志最后一句是
        `Agent loop started`,之后什么都没有。两份日志摆在面前,我也答不了
        「它是被杀的还是自己崩的」—— 因为**退出码从来没被打印过**。
        退出码分得清这两件事(被杀 vs 自己退),日志尾巴给的是崩在哪。

        看门狗现在走 `take_dead()`(名字和原因同一眼);这个留给只要原因的调用方。
        """
        out = []
        for _, said in self.take_dead():
            out.append(said)
        return out

    @staticmethod
    def _group_gone(child: _Managed) -> bool:
        """这条腿的进程组是不是真的空了(信号 0 = 只探不杀)。

        Windows 没有便宜的等价问法(Job 关掉就算数),那边只看直接子进程。
        """
        if os.name != "posix" or not child.pgid:
            return child.proc.poll() is not None
        try:
            os.killpg(child.pgid, 0)
            return False
        except OSError:
            return True

    def _by_name(self, name: str) -> _Managed:
        return next(c for c in self._children if c.service.name == name)

    def _spawn(self, svc: Service) -> _Managed:
        log_path = Path(svc.log_path)
        try:
            # 开日志也会失败(路径被占、没权限)。包成 StartupFailed,
            # 免得调用方只接 StartupFailed 时漏掉这条路,把兄弟腿丢成孤儿。
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = log_path.open("ab")
        except OSError as exc:
            raise StartupFailed(f"{svc.name} 起不来:日志写不了({log_path}):{exc}") from exc
        kwargs: dict[str, Any] = {
            "stdout": log_file,
            "stderr": subprocess.STDOUT,
            "env": {str(k): str(v) for k, v in svc.env.items()},
        }
        kwargs.update(spawn_kwargs())
        try:
            proc = subprocess.Popen([str(x) for x in svc.argv], **kwargs)
        except Exception as exc:
            try:
                log_file.close()
            except Exception:
                pass
            raise StartupFailed(f"{svc.name} 启动失败: {exc}") from exc
        child = _Managed(service=svc, proc=proc, log_file=log_file)
        if os.name == "posix":
            # 开跑时就把进程组记下来。等到收摊时才去问就晚了:
            # 组长(nanobot 父进程)可能已经死了,而它的 3 个 MCP 孙进程还活着 ——
            # 那时候 os.getpgid(pid) 已经问不到,进程组就永远没人收。
            try:
                child.pgid = os.getpgid(proc.pid)
            except OSError:
                child.pgid = proc.pid
        elif os.name == "nt":
            child.job_handle = self._assign_windows_job(proc)
        return child

    def _wait_ready(self, child: _Managed) -> None:
        svc = child.service
        deadline = time.monotonic() + float(svc.ready_timeout)
        while True:
            # 盯的是**所有**已起的腿,不只当前这条:前面那条先就绪、随后崩掉的话,
            # 只盯当前这条会让 start() 一路绿到底(攻题二轮 HIGH#3)。
            for other in self._children:
                code = other.proc.poll()
                if code is not None:
                    raise StartupFailed(self._failure_message(
                        other.service, f"退出码 {code}", code))
            if port_listening(int(svc.ready_port)) and self._probe_ok(svc):
                return
            now = time.monotonic()
            if now >= deadline:
                raise StartupFailed(self._failure_message(svc, "启动超时", None))
            time.sleep(min(0.1, max(0.0, deadline - now)))

    @staticmethod
    def _probe_ok(svc: Service) -> bool:
        if svc.ready_probe is None:
            return True
        try:
            return bool(svc.ready_probe(int(svc.ready_port)))
        except Exception:
            return False      # 探针自己炸了 = 还没就绪,不是就绪

    def _failure_message(self, svc: Service, reason: str, code: int | None,
                         what: str = "启动失败") -> str:
        tail = self._log_tail(Path(svc.log_path))
        parts = [f"{svc.name} {what}: {reason}" if reason else f"{svc.name} {what}"]
        if code is not None:
            parts.append(f"退出码: {code}")
        parts.append(f"日志尾巴:\n{tail}")
        return "\n".join(parts)

    def _log_tail(self, path: Path, limit: int = 4000) -> str:
        try:
            with path.open("rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - limit))
                data = f.read()
            text = data.decode("utf-8", errors="replace").strip()
            return text or "(日志为空)"
        except OSError:
            return "(读不到日志)"

    # 🔴 下面两个**不许**因为 "poll() 非 None 就直接 return"。
    # 父进程先死、孙进程还活着,是 nanobot 最真实的一种残局(它自己拉起 3 个 MCP):
    # 那时候整个进程组还在,而"父进程已经死了"恰恰让收割整段被跳过 ⇒
    # 业主机器上留下几个占着端口的孤儿,看不出是谁,下次打开就撞端口。
    def _terminate_tree(self, child: _Managed) -> None:
        if os.name == "posix":
            if child.pgid:
                try:
                    os.killpg(child.pgid, signal.SIGTERM)
                except OSError:
                    pass          # 组已经空了:正常
            return
        if child.proc.poll() is None:
            try:
                child.proc.terminate()
            except Exception:
                pass

    def _kill_tree(self, child: _Managed) -> None:
        if os.name == "posix":
            if child.pgid:
                try:
                    os.killpg(child.pgid, signal.SIGKILL)
                except OSError:
                    pass
            return
        # Windows:关掉 Job 就等于收掉整棵树(KILL_ON_JOB_CLOSE)——
        # 父进程已经死了也照关,道理同上(孙进程还在这个 Job 里)。
        if child.job_handle:
            self._close_job(child)
            return
        if child.proc.poll() is not None:
            return
        try:
            # 没挂上 Job 时的退路:taskkill /T 连子孙一起杀。
            # 它也是控制台程序 ⇒ 平台参数走同一个来源,否则每收一次尸闪一个黑窗口。
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(child.proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
                **spawn_kwargs("nt"),
            )
            return
        except Exception:
            pass
        try:
            child.proc.kill()
        except Exception:
            pass

    def _assign_windows_job(self, proc: subprocess.Popen):
        if os.name != "nt":
            return None
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            # ⚠️ 必须显式声明 HANDLE 的类型。ctypes 默认把返回值当 c_int(32 位),
            # 而 64 位 Windows 上句柄是 64 位 ⇒ **句柄被静默截断**,后面
            # AssignProcessToJobObject / CloseHandle 打在一个不存在的句柄上,
            # 于是"整棵进程树跟着一起收"这条防线悄悄失效,而且一声不响。
            # 这一处 Linux 上一行都跑不到,只能靠读代码抓(闸③),已进真机考卷。
            kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
            kernel32.SetInformationJobObject.restype = wintypes.BOOL
            kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                        wintypes.LPVOID, wintypes.DWORD]
            kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
            kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            job = kernel32.CreateJobObjectW(None, None)
            if not job:
                return None

            class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
                    ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD),
                ]

            class IO_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("ReadOperationCount", ctypes.c_ulonglong),
                    ("WriteOperationCount", ctypes.c_ulonglong),
                    ("OtherOperationCount", ctypes.c_ulonglong),
                    ("ReadTransferCount", ctypes.c_ulonglong),
                    ("WriteTransferCount", ctypes.c_ulonglong),
                    ("OtherTransferCount", ctypes.c_ulonglong),
                ]

            class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]

            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            ok = kernel32.SetInformationJobObject(
                job, 9, ctypes.byref(info), ctypes.sizeof(info)
            )
            if not ok:
                kernel32.CloseHandle(job)
                return None
            if not kernel32.AssignProcessToJobObject(job, proc._handle):
                kernel32.CloseHandle(job)
                return None
            return job
        except Exception:
            return None

    def _close_job(self, child: _Managed) -> None:
        if os.name != "nt" or not child.job_handle:
            return
        try:
            import ctypes
            from ctypes import wintypes

            # 同上:不声明 argtypes,64 位句柄会被截成 32 位 ⇒ 关的是别的东西,
            # 而 KILL_ON_JOB_CLOSE 那条命就白挂了(这一处是第二个现场,别只修一个)。
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.CloseHandle.restype = wintypes.BOOL
            k32.CloseHandle.argtypes = [wintypes.HANDLE]
            k32.CloseHandle(child.job_handle)
        except Exception:
            pass
        child.job_handle = None


# OpenDesign 自己的三个 MCP(名字与 config/nanobot.config.windows.jsonc 一致)。
# 只有它们的 command 会被改写指向包内 python —— 机主自己装的第三方 MCP
# (npx / 别的 exe)一个字都不许动,改了就是把人家的工具弄坏。
OUR_MCP = ("design-studio", "design-studio-organize", "design-studio-refs")


def patch_config(path, *, gateway_port: int, ws_port: int, python_exe: str,
                 data_root: str | None = None) -> None:
    cfg_path = Path(path)
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    ws = cfg.get("channels", {}).get("websocket", {})
    if ws.get("enabled") is not True:
        raise ConfigUnusable("聊天通道没打开,请重新运行安装程序设置登录口令")
    token = ws.get("token")
    if not token:
        raise ConfigUnusable("聊天通道缺少登录口令,请重新运行安装程序设置")
    # 🔴 口令必须是浏览器发得出去的。前端把它放进 HTTP 头,而 fetch 的头值只收
    # Latin-1(web/src/chat/connection.ts:85 已经明确拒收)⇒ 中文口令会让两条腿
    # 全部正常起来、界面也正常,**唯独第一句话永远发不出去**。
    # 这里 fail closed:宁可现在报一句人话,也不要业主拿着一台"看着装好了"的机器来问。
    try:
        str(token).encode("latin-1")
    except UnicodeEncodeError:
        raise ConfigUnusable(
            "登录口令里有中文或特殊字符,浏览器发不出去 —— 请改成字母数字口令") from None

    servers = cfg.get("tools", {}).get("mcpServers")
    if not isinstance(servers, dict):
        raise ConfigUnusable("配置里没有工具服务(mcpServers),这份配置是残的")
    missing = [n for n in OUR_MCP if not isinstance(servers.get(n), dict)]
    if missing:
        raise ConfigUnusable(f"配置里缺少 OpenDesign 自己的工具服务:{'、'.join(missing)}")

    cfg.setdefault("gateway", {})["port"] = int(gateway_port)
    ws["port"] = int(ws_port)
    for name in OUR_MCP:
        servers[name]["command"] = str(python_exe)
        # 🔴 三个 MCP **不是外壳起的** —— 网关按这里的 env 块起它们,而 MCP SDK 的
        # stdio 客户端只继承一份固定白名单,DS_DATA_ROOT 不在里面。不写进来的话:
        # 助手(聊天侧)建的档案全部落回安装目录 = 卸载会删的地方,而工作台读数据根
        # ⇒ 同一份档案两个世界,重启时迁移再把它搬走,来回翻。
        # 四审 subkimi 抓的 BLOCK;判据 d4 咬着。写绝对路径,不用 ${VAR}:
        # 那要 loader 展开,而它只在网关自己的 env 里查得到。
        if data_root:
            servers[name].setdefault("env", {})[ds_common.DATA_ROOT_ENV] = str(data_root)

    tmp_name: str | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{cfg_path.name}.", suffix=".tmp", dir=str(cfg_path.parent)
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        try:
            mode = cfg_path.stat().st_mode
            os.chmod(tmp_name, mode)
        except OSError:
            pass
        os.replace(tmp_name, cfg_path)
        tmp_name = None
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


# nanobot 会把配置里的 `${VAR}` 换成环境变量,而**任何一个没设的都会让网关整个拒绝启动**
# (nanobot/config/loader.py:143-149 抛 ValueError)。下面这条正则与它逐字一致。
#
# 🔴 为什么要有这一段(2026-08-14 业主真机实证,不是推演):
# 没放 key 那一跑,外壳照着我的注释「没 key 也能看待办」把网关拉了起来,网关一秒后
# 自己退出,业主拿到的是一句英文 `Environment variable 'DS_LLM_KEY' … is not set`。
# 提前扫一遍,是把那句英文换成人话、并且**省掉起后台那段等待**。
#
# 抄这条正则是有代价的:nanobot 换了写法我们就跟丢。所以它只当"提前一步的报错"用,
# 不承担正确性 —— 跟丢的最坏后果是退回今天这个样子(网关自己报错),不会更坏。
# nanobot 版本 pin 在 bin/install.ps1(nanobot-ai==0.2.2)。
_ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def missing_env_refs(config: Any, env: dict) -> list[str]:
    """配置里引用了、但 `env` 里没给的环境变量名(按出现顺序,去重)。

    与 nanobot 对齐的两处,都关系到**会不会造出假红**(假红 = 业主装好的机器打不开,
    和漏判一样坏):
      · 值为空串算"设了"(它判的是 `os.environ.get() is None`);
      · **只看字典的值,不看键** —— nanobot 的解析器不碰键,跟着它。
    """
    found: dict[str, None] = {}

    def walk(node: Any) -> None:
        if isinstance(node, str):
            for name in _ENV_REF.findall(node):
                if name not in env:
                    found[name] = None
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    walk(config)
    return list(found)


def missing_env_message(missing: list[str], *, app: str, key_path: str) -> str:
    """`missing_env_refs()` 的结果 → 念给业主听的那段话(没缺就返回空串)。

    住在这里而不是 ds_shell.py,是因为**这段话是业主唯一会看见的输出**,而那一层
    在 Linux 上一条考卷都跑不了 ⇒ 放在那儿等于没人验。判据 H6~H9。

    分两种缺法说,不是为了话好听 —— 两种缺法**该做的事完全不同**:
      · 缺 key   :业主自己补得上(往那个文件里放一行),路径必须原样念出来;
      · 缺别的   :装机没装好,他补不了,只能重跑安装程序。
    说反或者笼统成一句"配置有问题",他就会去做解决不了问题的那件事。
    """
    if not missing:
        return ""
    tips = []
    if "DS_LLM_KEY" in missing:
        tips.append("· 还没填大模型的 key。请把 key 放进这个文件(没有就新建一个):\n"
                    f"    {key_path}")
    others = [n for n in missing if n != "DS_LLM_KEY"]
    if others:
        tips.append(f"· 配置里还用到了这些没设好的东西:{'、'.join(others)}\n"
                    "    请重新运行安装程序。")
    return f"{app} 起不来,还差点东西:\n\n" + "\n\n".join(tips) + "\n\n补好之后重新打开就行。"


def startup_plan(has_key: bool) -> dict:
    """起哪几条腿。

    🔴 规划双出 B 卷抓到的:上一版是"缺 key 就整个 `die()`",而那发生在**开窗口之前**
    ⇒ 业主永远看不到填 key 的引导页,只看到一个弹窗然后程序没了。
    正确形状:**界面(ds-web)无条件起**,网关**有 key 才起** ——
    网关缺 `${VAR}` 会自己拒绝启动,让它带着缺失去起本来就只会换来一句英文。
    """
    if has_key:
        return {"start": ["ds-web", "网关"], "wait": []}
    return {"start": ["ds-web"], "wait": ["网关"]}


def data_root_for(user_home: str) -> str:
    """装出来那一份的数据根:`<应用状态根>\\Data`(user_home 是它下面的 UserData)。

    **单一来源** —— child_env 与外壳自己都从这里取。分成两处算的代价我付过:
    外壳只给子进程设了 env、自己没设,于是它那次迁移空转了(判据 d3)。
    """
    return os.path.join(os.path.dirname(os.path.realpath(user_home)), "Data")


def prepare_data_root(user_home: str, ds_root: str) -> dict:
    """起任何服务之前:把数据根**给本进程也设上**,然后把遗留数据搬过去。

    为什么在 core 里而不在 ds_shell.py:那一层在 Linux 上一条判据都跑不了
    (pywebview/pystray/WebView2 全是 Windows 独有),而这段逻辑是可判定的。
    """
    os.environ[ds_common.DATA_ROOT_ENV] = data_root_for(user_home)
    return ds_common.migrate_legacy_data(ds_root)


def child_env(
    base_env: dict,
    *,
    ds_root: str,
    user_home: str,
    dsweb_port: int,
    ws_port: int,
    key: str | None = None,
    key_var: str | None = None,
    lock_port: int | None = None,
) -> dict:
    env: dict[str, str] = {}
    for k, v in base_env.items():
        name = str(k)
        upper = name.upper()
        if upper in {"PYTHONPATH", "PYTHONHOME"} or upper.startswith("DS_"):
            continue
        env[name] = str(v)

    env.update(
        {
            "DS_ROOT": str(ds_root),
            "DS_DATA_ROOT": data_root_for(str(user_home)),
            "DS_WEB_PORT": str(dsweb_port),
            "DS_NANOBOT_PORT": str(ws_port),
            "HOME": str(user_home),
            "USERPROFILE": str(user_home),
            "PYTHONIOENCODING": "utf-8",
        }
    )
    if lock_port:
        # ds-web 拿它去请外壳重启网关(业主填完 key 那一下)。没有锁就**什么都不留** ——
        # 留个假号的话 ds-web 会拿它去连别人。
        env["DS_SHELL_LOCK_PORT"] = str(lock_port)
    if key:
        # 变量名从配置的 apiKey 引用里读(ds_credential.env_var_name),**不许写死**:
        # Linux 那份引用的就是 ${MIMO_TP_KEY}。忘了传就抛 —— 悄悄退回一个默认名的话,
        # 症状是"填了 key 还是不能聊天",最难往这儿查。
        if not key_var:
            raise ValueError("有 key 却没说该设哪个环境变量(从配置的 apiKey 引用里读)")
        env[str(key_var)] = str(key)
    return env


def service_envs(
    base_env: dict,
    *,
    ds_root: str,
    user_home: str,
    dsweb_port: int,
    ws_port: int,
    key: str | None = None,
    key_var: str | None = None,
    lock_port: int | None = None,
) -> dict[str, dict]:
    """两条腿各自的环境:**key 只进网关,不进 ds-web。**

    🔴 为什么必须分开(2026-08-16 四审 BLOCK,两条评审腿各自独立命中):
    ds-web **不消费**这把 key —— 只有网关按配置里的 `${VAR}` 解析它。可上一版把
    同一份 env 给了两条腿,于是 ds-web 自己的 `os.environ` 里也有了它,而
    `ds_credential.status()` 分不出**外壳自注入**和**业主真设过**,判成
    `source="env" / writable=False` ⇒ 装好的应用第一次重启后,设置里那张改 key 的
    卡片**永久只读**,还让业主去清一个他从没设过的变量。
    「改 key / 换厂商」是 in-scope 功能,那条路在主形状上直接死了。

    拿掉之后,H1 的只读态回到它该有的语义:**只有业主自己真设过的环境变量**才让
    那一格变灰。(在装好的形状里那几乎不会发生 —— `child_env` 剥掉继承的 `DS_*`
    —— 但在 git-pull 那两台、以及业主手工设过变量的机器上仍然成立。)
    """
    common = dict(ds_root=ds_root, user_home=user_home, dsweb_port=dsweb_port,
                  ws_port=ws_port, lock_port=lock_port)
    return {
        "网关": child_env(base_env, key=key, key_var=key_var, **common),
        "ds-web": child_env(base_env, key=None, key_var=None, **common),
    }


class ShellState:
    visible: bool
    exiting: bool

    def __init__(self, ui, on_stop):
        self.ui = ui
        self.on_stop = on_stop
        self.visible = True
        self.exiting = False
        # 事件从三个方向来:锁的监听线程(第二次双击)、托盘线程、UI 线程。
        # 没有这把锁,"检查 exiting 再置位"是两步 —— 两个线程能一起穿过去,
        # 后台被收两遍、窗口被销毁两遍。锁只护**状态判定**,不护 UI 调用本身。
        self._lock = threading.RLock()

    def on_close_requested(self) -> bool:
        with self._lock:
            if self.exiting:
                return True
            self.visible = False
        self.ui.hide_window()
        return False

    def on_show(self) -> None:
        with self._lock:
            if self.exiting:
                return
            self.visible = True
        self.ui.show_window()

    def on_quit(self) -> None:
        with self._lock:
            if self.exiting:
                return
            self.exiting = True
            self.visible = False
        self.on_stop()
        self.ui.destroy()
