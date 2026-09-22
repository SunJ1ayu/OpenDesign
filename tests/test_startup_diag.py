#!/usr/bin/env python3
"""启动可观测性的判据(track `opendesign-startup-observability` 第一刀)。

**为什么有这个文件**:2026-08-25 业主装 0.98.0 后「打开全是白的」,我们手上
**一条线索都没有** —— 日志没有日期、没有启动编号、没有分阶段耗时,
`窗口打开:` 那一行还写在窗口真打开**之前**(假信息)。
到今天(08-30)结论仍然只能写「站得住,不是铁证」。

08-30 我还在业主面前把「开窗要等 11 秒、因为每次现建临时档案」讲成了事实 ——
**去仓库里核,这个数字和这个因果都没有任何测量支撑**。这个文件是那笔账的收口:
**先有尺,再谈快慢。**

分工(别写成 test_ds_shell_startup 的抄件):
  · `test_ds_shell_startup.py` 验 start_backend 把两条腿串对了没有;
  · **这里**验"这一次启动留下的证据够不够查案"。
"""
from __future__ import annotations

import ast
import io
import re
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))

import ds_diag                     # noqa: E402  ← 第一刀新增,现在还不存在(判据先红)
import ds_shell as shell           # noqa: E402
import ds_web                      # noqa: E402  ← 版本号的唯一来源在这儿,不在 ds_shell


class S1LogHasFullDate(unittest.TestCase):
    """s1 外壳日志的时间戳必须带日期。

    08-14 真机红补上了 `%H:%M:%S`(注释原话:"一个 strftime 换的是一趟真机")。
    这是同一笔账的下半截:**只有时分秒,跨天的日志对不了账** ——
    业主 08-25 晚白屏、08-30 才回话,中间那几行属于哪一天,现在的日志答不了。
    """

    def test_s1_timestamp_carries_a_date(self):
        with mock.patch.object(shell, "_log_path") as p:
            buf = Path(self.enterContext(tempfile.TemporaryDirectory()))
            p.return_value = buf / "外壳.log"
            shell.log("测试行")
            line = (buf / "外壳.log").read_text(encoding="utf-8").splitlines()[0]
        # 年份必须在里面。只认 4 位数字年,别让 "08-30" 这种半截货蒙混过关。
        self.assertRegex(line, r"\b20\d{2}\b",
                         f"外壳日志少了日期,跨天对不了账:{line!r}")


class S3S4RunIdAndMonotonic(unittest.TestCase):
    """s3 每次启动一个编号;s4 耗时用单调钟。"""

    def test_s3_each_startup_gets_its_own_id(self):
        a, b = ds_diag.StartupLog(emit=lambda _: None), ds_diag.StartupLog(emit=lambda _: None)
        self.assertTrue(a.run_id, "run_id 不能是空的")
        self.assertNotEqual(a.run_id, b.run_id,
                            "两次启动拿到同一个 run_id ⇒ 业主一晚开关五次,日志分不清哪行属于哪次")

    def test_s3_every_line_carries_the_run_id(self):
        seen: list[str] = []
        d = ds_diag.StartupLog(emit=seen.append)
        d.mark("lock.acquired")
        d.mark("backend.ready")
        self.assertEqual(len(seen), 2)
        for line in seen:
            self.assertIn(d.run_id, line, f"这一行没带 run_id:{line!r}")

    def test_s4_elapsed_survives_a_wall_clock_jump_backwards(self):
        """墙上时钟往回跳(对时/夏令时),耗时不许倒退。

        🔴 这条是**行为**判据不是结构判据:如果实现拿 `time.time()` 算耗时,
        下面把 time.time 钉死成一个常数就会让第二次 mark 的耗时不增 ⇒ 红。
        `ds_shell_core.py:621` 早就用 monotonic 了,这里只是不许新代码走回头路。
        """
        seen: list[str] = []
        # 🔴 StartupLog **必须在 patch 生效之后建**:`self._clock = clock or time.monotonic`
        #    在 __init__ 那一刻就把函数对象抓走了,事后再 patch 模块属性对它无效
        #    —— 第一版就是这么写的,M5 变异下判据全绿(量具自己坏了)。
        with mock.patch("time.time", return_value=0.0):
            d = ds_diag.StartupLog(emit=seen.append)
            d.mark("first")
            time.sleep(0.01)
            d.mark("second")
        got = [ms for _, ms in d.milestones()]
        self.assertEqual(len(got), 2)
        self.assertGreater(got[1], got[0],
                           "墙上时钟被钉死之后耗时没有增长 ⇒ 用的不是单调钟")


