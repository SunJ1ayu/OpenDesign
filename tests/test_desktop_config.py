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
    """从 src[start] 那个 `{`(或 `(`)起,数深度取到配对的 `}`(`)`)(跳过字符串)。别用正则找边界 —— 本仓栽过四次。"""
    assert src[start] in "{(", src[start:start + 20]
    op, cl = src[start], "}" if src[start] == "{" else ")"
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
        elif c == op:
            depth += 1
        elif c == cl:
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    raise AssertionError(f"没找到配对的 {cl} —— 这道闸问不出东西")


def _call_args(src: str, callee_rx: str) -> list[str]:
    """每一处 `<callee>(` 调用的整段实参(含两头括号)。"""
    return [_balanced(src, m.end() - 1) for m in re.finditer(callee_rx + r"\s*\(", src)]


def _top_entries(obj_src: str) -> dict[str, str]:
    """对象字面量第一层:键名 → 这一项的全文(含键名)。只认 `,` 分隔,深度 > 0 的逗号不算。"""
    body = obj_src[1:-1]
    parts, depth, quote, cur, i = [], 0, "", "", 0
    while i < len(body):
        c = body[i]
        if quote:
            if c == "\\":
                cur += body[i:i + 2]
                i += 2
                continue
            if c == quote:
                quote = ""
        elif c in "\"'`":
            quote = c
        elif c in "{([":
            depth += 1
        elif c in "})]":
            depth -= 1
        elif c == "," and depth == 0:
            parts.append(cur)
            cur = ""
            i += 1
            continue
        cur += c
        i += 1
    parts.append(cur)
    out = {}
    for p in parts:
        m = re.match(r"\s*(?:async\s+)?([A-Za-z_$][\w$]*)", p)
        if m:
            out[m.group(1)] = p
    return out


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

    def test_c2_the_which_user_page_is_not_forced_away(self):
        """U4「留着和zcode一样」:「为哪位用户」页照 ZCode 留着。模板里让它消失的开关是把
        `$isForceCurrentInstall` 置 1(第四跑零点击那版就是这么做的,已撤回)。
        攻题 #13:原来按宏名禁 customInstallMode / customFinishPage,会误伤正当的定制、又挡不住换个宏名跳页
        ⇒ 静态这边只钉那个开关;页面序列由云 Windows E5.pages / E4.wizard 按真实向导逐页核。"""
        code = _nsis_code_only(NSH.read_text(encoding="utf-8"))
        self.assertEqual(_hits(code, r"StrCpy\s+\$isForceCurrentInstall\s+\"?1"), [],
                         "「为哪位用户」页被强行跳过 ⇒ 不再是业主选的 U4")

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
        files = list(DESKTOP.glob("*.js")) + list((DESKTOP / "lib").glob("*.js"))
        self.assertIn(DESKTOP / "main.js", files, "desktop/main.js 都没有 —— 这条问不出东西(不许空转成绿)")
        for f in files:
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

    def test_c6c_every_preload_channel_has_a_main_side_in_the_right_direction(self):
        """攻题 #9:同名字符串方向反了照样对得上 —— `invoke` 却只有 `webContents.send`,那一问永远没人答。
        三张表分开对:invoke↔ipcMain.handle、send↔ipcMain.on、ipcRenderer.on↔webContents.send。"""
        main_side = "\n".join(_code_only(f.read_text(encoding="utf-8"))
                              for f in list(DESKTOP.glob("*.js")) + list((DESKTOP / "lib").glob("*.js"))
                              if f.name != "preload.js")
        pairs = {"invoke": r"ipcMain\.handle", "send": r"ipcMain\.on", "on": r"webContents\.send"}
        seen = 0
        for verb, main_rx in pairs.items():
            for ch in set(re.findall(rf'ipcRenderer\.{verb}\(\s*["\']([^"\']+)["\']', self.preload)):
                seen += 1
                self.assertTrue(_hits(main_side, rf'{main_rx}\(\s*["\']{re.escape(ch)}["\']'),
                                f"preload 用 ipcRenderer.{verb}('{ch}'),主进程没有对应的 {main_rx.replace(chr(92), '')}('{ch}')"
                                " ⇒ 前端那一下永远等不到回音")
        self.assertGreater(seen, 0, "preload 一个通道都没有")

    def test_c6d_the_page_cannot_reach_node(self):
        main = _code_only((DESKTOP / "main.js").read_text(encoding="utf-8"))
        for want in (r"contextIsolation\s*:\s*true", r"nodeIntegration\s*:\s*false", r"sandbox\s*:\s*true"):
            self.assertTrue(_hits(main, want), f"main.js 的 webPreferences 里没有 {want} ⇒ 网页够得着 Node")


