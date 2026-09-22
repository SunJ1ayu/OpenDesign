#!/usr/bin/env python3
"""管家 `bin/ds_host.py` 的判据(track opendesign-electron-shell,T3;主 agent 亲写,判据先单独 commit)。

**为什么有这个文件**:换 Electron 之后,Python 这一侧不再有窗口,只剩「管家」——
Electron 主进程起它,它起网关与工作台、拿单实例锁(ds-web「存 key 后重启网关」那条通道)、
看门狗、首帧看门、导出诊断。两边只靠**一根管道里的一行行 JSON** 说话。

这根管道是新的失败面,而且坏法都是**安静的**:
  · 中文 Windows 上 Python 的管道默认按 cp936 编码,Node 按 UTF-8 读 ⇒ 业主看到的报错是乱码
    (探路版十跑全绿,因为它只发过一条纯 ASCII 的 `ready`);
  · 任何一个 `print()` 漏进 stdout ⇒ 协议行被夹断;
  · 起后台失败时 `ds_shell.die()` 会弹 MessageBox,Electron 再弹一个「后台意外退出」⇒ 同一个错两个框,
    而后一个说的是错的(不是意外退出,是根本没起来)。

接缝(design.md「Test strategy」表,实现照这个写):
    serve(inp, out, *, make_lock, start_backend, home, diag, app_dir, log,
          watch_interval=3.0, first_frame_timeout=90.0) -> int
  `inp` / `out` 是**字节流**;`make_lock(on_show=…, on_restart=…)` 返回有 acquire()/release()/port 的锁;
  `start_backend(home, lock_port=…)` 返回 (supervisor, web_port, restart_gateway),与 `ds_shell.start_backend` 同形。

从旧判据搬来的保证(判据迁移账):s7 前端只许报白名单事件 → h8;s10 诊断包白名单 → h9;
s14 首帧看门只上一次膛 → h10;c21 看门狗一眼看全 → h7;w3/w4 锁通道与锁端口 → h1/h11。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))

import ds_diag                      # noqa: E402
import ds_openfolder                # noqa: E402
import ds_shell                     # noqa: E402
import ds_shell_core as core        # noqa: E402
import ds_host                      # noqa: E402  ← 本单新增,现在还不存在(判据先红)

VERSION = re.search(r'(?m)^VERSION = "([^"]+)"',
                    (ROOT / "bin" / "ds_web.py").read_text(encoding="utf-8")).group(1)


# ---------------------------------------------------------------- 假件
class Sink:
    """管家写 stdout 的那一头。多条线程(主循环 / 看门狗 / 锁回调)都会写 ⇒ 带锁。"""

    def __init__(self):
        self._buf = bytearray()
        self._lock = threading.Lock()

    def write(self, b):
        assert isinstance(b, (bytes, bytearray)), (
            f"管家往 stdout 写的是 {type(b).__name__} 不是字节 —— 接缝要求字节流(编码由管家自己定成 UTF-8)")
        with self._lock:
            self._buf += b
        return len(b)

    def flush(self):
        pass

    def raw(self) -> bytes:
        with self._lock:
            return bytes(self._buf)


class FakeLock:
    def __init__(self, ok=True, busy=False):
        self.ok, self.busy = ok, busy
        self.port = 18791
        self.released = 0
        self.callbacks = {}

    def acquire(self):
        if self.busy:
            raise core.PortBusy("18788~18792 全被占了")
        return self.ok

    def release(self):
        self.released += 1


class FakeSup:
    def __init__(self, dead=None, dead_on_shutdown=None):
        self.shutdowns = 0
        self._dead = list(dead or [])
        self._dead_on_shutdown = list(dead_on_shutdown or [])
        self._lock = threading.Lock()

    def shutdown(self):
        with self._lock:
            self.shutdowns += 1
            # 收摊时两条腿当然会退出 —— 那不是「意外」,看门狗不许为它报
            self._dead += self._dead_on_shutdown

    def take_dead(self):
        with self._lock:
            d, self._dead = self._dead, []
        return d

    def poll_dead(self):
        raise AssertionError("看门狗不许用 poll_dead(c21:两眼之间名册会变,原因会丢)")

    def dead_reports(self):
        raise AssertionError("看门狗不许用 dead_reports(c21)")


class Harness:
    """把 serve() 跑在一条线程里,测试这边握着 stdin 的写端。"""

    def __init__(self, tc: unittest.TestCase, *, lock=None, sup=None, start_backend=None,
                 app_dir=None, first_frame_timeout=90.0, watch_interval=0.05):
        self.tc = tc
        self.lock = lock or FakeLock()
        self.sup = sup or FakeSup()
        self.home = Path(tc.enterContext(tempfile.TemporaryDirectory()))
        self.app_dir = app_dir or Path(tc.enterContext(tempfile.TemporaryDirectory()))
        self.logs: list[str] = []
        self.diag = ds_diag.StartupLog(emit=self.logs.append)
        self.backend_calls = []
        self.restarts = 0

        def default_start_backend(home, lock_port=None):
            self.backend_calls.append({"home": home, "lock_port": lock_port})
            return self.sup, 8766, self._restart

        self.start_backend = start_backend or default_start_backend
        r, w = os.pipe()
        self.inp = os.fdopen(r, "rb")
        self._w = os.fdopen(w, "wb", buffering=0)
        self.out = Sink()
        self.result = []
        self.error = []

        def make_lock(**kw):
            self.lock.callbacks = kw
            return self.lock

        def run():
            try:
                self.result.append(ds_host.serve(
                    self.inp, self.out, make_lock=make_lock, start_backend=self.start_backend,
                    home=self.home, diag=self.diag, app_dir=self.app_dir, log=self.logs.append,
                    watch_interval=watch_interval, first_frame_timeout=first_frame_timeout))
            except BaseException as exc:          # SystemExit 也要接住:serve 不许把它放出来
                self.error.append(exc)

        self.thread = threading.Thread(target=run, daemon=True)
        tc.addCleanup(self._cleanup)

    def _restart(self):
        self.restarts += 1

    def _cleanup(self):
        for f in (self._w, self.inp):
            try:
                f.close()
            except OSError:
                pass

    def start(self):
        self.thread.start()
        return self

    def send(self, obj):
        self._w.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))

    def send_raw(self, b: bytes):
        self._w.write(b)

    def eof(self):
        self._w.close()

    def events(self):
        out = []
        for line in self.out.raw().decode("utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def wait_event(self, name, timeout=5.0):
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            for e in self.events():
                if e.get("event") == name:
                    return e
            time.sleep(0.02)
        self.tc.fail(f"{timeout}s 内没等到管家发 `{name}`;实际发了:{self.events()};日志:{self.logs[-8:]}")

    def finish(self, timeout=5.0):
        self.thread.join(timeout)
        self.tc.assertFalse(self.thread.is_alive(), f"{timeout}s 了 serve 还没返回 —— 收摊卡住")
        self.tc.assertEqual(self.error, [], f"serve 把异常放出来了:{self.error!r}")
        return self.result[0]


# ---------------------------------------------------------------- h1~h4 起与收
class H1Ready(unittest.TestCase):
    def test_h1_ready_carries_port_and_the_one_version(self):
        """ready 带工作台端口与后台版本号(挑战 a4:主进程拿它比 app.getVersion(),抓半新半旧)。
        版本号只有一个来源:`bin/ds_web.py` 的 VERSION。"""
        h = Harness(self).start()
        ready = h.wait_event("ready")
        self.assertEqual(ready.get("web_port"), 8766)
        self.assertEqual(ready.get("version"), VERSION,
                         "ready 里的版本不是 ds_web.VERSION ⇒ 版本自检比的是别的东西")
        self.assertEqual(h.events()[0]["event"], "ready", "ready 之前不该有别的事件")
        # 锁端口必须一路传给后台(旧判据 w4):不传 ⇒ ds-web 回不来,填完 key 不会自动重启网关
        self.assertEqual(h.backend_calls[0]["lock_port"], h.lock.port)
        h.eof()
        h.finish()


class H2H3Quit(unittest.TestCase):
    def test_h2_stdin_eof_means_shut_everything_down(self):
        """Electron 被硬杀 ⇒ 管道断 ⇒ 这里读到 EOF ⇒ 收摊(探路第二跑量到 502ms)。
        不收的话 Python 树成了孤儿,还攥着安装目录里的文件,下一次更新装不上。"""
        h = Harness(self).start()
        h.wait_event("ready")
        h.eof()
        rc = h.finish()
        self.assertEqual(rc, 0)
        self.assertEqual(h.sup.shutdowns, 1, "读到 EOF 没收后台")
        self.assertGreaterEqual(h.lock.released, 1, "读到 EOF 没放锁")

    def test_h3_quit_command_shuts_down_even_with_stdin_open(self):
        h = Harness(self).start()
        h.wait_event("ready")
        h.send({"cmd": "quit"})
        rc = h.finish()
        self.assertEqual(rc, 0)
        self.assertEqual(h.sup.shutdowns, 1)
        self.assertGreaterEqual(h.lock.released, 1)

    def test_h3b_garbage_lines_are_ignored_not_fatal(self):
        """管道里来了一行坏的(半截 JSON / 不认识的命令)⇒ 忽略,不许把管家带崩。"""
        h = Harness(self).start()
        h.wait_event("ready")
        h.send_raw(b"{not json\n")
        h.send_raw(b"\xff\xfe\n")
        h.send({"cmd": "no-such-command"})
        h.send(["not", "an", "object"])
        time.sleep(0.2)
        self.assertTrue(h.thread.is_alive(), "一行坏输入就让管家退出了")
        self.assertEqual(h.sup.shutdowns, 0)
        h.send({"cmd": "quit"})
        self.assertEqual(h.finish(), 0)


class H4Lock(unittest.TestCase):
    def test_h4_already_running_does_not_start_a_second_backend(self):
        """表 #9:Electron 的锁先拿;万一还是撞上一份在跑的管家 ⇒ 说一声、不起第二套后台。"""
        h = Harness(self, lock=FakeLock(ok=False)).start()
        rc = h.finish()
        self.assertEqual([e["event"] for e in h.events()], ["already-running"])
        self.assertEqual(h.backend_calls, [], "锁没拿到还起了后台 ⇒ 两套网关抢端口")
        self.assertEqual(rc, 0)

    def test_h4b_lock_ports_all_busy_is_a_fatal_with_words(self):
        h = Harness(self, lock=FakeLock(busy=True)).start()
        rc = h.finish()
        ev = h.events()
        self.assertEqual([e["event"] for e in ev], ["fatal"], f"实际:{ev}")
        self.assertTrue(ev[0].get("message"), "fatal 没带人话")
        self.assertNotEqual(rc, 0)
        self.assertEqual(h.backend_calls, [])


