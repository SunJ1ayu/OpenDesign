#!/usr/bin/env python3
"""ds_web 写针孔 ⑪ `POST /api/refs/update` 的 oracle
—— track opendesign-stage-history §8(参考图标签/备注就地改)。

跑法:  python3 tests/test_ds_web_refs_update.py
纯 stdlib、离线、端口 0。

契约(design.md §8):薄壳,posture 同 ⑩ / `_edit_change`:
  CT application/json → 0 < len ≤ OPEN_BODY_MAX → JSON dict + 键白名单
  {ref_id, style, space, note}(多余键即拒)→ 给了的字段必须是 str
  → ds_refs.update_ref(...)   ← 词表/分段重写/锁/页脚 bump 全在核心里
错误码:ref_not_found 404 / ambiguous_ref 409 / malformed_entry 409 /
        style_unknown·space_unknown·no_fields 400。
词表由 `GET /api/projects/<key>/refs` 的 `vocab` 下发(风格 = _load_styles,空间 = SPACES),
前端不许硬编码副本。

red-check:未实现前该路径落兜底 → 404/405,happy 组红;refs 响应无 vocab → 词表组红。
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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tests/ 自己
import _tmpreg  # noqa: E402  临时目录登记表,见 tests/_tmpreg.py
import ds_refs  # noqa: E402
import ds_web  # noqa: E402

UPDATE_PATH = "/api/refs/update"
KEY = "翡翠湾-1801"
TODAY = "2026-07-21"
PROJ_MD = """# 翡翠湾-1801

- 业主: [[李四]]
- 阶段: 方案深化

## 变更记录

- [待确认] C1 2026-07-01 主卧灯位右移

