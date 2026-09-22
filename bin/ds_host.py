#!/usr/bin/env python3
"""OpenDesign 的管家(track opendesign-electron-shell,2026-09-22 换 Electron 起)。

Electron 主进程起它:`resources\\python\\python.exe resources\\ds\\bin\\ds_host.py`。
它做窗口之外、原来外壳做的那些事:拿单实例锁(ds-web「存 key 后重启网关」那条通道)、
起网关与工作台(`ds_shell.start_backend`)、看门狗、首帧看门、导出诊断。
窗口、托盘、更新都在 Electron 那边(`desktop/`)。

两边只靠**一根管道里的一行行 JSON** 说话(协议见 design.md「Test strategy」接缝表):
  stdout(管家 → Electron):`ready{web_port,version}` / `show` / `already-running` / `fatal{message}` /
          `alert{message}` / `backend-died{names,message}` / `diagnostics{path}` 或 `diagnostics{error}`
  stdin (Electron → 管家):`quit` / `export-diagnostics` / `report{event,detail}` / `window-shown`;
          **stdin EOF = 收摊**(Electron 被硬杀时管道断,管家自己把整棵后台树收掉)。

这根管道的坏法都是**安静的**,每条都有判据(tests/test_ds_host.py):
  · 中文 Windows 上被重定向的 stdout 默认按 cp936 编码,Node 按 UTF-8 读 ⇒ 业主看到乱码(h14)
    ⇒ `serve` 只收**字节流**,编码在这里定死成 UTF-8;
  · 一条事件分两次写,看门狗线程和锁回调同时发时会粘成一行,Electron 整行丢弃(h13b)⇒ 一次写完、带锁;
  · 起后台失败时 `ds_shell.die()` 会弹 MessageBox,Electron 再弹一个 ⇒ 同一个错两个框(h5)
    ⇒ 管家在跑的时候,`ds_shell` 的 `alert` / `die` 改成往管道里发事件,框由 Electron 弹(父窗口是它、在最前面)。
"""
from __future__ import annotations

import json
import sys
import threading
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ds_diag  # noqa: E402
import ds_shell  # noqa: E402  后台那一半:start_backend / 日志 / 诊断时间线
import ds_shell_core as core  # noqa: E402

APP = ds_shell.APP


