#!/usr/bin/env python3
"""track opendesign-intake-simplify 的 oracle(真机反馈 2026-07-24 #4)——
「打开文件夹」在 Windows 上要把资源管理器窗口提到前台。主 agent 亲写,executor off-limits。

**这个 oracle 覆盖不了什么(先说清,别自欺)**:
下面每一条断的都是"我的假 user32 被正确调用了",**没有一条能证明真 Windows 会把窗口
提到前面**。真机三种失败模式全在断言之外:①SetForegroundWindow 的前台权规则拒绝后台
进程抢焦点;②杀毒软件把抢焦点当异常行为;③Explorer 复用已有窗口(标题命中但那扇窗
不是刚开的)。接得住的只有用户在 Windows 上点一次 —— 见 verify.md 的 UNTESTED 清单。
本文件保证的是**决策逻辑与失败姿态**:选对窗口、等窗口出现、失败不炸、绝不阻塞。

跑法: python3 tests/test_ds_web_open_front.py
"""
import os
import shutil
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_web  # noqa: E402

FOLDER = r"D:\AI\OpenDesign-ws\01-项目\20260701 王女士 翡翠湾 3#1801"
BASE = "20260701 王女士 翡翠湾 3#1801"


class PickFolderWindow(unittest.TestCase):
    """_pick_folder_window:纯逻辑(hwnd, 类名, 标题)三元组 → 该激活哪个句柄。"""

    def test_p01_exact_title_match(self):
        wins = [(11, "CabinetWClass", BASE)]
        self.assertEqual(ds_web._pick_folder_window(wins, FOLDER), 11)

    def test_p02_wrong_class_is_ignored(self):
        """标题对但不是资源管理器窗口(如浏览器某个标签页恰好同名)→ 不动它。"""
        wins = [(12, "Chrome_WidgetWin_1", BASE)]
        self.assertIsNone(ds_web._pick_folder_window(wins, FOLDER))

    def test_p03_right_class_wrong_title(self):
        wins = [(13, "CabinetWClass", "下载"), (14, "ExploreWClass", "文档")]
        self.assertIsNone(ds_web._pick_folder_window(wins, FOLDER))

    def test_p04_full_path_title_mode(self):
        """用户开了"标题栏显示完整路径"时,标题是整条路径 → 仍要命中。"""
        wins = [(15, "CabinetWClass", FOLDER)]
        self.assertEqual(ds_web._pick_folder_window(wins, FOLDER), 15)

    def test_p05_mixed_returns_a_matching_hwnd(self):
        """一堆窗口混杂:返回的必须来自命中集合(不断言"选哪个"——z-order 不可靠)。"""
        wins = [
            (21, "Chrome_WidgetWin_1", BASE),      # 类不对
            (22, "CabinetWClass", "图片"),          # 标题不对
            (23, "ExploreWClass", BASE),           # 命中
            (24, "CabinetWClass", FOLDER),         # 命中(完整路径模式)
        ]
        self.assertIn(ds_web._pick_folder_window(wins, FOLDER), (23, 24))

    def test_p05b_short_name_does_not_match_by_substring(self):
        """短文件夹名不能靠"标题含这几个字"乱认窗口:文件夹叫「图」,不该把
        「施工图」「图片」这些窗口提到前台。命中只在"标题 == 名字"或"标题是以
        路径分隔符结尾于该名字的完整路径"两种情况成立。"""
        wins = [(61, "CabinetWClass", "施工图"), (62, "CabinetWClass", "图片")]
        self.assertIsNone(ds_web._pick_folder_window(wins, r"D:\ws\图"))
        wins2 = [(63, "CabinetWClass", r"D:\ws\图")]
        self.assertEqual(ds_web._pick_folder_window(wins2, r"D:\ws\图"), 63)

    def test_p05c_same_name_different_drive_is_not_a_match(self):
        """panel subdeepseek(MEDIUM)提的真问题:标题是**完整路径**时,只比末段
        会把 `E:\\work` 的窗口当成 `D:\\work` 的。标题带路径就整条比,别只比尾巴。
        (标题只有裸文件夹名时确实分不出来 —— 那是信息不足,不是判据松。)"""
        wins = [(71, "CabinetWClass", r"E:\work")]
        self.assertIsNone(ds_web._pick_folder_window(wins, r"D:\work"))
        wins2 = [(72, "CabinetWClass", r"D:\work")]
        self.assertEqual(ds_web._pick_folder_window(wins2, r"D:\work"), 72)
        # 正斜杠/尾分隔符的写法差异不该影响判断
        wins3 = [(73, "CabinetWClass", "D:/work/")]
        self.assertEqual(ds_web._pick_folder_window(wins3, r"D:\work"), 73)

    def test_p06_empty_list(self):
        self.assertIsNone(ds_web._pick_folder_window([], FOLDER))

    def test_p07_trailing_separator_path(self):
        """路径带尾分隔符时 basename 不能算成空串(否则"标题含空串"人人命中)。"""
        wins = [(31, "CabinetWClass", "下载")]
        self.assertIsNone(ds_web._pick_folder_window(wins, FOLDER + "\\"))
        wins2 = [(32, "CabinetWClass", BASE)]
        self.assertEqual(ds_web._pick_folder_window(wins2, FOLDER + "\\"), 32)


