#!/usr/bin/env python3
"""换壳后的配置不变量与跨文件对表(track opendesign-electron-shell,T3;主 agent 亲写,判据先单独 commit)。

这些值错了**都不报错**,只会在业主那边安静地变坏 —— 而且多半要到下一次发版才暴露:
  · publish 地址写错 / 用了 github provider ⇒ 走 api.github.com,VPN 出口 60 次/小时限流那个坑重踩(表 #2);
  · `useMultipleRangeRequest` 没关 ⇒ GitHub 多段请求 501 ⇒ 每次更新整包 158MB(探路第二跑亲测);
  · 装机页面多了/少了 ⇒ 不再是业主选的 C(照 ZCode,U3/U4);
  · 版本号两处各写各的 ⇒ exe 0.98.11 而后台报 0.98.9(探路第二跑真出过);
  · 新发布的名字被旧更新器认出来 ⇒ 没手动装的那台被旧更新器拿去当旧格式装(表 #6)。
每条都能追到 design.md 的一条决定;改这里的值要先改 design、写理由。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = ROOT / "desktop"
PKG = DESKTOP / "package.json"
NSH = DESKTOP / "build" / "installer.nsh"
PRELOAD = DESKTOP / "preload.js"
FEED = "https://github.com/SunJ1ayu/OpenDesign/releases/latest/download"
TS_SEPS = ",;\n"


def _pkg() -> dict:
    return json.loads(PKG.read_text(encoding="utf-8"))


def _code_only(src: str) -> str:
    """剥掉 JS/TS 注释 —— 注释里讲历史(pywebview、/api/update)是应该的,问的是代码还用不用。"""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(re.sub(r"(^|[^:])//.*$", r"\1", line) for line in src.splitlines())


def _nsis_code_only(src: str) -> str:
    return "\n".join(line.split(";")[0].split("#")[0] for line in src.splitlines())


def _balanced(src: str, start: int) -> str:
    """从 src[start] 那个 `{` 起,数深度取到配对的 `}`(跳过字符串)。别用正则找边界 —— 本仓栽过四次。"""
    assert src[start] == "{", src[start:start + 20]
    depth, quote, i = 0, "", start
    while i < len(src):
        c = src[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = ""
        elif c in "\"'`":
            quote = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    raise AssertionError("没找到配对的 } —— 这道闸问不出东西")


def _top_keys(obj_src: str, seps: str = ",") -> set[str]:
    """对象字面量 / 类型体第一层的键名。JS 对象只认 `,` 分隔;TS 类型体再加 `;` 与换行。
    认三种写法:`a: …`、`a(…)…`(方法)、`a,`(简写)。深度 > 0 的一律不看。"""
    body = obj_src[1:-1]
    keys, depth, quote, token = set(), 0, "", ""
    head = re.compile(r"^\s*(?:readonly\s+)?([A-Za-z_$][\w$]*)\s*\??\s*[:(]$")
    bare = re.compile(r"^\s*([A-Za-z_$][\w$]*)\s*$")
    i = 0
    while i < len(body):
        c = body[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = ""
        elif c in "\"'`":
            quote = c
        elif c in "{([":
            if depth == 0:
                token += c
                m = head.match(token)
                if m:
                    keys.add(m.group(1))
            depth += 1
            i += 1
            continue
        elif c in "})]":
            depth -= 1
        elif depth == 0 and c in seps:
            m = bare.match(token)
            if m:
                keys.add(m.group(1))
            token = ""
            i += 1
            continue
        if depth == 0:
            token += c
            m = head.match(token)
            if m:
                keys.add(m.group(1))
        i += 1
    m = bare.match(token)
    if m:
        keys.add(m.group(1))
    return keys


def _hits(text: str, pattern: str) -> list[str]:
    """命中的行(带行号)。**别用 assertNotIn / assertNotRegex 对整份文件** —— 红的时候它们把
    三千行的 ds_web.py 整个印出来,真正该看的那一行淹在里面。"""
    rx = re.compile(pattern)
    return [f"{i}: {line.strip()[:160]}" for i, line in enumerate(text.splitlines(), 1) if rx.search(line)]


class C1Installer(unittest.TestCase):
    def test_c1_nsis_is_the_zcode_wizard_in_chinese_that_keeps_the_data(self):
        nsis = _pkg()["build"]["nsis"]
        self.assertIs(nsis.get("oneClick"), False, "U3 = 照 ZCode:向导模式")
        self.assertIs(nsis.get("perMachine"), False, "旧版一直装在当前用户下(HKCU);所有用户要管理员")
        self.assertIs(nsis.get("allowToChangeInstallationDirectory"), True, "业主装在自选的 D:/F: 目录")
        self.assertEqual(nsis.get("installerLanguages"), ["zh_CN"], "只一种语言 ⇒ 不弹语言选择页")
        self.assertIs(nsis.get("deleteAppDataOnUninstall"), False, "卸载不许碰资料根")
        self.assertEqual(nsis.get("artifactName"), "OpenDesign-${version}-electron-setup.${ext}")
        self.assertEqual(nsis.get("include"), "build/installer.nsh")

    def test_c2_no_skipped_pages_we_decided_to_keep(self):
        """U3「c吧」+ U4「留着和zcode一样」⇒ 「为哪位用户」页与「完成」页都照 ZCode 留着。
        第四跑那两个零点击钩子(customInstallMode / customFinishPage)已撤回,不许悄悄加回来。"""
        code = _nsis_code_only(NSH.read_text(encoding="utf-8"))
        for macro in ("customInstallMode", "customFinishPage"):
            self.assertEqual(_hits(code, rf"!macro\s+{macro}\b"), [], f"{macro} 回来了 ⇒ 不再是业主选的 C/U4")

    def test_c2c_every_messagebox_answers_itself_in_silent_mode(self):
        """旧判据 installer_silent s2 搬过来:没有 `/SD` 的 MessageBox 在静默装/卸时就停在那儿等人
        (云 Windows 判据的收尾、将来任何 /S 调用都会卡死)。有框才查,没有框不算红。"""
        code = _nsis_code_only(NSH.read_text(encoding="utf-8"))
        boxes = _hits(code, r"\bMessageBox\b")
        bare = [b for b in boxes if "/SD" not in b]
        self.assertEqual(bare, [], "这些框静默模式下会一直等人点")

    def test_c2b_old_install_dir_is_where_we_install_and_where_we_clean(self):
        """旧版记目录的键(旧 OpenDesign.nsi 的 InstallDirRegKey)必须被读:
        选目录页默认值(E3 guidir)与「旧版在哪就去哪收」都靠它。行为在云 Windows E3/E3b 验。"""
        code = _nsis_code_only(NSH.read_text(encoding="utf-8"))
        # 探路版写的是 `ReadRegStr $0 HKCU "${OD_OLD_KEY}" "InstallDir"` ⇒ 先把 !define 展开再认
        for name, val in re.findall(r'!define\s+(\w+)\s+"([^"]*)"', code):
            code = code.replace("${" + name + "}", val)
        self.assertTrue(_hits(code, r'ReadRegStr\s+\S+\s+HKCU\s+"?Software\\OpenDesign"?\s+"?InstallDir'),
                        "安装包没读旧版记目录的键 ⇒ 选目录页默认值与「旧版在哪就去哪收」都没了依据")


class C3Publish(unittest.TestCase):
    def test_c3_feed_is_github_download_urls_not_the_api(self):
        pub = _pkg()["build"]["publish"]
        pub = pub if isinstance(pub, list) else [pub]
        self.assertEqual(len(pub), 1, f"只许一个更新源:{pub}")
        p = pub[0]
        self.assertEqual(p.get("provider"), "generic", "github provider 走 api.github.com(限流坑,表 #2)")
        self.assertEqual(p.get("url", "").rstrip("/"), FEED)
        self.assertIs(p.get("useMultipleRangeRequest"), False, "GitHub 多段 Range 回 501 ⇒ 退整包(第二跑)")

    def test_c3b_no_other_update_source_hides_in_the_repo(self):
        for f in list(DESKTOP.glob("*.js")) + list((DESKTOP / "lib").glob("*.js")):
            code = _code_only(f.read_text(encoding="utf-8"))
            self.assertEqual(_hits(code, r"api\.github\.com"), [], f"{f.name} 直连 api.github.com")
            self.assertEqual(_hits(code, r"setFeedURL\s*\("), [], f"{f.name} 在运行时换更新源 ⇒ 构建期那份 publish 形同虚设")


class C4Version(unittest.TestCase):
    def test_c4_one_version_everywhere(self):
        """版本号唯一来源:`bin/ds_web.py` VERSION(挑战 a4)。安装包文件名、「应用和功能」、
        electron-updater 比较的都是 package.json 的 version ⇒ 两处必须同值。"""
        web = re.search(r'(?m)^VERSION = "([^"]+)"', (ROOT / "bin" / "ds_web.py").read_text(encoding="utf-8")).group(1)
        self.assertEqual(_pkg().get("version"), web, "package.json 与 ds_web.VERSION 分叉 ⇒ 版本自检每次开机都弹框")


class C5OldUpdaterBlind(unittest.TestCase):
    def test_c5_released_updater_cannot_see_the_electron_release(self):
        """表 #6:没手动装的那台上跑着 0.98.8 的旧更新器;它要是认出新 release,会拿旧格式去装(接力换名)。
        正则取**已发布的那份代码**(git tag),不取工作树 —— 工作树那份要退役。"""
        src = subprocess.run(["git", "-C", str(ROOT), "show", "win-installer-0.98.8:bin/ds_update.py"],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(src.returncode, 0, f"读不到已发布的旧更新器:{src.stderr}")
        ns: dict = {}
        head = src.stdout.split("\ndef ", 1)[0]
        exec(compile(head, "ds_update@0.98.8", "exec"), ns)      # 只执行模块头:常量与正则
        ver = _pkg()["version"]
        asset = _pkg()["build"]["nsis"]["artifactName"].replace("${version}", ver).replace("${ext}", "exe")
        self.assertIsNone(ns["ASSET_RE"].match(asset), f"旧更新器认得出 {asset}")
        self.assertIsNone(ns["TAG_RE"].match(f"v{ver}"), f"旧更新器认得出 tag v{ver}")


class C6Contract(unittest.TestCase):
    """preload ↔ 前端 ↔ 主进程三方对表(旧判据 x2「按下去的名字对面接不接得住」的 Electron 版)。"""

    @classmethod
    def setUpClass(cls):
        cls.preload = _code_only(PRELOAD.read_text(encoding="utf-8"))
        m = re.search(r'exposeInMainWorld\(\s*["\']odShell["\']\s*,\s*', cls.preload)
        assert m, "preload 没有把 odShell 暴露给页面"
        cls.exposed = _balanced(cls.preload, m.end())
        ts = _code_only((ROOT / "web" / "src" / "desktopShell.ts").read_text(encoding="utf-8"))
        m = re.search(r"export\s+(?:interface|type)\s+OdShell\s*=?\s*", ts)
        assert m, "web/src/desktopShell.ts 里没有 OdShell 类型"
        cls.declared = _balanced(ts, m.end())

    def test_c6_page_and_preload_agree_on_every_name(self):
        exposed, declared = _top_keys(self.exposed), _top_keys(self.declared, TS_SEPS)
        self.assertTrue({"minimize", "toggleMaximize", "close", "windowState", "onWindowState",
                         "reportStartup", "update"} <= declared, f"前端类型少了 design B 列的方法:{declared}")
        self.assertEqual(declared - exposed, set(), "前端以为有、preload 没给 ⇒ 按下去 undefined is not a function")
        self.assertEqual(exposed - declared, set(), "preload 给了、前端不认 ⇒ 死代码或名字拼错")

    def test_c6b_update_sub_api_agrees_too(self):
        def sub(src, seps):
            m = re.search(r"\bupdate\s*:\s*", src)
            self.assertIsNotNone(m, "没有 update 子对象")
            return _top_keys(_balanced(src, m.end()), seps)
        self.assertEqual(sub(self.declared, TS_SEPS), sub(self.exposed, ","))
        self.assertTrue({"check", "install", "state", "onState"} <= sub(self.declared, TS_SEPS))

    def test_c6c_every_preload_channel_has_a_main_side(self):
        chans = set(re.findall(r'ipcRenderer\.(?:invoke|send|on)\(\s*["\']([^"\']+)["\']', self.preload))
        self.assertTrue(chans, "preload 一个通道都没有")
        main_side = "\n".join(_code_only(f.read_text(encoding="utf-8"))
                              for f in list(DESKTOP.glob("*.js")) + list((DESKTOP / "lib").glob("*.js"))
                              if f.name != "preload.js")
        for ch in chans:
            self.assertTrue(_hits(main_side, rf'(ipcMain\.(handle|on)|\.send)\(\s*["\']{re.escape(ch)}["\']'),
                            f"通道 {ch} 主进程没人接 ⇒ 前端那一下永远等不到回音")

    def test_c6d_the_page_cannot_reach_node(self):
        main = _code_only((DESKTOP / "main.js").read_text(encoding="utf-8"))
        for want in (r"contextIsolation\s*:\s*true", r"nodeIntegration\s*:\s*false", r"sandbox\s*:\s*true"):
            self.assertTrue(_hits(main, want), f"main.js 的 webPreferences 里没有 {want} ⇒ 网页够得着 Node")


class C7Retired(unittest.TestCase):
    RETIRED = [
        # 旧更新器(design D「退役」;表 #11 两个真相源只剩一个)
        "bin/ds_update.py", "bin/ds_update_apply.py", "bin/ds_update_startup.py", "bin/ds_auto_update.py",
        # 旧安装包工具链(design D「旧安装包工具链一起退役」)
        "installer/OpenDesign.nsi", "installer/launcher.nsi", "installer/build-installer.sh",
        "installer/check-installer.py", "installer/make-update-manifest.py", "installer/mutation-installer.sh",
        ".github/workflows/windows-package-probe.yml", ".github/workflows/windows-update-e2e.yml",
        ".github/scripts/windows-package-probe.ps1", ".github/scripts/windows-update-e2e.ps1",
        # 两支旧云判据自己的判定器 / 替身 GitHub / 证书(只有它们在用)
        "bin/probe_verdict.py", ".github/scripts/update_e2e_verdict.py", ".github/scripts/fake_github.py",
        ".github/scripts/make-e2e-certs.sh",
        # 探路 workflow 由 electron-e2e.yml 取代(spike/ 目录留作参照)
        ".github/workflows/electron-shell-probe.yml",
    ]

    def test_c7_retired_files_are_gone(self):
        left = [p for p in self.RETIRED if (ROOT / p).exists()]
        self.assertEqual(left, [], "退役清单里的文件还在 —— 留着就会有人以为它还管用")

    def test_c7b_window_half_of_ds_shell_is_gone(self):
        src = (ROOT / "bin" / "ds_shell.py").read_text(encoding="utf-8")
        for gone in ("class WindowApi", "class Shell", "import webview", "import pystray", "def main("):
            self.assertEqual(_hits(src, re.escape(gone)), [], f"ds_shell.py 里 {gone!r} 还在(design A:窗口那一半退役)")
        self.assertIn("def start_backend(", src, "后台那一半要留给管家用")

    def test_c7c_release_notes_say_formal_release(self):
        """挑战 a8:旧 RELEASE.md 写死 --prerelease;`latest/download` 跳过 prerelease ⇒ 照旧发 = 没人收得到更新。"""
        text = (ROOT / "installer" / "RELEASE.md").read_text(encoding="utf-8")
        self.assertEqual(_hits(text, r"--prerelease"), [])
        self.assertIn("release-feed.mjs", text, "发布说明要写改写 latest.yml 那一步(漏了 ⇒ 每次更新整包)")


class C8NoOldUpdateSurface(unittest.TestCase):
    def test_c8_no_update_endpoints_left(self):
        web = (ROOT / "bin" / "ds_web.py").read_text(encoding="utf-8")
        self.assertEqual(_hits(web, r"/api/update"), [], "ds-web 还留着更新端点 ⇒ 两个真相源(表 #11)")
        for f in (ROOT / "web" / "src").rglob("*.ts*"):
            self.assertEqual(_hits(_code_only(f.read_text(encoding="utf-8")), r"/api/update"), [],
                             f"{f.relative_to(ROOT)} 还在调旧更新端点")

    def test_c9_frontend_no_longer_reads_pywebview(self):
        for f in (ROOT / "web" / "src").rglob("*.ts*"):
            code = _code_only(f.read_text(encoding="utf-8"))
            self.assertEqual(_hits(code, r"\bpywebview"), [], f"{f.relative_to(ROOT)} 还在读 pywebview(preload 给的是 odShell)")


if __name__ == "__main__":
    unittest.main()
