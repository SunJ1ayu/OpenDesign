"""启动可观测性 —— 让"这一次启动"留下查得动的证据。

**为什么有这个文件**(2026-08-30,track `opendesign-startup-observability`):
08-25 业主装 0.98.0 后「打开全是白的」,我们手上一条线索都没有 ——
日志没有日期、没有启动编号、没有分阶段耗时。到 08-30 结论仍只能写「站得住,不是铁证」。
同一天我还把「开窗要等 11 秒、因为每次现建临时档案」讲成了事实,
**而仓库里根本没有量过它**。所以:先有尺,再谈快慢。

设计上刻意克制的两处(别"顺手"加回来):
  · **不做"启动管理器"抽象**。就是一个 t0 + 一个 mark(),十几行。
    启动路径已经够挤了,为一个消费者建一层机制正是屎山的来路。
  · **超时不弹框**(判据 s9 钉死)。不弹框之后,"多少秒算白屏"这个阈值就
    **不再承重** —— 定错了最多多写一段日志,不会天天骚扰业主。
    误报和假绿一样坏,这个项目实证过很多次。

前端回叫是**网页能写进日志的口子** ⇒ 当不可信输入对待:白名单 + 限长 + 去重(s7)。
"""
from __future__ import annotations

import platform
import re
import secrets
import struct
import threading
import time
import zipfile
from pathlib import Path

# 前端只许报这几件事。名字之外的一律丢弃 —— 网页不能往日志里写任意事件名。
UI_EVENTS = frozenset({
    "frontend.bundle_started",     # JS 开始执行
    "frontend.react_committed",    # React 提交了第一棵树
    "frontend.frame_submitted",    # 浏览器提交了一帧
    "frontend.error",              # 未捕获异常
    "frontend.resource_failed",    # 脚本/样式没加载下来
})
DETAIL_CAP = 200                   # detail 截断长度,防网页把日志撑爆

# 官方文档给的常青运行时注册表位置(2026-08-30 从 learn.microsoft.com 读来的)
_WV2_KEY = r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

# 导出诊断包**只带**这三份日志。白名单是硬的:判据 s10 会摆上 key/配置/项目档案/
# 参考图库当诱饵,证明它们一个都进不去。
BUNDLE_LOGS = ("外壳.log", "工作台.log", "网关.log")
BUNDLE_TAIL_BYTES = 256 * 1024

# 🔴 请求行里的路径要涂抹(判据 s16;2026-08-30 四审 subdeepseek F3)。
# 白名单只管到**文件级**:`工作台.log` 里的
# `GET /api/files/overview/<项目名> HTTP/1.1` 会把业主的项目名和文件名带出去。
# 我跟业主说过"包里不会有项目档案、客户资料" —— 文件级成立、内容级不成立,
# 那是半真话。查启动只需要"打了哪个端点、什么状态",不需要知道是哪个客户
# ⇒ 只留前两段路径,后面一律涂掉。
_REQ_LINE = re.compile(r'"(?P<m>[A-Z]+) (?P<path>[^" ]+) (?P<v>HTTP/[\d.]+)"')


def _redact_request_line(line: str) -> str:
    def sub(m):
        head = m.group("path").split("?", 1)[0]
        parts = [p for p in head.split("/") if p]
        kept = "/" + "/".join(parts[:2])
        if len(parts) > 2:
            kept += "/<已涂抹>"
        return f'"{m.group("m")} {kept} {m.group("v")}"'
    return _REQ_LINE.sub(sub, line)


def webview2_version() -> str:
    """业主机器上的网页内核是哪一版。**这一行直击 08-25 那次白屏** ——
    那晚最关键的证据就是内核版本,而我们是靠他重启后去翻文件夹才知道的。"""
    try:
        import winreg
    except ImportError:
        return "不适用(非 Windows)"
    for hive in (getattr(__import__("winreg"), "HKEY_LOCAL_MACHINE", None),
                 getattr(__import__("winreg"), "HKEY_CURRENT_USER", None)):
        try:
            with winreg.OpenKey(hive, _WV2_KEY) as k:
                v = winreg.QueryValueEx(k, "pv")[0]
                if v and v != "0.0.0.0":
                    return str(v)
        except OSError:
            continue
    return "查不到(可能是自带内核或没装)"


def _app_version() -> str:
    """版本号的唯一来源在 ds_web —— 别在这里抄一份(抄件会过期,本项目栽过)。"""
    try:
        import ds_web
        return str(ds_web.VERSION)
    except Exception:
        return "未知"


