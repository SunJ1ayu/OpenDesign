"""判据:打开软件不许被更新检查挡住(track opendesign-startup-not-blocked-by-update)。

🔴 **判据先行,此刻按预期全红** —— `ds_update_startup` 还不存在。

由来(业主 2026-09-19):「现在每次打开都会弹出正在检测更新,这严重拖慢了我们开软件的速度」。
基线实测 **20.1 秒**(收据 evidence/20260919T152900Z-01-startup-block-baseline.txt):
后端串行两跳 × 10s,前端 startupPhase 初值 'checking' ⇒ 整个工作区不渲染。

**这份考卷防的是什么**:一个"合规但错误"的实现最可能的两种作弊是
① 把超时从 35s 改小就说修好了(照样在启动路径上联网,网一慢照样等);
② 状态文件一有问题就抛,把"不更新"变成"打不开"。
su_net 段钉①,su4~su12 钉②。
"""
# 🔴 每个建了临时目录的 setUp 都必须 addCleanup 删掉它。
#    2026-09-19 本单实测:漏了 27 个 —— 而"判据把盘撑满"我们整单治过
#    (track opendesign-tmpdir-leak:一轮往 /tmp 扔 1.7 万个空壳目录,业主磁盘满了)。
#    总跑里有专门的泄漏闸在数这个,它当场把我抓了。
import json
import os
import shutil
import socket
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))

try:
    import ds_update_startup  # noqa: E402
except ModuleNotFoundError:                     # 判据先行:实现还不存在
    # 🔴 **不让整份文件在 import 处崩掉**。整份崩只报 1 个 error,红收据就数不出
    # "哪几条断言会咬" —— 而那正是判据先行唯一要证明的事。换成一调用就失败的桩,
    # 每条判据各自红、各自说明缺什么。
    class _Missing:
        def __getattr__(self, name):
            def boom(*a, **k):
                raise AssertionError(
                    f"ds_update_startup.{name} 还不存在 —— 判据先行,此刻应当红")
            return boom
    ds_update_startup = _Missing()  # type: ignore[assignment]


def _state(**over):
    """一份"本该装"的合法状态;各用例只改一个字段,好指认是哪条规则在起作用。"""
    base = {"schema": 1, "phase": "ready", "version": "0.98.8",
            "asset": {"name": "OpenDesign-Setup-0.98.8.exe", "size": 4, "sha256": None},
            "path": None, "updated_at": 1789800000}
    base.update(over)
    return base


