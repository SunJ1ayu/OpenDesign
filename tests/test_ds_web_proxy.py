#!/usr/bin/env python3
"""ds_web 聊天代理 oracle — track opendesign-workbench-p1 T1(design Test strategy 1-3)。

跑法:  python3 tests/test_ds_web_proxy.py
red-check:本文件先于代理实现落仓(2026-07-08),此时 make_server 无
nanobot_port 参数,全体 TypeError 即 red 证明。
XSS 闸(Test strategy #4)属前端渲染,oracle 在 T5/T9(组件/Playwright),不在本文件。

契约(design.md D-C1,plan v2):
  make_server(ds_root, dist, port=0, nanobot_port=<mock>) 起代理;
  白名单三条 GET(其余 /api/chat/* 一律 404,不碰上游):
    /api/chat/bootstrap                  → /webui/bootstrap
    /api/chat/sessions                   → /api/sessions
    /api/chat/sessions/<key>/thread      → /api/sessions/<key>/webui-thread
  <key> 先验 [A-Za-z0-9_:.-]{1,128},非法 404 且零上游请求;
  查询串原样透传;请求头只透传 Authorization / X-Nanobot-Auth;
  上游连不上 → 502 JSON;上游状态码(含 401)原样透传不吞;
  写方法 405+Allow: GET(P0 只读不变量延续)。
纯 stdlib、离线、端口 0,不烧 LLM。
"""
import http.client
import json
import os
import socket
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # design-studio/
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_web  # noqa: E402


# ---------- 记录型 mock 上游 ----------

class _UpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        srv = self.server
        srv.requests.append({
            "method": "GET",
            "path": self.path,  # 含查询串,原样
            "headers": {k.lower(): v for k, v in self.headers.items()},
        })
        base = self.path.split("?", 1)[0]
        status, obj = srv.script.get(base, (200, {"ok": True, "path": base}))
        body = b"" if obj is None else json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@contextmanager
def _upstream(script=None):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _UpHandler)
    httpd.requests = []
    httpd.script = script or {}
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()


# ---------- 被测服务 ----------

def _mkdist() -> str:
    d = tempfile.mkdtemp(prefix="ds_web_proxy_dist_")
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<!doctype html><div>x</div>")
    return d


@contextmanager
def _serve(nanobot_port: int):
    root = tempfile.mkdtemp(prefix="ds_web_proxy_root_")
    os.makedirs(os.path.join(root, "projects"))
    httpd = ds_web.make_server(root, _mkdist(), port=0, nanobot_port=nanobot_port)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()


def _req(port: int, path: str, method: str = "GET", headers: dict | None = None,
         body: bytes | None = None):
    """裸 http.client:路径原样上线(urllib 会预规范化,测不到服务端校验)。"""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request(method, path, body=body, headers=headers or {})
    r = conn.getresponse()
    body = r.read()
    hd = {k.lower(): v for k, v in r.getheaders()}
    conn.close()
    return r.status, hd, body


