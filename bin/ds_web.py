#!/usr/bin/env python3
"""ds_web — OpenDesign 工作台本地服务(纯 stdlib,track opendesign-workbench)。

静态服务 web/dist(Vite 构建产物) + 只读 API:
  GET /api/todos   ds_todo.collect() 结构化 JSON(每请求现读 PKB,零缓存)
  GET /api/health  存活探针(version + ds_root)
聊天代理(P1,docs/nanobot-ws-protocol.md;8765 零 CORS → 同源转发,纯管道零秘密):
  GET /api/chat/bootstrap             → 127.0.0.1:<nanobot>/webui/bootstrap
  GET /api/chat/sessions              → …/api/sessions
  GET /api/chat/sessions/<key>/thread → …/api/sessions/<key>/webui-thread
  白名单仅此三条;<key> 先验 [A-Za-z0-9_:.-]{1,128} 且拒 './..'(不 unquote,
  %xx 直接非法 → 转发段永远改不了上游路径结构);查询串原样透传;请求头只
  透传 Authorization / X-Nanobot-Auth;上游状态码原样回传(401 不吞,前端
  靠它透明重签);上游连不上 → 502。
其余方法一律 405 —— 无写面;将来写操作必须过 ds_tools 核心,本服务不直改 PKB。

约束(design.md D2):只绑 127.0.0.1;端口 DS_WEB_PORT(默认 8766),被占明确报错
退出不静默换口;JSON ensure_ascii=False + charset=utf-8;读期 OSError(Windows
msvcrt 强制锁窗口内并发读会瞬时报错)归入 500 路径,刷新自愈;静态路径
unquote → realpath → ds_common.within 防逃逸。
环境变量:DS_ROOT / DS_WEB_PORT / DS_WEB_DIST(测试注入用)/ DS_NANOBOT_PORT。
"""
import http.client
import json
import os
import re
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

import ds_common
import ds_todo

VERSION = "0.1.0"
DEFAULT_NANOBOT_PORT = 8765
# 与上游 _decode_api_key 同字符集;不含 % 和 / ⇒ 原样转发也无路径走私
_KEY_RE = re.compile(r"^[A-Za-z0-9_:.-]{1,128}$")
_THREAD_RE = re.compile(r"^/api/chat/sessions/([^/]+)/thread$")
DEFAULT_DS_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DEFAULT_DIST = os.path.join(DEFAULT_DS_ROOT, "web", "dist")
DEFAULT_PORT = 8766

_CTYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".map": "application/json; charset=utf-8",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


