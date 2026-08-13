#!/usr/bin/env python3
"""OpenDesign 桌面外壳的平台无关内核。"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class PortBusy(RuntimeError):
    """端口段全被占。"""


class StartupFailed(RuntimeError):
    """子进程启动失败。"""


class ConfigUnusable(RuntimeError):
    """配置本身无法安全使用。"""


def port_free(port: int, host: str = "127.0.0.1") -> bool:
    """端口是否可以被当前进程绑定。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, int(port)))
        return True
    except OSError:
        return False
    finally:
        s.close()


def port_listening(port: int, host: str = "127.0.0.1") -> bool:
    """端口上是否有 TCP 服务正在接受连接。"""
    try:
        with socket.create_connection((host, int(port)), timeout=0.25):
            return True
    except OSError:
        return False


def pick_port(preferred: int, *, span: int = 20) -> int:
    start = int(preferred)
    for port in range(start, start + int(span) + 1):
        if port_free(port):
            return port
    raise PortBusy(f"端口段 {start}..{start + int(span)} 全部被占")


def pick_ports(preferred: list[int], *, span: int = 20) -> list[int]:
    chosen: list[int] = []
    used: set[int] = set()
    for wanted in preferred:
        start = int(wanted)
        for port in range(start, start + int(span) + 1):
            if port not in used and port_free(port):
                chosen.append(port)
                used.add(port)
                break
        else:
            raise PortBusy(f"端口段 {start}..{start + int(span)} 没有可用端口")
    return chosen


def lock_sockopts(platform: str) -> list[tuple[str, int]]:
    if platform.startswith("win"):
        return [("SO_EXCLUSIVEADDRUSE", int(getattr(socket, "SO_EXCLUSIVEADDRUSE", 4)))]
    return []


class InstanceLock:
    _HELLO = b"OpenDesign.ds_shell_core.lock.v1\n"
    _SHOW = b"SHOW\n"
    _OK = b"OK\n"

    port: int | None
    _sock: socket.socket | None

    def __init__(self, base_port: int, span: int = 5, on_show=None):
        self.base_port = int(base_port)
        self.span = int(span)
        self.on_show = on_show
        self.port = None
        self._sock = None
        self._thread: threading.Thread | None = None
        self._released = threading.Event()

    def acquire(self) -> bool:
        # 第一份可能落在备用锁位上，所以先扫完整段握手，再尝试占新锁。
        for port in self._ports():
            if self._send_show(port):
                self.port = port
                return False

        for port in self._ports():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                for name, value in lock_sockopts(sys.platform):
                    opt = getattr(socket, name, None)
                    if opt is not None:
                        sock.setsockopt(socket.SOL_SOCKET, opt, value)
                sock.bind(("127.0.0.1", port))
                sock.listen(8)
            except OSError:
                sock.close()
                continue
            self._sock = sock
            self.port = port
            self._thread = threading.Thread(target=self._serve, name="ds-shell-lock", daemon=True)
            self._thread.start()
            return True

        raise PortBusy(f"单实例锁端口段 {self.base_port}..{self.base_port + self.span} 全部被占")

    def release(self) -> None:
        self._released.set()
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        self.port = None

    def _ports(self):
        return range(self.base_port, self.base_port + self.span + 1)

    def _send_show(self, port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.35) as s:
                s.settimeout(0.35)
                s.sendall(self._HELLO + self._SHOW)
                return s.recv(32) == self._OK
        except OSError:
            return False

    def _serve(self) -> None:
        assert self._sock is not None
        while not self._released.is_set():
            try:
                conn, _ = self._sock.accept()
            except OSError:
                break
            with conn:
                try:
                    conn.settimeout(1.0)
                    data = conn.recv(1024)
                    if data.startswith(self._HELLO) and self._SHOW in data:
                        conn.sendall(self._OK)
                        if self.on_show is not None:
                            self.on_show()
                except OSError:
                    pass


@dataclass
class Service:
    name: str
    argv: list[str]
    env: dict
    ready_port: int
    log_path: Path
    ready_timeout: float = 60.0