class S5Manifest(unittest.TestCase):
    """s5 启动首行要记版本清单。

    **直击 08-25 本案**:那晚最关键的证据是「WebView2 内核目录从 101+107 变成只剩 107」,
    而我们是靠业主重启后去翻文件夹才知道的。软件自己每次记一行,当晚就有答案。
    """

    def test_s5_manifest_names_the_app_and_the_webview2_version(self):
        d = ds_diag.StartupLog(emit=lambda _: None)
        m = d.manifest()
        self.assertIn(ds_web.VERSION, m, "版本清单里没有应用版本")
        for key in ("windows", "webview2", "python"):
            self.assertIn(key, m.lower(), f"版本清单里没有 {key} 这一项:{m!r}")

    def test_s5_manifest_does_not_explode_off_windows(self):
        """Linux 上查不到 WebView2 是正常的 —— 但**不许因此炸掉启动**。"""
        d = ds_diag.StartupLog(emit=lambda _: None)
        self.assertIsInstance(d.manifest(), str)


class S7UiReportIsUntrustedInput(unittest.TestCase):
    """s7 前端回叫是**网页能写进日志的口子**,必须当不可信输入对待。

    这是我自己新开的口子,双出那一轮 GPT 点破的:我原方案只想着"前端叫一声我就知道它活了",
    没想过要限死能写什么。
    """

    def test_s7_only_whitelisted_events_get_through(self):
        seen: list[str] = []
        d = ds_diag.StartupLog(emit=seen.append)
        self.assertTrue(d.report_from_ui("frontend.react_committed"))
        self.assertFalse(d.report_from_ui("随便什么名字"),
                         "白名单外的事件被放进来了 ⇒ 网页可以往日志里写任意事件名")
        self.assertEqual(len(seen), 1)

    def test_s7_detail_is_length_capped(self):
        seen: list[str] = []
        d = ds_diag.StartupLog(emit=seen.append)
        d.report_from_ui("frontend.error", "х" * 10000)
        self.assertLess(len(seen[0]), 1000,
                        "detail 没限长 ⇒ 网页一行能把日志撑爆")

    def test_s7_same_event_is_not_logged_twice(self):
        seen: list[str] = []
        d = ds_diag.StartupLog(emit=seen.append)
        d.report_from_ui("frontend.react_committed")
        d.report_from_ui("frontend.react_committed")
        self.assertEqual(len(seen), 1, "同一事件没去重 ⇒ 网页可以刷屏")


class S8S9FirstFrameWatch(unittest.TestCase):
    """s8 没等到首帧要写一次诊断快照;s9 **第一版不许弹框**。

    s9 是设计规则不是口号:不弹框之后,"多少秒算白屏"这个阈值就**不再承重** ——
    定错了最多多写一段日志,不会天天骚扰业主。
    (双出那一轮 GPT 把我原方案的最大风险 R1 整个消解掉了,靠的就是这一条。)
    """

    def _watch(self, fired: list, seen: list):
        return ds_diag.FirstFrameWatch(
            timeout=0.01, on_timeout=lambda: fired.append(1), emit=seen.append)

    def test_s8_snapshot_when_the_frame_never_arrives(self):
        fired: list = []
        w = self._watch(fired, [])
        w.start()
        w.join(timeout=2)
        self.assertEqual(len(fired), 1, "首帧没来,诊断快照没写 ⇒ 白屏又一次没有现场")

    def test_s8_absolutely_silent_when_the_frame_does_arrive(self):
        """反误报:正常启动**一行都不许多写**。误报和假绿一样坏,本项目多次实证。"""
        fired: list = []
        w = self._watch(fired, [])
        w.start()
        w.seen()
        w.join(timeout=2)
        self.assertEqual(fired, [], "首帧已经到了还写诊断 ⇒ 业主每次开机都被骚扰")

    def test_s9_the_timeout_path_never_pops_a_dialog(self):
        """第一版硬规则:超时路径**不许**碰 alert。"""
        src = (ROOT / "bin" / "ds_diag.py").read_text(encoding="utf-8")
        self.assertNotIn("alert", src,
                         "ds_diag 里出现了 alert ⇒ 阈值又变成承重的了(s9 钉的就是这个)")


