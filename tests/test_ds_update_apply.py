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
import re
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


def _installer_cmdline(setup_path, target_dir):
    """`_default_install` 在 Windows 上**真正交给安装器的那条命令行**。

    Windows 起进程只有一条字符串:传列表时 subprocess 先用 list2cmdline 拼(会给带空格的元素加引号),
    传字符串就原样用。替身只截获、不起进程。
    """
    import subprocess
    seen = []
    real = subprocess.call
    subprocess.call = lambda cmd, **kw: seen.append(cmd) or 0
    try:
        ds_update_apply._default_install(setup_path, target_dir)
    finally:
        subprocess.call = real
    assert seen, "没调起安装器"
    cmd = seen[0]
    return cmd if isinstance(cmd, str) else subprocess.list2cmdline(cmd)


def _nsis_reads(cmdline):
    """NSIS 安装器读自己命令行的那段循环 —— **逐行照搬**,不是我对它的理解。

    来源:kichik/nsis `Source/exehead/Main.c` 第 237~288 行(master,2026-09-15 取;
    这段逻辑多年未变)。`CMP4CHAR(cmdline-2, " /D=")` 要求 `/D=` 前面紧挨着的是**空格**:
    参数被引号包住时,前一个字符是引号 ⇒ 整个 `/D=` 被当成没传,安装目录退回注册表里记的那个。
    返回 `{"silent": /S 认出来了吗, "instdir": /D= 读出的目录或 None}`。
    """
    s = cmdline + "\0"

    def findchar(i, c):
        while s[i] != "\0" and s[i] != c:
            i += 1
        return i

    i, seek = 0, " "
    if s[0] == '"':
        seek, i = '"', 1
    i = findchar(i, seek)
    if s[i] != "\0":          # CharNext
        i += 1
    silent, instdir = False, None
    while s[i] != "\0":
        while s[i] == " ":
            i += 1
        seek = " "
        if s[i] == '"':
            i += 1
            seek = '"'
        if s[i] == "/":
            i += 1
            if s[i] == "S" and s[i + 1] in (" ", "\0"):
                silent = True
            if i >= 2 and s[i - 2:i + 2] == " /D=":
                instdir = s[i + 2:-1]     # mystrcpy 抄到结尾
                break                      # /D= must always be last
        i = findchar(i, seek)
        if s[i] == '"':
            i += 1
    return {"silent": silent, "instdir": instdir}


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