class StartupDecisionTests(unittest.TestCase):
    """su1~su12:只有一条路通向 install,其余一切进工作区。"""

    def setUp(self):
        import hashlib, tempfile
        self.tmp = tempfile.mkdtemp(prefix="ds-startup-")
        self.addCleanup(shutil.rmtree, self.tmp, True)   # 判据不许往盘上扔垃圾(泄漏闸会数)
        self.pkg = os.path.join(self.tmp, "OpenDesign-Setup-0.98.8.exe")
        with open(self.pkg, "wb") as f:
            f.write(b"abcd")
        self.sha = hashlib.sha256(b"abcd").hexdigest()

    def good(self, **over):
        s = _state(path=self.pkg)
        s["asset"] = dict(s["asset"], sha256=self.sha, size=4)
        s.update(over)
        return s

    def decide(self, state, current="0.98.7"):
        return ds_update_startup.startup_decision(state, current, now=1789800001)

    # —— 唯一该装的那条路 ——
    def test_su1_ready_and_verified_installs(self):
        """su1:phase=ready + 版本更新 + 包在 + 大小摘要都对 ⇒ 装。"""
        self.assertEqual(self.decide(self.good())["action"], "install")

    # —— 其余一切都必须进工作区 ——
    def test_su2_missing_state_enters(self):
        """su2:根本没有状态文件(None)⇒ 进工作区。"""
        self.assertEqual(self.decide(None)["action"], "enter")

    def test_su3_not_a_dict_enters(self):
        """su3:盘上是合法 JSON 但不是对象(列表/字符串/数字)⇒ 进工作区,不抛。"""
        for junk in ([], "ready", 42, True):
            self.assertEqual(self.decide(junk)["action"], "enter", junk)

    def test_su4_missing_fields_enters(self):
        """su4:半写 —— 字段缺一个就不许装(原子写失败时盘上可能就是这样)。"""
        for drop in ("phase", "version", "asset", "path"):
            s = self.good()
            s.pop(drop)
            self.assertEqual(self.decide(s)["action"], "enter", drop)

    def test_su5_unknown_schema_enters(self):
        """su5:schema 不是我们认识的版本 ⇒ 进工作区(将来改格式时的前向保护)。"""
        self.assertEqual(self.decide(self.good(schema=999))["action"], "enter")
        self.assertEqual(self.decide(self.good(schema="1"))["action"], "enter")

    def test_su6_phase_not_ready_enters(self):
        """su6:还没下完(downloading)或空闲(idle)⇒ 进工作区。"""
        for phase in ("downloading", "idle", "", None, "READY"):
            self.assertEqual(self.decide(self.good(phase=phase))["action"], "enter", phase)

    def test_su7_package_gone_enters(self):
        """su7:状态说 ready,但那个安装包已经不在盘上了 ⇒ 进工作区。"""
        os.remove(self.pkg)
        self.assertEqual(self.decide(self.good())["action"], "enter")

    def test_su8_digest_mismatch_enters(self):
        """su8:摘要对不上 ⇒ 进工作区。**绝不许装一个校验不过的包。**"""
        s = self.good()
        s["asset"] = dict(s["asset"], sha256="0" * 64)
        self.assertEqual(self.decide(s)["action"], "enter")

    def test_su9_size_mismatch_enters(self):
        """su9:字节数对不上(下到一半就被标成 ready)⇒ 进工作区。"""
        s = self.good()
        s["asset"] = dict(s["asset"], size=999999)
        self.assertEqual(self.decide(s)["action"], "enter")

    def test_su10_not_newer_enters(self):
        """su10:状态里的版本不比当前新 ⇒ 进工作区(不许降级、不许重装同版)。"""
        for cur in ("0.98.8", "0.98.9", "1.0.0"):
            self.assertEqual(self.decide(self.good(), current=cur)["action"], "enter", cur)

    def test_su11_unreadable_version_enters(self):
        """su11:版本号读不出来(空/乱码/None)⇒ 进工作区,不抛。"""
        for v in (None, "", "beta", "0.98.8-rc1", 98):
            self.assertEqual(self.decide(self.good(version=v))["action"], "enter", v)

    def test_su12_path_outside_or_weird_enters(self):
        """su12:path 不是字符串、是目录、或是符号链接 ⇒ 进工作区。"""
        self.assertEqual(self.decide(self.good(path=None))["action"], "enter")
        self.assertEqual(self.decide(self.good(path=12))["action"], "enter")
        self.assertEqual(self.decide(self.good(path=self.tmp))["action"], "enter")
        link = os.path.join(self.tmp, "link.exe")
        os.symlink(self.pkg, link)
        self.assertEqual(self.decide(self.good(path=link))["action"], "enter")

    def test_su13_never_raises_on_arbitrary_input(self):
        """su13:🔴 它永远不许抛。盘上的数据可以是任何东西,抛一次 = 软件打不开。

        本项目已有四次"注入/时机"导致打不开的前科,这条是那一类的机械防线。
        """
        for junk in (None, [], {}, {"schema": 1}, {"phase": {"a": 1}},
                     {"schema": 1, "phase": "ready", "asset": "x", "path": [], "version": {}},
                     {"asset": {"size": "big", "sha256": 1}}):
            try:
                out = ds_update_startup.startup_decision(junk, "0.98.7", now=1)
            except Exception as exc:                      # noqa: BLE001 —— 就是要抓它
                self.fail(f"startup_decision 对 {junk!r} 抛了 {exc!r} —— 这会让软件打不开")
            self.assertIn(out["action"], ("install", "enter"))

    def test_su13b_survives_failure_deep_in_the_path(self):
        """su13b:走到深处才炸的那种错误,也必须被兜住。

        🔴 由来(2026-09-19 变异红检 B5 抓到):su13 喂的坏输入在到达深处之前
        就被前面的类型检查拦下返回了 ⇒ **去不去掉兜底 try,行为完全一样**,
        su13 咬不住"把 except Exception 改窄"这个变异。
        这里让一个合法状态在读文件那一步炸,才真正测到兜底。
        """
        s = self.good()
        def boom(*a, **k):
            raise OSError("磁盘这一刻读不了了")
        with mock.patch.object(os.path, "getsize", boom):
            try:
                out = ds_update_startup.startup_decision(s, "0.98.7", now=1)
            except Exception as exc:                      # noqa: BLE001
                self.fail(f"深处的 OSError 漏出来了:{exc!r} —— 这会让软件打不开")
        self.assertEqual(out["action"], "enter")

    def test_su14_reason_is_a_stable_token(self):
        """su14:reason 必须是稳定枚举,不是自由散文 —— 判据和界面都要认它。"""
        out = self.decide(self.good(phase="downloading"))
        self.assertRegex(out["reason"], r"^[a-z][a-z0-9_]*$")


