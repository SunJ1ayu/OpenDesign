#!/usr/bin/env python3
"""ds_web 写针孔 ⑩ `POST /api/projects/stage` 的 oracle
—— track opendesign-stage-history §7(切阶段)。

跑法:  python3 tests/test_ds_web_stage.py
纯 stdlib、离线、端口 0。

契约(design.md §7):薄壳,posture 逐条照抄既有 `_edit_change`:
  CT application/json → 0 < len ≤ OPEN_BODY_MAX → JSON dict + 键白名单
  {project, stage}(多余键即拒,防夹带 ds_root/today 走私)→ 两键都必须非空 str
  → ds_tools.set_stage(...)   ← 名字闸/词表/锁/页脚 bump 全在核心里
错误码:bad_stage 400 / project_not_found 404 / bad_name·path_escape 404。
**写口不回显词表**;词表由 `GET /api/projects` 的顶层 `stages` 下发,值 ==
ds_tools.PROJECT_STAGES(单一真相源,漂移即红)。

red-check:未实现前该路径落 do_POST 的兜底 → 404/405,happy 组红;
`/api/projects` 无 stages 键 → 词表组红。
"""
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_tools  # noqa: E402
import ds_web  # noqa: E402

STAGE_PATH = "/api/projects/stage"
KEY = "翡翠湾-1801"
PROJ_MD = """# 翡翠湾-1801

- 业主: [[李四]]
- 阶段: 方案深化
- 当前状态: 等瓦工进场

## 变更记录

- [待确认] C1 2026-07-01 主卧灯位右移

---
最后更新: 2026-07-01
"""


def _mkroot() -> str:
    d = tempfile.mkdtemp(prefix="ds_web_stage_")
    os.makedirs(os.path.join(d, "projects"), exist_ok=True)
    with open(os.path.join(d, "projects", f"{KEY}.md"), "w", encoding="utf-8") as fh:
        fh.write(PROJ_MD)
    return d


def _mkdist() -> str:
    d = tempfile.mkdtemp(prefix="ds_web_stage_dist_")
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


def _post(port, body, path=STAGE_PATH, ctype="application/json"):
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


def _md(root, key=KEY):
    with open(os.path.join(root, "projects", f"{key}.md"), encoding="utf-8") as fh:
        return fh.read()


class StagePinholeHappy(unittest.TestCase):
    def test_sets_stage_on_disk(self):
        root = _mkroot()
        with _serve(root) as port:
            st, body = _post(port, {"project": KEY, "stage": "施工图"})
            self.assertEqual(200, st, body)
            self.assertTrue(body.get("ok"), body)
            self.assertEqual("施工图", body.get("stage"), body)
            self.assertEqual("方案深化", body.get("prev"), "应回传原阶段供 UI 播报")
        text = _md(root)
        self.assertIn("- 阶段: 施工图", text)
        self.assertNotIn("方案深化", text.split("## 变更记录")[0],
                         "头部不许残留旧阶段")

    def test_can_go_backwards(self):
        """返工很正常:允许回退到更早的阶段(核心语义,针孔不许加额外约束)。"""
        root = _mkroot()
        with _serve(root) as port:
            st, _ = _post(port, {"project": KEY, "stage": "量房"})
            self.assertEqual(200, st)
        self.assertIn("- 阶段: 量房", _md(root))

    def test_bumps_last_updated(self):
        root = _mkroot()
        with _serve(root) as port:
            _post(port, {"project": KEY, "stage": "软装"})
        last = _md(root).rstrip().split("\n")[-1]
        self.assertTrue(last.startswith("最后更新:"), last)
        self.assertNotIn("2026-07-01", last, "页脚应 bump 到今天,不再是旧日期")

    def test_change_lines_untouched(self):
        root = _mkroot()
        before = [ln for ln in _md(root).split("\n") if ln.startswith("- [")]
        with _serve(root) as port:
            _post(port, {"project": KEY, "stage": "竣工验收"})
        after = [ln for ln in _md(root).split("\n") if ln.startswith("- [")]
        self.assertEqual(before, after, "改阶段不许碰变更行")