class C11LockfilesResolvePublicly(unittest.TestCase):
    """T4 云跑 run 35728406022 红在 E1 的 `npm ci`(`npm error Exit handler never called!`,2 分钟就死):
    本机 npm 配的是腾讯云内网镜像,我生成的锁文件把每个包都钉在 `http://mirrors.tencentyun.com/npm/…` ——
    只有腾讯云里的机器连得上,GitHub 的 Windows 机器、业主的电脑都连不上;而且是 http。
    npm 只在 resolved 的主机是 registry.npmjs.org 时才换成当前配置的源(replace-registry-host 默认值),
    所以别的机器上 `npm ci` 照着锁文件直连那个内网地址,卡死。
    钉住**在别的机器上装**的那几份锁:Electron 的 `desktop/`、云判据自己的 `.github/scripts/electron-e2e/`。
    (`web/package-lock.json` 同病,但没有任何一处在本机之外装它 —— 前端产物是本机 build 好提交的;延期,不在本单承诺里。)"""

    LOCKS = ["desktop/package-lock.json", ".github/scripts/electron-e2e/package-lock.json"]

    def test_c11_every_package_resolves_from_the_public_registry(self):
        for rel in self.LOCKS:
            data = json.loads((ROOT / rel).read_text(encoding="utf-8"))
            resolved = [(name, meta["resolved"]) for name, meta in data.get("packages", {}).items()
                        if isinstance(meta, dict) and meta.get("resolved")]
            self.assertTrue(resolved, f"{rel}:一个 resolved 都没有 ⇒ 这条问不出东西")
            bad = [(n, u) for n, u in resolved if not u.startswith("https://registry.npmjs.org/")]
            self.assertEqual(bad[:5], [], f"{rel}:{len(bad)}/{len(resolved)} 个包不是从官方 https 源装的 ⇒ 别的机器上 npm ci 连不上")


class C12PsNoCaseTwins(unittest.TestCase):
    """T4 云跑第二跑 run 35728968821:**PowerShell 变量名不分大小写**,e2e.ps1 E4 那段 `$ver = $Ver` 再在循环里
    给 `$ver` 赋值 ⇒ 期望版本 `$Ver` 被悄悄改成了新版号。两个后果方向相反:
      · E5.samever 假红(新装的是 v1,却拿 v2 的号去比);
      · E4.oldmap 假绿(本该查「旧版 blockmap 取到了」,实际拿新版那份去比 —— 新版那份每次都一定会取)。
    这类错看代码看不出来(读的人按大小写区分),只有跑到那一行才暴露。钉住:云判据的 .ps1 里,
    同一个变量名不许出现两种大小写 —— 函数里的局部变量也算(眼下作用域隔开无害,但下一次挪代码就不是了)。"""

    DIR = ".github/scripts/electron-e2e"
    VAR = re.compile(r"\$\{?(?:(?:script|global|local|private|using):)?([A-Za-z_][A-Za-z0-9_]*)")

    def test_c12_no_variable_spelled_two_ways(self):
        files = sorted((ROOT / self.DIR).glob("*.ps1"))
        self.assertTrue(files, f"{self.DIR} 下一个 .ps1 都没有 ⇒ 这条问不出东西")
        twins = {}
        for f in files:
            seen: dict[str, set[str]] = {}
            for m in self.VAR.finditer(f.read_text(encoding="utf-8")):
                seen.setdefault(m.group(1).lower(), set()).add(m.group(1))
            for k, v in seen.items():
                if len(v) > 1:
                    twins[f"{f.name}:{k}"] = sorted(v)
        self.assertEqual(twins, {}, "PowerShell 变量名不分大小写 ⇒ 这些拼法其实是同一个变量,给一个赋值就改了另一个")