def _dead_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class TestChatProxy(unittest.TestCase):

    # ① bootstrap 映射 + Authorization 原样透传 + 响应原样回传
    def test_01_bootstrap_forward(self):
        script = {"/webui/bootstrap": (200, {"token": "nbwt_x", "ws_path": "/",
                                             "expires_in": 300})}
        with _upstream(script) as up, _serve(up.server_address[1]) as port:
            # 口令值恒 ASCII(HTTP 头 latin-1 约束,浏览器 fetch 同禁非 ASCII)
            st, hd, body = _req(port, "/api/chat/bootstrap",
                                headers={"Authorization": "Bearer secret-abc"})
            self.assertEqual(st, 200)
            self.assertIn("application/json", hd["content-type"])
            self.assertEqual(json.loads(body.decode("utf-8"))["token"], "nbwt_x")
            self.assertEqual(len(up.requests), 1)
            r = up.requests[0]
            self.assertEqual(r["path"], "/webui/bootstrap")
            self.assertEqual(r["headers"].get("authorization"), "Bearer secret-abc")

    # ② sessions 映射 + 查询串原样透传(含 ?token=)
    def test_02_sessions_query_passthrough(self):
        with _upstream() as up, _serve(up.server_address[1]) as port:
            q = "?limit=2&direction=latest&before=abc&token=tk1"
            st, _, _ = _req(port, "/api/chat/sessions" + q)
            self.assertEqual(st, 200)
            self.assertEqual(up.requests[0]["path"], "/api/sessions" + q)

    # ③ thread 映射:<key> 合法字符集全覆盖 + 查询串
    def test_03_thread_forward(self):
        key = "websocket:aB3_x.y-9"
        with _upstream() as up, _serve(up.server_address[1]) as port:
            st, _, _ = _req(port, f"/api/chat/sessions/{key}/thread?limit=1")
            self.assertEqual(st, 200)
            self.assertEqual(up.requests[0]["path"],
                             f"/api/sessions/{key}/webui-thread?limit=1")

    # ④ 非法 key 一律 404 且零上游请求(路径走私闸)
    def test_04_bad_key_rejected(self):
        # 裸空格/裸非 ASCII 不列:请求行里不合法,http 栈(含测试客户端)
        # 在到达路由前就拒;wire 上真实形状是 %xx,而 % 本身就在闸外
        bad = ["..", "%2e%2e", "a%2fb", "a%20b", "%e2%82%ac",
               "a" * 129, "x%00y"]
        with _upstream() as up, _serve(up.server_address[1]) as port:
            for k in bad:
                st, _, _ = _req(port, f"/api/chat/sessions/{k}/thread")
                self.assertEqual(st, 404, f"key={k!r} 应 404")
            # 空 key(裸双斜线)同拒
            st, _, _ = _req(port, "/api/chat/sessions//thread")
            self.assertEqual(st, 404)
            self.assertEqual(up.requests, [], "非法 key 不得触达上游")

    # ⑤ 白名单外 /api/chat/* 一律 404 且零上游请求
    def test_05_non_whitelist_404(self):
        paths = ["/api/chat/bootstrap/extra", "/api/chat/other",
                 "/api/chat/sessions/k/thread/x", "/api/chat/", "/api/chat"]
        with _upstream() as up, _serve(up.server_address[1]) as port:
            for p in paths:
                st, _, _ = _req(port, p)
                self.assertEqual(st, 404, f"path={p} 应 404")
            self.assertEqual(up.requests, [])

    # ⑥ 写方法 405+Allow(P0 只读不变量延续到代理路径)
    def test_06_write_methods_405(self):
        with _upstream() as up, _serve(up.server_address[1]) as port:
            for m in ("POST", "PUT", "DELETE", "PATCH"):
                st, hd, _ = _req(port, "/api/chat/bootstrap", method=m)
                self.assertEqual(st, 405)
                self.assertEqual(hd.get("allow"), "GET")
            self.assertEqual(up.requests, [])

    # ⑦ 上游不可达 → 502 JSON 错误体,不挂进程
    def test_07_upstream_down_502(self):
        with _serve(_dead_port()) as port:
            st, hd, body = _req(port, "/api/chat/bootstrap")
            self.assertEqual(st, 502)
            self.assertIn("application/json", hd["content-type"])
            self.assertIn("error", json.loads(body.decode("utf-8")))
            # 服务还活着(后续请求正常)
            st, _, _ = _req(port, "/api/health")
            self.assertEqual(st, 200)

    # ⑧ 上游 401 原样透传不吞(前端靠它做透明重签)
    def test_08_401_passthrough(self):
        script = {"/api/sessions": (401, None)}
        with _upstream(script) as up, _serve(up.server_address[1]) as port:
            st, _, _ = _req(port, "/api/chat/sessions",
                            headers={"Authorization": "Bearer expired"})
            self.assertEqual(st, 401)

    # ⑨ 请求头白名单:只透传 Authorization / X-Nanobot-Auth,其余剥离
    def test_09_header_allowlist(self):
        with _upstream() as up, _serve(up.server_address[1]) as port:
            _req(port, "/api/chat/sessions", headers={
                "Authorization": "Bearer z", "X-Nanobot-Auth": "w",
                "Cookie": "a=1", "X-Evil": "y", "Referer": "http://x/",
            })
            h = up.requests[0]["headers"]
            self.assertEqual(h.get("authorization"), "Bearer z")
            self.assertEqual(h.get("x-nanobot-auth"), "w")
            for k in ("cookie", "x-evil", "referer"):
                self.assertNotIn(k, h, f"{k} 不得透传")
            # 不带 Authorization 时,上游也不得凭空收到
            _req(port, "/api/chat/sessions")
            self.assertNotIn("authorization", up.requests[1]["headers"])