class StartupTouchesNoNetworkTests(unittest.TestCase):
    """su_net:🔴 本考卷的核心 —— 启动决策路径一次网络都不许发。

    为什么这么验而不是量耗时:量耗时受机器快慢影响、会变成 flaky;
    而"把超时从 35s 调成 3s"这种假修复**照样能通过耗时判据**,却通不过这一条。
    """

    def test_su_net1_decision_makes_no_socket(self):
        """su_net1:决策期间任何 socket 创建都算失败。"""
        def boom(*a, **k):
            raise AssertionError("启动决策路径创建了 socket —— 启动路径不许联网")
        with mock.patch.object(socket, "socket", boom), \
             mock.patch.object(socket, "create_connection", boom):
            out = ds_update_startup.startup_decision(None, "0.98.7", now=1)
        self.assertEqual(out["action"], "enter")

    def test_su_net2_read_state_makes_no_socket(self):
        """su_net2:读盘上的状态也不许联网(它只该碰文件系统)。"""
        import tempfile
        def boom(*a, **k):
            raise AssertionError("读状态文件的路径创建了 socket")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "update-state.json"
            p.write_text(json.dumps(_state()), encoding="utf-8")
            with mock.patch.object(socket, "socket", boom), \
                 mock.patch.object(socket, "create_connection", boom):
                ds_update_startup.read_state(p)

    def test_su_net3_does_not_import_or_call_update_fetchers(self):
        """su_net3:启动决策一次都不许调 ds_update 的取数函数。

        🔴 **必须用记账探针,不能用"一调用就抛"**(2026-09-19 变异红检 B1 抓到):
        `startup_decision` 自己包着 `except Exception` 兜底(su13 要求的),
        而 AssertionError 是 Exception 的子类 ⇒ **抛出来的探针会被那个兜底吞掉**,
        判据照样绿。两条防线互相抵消,变异 B1(在启动路径上偷查一次更新)当场漏网。
        记账探针不抛,吞不掉。
        """
        import ds_update
        called = []
        def spy(name):
            def f(*a, **k):
                called.append(name)
                return None
            return f
        names = ("fetch_releases", "fetch_atom", "fetch_manifest",
                 "check_for_update", "check_cached")
        with mock.patch.multiple(ds_update, **{n: spy(n) for n in names}):
            out = ds_update_startup.startup_decision(None, "0.98.7", now=1)
            ds_update_startup.startup_decision(_state(), "0.98.7", now=1)
        self.assertEqual(called, [], f"启动决策调用了 ds_update 的取数函数:{called}")
        self.assertEqual(out["action"], "enter")


