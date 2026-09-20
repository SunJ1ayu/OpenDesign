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
import time
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
import ds_update_startup  # noqa: E402
import hashlib  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "update",
                       "github-releases-20260907.json")
LATEST = "0.98.3"           # 夹具里最新的那一版
RECORD_NAME = "auto-update-attempts.json"
AUTO_KNOB = "OPENDESIGN_AUTO_UPDATE"   # 值为 off ⇒ why_not="disabled"(Windows 真机判据关掉产品自己的倒计时用)
AUTO = b'{"auto": true}'
MANUAL = b"{}"              # 界面上那个「更新」按钮发的就是它(App.tsx applyUpdate)


def _fixture():
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


def _without(releases, tag):
    return [r for r in releases if r.get("tag_name") != tag]


def _upto(releases, version):
    """只留版本号 ≤ version 的正式安装包 release(夹具里的 spike / data-outside 这类 tag 产品本来就不认)。"""
    want = ds_update.parse_version(version)
    out = []
    for r in releases:
        m = ds_update.TAG_RE.match(r.get("tag_name") or "")
        if m and ds_update.parse_version(m.group(1)) <= want:
            out.append(r)
    return out


def _renamed(release, old, new):
    """把一个 release 整个改名成另一个版本号(tag、安装包名、下载地址一起改),摆出 0.98.10 这种夹具里没有的版本。"""
    return json.loads(json.dumps(release).replace(old, new))


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
        os.environ.pop(AUTO_KNOB, None)
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
        self.seen_at_apply = []     # apply_update 被叫到那一刻,**产品自己**(查更新)怎么看这个版本
        self.apply_ok = True
        self.port = None

        def fake_apply(decision, paths, **kw):
            self.order.append("apply")
            # 攻题 #2/#17:不读文件找子串(那样"先写一句裸文本、事后再补成合法账"也绿,
            # 而合法的别种表示法反而红)。问产品自己:这一刻它认不认这个版本已经自动试过。
            try:
                _st, body = _get(self.port, "/api/update/check")
                self.seen_at_apply.append((body or {}).get("auto_update"))
            except Exception as e:  # noqa: BLE001
                self.seen_at_apply.append("check failed: %r" % (e,))
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
        self.port = httpd.server_address[1]
        try:
            yield self.port
        finally:
            httpd.shutdown()
            httpd.server_close()

    def _auto_apply(self, port):
        """发一次"打开软件时的自动安装"请求。

        🔴 **前提变更(2026-09-19,track opendesign-startup-not-blocked-by-update)**:
        业主把规格改了 ——「不应该让用户看到这个界面…没更新就跟平时打开软件一样」。
        自动安装装的因此是**盘上已经下好、校验过的那个包**(后台备货),
        不再是"打开软件那一刻查到的新版"(那条路要联网,实测最坏干等 20.1 秒)。

        所以发请求之前得先把备货摆上。**下面每一条断言一个字都没改**:
        它们问的是记账与防循环(动手前先记账 / 账不被缓存吞掉 / 试过的版本不再自动试),
        问的从来不是"谁触发的" —— 触发点换了,这些账照样必须成立。
        摆备货对旧实现是**无害的多余动作**(旧实现根本不读它),
        所以这次改动没有放松任何一条:见 verify.md 里"旧实现照样全绿"的收据。
        """
        self._stock_latest()
        return _post(port, "/api/update/apply", AUTO)

    def _stock_latest(self):
        """把此刻 self.releases 里的最新版摆成"后台已经下好"的样子(离线,不打网)。"""
        info = ds_update.check_for_update(ds_web.VERSION)
        # 🔴 门槛用**产品自己**那套(_asset_facts):缺 digest / 缺地址 / 大小不对的资产,
        #    后台备货本来就不会下 ⇒ 判据也不许替它摆上,否则 au12a 那种"资产被拒"的
        #    场景会被夹具偷偷救活。
        facts = ds_update_startup._asset_facts(info)
        if facts is None:
            return None
        version, asset = facts["version"], {"name": facts["name"], "url": facts["url"]}
        payload = ("pretend installer for %s" % version).encode("utf-8")
        d = os.path.join(self.data_root, "Logs", "pending")
        path = os.path.join(d, asset["name"])
        try:
            os.makedirs(d, exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(payload)
        except OSError:
            return None        # 备不上货就别摆:让请求照它自己的路子被拒,别掩盖真实死法
        ds_update_startup.write_state(
            ds_update_startup.state_path(self.data_root),
            {"schema": 1, "phase": "ready", "version": version,
             "asset": {"name": asset["name"], "size": len(payload),
                       "sha256": hashlib.sha256(payload).hexdigest(),
                       "url": asset.get("url") or "https://example.invalid/setup.exe"},
             "path": path, "updated_at": time.time()})
        return path

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
        self.assertEqual(body.get("auto_update"), {"eligible": True, "why_not": None, "recent_failure": False},
                         "装出来的桌面版 + 有可装的新版 + 没试过,却不让倒计时:%r" % (body.get("auto_update"),))
        for k in ("current", "update_available", "latest", "asset", "notes", "error", "release_url"):
            self.assertIn(k, body, "原有字段 %s 丢了" % k)
        self.assertEqual(body["latest"], LATEST)
        # 攻题二 #4:查更新(GET)只许回答「能不能倒计时」,**自己绝不许开始更新** —— 倒计时和取消由页面做。
        self.assertEqual(self.order, [], "查更新这个 GET 自己开始准备更新了 —— 业主来不及取消")

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
            self._auto_apply(port)
            ds_update.cache_clear()
            self._assert_not(self._auto(port), "attempted")

    # --- au3 ~ au12:自动那条路 ------------------------------------------------

    def test_au3_the_attempt_is_written_before_anything_is_prepared(self):
        """🔴 预写。接力脚本回滚、旧版被重新拉起时,界面早就没了 —— 只有动手前记下的账才活得过那一刻。

        替身 apply_update 里向同一个服务发一次查更新(10 秒超时)。这也顺带钉住:**查更新不许等更新锁**
        —— 真实更新要下载几十 MB,等锁的查更新会在那几分钟里一直挂着(攻题二 #7 我核后判为规格要求,不是判据误红)。"""
        with self._serve() as port:
            st, body = self._auto_apply(port)
        self.assertEqual(st, 200)
        self.assertEqual(self.order, ["apply", "handoff", "bridge"],
                         "自动那条路的顺序不对(或根本没走到安装):%r / %r" % (self.order, body))
        self.assertTrue(body.get("ok"), body)
        self.assertEqual(len(self.seen_at_apply), 1)
        seen = self.seen_at_apply[0]
        self.assertIsInstance(seen, dict, "开始准备的那一刻查更新没答上来:%r" % (seen,))
        self.assertEqual((seen.get("eligible"), seen.get("why_not")), (False, "attempted"),
                         "开始准备的那一刻,产品自己还不认为这个版本自动试过 —— 回滚之后下次打开会再自动试:%r" % (seen,))

    def test_au4_a_failed_attempt_is_seen_through_the_cache_and_a_restart(self):
        """查更新结果缓存 6 小时。auto_update 若跟着进了缓存,同一进程里下一次查仍说 eligible。
        换一个新进程(新 server、缓存清空)也必须还认得 —— 回滚之后被拉起的就是一个新进程。"""
        self.apply_ok = False
        with self._serve() as port:
            before = self._auto(port)
            _st, body = self._auto_apply(port)
            after = self._auto(port)          # 不带 force
        self.assertEqual(before.get("eligible"), True, "前提没摆好:%r" % (before,))
        self.assertEqual(body.get("stage"), "verify", "前提没摆好:准备应当失败在 verify:%r" % (body,))
        self._assert_not(after, "attempted")
        ds_update.cache_clear()
        with self._serve() as port:
            self._assert_not(self._auto(port), "attempted")

    def test_au5_an_attempted_version_is_refused_on_the_server_too(self):
        """服务端二次把关:界面慢一拍、两个窗口同时倒计时、别的页面直接发请求,都绕不过去。"""
        self.apply_ok = False   # 准备失败 ⇒ 锁放开(t35:接力脚本起来之后锁不放,第二次会是 busy)
        with self._serve() as port:
            self._auto_apply(port)
            _st, body = self._auto_apply(port)
        self.assertFalse(body.get("ok"))
        self.assertEqual(body.get("stage"), "auto_skipped", body)
        self.assertEqual(self.order.count("apply"), 1, "试过的版本又被自动装了一遍")

    def test_au6_manual_update_still_works_for_an_attempted_version(self):
        """反面(防修过头):不再**自动**试,不等于业主自己点也不让装。"""
        self.apply_ok = False   # 准备失败 ⇒ 锁放开(t35:接力脚本起来之后锁不放,第二次会是 busy)
        with self._serve() as port:
            self._auto_apply(port)
            _st, body = _post(port, "/api/update/apply", MANUAL)
        self.assertNotEqual(body.get("stage"), "auto_skipped", body)
        self.assertEqual(self.order.count("apply"), 2, "试过自动之后,业主手动点「更新」被挡住了")

    def test_au7_cannot_record_means_do_not_touch_anything(self):
        """记不下 ⇒ 下次打开还会再自动试 ⇒ 循环。宁可这次不自动。"""
        # 🔴 2026-09-20 前提收窄(track opendesign-startup-not-blocked-by-update):
        #    原来这里把整个 Logs 变成文件。新流程下备货的状态文件也住 Logs ⇒ 那样连货都备不上,
        #    自动安装在更早一步就停了,**问不出**"记不下账该怎么办"。
        #    改成只让**记账文件**写不进去(它自己是个目录),断言一个字没改。
        os.makedirs(os.path.join(self.data_root, "Logs"), exist_ok=True)
        os.makedirs(self.record, exist_ok=True)           # 记账文件的位置是个目录 ⇒ 换名必失败
        with self._serve() as port:
            _st, body = self._auto_apply(port)
        self.assertFalse(body.get("ok"))
        self.assertEqual(body.get("stage"), "auto_unrecorded", body)
        self.assertEqual(self.order, [], "账没记上就开始准备更新了")

    def test_au8_a_garbage_record_is_an_empty_record(self):
        os.makedirs(os.path.dirname(self.record))
        with open(self.record, "wb") as fh:
            fh.write(b"\x00\xffnot json {{{")
        with self._serve() as port:
            before = self._auto(port)
            self._auto_apply(port)
            after = self._auto(port)
        self.assertEqual(before, {"eligible": True, "why_not": None, "recent_failure": False},
                         "账是坏的就永远不自动更新了:%r" % (before,))
        self._assert_not(after, "attempted")

    def test_au9_earlier_attempts_are_kept(self):
        """追加,不覆盖。覆盖的话:试 A → 试 B → 线上撤回 B ⇒ A 又会被自动试一遍。"""
        self.apply_ok = False   # 准备失败 ⇒ 锁放开(t35:接力脚本起来之后锁不放,第二次会是 busy)
        with self._serve() as port:
            self.releases = _without(_fixture(), "win-installer-" + LATEST)   # 线上最新是 0.98.2
            ds_update.cache_clear()
            self._auto_apply(port)
            self.releases = _fixture()                                        # 线上最新变成 0.98.3
            ds_update.cache_clear()
            self._auto_apply(port)
            self.releases = _without(_fixture(), "win-installer-" + LATEST)   # 0.98.3 被撤回
            ds_update.cache_clear()
            again = self._auto(port)
        self.assertEqual(self.order.count("apply"), 2, "前提没摆好:两个版本应各自动试一次")
        self._assert_not(again, "attempted")

    def test_au9b_a_withdrawn_newer_attempt_does_not_block_an_untried_older_one(self):
        """攻题 #14:只记"试过的最大版本"、按 ≤ 判 attempted 的写法 —— 试 0.98.3 → 撤回 ⇒ 从没试过的 0.98.2 被误封。"""
        self.apply_ok = False
        with self._serve() as port:
            self._auto_apply(port)                          # 自动试 0.98.3
            self.releases = _without(_fixture(), "win-installer-" + LATEST)  # 撤回 0.98.3
            ds_update.cache_clear()
            auto = self._auto(port)
        self.assertEqual(self.order.count("apply"), 1, "前提没摆好")
        self.assertEqual(auto.get("why_not"), None, "0.98.2 从没自动试过,却不让倒计时:%r" % (auto,))
        self.assertIs(auto.get("eligible"), True)

    def test_au9c_versions_are_compared_exactly(self):
        """攻题 #14:子串 / 前缀 / 字典序 —— 试过 0.98.1,不等于试过 0.98.10。"""
        self.apply_ok = False
        base = _upto(_fixture(), "0.98.1")
        self.assertEqual(ds_update.decide("0.90.0", base)["latest"], "0.98.1", "前提没摆好")
        ten = _renamed(base[0], "0.98.1", "0.98.10")
        with self._serve() as port:
            self.releases = base
            self._auto_apply(port)                          # 自动试 0.98.1
            self.releases = [ten] + base
            ds_update.cache_clear()
            auto = self._auto(port)
        self.assertEqual(self.order.count("apply"), 1, "前提没摆好")
        self.assertEqual(auto, {"eligible": True, "why_not": None, "recent_failure": False},
                         "0.98.10 从没试过,却被当成试过了(拿 0.98.1 做了子串 / 前缀比较?):%r" % (auto,))

    def test_au10_only_logs_is_written_under_the_data_root(self):
        """t13 死线的同一条:更新前后 Data\\ 与 UserData\\ 逐字节不变,Logs\\ 豁免。"""
        with self._serve() as port:
            self._auto_apply(port)
        self.assertTrue(os.path.isfile(self.record), "记账文件不在约定位置 <数据根>/Logs/%s" % RECORD_NAME)
        self.assertEqual(sorted(os.listdir(self.data_root)), ["Logs"],
                         "自动那条路在数据根下写了 Logs 以外的东西")

    def test_au11_a_string_true_is_not_auto(self):
        """只有 JSON 的 true 才算自动;其余一律手动语义(手动那条路一行不改)。"""
        self.apply_ok = False   # 准备失败 ⇒ 锁放开(t35:接力脚本起来之后锁不放,第二次会是 busy)
        with self._serve() as port:
            self._auto_apply(port)
            _st, body = _post(port, "/api/update/apply", b'{"auto": "true"}')
        self.assertNotEqual(body.get("stage"), "auto_skipped", body)
        self.assertEqual(self.order.count("apply"), 2)

    # --- au12:被拒的自动请求什么都不碰 ---------------------------------------
    # 攻题 #13:服务端二次把关要把**每一个**条件都重判一遍,不是只判 attempted / no_shell。
    # 被拒的自动请求:回 auto_skipped、不准备、**不记账**(否则条件修好之后这一版也永远不会再自动试;
    # 浏览器里点开一次,也会把桌面版以后的自动更新关掉)。

    def _refused(self, why, install_root=None):
        with self._serve(install_root) as port:
            _st, body = self._auto_apply(port)
            again = self._auto(port)
        self.assertEqual(body.get("stage"), "auto_skipped", body)
        self.assertEqual(self.order, [], "条件不满足却开始准备了")
        self.assertFalse(os.path.exists(self.record), "被拒的自动请求也记了账")
        self.assertEqual(again.get("why_not"), why, "被拒之后原因变了(记了账?):%r" % (again,))

    def test_au12a_refused_asset(self):
        rel = _fixture()
        for a in rel[0].get("assets", []):
            a["digest"] = None
        self.releases = rel
        self._refused("asset")

    def test_au12b_refused_no_shell(self):
        with mock.patch.dict(os.environ, {"DS_SHELL_LOCK_PORT": ""}):
            self._refused("no_shell")

    def test_au12c_refused_not_installed(self):
        os.remove(os.path.join(self.install_root, "OpenDesign.exe"))
        self._refused("not_installed")

    def test_au12d_refused_path_unsupported(self):
        self._refused("path_unsupported", self._install("Open%Design"))

    def test_au12e_refused_disabled(self):
        with mock.patch.dict(os.environ, {AUTO_KNOB: "off"}):
            self._refused("disabled")

    def test_au13_a_failed_write_keeps_the_old_record_and_touches_nothing(self):
        """攻题 #3 / 攻题二 #8:写记账必须是「同目录临时文件 → 写完 flush → 对**这个临时文件** os.fsync → os.replace 到记账文件」。
        原地截断重写的实现,写到一半崩掉 ⇒ 半截 JSON ⇒ 下次读成空账 ⇒ 又自动试。
        判据按模块属性注入 os.fsync / os.replace(规格写明调用方式;`from os import fsync` 这种别名注入不到)。"""
        self.apply_ok = False
        synced, replaced = [], []
        real_fsync, real_replace = os.fsync, os.replace

        def spy_fsync(fd):
            # 按 inode 认文件(不靠 /proc,Windows 上 PY=... tests/run-all.sh 也跑这份);
            # 记下 fsync 那一刻文件在 OS 里有多大 —— 没 flush 就 fsync,小文件在这里是 0 字节。
            st = os.fstat(fd)
            synced.append((st.st_dev, st.st_ino, st.st_size))
            return real_fsync(fd)

        def spy_replace(a, b, **kw):
            try:
                st = os.stat(a)
                with open(a, encoding="utf-8") as fh:
                    json.loads(fh.read())
                src = (st.st_dev, st.st_ino, st.st_size, True)
            except (OSError, ValueError):
                src = (None, None, None, False)
            replaced.append((os.path.realpath(a), os.path.realpath(b), src, list(synced)))
            return real_replace(a, b, **kw)

        with mock.patch("os.fsync", spy_fsync), mock.patch("os.replace", spy_replace):
            with self._serve() as port:
                self.releases = _upto(_fixture(), "0.98.2")
                self._auto_apply(port)                      # 0.98.2 记上
        into_record = [r for r in replaced if r[1] == os.path.realpath(self.record)]
        self.assertTrue(into_record, "记账没有用 os.replace 换到 %s(原地写?):%r" % (self.record, replaced))
        src_path, _dst, (dev, ino, size, complete), synced_before = into_record[-1]
        self.assertNotEqual(src_path, os.path.realpath(self.record), "临时文件就是记账文件本身")
        self.assertEqual(os.path.dirname(src_path), os.path.dirname(os.path.realpath(self.record)),
                         "临时文件不在同一个目录(跨盘 replace 不是原子的)")
        self.assertTrue(complete, "换名那一刻临时文件里不是完整的 JSON")
        self.assertIn((dev, ino, size), synced_before,
                      "换名之前没有对这个临时文件做 fsync,或 fsync 时内容还没 flush 完(那一刻的大小和换名时不同):"
                      "synced=%r src=%r" % (synced_before, (dev, ino, size)))

        def broken_replace(a, b, **kw):
            raise OSError("判据注入:换名那一刻失败")

        ds_update.cache_clear()
        self.releases = _fixture()                                          # 线上最新 0.98.3
        self._stock_latest()          # 备货得在注入之前摆:注入的是 os.replace,写状态文件也走它
        with mock.patch("os.replace", broken_replace):
            with self._serve() as port:
                _st, body = _post(port, "/api/update/apply", AUTO)
        self.assertEqual(body.get("stage"), "auto_unrecorded", body)
        self.assertEqual(self.order.count("apply"), 1, "0.98.3 的账没记上就开始准备了")
        ds_update.cache_clear()
        with self._serve() as port:
            self.releases = _upto(_fixture(), "0.98.2")
            self._assert_not(self._auto(port), "attempted")   # 旧账完好
            self.releases = _fixture()
            ds_update.cache_clear()
            self.assertEqual(self._auto(port).get("eligible"), True, "没记上的 0.98.3 却被当成试过了")

    def test_au14_disabled_is_judged_last(self):
        """OPENDESIGN_AUTO_UPDATE=off ⇒ disabled。它排在**最后**:Windows 真机判据(aw1)靠
        「看到 disabled = 其余条件在真机上全成立」来证明倒计时真会出现。"""
        for value in ("off", "OFF"):
            with mock.patch.dict(os.environ, {AUTO_KNOB: value}):
                with self._serve() as port:
                    self._assert_not(self._auto(port), "disabled")
        with mock.patch.dict(os.environ, {AUTO_KNOB: "on"}):
            with self._serve() as port:
                self.assertEqual(self._auto(port).get("eligible"), True, "只有 off 才关;别的值不许关掉")
        exe = os.path.join(self.install_root, "OpenDesign.exe")
        os.remove(exe)
        with mock.patch.dict(os.environ, {AUTO_KNOB: "off"}):
            with self._serve() as port:
                self._assert_not(self._auto(port), "not_installed")
        _touch(exe)
        self.apply_ok = False
        with self._serve() as port:
            self._auto_apply(port)
            with mock.patch.dict(os.environ, {AUTO_KNOB: "off"}):
                self._assert_not(self._auto(port), "attempted")

    def test_au15_a_recent_failed_attempt_is_reported_once_the_app_is_back(self):
        """攻题 #1:接力脚本回滚、旧版被拉起之后,业主眼前得有一句「上次自动更新没成功」。
        GET 面只读(不许在查更新里记"已提示过"),所以用时间界定:自动试过、仍是旧版、且不到 10 分钟 ⇒ recent_failure。
        时间一律按 time.time() 算。"""
        self.apply_ok = False
        with self._serve() as port:
            fresh = self._auto(port)
            self._auto_apply(port)
            recent = self._auto(port)
            with mock.patch("time.time", return_value=time.time() + 590):
                still = self._auto(port)
            with mock.patch("time.time", return_value=time.time() + 610):
                old = self._auto(port)
        self.assertIs(fresh.get("recent_failure"), False, fresh)
        self.assertEqual(recent, {"eligible": False, "why_not": "attempted", "recent_failure": True},
                         "刚自动试过、还是旧版,却没标出来 —— 回滚之后业主眼前什么都没有:%r" % (recent,))
        self.assertIs(still.get("recent_failure"), True, "10 分钟之内就不报了:%r" % (still,))
        self.assertEqual(old, {"eligible": False, "why_not": "attempted", "recent_failure": False},
                         "过了 10 分钟每次打开还报「上次没成功」:%r" % (old,))

    def test_au15b_recent_failure_is_per_version(self):
        """攻题二 #6:只存一个全局「最后尝试时刻」的写法 —— 很久前试过 A、刚试过 B、B 被撤回 ⇒ 把 A 说成「刚失败」。"""
        self.apply_ok = False
        t0 = time.time()
        with self._serve() as port:
            self.releases = _upto(_fixture(), "0.98.2")
            with mock.patch("time.time", return_value=t0):
                self._auto_apply(port)                      # t0 试 0.98.2
            self.releases = _fixture()
            ds_update.cache_clear()
            with mock.patch("time.time", return_value=t0 + 1000):
                self._auto_apply(port)                      # t0+1000 试 0.98.3
            self.releases = _upto(_fixture(), "0.98.2")                     # 0.98.3 撤回
            ds_update.cache_clear()
            with mock.patch("time.time", return_value=t0 + 1010):
                a = self._auto(port)
        self.assertEqual(self.order.count("apply"), 2, "前提没摆好")
        self.assertEqual(a, {"eligible": False, "why_not": "attempted", "recent_failure": False},
                         "0.98.2 是 1000 秒前试的,却被说成刚失败(刚失败的是 0.98.3):%r" % (a,))


if __name__ == "__main__":
    unittest.main()