# ---------------------------------------------------------------- h5~h6 人话只弹一次
class H5H6Words(unittest.TestCase):
    def test_h5_die_during_startup_is_one_fatal_and_no_messagebox(self):
        """`start_backend` 里每条失败都走 `ds_shell.die()` = MessageBox + exit(1)。
        换壳后这一个框由 Electron 弹(父窗口是它、在最前面)⇒ 管家只发 `fatal`,
        **原来那个 `alert` 不许被叫**(否则同一个错两个框);`SystemExit` 不许漏出 serve。"""
        popped = []

        def dying_backend(home, lock_port=None):
            ds_shell.die("还没装好:找不到配置文件\nC:\\x\\config.json\n\n请重新运行安装程序。")

        with mock.patch.object(ds_shell, "alert", side_effect=lambda *a, **k: popped.append(a)):
            h = Harness(self, start_backend=dying_backend).start()
            rc = h.finish()
        self.assertEqual(popped, [], "管家让 ds_shell 自己弹了 MessageBox ⇒ 业主会看到两个框")
        fatals = [e for e in h.events() if e["event"] == "fatal"]
        self.assertEqual(len(fatals), 1, f"实际:{h.events()}")
        self.assertIn("找不到配置文件", fatals[0].get("message", ""))
        self.assertNotIn("ready", [e["event"] for e in h.events()])
        self.assertNotEqual(rc, 0)
        self.assertGreaterEqual(h.lock.released, 1, "起不来也得放锁")

    def test_h5b_unexpected_exception_during_startup_is_a_fatal_too(self):
        def broken_backend(home, lock_port=None):
            raise RuntimeError("意外的栈")

        with mock.patch.object(ds_shell, "alert", side_effect=AssertionError("不许弹框")):
            h = Harness(self, start_backend=broken_backend).start()
            rc = h.finish()
        fatals = [e for e in h.events() if e["event"] == "fatal"]
        self.assertEqual(len(fatals), 1, f"实际:{h.events()}")
        self.assertTrue(fatals[0].get("message"))
        self.assertNotEqual(rc, 0)

    def test_h6_alert_after_ready_becomes_an_event_not_a_messagebox(self):
        """重启网关失败时 `restart_gateway` 会 `alert(...)`(业主存了 key、后台没能自己重启)。
        那句话仍要让业主看见 —— 由 Electron 弹,不由 Python 弹。"""
        popped = []
        h = Harness(self)

        def failing_restart():
            ds_shell.alert("key 已经存好了,但后台没能自己重启:\nboom\n\n请退出 OpenDesign 再打开一次。")

        h._restart = failing_restart
        with mock.patch.object(ds_shell, "alert", side_effect=lambda *a, **k: popped.append(a)):
            h.start()
            h.wait_event("ready")
            h.lock.callbacks["on_restart"]()
            ev = h.wait_event("alert")
            h.send({"cmd": "quit"})
            h.finish()
        self.assertIn("没能自己重启", ev.get("message", ""))
        self.assertEqual(popped, [])