class StateWriteTests(unittest.TestCase):
    """sw1~sw3:写状态必须原子,半写的文件不许出现在那个路径上。"""

    def setUp(self):
        import tempfile
        self.d = tempfile.mkdtemp(prefix="ds-startup-w-")
        self.addCleanup(shutil.rmtree, self.d, True)
        self.p = Path(self.d) / "update-state.json"

    def test_sw1_write_then_read_roundtrips(self):
        """sw1:写进去能原样读回来。"""
        ds_update_startup.write_state(self.p, _state())
        self.assertEqual(ds_update_startup.read_state(self.p)["version"], "0.98.8")

    def test_sw2_write_is_atomic(self):
        """sw2:🔴 替换那一刻之前,目标路径上要么是旧内容、要么不存在 —— 绝不能是半个文件。

        用 os.replace 被调用时目标文件的状态来验:此刻临时文件已经写完,
        目标路径要么还是旧的、要么还没有。
        """
        ds_update_startup.write_state(self.p, _state(version="0.98.8"))
        seen = {}
        real_replace = os.replace

        def spy(src, dst, *a, **k):
            seen["at_replace"] = Path(dst).read_text(encoding="utf-8") if Path(dst).exists() else None
            return real_replace(src, dst, *a, **k)

        with mock.patch.object(os, "replace", spy):
            ds_update_startup.write_state(self.p, _state(version="0.98.9"))
        self.assertIn("at_replace", seen, "write_state 没有走 os.replace ⇒ 不是原子写")
        self.assertIn('"0.98.8"', seen["at_replace"] or "",
                      "替换那一刻目标路径上不是完整的旧内容 ⇒ 存在半写窗口")
        self.assertEqual(ds_update_startup.read_state(self.p)["version"], "0.98.9")

    def test_sw3_corrupt_file_reads_as_none(self):
        """sw3:盘上是坏的(非 JSON / 半截 / 空)⇒ read_state 返回 None,不抛。"""
        for junk in ("", "{", "not json", '{"schema": 1, "phase": "rea'):
            self.p.write_text(junk, encoding="utf-8")
            self.assertIsNone(ds_update_startup.read_state(self.p), junk)

    def test_sw4_missing_file_reads_as_none(self):
        """sw4:文件不存在 ⇒ None,不抛。"""
        self.assertIsNone(ds_update_startup.read_state(self.p / "nope.json"))


class StatePathTests(unittest.TestCase):
    """sp1~sp2:状态文件放在哪 —— 和既有的自动更新记账同侧。"""

    def test_sp1_lives_next_to_the_attempts_record(self):
        """sp1:放在数据根的 Logs 下,**不进安装目录、不进用户数据目录**。

        进安装目录 ⇒ 更新时被覆盖/卸载时被删(业主卸载丢资料那一单的教训);
        进用户数据目录 ⇒ 混进他的真实档案里。既有的 auto-update-attempts.json
        已经定在 Logs 下,这个跟它走,省得下一个人再想一遍。
        """
        import ds_auto_update
        got = Path(ds_update_startup.state_path("/data"))
        self.assertEqual(got.parent, Path(ds_auto_update.record_path("/data")).parent)
        self.assertEqual(got.name, "update-state.json")

    def test_sp2_accepts_path_objects(self):
        """sp2:传 Path 和传 str 结果一样(调用方两种都有)。"""
        self.assertEqual(str(ds_update_startup.state_path("/data")),
                         str(ds_update_startup.state_path(Path("/data"))))


