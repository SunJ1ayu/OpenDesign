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
        d = ds_diag.StartupLog(emit=seen.append)
        with mock.patch("time.time", return_value=0.0):
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


if __name__ == "__main__":
    unittest.main()
