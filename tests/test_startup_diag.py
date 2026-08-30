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

import io
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


class S6NoLyingWindowOpenedLine(unittest.TestCase):
    """s6 不许再有一行在窗口真打开**之前**宣布"窗口打开了"。

    这条是钉住 D4 不被改回去。白屏那晚(08-25)日志里就有那一行 ——
    它把根本没发生的事说成了既成事实,而我事后还拿它当过证据。
    """

    def test_s6_the_lying_literal_is_gone(self):
        src = (ROOT / "bin" / "ds_shell.py").read_text(encoding="utf-8")
        self.assertNotIn('log(f"窗口打开', src,
                         "那行假信息又回来了 —— 它写在 webview.start() 之前,报的是"
                         "「我要开了」不是「开了」")

    def test_s6_window_shown_is_reported_from_the_shown_event(self):
        src = (ROOT / "bin" / "ds_shell.py").read_text(encoding="utf-8")
        self.assertIn('events.shown += lambda: DIAG.mark("window.shown")', src,
                      "「窗口真的显示了」没有挂在 shown 事件上 ⇒ 时间线又会撒谎")


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


class S14WatchIsArmedOnlyOnce(unittest.TestCase):
    """s14 首帧看门**只许上一次膛**。

    🔴 四审 subdeepseek 抓到:`start_first_frame_watch` 挂在 `events.shown` 上,
    而托盘还原(hide → show)会**再发一次 Shown** ⇒ 又拉起一个 90s 看门;
    此时页面不会再报首帧(只在加载时报一次),而且 `report_from_ui` 按进程去重
    连重报都会丢 ⇒ 新看门**必然超时** ⇒ 业主每次从托盘还原都换来一段假诊断。
    这就是"每次开机被骚扰"的原形,只是从弹框降级成了假日志。
    """

    def test_s14_second_arm_does_not_start_a_second_watch(self):
        sh = shell.Shell.__new__(shell.Shell)
        sh._frame_watch = None
        sh.web_port = 1
        sh.start_first_frame_watch()
        first = sh._frame_watch
        sh.start_first_frame_watch()
        self.assertIs(sh._frame_watch, first,
                      "第二次 shown(托盘还原)又上了一次膛 ⇒ 必然超时 ⇒ 假诊断")


class S15WiringFromUiToWatch(unittest.TestCase):
    """s15 前端报首帧 ⇒ 必须真的解除看门(接线闸)。

    🔴 四审 subdeepseek F6:`report_startup → note_first_frame → watch.seen()`
    这段接线**一条判据都没有**。断了的话所有判据照绿,而看门每次都误报。
    本单自己的标准就是"接线要钉死"(s6/s11 都做了),这段不该例外。
    """

    def test_s15_frame_submitted_disarms_the_watch(self):
        sh = shell.Shell.__new__(shell.Shell)
        sh._frame_watch = None
        sh.web_port = 1
        sh.start_first_frame_watch()
        api = shell.WindowApi(sh)
        api.report_startup("frontend.frame_submitted", "1280x860")
        self.assertTrue(sh._frame_watch._seen.is_set(),
                        "前端说画出来了,看门却没被解除 ⇒ 90s 后照样写假诊断")


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

    NEEDED = ("shell.imports_done", "main.entered", "manifest.done", "lock.acquired")

    def test_s17_the_startup_path_marks_every_stage(self):
        src = (ROOT / "bin" / "ds_shell.py").read_text(encoding="utf-8")
        for name in self.NEEDED:
            self.assertIn(f'DIAG.mark("{name}")', src,
                          f"开头那一大块少了里程碑 {name!r} ⇒ 它仍然是个黑块")

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

PROBE = ROOT / ".github" / "scripts" / "windows-package-probe.ps1"


def _probe_phase(src: str, n: str) -> str:
    """切出探针里第 n 相那一段(`# ── n …` 到下一个 `# ── `)。

    按段切、**不按行号切** —— 行号在本项目已经被证明第 N 次不是身份。
    """
    lines = src.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.startswith(f"# ── {n} ")), None)
    assert start is not None, f"探针里找不到第 {n} 相"
    end = next((j for j in range(start + 1, len(lines)) if lines[j].startswith("# ── ")),
               len(lines))
    # 🔴 **注释行不算数**。这几条判据问的都是"这一段里有没有这句代码",而这一段的
    #    注释里恰好写着同样的字(讲的就是这个坑)⇒ 不滤掉的话,把代码删干净、
    #    只留注释,判据照样绿 —— 那就是本项目记过多次的死断言。
    return "\n".join(ln for ln in lines[start:end] if not ln.lstrip().startswith("#"))


