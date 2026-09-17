#!/usr/bin/env python3
"""打开软件倒计时自动更新 —— 后端那半(track opendesign-auto-update-countdown)。

主 agent 亲写,执行腿逐字节 off-limits。编号与问法的唯一权威在 design.md 的 Test strategy。

业主 09-15 夜选的原话:「打开软件时发现新版,显示「发现新版,X 秒后自动更新」,可以点取消。
同一个版本失败过一次就不再自动试,免得每次打开都卡住」。

🔴 这份考卷最要紧的是 au3 + au4 + au5 这一串:
   **动手之前先记账**(接力脚本回滚那种失败,界面早没了,谁也来不及记"失败"),
   **记下的账不被 6 小时缓存吞掉**,**服务端自己再把一次关**(界面慢一拍、两个窗口、别的页面都绕不过去)。
   任何一环断掉,业主拿到的就是「打开 → 自动更新 → 失败换回旧版 → 再打开 → 又自动更新」的循环。

纯 stdlib、离线(网络 / 安装器 / 外壳交棒一律替身)、端口 0、`LOCALAPPDATA` 指到临时目录。
"""
import http.client
import json
import os
import sys
import threading
import unittest
from contextlib import contextmanager
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, HERE)
import _tmpreg   # noqa: E402
import ds_update  # noqa: E402
import ds_web     # noqa: E402
import ds_update_apply  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "update",
                       "github-releases-20260907.json")
LATEST = "0.98.3"           # 夹具里最新的那一版
RECORD_NAME = "auto-update-attempts.json"
AUTO = b'{"auto": true}'
MANUAL = b"{}"              # 界面上那个「更新」按钮发的就是它(App.tsx applyUpdate)


def _fixture():
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


def _without(releases, tag):
    return [r for r in releases if r.get("tag_name") != tag]


def _mkdist():
    d = _tmpreg.mkdtemp("ds_auto_update_dist_")
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<!doctype html><div>x</div>")
    return d


def _touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"x")


def _get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", path)
    r = conn.getresponse()
    raw = r.read()
    conn.close()
    return r.status, (json.loads(raw.decode("utf-8")) if raw else None)


def _post(port, path, body):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
    r = conn.getresponse()
    raw = r.read()
    conn.close()
    return r.status, (json.loads(raw.decode("utf-8")) if raw else None)


