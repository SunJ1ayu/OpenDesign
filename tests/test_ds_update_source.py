"""判据:查更新不再只靠会被未登录限流的 GitHub API(track opendesign-update-check-rate-limit)。

编号权威表在 tracks/opendesign-update-check-rate-limit/design.md(前缀 rl)。

🔴 由来:业主 09-15 夜装着 0.98.4,开着 VPN 点「检查更新」一直「查不到更新」,本机取回的原文是
`查更新失败:HTTPError: HTTP Error 403: rate limit exceeded` —— 未登录 API 每个出口 IP 每小时 60 次,
商用 VPN 出口很多人共用。新查法:github.com 的 releases.atom 为主 + 每版清单 OpenDesign-update.json,API 为备。

**判据不许有外网出口**:本文件在 setUpModule 里把 DNS 换成"非本机一律拒绝",漏打真网会当场报错而不是悄悄出去。
"""
import json
import os
import socket
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_update  # noqa: E402

REPO = "SunJ1ayu/OpenDesign"
ATOM = os.path.join(ROOT, "tests", "fixtures", "update", "releases-atom-20260915.xml")
API = os.path.join(ROOT, "tests", "fixtures", "update", "github-releases-20260907.json")
HEX = "ab" * 32

_real_gai = socket.getaddrinfo
_patch = None


def _local_only(host, *args, **kwargs):
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise OSError("判据不许有外网出口:%s" % host)
    return _real_gai(host, *args, **kwargs)


def setUpModule():
    global _patch
    _patch = mock.patch("socket.getaddrinfo", _local_only)
    _patch.start()


def tearDownModule():
    _patch.stop()


def atom_text(tags=None):
    """真夹具;`tags` 给出时按顺序把三个 entry 的 tag 换掉(链接、id 一起换)。"""
    with open(ATOM, encoding="utf-8") as fh:
        text = fh.read()
    if tags:
        for old, new in zip(["0.98.5", "0.98.4", "0.98.3"], tags):
            text = text.replace("win-installer-%s" % old, "win-installer-%s" % new)
    return text


def manifest(tag="win-installer-0.99.1", version="0.99.1", name=None, size=12345,
             sha256=HEX, schema=1, notes="## 这一版改了什么\n\n修了查更新。"):
    return json.dumps({
        "schema": schema, "tag": tag, "version": version,
        "asset": {"name": name or "OpenDesign-Setup-%s.exe" % version, "size": size, "sha256": sha256},
        "notes": notes,
    }, ensure_ascii=False)


def api_releases():
    with open(API, encoding="utf-8") as fh:
        return json.load(fh)


class _Sources:
    """把三处联网都换成替身,并记下谁被问过。"""

    def __init__(self, test, atom=None, manifests=None, api=None):
        self.calls = []
        self.atom, self.manifests, self.api = atom, manifests or {}, api
        for name, fn in (("fetch_atom", self._atom), ("fetch_manifest", self._manifest),
                         ("fetch_releases", self._api)):
            p = mock.patch.object(ds_update, name, fn)
            p.start()
            test.addCleanup(p.stop)

    def _atom(self, *a, **kw):
        self.calls.append(("atom",))
        if isinstance(self.atom, Exception):
            raise self.atom
        return self.atom

    def _manifest(self, tag, *a, **kw):
        self.calls.append(("manifest", tag))
        m = self.manifests.get(tag)
        if isinstance(m, Exception):
            raise m
        if m is None:
            raise urllib.error.HTTPError(ds_update.manifest_url(REPO, tag), 404, "Not Found", {}, None)
        return m

    def _api(self, *a, **kw):
        self.calls.append(("api",))
        if isinstance(self.api, Exception):
            raise self.api
        return self.api

    def asked(self, kind):
        return [c for c in self.calls if c[0] == kind]


def rate_limited():
    return urllib.error.HTTPError(ds_update.releases_url(REPO), 403, "rate limit exceeded", {}, None)