_JSON_CT = {"Content-Type": "application/json"}


class TestSessionDelete(unittest.TestCase):
    """p7 POST 针孔②(design D1)。red-check:注释 _delete_session 的 CT 闸 →
    test_11 红;注释 key 闸 → test_12 红;把 do_POST 的 _SESSION_DELETE_RE 分支
    改成透传任意路径 → test_13 红。"""

    # ⑩ 转发:POST(CT json)→ 上游 /api/sessions/<key>/delete,Authorization
    #    透传,响应(含 blocked_by_automations 形状)原样回传
    def test_10_delete_forward(self):
        script = {"/api/sessions/websocket:abc/delete": (200, {"deleted": True})}
        with _upstream(script) as up, _serve(up.server_address[1]) as port:
            st, _, body = _req(
                port, "/api/chat/sessions/websocket:abc/delete", method="POST",
                headers={**_JSON_CT, "Authorization": "Bearer tk"}, body=b"{}")
            self.assertEqual(st, 200)
            self.assertTrue(json.loads(body.decode("utf-8"))["deleted"])
            r = up.requests[0]
            self.assertEqual(r["path"], "/api/sessions/websocket:abc/delete")
            self.assertEqual(r["headers"].get("authorization"), "Bearer tk")

    # ⑪ CSRF 纵深:非 application/json(缺省/text/plain)→ 400,零上游
    def test_11_delete_requires_json_ct(self):
        with _upstream() as up, _serve(up.server_address[1]) as port:
            for hd in ({}, {"Content-Type": "text/plain"}):
                st, _, _ = _req(port, "/api/chat/sessions/websocket:abc/delete",
                                method="POST", headers=hd, body=b"{}")
                self.assertEqual(st, 400, f"headers={hd}")
            # body 超限同拒
            st, _, _ = _req(port, "/api/chat/sessions/websocket:abc/delete",
                            method="POST", headers=_JSON_CT, body=b"x" * 5000)
            self.assertEqual(st, 400)
            self.assertEqual(up.requests, [], "拒绝路径不得触达上游")

    # ⑫ 非法 key → 404,零上游(同 thread 代理:%xx 直接非法)
    def test_12_delete_bad_key(self):
        bad = ["..", "%2e%2e", "a%2fb", "%e9%be%99", "a" * 129]
        with _upstream() as up, _serve(up.server_address[1]) as port:
            for k in bad:
                st, _, _ = _req(port, f"/api/chat/sessions/{k}/delete",
                                method="POST", headers=_JSON_CT, body=b"{}")
                self.assertEqual(st, 404, f"key={k!r} 应 404")
            self.assertEqual(up.requests, [])

    # ⑬ POST 白名单仍然锁死:delete 之外的 POST 代理路径维持 405
    def test_13_post_whitelist_still_locked(self):
        paths = ["/api/chat/sessions", "/api/chat/bootstrap",
                 "/api/chat/sessions/k/thread",
                 "/api/chat/sessions/k/delete/extra"]
        with _upstream() as up, _serve(up.server_address[1]) as port:
            for p in paths:
                st, hd, _ = _req(port, p, method="POST",
                                 headers=_JSON_CT, body=b"{}")
                self.assertEqual(st, 405, f"path={p} 应 405")
                self.assertEqual(hd.get("allow"), "GET")
            self.assertEqual(up.requests, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