class TheRelayIsARealProgram(_Base):
    """t24 —— 渲染出来的 `.cmd` **必须是一个真程序**,不是一份带注释的清单。

    🔴 这一组是 2026-09-08 我自己生成一份脚本、肉眼看它长什么样时逼出来的,
    而当时 `t6`/`t17` **全是绿的**。生成物的实际形态是:

        call :wait_gone ...        ← 这个标签根本不存在
        :: on_fail -> delete_new   ← 失败分支只是**注释**,没有任何真实控制流
        move ... （改名）           ← 于是"收摊没干净"照样往下改名
        call :ask_health ...
        :: on_fail -> rollback
        move ...（回滚)            ← 回滚是**无条件执行**的:成功路径也会跑

    真跑起来会毁掉业主的安装,而判据一片绿。

    **根因是同一个形状,今天第三次:结构断言 ≠ 行为断言。**
    `t6a` 只问"收摊闸的下标小于改名的下标",`t6b` 只问 plan 的 on_fail 列表里
    有没有 `delete_new` —— 它们问的是**计划里有没有这几件事**,
    没问**渲染出来的脚本会不会照着计划执行**。

    design 里写过"python 侧只判结构、行为归 Windows CI",那句话没错;
    错在我把"结构"理解得太松了 —— **结构断言必须强到能保证"渲染出来的是个真程序"**,
    否则 CI 之前的一切都是假的(而 CI 上它会红在一堆 Windows 环境噪音里)。
    """

    #: ⚠️ 第一版这里只传了 plan、**没传 paths** ⇒ 渲染出来的脚本里所有路径都是空的,
    #: 于是 t24e(不许混合分隔符)一行 `C:` 都看不到、**天然全绿**。
    #: 是我把 `_win_path` 改成用 `/` 拼、发现它照样不红,才查出来的。
    #: 教训:**判据调用被测函数时参数给不全,它测的就是一个不存在的场景。**
    PATHS = {"live": r"C:\P\OpenDesign", "new": r"C:\P\OpenDesign.new",
             "old": r"C:\P\OpenDesign.old", "data_root": r"C:\D\OpenDesign",
             "temp": r"C:\T"}

    def _text(self):
        plan = ds_update_apply.relay_plan(self.PATHS, port=8766, nonce="n1",
                                          expect_version="0.98.5")
        return ds_update_apply.render_relay(plan, paths=self.PATHS, port=8766,
                                            nonce="n1", expect_version="0.98.5")

    def _lines(self):
        return [ln.strip() for ln in self._text().splitlines()]

    def test_t24a_every_called_label_exists(self):
        """`call :foo` 而没有 `:foo` ⇒ 脚本当场报错。"""
        import re
        text = self._text()
        called = set(re.findall(r"(?mi)^\s*call\s+:(\w+)", text))
        defined = set(re.findall(r"(?mi)^\s*:(\w+)\b", text))
        missing = sorted(called - defined)
        self.assertEqual(missing, [],
                         "call 了不存在的标签 %s —— 这份脚本一跑就报错" % (missing,))
        self.assertTrue(called, "一个子程序都没有?收摊和问 health 是怎么做的")

    def test_t24b_failure_branches_are_control_flow_not_comments(self):
        """🔴 `:: on_fail -> delete_new` 是**注释**,不是分支。

        收摊没干净时它挡不住下一行的改名 —— 而"不许进换名步"正是 t6 存在的全部理由。
        """
        # ⚠️ 09-15 改问法:原来问"含 on_fail 的行不许是注释",而 t24 重写渲染器(2d63076)后
        #    生成物里再没有 on_fail 这几个字 ⇒ 那条断言从 09-08 起**一次都没执行过**(死断言闸 09-15 咬出)。
        #    它真正要防的是"控制流被写成注释" ⇒ 直接问:注释行里不许出现 goto / errorlevel。
        comments = [l for l in self._lines() if l.startswith("::") or l.lower().startswith("rem ")]
        self.assertTrue(comments, "一行注释都没有?这条问法问不出东西了,换个问法")
        for line in comments:
            self.assertFalse("goto" in line.lower() or "errorlevel" in line.lower(),
                             "控制流写进了注释,它挡不住任何东西:%s" % line)
        text = self._text()
        self.assertIn("errorlevel", text.lower(),
                      "整份脚本没有一次错误检查 ⇒ 每一步都是「跑了就算成功」")

    def test_t24c_teardown_failure_really_skips_the_rename(self):
        """收摊闸失败时,**改名那一行必须够不着**。

        查法:收摊闸和第一次改名之间,必须存在一条会跳走的控制流
        (goto / exit / if errorlevel ... goto)。
        """
        lines = self._lines()
        gate = next(i for i, l in enumerate(lines) if "wait_gone" in l or "teardown" in l.lower())
        first_rename = next(i for i, l in enumerate(lines)
                            if l.lower().startswith("move ") and i > gate)
        between = " ".join(lines[gate:first_rename]).lower()
        self.assertTrue("goto" in between or "exit" in between,
                        "收摊闸和第一次改名之间没有任何跳转 ⇒ 收不干净照样改名")

    def test_t24d_rollback_is_not_unconditional(self):
        """🔴 回滚不许无条件执行 —— 否则**成功路径也会回滚**:

        改名成新版 → 起起来 → 问 health → 然后又把新版改回 `.new`、把 `.old` 改回来。
        """
        lines = [l for l in self._lines() if l and not l.startswith("::")]
        # 找的是**标签定义**(`:rollback`),不是那些 `goto :rollback`。
        # 第一版写成"含 rollback 的第一行",匹配到的是 goto,问错了地方。
        rb = next(i for i, l in enumerate(lines)
                  if l.lower().rstrip() == ":rollback")
        prev = lines[rb - 1].lower() if rb else ""
        # 最精确的问法:**紧挨着回滚之前那条可执行语句**必须是 exit 或 goto ——
        # 否则成功路径跑完会直接"掉进"回滚,把刚装好的新版又换回去。
        self.assertTrue(prev.startswith("exit") or prev.startswith("goto"),
                        "成功路径会掉进回滚:回滚前一句是「%s」" % prev)

    def test_t24e_no_mixed_path_separators(self):
        """`C:\\A\\B/Logs\\c.log` 这种混合分隔符在 cmd 里是坑,而且一眼看不出来。"""
        for line in self._lines():
            if "C:" in line:
                self.assertNotIn("/", line.replace("/Y", "").replace("/S", "")
                                 .replace("/Q", "").replace("/b", "").replace("/c", ""),
                                 "路径里混进了正斜杠:%s" % line)

    def test_t24f_the_script_does_not_always_exit_zero(self):
        """全程 `exit /b 0` = 段① 永远不知道段② 出没出事,日志里也查不出来。"""
        text = self._text()
        self.assertNotEqual(text.count("exit /b"), text.count("exit /b 0"),
                            "每一条退出路径都返回 0 ⇒ 失败和成功在外面长得一模一样")


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
        # ⚠️ 2026-09-15 收紧:原来问的是 argv 列表(`argv[-1].startswith("/D=")`)。
        #    而"不加引号"是**命令行**层面的规矩,argv 里根本不存在引号 —— 引号是 Windows 上
        #    list2cmdline 在起进程前才加的 ⇒ 那条断言结构上问不出它注释里声称的事(外审 DeepSeek 发现 6)。
        #    改成问安装器真正收到的那条命令行;"读出来的目录对不对"归 t33。
        cmdline = _installer_cmdline("C:/tmp/Setup.exe", "C:/tmp/OpenDesign.new")
        self.assertIn(" %s " % ds_update_apply.INSTALL_UPDATE_FLAG, cmdline)
        self.assertIn(" /S ", cmdline, "更新必须静默")
        self.assertRegex(cmdline, r' /D=[^"]*$',
                         "/D= 必须是最后一个参数且不加引号(NSIS 的规矩,不是我们的选择)")

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