# ---------------------------------------------------------------- h7 看门狗
class H7Watchdog(unittest.TestCase):
    def test_h7_dead_leg_is_reported_once_with_names(self):
        sup = FakeSup(dead=[("网关", "网关 意外退出了(退出码 3)。最后几句:boom")])
        h = Harness(self, sup=sup).start()
        ev = h.wait_event("backend-died")
        self.assertEqual(ev.get("names"), ["网关"])
        self.assertIn("网关", ev.get("message", ""))
        self.assertIn("意外退出", ev.get("message", ""))
        # 退出码与日志尾进日志(旧判据 c20):弹窗只说人话,线索留给我查
        self.assertTrue(any("退出码 3" in line for line in h.logs), f"日志里没有死因:{h.logs[-6:]}")
        time.sleep(0.3)   # 六个看门周期
        self.assertEqual(sum(e["event"] == "backend-died" for e in h.events()), 1, "同一次死亡报了不止一次")
        h.send({"cmd": "quit"})
        h.finish()

    def test_h7b_legs_exiting_during_shutdown_are_not_accidents(self):
        """收摊时两条腿退出是**预期的**;看门狗在这时候报「意外退出」= 每次退出都吓业主一跳。"""
        sup = FakeSup(dead_on_shutdown=[("工作台", "工作台 意外退出了(退出码 0)")])
        h = Harness(self, sup=sup).start()
        h.wait_event("ready")
        h.send({"cmd": "quit"})
        h.finish()
        time.sleep(0.2)
        self.assertNotIn("backend-died", [e["event"] for e in h.events()])


