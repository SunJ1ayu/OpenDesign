"""Windows 更新端到端(e1~e7)的**本机能判的那一半**(track opendesign-in-app-update-install §3)。

CI 那一趟要 ~40 分钟,而且它红了分不清"产品坏了"还是"考卷搭错了"。
所以考卷自己能在本机判的,全部在这里先判掉:

- `H1` 替身给的 releases JSON,**真的产品代码认不认**(直接喂 `ds_update.decide`)
- `H2` 软件会碰的主机,hosts 重定向**全都盖住了**(拿真的 `releases_url()` 和替身给的下载地址核)
- `H3` 替身证书链按 `api.github.com` / `github.com` **真握手**(显式开 VERIFY_X509_STRICT);
       不信那张 CA 时必须握不上(证明信任确实来自它)
- `H4` 替身真发得出安装包;corrupt 模式只翻一个字节(大小不变、sha 变)
- `H5` 目录清单只排 `__pycache__`,别的差异一律看得见
- `H6` 查更新的两条来源(track opendesign-update-check-rate-limit,判据 rl12):
       `feed` 模式(默认)订阅源 + 清单照真 GitHub 的样子给、**API 回 403 限流**(业主 09-15 夜实测的那句);
       `api` 模式订阅源坏、API 好。清单带 `Accept: application/json` 回 404(真 GitHub 就这样,rl8e)。
- `H7` 脚本 / 工作流:默认 feed、e8 切 api 且一定切回、e8 在 e6/e7 之前、两道收据闸都点名 e8
- `V*` 判定器:每个场景一份"该过"的事实 ⇒ OK;逐项改坏 ⇒ FAIL;缺字段 ⇒ FAIL;CLI 退出码契约

⚠️ 这里一律只连 127.0.0.1(判据不许有外网出口,2026-08-10 那次事故立的规矩)。
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, ".github", "scripts")
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, SCRIPTS)

import ds_update  # noqa: E402
import ds_update_apply  # noqa: E402
import fake_github  # noqa: E402
import update_e2e_verdict as V  # noqa: E402

OLD, NEW = "0.98.4", "0.98.900"
PS1 = os.path.join(SCRIPTS, "windows-update-e2e.ps1")
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "windows-update-e2e.yml")


def _write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _setup_file(tmp, size=4096):
    path = os.path.join(tmp, "OpenDesign-Setup-%s.exe" % NEW)
    with open(path, "wb") as fh:
        fh.write(b"MZ" + os.urandom(size - 2))
    return path


class H1StandInIsWhatTheProductAccepts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.setup = _setup_file(self.tmp)
        self.rels = fake_github.releases_json(ds_update.REPO, NEW, self.setup)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_h1a_decide_offers_the_stand_in_release(self):
        d = ds_update.decide(OLD, self.rels)
        self.assertIsNone(d["error"])
        self.assertTrue(d["update_available"])
        self.assertEqual(d["latest"], NEW)

    def test_h1b_digest_is_what_apply_update_will_verify_against(self):
        d = ds_update.decide(OLD, self.rels)
        with open(self.setup, "rb") as fh:
            want = hashlib.sha256(fh.read()).hexdigest()
        self.assertEqual(ds_update_apply.parse_digest(d["asset"]["digest"]), want)

    def test_h1c_download_url_path_is_the_one_the_stand_in_serves(self):
        d = ds_update.decide(OLD, self.rels)
        self.assertEqual(urlsplit(d["asset"]["url"]).path, fake_github.download_path(ds_update.REPO, NEW))

    def test_h1d_the_ci_new_version_is_newer_than_the_repo_version(self):
        # workflow 里写死的新版号必须严格大于仓里的 VERSION,否则 e1~e5 全部"没有新版"。
        with open(WORKFLOW, encoding="utf-8") as fh:
            m = re.search(r'^\s*NEW="([0-9.]+)"', fh.read(), re.M)
        self.assertIsNotNone(m, "workflow 里找不到 NEW=")
        import ds_web  # noqa: E402  (只读 VERSION)
        self.assertGreater(ds_update.parse_version(m.group(1)), ds_update.parse_version(ds_web.VERSION))


class H2HostsCoverEveryHostTheProductTouches(unittest.TestCase):
    def test_h2_both_hosts_are_redirected_in_the_ps1(self):
        tmp = tempfile.mkdtemp()
        try:
            d = ds_update.decide(OLD, fake_github.releases_json(ds_update.REPO, NEW, _setup_file(tmp)))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        touched = {urlsplit(ds_update.releases_url()).hostname, urlsplit(d["asset"]["url"]).hostname,
                   urlsplit(ds_update.atom_url()).hostname,
                   urlsplit(ds_update.manifest_url(ds_update.REPO, "win-installer-%s" % NEW)).hostname}
        with open(PS1, encoding="utf-8") as fh:
            m = re.search(r"^\$RedirectHosts\s*=\s*@\(([^)]*)\)", fh.read(), re.M)
        self.assertIsNotNone(m, "ps1 里找不到 $RedirectHosts")
        redirected = set(re.findall(r"'([^']+)'", m.group(1)))
        self.assertEqual(touched - redirected, set(), "有主机没被 hosts 盖住,软件会去打真网")


class _Served(unittest.TestCase):
    """用 make-e2e-certs.sh 造证书,本机起替身(和 CI 同一份 make_handler)。"""

    @classmethod
    def setUpClass(cls):
        if not shutil.which("openssl"):
            raise unittest.SkipTest("本机没有 openssl")
        cls.tmp = tempfile.mkdtemp()
        cls.certs = os.path.join(cls.tmp, "certs")
        subprocess.run(["bash", os.path.join(SCRIPTS, "make-e2e-certs.sh"), cls.certs],
                       check=True, capture_output=True)
        cls.setup = _setup_file(cls.tmp, size=65536)
        cls.mode = os.path.join(cls.tmp, "mode.txt")
        cls.source = os.path.join(cls.tmp, "source.txt")
        cls.log = os.path.join(cls.tmp, "fake.log")
        with open(cls.mode, "w") as fh:
            fh.write("normal")
        with open(cls.source, "w") as fh:
            fh.write("feed")
        handler = fake_github.make_handler(ds_update.REPO, NEW, cls.setup, cls.mode, cls.log,
                                           source_file=cls.source)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(os.path.join(cls.certs, "server.crt"), os.path.join(cls.certs, "server.key"))
        cls.httpd.socket = ctx.wrap_socket(cls.httpd.socket, server_side=True)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _get(self, host, path, cafile, accept=None):
        ctx = ssl.create_default_context(cafile=cafile) if cafile else ssl.create_default_context()
        ctx.verify_flags |= ssl.VERIFY_X509_STRICT
        raw = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        extra = ("Accept: %s\r\n" % accept) if accept else ""
        with ctx.wrap_socket(raw, server_hostname=host) as s:
            s.sendall(("GET %s HTTP/1.1\r\nHost: %s\r\n%sConnection: close\r\n\r\n"
                       % (path, host, extra)).encode())
            data = b""
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                data += chunk
        head, _, body = data.partition(b"\r\n\r\n")
        return head.decode("latin-1"), body


class H3TlsHandshakeWithTheThrowawayCa(_Served):
    def _source(self, value):
        with open(self.source, "w") as fh:
            fh.write(value)
        self.addCleanup(_write, self.source, "feed")

    def test_h3a_api_github_com_verifies_strictly(self):
        self._source("api")   # feed 模式下 API 故意回 403;这条问的是证书,在 api 模式下问
        head, body = self._get("api.github.com", "/repos/%s/releases?per_page=100" % ds_update.REPO,
                               os.path.join(self.certs, "ca.crt"))
        self.assertIn(" 200 ", head.splitlines()[0])
        self.assertEqual(json.loads(body)[0]["tag_name"], "win-installer-%s" % NEW)

    def test_h3b_github_com_verifies_strictly(self):
        head, _ = self._get("github.com", fake_github.download_path(ds_update.REPO, NEW),
                            os.path.join(self.certs, "ca.crt"))
        self.assertIn(" 200 ", head.splitlines()[0])

    def test_h3c_without_the_ca_the_handshake_is_refused(self):
        with self.assertRaises(ssl.SSLCertVerificationError):
            self._get("api.github.com", "/", None)

    def test_h3d_ca_private_key_is_not_left_behind(self):
        self.assertEqual(sorted(os.listdir(self.certs)), ["ca.crt", "server.crt", "server.key"])


class H4DownloadModes(_Served):
    def _download(self):
        return self._get("github.com", fake_github.download_path(ds_update.REPO, NEW),
                         os.path.join(self.certs, "ca.crt"))[1]

    def test_h4a_normal_serves_the_exact_bytes(self):
        with open(self.mode, "w") as fh:
            fh.write("normal")
        with open(self.setup, "rb") as fh:
            self.assertEqual(self._download(), fh.read())

    def test_h4b_corrupt_flips_one_byte_same_size(self):
        with open(self.mode, "w") as fh:
            fh.write("corrupt")
        try:
            got = self._download()
        finally:
            with open(self.mode, "w") as fh:
                fh.write("normal")
        with open(self.setup, "rb") as fh:
            want = fh.read()
        self.assertEqual(len(got), len(want))
        self.assertEqual(sum(1 for a, b in zip(got, want) if a != b), 1)
        with open(self.log, encoding="utf-8") as fh:
            kinds = [json.loads(line) for line in fh]
        self.assertTrue(any(e["kind"] == "download" and e["mode"] == "corrupt" for e in kinds))


class H6FeedAndApiSources(_Served):
    """rl12 —— 替身的两种来源模式。形状一律拿真的 ds_update 解析函数核:替身给的东西产品不认,CI 那一趟就白跑。"""

    CA = None

    def setUp(self):
        self.ca = os.path.join(self.certs, "ca.crt")

    def _set_source(self, value):
        with open(self.source, "w") as fh:
            fh.write(value)
        self.addCleanup(_write, self.source, "feed")

    def _status(self, head):
        return int(head.splitlines()[0].split()[1])

    def test_h6a_feed_mode_serves_feed_and_manifest_the_product_accepts(self):
        tag = "win-installer-%s" % NEW
        head, body = self._get("github.com", fake_github.atom_path(ds_update.REPO), self.ca)
        self.assertEqual(self._status(head), 200)
        entries = ds_update.parse_atom(body.decode("utf-8"))
        tags = [e["tag"] for e in entries]
        self.assertIn(tag, tags)
        self.assertGreaterEqual(len(tags), 3, "替身订阅源只有一条 entry ⇒ e2e 照不出「取第一条而不是取最大」的回归")
        self.assertNotEqual(tags[0], tag, "最新那条排在第一个 ⇒ 取第一条的回归照样绿")
        best = max(entries, key=lambda e: ds_update.parse_version(e["tag"]))
        self.assertEqual(best["tag"], tag)
        head, body = self._get("github.com", fake_github.update_manifest_path(ds_update.REPO, NEW), self.ca,
                               accept="application/octet-stream")
        self.assertEqual(self._status(head), 200)
        asset = ds_update.parse_manifest(body.decode("utf-8"), tag)
        self.assertEqual(urlsplit(asset["browser_download_url"]).path, fake_github.download_path(ds_update.REPO, NEW))
        with open(self.setup, "rb") as fh:
            self.assertEqual(asset["digest"], "sha256:" + hashlib.sha256(fh.read()).hexdigest())

    def test_h6b_feed_mode_manifest_with_json_accept_is_404_like_real_github(self):
        head, _ = self._get("github.com", fake_github.update_manifest_path(ds_update.REPO, NEW), self.ca,
                            accept="application/json")
        self.assertEqual(self._status(head), 404, "真 GitHub 的下载地址对 JSON Accept 回 404,替身要照样(rl8e)")

    def test_h6c_feed_mode_api_is_rate_limited(self):
        head, body = self._get("api.github.com", "/repos/%s/releases?per_page=100" % ds_update.REPO, self.ca)
        self.assertEqual(self._status(head), 403)
        self.assertIn("rate limit exceeded", head.splitlines()[0].lower() + body.decode("utf-8").lower())

    def test_h6d_api_mode_feed_broken_api_works(self):
        self._set_source("api")
        head, _ = self._get("github.com", fake_github.atom_path(ds_update.REPO), self.ca)
        self.assertGreaterEqual(self._status(head), 500)
        head, body = self._get("api.github.com", "/repos/%s/releases?per_page=100" % ds_update.REPO, self.ca)
        self.assertEqual(self._status(head), 200)
        self.assertTrue(ds_update.decide(OLD, json.loads(body))["update_available"])

    def test_h6e_log_says_which_source_was_asked(self):
        self._get("github.com", fake_github.atom_path(ds_update.REPO), self.ca)
        with open(self.log, encoding="utf-8") as fh:
            entries = [json.loads(line) for line in fh]
        atoms = [e for e in entries if e.get("kind") == "atom"]
        self.assertTrue(atoms, "替身没把订阅源请求记成 kind=atom")
        self.assertIn("status", atoms[-1])


class H7ScriptRunsBothSources(unittest.TestCase):
    """rl12 —— 脚本默认 feed(全部既有场景走新路)、e8 切 api(备路)且一定切回、两道收据闸都点名 e8。"""

    @classmethod
    def setUpClass(cls):
        with open(PS1, encoding="utf-8") as fh:
            cls.ps1 = fh.read()
        with open(WORKFLOW, encoding="utf-8") as fh:
            cls.wf = fh.read()

    def test_h7a_e8_is_expected_before_the_spaced_dir_scenarios(self):
        m = re.search(r"^\$Expected\s*=\s*@\(([^)]*)\)", self.ps1, re.M)
        names = re.findall(r"'(e\d+)'", m.group(1))
        self.assertIn("e8", names)
        self.assertLess(names.index("e8"), names.index("e6"), "e8 要在搬去带空格目录(e6/e7)之前跑")

    def test_h7b_fake_is_started_with_a_source_file_defaulting_to_feed(self):
        self.assertRegex(self.ps1, r"--source-file")
        loop = self.ps1.index("foreach ($s in $Expected)")
        feed = [m.start() for m in re.finditer(r"Set-Content -LiteralPath \$SourceFile -Value 'feed'", self.ps1)]
        self.assertTrue(feed and feed[0] < loop, "跑场景之前没把来源设成 feed")

    def test_h7c_e8_switches_to_api_and_always_switches_back(self):
        m = re.search(r"^function Run-e8 \{(.*?)^\}", self.ps1, re.M | re.S)
        self.assertIsNotNone(m, "没有 Run-e8")
        body = m.group(1)
        self.assertIn("Set-Content -LiteralPath $SourceFile -Value 'api'", body)
        fin = re.search(r"\bfinally\s*\{([^{}]*)\}", body)
        self.assertIsNotNone(fin, "e8 没有 finally 块")
        self.assertIn("Set-Content -LiteralPath $SourceFile -Value 'feed'", fin.group(1),
                      "e8 切回 feed 不在 finally 块里 —— 中途炸了会把后面的场景留在 api 模式")

    def test_h7d_facts_record_the_source(self):
        m = re.search(r"^function New-Facts \{(.*?)^\}", self.ps1, re.M | re.S)
        self.assertRegex(m.group(1), r"\$f\.source\s*=")

    def test_h7e_workflow_receipt_gate_names_e8(self):
        m = re.search(r"foreach \(\$k in ([^)]*)\)", self.wf)
        self.assertIn("'e8'", m.group(1))


class H5ManifestSkipsOnlyPycache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        for rel in ("ds/bin/ds_web.py", "ds/bin/__pycache__/ds_web.cpython-312.pyc",
                    "ds/bin/__pycache__x/keep.txt", "python/pythonw.exe"):
            p = os.path.join(self.tmp, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as fh:
                fh.write(rel)
        self.base = fake_github.manifest_digest(fake_github.manifest(self.tmp))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _touch(self, rel, text="changed"):
        p = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write(text)
        return fake_github.manifest_digest(fake_github.manifest(self.tmp))

    def test_h5a_pycache_changes_are_invisible(self):
        self.assertEqual(self._touch("ds/bin/__pycache__/ds_web.cpython-312.pyc"), self.base)
        self.assertEqual(self._touch("ds/bin/__pycache__/new.pyc"), self.base)

    def test_h5b_a_source_change_is_visible(self):
        self.assertNotEqual(self._touch("ds/bin/ds_web.py"), self.base)

    def test_h5c_lookalike_dir_is_not_skipped(self):
        self.assertNotEqual(self._touch("ds/bin/__pycache__x/keep.txt"), self.base)

    def test_h5d_a_new_file_is_visible(self):
        self.assertNotEqual(self._touch("OpenDesign.old/ds/x.py"), self.base)


# ---------------------------------------------------------------- 判定器

MARKERS = {"Data/客户资料-e2e.bin": "a" * 64, "UserData/项目备忘-e2e.md": "b" * 64}
LIVE = r"C:\Users\runneradmin\AppData\Local\Programs\OpenDesign"
POINTERS = {
    "live": LIVE,
    "install_dir": LIVE,
    "uninstall": {"InstallLocation": LIVE, "UninstallString": '"%s\\卸载.exe"' % LIVE,
                  "DisplayIcon": LIVE + "\\OpenDesign.exe", "DisplayVersion": OLD},
    "autorun": None,
    "shortcuts": {r"C:\Users\runneradmin\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\OpenDesign\OpenDesign.lnk":
                  LIVE + "\\OpenDesign.exe",
                  r"C:\Users\runneradmin\Desktop\OpenDesign.lnk": LIVE.upper() + "\\OpenDesign.exe"},
}
SPACED_LIVE = r"C:\OD e2e space\Programs\OpenDesign"


def _pointers_at(live):
    """同一套指向,换成另一个活树路径(e6/e7 装在带空格的目录)。"""
    text = json.dumps(POINTERS, ensure_ascii=False).replace(json.dumps(LIVE)[1:-1], json.dumps(live)[1:-1])
    text = text.replace(json.dumps(LIVE.upper())[1:-1], json.dumps(live.upper())[1:-1])
    return json.loads(text)


REAL_WINDOW = {"wins": [{"title": "OpenDesign", "cls": "WindowsForms10.Window.8.app.0.141b42a_r6_ad1",
                         "proc": "pythonw"}], "procs": ["pythonw:「OpenDesign」"]}


def _base(kind):
    source = "api" if kind == "e8" else "feed"
    asked = ([{"kind": "atom", "status": 503}, {"kind": "releases", "status": 200}] if source == "api"
             else [{"kind": "atom", "status": 200}, {"kind": "manifest", "status": 200}])
    f = {
        "old_version": OLD, "new_version": NEW, "source": source,
        "reset": {"installer_rc": 0, "health": {"port": 8766, "version": OLD}},
        "check": {"update_available": True, "latest": NEW, "error": None},
        "fake_log": asked + [{"kind": "download", "mode": "corrupt" if kind == "e2" else "normal"}],
        "markers_before": copy.deepcopy(MARKERS), "markers_after": copy.deepcopy(MARKERS),
        "pointers": copy.deepcopy(POINTERS),
    }
    started = {"ok": True, "stage": "started", "error": None}
    relay = {"seen": True, "ended": True, "seconds": 42.0, "old_seen": True}
    if kind == "e2":
        f.update(apply={"ok": False, "stage": "verify", "error": "sha256"}, live_before="d1", live_after="d1",
                 new_exists=False, old_exists=False, health_after={"port": 8766, "version": OLD})
    elif kind == "e3":
        f.update(inject={"landed": True, "detail": "x"}, apply=started, relay=relay, live_before="d1",
                 live_after="d1", new_exists=False, old_exists=False, health_after=None,
                 relaunch={"health": {"port": 8766, "version": OLD}})
    elif kind in ("e4", "e5"):
        f.update(inject={"landed": True, "detail": "x"}, apply=started, relay=relay, live_before="d1",
                 live_after="d1", live_version_after=OLD, new_exists=True, old_exists=False,
                 nested_old_exists=False, health_after={"port": 8766, "version": OLD})
        if kind == "e5":
            f["inject"]["version"] = "0.0.1"
            f["seen_versions"] = ["0.0.1", OLD]
    elif kind in ("e1", "e6", "e8"):
        f.update(apply=started, relay=relay, health_after={"port": 8766, "version": NEW},
                 live_version_after=NEW, old_exists=False, new_exists=False, window=copy.deepcopy(REAL_WINDOW),
                 health_final={"port": 8766, "version": NEW})
        if kind == "e6":
            f["pointers"] = _pointers_at(SPACED_LIVE)
    elif kind == "e7":
        # e7 不走替身、不点更新:直接把修 t33 之前那条参数交给新版安装器
        for k in ("new_version", "check", "fake_log", "source"):
            del f[k]
        f.update(pointers=_pointers_at(SPACED_LIVE),
                 cmdline='/S /UPDATE "/D=%s.new"' % SPACED_LIVE, installer_rc=3,
                 live_before="d1", live_after="d1", new_exists=False,
                 health_after={"port": 8766, "version": OLD})
    return f


def _set(path, value):
    def mutate(f):
        node = f
        keys = path.split(".")
        for k in keys[:-1]:
            node = node[k]
        node[keys[-1]] = value
    return mutate


def _drop(key):
    def mutate(f):
        del f[key]
    return mutate


COMMON_BREAKS = {
    "installer failed": _set("reset.installer_rc", 1),
    "old app never answered": _set("reset.health", None),
    "app did not see stand-in": _set("check.update_available", False),
    "stand-in never asked": _set("fake_log", []),
    "archive marker changed": _set("markers_after", {"Data/客户资料-e2e.bin": "c" * 64}),
    "no markers seeded": _set("markers_before", {}),
    "markers fact missing": _drop("markers_after"),
    "InstallDir points at .new": _set("pointers.install_dir", LIVE + ".new"),
    "uninstall entry points at .new": _set("pointers.uninstall.UninstallString", '"%s.new\\卸载.exe"' % LIVE),
    "desktop shortcut points at .new": _set(
        "pointers.shortcuts", {r"C:\Users\runneradmin\Desktop\OpenDesign.lnk": LIVE + ".new\\OpenDesign.exe"}),
    "shortcut points at .old": _set(
        "pointers.shortcuts", {r"C:\x\OpenDesign.lnk": LIVE + ".old\\OpenDesign.exe"}),
    "no shortcuts at all": _set("pointers.shortcuts", {}),
    "shortcut target unreadable": _set(
        "pointers.shortcuts", {r"C:\\x\\OpenDesign.lnk": "", r"C:\\x\\y.lnk": "unreadable: COMException"}),
    "pointers fact missing": _drop("pointers"),
}

BREAKS = {
    "e2": {
        "update accepted": _set("apply", {"ok": True, "stage": "started"}),
        "refused at wrong stage": _set("apply.stage", "download"),
        "download not corrupted": _set("fake_log", [{"kind": "atom", "status": 200}, {"kind": "manifest", "status": 200},
                                                    {"kind": "download", "mode": "normal"}]),
        "live tree changed": _set("live_after", "d2"),
        "live digest missing": _set("live_before", None),
        ".new left": _set("new_exists", True),
        ".old exists": _set("old_exists", True),
        "old app gone": _set("health_after", None),
    },
    "e3": {
        "inject missed": _set("inject.landed", False),
        "apply not started": _set("apply.ok", False),
        "relay never seen": _set("relay.seen", False),
        "relay still running": _set("relay.ended", False),
        "renamed anyway": _set("live_after", "d2"),
        ".new not deleted": _set("new_exists", True),
        ".old exists": _set("old_exists", True),
        "old does not relaunch": _set("relaunch.health", {"port": 8766, "version": NEW}),
        "relaunch fact missing": _drop("relaunch"),
    },
    "e4": {
        "gave up before renaming (looks like rollback)": _set("relay.old_seen", False),
        "old_seen fact missing": _set("relay", {"seen": True, "ended": True, "seconds": 42.0}),
        "inject missed": _set("inject.landed", False),
        "apply not started": _set("apply.stage", "shell"),
        "relay still running": _set("relay.ended", False),
        "live tree not restored": _set("live_after", "d2"),
        "live version new": _set("live_version_after", NEW),
        ".old left": _set("old_exists", True),
        "old nested in new": _set("nested_old_exists", True),
        "nobody relaunched old": _set("health_after", None),
        "new answering": _set("health_after", {"port": 8766, "version": NEW}),
    },
    "e5": {
        "gave up before renaming (looks like rollback)": _set("relay.old_seen", False),
        "inject missed": _set("inject.landed", False),
        "bad new never ran": _set("seen_versions", [OLD]),
        "live version new": _set("live_version_after", NEW),
        "old nested in new": _set("nested_old_exists", True),
        "bad new still answering": _set("health_after", {"port": 8766, "version": "0.0.1"}),
        "live tree not restored": _set("live_after", "d2"),
        ".old left": _set("old_exists", True),
    },
    "e6": {
        "install path has no space (scenario untested)": _set("pointers", copy.deepcopy(POINTERS)),
        "apply not started (quoted /D= fell back to live)": _set("apply", {"ok": False, "stage": "install", "error": "rc=3"}),
        "old still answering": _set("health_after", {"port": 8766, "version": OLD}),
        "health new but tree old": _set("live_version_after", OLD),
        "new version gone by the end": _set("health_final", None),
        "no window at all": _set("window", {"wins": [], "procs": []}),
        ".new left": _set("new_exists", True),
    },
    "e7": {
        "not the quoted form (scenario untested)": _set("cmdline", '/S /UPDATE /D=%s.new' % SPACED_LIVE),
        "no /UPDATE (scenario untested)": _set("cmdline", '/S "/D=%s.new"' % SPACED_LIVE),
        "quoted but no space (scenario untested)": _set("cmdline", '/S /UPDATE "/D=C:\\x\\OpenDesign.new"'),
        "install path has no space (scenario untested)": _set("pointers", copy.deepcopy(POINTERS)),
        "installer accepted it": _set("installer_rc", 0),
        "installer failed some other way": _set("installer_rc", 2),
        "installer hung": _set("installer_rc", "timeout"),
        "live tree overwritten": _set("live_after", "d2"),
        ".new created": _set("new_exists", True),
        "old app gone": _set("health_after", None),
    },
    "e1": {
        "new version gone by the end": _set("health_final", None),
        "old answering at the end": _set("health_final", {"port": 8766, "version": OLD}),
        "apply not started": _set("apply", {"ok": False, "stage": "install", "error": "rc=2"}),
        "relay never ended": _set("relay.ended", False),
        "old still answering": _set("health_after", {"port": 8766, "version": OLD}),
        "nobody answering": _set("health_after", None),
        "health new but tree old": _set("live_version_after", OLD),
        ".old left": _set("old_exists", True),
        ".new left": _set("new_exists", True),
        "only an error box": _set("window", {"wins": [{"title": "OpenDesign", "cls": "#32770", "proc": "pythonw"}],
                                            "procs": ["pythonw:「OpenDesign」"]}),
        "no window at all": _set("window", {"wins": [], "procs": []}),
        "download not normal": _set("fake_log", [{"kind": "atom", "status": 200}, {"kind": "manifest", "status": 200}]),
    },
    "e8": {
        "feed never tried first": _set("fake_log", [{"kind": "releases", "status": 200},
                                                    {"kind": "download", "mode": "normal"}]),
        "API never asked after the feed failed": _set("fake_log", [{"kind": "atom", "status": 503},
                                                                   {"kind": "download", "mode": "normal"}]),
        "download not normal": _set("fake_log", [{"kind": "atom", "status": 503}, {"kind": "releases", "status": 200}]),
        "scenario not in api mode (untested)": _set("source", "feed"),
        # 后面也有一次成功的 API(红检 h5 照出:没有它的话,这条反例靠"订阅源失败之后没有 API 应答"那道也会红,
        # "先问 API"那道检查从来没被单独问到)
        "API asked before the feed failed": _set("fake_log", [{"kind": "releases", "status": 200},
                                                              {"kind": "atom", "status": 503},
                                                              {"kind": "releases", "status": 200},
                                                              {"kind": "download", "mode": "normal"}]),
        "feed did not actually fail": _set("fake_log", [{"kind": "atom", "status": 200},
                                                        {"kind": "releases", "status": 200},
                                                        {"kind": "download", "mode": "normal"}]),
        "API failed too": _set("fake_log", [{"kind": "atom", "status": 503}, {"kind": "releases", "status": 403},
                                            {"kind": "download", "mode": "normal"}]),
        "download before the API answered": _set("fake_log", [{"kind": "atom", "status": 503},
                                                              {"kind": "download", "mode": "normal"},
                                                              {"kind": "releases", "status": 200}]),
        "apply not started": _set("apply", {"ok": False, "stage": "digest", "error": "x"}),
        "old still answering": _set("health_after", {"port": 8766, "version": OLD}),
        "new version gone by the end": _set("health_final", None),
        ".new left": _set("new_exists", True),
    },
}

# 走 feed 那条(默认)的场景都要问:订阅源 + 清单真被问过、API 没被问(rl4 的真机版)。
FEED_BREAKS = {
    "feed worked but the rate-limited API was still asked": lambda f: f["fake_log"].insert(
        0, {"kind": "releases", "status": 403}),
    "manifest never fetched": lambda f: f.__setitem__(
        "fake_log", [e for e in f["fake_log"] if e.get("kind") != "manifest"]),
    "feed never asked": lambda f: f.__setitem__(
        "fake_log", [e for e in f["fake_log"] if e.get("kind") != "atom"]),
    "unknown source mode": _set("source", "carrier-pigeon"),
    "manifest only ever 404": lambda f: [e.update(status=404) for e in f["fake_log"] if e.get("kind") == "manifest"],
    "feed answered 503": lambda f: [e.update(status=503) for e in f["fake_log"] if e.get("kind") == "atom"],
    "download before the manifest": lambda f: f["fake_log"].sort(key=lambda e: 0 if e.get("kind") == "download" else 1),
}


class VVerdictIsABehaviour(unittest.TestCase):
    def test_v1_good_facts_pass(self):
        for kind in V.KINDS:
            with self.subTest(kind=kind):
                ok, text = V.KINDS[kind](_base(kind))
                self.assertTrue(ok, text)
                self.assertTrue(text.startswith("OK %s" % kind), text)

    # 通用反例里问"替身"的那两条:e7 不经过替身(直接调安装器),这两条对它问不出东西 —— 具名豁免,不是整组跳过。
    STAND_IN_BREAKS = {"app did not see stand-in", "stand-in never asked"}
    NO_STAND_IN = {"e7"}

    def test_v2_every_break_fails(self):
        for kind, breaks in BREAKS.items():
            common = [(n, m) for n, m in COMMON_BREAKS.items()
                      if not (kind in self.NO_STAND_IN and n in self.STAND_IN_BREAKS)]
            feed = list(FEED_BREAKS.items()) if _base(kind).get("source") == "feed" else []
            for name, mutate in common + feed + list(breaks.items()):
                with self.subTest(kind=kind, brk=name):
                    f = _base(kind)
                    mutate(f)
                    ok, text = V.KINDS[kind](f)
                    self.assertFalse(ok, "%s/%s 应该红却绿了:%s" % (kind, name, text))
                    self.assertTrue(text.startswith("FAIL %s" % kind), text)

    def test_rl12c_any_failing_feed_status_counts_as_the_feed_having_failed(self):
        """评审(整份 DeepSeek #4):产品在订阅源**任何**失败(404 / 403 / 5xx)时都回落 API,
        而判定器只认 `status >= 500` ⇒ 真机上产品行为完全正确却判红
        (`the release feed never failed first`)。替身今天固定回 503 所以还没误报过,
        换个状态码或换一种坏法就误。200 仍然不许算失败 —— 那条反例(feed did not actually fail)守着。"""
        for status in (403, 404, 429, 500, 503):
            with self.subTest(status=status):
                f = _base("e8")
                f["fake_log"] = [{"kind": "atom", "status": status},
                                 {"kind": "releases", "status": 200},
                                 {"kind": "download", "mode": "normal"}]
                ok, text = V.KINDS["e8"](f)
                self.assertTrue(ok, "订阅源以 %s 挂掉、产品照样靠 API 更新成功,判定器却红了:%s" % (status, text))

    def test_v3_every_scenario_has_breaks(self):
        self.assertEqual(set(BREAKS), set(V.KINDS))

    # 只进读数、不进裁决的字段(逐个说得出理由):
    #   e3.health_after  接力脚本放弃之后软件自己回没回来 —— 是产品取舍,不是 e3 问的事
    #   e4.new_exists    回滚后 .new 被注入方锁着删不掉,留着是注入造成的
    INFORMATIONAL = {"e3": {"health_after"}, "e4": {"new_exists"}, "e5": {"new_exists"}}

    def test_v4_every_fact_key_is_load_bearing_or_named_informational(self):
        # 删掉"该过"事实里的任何一个字段都必须红 —— 缺字段不许被当成"没问题"。
        for kind in V.KINDS:
            for key in _base(kind):
                if key in self.INFORMATIONAL.get(kind, set()):
                    continue
                with self.subTest(kind=kind, key=key):
                    f = _base(kind)
                    del f[key]
                    ok, text = V.KINDS[kind](f)
                    self.assertFalse(ok, "删掉 %s 之后 %s 还是绿:%s" % (key, kind, text))

    def test_v5_output_is_ascii(self):
        for kind in V.KINDS:
            f = _base(kind)
            f["apply"] = {"ok": False, "stage": "装机", "error": "中文错误"}
            _, text = V.KINDS[kind](f)
            tmp = tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)   # 泄漏闸 09-15 咬出:原来一个场景漏一个目录
            path = os.path.join(tmp, "f.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(f, fh, ensure_ascii=False)
            out = subprocess.run([sys.executable, os.path.join(SCRIPTS, "update_e2e_verdict.py"), kind, path],
                                 capture_output=True)
            out.stdout.decode("ascii")  # 非 ASCII 会在这里抛

    def test_v6_cli_exit_codes(self):
        script = os.path.join(SCRIPTS, "update_e2e_verdict.py")
        tmp = tempfile.mkdtemp()
        try:
            good = os.path.join(tmp, "good.json")
            with open(good, "w", encoding="utf-8-sig") as fh:  # pwsh 可能写 BOM
                json.dump(_base("e1"), fh, ensure_ascii=False)
            bad = os.path.join(tmp, "bad.json")
            f = _base("e1")
            f["health_after"] = None
            with open(bad, "w", encoding="utf-8") as fh:
                json.dump(f, fh)
            junk = os.path.join(tmp, "junk.json")
            with open(junk, "w") as fh:
                fh.write("{not json")
            run = lambda *a: subprocess.run([sys.executable, script, *a], capture_output=True)  # noqa: E731
            self.assertEqual(run("e1", good).returncode, 0)
            self.assertEqual(run("e1", bad).returncode, 1)
            self.assertEqual(run("e1", junk).returncode, 2)
            self.assertEqual(run("e9", good).returncode, 2)
            self.assertEqual(run("e1").returncode, 2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class WWorkflowGateIsIndependent(unittest.TestCase):
    """退出闸第二条路住在 workflow 里、写死全部场景名。和脚本那边的场景表**必须一致**。"""

    def test_w1_workflow_and_script_list_the_same_scenarios(self):
        with open(WORKFLOW, encoding="utf-8") as fh:
            wf = fh.read()
        with open(PS1, encoding="utf-8") as fh:
            ps = fh.read()
        m_wf = re.search(r"foreach \(\$k in ([^)]*)\)", wf)
        m_ps = re.search(r"^\$Expected\s*=\s*@\(([^)]*)\)", ps, re.M)
        self.assertIsNotNone(m_wf)
        self.assertIsNotNone(m_ps)
        want = set(V.KINDS)
        self.assertEqual(set(re.findall(r"'(e\d)'", m_wf.group(1))), want)
        self.assertEqual(set(re.findall(r"'(e\d)'", m_ps.group(1))), want)


class ZWaitRelayChainIsIntact(unittest.TestCase):
    """pwsh 本机跑不了,这一段的控制流只能钉结构。

    run 34863116162:我往 Wait-Relay 里加"看 .old 出现过没有"那一行时,插在了 `if ($running)` 和
    `elseif ($seen) { break }` 中间 ⇒ elseif 挂到了新那行上 ⇒ 等 0 秒就走,五个场景的事实全量早了,
    而本机 23 条全绿。⇒ 钉住:`elseif ($seen)` 的上一条非空、非注释语句必须是 `if ($running) ...`。
    """

    def test_z2_elseif_seen_hangs_off_if_running(self):
        with open(PS1, encoding="utf-8") as fh:
            lines = [l.strip() for l in fh.read().splitlines()]
        code = [l for l in lines if l and not l.startswith("#")]
        at = [i for i, l in enumerate(code) if l.startswith("elseif ($seen)")]
        self.assertEqual(len(at), 1, "找不到(或不止一处)elseif ($seen)")
        self.assertTrue(code[at[0] - 1].startswith("if ($running)"),
                        "elseif ($seen) 没挂在 if ($running) 上,挂在了:%s" % code[at[0] - 1])


class ZResetInstallsWhereTheScenarioLooks(unittest.TestCase):
    """场景前重装旧版必须显式 `/D=$InstallDir`(run 34848924198:注册表被上一个场景写成 .new,
    不带 /D 的静默安装就装进 .new,后面三个场景全被带崩)。注册表写没写坏,由各场景的 pointers 事实判。"""

    def test_z1_reset_passes_the_install_dir(self):
        with open(PS1, encoding="utf-8") as fh:
            ps = fh.read()
        m = re.search(r"^function Reset-Old \{(.*?)^\}", ps, re.M | re.S)
        self.assertIsNotNone(m, "找不到 Reset-Old")
        self.assertRegex(m.group(1), r'Start-Process -FilePath \$OldSetup -ArgumentList "/S /D=\$InstallDir"')


class ZSpacedScenariosRunLastAndReallyHaveASpace(unittest.TestCase):
    """e6/e7 把安装目录换成带空格的那个就不换回来 ⇒ 必须排在场景表最后;
    目录必须真带空格(否则 t33 那一支结构上照不出)且纯 ASCII(否则 runner 的 437 代码页下 t36 会先拒掉)。"""

    def test_z3_spaced_dir_and_order(self):
        with open(PS1, encoding="utf-8") as fh:
            ps = fh.read()
        m = re.search(r"^\$SpacedInstallDir\s*=\s*'([^']*)'", ps, re.M)
        self.assertIsNotNone(m, "找不到 $SpacedInstallDir")
        self.assertIn(" ", m.group(1))
        self.assertTrue(m.group(1).isascii(), m.group(1))
        order = re.findall(r"'(e\d)'", re.search(r"^\$Expected\s*=\s*@\(([^)]*)\)", ps, re.M).group(1))
        self.assertEqual(order[-2:], ["e6", "e7"], "e6/e7 不在最后:%r" % order)
        for fn in ("Run-e6", "Run-e7"):
            body = re.search(r"^function %s \{(.*?)^\}" % fn, ps, re.M | re.S)
            self.assertIsNotNone(body, fn)
            self.assertIn("Use-SpacedInstallDir", body.group(1).split("\n")[1], "%s 第一件事不是换目录" % fn)


if __name__ == "__main__":
    unittest.main()