class AutoUpdate(unittest.TestCase):
    """夹具摆出「装出来的桌面版」:`<安装根>/OpenDesign.exe` + `<安装根>/ds/bin/ds_shell.py`,
    ds_root 指 `<安装根>/ds`;外壳锁端口是个数字;本机版本调旧,让夹具里的 0.98.3 真的比它新。"""

    def setUp(self):
        ds_update.cache_clear()
        self.tmp = _tmpreg.mkdtemp("ds_auto_update_")
        self.appdata = os.path.join(self.tmp, "appdata")
        os.makedirs(self.appdata)
        self.data_root = os.path.join(self.appdata, "OpenDesign")
        self.record = os.path.join(self.data_root, "Logs", RECORD_NAME)
        self.install_root = self._install("OpenDesign")

        env = mock.patch.dict(os.environ, {"LOCALAPPDATA": self.appdata,
                                           "DS_SHELL_LOCK_PORT": "47123"})
        env.start()
        self.addCleanup(env.stop)

        for mod, name in ((ds_update, "fetch_releases"), (ds_update, "fetch_atom"),
                          (ds_update_apply, "apply_update"), (ds_update_apply, "handoff"),
                          (ds_web, "ds_shell_bridge_update"), (ds_web, "VERSION")):
            real = getattr(mod, name)
            self.addCleanup(setattr, mod, name, real)
        self.addCleanup(ds_update.cache_clear)
        ds_web.VERSION = "0.90.0"

        def feed_unavailable(*a, **kw):
            raise OSError("判据不打网:订阅源在这份判据里一律不可用")
        ds_update.fetch_atom = feed_unavailable
        self.releases = _fixture()
        ds_update.fetch_releases = lambda *a, **kw: self.releases

        self.order = []
        self.record_at_apply = []   # apply_update 被叫到那一刻,记账文件里有什么
        self.apply_ok = True

        def fake_apply(decision, paths, **kw):
            self.order.append("apply")
            try:
                with open(self.record, encoding="utf-8", errors="replace") as fh:
                    self.record_at_apply.append(fh.read())
            except OSError:
                self.record_at_apply.append(None)
            if self.apply_ok:
                return {"ok": True, "stage": "relay", "error": None, "relay": "C:/tmp/relay.cmd"}
            return {"ok": False, "stage": "verify", "error": "sha256 对不上", "relay": None}

        def fake_handoff(relay, **kw):
            self.order.append("handoff")
            return True

        def fake_bridge():
            self.order.append("bridge")
            return "started"

        ds_update_apply.apply_update = fake_apply
        ds_update_apply.handoff = fake_handoff
        ds_web.ds_shell_bridge_update = fake_bridge

    # --- 夹具 ---------------------------------------------------------------

    def _install(self, name):
        root = os.path.join(self.tmp, name)
        _touch(os.path.join(root, "OpenDesign.exe"))
        _touch(os.path.join(root, "ds", "bin", "ds_shell.py"))
        return root

    @contextmanager
    def _serve(self, install_root=None):
        ds_root = os.path.join(install_root or self.install_root, "ds")
        httpd = ds_web.make_server(ds_root, _mkdist(), port=0)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            yield httpd.server_address[1]
        finally:
            httpd.shutdown()
            httpd.server_close()

    def _auto(self, port):
        st, body = _get(port, "/api/update/check")
        self.assertEqual(st, 200, "查更新不是 200:%r" % (body,))
        self.assertIn("auto_update", body, "查更新回包里没有 auto_update:%r" % (sorted(body),))
        return body["auto_update"]

    def _assert_not(self, auto, why):
        self.assertIsInstance(auto, dict, "auto_update 形状不对:%r" % (auto,))
        self.assertIs(auto.get("eligible"), False, "这种情况下不该倒计时:%r" % (auto,))
        self.assertEqual(auto.get("why_not"), why, "原因说错了:%r" % (auto,))

    # --- au1 / au2:查更新回包里的 auto_update ---------------------------------

    def test_au1_all_conditions_met_means_eligible(self):
        with self._serve() as port:
            st, body = _get(port, "/api/update/check")
        self.assertEqual(st, 200)
        self.assertEqual(body.get("auto_update"), {"eligible": True, "why_not": None},
                         "装出来的桌面版 + 有可装的新版 + 没试过,却不让倒计时:%r" % (body.get("auto_update"),))
        for k in ("current", "update_available", "latest", "asset", "notes", "error", "release_url"):
            self.assertIn(k, body, "原有字段 %s 丢了" % k)
        self.assertEqual(body["latest"], LATEST)

    def test_au2a_no_update(self):
        self.releases = []
        with self._serve() as port:
            self._assert_not(self._auto(port), "no_update")

    def test_au2b_asset_without_digest(self):
        """没有可信 sha256 的安装包,一键更新会在下载前拒绝(t15)—— 倒计时 10 秒然后报失败没有意义。"""
        rel = _fixture()
        for a in rel[0].get("assets", []):
            a["digest"] = None
        self.releases = rel
        with self._serve() as port:
            self._assert_not(self._auto(port), "asset")

    def test_au2c_no_shell(self):
        """没有桌面外壳接交棒(浏览器里开、开发方式跑)⇒ 走到最后一步必失败,别倒计时。"""
        with mock.patch.dict(os.environ, {"DS_SHELL_LOCK_PORT": ""}):
            with self._serve() as port:
                self._assert_not(self._auto(port), "no_shell")

    def test_au2d_not_installed(self):
        os.remove(os.path.join(self.install_root, "OpenDesign.exe"))
        with self._serve() as port:
            self._assert_not(self._auto(port), "not_installed")

    def test_au2e_path_the_relay_cannot_handle(self):
        """t36 那一类:接力脚本处理不了的路径,apply_update 第 -1 步会拒绝 —— 同一个判断,不许两处各说各的。"""
        root = self._install("Open%Design")
        with self._serve(root) as port:
            self._assert_not(self._auto(port), "path_unsupported")

    def test_au2f_attempted(self):
        self.apply_ok = False   # 准备失败 ⇒ 锁放开(t35:接力脚本起来之后锁不放,第二次会是 busy)
        with self._serve() as port:
            _post(port, "/api/update/apply", AUTO)
            ds_update.cache_clear()
            self._assert_not(self._auto(port), "attempted")

    # --- au3 ~ au12:自动那条路 ------------------------------------------------

    def test_au3_the_attempt_is_written_before_anything_is_prepared(self):
        """🔴 预写。接力脚本回滚、旧版被重新拉起时,界面早就没了 —— 只有动手前记下的账才活得过那一刻。"""
        with self._serve() as port:
            st, body = _post(port, "/api/update/apply", AUTO)
        self.assertEqual(st, 200)
        self.assertEqual(self.order, ["apply", "handoff", "bridge"],
                         "自动那条路的顺序不对(或根本没走到安装):%r / %r" % (self.order, body))
        self.assertTrue(body.get("ok"), body)
        self.assertEqual(len(self.record_at_apply), 1)
        seen = self.record_at_apply[0]
        self.assertIsNotNone(seen, "开始准备的那一刻记账文件还不存在 —— 回滚之后下次打开会再自动试")
        self.assertIn(LATEST, seen, "开始准备的那一刻账里没有这个版本:%r" % (seen,))

    def test_au4_a_failed_attempt_is_seen_through_the_cache(self):
        """查更新结果缓存 6 小时。auto_update 若跟着进了缓存,同一进程里下一次查仍说 eligible。"""
        self.apply_ok = False
        with self._serve() as port:
            before = self._auto(port)
            _st, body = _post(port, "/api/update/apply", AUTO)
            after = self._auto(port)          # 不带 force
        self.assertEqual(before.get("eligible"), True, "前提没摆好:%r" % (before,))
        self.assertEqual(body.get("stage"), "verify", "前提没摆好:准备应当失败在 verify:%r" % (body,))
        self._assert_not(after, "attempted")

    def test_au5_an_attempted_version_is_refused_on_the_server_too(self):
        """服务端二次把关:界面慢一拍、两个窗口同时倒计时、别的页面直接发请求,都绕不过去。"""
        self.apply_ok = False   # 准备失败 ⇒ 锁放开(t35:接力脚本起来之后锁不放,第二次会是 busy)
        with self._serve() as port:
            _post(port, "/api/update/apply", AUTO)
            _st, body = _post(port, "/api/update/apply", AUTO)
        self.assertFalse(body.get("ok"))
        self.assertEqual(body.get("stage"), "auto_skipped", body)
        self.assertEqual(self.order.count("apply"), 1, "试过的版本又被自动装了一遍")

    def test_au6_manual_update_still_works_for_an_attempted_version(self):
        """反面(防修过头):不再**自动**试,不等于业主自己点也不让装。"""
        self.apply_ok = False   # 准备失败 ⇒ 锁放开(t35:接力脚本起来之后锁不放,第二次会是 busy)
        with self._serve() as port:
            _post(port, "/api/update/apply", AUTO)
            _st, body = _post(port, "/api/update/apply", MANUAL)
        self.assertNotEqual(body.get("stage"), "auto_skipped", body)
        self.assertEqual(self.order.count("apply"), 2, "试过自动之后,业主手动点「更新」被挡住了")

    def test_au7_cannot_record_means_do_not_touch_anything(self):
        """记不下 ⇒ 下次打开还会再自动试 ⇒ 循环。宁可这次不自动。"""
        _touch(os.path.join(self.data_root, "Logs"))      # Logs 是个文件,里面建不了东西
        with self._serve() as port:
            _st, body = _post(port, "/api/update/apply", AUTO)
        self.assertFalse(body.get("ok"))
        self.assertEqual(body.get("stage"), "auto_unrecorded", body)
        self.assertEqual(self.order, [], "账没记上就开始准备更新了")

    def test_au8_a_garbage_record_is_an_empty_record(self):
        os.makedirs(os.path.dirname(self.record))
        with open(self.record, "wb") as fh:
            fh.write(b"\x00\xffnot json {{{")
        with self._serve() as port:
            before = self._auto(port)
            _post(port, "/api/update/apply", AUTO)
            after = self._auto(port)
        self.assertEqual(before, {"eligible": True, "why_not": None},
                         "账是坏的就永远不自动更新了:%r" % (before,))
        self._assert_not(after, "attempted")

    def test_au9_earlier_attempts_are_kept(self):
        """追加,不覆盖。覆盖的话:试 A → 试 B → 线上撤回 B ⇒ A 又会被自动试一遍。"""
        self.apply_ok = False   # 准备失败 ⇒ 锁放开(t35:接力脚本起来之后锁不放,第二次会是 busy)
        with self._serve() as port:
            self.releases = _without(_fixture(), "win-installer-" + LATEST)   # 线上最新是 0.98.2
            ds_update.cache_clear()
            _post(port, "/api/update/apply", AUTO)
            self.releases = _fixture()                                        # 线上最新变成 0.98.3
            ds_update.cache_clear()
            _post(port, "/api/update/apply", AUTO)
            self.releases = _without(_fixture(), "win-installer-" + LATEST)   # 0.98.3 被撤回
            ds_update.cache_clear()
            again = self._auto(port)
        self.assertEqual(self.order.count("apply"), 2, "前提没摆好:两个版本应各自动试一次")
        self._assert_not(again, "attempted")

    def test_au10_only_logs_is_written_under_the_data_root(self):
        """t13 死线的同一条:更新前后 Data\\ 与 UserData\\ 逐字节不变,Logs\\ 豁免。"""
        with self._serve() as port:
            _post(port, "/api/update/apply", AUTO)
        self.assertTrue(os.path.isfile(self.record), "记账文件不在约定位置 <数据根>/Logs/%s" % RECORD_NAME)
        self.assertEqual(sorted(os.listdir(self.data_root)), ["Logs"],
                         "自动那条路在数据根下写了 Logs 以外的东西")

    def test_au11_a_string_true_is_not_auto(self):
        """只有 JSON 的 true 才算自动;其余一律手动语义(手动那条路一行不改)。"""
        self.apply_ok = False   # 准备失败 ⇒ 锁放开(t35:接力脚本起来之后锁不放,第二次会是 busy)
        with self._serve() as port:
            _post(port, "/api/update/apply", AUTO)
            _st, body = _post(port, "/api/update/apply", b'{"auto": "true"}')
        self.assertNotEqual(body.get("stage"), "auto_skipped", body)
        self.assertEqual(self.order.count("apply"), 2)

    def test_au12_a_refused_auto_request_records_nothing(self):
        """不满足条件被拒的自动请求不许记账 —— 否则浏览器里点开一次,就把桌面版以后的自动更新也关掉了。"""
        with mock.patch.dict(os.environ, {"DS_SHELL_LOCK_PORT": ""}):
            with self._serve() as port:
                _st, body = _post(port, "/api/update/apply", AUTO)
        self.assertEqual(body.get("stage"), "auto_skipped", body)
        self.assertEqual(self.order, [])
        self.assertFalse(os.path.exists(self.record), "被拒的自动请求也记了账")


if __name__ == "__main__":
    unittest.main()