# ---------------------------------------------------------------- h8~h10 诊断
class H8Report(unittest.TestCase):
    def test_h8_only_whitelisted_ui_events_reach_the_log(self):
        """网页能往日志里写东西的唯一口子 ⇒ 当不可信输入(旧判据 s7 搬过来)。
        detail 带中文:管道这一头必须按 UTF-8 解,不是按系统代码页。"""
        h = Harness(self).start()
        h.wait_event("ready")
        h.send({"cmd": "report", "event": "frontend.react_committed", "detail": "首帧已提交"})
        h.send({"cmd": "report", "event": "evil.inject", "detail": "x"})
        h.send({"cmd": "quit"})
        h.finish()
        names = [n for n, _ in h.diag.milestones()]
        self.assertIn("frontend.react_committed", names)
        self.assertNotIn("evil.inject", names)
        self.assertTrue(any("首帧已提交" in line for line in h.logs),
                        f"中文 detail 没原样进日志(按错编码解了?):{h.logs[-4:]}")


class H9Diagnostics(unittest.TestCase):
    def test_h9_export_bundle_carries_electron_log_and_nothing_secret(self):
        """托盘「导出本次启动诊断」。换壳后窗口那一侧的日志在 `electron.log` —— 包里没有它,
        白屏那种事再来一次我手上还是零线索。白名单照旧是硬的(旧判据 s10 的诱饵)。"""
        app_dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (app_dir / "Logs").mkdir()
        (app_dir / "Logs" / "electron.log").write_text("2026-09-22 [窗口] 起来了\n", encoding="utf-8")
        (app_dir / "Logs" / "外壳.log").write_text("2026-09-22 [管家] 起来了\n", encoding="utf-8")
        (app_dir / "Logs" / "key.txt").write_text("sk-诱饵", encoding="utf-8")
        opened = []
        # 打开文件夹是 Electron 的事(shell.showItemInFolder,在业主那个桌面会话里);
        # 管家在后台进程里开,Linux 判据上还会真去起 xdg-open。
        with mock.patch.object(ds_openfolder, "_default_open_launcher",
                               side_effect=lambda *a, **k: opened.append(a)):
            h = Harness(self, app_dir=app_dir).start()
            h.wait_event("ready")
            h.send({"cmd": "export-diagnostics"})
            ev = h.wait_event("diagnostics")
            h.send({"cmd": "quit"})
            h.finish()
        self.assertEqual(opened, [], "管家自己去开文件夹了 —— 那是窗口那一侧的事")
        self.assertTrue(ev.get("path"), f"没给出包的位置:{ev}")
        z = Path(ev["path"])
        self.assertTrue(z.is_file(), f"说导出了,盘上没有:{z}")
        self.assertEqual(z.parent, app_dir, "诊断包该落在应用数据目录(业主找得到的地方)")
        with zipfile.ZipFile(z) as zf:
            names = zf.namelist()
            blob = b"".join(zf.read(n) for n in names)
        self.assertIn("Logs/electron.log", names)
        self.assertIn("本次启动.txt", names)
        self.assertNotIn(b"sk-", blob, "诊断包里混进了 key")