class WinFocusFolder(unittest.TestCase):
    """_win_focus_folder:等窗口出现 → 激活;失败姿态必须是"静默退化"。"""

    def test_f01_window_appears_late(self):
        """窗口是异步创建的:前两轮枚举为空,第三轮才有 → 仍命中,activator 只调一次。"""
        calls = {"enum": 0}
        acted = []

        def enumerator():
            calls["enum"] += 1
            if calls["enum"] < 3:
                return []
            return [(41, "CabinetWClass", BASE)]

        def activator(hwnd):        # v2 起返回值 = "真的到前台了吗",不是"调用过了"
            acted.append(hwnd)
            return True

        ok = ds_web._win_focus_folder(
            FOLDER, enumerator=enumerator, activator=activator,
            attempts=10, delay=0, sleep=lambda _s: None)
        self.assertTrue(ok)
        self.assertEqual(acted, [41])

    def test_f02_never_appears_gives_up_quietly(self):
        acted = []
        ok = ds_web._win_focus_folder(
            FOLDER, enumerator=lambda: [], activator=acted.append,
            attempts=4, delay=0, sleep=lambda _s: None)
        self.assertFalse(ok)
        self.assertEqual(acted, [])

    def test_f03_enumerator_raises_is_swallowed(self):
        """置顶失败绝不能连带把"打开文件夹"这件事搞失败 —— 异常必须被吞。"""
        def boom():
            raise OSError("ctypes 不在这台机器上")
        ok = ds_web._win_focus_folder(
            FOLDER, enumerator=boom, activator=lambda _h: None,
            attempts=2, delay=0, sleep=lambda _s: None)
        self.assertFalse(ok)

    def test_f04_activator_raises_is_swallowed(self):
        def boom(_hwnd):
            raise OSError("SetForegroundWindow 被系统拒")
        ok = ds_web._win_focus_folder(
            FOLDER, enumerator=lambda: [(51, "CabinetWClass", BASE)], activator=boom,
            attempts=2, delay=0, sleep=lambda _s: None)
        self.assertFalse(ok)

    def test_f05_attempts_are_bounded(self):
        """轮询有上限:不能因为窗口永不出现就无限转(daemon 线程也会吃 CPU)。"""
        calls = []
        ds_web._win_focus_folder(
            FOLDER, enumerator=lambda: calls.append(1) or [], activator=lambda _h: None,
            attempts=3, delay=0, sleep=lambda _s: None)
        self.assertEqual(len(calls), 3)