class WhereTheNewTreeGoes(_Base):
    """t23 —— `.new` / `.old` 放哪。**放错地方就是踩死线,或者被安装器自己覆盖掉。**

    `ds_web` 手上只有 `ds_root`(它就是 `<安装根>\\ds`,安装器写死的布局;
    `OpenDesign.nsi` 的哨兵 `ds\\bin\\ds_shell.py` 也是按它算的)。
    这一层负责把它推成段① 要的那几个路径,**而三个"不许"必须机械地钉住**:
    不许放进安装根(会被覆盖)、不许放进数据根(会踩死线 t13)、不许和活树同名。
    """

    def test_t23a_install_root_is_the_parent_of_ds_root(self):
        paths = ds_update_apply.paths_for_update(
            os.path.join(self.base, "Programs", "OpenDesign", "ds"),
            data_root=self.data_root, temp_dir=self.temp)
        self.assertEqual(paths["live"],
                         os.path.join(self.base, "Programs", "OpenDesign"))

    def test_t23b_new_and_old_are_siblings_of_the_live_tree(self):
        paths = ds_update_apply.paths_for_update(
            os.path.join(self.live, "ds"), data_root=self.data_root,
            temp_dir=self.temp)
        for key in ("new", "old"):
            with self.subTest(key=key):
                self.assertEqual(os.path.dirname(paths[key]),
                                 os.path.dirname(paths["live"]),
                                 "%s 不是活树的同级" % key)
                self.assertNotEqual(paths[key], paths["live"])
                self.assertFalse(
                    paths[key].startswith(paths["live"] + os.sep),
                    "%s 放进了安装根里面 —— 安装器会把它一起覆盖掉" % key)

    def test_t23c_new_and_old_are_never_inside_the_data_root(self):
        paths = ds_update_apply.paths_for_update(
            os.path.join(self.live, "ds"), data_root=self.data_root,
            temp_dir=self.temp)
        root = os.path.normpath(self.data_root)
        for key in ("new", "old"):
            with self.subTest(key=key):
                self.assertFalse(
                    os.path.normpath(paths[key]).startswith(root + os.sep),
                    "%s 放进了数据根 —— 更新过程会往那儿写整整一棵树,死线 t13 当场破" % key)

    def test_t23d_the_data_root_is_the_one_holding_data_and_userdata(self):
        """数据根指的是**装着 `Data\\` 和 `UserData\\` 的那一层**,不是它们自己。

        差一层的后果不是报错,是死线判据比对了个空目录然后一路绿 ——
        本单已经吃过一次同款(那个探针路径传错、两遍都失败,diff 照报"无差异")。
        """
        paths = ds_update_apply.paths_for_update(
            os.path.join(self.live, "ds"), data_root=self.data_root,
            temp_dir=self.temp)
        for name in ds_update_apply.DATA_ROOT_PROTECTED_DIRS:
            self.assertTrue(os.path.isdir(os.path.join(paths["data_root"], name)),
                            "数据根底下没有 %s\\ —— 层数错了" % name)


class TheRelayApplyWritesIsFilledIn(_Base):
    """t25 —— `apply_update` **真正写到盘上的**那份接力脚本,必须带着真实的路径、端口、nonce、版本号。

    🔴 2026-09-14 Windows 端到端第一趟(run 34848924198)抓到的,构件 `relay-e3.cmd` 原文:

        set "LIVE="
        set "NEWT="
        set "OLDT="
        set "LOGF=\\Logs\\更新.log"
        set "NONCE="
        set "WANT="

    `t24` 修渲染器时给 `render_relay` 加了 `paths/port/nonce/expect_version` 四个参数,
    判据 `t24` 调它时**参数给全了**,而**生产调用点 `apply_update` 只传了 plan**。
    后果:收摊闸问的哨兵变成 `\\ds\\bin\\ds_shell.py`(永远"被占着")⇒ 等满超时 ⇒ 放弃;
    就算放行,`move "" ""` 也什么都换不了 —— **每一次点更新,软件都关掉、再也不回来**。
    本机 88 条全绿,因为没有一条判据读过 `apply_update` 写出来的那个文件。

    t24 那条教训("判据调用被测函数时参数给不全,测的是不存在的场景")的**反面**:
    生产调用点参数给不全,判据给全了,于是判据测的是一个生产里不存在的程序。
    ⇒ 这里只读**盘上那个文件**,不自己调渲染器。
    """

    PORT = 18777

    def _relay_text(self):
        self.paths["port"] = self.PORT
        r = self._apply(_decision())
        self.assertTrue(r["ok"], r.get("error"))
        with open(r["relay"], encoding="gbk") as fh:
            return fh.read()

    @staticmethod
    def _var(text, name):
        m = re.search(r'^set "%s=(.*)"\s*$' % name, text, re.M)
        return None if m is None else m.group(1)

    def test_t25a_tree_paths_are_the_real_ones(self):
        text = self._relay_text()
        for var, key in (("LIVE", "live"), ("NEWT", "new"), ("OLDT", "old")):
            with self.subTest(var=var):
                self.assertEqual(self._var(text, var), self.paths[key],
                                 "盘上接力脚本里的 %s 不是真路径" % var)

    def test_t25b_port_nonce_and_version_are_filled_in(self):
        text = self._relay_text()
        self.assertEqual(self._var(text, "PORT"), str(self.PORT))
        self.assertEqual(self._var(text, "WANT"), NEW_VERSION)
        self.assertRegex(self._var(text, "NONCE") or "", r"^[0-9a-f]{16,}$", "nonce 是空的 —— 收口认不出新版")

    def test_t25c_log_file_lives_under_the_real_data_root(self):
        logf = self._var(self._relay_text(), "LOGF") or ""
        self.assertTrue(logf.startswith(self.data_root), "更新日志写到了数据根外面:%r" % logf)