class H10FirstFrame(unittest.TestCase):
    SNAPSHOT = "到点还没等到界面画出来"

    def _snapshots(self, h):
        return sum(self.SNAPSHOT in line for line in h.logs)

    def test_h10_window_shown_twice_arms_the_watch_once(self):
        """托盘还原会再发一次 window-shown;再上一次膛 ⇒ 每次还原都写一段假诊断(旧判据 s14)。"""
        h = Harness(self, first_frame_timeout=0.2).start()
        h.wait_event("ready")
        h.send({"cmd": "window-shown"})
        h.send({"cmd": "window-shown"})
        time.sleep(0.8)
        h.send({"cmd": "quit"})
        h.finish()
        self.assertEqual(self._snapshots(h), 1, f"快照写了 {self._snapshots(h)} 次:{h.logs[-10:]}")

    def test_h10b_frame_reported_in_time_means_no_snapshot(self):
        h = Harness(self, first_frame_timeout=0.4).start()
        h.wait_event("ready")
        h.send({"cmd": "window-shown"})
        h.send({"cmd": "report", "event": "frontend.frame_submitted", "detail": ""})
        time.sleep(0.8)
        h.send({"cmd": "quit"})
        h.finish()
        self.assertEqual(self._snapshots(h), 0, "首帧按时到了还写诊断快照 ⇒ 假线索")


class H15Milestones(unittest.TestCase):
    def test_h15_the_startup_timeline_keeps_its_milestones(self):
        """白屏那晚手上零线索,才有了分阶段的启动时间线(旧判据 s6/s17)。换壳后这条线由管家接着记:
        拿到锁 → 后台就绪 → 窗口真出来了(Electron 发 window-shown)。少一个,那一段又成了黑块。"""
        h = Harness(self).start()
        h.wait_event("ready")
        h.send({"cmd": "window-shown"})
        h.send({"cmd": "quit"})
        h.finish()
        names = [n for n, _ in h.diag.milestones()]
        for need in ("lock.acquired", "backend.ready", "window.shown"):
            self.assertIn(need, names, f"时间线少了 {need}:{names}")
        self.assertLess(names.index("lock.acquired"), names.index("backend.ready"))
        self.assertLess(names.index("backend.ready"), names.index("window.shown"))