---
最后更新: 2026-07-01
"""


def _touch(path, data=b"\xff\xd8fakejpg"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def _mkroot() -> str:
    d = _tmpreg.mkdtemp("ds_web_refupd_")
    os.makedirs(os.path.join(d, "projects"), exist_ok=True)
    with open(os.path.join(d, "projects", f"{KEY}.md"), "w", encoding="utf-8") as fh:
        fh.write(PROJ_MD)
    _touch(os.path.join(d, "refs", "奶油风", "客厅", "a.jpg"))
    _touch(os.path.join(d, "refs", "侘寂风", "主卧", "b.jpg"))
    ds_refs.add_ref("refs/奶油风/客厅/a.jpg", "奶油风", "客厅", "小红书",
                    "弧形吊顶", ds_root=d, today=TODAY)
    ds_refs.add_ref("refs/侘寂风/主卧/b.jpg", "侘寂风", "主卧", "Pinterest",
                    "原木床头", ds_root=d, today=TODAY)
    # 两条都挂到项目上 —— /api/refs/<key> 才看得见它们
    ds_refs.link_ref("r1", KEY, ds_root=d, today=TODAY)
    ds_refs.link_ref("r2", KEY, ds_root=d, today=TODAY)
    return d


def _mkdist() -> str:
    d = _tmpreg.mkdtemp("ds_web_refupd_dist_")
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<!doctype html><div>x</div>")
    return d


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


def _post(port, body, path=UPDATE_PATH, ctype="application/json"):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    payload = (json.dumps(body).encode("utf-8") if isinstance(body, (dict, list))
               else body)
    headers = {"Content-Type": ctype} if ctype else {}
    conn.request("POST", path, body=payload, headers=headers)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    try:
        return r.status, json.loads(data.decode("utf-8"))
    except Exception:
        return r.status, None


def _get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", path)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    try:
        return r.status, json.loads(data.decode("utf-8"))
    except Exception:
        return r.status, None


def _index(root):
    with open(os.path.join(root, "refs-index.md"), encoding="utf-8") as fh:
        return fh.read()


def _line(root, ref_id):
    for ln in _index(root).split("\n"):
        if ln.startswith(f"- [{ref_id}] "):
            return ln
    return None


class RefsUpdateHappy(unittest.TestCase):
    def test_note_written(self):
        root = _mkroot()
        with _serve(root) as port:
            st, body = _post(port, {"ref_id": "r1", "note": "改成平顶"})
            self.assertEqual(200, st, body)
            self.assertTrue(body.get("ok"), body)
        self.assertIn("备注:改成平顶", _line(root, "r1"))

    def test_tags_written(self):
        root = _mkroot()
        with _serve(root) as port:
            st, body = _post(port, {"ref_id": "r1", "style": "侘寂风",
                                    "space": "主卧,客厅"})
            self.assertEqual(200, st, body)
        self.assertTrue(_line(root, "r1").startswith("- [r1] 侘寂风|主卧,客厅 "),
                        _line(root, "r1"))

    def test_other_segments_and_entries_untouched(self):
        root = _mkroot()
        before_r2 = _line(root, "r2")
        with _serve(root) as port:
            _post(port, {"ref_id": "r1", "note": "换个备注"})
        self.assertEqual(before_r2, _line(root, "r2"), "改 r1 不许碰 r2")
        line = _line(root, "r1")
        self.assertIn("来源:小红书", line)
        self.assertIn("文件:refs/奶油风/客厅/a.jpg", line)
        self.assertIn(f"用于:{KEY}", line)

    def test_visible_via_refs_get(self):
        """改完立刻能从读侧看到 —— 前端保存后重拉的依据。"""
        root = _mkroot()
        with _serve(root) as port:
            _post(port, {"ref_id": "r1", "style": "侘寂风", "note": "新标签"})
            st, body = _get(port, f"/api/projects/{quote(KEY)}/refs")
            self.assertEqual(200, st)
            r1 = next(r for r in body["refs"] if r["id"] == "r1")
            self.assertEqual(["侘寂风"], r1["style"])
            self.assertEqual("新标签", r1["note"])


class RefsUpdateRejects(unittest.TestCase):
    """一切拒绝路径:状态码对 + **索引逐字节不变**。"""

    def _reject(self, want_status, msg, **kwargs):
        root = _mkroot()
        before = _index(root)
        with _serve(root) as port:
            st, _ = _post(port, **kwargs)
        self.assertEqual(want_status, st, msg)
        self.assertEqual(before, _index(root), f"{msg}:拒绝路径必须零落盘")

    def test_unknown_ref(self):
        self._reject(404, "不存在的 ref 应 404", body={"ref_id": "r999", "note": "x"})

    def test_bad_ref_id_shapes(self):
        for bad in ("", "1", "R1", "r", "../r1", "r1 ", "r-1"):
            with self.subTest(bad=bad):
                self._reject(404, f"畸形 ref_id {bad!r} 应 404",
                             body={"ref_id": bad, "note": "x"})

    def test_no_fields(self):
        self._reject(400, "一个字段都不给应 400", body={"ref_id": "r1"})

    def test_style_and_space_vocab(self):
        self._reject(400, "词表外风格应 400",
                     body={"ref_id": "r1", "style": "赛博朋克风"})
        self._reject(400, "词表外空间应 400",
                     body={"ref_id": "r1", "space": "停机坪"})
        self._reject(400, "空标签应 400", body={"ref_id": "r1", "style": ""})

    def test_extra_keys_rejected(self):
        for extra in ({"ds_root": "/etc"}, {"today": "2099-01-01"},
                      {"file": "refs/../../etc/passwd"}, {"used": "别的项目"},
                      {"source": "伪造来源"}):
            with self.subTest(extra=extra):
                self._reject(400, f"夹带 {extra} 应 400",
                             body={"ref_id": "r1", "note": "x", **extra})

    def test_wrong_types(self):
        for body in ({"ref_id": "r1", "note": 1}, {"ref_id": "r1", "style": ["侘寂风"]},
                     {"ref_id": "r1", "space": {"a": 1}}, {"ref_id": 1, "note": "x"},
                     {"ref_id": None, "note": "x"}, {"note": "x"}):
            with self.subTest(body=body):
                self._reject(400, f"{body} 应 400", body=body)

    def test_bad_content_type(self):
        self._reject(400, "非 json CT 应 400(CSRF 纵深)",
                     body={"ref_id": "r1", "note": "x"}, ctype="text/plain")
        self._reject(400, "缺 CT 应 400", body={"ref_id": "r1", "note": "x"},
                     ctype="")

    def test_not_a_dict(self):
        for payload in (b"[]", b"\"x\"", b"123", b"null", b"{", b""):
            with self.subTest(payload=payload):
                self._reject(400, f"非对象 body {payload!r} 应 400", body=payload)

    def test_oversized_body(self):
        big = json.dumps({"ref_id": "r1", "note": "x"}).encode() \
            + b" " * (ds_web.OPEN_BODY_MAX + 10)
        self._reject(400, "超尺寸 body 应 400", body=big)

    def test_ambiguous_entry_conflicts(self):
        root = _mkroot()
        line = _line(root, "r1")
        path = os.path.join(root, "refs-index.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace(line, line + "\n" + line, 1))
        before = _index(root)
        with _serve(root) as port:
            st, _ = _post(port, {"ref_id": "r1", "note": "改不了"})
        self.assertEqual(409, st, "重复 id 应 409")
        self.assertEqual(before, _index(root))

    def test_malformed_entry_conflicts(self):
        root = _mkroot()
        path = os.path.join(root, "refs-index.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace(" | 备注:弧形吊顶", "", 1))
        before = _index(root)
        with _serve(root) as port:
            st, _ = _post(port, {"ref_id": "r1", "note": "补一个"})
        self.assertEqual(409, st, "畸形索引行应 409")
        self.assertEqual(before, _index(root))


class RefsUpdateSurface(unittest.TestCase):
    def test_get_on_update_path_not_allowed(self):
        root = _mkroot()
        with _serve(root) as port:
            st, _ = _get(port, UPDATE_PATH)
        self.assertIn(st, (404, 405), f"GET {UPDATE_PATH} 实得 {st}")

    def test_update_path_not_shadowed_by_file_server(self):
        """既有只读面是 `/api/refs/file/<rel>`(静态图)与 `/api/projects/<key>/refs`;
        新写口 `/api/refs/update` 不许被它们接管,GET 它也不许有内容面。"""
        root = _mkroot()
        with _serve(root) as port:
            st, body = _get(port, "/api/refs/file/update")
            self.assertNotEqual(200, st, f"GET /api/refs/file/update 实得 {st}")
            st, body = _get(port, f"/api/projects/{quote('update')}/refs")
            self.assertNotEqual(500, st, f"读面吃 update 当 key 不许 500,实得 {st}")

    def test_path_is_exact_match(self):
        root = _mkroot()
        before = _index(root)
        with _serve(root) as port:
            for path in (UPDATE_PATH + "/", UPDATE_PATH + "x",
                         UPDATE_PATH + "/../update"):
                with self.subTest(path=path):
                    st, _ = _post(port, {"ref_id": "r1", "note": "x"}, path=path)
                    self.assertNotEqual(200, st, f"{path} 不该被接管")
        self.assertEqual(before, _index(root))

    def test_host_gate_inherited(self):
        root = _mkroot()
        before = _index(root)
        with _serve(root) as port:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            conn.request("POST", UPDATE_PATH,
                         body=json.dumps({"ref_id": "r1", "note": "x"}),
                         headers={"Content-Type": "application/json",
                                  "Host": "evil.example.com"})
            st = conn.getresponse().status
            conn.close()
        self.assertNotEqual(200, st, "外部 Host 必须被拒(DNS rebinding)")
        self.assertEqual(before, _index(root))


class RefsVocabDelivery(unittest.TestCase):
    def test_refs_get_carries_vocab(self):
        root = _mkroot()
        with _serve(root) as port:
            st, body = _get(port, f"/api/projects/{quote(KEY)}/refs")
        self.assertEqual(200, st)
        self.assertIn("vocab", body, "应下发风格/空间词表")
        self.assertEqual(ds_refs._load_styles(root), body["vocab"]["style"],
                         "风格词表必须与核心逐项一致")
        self.assertEqual(list(ds_refs.SPACES), body["vocab"]["space"],
                         "空间词表必须与核心逐项一致")

    def test_refs_get_shape_unchanged(self):
        """加字段不许改既有形状(回归)。"""
        root = _mkroot()
        with _serve(root) as port:
            st, body = _get(port, f"/api/projects/{quote(KEY)}/refs")
        self.assertEqual(200, st)
        ids = sorted(r["id"] for r in body["refs"])
        self.assertEqual(["r1", "r2"], ids)
        r1 = next(r for r in body["refs"] if r["id"] == "r1")
        self.assertEqual({"id", "style", "space", "file", "note"}, set(r1),
                         "只回 UI 需要的字段:source/used 仍不外泄")


if __name__ == "__main__":
    unittest.main(verbosity=2)
