"""判据:查更新不再只靠会被未登录限流的 GitHub API(track opendesign-update-check-rate-limit)。

编号权威表在 tracks/opendesign-update-check-rate-limit/design.md(前缀 rl)。

🔴 由来:业主 09-15 夜装着 0.98.4,开着 VPN 点「检查更新」一直「查不到更新」,本机取回的原文是
`查更新失败:HTTPError: HTTP Error 403: rate limit exceeded` —— 未登录 API 每个出口 IP 每小时 60 次,
商用 VPN 出口很多人共用。新查法:github.com 的 releases.atom 为主 + 每版清单 OpenDesign-update.json,API 为备。

**判据不许有外网出口**:本文件在 setUpModule 里把 DNS 换成"非本机一律拒绝",漏打真网会当场报错而不是悄悄出去。
"""
import http.client
import json
import os
import socket
import ssl
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

    def test_rl1d_links_to_other_repos_are_dropped(self):
        """评审(切片 core DeepSeek #2):链接正则原来不钉仓库,别的仓库的 tag 链接会被当成本仓版本、release_url 原样透传。"""
        text = atom_text().replace("https://github.com/SunJ1ayu/OpenDesign/releases/tag/win-installer-0.98.4",
                                   "https://github.com/EVIL/Other/releases/tag/win-installer-0.98.4")
        entries = ds_update.parse_atom(text, REPO)
        self.assertEqual([e["tag"] for e in entries], ["win-installer-0.98.5", "win-installer-0.98.3"])
        self.assertTrue(all(e["html_url"].startswith("https://github.com/SunJ1ayu/OpenDesign/") for e in entries))

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
            # 评审(overall GPT #1,我复现):`$` 配 match() 会放过末尾换行 ⇒ 下载地址 / 本地文件名带换行,Windows 存不下
            "文件名末尾带换行": manifest(name="OpenDesign-Setup-0.99.1.exe\n"),
        }
        for why, text in bad.items():
            with self.subTest(why):
                with self.assertRaises(ValueError, msg="这份清单该被拒:%s" % why):
                    ds_update.parse_manifest(text, self.TAG, REPO)


class TrailingNewlinesAreNotVersions(unittest.TestCase):
    def test_rl3d_tag_with_trailing_newline_is_refused(self):
        tag = "win-installer-0.99.1\n"
        with self.assertRaises(ValueError):
            ds_update.parse_manifest(manifest(tag=tag), tag, REPO)
        self.assertIsNone(ds_update.TAG_RE.match(tag), "TAG_RE 的 $ 放过了末尾换行")
        self.assertIsNone(ds_update.ASSET_RE.match("OpenDesign-Setup-0.99.1.exe\n"))


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

    def test_rl5d_feed_saw_a_newer_version_but_the_api_fallback_says_up_to_date(self):
        """评审(切片 core DeepSeek #1 中 / 整份 DeepSeek #3):订阅源看见 0.99.1 但清单不可核对,回落 API 又说没有更新
        ⇒ 原来返回一条干净的「已是最新」(且进 6 小时缓存)。线上明明有新版 —— 这是在撒谎。必须带着原因失败(不进缓存)。"""
        _Sources(self, atom=atom_text(["0.99.1", "0.98.4", "0.98.3"]), manifests={}, api=api_releases())
        d = ds_update.check_for_update("0.98.4")
        self.assertFalse(d["update_available"])
        self.assertTrue(d["error"], "线上有 0.99.1,却安静地说已是最新")
        self.assertIn("0.99.1", d["error"])
        self.assertIn("新版缺少可核对的安装包信息", d["error"])

    def test_rl6b_unreadable_local_version_asks_nobody(self):
        """评审(整份 GLM / Kimi):本机版本号读不出时原来会先白拉清单,错误里同一句还按两个来源重复两遍。"""
        src = _Sources(self, atom=atom_text(["0.99.1", "0.98.4", "0.98.3"]),
                       manifests={"win-installer-0.99.1": manifest()}, api=api_releases())
        d = ds_update.check_for_update("not-a-version")
        self.assertEqual(src.calls, [], "读不出本机版本号,还去联网")
        self.assertFalse(d["update_available"])
        self.assertEqual(d["error"].count("读不出本机版本号"), 1, d["error"])

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