class StartupLog:
    """一次启动的证据链。线程安全:前端回叫和窗口回调不在同一条线程上。"""

    def __init__(self, emit, clock=None, run_id=None):
        self._emit = emit
        # 🔴 单调钟,不是墙上时钟(判据 s4)。对时/夏令时会让 time.time() 往回跳,
        #    算出来的耗时就是错的。ds_shell_core.py:621 早就这么写了。
        self._clock = clock or time.monotonic
        self._t0 = self._clock()
        self.run_id = run_id or secrets.token_hex(3)
        self._marks: list[tuple[str, float]] = []
        self._ui_seen: set[str] = set()
        self._lock = threading.Lock()

    # -- 内部 ---------------------------------------------------------
    def _write(self, text: str) -> None:
        """🔴 观测层自己炸了不许拖垮启动(判据 s12)。
        这一层是**加进来查案的**,它绝不能成为新的故障源。"""
        try:
            self._emit(text)
        except Exception:
            pass

    def _elapsed_ms(self) -> float:
        return (self._clock() - self._t0) * 1000.0

    # -- 对外 ---------------------------------------------------------
    def mark(self, event: str, detail: str = "") -> None:
        ms = self._elapsed_ms()
        with self._lock:
            self._marks.append((event, ms))
        tail = f" {detail}" if detail else ""
        self._write(f"[启动] run={self.run_id} +{ms:.0f}ms {event}{tail}")

    def milestones(self) -> list[tuple[str, float]]:
        with self._lock:
            return list(self._marks)

    def manifest(self) -> str:
        bits = struct.calcsize("P") * 8
        return (f"[启动] run={self.run_id} 版本清单 "
                f"OpenDesign={_app_version()} "
                f"Windows={platform.platform()} "
                f"位数={bits} "
                f"Python={platform.python_version()} "
                f"WebView2={webview2_version()}")

    def report_from_ui(self, event: str, detail: str = "") -> bool:
        """前端报上来的。**不可信输入**:白名单 + 限长 + 去重(判据 s7)。"""
        if event not in UI_EVENTS:
            return False
        with self._lock:
            if event in self._ui_seen:
                return False
            self._ui_seen.add(event)
        self.mark(event, str(detail)[:DETAIL_CAP])
        return True

    def timeline_text(self) -> str:
        lines = [self.manifest()]
        lines += [f"+{ms:.0f}ms {name}" for name, ms in self.milestones()]
        return "\n".join(lines) + "\n"

    def export_bundle(self, out, app_dir) -> Path:
        """托盘那一项打的包。**白名单是硬的** —— 判据 s10 摆了诱饵证明别的进不去。

        白屏时窗口是废的、托盘还活着,所以这是业主唯一还能操作的地方;
        但它同时是"把文件打包交出去"的动作,所以只带该带的。
        """
        out, app_dir = Path(out), Path(app_dir)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("本次启动.txt", self.timeline_text())
            for name in BUNDLE_LOGS:
                p = app_dir / "Logs" / name
                try:
                    data = p.read_bytes()[-BUNDLE_TAIL_BYTES:]
                except OSError:
                    continue
                # 请求行里的路径涂抹掉(s16)。只对文本可解的部分做,解不出来就
                # 原样带走 —— 涂抹失败绝不能让导出整个失败(观测层不当故障源)。
                try:
                    text = data.decode("utf-8", "replace")
                    data = "".join(_redact_request_line(ln)
                                   for ln in text.splitlines(keepends=True)).encode("utf-8")
                except Exception:
                    pass
                z.writestr(f"Logs/{name}", data)
        return out


class FirstFrameWatch:
    """首帧没来就写一次诊断快照。**不弹框**(判据 s9)。"""

    def __init__(self, timeout, on_timeout, emit):
        self._timeout = float(timeout)
        self._on_timeout = on_timeout
        self._emit = emit
        self._seen = threading.Event()
        self._done = threading.Event()
        self._thread = None

    def _run(self) -> None:
        if not self._seen.wait(self._timeout):
            try:
                self._on_timeout()
            except Exception:
                pass
        self._done.set()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="ds-first-frame", daemon=True)
        self._thread.start()

    def seen(self) -> None:
        self._seen.set()

    def join(self, timeout=None) -> None:
        self._done.wait(timeout)
