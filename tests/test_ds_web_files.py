#!/usr/bin/env python3
"""ds_web 文件工作区端点 oracle — track opendesign-workbench-p5 T2/T3。

跑法:  python3 tests/test_ds_web_files.py
覆盖:
  GET  /api/files/overview/<key>   类目计数+最近文件(未配置/未映射诚实降级)
  GET  /api/files/images/<key>     项目图片清单
  GET  /api/files/file/<key>/<rel> 图片静态服务(三闸:字符集/realpath/扩展白名单)
  POST /api/open-folder            唯一受控非 GET:{"key","sub"?} → 启动器
red-check(commit message 附结果):
  Gate B:ds_web._files_file 去 within 闸 → traversal/symlink 测试变红
  T3:去 resolve_sub 调用直接拼路径 → open_folder sub 逃逸测试变红
  405 不变量:POST 精确匹配以外路径全 405、PUT/DELETE/PATCH 含 /api/open-folder 全 405
  启动器"未执行"断言:所有 4xx 路径 launcher 调用数必须为 0
纯 stdlib、离线、端口 0;启动器一律注入 fake,测试永不真开资源管理器。
"""
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_web  # noqa: E402

KEY = "龙腾世纪-1802"
PROJ_REL = "01-项目/20260612 周宁 龙腾世纪 12#1802"
PNG = b"\x89PNG\r\n\x1a\n"