class TheRelaySurvivesTheShellTeardown(unittest.TestCase):
    """t27 —— 接力脚本必须**活过外壳收摊**:它不许留在 ds-web 那个 Job 里。

    🔴 2026-09-14 Windows 端到端第二趟(run 34851863087)坐实的:四个场景里接力脚本都在
    交棒后 **1 秒内**死掉;它的日志里每次只有第一行「接力开始」,而那一秒正是外壳日志里的
    「收摊:停两条腿」。机制(读 `ds_shell_core._assign_windows_job` 确认):
    外壳把 ds-web 放进一个 `KILL_ON_JOB_CLOSE` 的 Job,**Windows 上子进程自动进父进程的 Job**,
    接力脚本是 ds-web 起的 ⇒ 外壳收摊一关 Job,接力脚本跟着 ds-web 一起被收掉。
    ⇒ 修好 t25 之后,点更新仍然是"软件关了、再也不回来"。

    修法要同时守住两件事:
    - 接力脚本**这一个**进程要脱离 Job(Job 允许脱离 + 起它时明确要求脱离);
    - ds-web 起的**其他**子孙照旧跟着收 —— 不许用 SILENT_BREAKAWAY 让整棵树都溜出去
      (那正是 Job 存在的理由:外壳一退,后台腿的子孙不许留在业主机器上)。
    这里判的是两边的**标志**(Linux 上只判得了这个);真的活没活下来是 e1~e5 的事。
    """

    CREATE_BREAKAWAY_FROM_JOB = 0x01000000
    JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x00000800
    JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK = 0x00001000
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

    def test_t27a_job_allows_explicit_breakaway_but_still_kills_the_rest(self):
        import ds_shell_core
        flags = getattr(ds_shell_core, "JOB_LIMIT_FLAGS", 0)
        self.assertTrue(flags & self.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, "Job 不再收整棵树了")
        self.assertTrue(flags & self.JOB_OBJECT_LIMIT_BREAKAWAY_OK, "Job 不允许脱离 ⇒ 接力脚本脱不出去")
        self.assertFalse(flags & self.JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK,
                         "SILENT_BREAKAWAY 会让 ds-web 的所有子孙都溜出 Job")

    def test_t27b_the_job_is_created_with_those_flags(self):
        code = _code_without_comments(os.path.join(ROOT, "bin", "ds_shell_core.py"))
        self.assertRegex(code, r"LimitFlags\s*=\s*JOB_LIMIT_FLAGS\b",
                         "_assign_windows_job 没用 JOB_LIMIT_FLAGS(常量对了、建 Job 时没用上 = 白对)")

    def test_t27c_only_the_relay_asks_to_leave_the_job(self):
        import ds_shell_core
        leave = ds_shell_core.spawn_kwargs("nt", leave_job=True)["creationflags"]
        stay = ds_shell_core.spawn_kwargs("nt")["creationflags"]
        self.assertTrue(leave & self.CREATE_BREAKAWAY_FROM_JOB, "要求脱离的那一份没带 CREATE_BREAKAWAY_FROM_JOB")
        self.assertEqual(leave & ds_shell_core.WINDOWS_SPAWN_FLAGS, ds_shell_core.WINDOWS_SPAWN_FLAGS,
                         "脱离 Job 时把不冒黑窗口那几位弄丢了")
        self.assertFalse(stay & self.CREATE_BREAKAWAY_FROM_JOB, "默认也脱离了 ⇒ 后台腿的子孙收不掉")

    def test_t27d_handoff_requests_leaving_the_job(self):
        import ds_shell_core
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        relay = os.path.join(tmp, "opendesign-update-relay.cmd")
        _write(relay, b"@echo off\r\n")
        asked = []
        real = ds_shell_core.spawn_kwargs

        def recorder(*args, **kwargs):
            asked.append(kwargs)
            return real(*args, **kwargs)

        ds_shell_core.spawn_kwargs = recorder
        try:
            ok = ds_update_apply.handoff(relay, launcher=lambda argv, **kw: object())
        finally:
            ds_shell_core.spawn_kwargs = real
        self.assertTrue(ok)
        self.assertTrue(any(k.get("leave_job") is True for k in asked),
                        "handoff 起接力脚本时没要求脱离 Job ⇒ 外壳一收摊它就被一起收掉")