class S10ExportBundleLeaksNothing(unittest.TestCase):
    """s10 托盘导出的那个包,**必须证明业主的东西一个都不在里面**。

    白屏时窗口是废的、托盘还活着 —— 这是业主唯一还能操作的地方,所以它必须存在;
    但它同时是一个**把文件打包交出去**的动作,所以要证明它只带该带的。
    """

    def test_s10_bundle_carries_only_the_whitelist(self):
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        logs = tmp / "Logs"; logs.mkdir()
        for name in ("外壳.log", "工作台.log", "网关.log"):
            (logs / name).write_text("一些日志\n", encoding="utf-8")
        # 摆几个**绝对不许出现在包里**的诱饵,名字取得和真实形态一致
        (tmp / "key.txt").write_text("sk-业主的真钥匙", encoding="utf-8")
        (tmp / "config.json").write_text('{"providers":{}}', encoding="utf-8")
        data = tmp / "Data" / "项目档案"; data.mkdir(parents=True)
        (data / "王先生家-客厅.md").write_text("客户资料", encoding="utf-8")
        refs = tmp / "Data" / "参考图库"; refs.mkdir(parents=True)
        (refs / "现场照片.jpg").write_bytes(b"\xff\xd8\xff")

        out = tmp / "诊断.zip"
        d = ds_diag.StartupLog(emit=lambda _: None)
        d.export_bundle(out, app_dir=tmp)

        names = zipfile.ZipFile(out).namelist()
        blob = b"".join(zipfile.ZipFile(out).read(n) for n in names)
        for forbidden in ("key.txt", "config.json", "王先生家", "参考图库", "现场照片"):
            self.assertNotIn(forbidden, " ".join(names),
                             f"导出包里出现了 {forbidden} ⇒ 业主的东西被打包交出去了")
        self.assertNotIn("业主的真钥匙".encode(), blob, "钥匙的**内容**进了包")
        self.assertTrue(names, "导出包是空的 ⇒ 等于没导出")


class S12CollectorsNeverBreakStartup(unittest.TestCase):
    """s12 观测层自己炸了,不许拖垮启动。

    第一性:这一层是**加进来查案的**,它绝不能成为新的故障源。
    """

    def test_s12_a_failing_emit_does_not_raise(self):
        def boom(_line):
            raise OSError("盘满了")
        d = ds_diag.StartupLog(emit=boom)
        d.mark("lock.acquired")          # 不许抛
        d.report_from_ui("frontend.error", "x")



class S2WebLogHasTime(unittest.TestCase):
    """s2 `工作台.log` 的请求行要带时间。

    它现在**一个时间戳都没有** —— 于是"JS 是什么时候被请求的""健康检查什么时候通的"
    这些问题,在白屏事后一个都答不了。而那正是分流表里最要紧的几个分叉。
    """

    def test_s2_request_lines_carry_a_timestamp(self):
        import ds_web
        buf = io.StringIO()
        fake = ds_web.Handler.__new__(ds_web.Handler)
        fake.address_string = lambda: "127.0.0.1"
        with mock.patch.object(ds_web.sys, "stdout", buf):
            ds_web.Handler.log_message(fake, '"%s" %s', "GET /api/health HTTP/1.1", "200")
        line = buf.getvalue()
        self.assertRegex(line, r"\b20\d{2}\b", f"工作台日志的请求行没有日期:{line!r}")
        self.assertRegex(line, r"\d{2}:\d{2}:\d{2}", f"工作台日志的请求行没有时间:{line!r}")