class C10MainIsWired(unittest.TestCase):
    """攻题 #1 #10 #11:纯函数与控制器写对了、main.js 不调用 ⇒ 全绿而业主那边什么都没发生。
    行为由 test_desktop_controller.mjs 钉;这里钉 **main.js 真的接上了它们**(第二道,查代码不查注释)。"""

    def test_c10_main_uses_the_tested_pieces(self):
        main = _code_only((DESKTOP / "main.js").read_text(encoding="utf-8"))
        for need, why in [
            (r'require\(\s*["\']\./lib/controller(\.js)?["\']\s*\)', "不经控制器 ⇒ 版本自检 / 调度 / 装失败恢复全是死代码"),
            (r"createController\s*\(", "控制器没被建出来"),
            (r"\.hostStdout\s*\(", "管家的输出没交给控制器(分块解码在它里面)"),
            (r"\.navigate\s*\(", "will-navigate 没问控制器 ⇒ 外链不会交给系统浏览器"),
            (r'require\(\s*["\']\./lib/menus(\.js)?["\']\s*\)', "托盘 / 右键菜单没用测过的模板"),
            (r"trayMenuTemplate\s*\(", "托盘菜单不是那三项"),
            (r"contextMenuTemplate\s*\(", "右键没有复制粘贴(旧版 WebView2 自带,不做是回归)"),
            (r"[\"']context-menu[\"']", "没接 context-menu 事件"),
            (r"requestSingleInstanceLock\s*\(", "没有单实例锁 ⇒ 双击两次起两套后台"),
            (r"windowsHide\s*:\s*true", "起管家时没藏控制台 ⇒ 业主每次开机看到一个黑框"),
            # 复核(Cursor grok-4.7-high)#2:下面这几项控制器测了、main.js 不叫照样全绿
            (r"\.startUpdates\s*\(", "没开更新调度 ⇒ 先开软件后开 VPN 的那天,一整天不再自己查(挑战 a6)"),
            (r"\.checkNow\s*\(", "「重试」没接到控制器"),
            (r"\.updateState\s*\(", "前端打开时拿不到当前更新状态"),
            (r"\.installUpdate\s*\(", "「重启以更新」不经控制器 ⇒ 装失败没有恢复(攻题 #8)"),
            (r"\.setQuitting\s*\(", "退出时没告诉控制器 ⇒ 正常关软件也弹「意外退出」"),
            # 同类再扫(主 agent):控制器把外链 / 诊断包交给 deps,deps 是空函数照样绿
            (r"shell\.openExternal\s*\(", "外链没真交给系统浏览器(mc9 只测到 deps)"),
            (r"shell\.showItemInFolder\s*\(", "导出的诊断包没在文件夹里点出来(mc7 只测到 deps)"),
            (r"setWindowOpenHandler\s*\(", "没拦 window.open / target=_blank ⇒ 外站开进一个带后台权限的新窗口"),
            (r"windowOpenDecision\s*\(", "新窗口的放行规则不是测过的那一份(navPolicy)"),
        ]:
            self.assertTrue(_hits(main, need), f"main.js:{why}(要有 {need})")

    def test_c10b_updates_only_go_through_the_controller(self):
        """复核 #2:main.js 自己 `checkForUpdates()` 一次、点按钮直接 `quitAndInstall()` ⇒ 控制器的调度和装失败恢复被绕过,
        而 c10 的「要有」清单照样满足。查更新和交安装器**只许**在控制器里(经 deps.updater)。"""
        main = _code_only((DESKTOP / "main.js").read_text(encoding="utf-8"))
        for banned, why in [
            (r"\.checkForUpdates\w*\s*\(", "main.js 自己查更新 ⇒ 绕过 15 分钟 / 4 小时调度与「只排一只」"),
            (r"\.quitAndInstall\s*\(", "main.js 自己交安装器 ⇒ 绕过「先收管家、装失败重新拉起」"),
        ]:
            self.assertEqual(_hits(main, banned), [], f"main.js:{why}")

    def test_c10c_host_exit_is_read_after_the_pipe_drains(self):
        """Node 的子进程 `exit` 事件来的时候 stdout **可能还没读完**;`close` 才保证读完。
        管家的 fatal 往往就是退出前最后一行 ⇒ 在 `exit` 上叫 hostExit = 先弹「意外退出」、再弹真原因(mc5 在现场失效)。
        写法照接缝表:`host.on("close", (code) => ctl.hostExit(code))`,回调写在调用处。
        另:管道原始块原样交给 hostStdout,**不许逐块 toString**(UTF-8 切半处会变成乱码,mc2b 只测得到控制器)。"""
        main = _code_only((DESKTOP / "main.js").read_text(encoding="utf-8"))
        handlers = _call_args(main, r"\.(?:on|once)")
        on_close = [h for h in handlers if re.match(r"\(\s*[\"']close[\"']", h) and ".hostExit" in h]
        on_exit = [h for h in handlers if re.match(r"\(\s*[\"']exit[\"']", h) and ".hostExit" in h]
        self.assertTrue(on_close, "main.js 没在管家的 close 事件里叫 hostExit")
        self.assertEqual(on_exit, [], "main.js 在 exit 事件里叫 hostExit ⇒ 最后一行 fatal 可能还在管道里")
        for arg in _call_args(main, r"\.hostStdout"):
            self.assertIsNone(re.search(r"toString|String\s*\(|TextDecoder|\.decode\s*\(", arg),
                              f"hostStdout{arg[:80]}:逐块转字符串会把切在中间的中文变成乱码 —— 原样交给控制器")

    def test_c10d_relaunch_really_leaves(self):
        """复核 #8:Electron 的 `app.relaunch()` 只是登记「退出后再起一份」,**当前进程不退**;
        托盘软件的关窗又是「藏起来」⇒ 只 relaunch 不 exit = 空壳窗口还在、新的一份永远不起。"""
        main = _code_only((DESKTOP / "main.js").read_text(encoding="utf-8"))
        self.assertIsNotNone(re.search(r"app\.relaunch\s*\([^)]*\)\s*;?\s*app\.exit\s*\(", main),
                             "main.js 里要有 `app.relaunch()` 紧跟 `app.exit(0)`(控制器的 deps.relaunch 就是它)")

    def test_c10e_tray_callbacks_do_something(self):
        """复核 #10:托盘真点延期到 T6,但传进 trayMenuTemplate 的三个回调是空函数照样全绿(mc17 只测模板)。
        写法照接缝表:回调写在调用处的对象字面量里,判据才看得见它们各自去做了什么。"""
        main = _code_only((DESKTOP / "main.js").read_text(encoding="utf-8"))
        calls = _call_args(main, r"trayMenuTemplate")
        self.assertTrue(calls, "main.js 没调 trayMenuTemplate")
        arg = calls[0]
        brace = arg.find("{")
        self.assertTrue(brace >= 0 and not arg[1:brace].strip(), f"trayMenuTemplate 的实参要是就地写的对象字面量:{arg[:80]}")
        entries = _top_entries(_balanced(arg, brace))
        for key, need, why in [
            ("onOpen", r"show", "「打开 OpenDesign」没把窗口叫出来"),
            ("onExport", r"(?i)export", "「导出本次启动诊断」没叫管家出包"),
            ("onQuit", r"(?i)quit", "「退出」没退"),
        ]:
            self.assertIn(key, entries, f"trayMenuTemplate 缺 {key}")
            body = re.sub(r"^\s*(?:async\s+)?" + key, "", entries[key], count=1)
            self.assertIsNotNone(re.search(need, body), f"托盘 {key}:{why}(回调里要有 {need}):{entries[key].strip()[:80]}")

    def test_c10f_host_spawn_and_pipe_errors_are_caught(self):
        """T4 收货补(主 agent 读 GPT 那一半的 diff):python.exe 缺失 / 被杀软隔离时 `spawn` 发 `error` 事件,
        没人接 ⇒ Node 把它抛成主进程未捕获异常:业主看到一框英文堆栈,窗口停在「正在启动…」(mc21 只测到控制器)。
        写法照接缝表:`host.on("error", (error) => ctl.hostError(error))`。
        同类再扫:管家先死了、我们还往它 stdin 写(window-shown / report)⇒ stdin 流发 EPIPE 的 `error`,没人接同样是未捕获异常
        (sendHost 的 try/catch 接不住:那是异步事件,不是 write() 同步抛)。"""
        main = _code_only((DESKTOP / "main.js").read_text(encoding="utf-8"))
        handlers = _call_args(main, r"\.(?:on|once)")
        on_error = [h for h in handlers if re.match(r"\(\s*[\"']error[\"']", h) and ".hostError" in h]
        self.assertTrue(on_error, "main.js 没在管家的 error 事件里叫 hostError ⇒ python.exe 起不来时主进程未捕获异常")
        self.assertTrue(_hits(main, r"\.stdin\s*\.\s*(?:on|once)\s*\(\s*[\"']error[\"']"),
                        "main.js 没接管家 stdin 的 error ⇒ 管家先死、再往它写一行就是 EPIPE 未捕获异常")

    def test_c10g_quit_app_goes_through_the_same_shutdown(self):
        """T4 收货补:起不来时控制器叫 deps.quitApp(),main.js 传个空函数 mc19~mc21 照样全绿(它们只测到 deps)。
        要走托盘「退出」同一条收摊路 quitAll(先收管家、再退)—— 版本对不上那一刻管家和两条腿都还活着。"""
        main = _code_only((DESKTOP / "main.js").read_text(encoding="utf-8"))
        calls = _call_args(main, r"createController")
        self.assertTrue(calls, "main.js 没调 createController")
        arg = calls[0]
        brace = arg.find("{")
        self.assertTrue(brace >= 0 and not arg[1:brace].strip(), f"createController 的实参要是就地写的对象字面量:{arg[:80]}")
        entries = _top_entries(_balanced(arg, brace))
        self.assertIn("quitApp", entries, "控制器的 deps 里没有 quitApp")
        body = re.sub(r"^\s*(?:async\s+)?quitApp", "", entries["quitApp"], count=1)
        self.assertIsNotNone(re.search(r"quitAll\s*\(", body),
                             f"quitApp 没走 quitAll(先收管家再退):{entries['quitApp'].strip()[:80]}")


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

    def test_c7c_release_notes_point_at_the_tested_tool(self):
        """挑战 a8:旧 RELEASE.md 写死 `--prerelease`;`latest/download` 跳过 prerelease ⇒ 照旧发 = 没人收得到更新。
        攻题 #15:文档里禁词会误伤正确的警告、提一句也能喂绿 ⇒ 发布命令本身由 release-feed.mjs 生成(r8 钉它的实参),
        这里只要求发布说明叫人用那个工具,而不是手敲命令。"""
        text = (ROOT / "installer" / "RELEASE.md").read_text(encoding="utf-8")
        self.assertTrue(_hits(text, r"release-feed\.mjs\s+gh-command"), "发布说明没叫人用生成好的发布命令")
        self.assertTrue(_hits(text, r"release-feed\.mjs\s+verify"), "发布说明没叫人先核 sha512")


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