# ---------------------------------------------------------------- h11~h12 锁通道
class H11Lock(unittest.TestCase):
    def test_h11_show_and_restart_verbs_are_wired(self):
        """锁通道只留 ds-web「存 key 后重启网关」;SHOW 也照接(第二份旧式启动把窗口叫出来)。"""
        h = Harness(self).start()
        h.wait_event("ready")
        cb = h.lock.callbacks
        self.assertTrue(callable(cb.get("on_restart")), "锁没接重启回调 ⇒ 填完 key 网关不重启(旧判据 w3)")
        self.assertTrue(callable(cb.get("on_show")))
        cb["on_restart"]()
        self.assertEqual(h.restarts, 1, "RESTART 帧到了没叫 start_backend 给的重启函数")
        cb["on_show"]()
        h.wait_event("show")
        h.send({"cmd": "quit"})
        h.finish()

    def test_h12_update_handoff_no_longer_shuts_the_host(self):
        """旧更新器的交棒动词随旧更新器退役:它不许再让管家收摊(那会让后台无声消失)。"""
        h = Harness(self).start()
        h.wait_event("ready")
        cb = h.lock.callbacks.get("on_update")
        if cb is not None:
            cb()
            time.sleep(0.2)
        self.assertEqual(h.sup.shutdowns, 0)
        self.assertTrue(h.thread.is_alive())
        h.send({"cmd": "quit"})
        h.finish()


# ---------------------------------------------------------------- h13~h14 管道本身
class H13Stdout(unittest.TestCase):
    def test_h13_every_stdout_line_is_a_protocol_event(self):
        h = Harness(self).start()
        h.wait_event("ready")
        h.send({"cmd": "report", "event": "frontend.bundle_started", "detail": ""})
        h.send({"cmd": "export-diagnostics"})
        h.wait_event("diagnostics")
        h.send({"cmd": "quit"})
        h.finish()
        raw = h.out.raw()
        self.assertTrue(raw.endswith(b"\n"), "最后一行没换行 ⇒ Electron 那边 readline 收不到它")
        for line in raw.decode("utf-8").splitlines():
            obj = json.loads(line)
            self.assertIsInstance(obj, dict)
            self.assertIsInstance(obj.get("event"), str, f"不是协议行:{line!r}")


class H14RealPipe(unittest.TestCase):
    def test_h14_real_process_speaks_utf8_on_a_chinese_windows_pipe(self):
        """真起一次 `python bin/ds_host.py`,把管道编码设成 gbk(= 中文 Windows 上被重定向的 stdout)。
        空的数据目录 ⇒ 起后台必然失败 ⇒ 必须收到一行**UTF-8** 的 JSON、中文原样。
        (锁端口若被占或本机回环不通,收到的会是另一条中文 fatal / already-running —— 编码照样要对。)"""
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        env = dict(os.environ, LOCALAPPDATA=str(tmp), HOME=str(tmp), USERPROFILE=str(tmp),
                   PYTHONIOENCODING="gbk", PYTHONUTF8="0")
        r = subprocess.run([sys.executable, str(ROOT / "bin" / "ds_host.py")], input=b"",
                           capture_output=True, env=env, timeout=120)
        lines = [ln for ln in r.stdout.split(b"\n") if ln.strip()]
        self.assertTrue(lines, f"stdout 一行都没有;stderr 尾:{r.stderr[-600:]!r}")
        events = []
        for ln in lines:
            try:
                events.append(json.loads(ln.decode("utf-8")))
            except (UnicodeDecodeError, ValueError) as exc:
                self.fail(f"stdout 里有一行不是 UTF-8 的协议 JSON({exc}):{ln[:120]!r} —— "
                          f"中文 Windows 上业主看到的就是乱码")
        first = events[0]
        self.assertIn(first.get("event"), ("fatal", "already-running"), f"实际:{events}")
        if first["event"] == "fatal":
            msg = first.get("message", "")
            self.assertRegex(msg, r"[一-鿿]", f"fatal 没有中文人话:{msg!r}")

    def test_h14b_main_wires_the_byte_streams(self):
        """serve 只收字节流;main 若把文本流塞进去,编码又回到系统代码页手里。"""
        src = (ROOT / "bin" / "ds_host.py").read_text(encoding="utf-8")
        self.assertIn("stdin.buffer", src)
        self.assertIn("stdout.buffer", src)


if __name__ == "__main__":
    unittest.main()