class S18ProbeAsksTheJudgeAndSaysWhatItAnswers(unittest.TestCase):
    """s18 探针只负责**采事实**,判定必须去问 `bin/probe_verdict.py`。

    🔴 2026-08-30 深夜重写。原来这一整套是**静态断言**(读 .ps1 源码问"这句话在不在"),
    今晚被连打回十几次,最后 subdeepseek 自己变异 8 种改法逐条执行、每一种都全绿。
    结论:**字面断言够不着语义**。判定已经搬进 `probe_verdict.py`(行为判据见 s19),
    这里只剩一件**静态的事非钉不可** —— 探针有没有真的去问它、有没有把答案原样说出来。

    这一条本机验不了(没有 pwsh),所以配的变异(M23~M28)全是"把接线剪掉"。
    """

    KINDS = {"5 服务活了吗": "health", "6 窗口在不在": "window",
             "8 收日志": "logs", "10 带系统代理启动": "health"}

    def _code(self, sec: str) -> list:
        return [ln for ln in sec.splitlines() if not ln.lstrip().startswith("#")]

    def test_s18_the_judge_is_asked_in_every_machine_decided_phase(self):
        src = PROBE.read_text(encoding="utf-8")
        for phase, kind in self.KINDS.items():
            sec = _probe_phase(src, phase.split()[0])
            code = "\n".join(self._code(sec))
            self.assertIn(f"Get-Verdict '{kind}'", code,
                          f"第 {phase} 相没有去问判定器 ⇒ 它又在自己判,而自己判的那套"
                          "本机验不了(今晚被打回十几次的就是它)")
            self.assertIn("Say", code, f"第 {phase} 相没把判定器的答案说出来")

    def test_s18_the_judge_is_the_repo_copy_not_the_installed_one(self):
        """判定器要用**仓库里这一份**(和探针同版本),不是装出来的那份旧的。"""
        src = "\n".join(self._code(PROBE.read_text(encoding="utf-8")))
        self.assertIn("probe_verdict.py", src, "没有引用判定器")
        self.assertIn("$PSScriptRoot", src,
                      "判定器不是按脚本自身位置找的 ⇒ 会去用装出来的那份(版本对不上)")

    def test_s18_the_facts_reach_the_judge_as_pure_ascii(self):
        """🔴 真跑(run 33321769218)当场照出来的:第 8 相把三份日志全判成缺席,
        而同一秒第 9 相导出的包里 `Logs/外壳.log`、`Logs/工作台.log` **明明在**;
        改之前那趟用同样的 `Test-Path` 报的是 `外壳.log 1188B`。

        ⇒ 不是路径,是**管道**:事实的键是中文,PowerShell 往原生进程写管道用的是
        控制台代码页(en-US runner = cp1252)⇒ 中文被打坏 ⇒ python 一个键都查不到
        ⇒ 三份全"缺席" ⇒ **假红**。这是本单栽过一次的同一个坑(第 9 相"打印中文即炸"),
        只是这次在**输入**方向。

        修法不是"再赌一次编码",是**让数据不含非 ASCII**:`-EscapeHandling EscapeNonAscii`
        把中文转成 `\\uXXXX`,任何代码页都打不坏它。
        """
        src = "\n".join(ln for ln in PROBE.read_text(encoding="utf-8").splitlines()
                         if not ln.lstrip().startswith("#"))
        self.assertIn("ConvertTo-Json", src, "没有把事实序列化给判定器")
        self.assertIn("EscapeNonAscii", src,
                      "交给判定器的 JSON 不是纯 ASCII ⇒ 中文键会被控制台代码页打坏 ⇒ "
                      "判定器一个键都查不到 ⇒ 假红(run 33321769218 就是这么红的)")

    def test_s18_a_judge_that_does_not_run_is_a_FAIL_not_a_pass(self):
        """判定器自己没跑成时必须 fail-closed —— 判不了就不能算过。"""
        src = PROBE.read_text(encoding="utf-8")
        start = src.index("function Get-Verdict")
        body = "\n".join(ln for ln in src[start:src.index("\n}", start)].splitlines()
                          if not ln.lstrip().startswith("#"))
        # 🔴 别数个数:剪掉两条 fail-closed 分支、剩下两条,数量断言照样满意
        #    (M35 当场照出来的)。要问的是:**每一条提前返回的路,是不是都带 FAIL**。
        returns = [ln.strip() for ln in body.splitlines() if "return" in ln]
        self.assertTrue(returns, "Get-Verdict 一条 return 都没有?")
        early = returns[:-1]          # 最后一条是把判定器的答案原样交出去
        self.assertTrue(early, "Get-Verdict 没有任何提前返回的失败路")
        for ln in early:
            self.assertIn("FAIL", ln,
                          f"这条提前返回没带 FAIL:{ln!r} ⇒ 判定器判不了却当过了(fail-open)")

    def test_s18_the_facts_it_collects_are_the_ones_the_judge_needs(self):
        src = PROBE.read_text(encoding="utf-8")
        logs = "\n".join(self._code(_probe_phase(src, "8")))
        for name in ("外壳.log", "工作台.log", "网关.log"):
            self.assertIn(name, logs, f"第 8 相没有采 {name} 这份事实 ⇒ 判定器看不见它")
        win = "\n".join(self._code(_probe_phase(src, "6")))
        self.assertIn("[W32]::Cls(", "\n".join(self._code(src)),
                      "没有采窗口类这个事实 ⇒ 判定器分不开报错框和真窗口")
        self.assertIn("cls", win, "第 6 相没把窗口类喂给判定器")
        self.assertIn("ours", win, "第 6 相没把老口径(进程主窗口标题)喂给判定器")

    def test_s18_the_health_phases_scan_a_span_not_one_hardcoded_port(self):
        """🔴 应用用 pick_ports(span=20) 挑端口,8766 被占会挪 ⇒ 写死一个端口 = 健康假红。"""
        src = PROBE.read_text(encoding="utf-8")
        # 🔴 光问"这一段里有没有 $PortSpan"不够:初始化用它、而**轮询那一圈**退回
        #    单端口,判据照样绿(M37 照出来的)。要问的是:每一圈 foreach 都得走整段。
        for phase in ("5", "10"):
            code = self._code(_probe_phase(src, phase))
            loops = [ln for ln in code if "foreach ($p in" in ln]
            self.assertTrue(loops, f"第 {phase} 相没有逐端口试的循环")
            for ln in loops:
                self.assertIn("$PortSpan", ln.strip(),
                              f"第 {phase} 相有一圈没走整段端口:{ln.strip()!r} ⇒ "
                              "应用挪到 8767 就判它没活(健康假红)")

    def test_s18_the_judge_failing_weirdly_is_a_FAIL_not_a_verdict(self):
        """🔴 rc 不能被忽略(第 2d 轮 subdeepseek 实测,也是我自己自审里写下的那条)。

        `$out = … 2>&1` 把 stderr 并进输出,而原来只在 `$out` **为空**时才看 rc ⇒
        任何"stderr 上有话、话里没有 FAIL"的失败都会被当成一条合法裁决原样 Say 出去:
          · 判定器 import 期炸 → traceback 在 stderr → 整趟绿;
          · kind 分发键被改名 → rc=2 + 用法串 → **第 6 相静默变绿**。
        ⇒ rc 只有 0(OK)和 1(FAIL)是**裁决**,别的都是"判定器自己坏了" = fail-closed。
        """
        src = PROBE.read_text(encoding="utf-8")
        start = src.index("function Get-Verdict")
        body = "\n".join(ln for ln in src[start:src.index("\n}", start)].splitlines()
                          if not ln.lstrip().startswith("#"))
        self.assertIn("$rc", body, "Get-Verdict 根本没接住判定器的退出码")
        rc_guard = [ln for ln in body.splitlines()
                    if "$rc" in ln and ("-ne" in ln or "-notin" in ln or "-gt" in ln)]
        self.assertTrue(rc_guard,
                        "退出码只被记下来、没被用来判 ⇒ 判定器异常退出(rc=2 用法串走 stderr)"
                        "会被当成裁决说出去 ⇒ 静默变绿")
        for ln in rc_guard:
            self.assertIn("FAIL", ln, f"这条 rc 守卫没有 fail-closed:{ln.strip()!r}")

    def test_s18_the_sampling_parameters_are_pinned_too(self):
        """🔴 采样**参数**也要钉:同一轮实测出三种改法,全都 s18+s19 全绿而行为已坏。

        · `Get-AppWindows $appTitle` → `Get-AppWindows ''`:标题过滤没了 ⇒
          b99b603 那个"CI 上永远有 WindowsTerminal ⇒ 第 6 相永远不会红"原样复活;
        · `$PortSpan = 8766..8786` → `@(8766)`:轮询那圈照样引用 $PortSpan,
          而这一刀要修的"写死 8766 健康假红"原样复活;
        · 第 10 相去掉 `-Proxy $null`:探针自己的健康检查也走那条死代理 ⇒ 每趟假红,
          而那一相正是验代理修复的,一废全废。
        """
        src = PROBE.read_text(encoding="utf-8")
        code = [ln for ln in src.splitlines() if not ln.lstrip().startswith("#")]
        win = [ln for ln in _probe_phase(src, "6").splitlines()
               if not ln.lstrip().startswith("#") and "Get-AppWindows" in ln]
        self.assertTrue(win, "第 6 相没有去取窗口清单")
        for ln in win:
            self.assertIn("$appTitle", ln,
                          f"取窗口时没按应用标题筛:{ln.strip()!r} ⇒ 同屏任何窗口都算我们的")
        span = [ln for ln in code if ln.lstrip().startswith("$PortSpan")]
        self.assertTrue(span, "没有端口段的定义")
        self.assertIn("..", span[0],
                      f"端口段被收窄成单端口:{span[0].strip()!r} ⇒ 应用挪到 8767 就判它没活")
        p10 = [ln for ln in _probe_phase(src, "10").splitlines()
               if not ln.lstrip().startswith("#") and "Invoke-WebRequest" in ln]
        self.assertTrue(p10, "第 10 相没有自己的健康请求")
        p10_block = "\n".join(ln for ln in _probe_phase(src, "10").splitlines()
                               if not ln.lstrip().startswith("#"))
        self.assertIn("-Proxy $null", p10_block,
                      "第 10 相探针自己的健康检查没有旁路代理 ⇒ 它也走那条死代理 ⇒ 每趟假红")

    def test_s18_any_phase_saying_FAIL_makes_the_run_red(self):
        """退出码闸是全探针的安全网,而它自己一直没有判据(第 2c 轮 submimo 指出)。"""
        src = PROBE.read_text(encoding="utf-8")
        code = [ln for ln in src.splitlines() if not ln.lstrip().startswith("#")]
        failed = [ln for ln in code if "$failed" in ln and "=" in ln and "FAIL" in ln]
        self.assertTrue(failed, "闸不是从各相的自报 FAIL 里算出来的")
        self.assertTrue(any("-match" in ln or "-like" in ln for ln in failed),
                        "闸没有在各相的文案里找 FAIL")
        tail = "\n".join(code)
        self.assertIn("exit 1", tail, "有相自报 FAIL 时不 exit 1 ⇒ 红的 run 会绿着交差")
        self.assertIn("exit 0", tail, "没有显式 exit 0 ⇒ 退出码又回到 $LASTEXITCODE 泄漏")


