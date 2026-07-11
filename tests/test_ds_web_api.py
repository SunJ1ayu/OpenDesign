#!/usr/bin/env python3
"""ds_web 只读 API oracle — track opendesign-workbench-p2 T1(design.md Test strategy)。

跑法:  python3 tests/test_ds_web_api.py
覆盖四条只读 GET:
  /api/projects                     项目列表(key/name/stage/open_count/delivered/last_update)
  /api/projects/<key>/changes       该项目全量变更(四状态,可选字段缺省)
  /api/projects/<key>/refs          该项目参考图(过滤 refs-index 用于:)
  /api/refs/file/<path>             参考图静态服务(三闸:字符集/realpath/扩展白名单)

red-check(commit message 附结果):对 refs 静态服务三闸各做一次突变验红——
  Gate A 字符集:注释掉字符集白名单 → test_file_charset_gate 变红(bad!.png 被误服务)
  Gate B realpath:注释掉 within 前缀闸 → test_file_symlink_escape / test_file_traversal 变红
  Gate C 扩展白名单:注释掉扩展闸 → test_file_ext_whitelist 变红(refs/notes.txt 被误服务)

纯 stdlib、离线、端口 0,不烧 LLM。
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
ROOT = os.path.dirname(HERE)  # design-studio/
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_todo  # noqa: E402
import ds_web   # noqa: E402


PROJ_A = """# 保利中央公园 2803

- 业主: [[张伟]]
- 阶段: 施工图
- 开始日期: 2026-05-01
- 当前状态: 玄关柜待业主确认

## 变更记录
- [待确认] C12 2026-07-09 玄关柜整体改到 2.4 米高,柜顶留 300mm 检修口
- [进行中] C11 2026-07-08 电视墙改用岩板,取消原定木格栅
- [已完成] C8 2026-06-28 全屋筒灯统一换 3000K
- [已关闭] C7 2026-06-20 沙发背景墙两侧加壁灯(业主取消)
- [待确认] 缺编号缺日期的残缺行也要能解析

## 沟通日志
- 2026-07-09 现场:太太提玄关柜改高

---
最后更新: 2026-07-10
"""

PROJ_DELIVERED = """# 翡翠湾-1801

- 业主: [[李四]]
- 阶段: 竣工验收

## 变更记录
- [已完成] C1 2026-06-01 全屋交付

---
最后更新: 2026-06-30
"""

PROJ_BARE = """# 光头项目

