#!/usr/bin/env python3
"""应用内更新「真去装」那一半的判据(track opendesign-in-app-update-install,第二刀)。

编号的权威表在 `tracks/opendesign-in-app-update-install/design.md` 的
`## Test strategy (oracle)`。**这里不重抄语义,只标 id。**

🔴 为什么从 `t13` 跳号:`t7`/`t8`/`t9`/`t10`/`t11` 在第一刀就被用掉了
(见 `tests/test_ds_update.py` 与 `tests/test_ds_web_update.py`),而
`tests/mutation-*.sh` **是按名字选测试的** —— 同一个名字指两件事,红检会咬错东西,
收据里那句 "t8 绿了" 也再没法判断说的是哪个 t8。
空着的 `t4/t5/t6` 继续用(第一刀的 design 本来就是给这三件事预留的)。

**这份考卷此刻应该全红** —— `bin/ds_update_apply.py` 还不存在。
判据先行单独一笔,git 历史里证明不了"红过"的判据等于没红检过。

**判据不许有外网出口**(2026-08-10 事故):下载、装、问 health 全部走注入的替身,
一次真网都不打;整棵"活树"和"数据根"都是 tmpdir 里造出来的。

⚠️ 这里判不了的那一半,别在这里假装判得了:`t6`(收摊闸)和 `t17`(换名回滚)
咬的是段② `.cmd` 的**行为**,而 `.cmd` 只有 Windows 跑得起来。在 Linux 上写个
模拟器再断言模拟器 = 证明不了任何事的绿。⇒ 这里只判**我们生成出来的那段脚本的结构**
(机械契约,形状照抄本单 `t12a/t12b`),真行为归 Windows CI 的 `e3`/`e4`。
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import sys
import tempfile
import tokenize
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bin"))

MODULE_SRC = os.path.join(ROOT, "bin", "ds_update_apply.py")

# 判据先行那一版这里包了个 try/except,好让"模块还不存在"时 30 条各自红、可数。
# 实现落地后那段就成了**一条永远不执行的断言**,死断言闸当场咬住(2026-09-08)。
# 脚手架的使命完成了就拆掉 —— 留着既挡不住什么,又让每层看到的都是绿的。
import ds_update_apply  # noqa: E402  (故意在路径注入之后)

# 一个**绝不可能由版本号拼出来**的下载地址:t14 靠它区分"照抄 GitHub 给的"
# 和"自己拼"。第一刀 F1 栽的就是拼地址(win-installer-1.0.0 对不上真 tag 1.0)。
ODD_ASSET_URL = ("https://objects.githubusercontent.com/gh-release-assets/"
                 "9f3c1a/OpenDesign-Setup-0.98.5.exe?token=NOT-DERIVABLE-42")

NEW_VERSION = "0.98.5"
OLD_VERSION = "0.98.4"

# 🔴 别用 None 当"帮我算一个合法 digest"的信号:t15a 要传的正是 None(缺失),
#    两种含义撞在一个值上,那条断言就**结构上问不出它要问的事**(第一版就是这么写的,
#    实现落地后当场照出来)。用一个独一无二的哨兵。
_AUTO = object()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tree_digest(root: str) -> dict:
    """整棵树的"逐字节"指纹:相对路径 → 内容 sha256。

    比"目录还在"强,也比"文件数一样"强 —— design 里那条
    「最像绿其实错:更新成功了但档案没了」要求比对**真实文件内容**。
    """
    out = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            with open(full, "rb") as fh:
                out[rel.replace(os.sep, "/")] = _sha256_bytes(fh.read())
    return out


def _write(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def _make_live_tree(base: str, version: str = OLD_VERSION) -> str:
    """造一棵"活树"(业主机器上那个 $INSTDIR 的最小形状)。"""
    live = os.path.join(base, "Programs", "OpenDesign")
    _write(os.path.join(live, "ds", "bin", "ds_shell.py"), b"# sentinel\n")
    _write(os.path.join(live, "ds", "版本号.txt"), version.encode("utf-8"))
    _write(os.path.join(live, "python", "python.exe"), b"MZ-fake-python\n")
    _write(os.path.join(live, "OpenDesign.exe"), b"MZ-fake-launcher\n")
    return live


def _make_data_root(base: str) -> str:
    """造数据根:`Data\\`(死线)、`UserData\\`(死线)、`Logs\\`(具名豁免)。"""
    root = os.path.join(base, "LocalAppData", "OpenDesign")
    _write(os.path.join(root, "Data", "项目", "客户备忘.md"),
           "# 业主的东西\n".encode("utf-8"))
    _write(os.path.join(root, "Data", "参考图库", "a.png"), b"\x89PNG-fake")
    _write(os.path.join(root, "UserData", "config.json"), b'{"model":"x"}')
    _write(os.path.join(root, "Logs", "更新.log"), b"old line\n")
    return root


def _installer_bytes(version: str = NEW_VERSION) -> bytes:
    return ("MZ-fake-setup-" + version).encode("utf-8")


def _decision(url: str = ODD_ASSET_URL, digest=_AUTO, version: str = NEW_VERSION,
              payload: bytes = None) -> dict:
    """`ds_update.decide()` 那个形状里,第二刀真正会消费的几格。"""
    if payload is None:
        payload = _installer_bytes(version)
    if digest is _AUTO:
        digest = "sha256:" + _sha256_bytes(payload)
    return {
        "current": OLD_VERSION,
        "update_available": True,
        "latest": version,
        "release_url": "https://github.com/SunJ1ayu/OpenDesign/releases/tag/win-installer-" + version,
        "asset": {"name": "OpenDesign-Setup-%s.exe" % version,
                  "url": url, "size": len(payload), "digest": digest},
    }


def _code_without_comments(path: str) -> str:
    """只留代码(含字符串字面量),**丢掉注释**。

    为什么费这个事:上一次我写"源码里不许出现 X"的结构闸,把解释"不许出现 X"的
    那句注释自己咬红了。**带误报的闸会逼出绕开它的习惯**,和放水一样坏。
    """
    with open(path, "rb") as fh:
        toks = list(tokenize.tokenize(fh.readline))
    return "\n".join(t.string for t in toks if t.type != tokenize.COMMENT)


class _Base(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="dsupd-")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.live = _make_live_tree(self.base)
        self.data_root = _make_data_root(self.base)
        self.temp = os.path.join(self.base, "Temp")
        os.makedirs(self.temp, exist_ok=True)
        self.paths = {
            "live": self.live,
            "new": self.live + ".new",
            "old": self.live + ".old",
            "data_root": self.data_root,
            "temp": self.temp,
        }
        self.live_before = _tree_digest(self.live)
        self.data_before = {
            "Data": _tree_digest(os.path.join(self.data_root, "Data")),
            "UserData": _tree_digest(os.path.join(self.data_root, "UserData")),
        }
        self.downloads = []   # 记下 download 替身被喂了什么地址
        self.installs = []    # 记下 install 替身被喂了什么目标目录

    # --- 注入的替身:一次真网都不打,一次真 NSIS 都不跑 ---

    def _download(self, payload: bytes):
        def fake(url, dest):
            self.downloads.append((url, dest))
            _write(dest, payload)
            return dest
        return fake

    def _install(self, version=NEW_VERSION, sentinel=True):
        """替身安装器:把"装出来的新树"materialize 到 target。"""
        def fake(setup_path, target_dir):
            self.installs.append((setup_path, target_dir))
            if sentinel:
                _write(os.path.join(target_dir, "ds", "bin", "ds_shell.py"),
                       b"# sentinel new\n")
            _write(os.path.join(target_dir, "ds", "版本号.txt"),
                   version.encode("utf-8"))
            _write(os.path.join(target_dir, "python", "python.exe"),
                   b"MZ-fake-python-new\n")
            return 0
        return fake

    def _apply(self, decision, payload=None, install=None):
        if payload is None:
            payload = _installer_bytes()
        return ds_update_apply.apply_update(
            decision, self.paths,
            download=self._download(payload),
            install=install if install is not None else self._install())

    # --- 复用的断言 ---

    def assertLiveUntouched(self, why=""):
        self.assertEqual(_tree_digest(self.live), self.live_before,
                         "活树被动过了 —— " + why)

    def assertDeadLineHeld(self, why=""):
        for name, before in self.data_before.items():
            self.assertEqual(_tree_digest(os.path.join(self.data_root, name)),
                             before, "死线破了:%s 变了 —— %s" % (name, why))


class DigestIsMandatory(_Base):
    """t15 —— `digest` 缺失/形状不对 ⇒ 当作校验失败,不许"没给就跳过校验"。"""

    def test_t15a_missing_digest_is_a_failure_not_a_skip(self):
        r = self._apply(_decision(digest=None))
        self.assertFalse(r["ok"])
        self.assertEqual(r["stage"], "digest")
        self.assertEqual(self.downloads, [],
                         "digest 都没有就不该开始下 43MB")
        self.assertLiveUntouched("digest 缺失")

    def test_t15b_malformed_digest_is_a_failure(self):
        for bad in ("", "sha256:", "md5:%s" % ("0" * 32), "sha256:xyz",
                    "sha256:" + "0" * 63, "deadbeef"):
            with self.subTest(bad=bad):
                r = self._apply(_decision(digest=bad))
                self.assertFalse(r["ok"], "%r 不该被当成合法 digest" % bad)
                self.assertEqual(r["stage"], "digest")

    def test_t15c_a_real_digest_parses(self):
        hexd = "a" * 64
        self.assertEqual(ds_update_apply.parse_digest("sha256:" + hexd), hexd)
        self.assertEqual(ds_update_apply.parse_digest("SHA256:" + hexd.upper()),
                         hexd, "大小写不该影响它")


class DownloadAddressComesFromGitHub(_Base):
    """t14 —— 地址只能来自选中 release 的 `browser_download_url`,不许拼。"""

    def test_t14a_downloader_gets_the_exact_url_github_gave(self):
        self._apply(_decision(url=ODD_ASSET_URL))
        self.assertEqual([u for u, _d in self.downloads], [ODD_ASSET_URL],
                         "地址被改写了 —— 拼出来的地址点开就是 404(第一刀 F1)")

    def test_t14b_source_never_composes_a_download_url(self):
        code = _code_without_comments(MODULE_SRC)
        self.assertNotIn("releases/download", code,
                         "源码里出现了自己拼下载地址的形状")


class ChecksumMismatchChangesNothing(_Base):
    """t4 —— sha256 对不上 ⇒ 拒绝执行,活树零改动,`.new` 删干净。"""

    def setUp(self):
        super().setUp()
        # 声明的是"好包"的哈希,真下回来的是别的字节 = 下坏了/被换了
        self.decision = _decision(digest="sha256:" + _sha256_bytes(b"the-good-one"))
        self.result = self._apply(self.decision, payload=b"tampered-bytes")

    def test_t4a_refuses(self):
        self.assertFalse(self.result["ok"])
        self.assertEqual(self.result["stage"], "verify")

    def test_t4b_live_tree_is_byte_identical(self):
        self.assertLiveUntouched("校验失败")

    def test_t4c_new_dir_is_gone(self):
        self.assertFalse(os.path.exists(self.paths["new"]),
                         ".new 该删干净 —— 失败就是当无事发生")

    def test_t4d_installer_never_ran(self):
        self.assertEqual(self.installs, [], "校验没过就不该去装")

    def test_t4e_dead_line_holds(self):
        self.assertDeadLineHeld("校验失败")


class NewTreeMustBeComplete(_Base):
    """t5 —— `.new` 树不完整 ⇒ 不交棒、删 `.new`、活树零改动。"""

    def test_t5a_missing_sentinel_aborts(self):
        r = self._apply(_decision(), install=self._install(sentinel=False))
        self.assertFalse(r["ok"])
        self.assertEqual(r["stage"], "newtree")
        self.assertFalse(os.path.exists(self.paths["new"]))
        self.assertLiveUntouched("新树缺哨兵")

    def test_t5b_wrong_version_in_new_tree_aborts(self):
        # 装出来的是 0.98.3(装了个旧的/错的),而我们要的是 0.98.5
        r = self._apply(_decision(), install=self._install(version="0.98.3"))
        self.assertFalse(r["ok"])
        self.assertEqual(r["stage"], "newtree")
        self.assertFalse(os.path.exists(self.paths["new"]))
        self.assertLiveUntouched("新树版本号不对")

    def test_t5c_a_good_new_tree_hands_off(self):
        r = self._apply(_decision())
        self.assertTrue(r["ok"], r.get("error"))
        self.assertTrue(os.path.isfile(r["relay"]),
                        "成功要留下接力脚本 —— 段② 全靠它")


class LiveTreeIsNeverTouchedInStageOne(_Base):
    """t16 —— 下载 + 装 `.new` 全程(**含成功路径**)活树逐字节不变。"""

    def test_t16a_success_path_does_not_touch_the_live_tree(self):
        r = self._apply(_decision())
        self.assertTrue(r["ok"], r.get("error"))
        self.assertLiveUntouched("成功路径")

    def test_t16b_installer_targets_new_not_live(self):
        self._apply(_decision())
        targets = [t for _s, t in self.installs]
        self.assertEqual(targets, [self.paths["new"]])
        self.assertNotEqual(self.paths["new"], self.live)

    def test_t16c_dead_line_holds_on_the_success_path(self):
        self._apply(_decision())
        self.assertDeadLineHeld("成功路径")


class TheDeadLine(_Base):
    """t13 —— `Data\\`/`UserData\\` 逐字节不变;`Logs\\` **具名**豁免。"""

    def test_t13a_logs_exemption_is_a_named_dir_not_a_glob(self):
        exempt = ds_update_apply.DATA_ROOT_EXEMPT_DIRS
        self.assertEqual(tuple(exempt), ("Logs",))
        for name in exempt:
            self.assertNotIn("*", name, "豁免不许写成通配符")
            self.assertNotIn("?", name, "豁免不许写成通配符")

    def test_t13b_protected_dirs_are_named(self):
        self.assertEqual(tuple(ds_update_apply.DATA_ROOT_PROTECTED_DIRS),
                         ("Data", "UserData"))

    def test_t13c_stage_one_writes_nothing_under_data_root_but_logs(self):
        before = _tree_digest(self.data_root)
        self._apply(_decision())
        after = _tree_digest(self.data_root)
        changed = {k for k in set(before) | set(after)
                   if before.get(k) != after.get(k)}
        stray = {k for k in changed if not k.startswith("Logs/")}
        self.assertEqual(stray, set(),
                         "段① 只允许写 Logs/,别的一个字节都不许动")


class HealthAcceptanceCannotBeFooled(_Base):
    """t18 —— 收口 health 必须带一次性 nonce,且绕开系统代理。"""

    def test_t18a_url_carries_the_nonce(self):
        url = ds_update_apply.health_url(8766, "n0nce-abc")
        self.assertIn("n0nce-abc", url)
        self.assertIn("127.0.0.1:8766", url)

    def test_t18b_opener_bypasses_the_system_proxy(self):
        """⚠️ 这条第一版问错了地方,实现落地当场照出来 —— 留个记号免得下次再写一遍。

        原来断言 `opener.handlers` 里有一个 proxies 为空的 ProxyHandler。**实测:没有。**
        空 proxies 的 ProxyHandler 一个 `*_open` 方法都不生成,而
        `OpenerDirector.add_handler` 明确跳过 `proxy_open` ⇒ 它压根不会被收进 handlers。
        那条断言问的是一件结构上不存在的事,和实现对不对无关。

        搬到问得出的地方:**在有代理环境变量的情况下**,我们的 opener 不许挂上任何
        带 proxies 的 handler。带对照组 —— 默认 opener 在同一环境下必须挂得上,
        否则这条判据自己就是恒绿的。
        """
        import urllib.request
        from unittest import mock
        env = {"http_proxy": "http://proxy.invalid:8080",
               "https_proxy": "http://proxy.invalid:8080",
               "HTTP_PROXY": "http://proxy.invalid:8080",
               "HTTPS_PROXY": "http://proxy.invalid:8080"}
        with mock.patch.dict(os.environ, env, clear=False):
            ours = ds_update_apply.build_opener()
            theirs = urllib.request.build_opener()   # 对照组

        def proxied(opener):
            return [h for h in opener.handlers
                    if isinstance(h, urllib.request.ProxyHandler) and h.proxies]

        self.assertTrue(proxied(theirs),
                        "对照组塌了:默认 opener 在有代理环境时都没挂上代理 ⇒ "
                        "这条判据问不出东西,别信它的绿")
        self.assertEqual(proxied(ours), [],
                         "业主跑 VPN —— 问自己机器不许绕道系统代理(0.98.1 栽过)")

    def test_t18c_answer_without_the_nonce_is_not_accepted(self):
        ok = ds_update_apply.health_says(
            {"ok": True, "version": NEW_VERSION}, NEW_VERSION, "n1")
        self.assertFalse(ok, "没回 nonce 的可能是旧进程在答")

    def test_t18d_answer_with_a_stale_nonce_is_not_accepted(self):
        ok = ds_update_apply.health_says(
            {"ok": True, "version": NEW_VERSION, "nonce": "n0"}, NEW_VERSION, "n1")
        self.assertFalse(ok)

    def test_t18e_right_version_and_right_nonce_is_accepted(self):
        ok = ds_update_apply.health_says(
            {"ok": True, "version": NEW_VERSION, "nonce": "n1"}, NEW_VERSION, "n1")
        self.assertTrue(ok)

    def test_t18f_right_nonce_but_old_version_is_not_accepted(self):
        ok = ds_update_apply.health_says(
            {"ok": True, "version": OLD_VERSION, "nonce": "n1"}, NEW_VERSION, "n1")
        self.assertFalse(ok, "换名没生效也可能答得出 nonce")


class RelayScriptShape(_Base):
    """t6 / t17 —— 只判**生成物的结构**;真行为归 Windows CI 的 e3/e4。

    机械契约,不是注释级契约:形状照抄本单 `t12a/t12b`(commit 46c0c90)。
    """

    def _plan(self):
        return ds_update_apply.relay_plan(self.paths, port=8766, nonce="n1",
                                          expect_version=NEW_VERSION)

    def _kinds(self, plan):
        return [step["kind"] for step in plan]

    def test_t6a_teardown_gate_comes_before_any_rename(self):
        kinds = self._kinds(self._plan())
        self.assertIn("teardown_gate", kinds)
        self.assertIn("rename", kinds)
        self.assertLess(kinds.index("teardown_gate"), kinds.index("rename"),
                        "收摊闸必须在任何一次改名之前 —— 锚点重拍后就是这一条")

    def test_t6b_failed_teardown_deletes_new_and_stops(self):
        gate = [s for s in self._plan() if s["kind"] == "teardown_gate"][0]
        self.assertIn("delete_new", gate["on_fail"])
        self.assertNotIn("rename", gate["on_fail"],
                         "收不干净就绝不许换名")

    def test_t6c_renderer_keeps_every_step_and_their_order(self):
        plan = self._plan()
        text = ds_update_apply.render_relay(plan)
        at = [text.index(s["marker"]) for s in plan]
        self.assertEqual(at, sorted(at),
                         "渲染出来的 .cmd 与 plan 的顺序对不上")
        self.assertEqual(len(set(at)), len(at), "有步骤被渲染器丢了")

    def test_t17a_plan_has_a_rollback_that_puts_old_back(self):
        rollback = [s for s in self._plan() if s["kind"] == "rollback"]
        self.assertTrue(rollback, "没有回滚步 —— 换名中断就回不去了")
        self.assertIn(self.paths["old"], rollback[0]["cmd"])
        self.assertIn(self.paths["live"], rollback[0]["cmd"])

    def test_t17b_rendered_script_contains_the_rollback(self):
        plan = self._plan()
        text = ds_update_apply.render_relay(plan)
        rollback = [s for s in plan if s["kind"] == "rollback"][0]
        self.assertIn(rollback["marker"], text)


class InstallerUpdateFlagContract(_Base):
    """t20 —— `/UPDATE` 这条跨文件契约是**机械的**,不是注释级的。

    死线(t13)要求更新前后 `UserData\\` 逐字节不变,而 `OpenDesign.nsi:143` 每次安装
    都 `Call ProvisionConfig`。修法是给安装器加 `/UPDATE` 档、更新时不跑 provisioning
    (**改实现不改考卷**)。

    那个修法**横跨两个文件、两种语言**:python 这边发旗子,NSIS 那边认。
    任何一边悄悄改掉,死线就破了,**而 t13 在 Linux 上照样全绿** —— 它用的是替身
    安装器,根本走不到真 NSIS。所以这条契约必须自己被钉住。
    形状照抄本单 `t12a/t12b`(commit 46c0c90):把注释级契约变成机械的。
    """

    NSI = os.path.join(ROOT, "installer", "OpenDesign.nsi")

    def _nsi(self):
        with open(self.NSI, encoding="utf-8", errors="replace") as fh:
            return fh.read()

    def test_t20a_installer_is_invoked_with_the_update_flag(self):
        import subprocess
        seen = []

        def fake_call(cmd, **kwargs):
            seen.append((list(cmd), kwargs))
            return 0

        real = subprocess.call
        subprocess.call = fake_call
        try:
            ds_update_apply._default_install("C:/tmp/Setup.exe", "C:/tmp/OpenDesign.new")
        finally:
            subprocess.call = real
        self.assertTrue(seen, "没调起安装器")
        argv, _kw = seen[0]
        self.assertIn(ds_update_apply.INSTALL_UPDATE_FLAG, argv)
        self.assertIn("/S", argv, "更新必须静默")
        self.assertTrue(argv[-1].startswith("/D="),
                        "/D= 必须是最后一个参数(NSIS 的规矩,不是我们的选择)")

    def test_t20b_the_nsi_parses_that_exact_flag(self):
        """⚠️ 这条第一版太松,红检当场照出来(m23 漏网,2026-09-08)。

        原来问的是「文件里出现过这面旗子吗」。而**我自己写的那段注释里就有这几个字**
        ⇒ 把 `${GetOptions}` 里的 `/UPDATE` 改成 `/UPD`,判据照样全绿。
        一条为了消灭"注释级契约"而写的断言,自己退化成了注释级 —— 正是它要防的病。

        收紧成:这面旗子必须出现在**真正解析参数的那一行**上(注释行不算数)。
        """
        lines = [ln for ln in self._nsi().splitlines()
                 if not ln.strip().startswith(";")]
        parsing = [ln for ln in lines
                   if "GetOptions" in ln
                   and ds_update_apply.INSTALL_UPDATE_FLAG in ln]
        self.assertTrue(parsing,
                        "没有任何一行 ${GetOptions} 在解析 %s —— python 发的旗子,"
                        "NSIS 那边根本没人接" % ds_update_apply.INSTALL_UPDATE_FLAG)

    def test_t20c_provisioning_is_guarded_by_the_update_flag(self):
        """`Call ProvisionConfig` 必须落在一个由更新档把守的分支里。

        不是"文件里出现过 /UPDATE 就算数" —— 那种断言随便加一行注释就骗过去了。
        这里查**结构**:那一行上方最近的一个 `${If}`/`${Unless}` 必须提到更新档变量。
        """
        lines = self._nsi().splitlines()
        at = [i for i, ln in enumerate(lines)
              if "Call ProvisionConfig" in ln and not ln.strip().startswith(";")]
        self.assertEqual(len(at), 1,
                         "ProvisionConfig 的调用点不止一处了,这条闸要跟着改")
        guard = None
        for i in range(at[0] - 1, -1, -1):
            line = lines[i].strip()
            if line.startswith("${EndIf}"):
                break          # 撞到别的块的收尾 ⇒ 我们这行不在那个块里
            if line.startswith(("${If}", "${Unless}", "${IfNot}")):
                guard = line
                break
        self.assertIsNotNone(guard, "ProvisionConfig 是无条件调用的 —— 死线 t13 破了")
        self.assertIn(ds_update_apply.UPDATE_MODE_VAR, guard,
                      "把守它的不是更新档:%s" % guard)


class HandoffToTheRelay(_Base):
    """t21 —— 交棒:把接力脚本**脱离**启动,起不来就绝不往下走。

    这一步是整条路上最不能出错的地方:它之后 `ds_web` 就要请外壳把整套软件关掉。
    **脚本没起来却把软件关了 = 业主看到"软件关了,没再打开",而且没有任何东西会去回滚。**
    """

    SRC = os.path.join(ROOT, "bin", "ds_update_apply.py")

    def _relay(self):
        path = os.path.join(self.temp, "opendesign-update-relay.cmd")
        with open(path, "w", encoding="gbk", errors="replace") as fh:
            fh.write("@echo off\r\n")
        return path

    def test_t21a_missing_script_is_never_reported_as_handed_off(self):
        seen = []
        ok = ds_update_apply.handoff(os.path.join(self.temp, "不存在.cmd"),
                                     launcher=lambda *a, **k: seen.append(a))
        self.assertFalse(ok)
        self.assertEqual(seen, [], "脚本都不在,还是把它启动了")

    def test_t21b_the_script_path_is_what_gets_launched(self):
        relay = self._relay()
        seen = []

        def fake(argv, **kwargs):
            seen.append((list(argv), kwargs))
            return object()

        self.assertTrue(ds_update_apply.handoff(relay, launcher=fake))
        self.assertTrue(seen, "没起")
        argv, _kw = seen[0]
        self.assertTrue(any(relay in str(a) for a in argv),
                        "起的不是我们刚写下的那个脚本:%r" % (argv,))

    def test_t21c_launch_uses_the_one_source_for_platform_flags(self):
        relay = self._relay()
        seen = []

        def fake(argv, **kwargs):
            seen.append(kwargs)
            return object()

        ds_update_apply.handoff(relay, launcher=fake)
        import ds_shell_core
        for key, value in ds_shell_core.spawn_kwargs().items():
            self.assertEqual(seen[0].get(key), value,
                             "平台标志没走唯一来源 —— Windows 上那个黑窗口业主一关,"
                             "接力脚本就跟着死,而软件已经在关了")

    def test_t21d_a_launcher_that_blows_up_is_not_a_handoff(self):
        relay = self._relay()

        def boom(*_a, **_k):
            raise OSError("起不来")

        self.assertFalse(ds_update_apply.handoff(relay, launcher=boom),
                         "起失败了却报交棒成功 ⇒ 下一步就把软件关了")

    def test_t21e_the_default_launcher_never_waits(self):
        """**机械契约**:默认启动器必须是"起了就走"。

        接力脚本要等我们**死透**才动手 —— 我们要是等它结束,就是互相等死:
        软件永远关不掉,更新永远不发生,而界面上写着"正在更新"。
        Linux 上没法真跑 `.cmd`,所以这里钉的是源码结构(形状同 t12a/t12b)。
        """
        import ast as _ast
        with open(self.SRC, encoding="utf-8") as fh:
            tree = _ast.parse(fh.read())
        fn = next((n for n in _ast.walk(tree)
                   if isinstance(n, _ast.FunctionDef) and n.name == "_default_launcher"), None)
        self.assertIsNotNone(fn, "没有默认启动器")
        names = set()
        for node in _ast.walk(fn):
            if isinstance(node, _ast.Call):
                f = node.func
                names.add(f.attr if isinstance(f, _ast.Attribute) else
                          getattr(f, "id", ""))
        self.assertIn("Popen", names, "默认启动器不是 Popen ⇒ 多半在等它结束")
        for blocking in ("call", "run", "check_call", "check_output", "wait", "communicate"):
            self.assertNotIn(blocking, names,
                             "默认启动器里出现了 %s() —— 那会等接力脚本结束,"
                             "而它正在等我们死:互相等死" % blocking)


if __name__ == "__main__":
    unittest.main()