class S11BackendReadyMeansItAnswers(unittest.TestCase):
    """s11 「工作台就绪」必须是**它真的应答了**,不是"端口有人监听"。

    双出那一轮 GPT 点出来、我亲自量证过的:`ready_probe` 机制早就存在,
    但 `web_service` 从来没接上 ⇒ 现在的"后端就绪"是句半真话,
    而整条启动时间线都建在这句话上面。
    """

    def test_s11_web_service_has_a_real_probe(self):
        import ds_shell_core as core
        probe = shell.web_ready_probe
        self.assertTrue(callable(probe), "工作台没有就绪探针")
        # 端口上没人 ⇒ 必须判"没就绪",不许因为异常就当成绿(fail-closed)
        self.assertFalse(probe(1), "探针在一个死端口上返回了 True ⇒ fail-open")

    def test_s11_the_probe_is_actually_wired_in(self):
        src = (ROOT / "bin" / "ds_shell.py").read_text(encoding="utf-8")
        self.assertIn("ready_probe=web_ready_probe", src,
                      "探针写出来了却没接到 工作台 Service 上 —— "
                      "「加了防线却没把构件放进防线」,本项目栽过")


class S13ProbeMustNotGoThroughAProxy(unittest.TestCase):
    """s13 就绪探针**不许走系统代理**。

    🔴 2026-08-30 四审 subdeepseek 孤腿 BLOCK 抓到、我实测坐实:
    `urllib.request.urlopen` 对 127.0.0.1 **不绕过**系统代理
    (`urllib.request.proxy_bypass('127.0.0.1')` 就是 False;Windows 上
    `ProxyOverride` 的 `<local>` 只匹配无点主机名,匹配不到 127.0.0.1)。
    ⇒ 凡是配了系统代理的机器(公司代理、**以及 Clash 那类会设系统代理的 VPN 客户端**),
    探针对健康服务返回 False ⇒ `_wait_ready` 死等 60s ⇒ StartupFailed ⇒ **软件打不开**。

    这正是本单设计里那条红线的字面违反:**观测层绝不能成为新的故障源**。
    而它在 Linux CI 上 19 条判据全绿 —— 判据对"探针走不走代理"零覆盖,是本单最大盲区。
    仓里本来就有不受代理影响的姿势:`port_listening` 用裸 socket。
    """

    def test_s13_probe_still_works_with_a_system_proxy_configured(self):
        import http.server, socketserver, threading
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200); self.end_headers(); self.wfile.write(b'{"ok":1}')
            def log_message(self, *a): pass
        srv = socketserver.TCPServer(("127.0.0.1", 0), H)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        # 模拟"这台机器配了系统代理",代理端口没人听 —— 走代理必失败。
        # 🔴 `urllib.request._opener` 必须一起清掉:urlopen 的 opener 是**首次调用时
        #    建好并缓存**的,进程里早先跑过的判据已经建了一个"无代理"的 opener,
        #    不清它这条判据就是**假绿**(第一版正是如此 —— 同一个坑我今天踩了两次:
        #    手工探针那次也是这么骗过自己的)。清空 = 忠实还原"软件在配了代理的机器上启动"。
        import urllib.request
        with mock.patch.dict("os.environ", {"http_proxy": "http://127.0.0.1:9",
                                            "https_proxy": "http://127.0.0.1:9"}), \
             mock.patch.object(urllib.request, "_opener", None):
            ok = shell.web_ready_probe(port)
        self.assertTrue(ok,
                        "配了系统代理的机器上,健康的工作台被判成没就绪 ⇒ 死等 60s ⇒ 软件打不开")