class TheRelayWaitsForTheTreeAndAlwaysComesBack(unittest.TestCase):
    """t28 —— 接力脚本**等活树真的空出来**再改名;放弃或回滚时**把软件带回来**、而且不把旧树塞进新树。

    🔴 2026-09-14 Windows 端到端第三趟(run 34855947275)坐实的:t27 修好后接力脚本活下来了,
    e1/e4/e5 却都是「接力开始 14:47:25.66 → 第一次改名就失败 14:47:25.70」—— **40 毫秒**。
    收摊闸问的是「端口空了没 + `ds_shell.py` 有没有被锁」,而 python 跑起来后**并不锁着 .py**,
    ds-web 一被收掉端口就空 ⇒ 闸立刻放行,而外壳的 `pythonw.exe` 还没退完、攥着活树 ⇒ 改名失败 ⇒
    `.new` 删掉、退出 —— **没人把软件打开,业主看到的是"关了、没回来"**。

    同一类问题读代码还能推出两处(同一个事实:Windows 上文件夹里有程序在跑,文件夹就改不了名):
    - 回滚时新版要是已经起来了,它攥着活树 ⇒ `move 活树 .new` 失败 ⇒
      下一句 `move .old 活树` 在活树还在时会把旧树**塞进**活树里(e5 要测的那个)。
    - 放弃的两条路(收摊不干净 / 改名一直失败)都不重新打开旧版。

    这里判生成物的结构(Linux 上只判得了这个);真行为是 e1/e3/e4/e5。
    """

    PATHS = TheRelayIsARealProgram.PATHS

    def _lines(self):
        plan = ds_update_apply.relay_plan(self.PATHS, port=8766, nonce="n1", expect_version="0.98.5")
        text = ds_update_apply.render_relay(plan, paths=self.PATHS, port=8766, nonce="n1",
                                            expect_version="0.98.5")
        # 注释行一律不算数:`rem goto :x` / `:: if ... GEQ ...` 什么都挡不住,却能骗过按文本找的断言。
        return [ln.strip() for ln in text.splitlines()
                if not ln.strip().startswith("::") and not ln.strip().lower().startswith("rem ")]

    def _section(self, label):
        """从标签定义那一行到它后面第一句 `exit /b`(含)。"""
        lines = self._lines()
        at = next((i for i, l in enumerate(lines) if l.lower() == ":" + label), None)
        self.assertIsNotNone(at, "脚本里没有 :%s 这一段" % label)
        end = next(i for i in range(at, len(lines)) if lines[i].lower().startswith("exit /b"))
        return lines[at:end + 1]

    def test_t28a_first_rename_is_retried_with_a_bound(self):
        lines = self._lines()
        mv = next(i for i, l in enumerate(lines) if l.startswith('move /Y "%LIVE%" "%OLDT%"'))
        label = lines[mv - 1]
        self.assertTrue(label.startswith(":") and not label.startswith("::"),
                        "第一次改名前面没有重试用的标签 ⇒ 只试一次(实测 40 毫秒就放弃)")
        after = lines[mv + 1:mv + 8]
        self.assertTrue(any(l.lower() == "goto " + label.lower() for l in after),
                        "改名失败后没有跳回去重试")
        self.assertTrue(any("geq" in l.lower() and "rename_failed" in l.lower() for l in after),
                        "重试没有上限 ⇒ 活树永远被占着时脚本永远不结束")

    def test_t28b_give_up_paths_bring_the_old_app_back(self):
        for label in ("teardown_failed", "rename_failed"):
            with self.subTest(label=label):
                sec = self._section(label)
                self.assertTrue(any(l.lower().startswith('start "" "%live%\\opendesign.exe"') for l in sec),
                                "%s 放弃之后没有把旧版打开 ⇒ 业主看到的是关了、没回来" % label)

    def test_t28c_rollback_stops_what_runs_from_the_live_tree_before_moving_it(self):
        sec = self._section("rollback")
        first_move = next((i for i, l in enumerate(sec) if "move" in l.lower() and "%live%" in l.lower()), None)
        self.assertIsNotNone(first_move, "回滚段里没有把活树挪走的那一步")
        stop = [i for i, l in enumerate(sec)
                if "%live%" in l.lower() and ("stop-process" in l.lower() or "taskkill" in l.lower())]
        self.assertTrue(stop and stop[0] < first_move,
                        "回滚挪活树之前没先停掉从活树里跑着的程序 ⇒ 新版起来了就挪不动")

    def test_t28d_rollback_never_moves_old_into_an_existing_live_tree(self):
        sec = self._section("rollback")
        put_back = next((i for i, l in enumerate(sec) if "%oldt%" in l.lower() and "%live%" in l.lower()
                         and ("move" in l.lower())), None)
        self.assertIsNotNone(put_back, "回滚段里没有把 .old 换回来的那一步")
        guard = [l.lower() for l in sec[:put_back] if l.lower().startswith('if exist "%live%"') and "goto" in l.lower()]
        self.assertTrue(guard, "活树还在时照样 move .old 活树 ⇒ 旧树被塞进活树里(e5 要测的那个)")