class ParseAtom(unittest.TestCase):
    def test_rl1a_tags_and_links_come_from_the_real_feed_shape(self):
        entries = ds_update.parse_atom(atom_text())
        self.assertEqual([e["tag"] for e in entries],
                         ["win-installer-0.98.5", "win-installer-0.98.4", "win-installer-0.98.3"])
        self.assertEqual(entries[0]["html_url"],
                         "https://github.com/SunJ1ayu/OpenDesign/releases/tag/win-installer-0.98.5")

    def test_rl1b_other_tags_are_dropped(self):
        text = atom_text().replace("win-installer-0.98.4", "some-other-tag")
        self.assertEqual([e["tag"] for e in ds_update.parse_atom(text)],
                         ["win-installer-0.98.5", "win-installer-0.98.3"])

    def test_rl1c_not_xml_raises(self):
        with self.assertRaises(ValueError):
            ds_update.parse_atom("<html>rate limited</html")


class ManifestIsCheckedField_by_field(unittest.TestCase):
    TAG = "win-installer-0.99.1"

    def test_rl3a_good_manifest_becomes_an_api_shaped_asset(self):
        a = ds_update.parse_manifest(manifest(), self.TAG, REPO)
        self.assertEqual(a["name"], "OpenDesign-Setup-0.99.1.exe")
        self.assertEqual(a["size"], 12345)
        self.assertEqual(a["digest"], "sha256:" + HEX)
        self.assertEqual(a["browser_download_url"],
                         "https://github.com/SunJ1ayu/OpenDesign/releases/download/win-installer-0.99.1/"
                         "OpenDesign-Setup-0.99.1.exe")

    def test_rl3b_tag_text_is_used_verbatim_in_the_url(self):
        """F1 教训:两段版本号的 tag 不许被补零成三段再拼进地址。"""
        a = ds_update.parse_manifest(manifest(tag="win-installer-1.0", version="1.0"), "win-installer-1.0", REPO)
        self.assertIn("/releases/download/win-installer-1.0/OpenDesign-Setup-1.0.exe", a["browser_download_url"])

    def test_rl3c_every_mismatch_is_refused(self):
        bad = {
            "tag 不是来路那个": manifest(tag="win-installer-0.99.0"),
            "version 与 tag 不同值": manifest(version="0.99.2", name="OpenDesign-Setup-0.99.1.exe"),
            "文件名里的版本不同值": manifest(name="OpenDesign-Setup-0.99.0.exe"),
            "文件名不是安装包": manifest(name="evil.exe"),
            "sha256 不是 64 位十六进制": manifest(sha256="zz" * 32),
            "sha256 太短": manifest(sha256="ab" * 10),
            "size 为 0": manifest(size=0),
            "size 不是整数": manifest(size="12345"),
            "schema 不认识": manifest(schema=2),
            "不是 JSON": "<html>not found</html>",
            "不是对象": "[]",
        }
        for why, text in bad.items():
            with self.subTest(why):
                with self.assertRaises(ValueError, msg="这份清单该被拒:%s" % why):
                    ds_update.parse_manifest(text, self.TAG, REPO)


