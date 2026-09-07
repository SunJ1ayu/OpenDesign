#!/usr/bin/env python3
"""`GET /api/update/check` 的判据(track opendesign-in-app-update,第一刀接线那半)。

`ds_update` 那份判据问的是**逻辑**(挑哪一版、比不比得对、缓不缓存);
这一份问的是**接线**:这条路真的通到界面上了吗,以及**它坏的时候界面会怎样**。

🔴 本文件最要紧的一条是 t9b:**网络出问题时端点必须仍然是 200**。
查更新失败是小事,而一个 500 会让前端那条通用错误路径弹东西给业主看 ——
业主什么都没干,只是打开了软件,却看见"出错了"。**功能失败不等于软件坏了,
界面上也不该长得一样。**

纯 stdlib、离线(fetch 一律注入替身)、端口 0。
"""
import http.client
import json
import os
import sys
import threading
import unittest
from contextlib import contextmanager

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, HERE)
import _tmpreg   # noqa: E402
import ds_update  # noqa: E402
import ds_web     # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "update",
                       "github-releases-20260907.json")


def _fixture():
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


def _mkdist():
    d = _tmpreg.mkdtemp("ds_web_update_dist_")
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<!doctype html><div>x</div>")
    return d


@contextmanager
def _serve():
    root = _tmpreg.mkdtemp("ds_web_update_root_")
    httpd = ds_web.make_server(root, _mkdist(), port=0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", path)
    r = conn.getresponse()
    body = r.read()
    conn.close()
    return r.status, (json.loads(body.decode("utf-8")) if body else None)


class UpdateCheckEndpoint(unittest.TestCase):

    def setUp(self):
        ds_update.cache_clear()
        self._real = ds_update.fetch_releases
        self.calls = []

    def tearDown(self):
        ds_update.fetch_releases = self._real
        ds_update.cache_clear()

    def _fake(self, payload):
        def fetch():
            self.calls.append(1)
            if isinstance(payload, Exception):
                raise payload
            return payload
        ds_update.fetch_releases = fetch

    def test_t9a_endpoint_answers_with_the_shape_the_ui_needs(self):
        self._fake(_fixture())
        with _serve() as port:
            st, body = _get(port, "/api/update/check")
        self.assertEqual(st, 200)
        self.assertEqual(
            set(body), {"current", "update_available", "latest", "asset", "notes", "error",
                        "release_url"},   # release_url 是评审 F1 加的:地址由 GitHub 给,不许界面自己拼
            f"端点吐出来的字段和约定的不一样:{sorted(body)} —— "
            "多出来的字段意味着把 GitHub 的原始响应往界面上漏")
        self.assertEqual(body["current"], ds_web.VERSION,
                         "端点报的「本机版本」不是 ds_web 的 VERSION —— "
                         "那它比的就不是业主真正在跑的那一版")

    def test_t9b_network_failure_is_still_200(self):
        """🔴 查更新失败 ≠ 软件坏了,界面上也不该长得一样。"""
        self._fake(OSError("no route to host"))
        with _serve() as port:
            st, body = _get(port, "/api/update/check")
        self.assertEqual(
            st, 200,
            "网络不通时端点返回了非 200 —— 前端的通用错误路径会弹东西给业主,"
            "而他只是打开了软件")
        self.assertFalse(body["update_available"])
        self.assertTrue(body["error"], "失败了却什么都不说,日志里也查不到")

    def test_t9e_force_false_is_not_force(self):
        """第三轮评审 F6:`?force=false` 现在会**强制**(判定是"非空且非 0")。

        没有危害(只多打一次 GitHub),但它把"关"读成了"开" —— 一个反着读的参数
        迟早会被下一个人当成"我关掉了"。这里钉死:只有明确的开才算开。
        """
        self._fake(_fixture())
        with _serve() as port:
            _get(port, "/api/update/check")
            _get(port, "/api/update/check?force=false")
            self.assertEqual(len(self.calls), 1,
                             "?force=false 被当成了强制刷新 —— 它字面写着 false")
            _get(port, "/api/update/check?force=1")
            self.assertEqual(len(self.calls), 2, "?force=1 反而没强制")

    def test_t9c_force_really_asks_again(self):
        """业主亲手点「检查更新」时不许给他缓存。"""
        self._fake(_fixture())
        with _serve() as port:
            _get(port, "/api/update/check")
            _get(port, "/api/update/check")
            self.assertEqual(len(self.calls), 1, "同一次开着的软件里问了两次")
            _get(port, "/api/update/check?force=1")
        self.assertEqual(len(self.calls), 2, "带了 force=1 却仍然给的是缓存")

    def test_t9d_endpoint_never_touches_the_network_in_tests(self):
        """接线不许绕过注入点 —— 绕过去的话这一整份判据都在骗自己。

        真去打网的痕迹是:替身一次都没被调用过,而端点却给出了答案。
        """
        self._fake(_fixture())
        with _serve() as port:
            st, body = _get(port, "/api/update/check")
        self.assertEqual(st, 200)
        self.assertGreaterEqual(
            len(self.calls), 1,
            "端点答出来了,但注入的替身一次都没被调用 —— 它绕过 ds_update.fetch_releases "
            "自己去打网了(那么离线判据全都是假的)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