class HumanReasonsMore(unittest.TestCase):
    def test_rl7d_rate_limit_seen_only_in_headers_is_still_rate_limit(self):
        """评审(整份 + 切片 DeepSeek):GitHub 有时 403 的状态行是 Forbidden,限流只写在 X-RateLimit-Remaining: 0 里。"""
        exc = urllib.error.HTTPError(ds_update.releases_url(REPO), 403, "Forbidden",
                                     {"X-RateLimit-Remaining": "0"}, None)
        d = ds_update.check_for_update("0.98.4", fetch=lambda: (_ for _ in ()).throw(exc))
        self.assertIn("限制了这个网络出口的查询次数", d["error"])

    def test_rl7d_plain_forbidden_is_not_called_rate_limit(self):
        exc = urllib.error.HTTPError(ds_update.releases_url(REPO), 403, "Forbidden", {}, None)
        d = ds_update.check_for_update("0.98.4", fetch=lambda: (_ for _ in ()).throw(exc))
        self.assertIn("GitHub 拒绝了这次请求", d["error"])
        self.assertNotIn("查询次数", d["error"])

    def test_rl7d_broken_http_from_a_middlebox_is_explained(self):
        """评审(整份 + 切片 DeepSeek):代理 / 门户回的不是 HTTP ⇒ http.client.HTTPException(不是 OSError)原来落进"出了意外"。"""
        import http.client
        for exc in (http.client.BadStatusLine("garbage"), http.client.IncompleteRead(b"x", 10)):
            with self.subTest(exc=type(exc).__name__):
                d = ds_update.check_for_update("0.98.4", fetch=lambda e=exc: (_ for _ in ()).throw(e))
                self.assertIn("返回的内容看不懂", d["error"])

    def test_rl7e_bad_manifest_is_said_in_plain_words(self):
        """评审(整份 Kimi / GLM):清单不符时原来直接甩「清单里的 sha256 形状不对」,业主看不懂;design 承诺的是这句人话。"""
        _Sources(self, atom=atom_text(["0.99.1", "0.98.4", "0.98.3"]),
                 manifests={"win-installer-0.99.1": manifest(sha256="zz" * 32)}, api=rate_limited())
        d = ds_update.check_for_update("0.98.4")
        self.assertIn("新版缺少可核对的安装包信息", d["error"])
        self.assertIn("sha256", d["error"], "技术细节要留在括号里")


