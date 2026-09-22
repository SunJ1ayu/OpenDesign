"""探路版管家(track opendesign-electron-shell,U2)。**不是产品代码。**

Electron 起它。它复用现有外壳的后台那一半 —— `ds_shell.start_backend`(挑端口、改配置、
起网关与工作台、Job)+ `ds_shell_core.InstanceLock`(ds-web「存 key 后重启网关」那条通道)。
窗口/托盘那一半(pywebview/pystray/WindowApi)一个都不碰:`import ds_shell` 不会导入 webview,
那只在 `ds_shell.main()` 里才发生。

协议:stdout 一行一个 JSON 事件;stdin 读到 EOF 或一行 `quit` = 收摊。
Electron 被杀时管道会断 ⇒ 这里读到 EOF ⇒ 照样收摊(E2 要量的就是这一条)。
"""
import json
import os
import sys
import threading

RES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RES, "ds", "bin"))

import ds_shell  # noqa: E402
import ds_shell_core as core  # noqa: E402

_out = threading.Lock()


def emit(event, **kw):
    with _out:
        sys.stdout.write(json.dumps({"event": event, **kw}, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def main():
    restart = []
    lock = core.InstanceLock(
        base_port=ds_shell.LOCK_PORT, span=5,
        on_show=lambda: emit("show"),
        on_restart=lambda: restart and restart[0](),
        on_update=lambda: emit("quit"))
    if not lock.acquire():
        emit("already-running")
        return 0
    try:
        home = ds_shell.user_home()
        sup, web, restart_gateway = ds_shell.start_backend(home, lock_port=lock.port)
        restart.append(restart_gateway)
        emit("ready", web_port=web)
        for line in sys.stdin:
            if line.strip() == "quit":
                break
        ds_shell.log("[管家] 收摊:stdin 断了或收到 quit")
        sup.shutdown()
    finally:
        lock.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