class AtomFirstThenApi(unittest.TestCase):
    def test_rl2_the_highest_version_wins_not_the_first_entry(self):
        src = _Sources(self, atom=atom_text(["0.98.5", "0.99.1", "0.98.7"]),
                       manifests={"win-installer-0.99.1": manifest()}, api=rate_limited())
        d = ds_update.check_for_update("0.98.4")
        self.assertEqual(src.asked("manifest"), [("manifest", "win-installer-0.99.1")])
        self.assertTrue(d["update_available"], d)
        self.assertEqual(d["latest"], "0.99.1")

    def test_rl4_when_the_feed_works_the_api_is_never_asked(self):
        src = _Sources(self, atom=atom_text(["0.99.1", "0.98.4", "0.98.3"]),
                       manifests={"win-installer-0.99.1": manifest()}, api=AssertionError("不许问 API"))
        d = ds_update.check_for_update("0.98.4")
        self.assertEqual(src.asked("api"), [], "订阅源已经成功,却还去问了会被限流的 API")
        self.assertIsNone(d["error"])
        self.assertTrue(d["update_available"])
        self.assertEqual(d["latest"], "0.99.1")
        self.assertEqual(d["release_url"], "https://github.com/SunJ1ayu/OpenDesign/releases/tag/win-installer-0.99.1")
        self.assertEqual(d["asset"]["digest"], "sha256:" + HEX)
        self.assertEqual(d["asset"]["size"], 12345)
        self.assertEqual(d["asset"]["url"],
                         "https://github.com/SunJ1ayu/OpenDesign/releases/download/win-installer-0.99.1/"
                         "OpenDesign-Setup-0.99.1.exe")
        self.assertIn("修了查更新", d["notes"])

    def test_rl5a_feed_down_falls_back_to_the_api(self):
        src = _Sources(self, atom=urllib.error.URLError("timed out"), api=api_releases())
        d = ds_update.check_for_update("0.98.1")
        self.assertEqual(len(src.asked("api")), 1)
        self.assertIsNone(d["error"], d)
        self.assertTrue(d["update_available"])

    def test_rl5b_missing_or_bad_manifest_falls_back_to_the_api(self):
        for manifests in ({}, {"win-installer-0.99.1": manifest(tag="win-installer-0.99.0")}):
            with self.subTest(manifests=list(manifests)):
                src = _Sources(self, atom=atom_text(["0.99.1", "0.98.4", "0.98.3"]),
                               manifests=manifests, api=api_releases())
                d = ds_update.check_for_update("0.98.1")
                self.assertEqual(len(src.asked("api")), 1, "清单拿不到/不对,却没回落 API")
                self.assertIsNone(d["error"], d)
                self.assertNotEqual(d["latest"], "0.99.1", "没有可核对清单的版本被当成了可更新目标")

    def test_rl5c_both_down_says_both_reasons_and_offers_nothing(self):
        _Sources(self, atom=urllib.error.URLError("timed out"), api=rate_limited())
        d = ds_update.check_for_update("0.98.4")
        self.assertFalse(d["update_available"])
        self.assertIsNone(d["asset"])
        self.assertTrue(d["error"])
        self.assertIn("订阅源", d["error"])
        self.assertIn("接口", d["error"])

    def test_rl6_not_newer_means_up_to_date_without_fetching_a_manifest(self):
        src = _Sources(self, atom=atom_text(), api=AssertionError("不许问 API"))
        d = ds_update.check_for_update("0.98.5")
        self.assertEqual(src.asked("manifest"), [], "线上最新不比本机新,还去拉清单")
        self.assertEqual(src.asked("api"), [])
        self.assertIsNone(d["error"], d)
        self.assertFalse(d["update_available"])
        self.assertEqual(d["latest"], "0.98.5")


class HumanReasons(unittest.TestCase):
    def test_rl7a_rate_limit_is_explained(self):
        d = ds_update.check_for_update("0.98.4", fetch=lambda: (_ for _ in ()).throw(rate_limited()))
        self.assertIn("限制了这个网络出口的查询次数", d["error"])
        self.assertIn("403", d["error"], "技术细节要留在括号里,排障用")

    def test_rl7b_timeout_and_unreachable_are_explained(self):
        for exc in (urllib.error.URLError("timed out"), socket.timeout("timed out"), ConnectionResetError()):
            with self.subTest(exc=type(exc).__name__):
                d = ds_update.check_for_update("0.98.4", fetch=lambda e=exc: (_ for _ in ()).throw(e))
                self.assertIn("连不上 GitHub", d["error"])


class ExplicitFetchIsTheOnlySource(unittest.TestCase):
    def test_rl9_injected_fetch_never_touches_the_feed(self):
        src = _Sources(self, atom=AssertionError("注入了 fetch 还去问订阅源"), api=AssertionError("x"))
        d = ds_update.check_for_update("0.98.1", fetch=api_releases)
        self.assertEqual(src.asked("atom"), [])
        self.assertEqual(src.asked("manifest"), [])
        self.assertTrue(d["update_available"])


