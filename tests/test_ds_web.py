#!/usr/bin/env python3
"""ds_web oracle — track opendesign-workbench T2(design.md Test strategy 9 条)。

跑法:  python3 tests/test_ds_web.py
red-check:本文件先于 bin/ds_web.py 落仓,import 失败即为 red 证明(2026-07-06)。
纯 stdlib、离线;端口用 0(内核分配临时口),不占 8766。
"""
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # design-studio/
BIN = os.path.join(ROOT, "bin")
sys.path.insert(0, BIN)
import ds_todo  # noqa: E402
import ds_web  # noqa: E402

TODAY = date(2026, 7, 3)

PROJ_CN = """# 翡翠湾-1801

## 变更记录
- [待确认] C1 2026-06-20 改推拉门
- [进行中] C2 2026-06-25 主卧门改到顶

---
最后更新: 2026-06-20
"""


def _mkroot(files: dict) -> str:
    d = tempfile.mkdtemp(prefix="ds_web_test_")
    proj = os.path.join(d, "projects")
    os.makedirs(proj)
    for name, text in files.items():
        mode = "wb" if isinstance(text, bytes) else "w"
        kw = {} if isinstance(text, bytes) else {"encoding": "utf-8"}
        with open(os.path.join(proj, name), mode, **kw) as fh:
            fh.write(text)
    return d


def _mkdist() -> str:
    d = tempfile.mkdtemp(prefix="ds_web_dist_")
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
        fh.write('<!doctype html><div id="root">OpenDesign</div>')
    os.makedirs(os.path.join(d, "assets"))
    with open(os.path.join(d, "assets", "app-abc123.js"), "w", encoding="utf-8") as fh:
        fh.write("console.log('ok')")
    # dist 隔壁放一个"不该被读到"的文件,供逃逸测试
    with open(os.path.join(os.path.dirname(d), "secret-" + os.path.basename(d)), "w") as fh:
        fh.write("LEAK")
    return d