def _touch(path, data=b"x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def _mkroot(with_config=True) -> str:
    """ds_root + 工作区样例树(taxonomy v1.0)。"""
    d = tempfile.mkdtemp(prefix="ds_web_files_")
    ws = os.path.join(d, "ws")
    proj = os.path.join(ws, *PROJ_REL.split("/"))
    _touch(os.path.join(proj, "02-参考图", "客厅参考.png"), PNG)
    _touch(os.path.join(proj, "03-CAD", "平面.dwg"))
    _touch(os.path.join(proj, "06-效果图", "定稿", "客厅终版.png"), PNG)
    _touch(os.path.join(proj, "06-效果图", "notes.txt"))
    # 工作区外的敏感文件(逃逸目标)
    _touch(os.path.join(d, "secret", "密.png"), PNG)
    os.symlink(os.path.join(d, "secret"),
               os.path.join(proj, "02-参考图", "外链"))
    if with_config:
        os.makedirs(os.path.join(d, "config"), exist_ok=True)
        with open(os.path.join(d, "config", "workspace.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"root": ws, "projects": {KEY: PROJ_REL}}, fh,
                      ensure_ascii=False)
    return d


def _mkdist() -> str:
    d = tempfile.mkdtemp(prefix="ds_web_files_dist_")
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<!doctype html><div>x</div>")
    return d


@contextmanager
def _serve(root: str, launcher=None):
    calls = []
    httpd = ds_web.make_server(root, _mkdist(), port=0)
    old = ds_web.OPEN_LAUNCHER
    ds_web.OPEN_LAUNCHER = launcher if launcher is not None else calls.append
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield httpd.server_address[1], calls
    finally:
        ds_web.OPEN_LAUNCHER = old
        httpd.shutdown()
        httpd.server_close()


def _req(port, path, method="GET", body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Content-Type": "application/json"} if body is not None else {}
    conn.request(method, path,
                 body=json.dumps(body).encode("utf-8") if isinstance(body, dict)
                 else body, headers=headers)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r.status, data


def _get_json(port, path):
    st, data = _req(port, path)
    return st, (json.loads(data.decode("utf-8")) if data else None)


def _k(key):  # 中文 key 在 wire 上是 %xx
    return quote(key, safe="")


class OverviewTest(unittest.TestCase):
    def test_mapped(self):
        with _serve(_mkroot()) as (port, _):
            st, obj = _get_json(port, f"/api/files/overview/{_k(KEY)}")
            self.assertEqual(200, st)
            self.assertTrue(obj["configured"])
            self.assertTrue(obj["mapped"])
            cats = {c["name"]: c["count"] for c in obj["categories"]}
            self.assertEqual({"02-参考图": 1, "03-CAD": 1, "06-效果图": 2}, cats)
            self.assertEqual(4, len(obj["recent"]))
            self.assertTrue(all(set(r) >= {"name", "category", "mtime", "size"}
                                for r in obj["recent"]))

    def test_unmapped_key(self):
        with _serve(_mkroot()) as (port, _):
            st, obj = _get_json(port, f"/api/files/overview/{_k('别的项目')}")
            self.assertEqual(200, st)
            self.assertEqual({"configured": True, "mapped": False}, obj)

    def test_unconfigured(self):
        with _serve(_mkroot(with_config=False)) as (port, _):
            st, obj = _get_json(port, f"/api/files/overview/{_k(KEY)}")
            self.assertEqual(200, st)
            self.assertEqual({"configured": False}, obj)

    def test_bad_key(self):
        with _serve(_mkroot()) as (port, _):
            st, _obj = _get_json(port, "/api/files/overview/" + quote("../x", safe=""))
            self.assertEqual(404, st)


class ImagesTest(unittest.TestCase):
    def test_list(self):
        with _serve(_mkroot()) as (port, _):
            st, obj = _get_json(port, f"/api/files/images/{_k(KEY)}")
            self.assertEqual(200, st)
            rels = [i["rel"] for i in obj["images"]]
            self.assertEqual(["02-参考图/客厅参考.png", "06-效果图/定稿/客厅终版.png"],
                             rels)
            self.assertEqual("02-参考图", obj["images"][0]["category"])

    def test_unconfigured(self):
        with _serve(_mkroot(with_config=False)) as (port, _):
            st, obj = _get_json(port, f"/api/files/images/{_k(KEY)}")
            self.assertEqual(200, st)
            self.assertEqual({"configured": False}, obj)


class FilesFileTest(unittest.TestCase):
    def _url(self, rel, key=KEY):
        return f"/api/files/file/{_k(key)}/" + quote(rel, safe="/")

    def test_serves_image(self):
        with _serve(_mkroot()) as (port, _):
            st, data = _req(port, self._url("02-参考图/客厅参考.png"))
            self.assertEqual(200, st)
            self.assertEqual(PNG, data)

    def test_traversal(self):
        with _serve(_mkroot()) as (port, _):
            st, _d = _req(port, self._url("../../../secret/密.png"))
            self.assertEqual(404, st)

    def test_symlink_escape(self):
        with _serve(_mkroot()) as (port, _):
            st, _d = _req(port, self._url("02-参考图/外链/密.png"))
            self.assertEqual(404, st)

    def test_ext_whitelist(self):
        with _serve(_mkroot()) as (port, _):
            st, _d = _req(port, self._url("06-效果图/notes.txt"))
            self.assertEqual(404, st)

    def test_charset_gate(self):
        with _serve(_mkroot()) as (port, _):
            st, _d = _req(port, self._url("02-参考图/bad!.png"))
            self.assertEqual(404, st)

    def test_unmapped_key(self):
        with _serve(_mkroot()) as (port, _):
            st, _d = _req(port, self._url("02-参考图/客厅参考.png", key="别的项目"))
            self.assertEqual(404, st)


class OpenFolderTest(unittest.TestCase):
    def test_opens_project_dir(self):
        root = _mkroot()
        with _serve(root) as (port, calls):
            st, data = _req(port, "/api/open-folder", "POST", {"key": KEY})
            self.assertEqual(200, st)
            self.assertEqual({"ok": True}, json.loads(data))
            self.assertEqual(1, len(calls))
            expect = os.path.realpath(os.path.join(root, "ws", *PROJ_REL.split("/")))
            self.assertEqual(expect, calls[0])

    def test_opens_sub(self):
        root = _mkroot()
        with _serve(root) as (port, calls):
            st, _d = _req(port, "/api/open-folder", "POST",
                          {"key": KEY, "sub": "03-CAD"})
            self.assertEqual(200, st)
            self.assertTrue(calls[0].endswith("03-CAD"))

    def test_rejections_never_launch(self):
        cases = [
            {"key": "别的项目"},                      # 未映射
            {"key": "../x"},                          # key 字符集
            {"key": KEY, "sub": "../.."},             # sub 逃逸
            {"key": KEY, "sub": "02-参考图/外链"},     # sub 多层
            {"key": KEY, "sub": "外链"},              # 需先建 symlink,见下
            {"key": KEY, "sub": "不存在"},            # 不存在目录
            {},                                        # 缺 key
        ]
        root = _mkroot()
        os.symlink(os.path.dirname(os.path.join(root, "secret", "x")),
                   os.path.join(root, "ws", *PROJ_REL.split("/"), "外链2"))
        cases.append({"key": KEY, "sub": "外链2"})    # sub symlink 外指
        with _serve(root) as (port, calls):
            for body in cases:
                st, _d = _req(port, "/api/open-folder", "POST", body)
                self.assertIn(st, (400, 404), body)
            self.assertEqual([], calls)  # 未执行断言:全部拒绝路径零调用

    def test_cross_site_content_type_rejected(self):
        """CSRF 硬化:非 application/json 一律 400 且零执行。跨站 fetch 想带 json
        Content-Type 必触发 preflight,而本服务无 OPTIONS 面 → 浏览器直接拦。"""
        root = _mkroot()
        with _serve(root) as (port, calls):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            conn.request("POST", "/api/open-folder",
                         body=json.dumps({"key": KEY}).encode("utf-8"),
                         headers={"Content-Type": "text/plain"})
            st = conn.getresponse().status
            conn.close()
            self.assertEqual(400, st)
            self.assertEqual([], calls)

    def test_bad_json_body(self):
        with _serve(_mkroot()) as (port, calls):
            st, _d = _req(port, "/api/open-folder", "POST", "{broken")
            self.assertEqual(400, st)
            self.assertEqual([], calls)

    def test_unconfigured(self):
        with _serve(_mkroot(with_config=False)) as (port, calls):
            st, _d = _req(port, "/api/open-folder", "POST", {"key": KEY})
            self.assertEqual(404, st)
            self.assertEqual([], calls)

    def test_launcher_failure_500(self):
        def boom(_path):
            raise OSError("no desktop")
        with _serve(_mkroot(), launcher=boom) as (port, _calls):
            st, _d = _req(port, "/api/open-folder", "POST", {"key": KEY})
            self.assertEqual(500, st)


class WriteMethod405Invariant(unittest.TestCase):
    """P0 以来的不变量:除 /api/open-folder 的 POST 外,一切写方法一律 405。"""

    def test_post_other_paths_405(self):
        with _serve(_mkroot()) as (port, calls):
            for p in ("/api/projects", "/api/todos", "/api/open-folder/",
                      "/api/open-folderX", "/", "/api/files/overview/x"):
                st, _d = _req(port, p, "POST", {})
                self.assertEqual(405, st, p)
            self.assertEqual([], calls)

    def test_other_methods_405_everywhere(self):
        with _serve(_mkroot()) as (port, calls):
            for m in ("PUT", "DELETE", "PATCH"):
                for p in ("/api/open-folder", "/api/projects"):
                    st, _d = _req(port, p, m, {})
                    self.assertEqual(405, st, (m, p))
            self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