class ProxyIsReadAtRequestTime(unittest.TestCase):
    """rl8 —— 三处联网都在请求那一刻读代理(t30b 同法;查更新那条当时漏了)。"""

    def _through_fake_proxy(self, call):
        seen, direct = [], []

        class FakeProxy(BaseHTTPRequestHandler):
            def do_CONNECT(self):
                seen.append(self.path)
                self.send_response(502)
                self.end_headers()

            def log_message(self, *args):
                pass

        srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeProxy)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        proxy = "http://127.0.0.1:%d" % srv.server_address[1]

        def record_direct(host, *args, **kwargs):
            if host not in ("127.0.0.1", "localhost", "::1"):
                direct.append(host)
            return _local_only(host, *args, **kwargs)

        self.addCleanup(urllib.request.install_opener, None)
        # 模拟"进程早先已经联过网":装一个当时的、不走代理的全局 opener
        urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
        env = {"https_proxy": proxy, "HTTPS_PROXY": proxy, "http_proxy": proxy, "HTTP_PROXY": proxy,
               "no_proxy": "", "NO_PROXY": ""}
        with mock.patch.dict(os.environ, env), mock.patch("socket.getaddrinfo", record_direct):
            with self.assertRaises(Exception):
                call()
        return direct, seen

    def test_rl8a_api(self):
        direct, seen = self._through_fake_proxy(lambda: ds_update.fetch_releases(REPO))
        self.assertEqual(direct, [], "查更新(API)用了进程早先缓存的代理设置,直连了 %s" % direct)
        self.assertTrue(any(p.startswith("api.github.com:443") for p in seen), seen)

    def test_rl8b_feed(self):
        direct, seen = self._through_fake_proxy(lambda: ds_update.fetch_atom(REPO))
        self.assertEqual(direct, [], "订阅源直连了 %s" % direct)
        self.assertTrue(any(p.startswith("github.com:443") for p in seen), seen)

    def test_rl8c_manifest(self):
        direct, seen = self._through_fake_proxy(lambda: ds_update.fetch_manifest("win-installer-0.99.1", REPO))
        self.assertEqual(direct, [], "清单直连了 %s" % direct)
        self.assertTrue(any(p.startswith("github.com:443") for p in seen), seen)

    def test_rl8e_manifest_is_asked_for_as_a_file_not_as_json(self):
        """🔴 2026-09-15 夜真 GitHub 冒烟照出来的(单测替身结构上问不到):
        `github.com/<repo>/releases/download/<tag>/<asset>` **带 `Accept: application/json` 就回 404**,
        `application/octet-stream` 或 `*/*` 才 302 到资产 CDN(curl 三种 Accept 各打一次实测)。
        第一版实现给清单请求写了 application/json ⇒ 真 GitHub 上清单永远"找不到"、每次都回落 API,
        而 rl1~rl9 全绿。这里钉住发出去的请求头。
        """
        seen = {}

        class _Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return b"{}"

        def fake_open(director, req, data=None, timeout=None):
            seen["accept"] = req.get_header("Accept")
            seen["url"] = req.full_url
            return _Resp()

        with mock.patch.object(urllib.request.OpenerDirector, "open", fake_open):
            ds_update.fetch_manifest("win-installer-0.99.1", REPO)
        self.assertEqual(seen["url"], ds_update.manifest_url(REPO, "win-installer-0.99.1"))
        self.assertNotIn("json", (seen.get("accept") or "").lower(),
                         "清单请求带了 JSON 的 Accept —— 真 GitHub 的下载地址对它回 404")
        self.assertEqual(seen.get("accept"), "application/octet-stream")

    def test_rl8d_urls_are_the_seam_urls(self):
        self.assertEqual(ds_update.atom_url(REPO), "https://github.com/SunJ1ayu/OpenDesign/releases.atom")
        self.assertEqual(ds_update.manifest_url(REPO, "win-installer-0.99.1"),
                         "https://github.com/SunJ1ayu/OpenDesign/releases/download/win-installer-0.99.1/"
                         "OpenDesign-update.json")


if __name__ == "__main__":
    unittest.main(verbosity=2)