class S16BundleRedactsProjectPaths(unittest.TestCase):
    """s16 诊断包里的请求行**不许带业主的项目名/文件名**。

    🔴 四审 subdeepseek F3:白名单是**文件级**的,而 `工作台.log` 的请求行里
    带着 `/api/files/file/<项目名>/<文件>`、`/api/projects/<项目名>/...` ——
    项目 key 和文件路径(百分号编码的中文)会随包走。
    **我在 08-30 跟业主说过"包里不会有项目档案、客户资料",文件级成立、内容级不成立
    ⇒ 那是半真话。** 要么涂抹,要么把承诺改口;选涂抹 ——
    查启动只需要知道"打了哪个端点、什么状态",不需要知道是哪个客户。
    """

    def test_s16_request_lines_keep_the_endpoint_but_lose_the_names(self):
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        logs = tmp / "Logs"; logs.mkdir()
        (logs / "外壳.log").write_text("启动\n", encoding="utf-8")
        (logs / "网关.log").write_text("网关\n", encoding="utf-8")
        (logs / "工作台.log").write_text(
            '2026-08-30 16:23:10 127.0.0.1 - "GET /api/files/overview/'
            '%E7%BF%A1%E7%BF%A0%E6%B9%BE-1801 HTTP/1.1" 200 -\n'
            '2026-08-30 16:23:10 127.0.0.1 - "GET /api/projects/王先生家/refs HTTP/1.1" 200 -\n'
            '2026-08-30 16:23:11 127.0.0.1 - "GET /api/health HTTP/1.1" 200 -\n',
            encoding="utf-8")
        out = tmp / "诊断.zip"
        d = ds_diag.StartupLog(emit=lambda _: None)
        d.export_bundle(out, app_dir=tmp)
        body = zipfile.ZipFile(out).read("Logs/工作台.log").decode("utf-8")

        for leaked in ("%E7%BF%A1", "翡翠湾", "王先生家", "1801"):
            self.assertNotIn(leaked, body,
                             f"诊断包里还带着业主的名字:{leaked!r}")
        # 但**诊断价值必须留住**:端点形状和状态码还得在,否则这份日志就没用了
        self.assertIn("/api/files", body, "端点形状被涂没了 ⇒ 这份日志失去诊断价值")
        self.assertIn("/api/health", body, "无参数的端点被误伤")
        self.assertIn("200", body, "状态码被涂没了")


