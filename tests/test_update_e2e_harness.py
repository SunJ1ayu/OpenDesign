"""Windows 更新端到端(e1~e5)的**本机能判的那一半**(track opendesign-in-app-update-install §3)。

CI 那一趟要 ~40 分钟,而且它红了分不清"产品坏了"还是"考卷搭错了"。
所以考卷自己能在本机判的,全部在这里先判掉:

- `H1` 替身给的 releases JSON,**真的产品代码认不认**(直接喂 `ds_update.decide`)
- `H2` 软件会碰的主机,hosts 重定向**全都盖住了**(拿真的 `releases_url()` 和替身给的下载地址核)
- `H3` 替身证书链按 `api.github.com` / `github.com` **真握手**(显式开 VERIFY_X509_STRICT);
       不信那张 CA 时必须握不上(证明信任确实来自它)
- `H4` 替身真发得出安装包;corrupt 模式只翻一个字节(大小不变、sha 变)
- `H5` 目录清单只排 `__pycache__`,别的差异一律看得见
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
        touched = {urlsplit(ds_update.releases_url()).hostname, urlsplit(d["asset"]["url"]).hostname}
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
        cls.log = os.path.join(cls.tmp, "fake.log")
        with open(cls.mode, "w") as fh:
            fh.write("normal")
        handler = fake_github.make_handler(ds_update.REPO, NEW, cls.setup, cls.mode, cls.log)
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

    def _get(self, host, path, cafile):
        ctx = ssl.create_default_context(cafile=cafile) if cafile else ssl.create_default_context()
        ctx.verify_flags |= ssl.VERIFY_X509_STRICT
        raw = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        with ctx.wrap_socket(raw, server_hostname=host) as s:
            s.sendall(("GET %s HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n\r\n" % (path, host)).encode())
            data = b""
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                data += chunk
        head, _, body = data.partition(b"\r\n\r\n")
        return head.decode("latin-1"), body


class H3TlsHandshakeWithTheThrowawayCa(_Served):
    def test_h3a_api_github_com_verifies_strictly(self):
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
REAL_WINDOW = {"wins": [{"title": "OpenDesign", "cls": "WindowsForms10.Window.8.app.0.141b42a_r6_ad1",
                         "proc": "pythonw"}], "procs": ["pythonw:「OpenDesign」"]}


def _base(kind):
    f = {
        "old_version": OLD, "new_version": NEW,
        "reset": {"installer_rc": 0, "health": {"port": 8766, "version": OLD}},
        "check": {"update_available": True, "latest": NEW, "error": None},
        "fake_log": [{"kind": "releases"}, {"kind": "download", "mode": "corrupt" if kind == "e2" else "normal"}],
        "markers_before": copy.deepcopy(MARKERS), "markers_after": copy.deepcopy(MARKERS),
        "pointers": copy.deepcopy(POINTERS),
    }
    started = {"ok": True, "stage": "started", "error": None}
    relay = {"seen": True, "ended": True, "seconds": 42.0}
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
    elif kind == "e1":
        f.update(apply=started, relay=relay, health_after={"port": 8766, "version": NEW},
                 live_version_after=NEW, old_exists=False, new_exists=False, window=copy.deepcopy(REAL_WINDOW))
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
        "download not corrupted": _set("fake_log", [{"kind": "releases"}, {"kind": "download", "mode": "normal"}]),
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
        "inject missed": _set("inject.landed", False),
        "bad new never ran": _set("seen_versions", [OLD]),
        "live version new": _set("live_version_after", NEW),
        "old nested in new": _set("nested_old_exists", True),
        "bad new still answering": _set("health_after", {"port": 8766, "version": "0.0.1"}),
        "live tree not restored": _set("live_after", "d2"),
        ".old left": _set("old_exists", True),
    },
    "e1": {
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
        "download not normal": _set("fake_log", [{"kind": "releases"}]),
    },
}


class VVerdictIsABehaviour(unittest.TestCase):
    def test_v1_good_facts_pass(self):
        for kind in V.KINDS:
            with self.subTest(kind=kind):
                ok, text = V.KINDS[kind](_base(kind))
                self.assertTrue(ok, text)
                self.assertTrue(text.startswith("OK %s" % kind), text)

    def test_v2_every_break_fails(self):
        for kind, breaks in BREAKS.items():
            for name, mutate in list(COMMON_BREAKS.items()) + list(breaks.items()):
                with self.subTest(kind=kind, brk=name):
                    f = _base(kind)
                    mutate(f)
                    ok, text = V.KINDS[kind](f)
                    self.assertFalse(ok, "%s/%s 应该红却绿了:%s" % (kind, name, text))
                    self.assertTrue(text.startswith("FAIL %s" % kind), text)

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
            path = os.path.join(tempfile.mkdtemp(), "f.json")
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
    """退出闸第二条路住在 workflow 里、写死五个场景名。和脚本那边的场景表**必须一致**。"""

    def test_w1_workflow_and_script_list_the_same_five(self):
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


class ZResetInstallsWhereTheScenarioLooks(unittest.TestCase):
    """场景前重装旧版必须显式 `/D=$InstallDir`(run 34848924198:注册表被上一个场景写成 .new,
    不带 /D 的静默安装就装进 .new,后面三个场景全被带崩)。注册表写没写坏,由各场景的 pointers 事实判。"""

    def test_z1_reset_passes_the_install_dir(self):
        with open(PS1, encoding="utf-8") as fh:
            ps = fh.read()
        m = re.search(r"^function Reset-Old \{(.*?)^\}", ps, re.M | re.S)
        self.assertIsNotNone(m, "找不到 Reset-Old")
        self.assertRegex(m.group(1), r'Start-Process -FilePath \$OldSetup -ArgumentList "/S /D=\$InstallDir"')


if __name__ == "__main__":
    unittest.main()