@contextmanager
def _serve(root: str, dist: str):
    httpd = ds_web.make_server(root, dist, port=0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()


def _req(port: int, path: str, method: str = "GET"):
    """裸 http.client:路径原样上线(urllib 会预规范化 ../,测不到服务端)。"""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request(method, path)
    r = conn.getresponse()
    body = r.read()
    headers = {k.lower(): v for k, v in r.getheaders()}
    conn.close()
    return r.status, headers, body


class TestDsWeb(unittest.TestCase):

    def setUp(self):
        os.environ["DS_TODAY"] = "2026-07-03"

    def tearDown(self):
        os.environ.pop("DS_TODAY", None)

    # ① /api/todos 与 collect() 同源(oracle #1)
    def test_01_todos_matches_collect(self):
        root = _mkroot({"翡翠湾-1801.md": PROJ_CN})
        with _serve(root, _mkdist()) as httpd:
            st, hd, body = _req(httpd.server_address[1], "/api/todos")
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(body.decode("utf-8")),
                         ds_todo.collect(root, 7, TODAY))

    # ② 空 PKB → 空清单不炸(oracle #2)
    def test_02_empty_pkb(self):
        root = _mkroot({})
        with _serve(root, _mkdist()) as httpd:
            st, hd, body = _req(httpd.server_address[1], "/api/todos")
        self.assertEqual(st, 200)
        d = json.loads(body.decode("utf-8"))
        self.assertEqual(d["open"], [])
        self.assertEqual(d["stale"], [])

    # ③ 静态服务:/ = index.html(no-cache),哈希资产 immutable(oracle #3+缓存策略)
    def test_03_static(self):
        with _serve(_mkroot({}), _mkdist()) as httpd:
            port = httpd.server_address[1]
            st, hd, body = _req(port, "/")
            self.assertEqual(st, 200)
            self.assertIn("text/html", hd["content-type"])
            self.assertIn(b"OpenDesign", body)
            self.assertIn("no-cache", hd.get("cache-control", ""))
            st2, hd2, _ = _req(port, "/assets/app-abc123.js")
            self.assertEqual(st2, 200)
            self.assertIn("immutable", hd2.get("cache-control", ""))
            st3, _, _ = _req(port, "/nonexistent.js")
            self.assertEqual(st3, 404)

    # ④ 路径逃逸:裸 ../ + 百分号编码 + Windows 反斜杠 + symlink 变体(oracle #4)
    def test_04_traversal(self):
        dist = _mkdist()
        secret = "secret-" + os.path.basename(dist)
        # dist 内指向外部的 symlink:realpath 展开后必须被 within 拦住
        if hasattr(os, "symlink"):
            os.symlink(os.path.join(os.path.dirname(dist), secret),
                       os.path.join(dist, "leak.js"))
        with _serve(_mkroot({}), dist) as httpd:
            port = httpd.server_address[1]
            for p in (f"/../{secret}", f"/%2e%2e/{secret}",
                      f"/assets/../../{secret}", f"/assets/%2e%2e/%2e%2e/{secret}",
                      "/leak.js"):
                st, _, body = _req(port, p)
                self.assertIn(st, (400, 404), f"path {p} -> {st}")
                self.assertNotEqual(st, 200, f"path {p} served")
                self.assertNotIn(b"LEAK", body, f"path {p} leaked")
            # 反斜杠变体走"bad path"分支,精确 400(防未来把该检查改弱)
            st, _, body = _req(port, f"/..%5c{secret}")
            self.assertEqual(st, 400)
            self.assertNotIn(b"LEAK", body)

    # ⑤ 只读锁死:写方法一律 405(oracle #5)
    def test_05_write_methods_405(self):
        with _serve(_mkroot({}), _mkdist()) as httpd:
            port = httpd.server_address[1]
            for m, p in (("POST", "/api/todos"), ("PUT", "/"),
                         ("DELETE", "/api/health"), ("PATCH", "/api/todos")):
                st, _, _ = _req(port, p, method=m)
                self.assertEqual(st, 405, f"{m} {p} -> {st}")

    # ⑦ 错误路径:一个坏编码 .md 不拖垮其余(M1,07-13 盲评;推翻原「整体 500」契约)。
    #    根因=collect() 无逐文件 try,一坏则 todos+projects 双端点全灭。现:坏文件跳过并
    #    进 errors 字段,好文件照常返回,进程活着。
    def test_07_bad_utf8_isolated_not_fatal(self):
        root = _mkroot({"bad.md": b"# bad\n\xff\xfe not utf8\n",
                        "翡翠湾-1801.md": PROJ_CN})
        with _serve(root, _mkdist()) as httpd:
            port = httpd.server_address[1]
            # /api/todos:200,好项目的未办结项在,坏文件记进 errors
            st, _, body = _req(port, "/api/todos")
            self.assertEqual(st, 200)
            data = json.loads(body.decode("utf-8"))
            self.assertTrue(any(it["project"] == "翡翠湾-1801" for it in data["open"]))
            self.assertIn("bad.md", data.get("errors", []))
            # /api/projects:200,好项目列出(坏文件不出现)
            st2, _, body2 = _req(port, "/api/projects")
            self.assertEqual(st2, 200)
            keys = {p["key"] for p in json.loads(body2.decode("utf-8"))["projects"]}
            self.assertIn("翡翠湾-1801", keys)
            self.assertNotIn("bad", keys)
            # 进程活着
            st3, _, body3 = _req(port, "/api/health")
            self.assertEqual(st3, 200)
            self.assertTrue(json.loads(body3.decode("utf-8"))["ok"])

    # ⑧ 实绑 127.0.0.1(oracle #8)
    def test_08_bind_loopback(self):
        with _serve(_mkroot({}), _mkdist()) as httpd:
            self.assertEqual(httpd.server_address[0], "127.0.0.1")

    # ⑨ 中文往返:ensure_ascii=False + charset 头,原始字节含 UTF-8 中文(oracle #9)
    def test_09_chinese_roundtrip(self):
        root = _mkroot({"翡翠湾-1801.md": PROJ_CN})
        with _serve(root, _mkdist()) as httpd:
            st, hd, body = _req(httpd.server_address[1], "/api/todos")
        self.assertEqual(st, 200)
        self.assertIn("charset=utf-8", hd["content-type"].lower())
        self.assertIn("改推拉门".encode("utf-8"), body)  # 非 \uXXXX 转义
        d = json.loads(body.decode("utf-8"))
        self.assertEqual(d["open"][0]["project"], "翡翠湾-1801")

    # ⑥ health 端点(补充面,oracle #7 已顺带打过;单独再断言形状)
    def test_10_health(self):
        with _serve(_mkroot({}), _mkdist()) as httpd:
            st, hd, body = _req(httpd.server_address[1], "/api/health")
        self.assertEqual(st, 200)
        d = json.loads(body.decode("utf-8"))
        self.assertTrue(d["ok"])
        self.assertIn("version", d)

    # ⑦ health.model(track p4 T2):读 nanobot config 的 agents.defaults.model
    def test_11_health_model(self):
        cfg = os.path.join(tempfile.mkdtemp(prefix="nb_cfg_"), "config.json")
        with open(cfg, "w", encoding="utf-8") as fh:
            json.dump({"agents": {"defaults": {"model": "xiaomi/mimo-v2.5-pro"}}}, fh)
        os.environ["DS_NANOBOT_CONFIG"] = cfg
        try:
            with _serve(_mkroot({}), _mkdist()) as httpd:
                st, _, body = _req(httpd.server_address[1], "/api/health")
        finally:
            del os.environ["DS_NANOBOT_CONFIG"]
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(body.decode("utf-8"))["model"],
                         "xiaomi/mimo-v2.5-pro")

    # ⑦b health.model 解析规则与 nanobot 一致:modelPreset 设了就以 preset 为准
    #    (nanobot 里 preset 优先于 model 字段;install.ps1 合并模板后真机就是这形态,
    #    只读 model 字段会回显假值 —— 07-13 发现的雷);指针悬空 → 回落 model 字段
    def test_11b_health_model_preset_wins(self):
        cfg = os.path.join(tempfile.mkdtemp(prefix="nb_cfg_"), "config.json")
        layout = {
            "agents": {"defaults": {"modelPreset": "mimo-v2.5", "model": "stale/ignored"}},
            "model_presets": {"mimo-v2.5": {"provider": "custom", "model": "mimo-v2.5"}},
        }
        with open(cfg, "w", encoding="utf-8") as fh:
            json.dump(layout, fh)
        os.environ["DS_NANOBOT_CONFIG"] = cfg
        try:
            with _serve(_mkroot({}), _mkdist()) as httpd:
                st, _, body = _req(httpd.server_address[1], "/api/health")
            self.assertEqual(st, 200)
            self.assertEqual(json.loads(body.decode("utf-8"))["model"], "mimo-v2.5")
            # 悬空指针 → 回落 model 字段,不炸
            layout["agents"]["defaults"]["modelPreset"] = "gone"
            with open(cfg, "w", encoding="utf-8") as fh:
                json.dump(layout, fh)
            with _serve(_mkroot({}), _mkdist()) as httpd:
                st, _, body = _req(httpd.server_address[1], "/api/health")
            self.assertEqual(st, 200)
            self.assertEqual(json.loads(body.decode("utf-8"))["model"], "stale/ignored")
        finally:
            del os.environ["DS_NANOBOT_CONFIG"]

    # ⑧ health.model 健壮:config 缺失/损坏 → 探针仍 200,model=null(不炸)
    def test_12_health_model_bad_config(self):
        bad = os.path.join(tempfile.mkdtemp(prefix="nb_cfg_"), "config.json")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("{broken json")
        for cfgpath in (bad, "/nonexistent/config.json"):
            os.environ["DS_NANOBOT_CONFIG"] = cfgpath
            try:
                with _serve(_mkroot({}), _mkdist()) as httpd:
                    st, _, body = _req(httpd.server_address[1], "/api/health")
            finally:
                del os.environ["DS_NANOBOT_CONFIG"]
            self.assertEqual(st, 200)
            self.assertIsNone(json.loads(body.decode("utf-8"))["model"])

    # ⑨ health.model 类型守卫:model 非字符串 / 空串 → null(isinstance 守卫的红检;
    #    panel p4 submimo/subglm 共同点名的最高优先测试缺口)
    def test_13_health_model_type_guard(self):
        d = tempfile.mkdtemp(prefix="nb_cfg_")
        cfg = os.path.join(d, "config.json")
        for weird in (123, True, [], None, ""):
            with open(cfg, "w", encoding="utf-8") as fh:
                json.dump({"agents": {"defaults": {"model": weird}}}, fh)
            os.environ["DS_NANOBOT_CONFIG"] = cfg
            try:
                with _serve(_mkroot({}), _mkdist()) as httpd:
                    st, _, body = _req(httpd.server_address[1], "/api/health")
            finally:
                del os.environ["DS_NANOBOT_CONFIG"]
            self.assertEqual(st, 200, f"model={weird!r} 探针不应炸")
            self.assertIsNone(json.loads(body.decode("utf-8"))["model"],
                              f"model={weird!r} 应回显 null")


