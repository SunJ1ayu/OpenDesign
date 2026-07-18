#!/usr/bin/env python3
"""ds_web 收件箱端点 oracle — track opendesign-intake T3。

跑法:  python3 tests/test_ds_web_intake.py
覆盖:
  GET  /api/intake             收件箱清单+建议+pending plans(只读)
  POST /api/intake/approve     针孔④:人工确认 = approve+apply 一气
                               (posture 同 edit-change:CT json/键白名单/
                                body 上限/plan 必须落在工作区根内)

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

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # design-studio/
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_intake    # noqa: E402
import ds_organize  # noqa: E402
import ds_web       # noqa: E402

PROJ = "20260612 周宁 龙腾世纪 12#1802"


def _write(path, content="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def _mkdist() -> str:
    d = tempfile.mkdtemp(prefix="ds_web_intake_dist_")
    _write(os.path.join(d, "index.html"), "<!doctype html><div>x</div>")
    return d


def _mkfixture():
    """ds_root(config/plans 落这)+ 工作区(收件箱/项目/共享资源)。"""
    ds = tempfile.mkdtemp(prefix="ds_web_intake_ds_")
    ws = tempfile.mkdtemp(prefix="ds_web_intake_ws_")
    os.makedirs(os.path.join(ws, "00-收件箱"))
    os.makedirs(os.path.join(ws, "01-项目", PROJ))
    os.makedirs(os.path.join(ws, "03-共享资源", "参考图库"))
    _write(os.path.join(ds, "config", "workspace.json"),
           json.dumps({"root": ws, "projects": {}}, ensure_ascii=False))
    return ds, ws


@contextmanager
def _serve(ds_root: str):
    httpd = ds_web.make_server(ds_root, _mkdist(), port=0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get_json(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", path)
    r = conn.getresponse()
    body = r.read()
    conn.close()
    return r.status, (json.loads(body.decode("utf-8")) if body else None)


def _post(port, path, body=None, ctype="application/json", raw=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    data = raw if raw is not None else json.dumps(body or {}).encode("utf-8")
    conn.request("POST", path, body=data, headers={"Content-Type": ctype})
    r = conn.getresponse()
    out = r.read()
    conn.close()
    return r.status, (json.loads(out.decode("utf-8")) if out else None)


class TestIntakeGet(unittest.TestCase):
    def setUp(self):
        self.ds, self.ws = _mkfixture()
        self.inbox = os.path.join(self.ws, "00-收件箱")

    def test_get_entries_and_suggestions(self):
        _write(os.path.join(self.inbox, "龙腾世纪玄关.jpg"))
        _write(os.path.join(self.inbox, "户型图.dwg"))
        with _serve(self.ds) as port:
            st, r = _get_json(port, "/api/intake")
        self.assertEqual(st, 200)
        self.assertTrue(r["configured"])
        by = {e["name"]: e for e in r["entries"]}
        self.assertEqual(by["龙腾世纪玄关.jpg"]["category"]["id"], "参考图")
        self.assertEqual(by["龙腾世纪玄关.jpg"]["project"], PROJ)
        self.assertEqual(r["pending"], [])

    def test_get_pending_plans_workspace_only(self):
        _write(os.path.join(self.inbox, "参考.jpg"))
        r = ds_intake.stage_intake(
            [{"name": "参考.jpg", "project": None, "category": "参考图"}],
            allowed_roots=[self.ws], ds_root=self.ds)
        pid = r["plan_id"]
        # 一份工作区外的 plan(比如 Desktop 清理)不该出现在收件箱卡片里
        other = tempfile.mkdtemp(prefix="ds_web_intake_other_")
        _write(os.path.join(other, "z.txt"))
        ds_organize.stage_plan(other, [{"op": "move", "src": "z.txt",
                                        "dst": "y.txt"}],
                               allowed_roots=[other], ds_root=self.ds)
        with _serve(self.ds) as port:
            st, r = _get_json(port, "/api/intake")
        self.assertEqual(st, 200)
        self.assertEqual([p["plan_id"] for p in r["pending"]], [pid])
        ops = r["pending"][0]["ops"]
        self.assertEqual(ops[0]["src_rel"].replace("\\", "/"), "00-收件箱/参考.jpg")
        self.assertEqual(ops[0]["dst_rel"].replace("\\", "/"),
                         "03-共享资源/参考图库/参考.jpg")

    def test_get_unconfigured_degrades(self):
        os.remove(os.path.join(self.ds, "config", "workspace.json"))
        with _serve(self.ds) as port:
            st, r = _get_json(port, "/api/intake")
        self.assertEqual(st, 200)
        self.assertFalse(r["configured"])
        self.assertEqual(r["entries"], [])
        self.assertEqual(r["pending"], [])


class TestIntakeApprove(unittest.TestCase):
    def setUp(self):
        self.ds, self.ws = _mkfixture()
        self.inbox = os.path.join(self.ws, "00-收件箱")

    def _staged(self):
        _write(os.path.join(self.inbox, "参考.jpg"), "IMG")
        r = ds_intake.stage_intake(
            [{"name": "参考.jpg", "project": None, "category": "参考图"}],
            allowed_roots=[self.ws], ds_root=self.ds)
        return r["plan_id"]

    def test_approve_applies_and_moves(self):
        pid = self._staged()
        with _serve(self.ds) as port:
            st, r = _post(port, "/api/intake/approve", {"plan_id": pid})
        self.assertEqual(st, 200, r)
        self.assertTrue(r["ok"])
        self.assertTrue(os.path.exists(os.path.join(
            self.ws, "03-共享资源", "参考图库", "参考.jpg")))
        self.assertFalse(os.path.exists(os.path.join(self.inbox, "参考.jpg")))
        # audit 落盘
        with open(os.path.join(self.ds, "organize", "audit.log"),
                  encoding="utf-8") as fh:
            self.assertIn(pid, fh.read())

    def test_approve_rejects_bad_requests(self):
        pid = self._staged()
        with _serve(self.ds) as port:
            st, _ = _post(port, "/api/intake/approve", {"plan_id": pid},
                          ctype="text/plain")
            self.assertEqual(st, 400)  # CT 闸
            st, _ = _post(port, "/api/intake/approve",
                          {"plan_id": pid, "extra": 1})
            self.assertEqual(st, 400)  # 键白名单
            st, _ = _post(port, "/api/intake/approve", {"plan_id": "../../x"})
            self.assertEqual(st, 400)  # plan_id 格式
            st, _ = _post(port, "/api/intake/approve",
                          {"plan_id": "20990101-000000-abcdef"})
            self.assertEqual(st, 404)  # 不存在
            st, _ = _post(port, "/api/intake/approve", raw=b"{broken")
            self.assertEqual(st, 400)  # 坏 json
        # 全程零执行:文件原地
        self.assertTrue(os.path.exists(os.path.join(self.inbox, "参考.jpg")))

    def test_approve_rejects_non_workspace_plan(self):
        """针孔只批工作区内的 plan:Desktop 清理 plan 走 ds-approve CLI,不走网页。"""
        other = tempfile.mkdtemp(prefix="ds_web_intake_other_")
        _write(os.path.join(other, "z.txt"))
        r = ds_organize.stage_plan(other, [{"op": "move", "src": "z.txt",
                                            "dst": "y.txt"}],
                                   allowed_roots=[other], ds_root=self.ds)
        with _serve(self.ds) as port:
            st, body = _post(port, "/api/intake/approve",
                             {"plan_id": r["plan_id"]})
        self.assertEqual(st, 403)
        self.assertEqual(body["error"], "not_intake_plan")
        self.assertTrue(os.path.exists(os.path.join(other, "z.txt")))  # 未动

    def test_approve_already_applied(self):
        pid = self._staged()
        ds_organize.approve_plan(pid, ds_root=self.ds)
        ds_organize.apply_plan(pid, [self.ws], ds_root=self.ds)
        with _serve(self.ds) as port:
            st, body = _post(port, "/api/intake/approve", {"plan_id": pid})
        self.assertEqual(st, 409)
        self.assertEqual(body["error"], "already_applied")

    def test_approve_malformed_plan_root_rejected(self):
        """root 缺失的坏 plan:realpath("") = 进程 cwd,不能靠 cwd 落点混进
        工作区判定(GLM panel 抓的批准侧不对称)——列表不列,批准 403。"""
        plans = os.path.join(self.ds, "organize", "plans")
        os.makedirs(plans, exist_ok=True)
        pid = "20260717-000000-abcdef"
        _write(os.path.join(plans, f"plan_{pid}.json"),
               json.dumps({"plan_id": pid, "created": "x",
                           "operations": [], "applied_at": None}))
        with _serve(self.ds) as port:
            st, r = _get_json(port, "/api/intake")
            self.assertEqual([p["plan_id"] for p in r["pending"]], [])
            st, body = _post(port, "/api/intake/approve", {"plan_id": pid})
        self.assertEqual(st, 403)
        self.assertEqual(body["error"], "not_intake_plan")

    def test_approve_bad_host_rejected(self):
        """Host 闸在 do_POST 入口继承(H2):非白名单 Host 一律 403。"""
        with _serve(self.ds) as port:
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            c.request("POST", "/api/intake/approve",
                      body=b'{"plan_id":"x"}',
                      headers={"Content-Type": "application/json",
                               "Host": "evil.example.com"})
            r = c.getresponse()
            st = r.status
            r.read()
            c.close()
        self.assertEqual(st, 403)

    def test_other_posts_still_405(self):
        with _serve(self.ds) as port:
            st, _ = _post(port, "/api/intake", {"x": 1})
            self.assertEqual(st, 405)  # 针孔精确匹配,GET 面维持只读
            st, _ = _post(port, "/api/intake/approve/extra", {"plan_id": "x"})
            self.assertEqual(st, 405)


class TestIntakeScanPinhole(unittest.TestCase):
    """POST /api/intake/scan(空 body {})→ ds_intake.stage_inbox_auto。
    只读墙受控开口,posture 同 /api/intake/approve;allowed_roots=[工作区根]。
    主 agent 拥有,执行腿 off-limits。"""

    def setUp(self):
        self.ds, self.ws = _mkfixture()
        self.inbox = os.path.join(self.ws, "00-收件箱")

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)
        shutil.rmtree(self.ws, ignore_errors=True)

    def _post_host(self, port, path, body, host):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("POST", path,
                     body=json.dumps(body).encode("utf-8"),
                     headers={"Content-Type": "application/json", "Host": host})
        r = conn.getresponse(); r.read(); conn.close()
        return r.status

    def test_scan_stages_confident(self):
        # 龙腾世纪.dwg → PROJ 唯一命中(project 级);参考.jpg → 参考图(workspace)
        _write(os.path.join(self.inbox, "龙腾世纪玄关.dwg"))
        _write(os.path.join(self.inbox, "参考.jpg"))
        _write(os.path.join(self.inbox, "未知.xyz"))
        with _serve(self.ds) as port:
            st, r = _post(port, "/api/intake/scan", {})
        self.assertEqual(st, 200)
        self.assertTrue(r["ok"])
        self.assertEqual(r["staged"], 2)
        self.assertIsNotNone(r["plan_id"])
        self.assertEqual([s["name"] for s in r["skipped"]], ["未知.xyz"])

    def test_scan_empty_inbox_ok(self):
        with _serve(self.ds) as port:
            st, r = _post(port, "/api/intake/scan", {})
        self.assertEqual(st, 200)
        self.assertEqual(r["staged"], 0)

    def test_scan_ct_gate(self):
        with _serve(self.ds) as port:
            st, _ = _post(port, "/api/intake/scan", {}, ctype="text/plain")
        self.assertEqual(st, 400)

    def test_scan_extra_key_rejected(self):
        # 空 body 白名单:任何键即拒
        with _serve(self.ds) as port:
            st, _ = _post(port, "/api/intake/scan", {"path": "/etc"})
        self.assertEqual(st, 400)

    def test_scan_exact_match_405(self):
        with _serve(self.ds) as port:
            for p in ("/api/intake/scanx", "/api/intake/scan/", "/api/intake"):
                st, _ = _post(port, p, {})
                self.assertEqual(st, 405, f"{p} 应 405")

    def test_scan_host_gate_inherited(self):
        with _serve(self.ds) as port:
            self.assertEqual(self._post_host(port, "/api/intake/scan", {}, "evil.example"), 403)

    def test_scan_unconfigured(self):
        empty = tempfile.mkdtemp(prefix="ds_web_intake_empty_")
        self.addCleanup(shutil.rmtree, empty, ignore_errors=True)
        with _serve(empty) as port:
            st, r = _post(port, "/api/intake/scan", {})
        self.assertEqual(st, 409)
        self.assertEqual(r["error"], "workspace_not_configured")


if __name__ == "__main__":
    unittest.main(verbosity=2)