@dataclass
class _Managed:
    service: Service
    proc: subprocess.Popen
    log_file: Any
    job_handle: Any = None


class Supervisor:
    def __init__(self):
        self._children: list[_Managed] = []
        self._shutdown_lock = threading.Lock()

    def start(self, services: list[Service]) -> None:
        ports = [int(s.ready_port) for s in services]
        if len(set(ports)) != len(ports):
            raise StartupFailed(f"服务端口重复: {ports}")
        for svc in services:
            if not port_free(int(svc.ready_port)):
                raise StartupFailed(f"{svc.name} 的端口 {svc.ready_port} 已被占用")

        try:
            for svc in services:
                child = self._spawn(svc)
                self._children.append(child)
                self._wait_ready(child)
        except StartupFailed:
            self.shutdown()
            raise

    def shutdown(self) -> None:
        with self._shutdown_lock:
            children = list(self._children)
            if not children:
                return

            for child in children:
                self._terminate_tree(child)

            deadline = time.monotonic() + 4.0
            while time.monotonic() < deadline:
                if all(child.proc.poll() is not None for child in children):
                    break
                time.sleep(0.05)

            for child in children:
                if child.proc.poll() is None:
                    self._kill_tree(child)

            final_deadline = time.monotonic() + 4.0
            for child in children:
                remaining = max(0.0, final_deadline - time.monotonic())
                try:
                    child.proc.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    pass

            for child in children:
                self._close_job(child)
                try:
                    child.log_file.close()
                except Exception:
                    pass
            self._children.clear()

    def poll_dead(self) -> list[str]:
        return [child.service.name for child in self._children if child.proc.poll() is not None]

    def _spawn(self, svc: Service) -> _Managed:
        log_path = Path(svc.log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = log_path.open("ab")
        kwargs: dict[str, Any] = {
            "stdout": log_file,
            "stderr": subprocess.STDOUT,
            "env": {str(k): str(v) for k, v in svc.env.items()},
        }
        if os.name == "posix":
            kwargs["start_new_session"] = True
        elif os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            proc = subprocess.Popen([str(x) for x in svc.argv], **kwargs)
        except Exception as exc:
            try:
                log_file.close()
            except Exception:
                pass
            raise StartupFailed(f"{svc.name} 启动失败: {exc}") from exc
        child = _Managed(service=svc, proc=proc, log_file=log_file)
        if os.name == "nt":
            child.job_handle = self._assign_windows_job(proc)
        return child

    def _wait_ready(self, child: _Managed) -> None:
        svc = child.service
        deadline = time.monotonic() + float(svc.ready_timeout)
        while True:
            code = child.proc.poll()
            if code is not None:
                raise StartupFailed(self._failure_message(svc, f"退出码 {code}", code))
            if port_listening(int(svc.ready_port)):
                return
            now = time.monotonic()
            if now >= deadline:
                raise StartupFailed(self._failure_message(svc, "启动超时", None))
            time.sleep(min(0.1, max(0.0, deadline - now)))

    def _failure_message(self, svc: Service, reason: str, code: int | None) -> str:
        tail = self._log_tail(Path(svc.log_path))
        parts = [f"{svc.name} 启动失败: {reason}"]
        if code is not None:
            parts.append(f"退出码: {code}")
        parts.append(f"日志尾巴:\n{tail}")
        return "\n".join(parts)

    def _log_tail(self, path: Path, limit: int = 4000) -> str:
        try:
            with path.open("rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - limit))
                data = f.read()
            text = data.decode("utf-8", errors="replace").strip()
            return text or "(日志为空)"
        except OSError:
            return "(读不到日志)"

    def _terminate_tree(self, child: _Managed) -> None:
        if child.proc.poll() is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(child.proc.pid, signal.SIGTERM)
            else:
                child.proc.terminate()
        except Exception:
            pass

    def _kill_tree(self, child: _Managed) -> None:
        if child.proc.poll() is not None:
            return
        if os.name == "posix":
            try:
                os.killpg(child.proc.pid, signal.SIGKILL)
                return
            except Exception:
                pass
        else:
            if child.job_handle:
                self._close_job(child)
                return
            try:
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(child.proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    check=False,
                )
                return
            except Exception:
                pass
        try:
            child.proc.kill()
        except Exception:
            pass

    def _assign_windows_job(self, proc: subprocess.Popen):
        if os.name != "nt":
            return None
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            job = kernel32.CreateJobObjectW(None, None)
            if not job:
                return None

            class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
                    ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD),
                ]

            class IO_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("ReadOperationCount", ctypes.c_ulonglong),
                    ("WriteOperationCount", ctypes.c_ulonglong),
                    ("OtherOperationCount", ctypes.c_ulonglong),
                    ("ReadTransferCount", ctypes.c_ulonglong),
                    ("WriteTransferCount", ctypes.c_ulonglong),
                    ("OtherTransferCount", ctypes.c_ulonglong),
                ]

            class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]

            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            ok = kernel32.SetInformationJobObject(
                job, 9, ctypes.byref(info), ctypes.sizeof(info)
            )
            if not ok:
                kernel32.CloseHandle(job)
                return None
            if not kernel32.AssignProcessToJobObject(job, proc._handle):
                kernel32.CloseHandle(job)
                return None
            return job
        except Exception:
            return None

    def _close_job(self, child: _Managed) -> None:
        if os.name != "nt" or not child.job_handle:
            return
        try:
            import ctypes

            ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(child.job_handle)
        except Exception:
            pass
        child.job_handle = None