class TestDistCommitted(unittest.TestCase):
    """oracle #3 后半:仓内 web/dist 必须真实存在(防"忘了构建就推")。"""

    def test_repo_dist_exists(self):
        self.assertTrue(
            os.path.isfile(os.path.join(ROOT, "web", "dist", "index.html")),
            "web/dist/index.html 缺失 —— 前端没构建或产物没进仓")


class HostGate(unittest.TestCase):
    """H2(07-13 盲评):Host 白名单闸,拒 DNS rebinding。

    rebinding = 恶意域名解析到 127.0.0.1,浏览器同源策略失效但 Host 头仍是
    恶意域名——入口统一校验 Host ∈ 本机形态,否则 403,一个数据端点都不给。
    """

    def _req_host(self, port, path, host, method="GET"):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request(method, path, headers={"Host": host})
        r = conn.getresponse()
        body = r.read()
        conn.close()
        return r.status, body

    def test_h2_evil_host_403_everywhere(self):
        root = _mkroot({"翡翠湾-1801.md": PROJ_CN})
        with _serve(root, _mkdist()) as httpd:
            port = httpd.server_address[1]
            for path in ("/api/health", "/api/todos", "/api/projects", "/"):
                st, body = self._req_host(port, path, "evil.example")
                self.assertEqual(st, 403, f"{path} 未拦 rebinding Host")
            # POST 针孔同闸:403 先于 405/业务逻辑
            st, _ = self._req_host(port, "/api/open-folder", "evil.example:80",
                                   method="POST")
            self.assertEqual(st, 403)

    def test_h2_local_hosts_pass(self):
        root = _mkroot({"翡翠湾-1801.md": PROJ_CN})
        with _serve(root, _mkdist()) as httpd:
            port = httpd.server_address[1]
            for host in (f"127.0.0.1:{port}", f"localhost:{port}",
                         f"LOCALHOST:{port}", f"[::1]:{port}"):
                st, _ = self._req_host(port, "/api/health", host)
                self.assertEqual(st, 200, f"本机 Host {host} 被误拦")
            # 默认 Host(http.client 自动带 127.0.0.1:<port>)不回归
            st, _, _ = _req(port, "/api/health")
            self.assertEqual(st, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