class OpenWindowsOrdering(unittest.TestCase):
    """_open_windows:先照旧 startfile 打开,再(异步)尝试置顶。"""

    def setUp(self):
        self.orig_focus = ds_web._WIN_FOCUS
        self.orig_startfile = getattr(ds_web.os, "startfile", None)
        self.seq = []

        def fake_startfile(p):
            self.seq.append(("startfile", p))
        ds_web.os.startfile = fake_startfile          # Linux 上本来没有这个属性
        ds_web._WIN_FOCUS = lambda p: self.seq.append(("focus", p))

    def tearDown(self):
        ds_web._WIN_FOCUS = self.orig_focus
        if self.orig_startfile is None:
            del ds_web.os.startfile
        else:
            ds_web.os.startfile = self.orig_startfile

    def test_o01_startfile_then_focus(self):
        d = tempfile.mkdtemp(prefix="openfront-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        ds_web._open_windows(d)
        self.assertEqual(self.seq, [("startfile", d), ("focus", d)])

    def test_o01b_file_open_does_not_chase_explorer_window(self):
        """同一个启动器也用于"用默认程序开单个文件"(rel 分支):那时前台窗口是
        CAD/PDF 阅读器,去找资源管理器窗口既无意义、又可能认错同名的那扇 →
        只对目录做置顶。"""
        d = tempfile.mkdtemp(prefix="openfront-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        f = os.path.join(d, "平面图.dwg")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("DWG")
        ds_web._open_windows(f)
        self.assertEqual(self.seq, [("startfile", f)])   # 开了,但没去抢窗口

    def test_o02_startfile_failure_propagates_and_skips_focus(self):
        """打开本身失败要让前端看见(500);置顶不该在没打开的情况下瞎找窗口。"""
        def boom(_p):
            raise OSError("路径没了")
        ds_web.os.startfile = boom
        with self.assertRaises(OSError):
            ds_web._open_windows(FOLDER)
        self.assertEqual(self.seq, [])


class SpawnWinFocusNonBlocking(unittest.TestCase):
    """_spawn_win_focus:必须立刻返回 —— 同步等 2 秒会把 POST /api/open-folder 的响应
    拖 2 秒(ThreadingHTTPServer 不至于卡死别的请求,但按钮转 2 秒 = 又像没反应)。"""

    def setUp(self):
        self.orig = ds_web._win_focus_folder

    def tearDown(self):
        ds_web._win_focus_folder = self.orig

    def test_s01_returns_immediately_and_thread_is_daemon(self):
        started = []

        def slow(path, **_kw):
            started.append(path)
            time.sleep(0.5)
            return False
        ds_web._win_focus_folder = slow

        t0 = time.monotonic()
        th = ds_web._spawn_win_focus(FOLDER)
        elapsed = time.monotonic() - t0
        self.assertLess(elapsed, 0.2, f"_spawn_win_focus 阻塞了 {elapsed:.2f}s")
        self.assertTrue(th.daemon, "置顶线程必须是 daemon,否则会拖住进程退出")
        th.join(timeout=2)
        self.assertEqual(started, [FOLDER])


class LauncherDispatchUnchanged(unittest.TestCase):
    """回归:DS_OPEN_CMD 注入分支与非 Windows 分支一字不动(e2e 靠它永不真开窗口)。"""

    def test_d01_ds_open_cmd_branch_wins(self):
        calls = []
        orig_popen = ds_web.__dict__.get("subprocess")
        import subprocess as _sp
        real = _sp.Popen

        def fake_popen(args, **kw):
            calls.append(args)
            class _P:  # noqa: E306
                pass
            return _P()
        _sp.Popen = fake_popen
        os.environ["DS_OPEN_CMD"] = "/bin/true"
        try:
            ds_web._default_open_launcher("/tmp")
        finally:
            _sp.Popen = real
            os.environ.pop("DS_OPEN_CMD", None)
            if orig_popen is not None:
                ds_web.subprocess = orig_popen
        self.assertEqual(calls, [["/bin/true", "/tmp"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ══════════════════════════════════════════════════════════════════════════
# track opendesign-open-front-v2(真机反馈 2026-07-25:0.44.0 装上后**仍然
# 没有置顶**)。第一版的病根不只是"没提到前面",而是**失败了什么都不说** ——
# 异常全吞、成功失败都不落日志,于是真机上只能靠猜。这一轮的判据分两块:
#   ① 可诊断:每次尝试都要留下一行日志,说清"看见几扇资源管理器窗口、
#      标题是什么、有没有命中、激活的返回是什么" —— 没有这行,下次还是瞎猜。
#   ② 激活升级:SwitchToThisWindow 之后若仍不在前台,按 Windows 的标准做法
#      AttachThreadInput 到当前前台线程再 SetForegroundWindow,并**保证解绑**。
# 仍然证明不了"真机上窗口真的到前面来了"(见文件头声明),但能把"到底卡在
# 哪一步"从猜测变成事实。
# ══════════════════════════════════════════════════════════════════════════


class FakeUser32:
    """够用的 user32 替身:记录调用序列,foreground 可被 SetForegroundWindow 改。"""

    def __init__(self, foreground=999, switch_works=False, set_works=True,
                 has_switch=True):
        self.calls = []
        self.foreground = foreground
        self.switch_works = switch_works
        self.set_works = set_works
        self._has_switch = has_switch

    def ShowWindow(self, hwnd, cmd):
        self.calls.append(("ShowWindow", hwnd, cmd))
        return 1

    def __getattr__(self, name):        # SwitchToThisWindow 可缺席(极老系统)
        if name == "SwitchToThisWindow" and not self._has_switch:
            raise AttributeError(name)
        raise AttributeError(name)

    def SwitchToThisWindow(self, hwnd, alt_tab):
        self.calls.append(("SwitchToThisWindow", hwnd, alt_tab))
        if self.switch_works:
            self.foreground = hwnd
        return 1

    def GetForegroundWindow(self):
        return self.foreground

    def GetWindowThreadProcessId(self, hwnd, _pid):
        return 4242 if hwnd == self.foreground else 4243

    def AttachThreadInput(self, a, b, attach):
        self.calls.append(("AttachThreadInput", a, b, bool(attach)))
        return 1

    def BringWindowToTop(self, hwnd):
        self.calls.append(("BringWindowToTop", hwnd))
        return 1

    def SetForegroundWindow(self, hwnd):
        self.calls.append(("SetForegroundWindow", hwnd))
        if self.set_works:
            self.foreground = hwnd
            return 1
        return 0


class FakeKernel32:
    def GetCurrentThreadId(self):
        return 7777


class ActivateEscalation(unittest.TestCase):
    """_win_activate:温和手段不奏效时才升级,且升级后必须解绑线程输入。"""

    def test_a01_switch_enough_no_escalation(self):
        u = FakeUser32(switch_works=True)
        ok = ds_web._win_activate(77, user32=u, kernel32=FakeKernel32())
        self.assertTrue(ok)
        names = [c[0] for c in u.calls]
        self.assertEqual(names[:2], ["ShowWindow", "SwitchToThisWindow"])
        self.assertNotIn("AttachThreadInput", names)   # 够用就别升级

    def test_a02_escalates_and_always_detaches(self):
        """SwitchToThisWindow 没把窗口拿到前台(真机现象)→ 绑前台线程再抢,
        且**无论成败都要解绑**(不解绑会把两个线程的输入队列绑死)。"""
        u = FakeUser32(switch_works=False, set_works=True)
        ok = ds_web._win_activate(77, user32=u, kernel32=FakeKernel32())
        self.assertTrue(ok)
        names = [c[0] for c in u.calls]
        self.assertIn("AttachThreadInput", names)
        self.assertIn("SetForegroundWindow", names)
        attaches = [c for c in u.calls if c[0] == "AttachThreadInput"]
        self.assertEqual(len(attaches), 2, "必须成对:绑一次、解一次")
        self.assertTrue(attaches[0][3] and not attaches[1][3])
        self.assertEqual(names[-1], "AttachThreadInput")   # 解绑收尾

    def test_a03_reports_failure_when_system_refuses(self):
        """系统就是不给焦点 → 返回 False(不谎报成功),且仍然解绑。"""
        u = FakeUser32(switch_works=False, set_works=False)
        ok = ds_web._win_activate(77, user32=u, kernel32=FakeKernel32())
        self.assertFalse(ok)
        attaches = [c for c in u.calls if c[0] == "AttachThreadInput"]
        self.assertEqual(len(attaches), 2)
        self.assertTrue(attaches[0][3] and not attaches[1][3])


class FocusDiagnostics(unittest.TestCase):
    """_win_focus_folder:每次尝试都要留下可读的一行诊断 —— 0.44.0 真机失败后
    无从下手,正是因为这一行不存在。"""

    def test_d01_logs_hit_with_window_inventory(self):
        logs = []
        ds_web._win_focus_folder(
            FOLDER,
            enumerator=lambda: [(41, "CabinetWClass", BASE),
                                (42, "CabinetWClass", "下载")],
            activator=lambda _h: True,
            attempts=2, delay=0, sleep=lambda _s: None, log=logs.append)
        joined = "\n".join(logs)
        self.assertTrue(logs, "命中也要留日志(否则无法确认走到了哪一步)")
        self.assertIn("hwnd=41", joined)
        self.assertIn("activate=True", joined)

    def test_d02_logs_miss_with_seen_titles(self):
        """没命中时**必须把看见的窗口标题列出来** —— 这是下一轮唯一的线索:
        到底是没找到窗口(标题对不上/Win11 标签页),还是找到了但抢不到焦点。"""
        logs = []
        ds_web._win_focus_folder(
            FOLDER,
            enumerator=lambda: [(51, "CabinetWClass", "文档"),
                                (52, "CabinetWClass", "图片")],
            activator=lambda _h: True,
            attempts=2, delay=0, sleep=lambda _s: None, log=logs.append)
        joined = "\n".join(logs)
        self.assertIn("no-match", joined)
        self.assertIn("文档", joined)      # 看见的标题要落进日志
        self.assertIn("图片", joined)

    def test_d03_logs_exception_instead_of_silence(self):
        logs = []
        def boom():
            raise OSError("ctypes 炸了")
        ok = ds_web._win_focus_folder(
            FOLDER, enumerator=boom, activator=lambda _h: True,
            attempts=2, delay=0, sleep=lambda _s: None, log=logs.append)
        self.assertFalse(ok)
        self.assertIn("error", "\n".join(logs))
        self.assertIn("ctypes 炸了", "\n".join(logs))

    def test_d04_activator_false_is_not_reported_as_success(self):
        """找到了窗口但系统拒绝给焦点 → 整体返回 False,日志写明 activate=False。
        (0.44.0 把"调用过了"当成功,真机上就表现为"说做了但没动静"。)"""
        logs = []
        ok = ds_web._win_focus_folder(
            FOLDER, enumerator=lambda: [(61, "CabinetWClass", BASE)],
            activator=lambda _h: False,
            attempts=2, delay=0, sleep=lambda _s: None, log=logs.append)
        self.assertFalse(ok)
        self.assertIn("activate=False", "\n".join(logs))


class RealWorldExplorerTitle(unittest.TestCase):
    """真机日志(2026-07-25,用户家里的机器)给出的决定性证据 —— 窗口**找到了**,
    只是标题带后缀:

        [open-front] 'E:\\YEGU1HONG DESIGN\\3MDAX': no-match 轮询 20 次未找到
                     资源管理器窗口 seen=['3MDAX - 文件资源管理器']

    我原来的判据要求"标题 == 文件夹名"或"标题 == 完整路径",而 Windows(至少
    Win11 / 这台机器上)给的是 `<文件夹名> - 文件资源管理器`。这一组判据用日志里
    的原文做夹具,英文界面的 `- File Explorer` 一并覆盖。
    """

    REAL_PATH = r"E:\YEGU1HONG DESIGN\3MDAX"
    REAL_TITLE = "3MDAX - 文件资源管理器"

    def test_r01_real_title_from_user_log(self):
        wins = [(101, "CabinetWClass", self.REAL_TITLE)]
        self.assertEqual(ds_web._pick_folder_window(wins, self.REAL_PATH), 101)

    def test_r02_english_ui_suffix(self):
        wins = [(102, "CabinetWClass", "3MDAX - File Explorer")]
        self.assertEqual(ds_web._pick_folder_window(wins, self.REAL_PATH), 102)

    def test_r03_full_path_title_with_suffix(self):
        """开了"标题栏显示完整路径"时:`<完整路径> - 文件资源管理器`。"""
        wins = [(103, "CabinetWClass", self.REAL_PATH + " - 文件资源管理器")]
        self.assertEqual(ds_web._pick_folder_window(wins, self.REAL_PATH), 103)

    def test_r04_prefix_must_end_at_a_boundary(self):
        """后缀匹配不能退化成"标题以文件夹名开头就算":`3MDAXX` 不是 `3MDAX`。"""
        wins = [(104, "CabinetWClass", "3MDAXX - 文件资源管理器")]
        self.assertIsNone(ds_web._pick_folder_window(wins, self.REAL_PATH))

    def test_r05_short_name_lesson_still_holds(self):
        """p05b 的教训不能被这次放宽推翻:文件夹叫「图」,`施工图 - 文件资源管理器`
        仍然不该命中(它是"以…结尾",不是"以…开头 + 边界")。"""
        wins = [(105, "CabinetWClass", "施工图 - 文件资源管理器")]
        self.assertIsNone(ds_web._pick_folder_window(wins, r"D:\ws\图"))

    def test_r06_same_name_different_drive_lesson_still_holds(self):
        """p05c 的教训也不能被推翻:标题带完整路径时,盘符不同就不是同一个。"""
        wins = [(106, "CabinetWClass", r"E:\work - 文件资源管理器")]
        self.assertIsNone(ds_web._pick_folder_window(wins, r"D:\work"))
