#!/usr/bin/env python3
"""判据:填 key 那两个接口 + 拿掉手输口令之后补的那道来源检查
(track opendesign-key-onboarding)。

    /root/.venvs/design-studio/bin/python tests/test_ds_web_credential.py

`tests/test_credential.py` 问的是**存取那一层**(key 会不会漏、变量名对不对);
这一份问的是 **HTTP 这一层**:接口回什么、跨站请求能不能打、
以及**前端不再手输口令之后,口令是不是真的没经过浏览器**。

## 它问不出什么

- 重启之后模型真的回话(只有真机能答)。
- 浏览器的同源策略(那是浏览器的事,不是我们的代码)—— 所以这里问的是
  **服务端自己会不会拒**,不是"浏览器会不会拦"。
"""
from __future__ import annotations

import http.client
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))

import ds_credential  # noqa: E402
import ds_web  # noqa: E402

FAKE_KEY = "sk-oracle-do-not-ship-0123456789abcdef0123456789"
# 口令必须是 latin-1 能编码的:它要进 HTTP 头。第一版我在这儿写了中文,
# **当场炸出一个真问题** —— 代理会在 header 编码上抛 UnicodeEncodeError 而不是降级
# (patch_config 早就在装机那一侧拦了中文口令,但 ds-web 这一侧没有兜底)。
# ⇒ 夹具改 ASCII,而"非 latin-1 口令不许把代理搞崩"单独立一条(j3)。
PASSWORD = "pw-only-on-the-server-side"

_JUDGE_HOME = None
_SAVED: dict[str, str | None] = {}


def setUpModule():
    global _JUDGE_HOME
    _JUDGE_HOME = tempfile.mkdtemp(prefix="ds-web-cred-判据假家-")
    for k in ("HOME", "USERPROFILE"):
        _SAVED[k] = os.environ.get(k)
        os.environ[k] = _JUDGE_HOME


def tearDownModule():
    for k, v in _SAVED.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


class _UpHandler(BaseHTTPRequestHandler):
    """假网关:把收到的 Authorization 记下来,好验"口令是服务端补的"。"""

    def do_GET(self):
        self.server.requests.append({k.lower(): v for k, v in self.headers.items()})
        body = json.dumps({"token": "短票-一次性", "ws_path": "/ws",
                           "ws_url": "ws://127.0.0.1/ws", "expires_in": 60}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@contextmanager
def _upstream():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _UpHandler)
    httpd.requests = []
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()