class HumanReasonsForGarbage(unittest.TestCase):
    def test_rl7c_garbage_body_is_explained_not_dumped(self):
        """自审(09-15 夜):`fetch_releases` 里 json.loads 失败抛的是 JSONDecodeError(ValueError 子类),
        原样当人话 ⇒ 业主看到「Expecting value: line 1 column 1 (char 0)」。代理 / 门户把 API 换成一张网页时就是这句。"""
        cases = (json.JSONDecodeError("Expecting value", "<html>", 0),
                 UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"))
        for exc in cases:
            with self.subTest(exc=type(exc).__name__):
                d = ds_update.check_for_update("0.98.4", fetch=lambda e=exc: (_ for _ in ()).throw(e))
                self.assertIn("返回的内容看不懂", d["error"])
                self.assertNotRegex(d["error"].split("(")[0], r"Expecting value|invalid start byte",
                                    "技术细节跑到了人话那半句里")


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


class SecondRoundReviewFindings(unittest.TestCase):
    """第 2 轮评审(增量)成立的几条低,判据先行。前缀仍是 rl。"""

    def test_rl3e_a_sha256_with_a_trailing_newline_is_refused(self):
        """整份 DeepSeek #1:`\Z` 那一刀只修了一半 —— `_HEX64_RE` 还用 `$`,
        于是 `"ab…ab\n"` 被清单核对**接受**,`digest` 原样回成 `sha256:<64hex>\n`。
        今天不炸只是因为下游 `ds_update_apply.parse_digest` 顺手 `.strip()` 了 ——
        谁把那个 strip 拿掉、或拿 digest 去逐字节比 / 写进文件名,就静默放过一份坏清单。"""
        with self.assertRaises(ValueError, msg="sha256 末尾带换行,清单核对却收下了"):
            ds_update.parse_manifest(manifest(sha256=HEX + "\n"), "win-installer-0.99.1", REPO)
        self.assertIsNone(ds_update._HEX64_RE.match(HEX + "\n"), "_HEX64_RE 的 $ 放过了末尾换行")

    def test_rl7f_weird_headers_do_not_make_explain_throw(self):
        """整份 DeepSeek #2 + Kimi #2(两家独立命中同一处):`exc.headers` 非 None 又没有 `.get` 时
        `explain` 自己抛 AttributeError,而它是在 except 分支里被调用的 ⇒ 异常穿出 `check_for_update`,
        违反它自己「任何异常都不许漏出去」的承诺(界面会落到泛化的「软件后台没响应」)。"""
        class Weird:
            pass

        for hdrs in (0, "X-RateLimit-Remaining: 0", Weird(), [("X-RateLimit-Remaining", "0")]):
            with self.subTest(hdrs=type(hdrs).__name__):
                exc = urllib.error.HTTPError(ds_update.releases_url(REPO), 403, "Forbidden", hdrs, None)
                d = ds_update.check_for_update("0.98.4", fetch=lambda e=exc: (_ for _ in ()).throw(e))
                self.assertFalse(d["update_available"])
                self.assertTrue(d["error"], d)
                self.assertIn("403", d["error"])

    def test_rl5e_cannot_reach_the_manifest_is_not_said_as_a_bad_release(self):
        """整份 DeepSeek #5:清单只是**拉不到**(超时 / 断网)时也照说「新版缺少可核对的安装包信息」——
        前半句是对这一版发布质量的断言,和括号里的网络原因打架,人会先去怀疑发版而不是网络。
        清单 404(=这一版真没传清单)仍然该说发布质量那句 —— 见 rl5d / rl7e,两句不许合并。"""
        for exc in (urllib.error.URLError("timed out"), socket.timeout("timed out"), ConnectionResetError()):
            with self.subTest(exc=type(exc).__name__):
                _Sources(self, atom=atom_text(["0.99.1", "0.98.4", "0.98.3"]),
                         manifests={"win-installer-0.99.1": exc}, api=rate_limited())
                d = ds_update.check_for_update("0.98.4")
                self.assertTrue(d["error"])
                self.assertIn("0.99.1", d["error"])
                self.assertIn("连不上 GitHub", d["error"])
                self.assertNotIn("新版缺少可核对的安装包信息", d["error"],
                                 "只是拉不到,却说成这一版发布质量有问题")

    def test_rl5e_garbled_http_while_fetching_the_manifest_is_not_said_as_a_bad_release(self):
        """我自审补的(第 3 轮派发之前):`http.client.HTTPException`(BadStatusLine / IncompleteRead ——
        代理或门户把清单换成一堆垃圾)**不是** OSError 子类 ⇒ 落进"发布质量"那句。
        和 DeepSeek 那条(超时/断网)是同一个毛病:我只修了一半。中间盒弄坏的东西不许指着发版说。"""
        import http.client
        for exc in (http.client.BadStatusLine("garbage"), http.client.IncompleteRead(b"x", 10)):
            with self.subTest(exc=type(exc).__name__):
                _Sources(self, atom=atom_text(["0.99.1", "0.98.4", "0.98.3"]),
                         manifests={"win-installer-0.99.1": exc}, api=rate_limited())
                d = ds_update.check_for_update("0.98.4")
                self.assertTrue(d["error"])
                self.assertIn("0.99.1", d["error"])
                self.assertIn("返回的内容看不懂", d["error"])
                self.assertNotIn("新版缺少可核对的安装包信息", d["error"],
                                 "中间盒把清单换成了垃圾,却说成这一版发布质量有问题")

    def test_rl5e_the_version_in_the_reason_is_the_tag_as_published(self):
        """Kimi #1:原因里的版本号用了补零后的三段值 ⇒ 真 tag `win-installer-1.0` 会被写成「有新版 1.0.0」,
        而 1.0 正是留给业主拍板的那个号(记忆 opendesign-version-scheme)。发版人照原因去发布页找 1.0.0 找不到。"""
        _Sources(self, atom=atom_text(["1.0", "0.98.4", "0.98.3"]), manifests={}, api=rate_limited())
        d = ds_update.check_for_update("0.98.4")
        self.assertIn("有新版 1.0,", d["error"], d["error"])
        self.assertNotIn("1.0.0", d["error"], "原因里的版本号不是 tag 原文")


class BlameIsDecidedInOnePlace(unittest.TestCase):
    """判据 rl5g —— 三轮评审每轮都照出"另一半没修":
    DeepSeek 照出超时 / 断网、我自审照出 `http.client.HTTPException`、Kimi 照出 `UnicodeDecodeError`。
    病根不是漏了哪一条,是"该怪谁"有**两份平行的类型清单**(`explain` 一份、`check_for_update` 一份),
    它们注定各自漂移。所以这条判据**不数类型**:凡是 `explain` 自己已经判成"路上的问题"的失败,
    原因前半句就不许说成这一版发布质量有问题 —— 以后新增一种失败也照样被这条罩住。"""

    TRANSPORT_WORDS = ("连不上 GitHub", "返回的内容看不懂",
                       "限制了这个网络出口的查询次数", "GitHub 拒绝了这次请求")

    def _reason_for(self, exc):
        _Sources(self, atom=atom_text(["0.99.1", "0.98.4", "0.98.3"]),
                 manifests={"win-installer-0.99.1": exc}, api=rate_limited())
        return ds_update.check_for_update("0.98.4")["error"]

    def test_rl5g_transport_failures_never_blame_the_release(self):
        url = ds_update.manifest_url(REPO, "win-installer-0.99.1")
        cases = [
            urllib.error.URLError("timed out"),
            socket.timeout("timed out"),
            ConnectionResetError(),
            ssl.SSLError("handshake failed"),
            http.client.BadStatusLine("garbage"),
            http.client.IncompleteRead(b"x", 10),
            UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
            json.JSONDecodeError("Expecting value", "<html>", 0),
            urllib.error.HTTPError(url, 403, "rate limit exceeded", {}, None),
            urllib.error.HTTPError(url, 403, "Forbidden", {}, None),
            urllib.error.HTTPError(url, 500, "Internal Server Error", {}, None),
            urllib.error.HTTPError(url, 404, "Not Found", {}, None),
        ]
        for exc in cases:
            with self.subTest(exc=type(exc).__name__, arg=str(exc)[:24]):
                detail = ds_update.explain(exc)
                on_the_way = any(w in detail for w in self.TRANSPORT_WORDS)
                error = self._reason_for(exc)
                self.assertIn("0.99.1", error)
                if on_the_way:
                    self.assertIn(ds_update.UNREACHABLE_HUMAN, error,
                                  "explain 判成路上的问题(%s),原因却说成发布质量:%s" % (detail, error))
                    self.assertNotIn(ds_update.UNVERIFIED_HUMAN, error, error)
                else:
                    self.assertIn(ds_update.UNVERIFIED_HUMAN, error,
                                  "explain 没判成路上的问题(%s),原因却说拿不到:%s" % (detail, error))

    def test_rl5g_a_bad_manifest_still_blames_the_release(self):
        """反面:清单**拿到了**、但它自己不对 ⇒ 仍然是这一版发布的问题(rl7e 同口径,别被上面那条带跑)。"""
        _Sources(self, atom=atom_text(["0.99.1", "0.98.4", "0.98.3"]),
                 manifests={"win-installer-0.99.1": manifest(sha256="zz" * 32)}, api=rate_limited())
        error = ds_update.check_for_update("0.98.4")["error"]
        self.assertIn(ds_update.UNVERIFIED_HUMAN, error)
        self.assertNotIn(ds_update.UNREACHABLE_HUMAN, error)

    def test_rl5g_blame_and_explain_come_from_one_place(self):
        """结构条:`explain` 与 `blame` 必须同出一处 —— 各自一份 isinstance 清单就是本条要防的形状。"""
        import inspect
        src = inspect.getsource(ds_update)
        self.assertEqual(src.count("def _human_and_blame("), 1)
        for fn in ("def explain(", "def blame("):
            body = src.split(fn, 1)[1].split("\ndef ", 1)[0]
            self.assertIn("_human_and_blame(", body, "%s 没走那个唯一的分类器" % fn)
            self.assertNotIn("isinstance(", body, "%s 又自己长出一份类型清单" % fn)


if __name__ == "__main__":
    unittest.main(verbosity=2)