class S17TheBigBlobIsSplit(unittest.TestCase):
    """s17 开头那一大块**必须被切开**。

    🔴 2026-08-30 云机器实测:到界面出来 24.8s,而**最大的一块是开头的 9.4s**
    (进程起来 → 拿到单实例锁)—— 全程最大单块,而 0.98.1 里它是**一个不透明的整块**:
    我埋的第一个里程碑正好落在它的**结尾**,里面发生了什么一样答不出来。
    同一段在 Linux 上只要 130ms(`ds_shell` 53ms + `ds_web` 76ms),差 70 倍
    ⇒ 差的是 I/O 不是算力,但**具体差在哪一段,不切开就只能猜**。
    而我今天已经猜错过一次("后端慢"被数据当场证伪),不再猜第二次。
    """

    # 🔴 2026-09-22(track opendesign-electron-shell 判据迁移账):`main()` 搬进了管家 `bin/ds_host.py`
    #    (窗口那一半退役,Electron 起管家)⇒ 后三个里程碑改在 ds_host.py 里找;
    #    `shell.imports_done` 仍记在 ds_shell 模块尾(管家 import 它时照样记)。
    #    同时认 `diag.mark(...)` 与 `ds_shell.DIAG.mark(...)` —— 管家的 serve() 用注入进来的 diag,
    #    这是**接缝的写法变了**,不是放宽:认的仍然只是真正的调用节点(下面两条对照组照旧)。
    #    行为版由 tests/test_ds_host.py h15 钉(lock.acquired → backend.ready → window.shown 真的依次记下)。
    NEEDED_SHELL = ("shell.imports_done",)
    NEEDED_HOST = ("main.entered", "manifest.done", "lock.acquired")

    @staticmethod
    def _marked_names(src: str) -> set[str]:
        """源码里**真正被 `DIAG.mark(...)` / `diag.mark(...)` 记下**的里程碑名字(按语法树认,不按字符串认)。"""
        names = set()
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if not (isinstance(f, ast.Attribute) and f.attr == "mark"):
                continue
            recv = f.value
            if not ((isinstance(recv, ast.Name) and recv.id in ("DIAG", "diag"))
                    or (isinstance(recv, ast.Attribute) and recv.attr == "DIAG")):
                continue
            if node.args and isinstance(node.args[0], ast.Constant) \
                    and isinstance(node.args[0].value, str):
                names.add(node.args[0].value)
        return names

    def test_s17_the_startup_path_marks_every_stage(self):
        """问的是"这个里程碑被记了吗",所以按**语法树**认,不按字符串形状认。

        🔴 2026-09-01 换掉了上一版 `assertIn(f'DIAG.mark("{name}")', src)`。
        换的理由不是它红了(它确实红了 —— 我给 `lock.acquired` 加了 detail 参数),
        而是**它问的和它想问的不是一回事**:那个写法要求里程碑"被记下**且不带 detail**"。
        证据不用推:`ds_shell.py` 里 `window.create_returned` 从 0.98.1 起就带着 detail,
        它只是**恰好不在 NEEDED 里**,所以这个洞一直没露出来。

        而且新写法**更严**,不只是更松:
        · 旧写法能被一句**注释**里的 `DIAG.mark("lock.acquired")` 喂饱(字符串搜整个文件);
          新写法只认真正的调用节点(对照组 c2 钉住)。
        · detail 是给业主看的诊断内容,不是里程碑在不在的证据 —— 它变化时这条不该红。

        (查过才敢改:全仓没有任何东西按整行匹配这几条 mark ——
        `probe_verdict.py` 和 `windows-package-probe.ps1` 里都没有 `lock.acquired`。
        所以加 detail 不会打坏下游,这条红是**题面问窄了**,不是真 bug。)
        """
        for fname, needed in (("ds_shell.py", self.NEEDED_SHELL), ("ds_host.py", self.NEEDED_HOST)):
            marked = self._marked_names((ROOT / "bin" / fname).read_text(encoding="utf-8"))
            for name in needed:
                self.assertIn(name, marked,
                              f"{fname}:开头那一大块少了里程碑 {name!r} ⇒ 它仍然是个黑块")

    def test_s17_a_milestone_named_only_in_a_comment_does_not_count(self):
        """对照组:光在注释里写出那行字,不算把里程碑记下来(旧写法在这里是绿的)。"""
        fake = 'DIAG.mark("main.entered")\n# DIAG.mark("lock.acquired") ← 只是注释\n'
        self.assertEqual(self._marked_names(fake), {"main.entered"},
                         "注释里的调用被当成真调用 ⇒ 这条判据可以被一句注释喂饱")

    def test_s17_a_detail_argument_does_not_hide_the_milestone(self):
        """对照组:带 detail 的调用必须照样算数(这正是 2026-09-01 那条假红的形状)。"""
        fake = 'DIAG.mark("lock.acquired", f"port={p} 用时{ms}ms")\n'
        self.assertEqual(self._marked_names(fake), {"lock.acquired"})

    def test_s17_imports_done_is_marked_before_main_ever_runs(self):
        """顺序要对 —— 但**按执行顺序判,不按源码顺序判**。

        🔴 第一版这条判的是"谁在源码里靠前",当场红了 —— 而**红的是我的题面不是代码**:
        `shell.imports_done` 写在文件末尾,执行却在 `main()` **之前**(模块体先跑完)。
        结构断言在这里问错了问题,改成真去 import 一次、看它到底先记了什么。
        """
        import subprocess, sys as _sys
        out = subprocess.run(
            [_sys.executable, "-c",
             "import sys; sys.path.insert(0, %r)\n"
             "import ds_shell\n"
             "print([n for n, _ in ds_shell.DIAG.milestones()])" % str(ROOT / "bin")],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        names = out.stdout.strip()
        self.assertIn("shell.imports_done", names,
                      "光 import 一次,imports_done 就该已经记下了")
        self.assertNotIn("main.entered", names,
                         "还没调用 main() 就记了 main.entered ⇒ 时间线会撒谎")


if __name__ == "__main__":
    unittest.main()