class Rig(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ds-web-cred-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = os.path.join(self.tmp, "UserData")
        os.makedirs(os.path.join(self.home, ".nanobot"))
        self.cfg_path = os.path.join(self.home, ".nanobot", "config.json")
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump({
                "channels": {"websocket": {"enabled": True, "token": PASSWORD}},
                "providers": {"custom": {"apiKey": "${DS_LLM_KEY}", "apiBase": "https://旧/v1"}},
                "model_presets": {}, "agents": {"defaults": {}},
            }, fh, ensure_ascii=False)
        os.environ["DS_NANOBOT_CONFIG"] = self.cfg_path
        self.addCleanup(os.environ.pop, "DS_NANOBOT_CONFIG", None)
        os.environ["HOME"] = self.home          # ds-web 从 HOME 找 .openDesign/key.txt
        os.environ["USERPROFILE"] = self.home
        self.addCleanup(lambda: os.environ.update(
            {"HOME": _JUDGE_HOME, "USERPROFILE": _JUDGE_HOME}))

        self.ds_root = os.path.join(self.tmp, "ds")
        os.makedirs(os.path.join(self.ds_root, "projects"))
        dist = os.path.join(self.tmp, "dist")
        os.makedirs(dist)
        with open(os.path.join(dist, "index.html"), "w", encoding="utf-8") as fh:
            fh.write("<!doctype html><div>x</div>")
        self.up = self.enterContext(_upstream()) if hasattr(self, "enterContext") else None
        self._dist = dist

    @contextmanager
    def serve(self, nanobot_port: int = 1):
        httpd = ds_web.make_server(self.ds_root, self._dist, port=0,
                                   nanobot_port=nanobot_port)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            yield httpd.server_address[1]
        finally:
            httpd.shutdown()
            httpd.server_close()

    def req(self, port, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        hd = {"Host": f"127.0.0.1:{port}"}
        if body is not None:
            hd["Content-Type"] = "application/json"
        hd.update(headers or {})
        conn.request(method, path, body=json.dumps(body).encode("utf-8") if body else None,
                     headers=hd)
        r = conn.getresponse()
        raw = r.read()
        conn.close()
        try:
            return r.status, json.loads(raw.decode("utf-8")) if raw else None, raw
        except ValueError:
            return r.status, None, raw


class TestCredentialEndpoints(Rig):

    def test_h1_status_starts_out_unconfigured(self):
        with self.serve() as port:
            st, d, raw = self.req(port, "GET", "/api/llm/credential")
            self.assertEqual(st, 200, raw[:200])
            self.assertFalse(d["configured"])
            self.assertIn("providers", d, "界面得知道有哪几家可选")

    def test_h2_saving_returns_no_key_and_says_what_happens_next(self):
        with self.serve() as port:
            st, d, raw = self.req(port, "POST", "/api/llm/credential",
                                  {"provider": "deepseek", "key": FAKE_KEY})
            self.assertEqual(st, 200, raw[:300])
            self.assertNotIn(FAKE_KEY, raw.decode("utf-8"), "响应里带着 key 原文")
            self.assertTrue(d["configured"])
            self.assertIn(d.get("restart"), ("requested", "manual"),
                          f"没说清接下来会发生什么:{d}")

    def test_h5_without_a_shell_it_says_manual_instead_of_pretending(self):
        """降级诚实(design 四组之四)。**这条是红检 M10 逼出来的**:h2 只问
        "restart 是那两个值之一",于是把桩改成恒回 "requested" 照样全绿 ——
        规格里写着"不假装成功",判据里却没有。判据环境没有外壳(锁端口没人听),
        ⇒ 必须**恰好**是 manual。将来通道接通了,这条仍成立:连不上就得说连不上。"""
        with self.serve() as port:
            _, d, _ = self.req(port, "POST", "/api/llm/credential",
                               {"provider": "deepseek", "key": FAKE_KEY})
            self.assertEqual(d.get("restart"), "manual",
                             "没有外壳却说重启已安排 —— 业主会干等一件不会发生的事")

    def test_h3_a_bad_provider_is_refused_in_human_words(self):
        with self.serve() as port:
            st, d, raw = self.req(port, "POST", "/api/llm/credential",
                                  {"provider": "不存在的厂商", "key": FAKE_KEY})
            self.assertEqual(st, 400)
            self.assertNotIn(FAKE_KEY, raw.decode("utf-8"))

    def test_h4_the_key_never_shows_up_in_a_later_read(self):
        with self.serve() as port:
            self.req(port, "POST", "/api/llm/credential",
                     {"provider": "mimo", "key": FAKE_KEY})
            st, d, raw = self.req(port, "GET", "/api/llm/credential")
            self.assertTrue(d["configured"])
            self.assertNotIn(FAKE_KEY, raw.decode("utf-8"))
            self.assertEqual(d.get("provider"), "mimo")


class TestCrossSiteIsRefused(Rig):
    """拿掉手输口令之后补的那道纵深。**双向验**,别造一个永远拒绝的闸。"""

    def test_i1_cross_site_post_is_refused(self):
        with self.serve() as port:
            st, _, _ = self.req(port, "POST", "/api/llm/credential",
                                {"provider": "mimo", "key": FAKE_KEY},
                                headers={"Origin": "https://evil.example",
                                         "Sec-Fetch-Site": "cross-site"})
            self.assertEqual(st, 403, "别的网站能替业主改 key")

    def test_i2_cross_site_read_is_refused(self):
        with self.serve() as port:
            st, _, _ = self.req(port, "GET", "/api/llm/credential",
                                headers={"Origin": "https://evil.example",
                                         "Sec-Fetch-Site": "cross-site"})
            self.assertEqual(st, 403)

    def test_i3_the_chat_proxy_refuses_cross_site_too(self):
        """代签上线后,聊天代理口不再需要业主的口令 ⇒ 它同样得拒跨站
        (design 骗法二:来源检查只加在新接口上等于没加)。"""
        with self.serve() as port:
            st, _, _ = self.req(port, "GET", "/api/chat/bootstrap",
                                headers={"Origin": "https://evil.example",
                                         "Sec-Fetch-Site": "cross-site"})
            self.assertEqual(st, 403)

    def test_i6_a_cross_site_origin_alone_is_enough_to_refuse(self):
        """🔴 红检 M1/M2 逼出来的:i1~i3 每一条都**同时**带 Origin 和 Sec-Fetch-Site,
        于是拆掉其中任意一道检查判据都照样绿(另一道接住了)——**两道防线只被合起来
        验过一次**,谁悄悄坏掉都没人知道。这条只带 Origin:**老浏览器不发
        Sec-Fetch-Site**,那种机器上顶着的就只有 Origin 白名单。"""
        with self.serve() as port:
            st, _, _ = self.req(port, "POST", "/api/llm/credential",
                                {"provider": "mimo", "key": FAKE_KEY},
                                headers={"Origin": "https://evil.example"})
            self.assertEqual(st, 403, "只看 Sec-Fetch-Site 的话,不发那个头的浏览器就失守")

    def test_i7_a_cross_site_fetch_marker_alone_is_enough_to_refuse(self):
        """i6 的另一半:只带 Sec-Fetch-Site,不带 Origin。
        (浏览器在某些跨站导航/表单里不发 Origin,但 Sec-Fetch-Site 仍是 cross-site。)"""
        with self.serve() as port:
            st, _, _ = self.req(port, "POST", "/api/llm/credential",
                                {"provider": "mimo", "key": FAKE_KEY},
                                headers={"Sec-Fetch-Site": "cross-site"})
            self.assertEqual(st, 403, "只看 Origin 白名单的话,不带 Origin 的跨站请求就进来了")

    def test_i4_same_origin_still_works(self):
        with self.serve() as port:
            st, _, _ = self.req(port, "GET", "/api/llm/credential",
                                headers={"Origin": f"http://127.0.0.1:{port}",
                                         "Sec-Fetch-Site": "same-origin"})
            self.assertEqual(st, 200)

    def test_i5_a_plain_request_without_origin_still_works(self):
        """非浏览器的调用(我自己 curl、真机清单里那些)不带 Origin —— 不许误伤。"""
        with self.serve() as port:
            st, _, _ = self.req(port, "GET", "/api/llm/credential")
            self.assertEqual(st, 200)


class TestPasswordNeverReachesTheBrowser(Rig):
    """前端不再手输口令 ⇒ 口令必须由 ds-web 自己补上,而且**不许回给浏览器**。"""

    def test_j1_proxy_signs_with_the_configured_password(self):
        with _upstream() as up:
            with self.serve(nanobot_port=up.server_address[1]) as port:
                st, d, raw = self.req(port, "GET", "/api/chat/bootstrap")
                self.assertEqual(st, 200, raw[:200])
                self.assertTrue(up.requests, "根本没打到上游")
                auth = up.requests[-1].get("authorization", "")
                self.assertIn(PASSWORD, auth,
                              "ds-web 没有替前端补上口令 —— 业主还得自己输")

    def test_j3_a_non_latin1_password_degrades_instead_of_exploding(self):
        """判据自己的夹具炸出来的:口令进 HTTP 头,非 latin-1 会抛编码错。
        装机那侧(patch_config)拦得住,但 ds-web 这侧也不许因此把请求打崩。"""
        with open(self.cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
        cfg["channels"]["websocket"]["token"] = "中文口令"
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False)
        with _upstream() as up:
            with self.serve(nanobot_port=up.server_address[1]) as port:
                st, _, raw = self.req(port, "GET", "/api/chat/bootstrap")
                self.assertIn(st, (200, 401, 502),
                              f"非 latin-1 口令把代理搞崩了:{st} {raw[:120]}")

    def test_j2_the_password_itself_never_comes_back(self):
        with _upstream() as up:
            with self.serve(nanobot_port=up.server_address[1]) as port:
                st, d, raw = self.req(port, "GET", "/api/chat/bootstrap")
                self.assertNotIn(PASSWORD, raw.decode("utf-8"),
                                 "口令被回给浏览器了 —— 那等于把它交出去")
                self.assertEqual(d.get("token"), "短票-一次性")


@contextmanager
# 2026-08-16(四审 kimi 腿 Finding 3):替身默认回**点名动词**的应答。
# 旧默认是裸 `OK\n` —— 那正是老外壳的应答:它收下帧、然后去把窗口叫到前台,
# 根本没重启。判据用它当"真外壳",于是"撒谎的重启"这条路一直没人问。
# 想演老外壳,显式传 answer=b"OK\n"(k3b 就是干这个的)。
def _fake_shell(answer: bytes = b"OK RESTART-BACKEND\n", stall: float = 0.0):
    """假外壳:在锁端口上听着,记下收到的整帧,按需回 OK。

    **手写协议、不复用 InstanceLock** —— 判据要钉住线上那几个字节。
    和实现抄同一处的话,两边一起改就没人发现(design 骗法四)。
    """
    got: list[bytes] = []
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(4)

    def loop():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            with conn:
                conn.settimeout(3)
                data = b""
                try:
                    while data.count(b"\n") < 2 and len(data) < 4096:
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        data += chunk
                except OSError:
                    pass
                got.append(data)
                if stall:
                    time.sleep(stall)
                if answer:
                    try:
                        conn.sendall(answer)
                    except OSError:
                        pass

    threading.Thread(target=loop, daemon=True).start()
    try:
        yield srv.getsockname()[1], got
    finally:
        srv.close()


class TestTheRestartBridgeIsHonest(Rig):
    """填完 key 得让网关重来一次(它只在启动时读 env)。
    这一组全部围绕**一句话不许撒谎**:说"已安排重启"就必须真的送到了外壳。"""

    def bridge_port(self, port):
        os.environ["DS_SHELL_LOCK_PORT"] = str(port)
        self.addCleanup(os.environ.pop, "DS_SHELL_LOCK_PORT", None)

    def save(self, port):
        _, d, _ = self.req(port, "POST", "/api/llm/credential",
                           {"provider": "mimo", "key": FAKE_KEY})
        return d

    def test_k1_nobody_listening_means_manual(self):
        """git-pull 那两台没有外壳 ⇒ 端口上没人。如实说"请重启一下",不假装。"""
        with socket.socket() as probe:          # 借一个端口号,随即关掉 ⇒ 保证没人听
            probe.bind(("127.0.0.1", 0))
            dead = probe.getsockname()[1]
        self.bridge_port(dead)
        with self.serve() as port:
            self.assertEqual(self.save(port).get("restart"), "manual")

    def test_k2_a_stranger_on_that_port_is_not_our_shell(self):
        """🔴 端口是全机器共用的。别的程序恰好占着那个号,不能就当成外壳报"已重启" ——
        那正是 b3 在锁那一侧防的同一件事,只是方向反过来。"""
        with _fake_shell(answer=b"HTTP/1.1 200 OK\r\n") as (lp, _):
            self.bridge_port(lp)
            with self.serve() as port:
                self.assertEqual(self.save(port).get("restart"), "manual",
                                 "把一个陌生程序当成了外壳")

    def test_k3_a_real_shell_gets_the_restart_verb_not_show(self):
        with _fake_shell() as (lp, got):
            self.bridge_port(lp)
            with self.serve() as port:
                self.assertEqual(self.save(port).get("restart"), "requested")
            self.assertTrue(got, "根本没往外壳发东西")
            frame = got[-1]
            self.assertTrue(frame.startswith(b"OpenDesign.ds_shell_core.lock.v1\n"),
                            f"帧头不对,外壳不会理它:{frame!r}")
            self.assertIn(b"RESTART-BACKEND\n", frame, f"发的不是重启动词:{frame!r}")
            self.assertNotIn(b"SHOW\n", frame,
                             "顺手把窗口弹到了前台 —— 他正在窗口里填 key")

    def test_k3b_an_old_shell_that_only_says_ok_must_degrade_to_manual(self):
        """老外壳认不出 RESTART:它照样回裸 `OK`,然后把窗口叫到前台。

        把那种情况报成 `requested`,界面就对业主说「已经自动应用新配置」而网关一动
        没动 —— 他填的新 key 根本没生效。**宁可让他多点一下。**(不变量 4)
        """
        with _fake_shell(answer=b"OK\n") as (lp, got):
            self.bridge_port(lp)
            with self.serve() as port:
                self.assertEqual(self.save(port).get("restart"), "manual",
                                 "老外壳只回了 OK,却被当成「已经重启了」")
            self.assertTrue(got, "根本没往外壳发东西")

    def test_k4_a_wedged_shell_does_not_hang_the_save(self):
        """外壳卡住时,业主点"保存"必须还能拿到回应。
        没有这一条,最坏情况是他以为程序死了 —— 而 key 其实已经存好了。"""
        with _fake_shell(stall=30.0) as (lp, _):
            self.bridge_port(lp)
            with self.serve() as port:
                t0 = time.monotonic()
                d = self.save(port)
                self.assertLess(time.monotonic() - t0, 10,
                                "外壳不吭声就把保存接口拖住了")
                self.assertEqual(d.get("restart"), "manual", "等不到应答就不许说已安排")
                self.assertTrue(d.get("configured"), "重启没谈拢,但 key 该存的还是要存")


if __name__ == "__main__":
    unittest.main(verbosity=2)