没有阶段、没有变更、没有页脚——读侧必须宽容不崩。
"""


def _mkroot(files: dict, refs_index: str | None = None) -> str:
    d = tempfile.mkdtemp(prefix="ds_web_api_")
    proj = os.path.join(d, "projects")
    os.makedirs(proj)
    for name, text in files.items():
        mode = "wb" if isinstance(text, bytes) else "w"
        kw = {} if isinstance(text, bytes) else {"encoding": "utf-8"}
        with open(os.path.join(proj, name), mode, **kw) as fh:
            fh.write(text)
    os.makedirs(os.path.join(d, "refs"))
    if refs_index is not None:
        with open(os.path.join(d, "refs-index.md"), "w", encoding="utf-8") as fh:
            fh.write(refs_index)
    return d


def _mkdist() -> str:
    d = tempfile.mkdtemp(prefix="ds_web_api_dist_")
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<!doctype html><div>x</div>")
    return d


def _write_bytes(path: str, data: bytes = b"\x89PNG\r\n\x1a\n"):
    with open(path, "wb") as fh:
        fh.write(data)


@contextmanager
def _serve(root: str):
    httpd = ds_web.make_server(root, _mkdist(), port=0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()


def _req(port: int, path: str, method: str = "GET"):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request(method, path)
    r = conn.getresponse()
    body = r.read()
    hd = {k.lower(): v for k, v in r.getheaders()}
    conn.close()
    return r.status, hd, body


def _get_json(port: int, path: str):
    st, hd, body = _req(port, path)
    return st, hd, (json.loads(body.decode("utf-8")) if body else None)


# ── /api/projects ────────────────────────────────────────────────────────────
class TestProjects(unittest.TestCase):

    def test_projects_list(self):
        root = _mkroot({"保利中央公园.md": PROJ_A, "翡翠湾-1801.md": PROJ_DELIVERED})
        with _serve(root) as port:
            st, hd, d = _get_json(port, "/api/projects")
        self.assertEqual(st, 200)
        self.assertIn("charset=utf-8", hd["content-type"].lower())
        by_key = {p["key"]: p for p in d["projects"]}
        a = by_key["保利中央公园"]
        self.assertEqual(a["name"], "保利中央公园 2803")
        self.assertEqual(a["stage"], "施工图")
        self.assertEqual(a["delivered"], False)
        self.assertEqual(a["last_update"], "2026-07-10")
        # open_count 与 ds_todo 同源:待确认(C12 + 残缺行)+ 进行中(C11) = 3
        self.assertEqual(a["open_count"], 3)
        d1 = by_key["翡翠湾-1801"]
        self.assertEqual(d1["delivered"], True)   # 竣工验收 = 已交付
        self.assertEqual(d1["open_count"], 0)

    def test_projects_open_count_matches_collect(self):
        root = _mkroot({"保利中央公园.md": PROJ_A})
        with _serve(root) as port:
            _, _, d = _get_json(port, "/api/projects")
        collected = ds_todo.collect(root)
        want = sum(1 for it in collected["open"] if it["project"] == "保利中央公园")
        got = {p["key"]: p for p in d["projects"]}["保利中央公园"]["open_count"]
        self.assertEqual(got, want)

    def test_projects_empty(self):
        with _serve(_mkroot({})) as port:
            st, _, d = _get_json(port, "/api/projects")
        self.assertEqual(st, 200)
        self.assertEqual(d["projects"], [])

    def test_projects_bare_md_tolerant(self):
        root = _mkroot({"光头项目.md": PROJ_BARE})
        with _serve(root) as port:
            st, _, d = _get_json(port, "/api/projects")
        self.assertEqual(st, 200)
        p = d["projects"][0]
        self.assertEqual(p["key"], "光头项目")
        self.assertEqual(p["open_count"], 0)
        self.assertEqual(p["last_update"], None)
        self.assertIn(p["stage"], ("", None))


# ── /api/projects/<key>/changes ──────────────────────────────────────────────
class TestChanges(unittest.TestCase):

    def test_changes_all_statuses(self):
        root = _mkroot({"保利中央公园.md": PROJ_A})
        with _serve(root) as port:
            st, hd, d = _get_json(port, "/api/projects/" + quote("保利中央公园") + "/changes")
        self.assertEqual(st, 200)
        self.assertEqual(d["key"], "保利中央公园")
        statuses = [c["status"] for c in d["changes"]]
        self.assertEqual(statuses, ["待确认", "进行中", "已完成", "已关闭", "待确认"])
        c12 = d["changes"][0]
        self.assertEqual(c12["cnum"], 12)
        self.assertEqual(c12["date"], "2026-07-09")
        self.assertIn("玄关柜", c12["text"])
        # 可选字段 space/source:现有 PKB 格式无 → 缺省(读侧宽容,accepted deviation)
        self.assertIn("space", c12)
        self.assertIn("source", c12)

    def test_changes_partial_line(self):
        root = _mkroot({"保利中央公园.md": PROJ_A})
        with _serve(root) as port:
            _, _, d = _get_json(port, "/api/projects/" + quote("保利中央公园") + "/changes")
        partial = d["changes"][-1]  # 缺编号缺日期的残缺行
        self.assertEqual(partial["status"], "待确认")
        self.assertEqual(partial["cnum"], None)
        self.assertEqual(partial["date"], None)

    def test_changes_bad_key_404(self):
        root = _mkroot({"保利中央公园.md": PROJ_A})
        # 隔壁放一个"不该被读到"的项目文件,逃逸若成立就会命中它
        with open(os.path.join(root, "SECRET.md"), "w", encoding="utf-8") as fh:
            fh.write("# secret")
        bad = ["..", "%2e%2e", "a%2fb", "a%2f%2e%2e%2fSECRET", "%2e%2e%2fSECRET",
               "x%00y", "a%5cb"]
        with _serve(root) as port:
            for k in bad:
                st, _, _ = _req(port, f"/api/projects/{k}/changes")
                self.assertEqual(st, 404, f"key={k!r} 应 404")
            # 空 key(裸双斜线)同 404
            st, _, _ = _req(port, "/api/projects//changes")
            self.assertEqual(st, 404)

    def test_changes_unknown_project_404(self):
        root = _mkroot({"保利中央公园.md": PROJ_A})
        with _serve(root) as port:
            st, _, _ = _req(port, "/api/projects/" + quote("不存在的项目") + "/changes")
        self.assertEqual(st, 404)


# ── /api/projects/<key>/refs ─────────────────────────────────────────────────
REFS_INDEX = """# 参考图索引