class _Fatal(Exception):
    """`ds_shell.die(msg)` 在管家里的样子:带着那句人话一路抛回 serve,由它发一条 `fatal`。"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _version() -> str:
    """版本号只有一个来源:`bin/ds_web.py` 的 VERSION(Electron 拿它比 app.getVersion(),抓半新半旧)。"""
    try:
        import ds_web
        return str(ds_web.VERSION)
    except Exception:
        return "未知"


class _Pipe:
    """stdout 那一头。**一条事件一次 write**、带锁 —— 主循环、看门狗、锁回调、首帧看门四条线程都会写。"""

    def __init__(self, out, log):
        self._out = out
        self._log = log
        self._lock = threading.Lock()

    def emit(self, event: str, **fields) -> None:
        data = (json.dumps({"event": event, **fields}, ensure_ascii=False) + "\n").encode("utf-8")
        with self._lock:
            try:
                self._out.write(data)
                self._out.flush()
            except (OSError, ValueError) as exc:
                # Electron 已经走了(管道断)。别让写失败把管家带崩 —— 它马上会读到 EOF,照常收摊。
                self._log(f"[管家] 写不进管道({exc.__class__.__name__}):{event}")


def serve(inp, out, *, make_lock, start_backend, home, diag, app_dir, log,
          watch_interval: float = 3.0, first_frame_timeout: float = 90.0) -> int:
    """管家的全部行为。`inp` / `out` 是**字节流**;依赖全部注入(判据用假件跑)。返回进程退出码。"""
    pipe = _Pipe(out, log)
    app_dir = Path(app_dir)
    logs_dir = app_dir / "Logs"
    restart_holder: list = []
    stopping = threading.Event()

    # ---- 管家在跑的时候,ds_shell 的两个出口改成往管道里说 ----------------------
    def _alert(msg, title=APP):
        log(f"[提示] {msg}")
        pipe.emit("alert", message=str(msg))

    def _die(msg):
        log(f"[提示] {msg}")
        raise _Fatal(str(msg))

    saved = (ds_shell.alert, ds_shell.die)
    ds_shell.alert, ds_shell.die = _alert, _die

    def on_restart():
        """ds-web:业主在界面里存好了 key ⇒ 请求重启网关。跑在锁的线程里,炸出去会把那条线程带走。"""
        if not restart_holder:
            log("[重启网关] 收到请求,但后台还没起好 —— 不动")
            return
        try:
            restart_holder[0]()
        except Exception as exc:
            log(f"[重启网关] 失败:{exc!r}")
            _alert(f"key 已经存好了,但后台没能自己重启:\n{exc}\n\n请退出 {APP} 再打开一次。")

    lock = make_lock(on_show=lambda: pipe.emit("show"), on_restart=on_restart)
    sup = None
    try:
        # ① 单实例锁。Electron 的锁先拿了;万一还是撞上一份在跑的管家 ⇒ 说一声、不起第二套后台(表 #9)。
        try:
            if not lock.acquire():
                log("[管家] 已有一份在跑,不起第二套后台")
                pipe.emit("already-running")
                return 0
        except core.PortBusy as exc:
            pipe.emit("fatal", message=f"启动失败:{exc}\n\n多半是有别的程序占着这几段端口,重启电脑再试一次。")
            return 1
        diag.mark("lock.acquired",
                  f"port={lock.port} 扫了{getattr(lock, 'scanned', '?')}格 "
                  f"用时{getattr(lock, 'scan_ms', 0.0):.0f}ms")

        # ② 起后台。每条失败都是 die(一句人话)⇒ 一条 fatal,由 Electron 弹那一个框。
        try:
            sup, web_port, restart_gateway = start_backend(home, lock_port=lock.port)
        except _Fatal as f:
            pipe.emit("fatal", message=f.message)
            return 1
        except SystemExit:
            pipe.emit("fatal", message=f"{APP} 没能启动。\n\n详细日志:{logs_dir}")
            return 1
        except Exception as exc:
            log(traceback.format_exc())
            pipe.emit("fatal", message=f"{APP} 启动时出错:{exc}\n\n详细日志:{logs_dir}")
            return 1
        diag.mark("backend.ready")
        restart_holder.append(restart_gateway)
        pipe.emit("ready", web_port=web_port, version=_version())

        # ③ 看门狗:哪条腿死了要说话,不能让界面一直转圈。**只看一眼**(c21):问 take_dead,
        #    名字和原因同一眼拿到;两眼之间名册会变(业主正好存了 key 触发重启),原因会丢。
        def watchdog():
            while not stopping.is_set():
                found = sup.take_dead()
                # 收摊时两条腿当然会退出 —— 那不是「意外」,不许为它吓业主一跳(h7b)
                if stopping.is_set():
                    return
                if found:
                    names = [name for name, _ in found]
                    for _, report in found:
                        log(f"[后台退出] {report}")      # 退出码与日志尾进日志,弹窗只说人话
                    pipe.emit("backend-died", names=names,
                              message=(f"{'、'.join(names)} 意外退出了。\n\n"
                                       f"请退出后重新打开 {APP};日志在:\n{logs_dir}\n\n"
                                       f"(把 外壳.log 发给我,里面有它的退出码和最后几句话。)"))
                    return
                stopping.wait(watch_interval)

        threading.Thread(target=watchdog, name="ds-host-watchdog", daemon=True).start()

        # ④ 首帧看门:窗口出来了,到点还没等到前端报「画出来了」⇒ 写一次现场。**不弹框**(s9)。
        frame = {"watch": None, "seen": False}

        def first_frame_missing():
            """🔴 不许在这里叫 `sup.take_dead()` —— 它是破坏性的,问一次就把死因从看门狗那边取走了。"""
            log("[启动] 🔴 到点还没等到界面画出来 —— 下面是现场,不是报错弹窗。")
            for name, ms in diag.milestones():
                log(f"[启动]   已到达 +{ms:.0f}ms {name}")
            try:
                # 绕开系统代理(见 ds_shell.web_ready_probe 的注释)
                import urllib.request
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(f"http://127.0.0.1:{int(web_port)}/api/health", timeout=3) as r:
                    log(f"[启动]   /api/health 通,HTTP {r.status} ⇒ 后端是活的,问题在网页那一层")
            except Exception as exc:
                log(f"[启动]   /api/health 不通:{exc!r} ⇒ 问题可能在后端")
            log("[启动]   右下角托盘 → 「导出本次启动诊断」可以把这些打包发出来。")

        def window_shown():
            # 🔴 只上一次膛(s14):托盘还原会再发一次 window-shown,而页面只在加载时报一次首帧
            #    ⇒ 再上膛必然超时 ⇒ 每次还原都写一段假诊断。
            if frame["watch"] is not None:
                return
            diag.mark("window.shown")
            frame["watch"] = ds_diag.FirstFrameWatch(
                timeout=first_frame_timeout, on_timeout=first_frame_missing, emit=log)
            frame["watch"].start()
            if frame["seen"]:            # 首帧比「窗口出来了」还先到(页面在隐藏窗口里先画好了)
                frame["watch"].seen()

        def report(event, detail):
            # 网页能写进日志的唯一口子 ⇒ 不可信输入:白名单 / 限长 / 去重全在 report_from_ui(s7)
            diag.report_from_ui(str(event), str(detail))
            if event == "frontend.frame_submitted":
                frame["seen"] = True
                if frame["watch"] is not None:
                    frame["watch"].seen()

        def export_diagnostics():
            """托盘「导出本次启动诊断」。白屏时窗口是废的、托盘还活着。
            打开文件夹是 Electron 的事(`shell.showItemInFolder`,在业主那个桌面会话里)——管家只出包、报位置。"""
            try:
                bundle = app_dir / f"OpenDesign-诊断-{diag.run_id}.zip"
                diag.export_bundle(bundle, app_dir=app_dir)
                log(f"[启动] 已导出诊断:{bundle}")
                pipe.emit("diagnostics", path=str(bundle))
            except Exception as exc:
                log(f"[启动] 导出诊断失败:{exc!r}")
                pipe.emit("diagnostics", error=f"导出诊断没成功:{exc}\n\n日志在:\n{logs_dir}")

        # ⑤ 读命令,直到 quit 或 EOF。坏行忽略,不许把管家带崩(h3b)。
        for raw in iter(inp.readline, b""):
            try:
                msg = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                log(f"[管家] 管道里来了一行认不出的:{raw[:80]!r}")
                continue
            if not isinstance(msg, dict):
                log(f"[管家] 管道里来了一行不是命令的:{raw[:80]!r}")
                continue
            cmd = msg.get("cmd")
            if cmd == "quit":
                break
            elif cmd == "window-shown":
                window_shown()
            elif cmd == "report":
                report(msg.get("event", ""), msg.get("detail", ""))
            elif cmd == "export-diagnostics":
                export_diagnostics()
            else:
                log(f"[管家] 不认识的命令,忽略:{cmd!r}")
        log("[管家] 收摊:停两条腿")
        return 0
    finally:
        stopping.set()
        try:
            if sup is not None:
                sup.shutdown()
        finally:
            lock.release()
            ds_shell.alert, ds_shell.die = saved


def main() -> int:
    ds_shell.DIAG.mark("main.entered")
    ds_shell.log(f"==== {APP} 管家启动 ====")
    # 版本清单先写 —— 万一后面炸了,至少知道是哪一版、哪个系统上炸的。
    ds_shell.log(ds_shell.DIAG.manifest())
    ds_shell.DIAG.mark("manifest.done")
    return serve(sys.stdin.buffer, sys.stdout.buffer,
                 make_lock=lambda **cb: core.InstanceLock(base_port=ds_shell.LOCK_PORT, span=5, **cb),
                 start_backend=ds_shell.start_backend, home=ds_shell.user_home(),
                 diag=ds_shell.DIAG, app_dir=ds_shell._app_dir(), log=ds_shell.log)


if __name__ == "__main__":
    sys.exit(main())