class Handler(BaseHTTPRequestHandler):
    server_version = f"ds-web/{VERSION}"

    # ---- helpers ----
    def _send(self, status: int, ctype: str, body: bytes, extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, obj):
        self._send(status, "application/json; charset=utf-8",
                   json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def log_message(self, fmt, *args):  # 请求日志走 stdout(design D2 运维面)
        sys.stdout.write("%s - %s\n" % (self.address_string(), fmt % args))

    # ---- routes ----
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/health":
            self._json(200, {"ok": True, "version": VERSION,
                             "ds_root": self.server.ds_root})
        elif path == "/api/todos":
            self._todos()
        elif path == "/api/chat/bootstrap":
            self._proxy("/webui/bootstrap")
        elif path == "/api/chat/sessions":
            self._proxy("/api/sessions")
        elif (m := _THREAD_RE.match(path)):
            key = m.group(1)  # 原样段,不 unquote(见模块头契约)
            if _KEY_RE.match(key) and key not in (".", ".."):
                self._proxy(f"/api/sessions/{key}/webui-thread")
            else:
                self._json(404, {"error": "bad key"})
        elif path.startswith("/api/"):
            self._json(404, {"error": "unknown api"})
        else:
            self._static(path)

    def _method_not_allowed(self):  # P0 只读:写方法焊死 405(oracle #5)
        body = json.dumps({"error": "read-only"}, ensure_ascii=False).encode("utf-8")
        self._send(405, "application/json; charset=utf-8", body,
                   {"Allow": "GET"})  # RFC 7231 §6.5.5:405 必带 Allow

    do_POST = do_PUT = do_DELETE = do_PATCH = _method_not_allowed

    def _todos(self):
        try:
            data = ds_todo.collect(self.server.ds_root)
        except Exception:
            # 含 Windows 写锁窗口内的读期 OSError(F3)与坏编码文件(F2):
            # 500 自愈路径,trace 进日志不进响应体
            traceback.print_exc()
            self._json(500, {"error": "internal"})
            return
        self._json(200, data)

    def _proxy(self, up_path: str):
        """白名单 GET 转发到本机 nanobot gateway。纯管道:不读不存任何秘密。"""
        q = urlsplit(self.path).query
        if q:
            up_path += "?" + q
        hdrs = {}
        for h in ("Authorization", "X-Nanobot-Auth"):  # 请求头白名单,其余剥离
            v = self.headers.get(h)
            if v is not None:
                hdrs[h] = v
        try:
            conn = http.client.HTTPConnection(
                "127.0.0.1", self.server.nanobot_port, timeout=30)
            try:
                conn.request("GET", up_path, headers=hdrs)
                r = conn.getresponse()
                body = r.read()
                status = r.status
                ctype = r.getheader("Content-Type") or "application/json; charset=utf-8"
            finally:
                conn.close()
        except OSError:  # gateway 没起/端口错:502 可辨,进程不挂
            self._json(502, {"error": "nanobot gateway unreachable"})
            return
        self._send(status, ctype, body)  # 状态码原样透传(含 401)

    def _static(self, path: str):
        raw = unquote(path)
        if "\\" in raw or "\x00" in raw:  # ..%5c 等 Windows 分隔符变体直接拒
            self._json(400, {"error": "bad path"})
            return
        rel = raw.lstrip("/") or "index.html"
        dist = self.server.dist  # 已 realpath(make_server 保证)
        target = os.path.realpath(os.path.join(dist, rel))
        if not ds_common.within(dist, target) or not os.path.isfile(target):
            self._json(404, {"error": "not found"})
            return
        ext = os.path.splitext(target)[1].lower()
        ctype = _CTYPES.get(ext, "application/octet-stream")
        # 缓存策略:入口页永远现取,哈希资产长缓存(git pull 后刷新即新版)
        cache = ("no-cache" if os.path.basename(target) == "index.html"
                 else "public, max-age=31536000, immutable")
        try:
            with open(target, "rb") as fh:
                body = fh.read()
        except OSError:  # git pull 覆盖 dist 的瞬间并发读:同 _todos,500 自愈
            traceback.print_exc()
            self._json(500, {"error": "internal"})
            return
        self._send(200, ctype, body, {"Cache-Control": cache})


def make_server(ds_root: str, dist: str, host: str = "127.0.0.1",
                port: int = DEFAULT_PORT,
                nanobot_port: int = DEFAULT_NANOBOT_PORT) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), Handler)  # allow_reuse_address 已内建
    httpd.ds_root = ds_root
    httpd.dist = os.path.realpath(dist)
    httpd.nanobot_port = nanobot_port  # 代理上游恒 127.0.0.1,仅端口可配
    return httpd


def main() -> int:
    ds_root = os.environ.get("DS_ROOT", DEFAULT_DS_ROOT)
    dist = os.environ.get("DS_WEB_DIST", DEFAULT_DIST)
    port = int(os.environ.get("DS_WEB_PORT", str(DEFAULT_PORT)))
    nanobot_port = int(os.environ.get("DS_NANOBOT_PORT", str(DEFAULT_NANOBOT_PORT)))
    if not os.path.isfile(os.path.join(dist, "index.html")):
        print(f"ds-web: 前端产物缺失 {dist}/index.html —— 先在开发机构建"
              f"(cd web && npm run build)或 git pull 取最新", file=sys.stderr)
        return 2
    try:
        httpd = make_server(ds_root, dist, port=port, nanobot_port=nanobot_port)
    except OSError as e:
        print(f"ds-web: 端口 {port} 起不来({e});被占用请设 DS_WEB_PORT 换端口",
              file=sys.stderr)
        return 2
    print(f"ds-web {VERSION}: http://127.0.0.1:{port}/  (DS_ROOT={ds_root})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