- [r1] 奶油风|玄关 | 来源:小红书 | 文件:refs/a.jpg | 用于:保利中央公园 | 备注:柜体
- [r2] 侘寂风|客厅 | 来源:Pinterest | 文件:refs/b.png | 用于:翡翠湾-1801 | 备注:
- [r3] 现代简约,轻奢|主卧,衣帽间 | 来源:Behance | 文件:refs/c.webp | 用于:保利中央公园,翡翠湾-1801 | 备注:灯光

---
最后更新: 2026-07-10
"""


class TestRefs(unittest.TestCase):

    def test_refs_filter(self):
        root = _mkroot({"保利中央公园.md": PROJ_A}, refs_index=REFS_INDEX)
        with _serve(root) as port:
            st, _, d = _get_json(port, "/api/projects/" + quote("保利中央公园") + "/refs")
        self.assertEqual(st, 200)
        ids = {r["id"] for r in d["refs"]}
        self.assertEqual(ids, {"r1", "r3"})  # r2 只用于翡翠湾
        r1 = next(r for r in d["refs"] if r["id"] == "r1")
        self.assertEqual(r1["file"], "refs/a.jpg")
        self.assertIn("奶油风", r1["style"])
        self.assertIn("玄关", r1["space"])
        self.assertEqual(r1["note"], "柜体")

    def test_refs_index_missing_empty(self):
        root = _mkroot({"保利中央公园.md": PROJ_A})  # 无 refs-index.md
        with _serve(root) as port:
            st, _, d = _get_json(port, "/api/projects/" + quote("保利中央公园") + "/refs")
        self.assertEqual(st, 200)
        self.assertEqual(d["refs"], [])

    def test_refs_bad_key_404(self):
        root = _mkroot({"保利中央公园.md": PROJ_A}, refs_index=REFS_INDEX)
        with _serve(root) as port:
            for k in ("..", "%2e%2e", "a%2fb"):
                st, _, _ = _req(port, f"/api/projects/{k}/refs")
                self.assertEqual(st, 404, f"key={k!r} 应 404")


# ── /api/refs/file/<path> 安全闸(本 track 唯一新增文件读出面) ───────────────
class TestRefsFile(unittest.TestCase):

    def test_file_serve_ok(self):
        root = _mkroot({}, refs_index=REFS_INDEX)
        _write_bytes(os.path.join(root, "refs", "a.jpg"), b"\xff\xd8\xffJPEGDATA")
        with _serve(root) as port:
            st, hd, body = _req(port, "/api/refs/file/a.jpg")
        self.assertEqual(st, 200)
        self.assertEqual(hd["content-type"], "image/jpeg")
        self.assertIn(b"JPEGDATA", body)
        self.assertIn("max-age", hd.get("cache-control", ""))

    def test_file_chinese_name(self):
        root = _mkroot({})
        _write_bytes(os.path.join(root, "refs", "玄关效果图.png"))
        with _serve(root) as port:
            st, hd, _ = _req(port, "/api/refs/file/" + quote("玄关效果图.png"))
        self.assertEqual(st, 200)
        self.assertEqual(hd["content-type"], "image/png")

    def test_file_subdir_ok(self):
        root = _mkroot({})
        os.makedirs(os.path.join(root, "refs", "sub"))
        _write_bytes(os.path.join(root, "refs", "sub", "x.gif"))
        with _serve(root) as port:
            st, hd, _ = _req(port, "/api/refs/file/sub/x.gif")
        self.assertEqual(st, 200)
        self.assertEqual(hd["content-type"], "image/gif")

    # Gate C —— 扩展白名单:refs 内真实非图片文件不得被读出
    def test_file_ext_whitelist(self):
        root = _mkroot({})
        with open(os.path.join(root, "refs", "notes.txt"), "w") as fh:
            fh.write("SECRET-NOTES")
        with _serve(root) as port:
            st, _, body = _req(port, "/api/refs/file/notes.txt")
        self.assertEqual(st, 404)
        self.assertNotIn(b"SECRET-NOTES", body)

    # Gate A —— 字符集白名单:含非法字符的路径拒服务(即便真有此文件)
    def test_file_charset_gate(self):
        root = _mkroot({})
        _write_bytes(os.path.join(root, "refs", "bad!.png"))  # 真实存在
        with _serve(root) as port:
            st, _, _ = _req(port, "/api/refs/file/" + quote("bad!.png"))
        self.assertEqual(st, 404)  # ! 不在字符集白名单 → 404,而非 200

    # Gate B —— realpath 前缀:裸 ../ 逃出 refs/ 一律 404 且不泄露内容
    def test_file_traversal(self):
        root = _mkroot({})
        # refs 外(ds_root 下)放一张真图片,逃逸若成立会被读到
        _write_bytes(os.path.join(root, "outer.png"), b"LEAK-OUTER")
        with _serve(root) as port:
            for p in ("/api/refs/file/../outer.png",
                      "/api/refs/file/%2e%2e/outer.png",
                      "/api/refs/file/sub/../../outer.png"):
                st, _, body = _req(port, p)
                self.assertEqual(st, 404, f"{p} -> {st}")
                self.assertNotIn(b"LEAK-OUTER", body)

    # Gate B —— realpath 前缀:refs 内 symlink 指向外部,realpath 展开后必须被拦
    def test_file_symlink_escape(self):
        if not hasattr(os, "symlink"):
            self.skipTest("平台无 symlink")
        root = _mkroot({})
        outer = os.path.join(root, "outer_secret.png")
        _write_bytes(outer, b"LEAK-SYMLINK")
        os.symlink(outer, os.path.join(root, "refs", "escape.png"))
        with _serve(root) as port:
            st, _, body = _req(port, "/api/refs/file/escape.png")
        self.assertEqual(st, 404)
        self.assertNotIn(b"LEAK-SYMLINK", body)

    def test_file_not_found_no_path_leak(self):
        root = _mkroot({})
        with _serve(root) as port:
            st, _, body = _req(port, "/api/refs/file/nope.png")
        self.assertEqual(st, 404)
        self.assertNotIn(b"nope.png", body)  # 404 不回显路径

    def test_file_write_methods_405(self):
        root = _mkroot({})
        _write_bytes(os.path.join(root, "refs", "a.png"))
        with _serve(root) as port:
            for m in ("POST", "PUT", "DELETE", "PATCH"):
                st, hd, _ = _req(port, "/api/refs/file/a.png", method=m)
                self.assertEqual(st, 405, f"{m} -> {st}")
                self.assertEqual(hd.get("allow"), "GET")


if __name__ == "__main__":
    unittest.main(verbosity=2)
