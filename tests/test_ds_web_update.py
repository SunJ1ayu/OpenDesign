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
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, HERE)
import _tmpreg   # noqa: E402
import ds_update  # noqa: E402
import ds_web     # noqa: E402
import ds_update_apply  # noqa: E402  (第二刀:真去装那一半)

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


class HealthEchoesTheNonce(unittest.TestCase):
    """t19 —— `/api/health` 必须把这次问话的 nonce 原样回给我(第二刀,更新收口)。

    为什么这条住在**服务端**这份考卷里:更新时两次改名之后,旧进程可能还没死透,
    **它也会回一个 200 和一个版本号**。客户端那半(`t18`,在 test_ds_update_apply.py)
    已经要求"没回对 nonce 就不算成功";可要是服务端压根不回显,那条要求就变成
    **永远不成功** —— 一条恒红的收口 = 每次更新都判失败、每次都回滚。
    **两半必须一起钉,少一半都是坏的。**
    """

    def test_t19a_health_echoes_the_nonce_i_asked_with(self):
        with _serve() as port:
            st, body = _get(port, "/api/health?nonce=n0nce-abc")
        self.assertEqual(st, 200)
        self.assertEqual(body.get("nonce"), "n0nce-abc")

    def test_t19b_no_nonce_asked_no_nonce_echoed(self):
        with _serve() as port:
            st, body = _get(port, "/api/health")
        self.assertEqual(st, 200)
        self.assertIsNone(body.get("nonce"),
                          "没问就别编一个 —— 回一个固定值会让 t18 的分辨力归零")

    def test_t19c_version_is_still_there(self):
        # 收口判的是 version + nonce 两件事;别为了加 nonce 把 version 挤掉。
        with _serve() as port:
            _st, body = _get(port, "/api/health?nonce=x")
        self.assertEqual(body.get("version"), ds_web.VERSION)

    def test_t19d_a_weird_nonce_does_not_500(self):
        # nonce 是我们自己生成的,但端点不许因为奇怪输入就 500 —— 500 会被前端那条
        # 通用错误路径弹给业主看(和 t9b 同一个理由:功能失败 != 软件坏了)。
        for nonce in ("a" * 200, "带中文的", "a&b=c", "<script>"):
            with self.subTest(nonce=nonce):
                with _serve() as port:
                    st, _body = _get(port, "/api/health?nonce=" + quote(nonce))
                self.assertEqual(st, 200)


def _post(port, path, body=b"{}"):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("POST", path, body=body,
                 headers={"Content-Type": "application/json"})
    r = conn.getresponse()
    raw = r.read()
    conn.close()
    return r.status, (json.loads(raw.decode("utf-8")) if raw else None)