class S19ProbeVerdictIsABehaviour(unittest.TestCase):
    """s19 探针的"机器事实 → 该不该 FAIL"必须是**跑得动的判定**,不是一段文本。

    🔴 为什么有这个类(2026-08-30 深夜,第三轮 panel 的 BLOCK):
    s18 那一整套是**静态断言** —— 它读 `.ps1` 的源码问"这句话在不在"。今晚这条路
    被连打回:M25/M27/M28/M30~M32、subgemini 的 M34~M37、submimo 的三条,
    最后 subdeepseek **自己动手变异了 8 种改法并逐条执行**(极性 `-eq`→`-lt`、
    把豁免的那份加进必须清单、`Test-Path` 取反、`$appTitle=''`、`-not` 去掉、
    while 条件少一项、`-like`→`-notlike`、`Cls($h)`→`Cls($l)`),**每一种 s18 都全绿**。

    形状是固定的:**字面断言天生够不着语义**。每补一条字面规则,下一层字面就能绕过去。

    ⇒ 出路(subdeepseek 与 subgemini 各自独立给的同一条):把判定从 `.ps1` 里抽出来,
    做成一个**纯函数**,喂事实、拿裁决。于是"极性/取值/终止条件/参数"全变成
    输入输出问题 —— 判据只要喂一组真实事实、断言裁决对不对,变异自然咬得住。

    `.ps1` 那边只剩一件事要静态钉:**它得真的去问这个函数**(见 s18 的接线断言)。
    """

    def setUp(self):
        import probe_verdict
        self.pv = probe_verdict

    # ── 第 8 相:收日志 ────────────────────────────────────────────────
    def test_s19_all_logs_present_is_ok(self):
        v = self.pv.logs_verdict({"外壳.log": 120, "工作台.log": 80, "网关.log": 40})
        self.assertTrue(v.ok, v.text)
        self.assertNotIn("FAIL", v.text)

    def test_s19_the_exempt_gateway_log_may_be_missing(self):
        """真机健康趟就是这个形状:没填 key ⇒ 网关不起 ⇒ 网关.log 合法缺席。"""
        v = self.pv.logs_verdict({"外壳.log": 120, "工作台.log": 80, "网关.log": None})
        self.assertTrue(v.ok, f"网关缺席被判成 FAIL ⇒ 每一趟健康的 run 都假红:{v.text}")

    def test_s19_a_missing_required_log_is_a_FAIL(self):
        v = self.pv.logs_verdict({"外壳.log": 120, "工作台.log": None, "网关.log": None})
        self.assertFalse(v.ok)
        self.assertIn("FAIL", v.text)
        self.assertIn("工作台.log", v.text)

    def test_s19_everything_missing_is_a_FAIL(self):
        """最该红的一种:现场是空的(应用根本没起来)。"""
        v = self.pv.logs_verdict({"外壳.log": None, "工作台.log": None, "网关.log": None})
        self.assertFalse(v.ok)
        self.assertIn("FAIL", v.text)

    # ── 第 6 相:窗口在不在 ────────────────────────────────────────────
    def test_s19_a_real_window_is_ok(self):
        v = self.pv.window_verdict(
            wins=[{"title": "OpenDesign", "cls": "WindowsForms10.Window.8.app.0.1"}],
            ours=["pythonw:「OpenDesign」"])
        self.assertTrue(v.ok, v.text)

    def test_s19_only_the_error_box_is_a_FAIL(self):
        """WebView2 缺失那类:后端活着、屏幕上只剩 alert()/die() 弹的框。"""
        v = self.pv.window_verdict(
            wins=[{"title": "OpenDesign", "cls": "#32770"}],
            ours=["pythonw:「OpenDesign」"])          # 框就是进程主窗口 ⇒ 老口径看得见它
        self.assertFalse(v.ok, "只有报错框却判成「窗口在」⇒ 软件根本打不开也整趟绿")
        self.assertIn("FAIL", v.text)

    def test_s19_a_box_next_to_a_real_window_is_still_ok(self):
        v = self.pv.window_verdict(
            wins=[{"title": "OpenDesign", "cls": "#32770"},
                  {"title": "OpenDesign", "cls": "WindowsForms10.Window.8.app.0.1"}],
            ours=["pythonw:「OpenDesign」"])
        self.assertTrue(v.ok, f"真窗口在场也被判红 ⇒ 假红:{v.text}")

    def test_s19_no_window_at_all_is_a_FAIL(self):
        v = self.pv.window_verdict(wins=[], ours=[])
        self.assertFalse(v.ok)
        self.assertIn("FAIL", v.text)

    def test_s19_enumeration_failure_falls_back_to_the_old_signal(self):
        """故意的 fail-open:一个窗口都枚举不到时退回老口径,别造假红。"""
        v = self.pv.window_verdict(wins=[], ours=["pythonw:「OpenDesign」"])
        self.assertTrue(v.ok, v.text)
        self.assertIn("枚举", v.text, "退回老口径时没把这件事写进读数 ⇒ 读数不诚实")

    def test_s19_the_cli_reads_utf8_facts_under_any_locale(self):
        """判定器**自己**也不许赌 locale:C locale 下喂 UTF-8 中文键,照样要判得对。

        (真跑那次坏在 PowerShell 那一侧,但同一条管道的两头都不该赌 —— 这一条
         本机验得了:`LC_ALL=C` 时 python 的 stdin 默认就是 ASCII。)
        """
        import json as _json, subprocess as _sp, sys as _sys, os as _os
        facts = {"present": {"外壳.log": 120, "工作台.log": None, "网关.log": None}}
        # 🔴 光设 LC_ALL=C **咬不动**:Python(PEP 538)会把 C 悄悄升成 C.UTF-8,
        #    于是这条判据看起来在验编码、其实永远绿 —— 那就是死断言。
        #    关掉强制升级(PYTHONCOERCECLOCALE=0)+ UTF-8 模式(PYTHONUTF8=0)之后,
        #    真跑那个假红在本机**原样复现**:同一份输入判成"外壳.log 缺席"。
        env = dict(_os.environ, LC_ALL="C", LANG="C", PYTHONIOENCODING="",
                   PYTHONCOERCECLOCALE="0", PYTHONUTF8="0")
        out = _sp.run([_sys.executable, str(ROOT / "bin" / "probe_verdict.py"), "logs"],
                      input=_json.dumps(facts, ensure_ascii=False).encode("utf-8"),
                      capture_output=True, env=env, timeout=60)
        text = out.stdout.decode("utf-8", "replace")
        self.assertEqual(out.returncode, 1, f"该判 FAIL 却给了 rc={out.returncode}:{text}")
        # 🔴 断言要盯**读到没读到那个值**。第一版写的是"文案里有没有 工作台.log" ——
        #    而那几个字来自 python 里的常量、**不是**来自输入,键全被打坏时它照样在,
        #    rc 也照样是 1 ⇒ 判据在坏的情况下也绿。`外壳.log 120B` 里的 120 只能从输入来。
        self.assertIn("外壳.log 120B", text,
                      f"中文键没活着穿过管道(在场的日志被判成缺席)⇒ 假红:{text!r}")

    def test_s19_every_kind_is_reachable_from_the_cli(self):
        """🔴 分发键改名(`window` → `win`)⇒ rc=2 + 用法串走 stderr ⇒ PowerShell 那边
        `2>&1` 把它当裁决 ⇒ 第 6 相静默绿。而原来两条 CLI 用例**只走 logs**,
        window/health 的分发完全裸奔(第 2d 轮 subdeepseek 实测)。
        """
        import json as _json, subprocess as _sp, sys as _sys
        cases = {
            "logs": ({"present": {"外壳.log": 1, "工作台.log": 2, "网关.log": None}}, 0),
            "window": ({"wins": [{"title": "OpenDesign", "cls": "#32770"}],
                        "ours": ["pythonw:「OpenDesign」"]}, 1),
            "health": ({"answers": {"8767": "0.98.2"}}, 0),
        }
        for kind, (facts, want_rc) in cases.items():
            out = _sp.run([_sys.executable, str(ROOT / "bin" / "probe_verdict.py"), kind],
                          input=_json.dumps(facts).encode("utf-8"),
                          capture_output=True, timeout=60)
            text = out.stdout.decode("utf-8", "replace").strip()
            self.assertEqual(out.returncode, want_rc,
                             f"kind={kind} 的 rc 不对(stdout={text!r} "
                             f"stderr={out.stderr.decode('utf-8','replace')!r})")
            self.assertTrue(text, f"kind={kind} 没有往 stdout 给一句裁决 ⇒ "
                                  "PowerShell 会把 stderr 当成裁决")

    def test_s19_the_cli_also_takes_ascii_escaped_facts(self):
        """PowerShell 那侧会把中文转成 ASCII 转义(\\uXXXX)再送进来 —— 这种形态也得判得对。"""
        import json as _json, subprocess as _sp, sys as _sys
        facts = {"present": {"外壳.log": 1, "工作台.log": 2, "网关.log": None}}
        out = _sp.run([_sys.executable, str(ROOT / "bin" / "probe_verdict.py"), "logs"],
                      input=_json.dumps(facts, ensure_ascii=True).encode("ascii"),
                      capture_output=True, timeout=60)
        self.assertEqual(out.returncode, 0,
                         f"网关缺席是合法的,却判了红:{out.stdout.decode('utf-8','replace')}")

    # ── 第 5/10 相:服务活了吗(端口会挪)──────────────────────────────
    def test_s19_health_on_the_moved_port_is_ok(self):
        """🔴 应用用 pick_ports(span=20) 挑端口,8766 被占会挪到 8767+;
        探针原来把 8766 写死 ⇒ 健康启动也判 FAIL(第三轮 subdeepseek 报的)。"""
        v = self.pv.health_verdict({8766: None, 8767: "0.98.2"})
        self.assertTrue(v.ok, f"应用挪到 8767 健康启动,却判成没活 ⇒ 假红:{v.text}")
        self.assertIn("8767", v.text)

    def test_s19_no_port_answering_is_a_FAIL(self):
        v = self.pv.health_verdict({p: None for p in range(8766, 8787)})
        self.assertFalse(v.ok)
        self.assertIn("FAIL", v.text)


if __name__ == "__main__":
    unittest.main()