class StagePinholeRejects(unittest.TestCase):
    """一切拒绝路径:状态码对 + **档案逐字节不变**。"""

    def _reject(self, want_status, msg, **kwargs):
        root = _mkroot()
        before = _md(root)
        with _serve(root) as port:
            st, _ = _post(port, **kwargs)
        self.assertEqual(want_status, st, msg)
        self.assertEqual(before, _md(root), f"{msg}:拒绝路径必须零落盘")

    def test_stage_not_in_vocab(self):
        self._reject(400, "词表外的阶段应 400",
                     body={"project": KEY, "stage": "拆迁"})

    def test_stage_injection_attempts(self):
        for bad in ("施工图\n- 业主: [[黑客]]", "## 变更记录", "施工图 | 软装",
                    "- 阶段: 售后", "施工图\r\n最后更新: 2099-01-01"):
            with self.subTest(bad=bad):
                self._reject(400, f"注入尝试 {bad!r} 应被词表精确匹配挡下",
                             body={"project": KEY, "stage": bad})

    def test_unknown_project(self):
        self._reject(404, "不存在的项目应 404",
                     body={"project": "查无此项目", "stage": "施工图"})

    def test_name_gate(self):
        for bad in ("../../etc/passwd", "a/b", "..", "小区\\1801", "项目%2e%2e"):
            with self.subTest(bad=bad):
                self._reject(404, f"名字闸应挡下 {bad!r}",
                             body={"project": bad, "stage": "施工图"})

    def test_bad_content_type(self):
        self._reject(400, "非 json CT 应 400(CSRF 纵深)",
                     body={"project": KEY, "stage": "施工图"},
                     ctype="text/plain")
        self._reject(400, "缺 CT 应 400",
                     body={"project": KEY, "stage": "施工图"}, ctype="")

    def test_not_a_dict(self):
        for payload in (b"[]", b"\"x\"", b"123", b"null", b"{", b""):
            with self.subTest(payload=payload):
                self._reject(400, f"非对象 body {payload!r} 应 400", body=payload)

    def test_extra_keys_rejected(self):
        """多余键即拒:防夹带 ds_root/today 走私(同 _edit_change 先例)。"""
        for extra in ({"ds_root": "/etc"}, {"today": "2099-01-01"},
                      {"new_status": "已完成"}, {"cnum": 1}):
            with self.subTest(extra=extra):
                self._reject(400, f"夹带 {extra} 应 400",
                             body={"project": KEY, "stage": "施工图", **extra})

    def test_missing_or_wrong_types(self):
        for body in ({"project": KEY}, {"stage": "施工图"}, {},
                     {"project": "", "stage": "施工图"},
                     {"project": KEY, "stage": ""},
                     {"project": 1, "stage": "施工图"},
                     {"project": KEY, "stage": ["施工图"]},
                     {"project": None, "stage": None}):
            with self.subTest(body=body):
                self._reject(400, f"{body} 应 400", body=body)

    def test_oversized_body(self):
        big = json.dumps({"project": KEY, "stage": "施工图",
                          }).encode() + b" " * (ds_web.OPEN_BODY_MAX + 10)
        self._reject(400, "超尺寸 body 应 400", body=big)


class StagePinholeSurface(unittest.TestCase):
    def test_get_on_stage_path_not_allowed(self):
        """只读墙:GET 这条路径不许有内容面(405/404 都可,200 绝不可)。"""
        root = _mkroot()
        with _serve(root) as port:
            st, _ = _get(port, STAGE_PATH)
        self.assertIn(st, (404, 405), f"GET {STAGE_PATH} 实得 {st}")

    def test_path_is_exact_match(self):
        """精确匹配,不是前缀:相邻路径不许被这条针孔接管。"""
        root = _mkroot()
        before = _md(root)
        with _serve(root) as port:
            for path in (STAGE_PATH + "/", STAGE_PATH + "x",
                         STAGE_PATH + "/../projects/stage"):
                with self.subTest(path=path):
                    st, _ = _post(port, {"project": KEY, "stage": "施工图"},
                                  path=path)
                    self.assertNotEqual(200, st, f"{path} 不该被接管")
        self.assertEqual(before, _md(root), "路径走私必须零落盘")

    def test_host_gate_inherited(self):
        """入口 Host 白名单(H2 修复)对新针孔同样生效。"""
        root = _mkroot()
        before = _md(root)
        with _serve(root) as port:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            conn.request("POST", STAGE_PATH,
                         body=json.dumps({"project": KEY, "stage": "施工图"}),
                         headers={"Content-Type": "application/json",
                                  "Host": "evil.example.com"})
            st = conn.getresponse().status
            conn.close()
        self.assertNotEqual(200, st, "外部 Host 必须被拒(DNS rebinding)")
        self.assertEqual(before, _md(root))


class StageVocabDelivery(unittest.TestCase):
    """词表单一真相源:前端不许硬编码副本 —— 由 /api/projects 下发。"""

    def test_projects_carries_stages(self):
        root = _mkroot()
        with _serve(root) as port:
            st, body = _get(port, "/api/projects")
        self.assertEqual(200, st)
        self.assertIn("stages", body, "应下发阶段词表")
        self.assertEqual(list(ds_tools.PROJECT_STAGES), body["stages"],
                         "词表必须与 ds_tools.PROJECT_STAGES 逐项一致(含顺序)")

    def test_projects_still_lists_projects(self):
        """加字段不许改既有形状(回归)。"""
        root = _mkroot()
        with _serve(root) as port:
            st, body = _get(port, "/api/projects")
        self.assertEqual(200, st)
        keys = [p["key"] for p in body["projects"]]
        self.assertIn(KEY, keys)
        stages = {p["key"]: p["stage"] for p in body["projects"]}
        self.assertEqual("方案深化", stages[KEY])


if __name__ == "__main__":
    unittest.main(verbosity=2)