class PrepareUpdateTests(unittest.TestCase):
    """pr1~pr7:后台把新版下下来、校验、写状态 —— **只下不装**,装留到下次打开软件。

    这是本单的另一半:没有它,状态文件永远不会被写,启动决策永远返回 enter,
    等于"打开快了但不会自动更新了"。
    """

    def setUp(self):
        import hashlib, tempfile
        self.root = tempfile.mkdtemp(prefix="ds-prep-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.body = b"NEW-INSTALLER-BYTES"
        self.sha = hashlib.sha256(self.body).hexdigest()
        self.info = {"update_available": True, "latest": "0.98.8",
                     "asset": {"name": "OpenDesign-Setup-0.98.8.exe",
                               "url": "https://example/x.exe",
                               "size": len(self.body),
                               "digest": "sha256:" + self.sha}}

    def dl_ok(self, url, dest):
        Path(dest).write_bytes(self.body)

    def state(self):
        return ds_update_startup.read_state(ds_update_startup.state_path(self.root))

    def test_pr1_success_writes_ready_and_startup_would_install(self):
        """pr1:下好且校验过 ⇒ 写 ready,而且**下一次启动真的会装**(端到端接上)。"""
        out = ds_update_startup.prepare_update(self.info, self.root, download=self.dl_ok)
        self.assertTrue(out["ok"], out)
        st = self.state()
        self.assertEqual(st["phase"], "ready")
        self.assertEqual(st["version"], "0.98.8")
        self.assertEqual(st["asset"]["sha256"], self.sha)
        # 🔴 这一条是本单两半之间唯一的接缝:prepare 写的东西,startup 必须认。
        self.assertEqual(
            ds_update_startup.startup_decision(st, "0.98.7")["action"], "install")

    def test_pr2_download_failure_leaves_no_ready(self):
        """pr2:下载炸了 ⇒ 绝不留下 ready。"""
        def boom(url, dest):
            raise OSError("网断了")
        out = ds_update_startup.prepare_update(self.info, self.root, download=boom)
        self.assertFalse(out["ok"])
        st = self.state()
        self.assertTrue(st is None or st.get("phase") != "ready", st)

    def test_pr3_digest_mismatch_deletes_the_bad_package(self):
        """pr3:摘要对不上 ⇒ 不写 ready,**并且把那个坏包删掉**。

        留着它只会占盘,而且下次万一有人放宽校验就会装上去。
        """
        def wrong(url, dest):
            # 🔴 **必须和好包等长**(2026-09-19 变异红检 B11 抓到):
            # 原来写的是 b"TAMPERED"(8 字节)而好包是 19 字节 ⇒ 字节数检查先拦住,
            # 这条判据根本走不到摘要检查 ⇒ 把 sha256 校验整个删掉它也照样绿。
            Path(dest).write_bytes(b"X" * len(self.body))
        out = ds_update_startup.prepare_update(self.info, self.root, download=wrong)
        self.assertFalse(out["ok"])
        st = self.state()
        self.assertTrue(st is None or st.get("phase") != "ready")
        leftovers = list(Path(self.root).rglob("*.exe"))
        self.assertEqual(leftovers, [], f"校验失败的包没删干净:{leftovers}")

    def test_pr4_size_mismatch_rejected(self):
        """pr4:字节数对不上也不许写 ready(下到一半就当下完)。"""
        info = dict(self.info, asset=dict(self.info["asset"], size=999999))
        out = ds_update_startup.prepare_update(info, self.root, download=self.dl_ok)
        self.assertFalse(out["ok"])
        st = self.state()
        self.assertTrue(st is None or st.get("phase") != "ready")

    def test_pr5_marks_downloading_before_fetching(self):
        """pr5:动手之前先把 downloading 写上 —— 下载中途断电,下次启动看到的不是 ready。"""
        seen = {}
        def spy(url, dest):
            seen["phase_at_download"] = (self.state() or {}).get("phase")
            self.dl_ok(url, dest)
        ds_update_startup.prepare_update(self.info, self.root, download=spy)
        self.assertEqual(seen.get("phase_at_download"), "downloading")

    def test_pr6_never_raises(self):
        """pr6:🔴 后台任务永不抛 —— 它跑在用户正在干活的时候。"""
        for bad in (None, {}, {"update_available": False}, {"asset": None},
                    {"update_available": True, "latest": None, "asset": {}},
                    {"update_available": True, "latest": "0.98.8", "asset": {"url": None}}):
            try:
                out = ds_update_startup.prepare_update(bad, self.root, download=self.dl_ok)
            except Exception as exc:                      # noqa: BLE001
                self.fail(f"prepare_update 对 {bad!r} 抛了 {exc!r}")
            self.assertFalse(out["ok"])

    def test_pr6b_survives_failure_deep_in_the_path(self):
        """pr6b:走到深处才炸的错误也必须被兜住。

        🔴 由来(变异红检 B15,和 su13b 同一个毛病):pr6 喂的坏输入在到达兜底之前
        就被 _asset_facts 返回 None 拦下了 ⇒ 去不去掉兜底行为完全一样。
        这里让建目录那一步炸,才真正测到 prepare_update 的兜底。
        """
        def boom(*a, **k):
            raise OSError("盘满了")
        with mock.patch.object(os, "makedirs", boom):
            try:
                out = ds_update_startup.prepare_update(self.info, self.root, download=self.dl_ok)
            except Exception as exc:                      # noqa: BLE001
                self.fail(f"后台任务把异常漏出来了:{exc!r} —— 它跑在业主干活的时候")
        self.assertFalse(out["ok"])

    def test_pr8_a_package_for_a_version_we_already_run_is_swept(self):
        """pr8:装完之后,盘上那个 46MB 的包必须被清掉 —— 别让它永远躺在业主的盘上。

        🔴 由来:本单新增的"后台备货"会把安装包留在 `Logs/pending/`。装完重启之后,
        状态文件里那一版**就是现在跑着的这一版**,谁也不会再用它,但没人清 ⇒
        每更新一次就永久多占 46MB。这个项目已经因为"没人清"被撑满过盘(track
        opendesign-tmpdir-leak:一轮往 /tmp 扔 1.7 万个空壳目录)。

        清扫挂在后台备货那一趟里(业主已经在用软件了),不挂启动路径 —— 那条路上
        只许读盘,越少动作越好。
        """
        ds_update_startup.prepare_update(self.info, self.root, download=self.dl_ok)
        pkg = self.state().get("path")
        self.assertTrue(os.path.isfile(pkg), "前提没摆好:包没下下来")

        # 已经升到 0.98.8 了:再跑一趟后台备货,这时线上没有更新的版本。
        latest_now = {"current": "0.98.8", "update_available": False, "latest": None,
                      "asset": None, "error": None}
        out = ds_update_startup.prepare_update(latest_now, self.root, download=self.dl_ok)
        self.assertFalse(out["ok"])            # 没东西可备,但不是因此就不打扫
        self.assertFalse(os.path.isfile(pkg), "装完之后那个包还躺在盘上(每更新一次多占 46MB)")
        self.assertIsNone(self.state(), "包清掉了,状态文件却还留着")

    def test_pr8b_a_still_pending_newer_package_is_not_swept(self):
        """pr8b:还没装的新版**不许**被打扫掉 —— 否则每 10 分钟一轮的后台轮询会把自己下的东西删了。"""
        ds_update_startup.prepare_update(self.info, self.root, download=self.dl_ok)
        pkg = self.state().get("path")
        same = {"current": "0.98.7", "update_available": True, "latest": "0.98.8",
                "asset": self.info["asset"], "error": None}
        ds_update_startup.prepare_update(same, self.root, download=self.dl_ok)
        self.assertTrue(os.path.isfile(pkg), "还没装的新版包被当成垃圾清掉了")
        self.assertEqual((self.state() or {}).get("phase"), "ready")

    def test_pr7_already_ready_does_not_redownload(self):
        """pr7:同一版已经下好了就别再下一遍(省业主的流量和磁盘)。"""
        ds_update_startup.prepare_update(self.info, self.root, download=self.dl_ok)
        calls = []
        def counting(url, dest):
            calls.append(url)
            self.dl_ok(url, dest)
        out = ds_update_startup.prepare_update(self.info, self.root, download=counting)
        self.assertTrue(out["ok"])
        self.assertEqual(calls, [], "同一个版本被重复下载了")


class BackgroundScheduleTests(unittest.TestCase):
    """sc1~sc4:后台查更新的节奏 —— 不在启动瞬间发起,轮询带抖动,失败要退避。"""

    def test_sc1_first_check_is_delayed(self):
        """sc1:首次检查不许在进入工作区的那一刻发起。"""
        self.assertGreaterEqual(ds_update_startup.FIRST_CHECK_DELAY_S, 5)

    def test_sc2_interval_has_jitter(self):
        """sc2:同一个间隔连算多次不该总是同一个数 —— 否则所有客户端会同一秒打服务器。"""
        vals = {ds_update_startup.next_delay(attempt=0) for _ in range(40)}
        self.assertGreater(len(vals), 1, "轮询间隔没有抖动")

    def test_sc3_failures_back_off_and_are_capped(self):
        """sc3:连续失败要退避,且有上限(不许退避到天荒地老)。"""
        # 🔴 **不许拿两组随机样本的同一个统计量比大小**(2026-09-19 变异红检抓到):
        # 原来写的是 min(40 次) vs min(40 次),去掉退避后两者同分布 ⇒ 约五成几率碰巧通过,
        # 同一个变异第一次咬住、第二次漏网。改成比**互不重叠的界**:真有退避时
        # attempt=3 的基数是 attempt=0 的 8 倍,而抖动只有 ±20%,两个区间不可能相交。
        d0_max = max(ds_update_startup.next_delay(attempt=0) for _ in range(200))
        d3_min = min(ds_update_startup.next_delay(attempt=3) for _ in range(200))
        self.assertGreater(d3_min, d0_max,
                           f"失败之后没有退避:attempt=3 最小 {d3_min} 没超过 attempt=0 最大 {d0_max}")
        big = max(ds_update_startup.next_delay(attempt=99) for _ in range(40))
        self.assertLessEqual(big, ds_update_startup.MAX_BACKOFF_S)

    def test_sc4_delay_never_negative(self):
        """sc4:抖动不许把间隔算成负数或 0。"""
        for attempt in (0, 1, 5, 99):
            for _ in range(40):
                self.assertGreater(ds_update_startup.next_delay(attempt=attempt), 0)


if __name__ == "__main__":
    unittest.main()