class TheRelayDoesNotStandInsideTheTreeItRenames(unittest.TestCase):
    """t29 —— 接力脚本的**当前目录**不许在活树里。

    🔴 2026-09-14 Windows 端到端第四趟(run 34860373658)坐实的:e1/e4/e5 的接力脚本日志全是
    「活树一直被占着改不了名,放弃更新」—— 重试满 60 秒,活树始终改不了名。
    占着它的就是接力脚本自己:`installer/launcher.nsi` 的 `SetOutPath "$EXEDIR"` 把工作目录设成活树,
    外壳 → ds-web → 接力脚本一路继承。**Windows 上一个进程的当前目录在哪个文件夹里,那个文件夹就改不了名。**

    两道都要:起它的时候给 `cwd`(它所在的 %TEMP%),脚本第一件事也 `cd /d` 出去 ——
    后者防的是将来有人换了起它的方式、又把 cwd 弄丢。
    """

    PATHS = TheRelayIsARealProgram.PATHS

    def test_t29a_handoff_launches_the_relay_from_its_own_folder(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        relay = os.path.join(tmp, "opendesign-update-relay.cmd")
        _write(relay, b"@echo off\r\n")
        seen = []
        ok = ds_update_apply.handoff(relay, launcher=lambda argv, **kw: seen.append(kw) or object())
        self.assertTrue(ok)
        self.assertEqual(os.path.normpath(seen[0].get("cwd") or ""), os.path.normpath(tmp),
                         "接力脚本没指定当前目录 ⇒ 继承 ds-web 的(活树里),自己把活树占住")

    def test_t29b_the_script_leaves_the_tree_before_anything_else(self):
        plan = ds_update_apply.relay_plan(self.PATHS, port=8766, nonce="n1", expect_version="0.98.5")
        text = ds_update_apply.render_relay(plan, paths=self.PATHS, port=8766, nonce="n1",
                                            expect_version="0.98.5")
        lines = [l.strip() for l in text.splitlines()
                 if l.strip() and not l.strip().startswith("::") and not l.strip().lower().startswith("rem ")]
        gate = next(i for i, l in enumerate(lines) if l.lower() == "call :wait_gone")
        cds = [i for i, l in enumerate(lines[:gate]) if l.lower().startswith("cd /d ")]
        self.assertTrue(cds, "收摊闸之前没有 cd /d 离开当前目录")
        target = lines[cds[0]][len("cd /d "):].strip().strip('"').lower()
        self.assertFalse("%live%" in target or "%newt%" in target or "%oldt%" in target,
                         "cd 进了要改名的树里:%s" % lines[cds[0]])


class TheDownloadGoesThroughTheSystemProxy(unittest.TestCase):
    """t30 —— **下载安装包要走系统代理**;只有问本机 127.0.0.1 的 health 才绕开代理(t18)。

    🔴 2026-09-15 收口前主 agent 自审读出来的,Windows CI **结构上照不出**(runner 上没有代理):
    `_default_download` 复用了 `build_opener()` —— 那是给 t18 问本机 health 用的、专门绕开代理的 opener。
    而查更新(`ds_update.fetch_releases`)走的是默认 urllib,认系统代理。
    ⇒ 业主开着 VPN(系统代理)时:**查更新说有新版,点下去下载却直接去连 github.com**,
    在他的网络里很可能下不动 —— 功能对他整个不可用,而 CI 六趟全绿。

    判法:本机起一个假代理(只认 CONNECT、一律回 502),环境变量指向它;
    同时把 DNS 解析换成"非本机一律拒绝"——**判据自己不许有外网出口**,绕开代理的实现也出不去,只会被记下来。
    """

    def test_t30a_download_asks_the_proxy_not_the_internet(self):
        import socket
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from unittest import mock

        seen = []

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
        direct = []
        real_gai = socket.getaddrinfo

        def local_only(host, *args, **kwargs):
            if host not in ("127.0.0.1", "localhost"):
                direct.append(host)
                raise OSError("判据不许有外网出口:%s" % host)
            return real_gai(host, *args, **kwargs)

        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        env = {"https_proxy": proxy, "HTTPS_PROXY": proxy, "http_proxy": proxy, "HTTP_PROXY": proxy,
               "no_proxy": "", "NO_PROXY": ""}
        url = "https://github.com/SunJ1ayu/OpenDesign/releases/download/win-installer-9.9.9/OpenDesign-Setup-9.9.9.exe"
        with mock.patch.dict(os.environ, env), mock.patch("socket.getaddrinfo", local_only):
            with self.assertRaises(Exception):   # 假代理回 502,下载必然失败 —— 要问的是它去了哪
                ds_update_apply._default_download(url, os.path.join(tmp, "x.exe"))
        self.assertEqual(direct, [], "下载绕开了系统代理、直接去连 %s(开 VPN 的业主下不动)" % direct)
        self.assertTrue(any(p.startswith("github.com:443") for p in seen), "代理没收到下载请求:%r" % seen)


class AStaleOldTreeIsClearedFirst(_Base):
    """t32 —— 开始更新前,上次留下的 `.old` 必须先清掉;清不掉就不开始。

    🔴 2026-09-15 收口前自审读出来的:接力脚本第一次改名是 `move 活树 .old`,
    **目标已经存在时 move 会把活树挪进 .old 里面**。上一次更新成功后的清理 `rmdir .old` 没删干净
    (比如某个晚退的进程还攥着里面的文件)就会留下它 —— 下一次更新一旦走到回滚,
    `move .old 活树` 换回来的是**那棵残缺的旧 .old,真正的活树被塞在它里面** ⇒ 软件打不开。
    活树在(我们正从它里面跑着)时,.old 一定是过期的,可以放心删。
    """

    def test_t32a_stale_old_is_removed_and_the_update_proceeds(self):
        _write(os.path.join(self.paths["old"], "ds", "bin", "leftover.py"), b"# from last time\n")
        r = self._apply(_decision())
        self.assertTrue(r["ok"], r.get("error"))
        self.assertFalse(os.path.exists(self.paths["old"]), "上次留下的 .old 还在 ⇒ 第一次改名会把活树塞进去")
        self.assertLiveUntouched("清 .old 时")

    def test_t32b_an_old_that_cannot_be_removed_stops_before_downloading(self):
        _write(self.paths["old"], b"not a directory, rmtree cannot take it")   # 删不掉的形状
        r = self._apply(_decision())
        self.assertFalse(r["ok"])
        self.assertEqual(r["stage"], "stale_old")
        self.assertEqual(self.downloads, [], ".old 清不掉还去下载 43MB")
        self.assertIsNone(r.get("relay"))
        self.assertLiveUntouched(".old 清不掉时")


class UpdateModeDoesNotRepointTheInstall(unittest.TestCase):
    """t26 —— 更新档(`/UPDATE`,装进 `OpenDesign.new`)**不许**把注册表和快捷方式指到 `$INSTDIR`。

    🔴 2026-09-14 Windows 端到端第一趟(run 34848924198)照出来的:e3 之后重装旧版,安装器报 rc=0,
    而默认位置上没有 `OpenDesign.exe` —— `InstallDirRegKey` 读到的"上次装在哪"已经被更新档写成了
    `...\\OpenDesign.new`。读 `.nsi` 确认:更新档装进 `.new` 时,`InstallDir`、卸载条目
    (`InstallLocation`/`UninstallString`/`DisplayIcon`)、开始菜单和桌面快捷方式**全部照写 `$INSTDIR`**。

    两次改名之后 `.new` 这个路径就不存在了 ⇒ **每次更新成功,业主的桌面图标、开始菜单、
    "设置 → 应用"里的卸载都指向一个不存在的文件夹**;下次手动装新版也会装进 `.new`。

    正确的指向本来就是活树那个路径,而改名之后活树还叫那个名字 ⇒ 更新档**什么都不用重写**。
    查结构(同 t20c):每一行"把 `$INSTDIR` 写进注册表/快捷方式"的语句,上方最近的块守卫必须是更新档。
    行为半在 Windows 端到端(e1~e5 的 pointers 事实)。
    """

    POINTER_OPS = ("WriteRegStr", "WriteRegExpandStr", "CreateShortcut")
    NSI = InstallerUpdateFlagContract.NSI   # 不继承那个类:继承会把 t20 的判据再跑一遍

    def _nsi(self):
        with open(self.NSI, encoding="utf-8", errors="replace") as fh:
            return fh.read()

    def _pointer_lines(self):
        lines = self._nsi().splitlines()
        return lines, [i for i, ln in enumerate(lines)
                       if not ln.strip().startswith(";")
                       and ln.strip().startswith(self.POINTER_OPS)
                       and "$INSTDIR" in ln]

    def test_t26a_there_are_pointer_writes_to_check(self):
        _lines, at = self._pointer_lines()
        self.assertGreaterEqual(len(at), 6, "一条都找不到了 —— 这条闸在查空气")

    def test_t26b_every_instdir_pointer_is_guarded_by_update_mode(self):
        lines, at = self._pointer_lines()
        for i in at:
            with self.subTest(line=i + 1, text=lines[i].strip()):
                guard = None
                for j in range(i - 1, -1, -1):
                    s = lines[j].strip()
                    if s.startswith(("${EndIf}", "Section", "SectionEnd", "Function", "FunctionEnd")):
                        break
                    if s.startswith(("${If}", "${Unless}", "${IfNot}")):
                        guard = s
                        break
                self.assertIsNotNone(guard, "更新档也会执行这一行,改名后它指向不存在的 .new")
                self.assertIn(ds_update_apply.UPDATE_MODE_VAR, guard, "把守它的不是更新档:%s" % guard)


class TheInstallerReadsTheDirectoryWeMeant(unittest.TestCase):
    """t33 —— 安装器**真正读到的**目录必须逐字是 `.new`,路径带空格也一样。

    🔴 2026-09-15 收口外审两条腿(DeepSeek 发现 1、GLM 发现 1)各自独立指出;我读 NSIS 源码坐实了更坏的那一支:
    `[setup, "/S", "/UPDATE", "/D=" + 目标]` 交给 subprocess ⇒ list2cmdline 给带空格的 `/D=` 加引号
    ⇒ NSIS 不认这个 `/D=` ⇒ 安装目录退回 `InstallDirRegKey`(= **正在运行的活树**)
    ⇒ 静默装进活树:被占着的文件跳过、其余覆盖 ⇒ 半新半旧,下次打不开。
    CI runner 是 `runneradmin`(无空格),`windows-nonempty-probe.ps1` 走的是不加引号那条 —— 这支从没被量过。
    """

    CASES = (
        # (安装包在哪, 装到哪)
        (r"C:\Users\runneradmin\AppData\Local\Temp\OpenDesign-Setup-0.98.5.exe",
         r"C:\Users\runneradmin\AppData\Local\Programs\OpenDesign.new"),
        (r"C:\Users\John Smith\AppData\Local\Temp\OpenDesign-Setup-0.98.5.exe",
         r"C:\Users\John Smith\AppData\Local\Programs\OpenDesign.new"),
        (r"C:\Users\ZHANGS~1\AppData\Local\Temp\OpenDesign-Setup-0.98.5.exe",
         r"D:\Program Files (x86)\设计 工具\OpenDesign.new"),
    )

    def test_t33a_nsis_reads_exactly_the_new_dir(self):
        for setup, target in self.CASES:
            with self.subTest(target=target):
                cmdline = _installer_cmdline(setup, target)
                got = _nsis_reads(cmdline)
                self.assertEqual(got["instdir"], target,
                                 "NSIS 从这条命令行读出的安装目录不是 .new:%r\n命令行:%s" % (got["instdir"], cmdline))
                self.assertTrue(got["silent"], "NSIS 没认出 /S:%s" % cmdline)

    def test_t33z_the_reference_parser_follows_the_documented_nsis_rule(self):
        """参照模型自检 —— 防止照搬错了、错成对实现有利的样子。

        NSIS 文档(Installer Usage):`/D` "must be the last parameter used in the command line and
        must not contain any quotes, even if the path contains spaces"。
        """
        self.assertIsNone(
            _nsis_reads(r'"C:\x y\Setup.exe" /S /UPDATE "/D=C:\Users\John Smith\OpenDesign.new"')["instdir"],
            "参照模型居然认了带引号的 /D= —— 和 NSIS 文档相反")
        self.assertEqual(
            _nsis_reads(r'"C:\x y\Setup.exe" /S /UPDATE /D=C:\Users\John Smith\OpenDesign.new')["instdir"],
            r"C:\Users\John Smith\OpenDesign.new")
        self.assertEqual(_nsis_reads(r"C:\x\Setup.exe /S /D=C:\a")["instdir"], r"C:\a")
        self.assertTrue(_nsis_reads(r"C:\x\Setup.exe /S /D=C:\a")["silent"])
        self.assertFalse(_nsis_reads(r"C:\x\Setup.exe /SILENT /D=C:\a")["silent"])


class TheUpdateModeOnlyInstallsIntoNew(unittest.TestCase):
    """t34 —— 更新档**只许装进 `.new`**:`.onInit` 里认出更新档、`$INSTDIR` 又不以 `.new` 结尾 ⇒ `Abort`。

    t33 管"python 发对";这条是纵深:哪天 `/D=` 又因为别的原因没被认出来,
    塌成"安装器 rc≠0、更新失败、活树没动",而不是"装进活树"。行为半 = Windows `e6`(真 NSIS)。
    """

    NSI = os.path.join(ROOT, "installer", "OpenDesign.nsi")

    def _oninit(self):
        with open(self.NSI, encoding="utf-8", errors="replace") as fh:
            lines = [ln.strip() for ln in fh.read().splitlines()]
        start = lines.index("Function .onInit")
        end = lines.index("FunctionEnd", start)
        return [ln for ln in lines[start + 1:end] if ln and not ln.startswith(";")]

    def test_t34a_update_mode_aborts_unless_instdir_ends_with_new(self):
        body = self._oninit()
        suffix = [m.group(1) for m in
                  (re.match(r'StrCpy\s+(\$\w+)\s+"?\$INSTDIR"?\s+""\s+-4$', ln) for ln in body) if m]
        self.assertTrue(suffix, ".onInit 里没有取 $INSTDIR 末 4 个字符的那一行")
        var = suffix[0]
        flag_at = next((i for i, ln in enumerate(body)
                        if "GetOptions" in ln and ds_update_apply.INSTALL_UPDATE_FLAG in ln), None)
        self.assertIsNotNone(flag_at, ".onInit 不解析更新档旗子了")

        # 逐行走块结构:记下每个 Abort 被哪些 ${If} 包着(${AndIf}/${OrIf} 并进当前块的条件)
        stack, aborts = [], []
        for i, ln in enumerate(body):
            if ln.startswith(("${If}", "${IfNot}", "${Unless}")):
                stack.append([i, ln])
            elif ln.startswith(("${AndIf}", "${AndIfNot}")) and stack:
                stack[-1][1] += " " + ln
            elif ln.startswith(("${Else}", "${ElseIf}", "${OrIf}")) and stack:
                stack[-1][1] += " <ELSE-OR> "     # 分支变了:之后的 Abort 不再受原条件保护
            elif ln.startswith("${EndIf}") and stack:
                stack.pop()
            elif ln == "Abort" or ln.startswith("Abort "):
                aborts.append((i, [cond for _at, cond in stack]))
        good = [i for i, conds in aborts
                if any(ds_update_apply.UPDATE_MODE_VAR in c.split("<ELSE-OR>")[0] for c in conds)
                and any(var in c.split("<ELSE-OR>")[0] and '".new"' in c.split("<ELSE-OR>")[0] and "!=" in c
                        for c in conds)
                and i > flag_at]
        self.assertTrue(good, "没有一个 Abort 同时被「更新档」和「%s != \".new\"」把守着:%r" % (var, aborts))


class RelayUnsafePathsStopBeforeAnything(_Base):
    """t36 —— 接力脚本扛不住的路径:**在清 .old / 下载 / 安装之前**就拒绝(`stage=path_unsupported`)。

    🔴 2026-09-15 收口外审(GLM 发现 2/4、DeepSeek 发现 2)+ 我重读自审第 1 条时的更正:
    `.cmd` 以 GBK 写、按控制台代码页读;路径一乱,连"放弃并打开旧版"那句 `start "%LIVE%\\..."` 也打不开
    ⇒ 不是"安全失败",是**关了不回来**。`%` 被 cmd 展开;`'` 拆坏回滚那行 PowerShell 单引号串
    (停不掉新版 ⇒ 挪不动 ⇒ 卡死);`^` 被 `call :move_retry "..."` 翻倍(回滚专用子程序)。
    """

    def _paths_under(self, dirname, temp=None, data_root=None):
        live = _make_live_tree(os.path.join(self.base, dirname))
        paths = {"live": live, "new": live + ".new", "old": live + ".old",
                 "data_root": data_root or self.data_root, "temp": temp or self.temp}
        for p in (paths["temp"], paths["data_root"]):
            os.makedirs(p, exist_ok=True)
        os.makedirs(paths["old"])     # 一棵过期 .old:拒绝必须早于 t32 的清理
        return paths

    def _apply_at(self, paths, oem_cp):
        # 控制台代码页和 port/nonce 一样经 paths 注入(生产里不给 = 问 Windows GetOEMCP)
        return ds_update_apply.apply_update(
            _decision(), dict(paths, oem_cp=oem_cp), download=self._download(_installer_bytes()),
            install=self._install())

    def test_t36a_unsafe_paths_are_refused_before_any_side_effect(self):
        cases = (
            ("O'Brien", {}, 936),
            ("100%off", {}, 936),
            ("a^b", {}, 936),
            ("Kullanıcı şahin", {}, 936),                     # GBK 写不进
            ("张 三", {}, 437),                                 # 英文系统控制台读 GBK 字节 = 乱码
            ("李 四", {}, 65001),                               # 中文系统开了"UTF-8 全球语言支持"
            ("plain", {"temp": os.path.join(self.base, "T%M%P")}, 936),        # 接力脚本自己住的地方
            ("plain2", {"data_root": os.path.join(self.base, "Dâtä€")}, 936),  # LOGF 在数据根底下
        )
        for dirname, extra, cp in cases:
            with self.subTest(dir=dirname, extra=extra, oem_cp=cp):
                self.downloads.clear()
                self.installs.clear()
                paths = self._paths_under(dirname, **extra)
                live_before = _tree_digest(paths["live"])
                result = self._apply_at(paths, cp)
                self.assertFalse(result.get("ok"))
                self.assertEqual(result.get("stage"), "path_unsupported", "%r" % (result,))
                self.assertEqual(self.downloads, [], "拒绝之前已经开始下载了")
                self.assertEqual(self.installs, [], "拒绝之前已经装了")
                self.assertTrue(os.path.isdir(paths["old"]), "拒绝之前已经动手清了 .old")
                self.assertFalse(os.path.exists(paths["new"]))
                self.assertEqual(_tree_digest(paths["live"]), live_before)

    def test_t36b_ordinary_paths_still_update(self):
        """反面(防修过头):空格、括号、中文(控制台 936)、纯 ASCII(英文系统)都得照常走到写出接力脚本。
        业主自己就是中文 Windows —— 修成"中文路径一律不更新"等于把这功能对他关掉。"""
        for dirname, cp in (("Program Files (x86)", 936), ("设计 工具", 936),
                            ("John Smith", 437), ("John Smith & Co", 65001)):
            with self.subTest(dir=dirname, oem_cp=cp):
                paths = self._paths_under(dirname)
                result = self._apply_at(paths, cp)
                self.assertTrue(result.get("ok"), "%r" % (result,))
                self.assertEqual(result.get("stage"), "relay")


if __name__ == "__main__":
    unittest.main()