class UpdateApplyEndpoint(unittest.TestCase):
    """t22 —— `POST /api/update/apply`:业主点了「更新」之后这条路。

    🔴 这份考卷里最要紧的一条是 **t22c 的顺序**:
    **先把接力脚本起起来、确认它真起来了,再请外壳把软件关掉。**
    反过来 = 外壳先把 ds_web 杀了,而接力脚本还没人起 ⇒
    **业主看到的是「软件关了,没再打开」,而且没有任何东西会去回滚。**

    第二要紧的是"不许撒谎"(t22e):只有外壳**点名认了**交棒动词才算开始。
    裸 OK 是老外壳收下了帧但做了别的事 —— 报成"更新已开始",业主会关掉浏览器等着,
    而实际什么都没发生。这条纪律照抄 `ds_shell_bridge_restart`。
    """

    def setUp(self):
        ds_update.cache_clear()
        self._real_fetch = ds_update.fetch_releases
        self._real_apply = ds_update_apply.apply_update
        self._real_handoff = ds_update_apply.handoff
        self._real_bridge = getattr(ds_web, "ds_shell_bridge_update", None)
        # 🔴 夹具录于 2026-09-07,里面最新的是 0.98.3,而本机 VERSION 已经是 0.98.4
        #    ⇒ 照原样跑,"线上有新版"这个前提**结构上不成立**,底下几条断言永远
        #    走不到它们要问的地方(第一版就是这么写的,实现落地后当场照出来)。
        #    把本机版本调旧,让这份真实录下来的响应真的比它新。
        self._real_version = ds_web.VERSION
        ds_web.VERSION = "0.90.0"
        self.order = []          # 谁先谁后 —— t22c 就靠它
        self.applied = []

    def tearDown(self):
        ds_update.fetch_releases = self._real_fetch
        ds_update_apply.apply_update = self._real_apply
        ds_update_apply.handoff = self._real_handoff
        ds_web.VERSION = self._real_version
        if self._real_bridge is not None:
            ds_web.ds_shell_bridge_update = self._real_bridge
        ds_update.cache_clear()

    # --- 替身:一次真网都不打,一次真安装器都不跑,一次真关停都不做 ---

    def _online(self, newer=True):
        rel = _fixture()
        if not newer:
            rel = []
        ds_update.fetch_releases = lambda: rel

    def _seams(self, apply_ok=True, handoff_ok=True, bridge="started"):
        def fake_apply(decision, paths, **kw):
            self.order.append("apply")
            self.applied.append(decision)
            if apply_ok:
                return {"ok": True, "stage": "relay", "error": None,
                        "relay": "C:/tmp/relay.cmd"}
            return {"ok": False, "stage": "verify", "error": "sha256 对不上",
                    "relay": None}

        def fake_handoff(relay, **kw):
            self.order.append("handoff")
            return handoff_ok

        def fake_bridge():
            self.order.append("bridge")
            return bridge

        ds_update_apply.apply_update = fake_apply
        ds_update_apply.handoff = fake_handoff
        ds_web.ds_shell_bridge_update = fake_bridge

    def test_t22a_get_never_triggers_an_install(self):
        """GET 面保持纯只读(本服务模块头的铁律)。装软件是本仓最重的副作用,
        一个能被 GET 触发的它,等于一条能被别的网页诱发的更新。"""
        self._online()
        self._seams()
        with _serve() as port:
            st, _b = _get(port, "/api/update/apply")
        self.assertIn(st, (404, 405), "GET 居然被路由到了安装口")
        self.assertEqual(self.order, [], "GET 触发了安装")

    def test_t22b_no_new_version_means_nothing_is_installed(self):
        self._online(newer=False)
        self._seams()
        with _serve() as port:
            st, body = _post(port, "/api/update/apply")
        self.assertEqual(st, 200)
        self.assertFalse(body.get("ok"))
        self.assertEqual(self.order, [], "线上没有新版,却还是装了一遍")

    def test_t22c_the_relay_is_launched_before_the_shell_is_told_to_quit(self):
        """🔴 这一单最怕的那个形态就在这条断言的反面。"""
        self._online()
        self._seams()
        with _serve() as port:
            _st, body = _post(port, "/api/update/apply")
        self.assertEqual(self.order, ["apply", "handoff", "bridge"],
                         "顺序不对:必须先起接力脚本,再请外壳关停")
        self.assertTrue(body.get("ok"))

    def test_t22d_a_failed_handoff_never_asks_the_shell_to_quit(self):
        """接力脚本没起来就请外壳关软件 = 关了没人接手。"""
        self._online()
        self._seams(handoff_ok=False)
        with _serve() as port:
            _st, body = _post(port, "/api/update/apply")
        self.assertNotIn("bridge", self.order,
                         "接力脚本都没起来,还是把关停请求发出去了")
        self.assertFalse(body.get("ok"))
        self.assertEqual(body.get("stage"), "handoff")

    def test_t22e_a_shell_that_did_not_name_the_verb_is_not_success(self):
        self._online()
        self._seams(bridge="manual")
        with _serve() as port:
            _st, body = _post(port, "/api/update/apply")
        self.assertFalse(body.get("ok"),
                         "外壳没认这个动词,却跟业主说更新已经开始了")

    def test_t22f_a_failed_preparation_says_which_step_died(self):
        """"装错了"和"没装成"在业主那儿长得一样(软件关了没回来),
        但在日志和界面上必须分得开 —— design「这个 oracle 能被什么骗过」第 4 条。"""
        self._online()
        self._seams(apply_ok=False)
        with _serve() as port:
            _st, body = _post(port, "/api/update/apply")
        self.assertFalse(body.get("ok"))
        self.assertEqual(body.get("stage"), "verify")
        self.assertIn("sha256", body.get("error") or "")
        self.assertEqual(self.order, ["apply"], "准备就没过,后面两步不该走")

    def test_t22g_the_decision_handed_to_the_installer_carries_the_asset(self):
        """端点必须把**查到的那个 release** 原样交下去 —— 不许自己另编一个。
        下载地址只能来自它(t14 钉的同一件事,这里守的是接线这一侧)。"""
        self._online()
        self._seams()
        with _serve() as port:
            _post(port, "/api/update/apply")
        self.assertTrue(self.applied, "没把决定交给安装那一层")
        asset = (self.applied[0] or {}).get("asset") or {}
        self.assertTrue(asset.get("url"), "交下去的决定里没有下载地址")