def patch_config(path, *, gateway_port: int, ws_port: int, python_exe: str) -> None:
    cfg_path = Path(path)
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    ws = cfg.get("channels", {}).get("websocket", {})
    if ws.get("enabled") is not True:
        raise ConfigUnusable("websocket 通道未开启，请登录并启用带口令的通道后再启动")
    if not ws.get("token"):
        raise ConfigUnusable("websocket 通道缺少口令，请登录后生成口令再启动")

    cfg.setdefault("gateway", {})["port"] = int(gateway_port)
    ws["port"] = int(ws_port)

    servers = cfg.get("tools", {}).get("mcpServers", {})
    if isinstance(servers, dict):
        for server in servers.values():
            if isinstance(server, dict):
                server["command"] = str(python_exe)

    tmp_name: str | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{cfg_path.name}.", suffix=".tmp", dir=str(cfg_path.parent)
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        try:
            mode = cfg_path.stat().st_mode
            os.chmod(tmp_name, mode)
        except OSError:
            pass
        os.replace(tmp_name, cfg_path)
        tmp_name = None
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def child_env(
    base_env: dict,
    *,
    ds_root: str,
    user_home: str,
    dsweb_port: int,
    ws_port: int,
    key: str | None = None,
) -> dict:
    env: dict[str, str] = {}
    for k, v in base_env.items():
        name = str(k)
        upper = name.upper()
        if upper in {"PYTHONPATH", "PYTHONHOME"} or upper.startswith("DS_"):
            continue
        env[name] = str(v)

    env.update(
        {
            "DS_ROOT": str(ds_root),
            "DS_WEB_PORT": str(dsweb_port),
            "DS_NANOBOT_PORT": str(ws_port),
            "HOME": str(user_home),
            "USERPROFILE": str(user_home),
            "PYTHONIOENCODING": "utf-8",
        }
    )
    if key:
        env["DS_LLM_KEY"] = str(key)
    return env


class ShellState:
    visible: bool
    exiting: bool

    def __init__(self, ui, on_stop):
        self.ui = ui
        self.on_stop = on_stop
        self.visible = True
        self.exiting = False

    def on_close_requested(self) -> bool:
        if self.exiting:
            return True
        self.ui.hide_window()
        self.visible = False
        return False

    def on_show(self) -> None:
        if self.exiting:
            return
        self.ui.show_window()
        self.visible = True

    def on_quit(self) -> None:
        if self.exiting:
            return
        self.exiting = True
        self.visible = False
        self.on_stop()
        self.ui.destroy()
