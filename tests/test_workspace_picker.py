"""业主手动选工作区 —— track opendesign-workspace-picker。

跑法:  python3 tests/test_workspace_picker.py

以前工作区只能靠助手设(set_workspace 走 MCP + 同意卡):首次在项目页填路径,其实是替业主往聊天里
发一句话;接好之后想换,界面上没有任何入口。现在界面上有「选择项目文件夹」:
先预览三种摆法各认出几个项目,再确定。业主亲手选的 = 同意本身,不走同意卡。

考的东西:
  P1 预览:三种摆法的计数与真实识别一致;「01-项目」总夹只在真的存在时才列;**只读**(配置、待确认一个字节都不动)
  P2 确定:按业主挑的摆法显式写入;换到摆法不同的文件夹时,旧的 projectsDir 不许残留(否则新根一个项目都认不出)
  P3 坏输入一律拒:相对路径 / 不存在 / 摆法非法(越界的总夹名、depth 不是 1/2)/ 与安装目录重叠
  P4 ds_web 针孔 posture:只收 JSON、键白名单、跨站 403;成功回 folder_count
  P5 模型碰不到:MCP 工具表里没有这两个入口
  P6 业主换了根,排队中的助手申请按既定规则判过期(判据 O10 的另一面)
  P7 (PR #4 审查)「01-项目」是软链接时,预览与接入后的项目数一致:总夹名取根下那一项自己的名字,
     不取链接目标的名字;链接指到工作区外时,预览老老实实说认不出,不许先说认出几个、接上后变 0

纯 stdlib、离线、端口 0。
"""
import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, HERE)
import ds_consent  # noqa: E402
import ds_tools    # noqa: E402
import ds_web      # noqa: E402


def _mkws():
    t = tempfile.mkdtemp(prefix="wspick_")
    ds = os.path.join(t, "ds")
    os.makedirs(os.path.join(ds, "config"))
    os.makedirs(os.path.join(ds, "projects"))
    ws = os.path.join(t, "ws")
    for p in ("01-项目/甲", "01-项目/乙", "2026/丙", "2026/丁", "散项目"):
        os.makedirs(os.path.join(ws, p))
    flat = os.path.join(t, "flat")                 # 没有总夹:项目直接摆着
    for p in ("戊", "己"):
        os.makedirs(os.path.join(flat, p))
    return t, ds, ws, flat


def _cfg(ds):
    p = os.path.join(ds, "config", "workspace.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _cfg_bytes(ds):
    p = os.path.join(ds, "config", "workspace.json")
    return open(p, "rb").read() if os.path.exists(p) else None


class P_核心(unittest.TestCase):
    def setUp(self):
        self.t, self.ds, self.ws, self.flat = _mkws()

    def tearDown(self):
        shutil.rmtree(self.t, ignore_errors=True)

    def test_p1a_预览的三种摆法与真实识别一致(self):
        r = ds_tools.preview_workspace(self.ws, ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        by = {l["layout"]: l for l in r["layouts"]}
        self.assertEqual(by["auto"]["projects_dir"], "01-项目")
        self.assertEqual(by["auto"]["count"], 2)
        self.assertEqual(sorted(by["auto"]["sample"]), ["乙", "甲"])
        self.assertEqual(by["direct"]["count"], 3)
        self.assertEqual(by["grouped"]["count"], 4)
        self.assertEqual(by["grouped"]["projects_depth"], 2)

    def test_p1b_没有总夹时不列auto(self):
        r = ds_tools.preview_workspace(self.flat, ds_root=self.ds)
        self.assertEqual([l["layout"] for l in r["layouts"]], ["direct", "grouped"])
        self.assertEqual(r["layouts"][0]["count"], 2)

    def test_p1c_预览只读_配置与待确认一个字节都不动(self):
        ds_tools.owner_set_workspace(self.flat, ".", 1, ds_root=self.ds)
        before = _cfg_bytes(self.ds)
        ds_tools.preview_workspace(self.ws, ds_root=self.ds)
        self.assertEqual(_cfg_bytes(self.ds), before)
        self.assertEqual(ds_consent.list_pending(self.ds), [])

    def test_p1d_预览与接入后的项目数一致(self):
        pv = {l["layout"]: l for l in ds_tools.preview_workspace(self.ws, ds_root=self.ds)["layouts"]}
        for name in ("auto", "direct", "grouped"):
            l = pv[name]
            r = ds_tools.owner_set_workspace(self.ws, l["projects_dir"], l["projects_depth"], ds_root=self.ds)
            self.assertEqual(r.get("folder_count"), l["count"], f"{name}:预览说 {l['count']},接上后是 {r}")

    def test_p2a_按挑的摆法显式写入(self):
        r = ds_tools.owner_set_workspace(self.ws, "01-项目", 1, ds_root=self.ds)
        self.assertEqual(r, {"ok": True, "root": os.path.realpath(self.ws), "folder_count": 2})
        self.assertEqual(_cfg(self.ds)["projectsDir"], "01-项目")
        ds_tools.owner_set_workspace(self.ws, ".", 2, ds_root=self.ds)
        c = _cfg(self.ds)
        self.assertEqual((c["projectsDir"], c.get("projectsDepth")), (".", 2))

    def test_p2b_换到摆法不同的文件夹_旧的projectsDir不许残留(self):
        ds_tools.owner_set_workspace(self.ws, "01-项目", 1, ds_root=self.ds)
        r = ds_tools.owner_set_workspace(self.flat, ".", 1, ds_root=self.ds)
        self.assertEqual(r.get("folder_count"), 2, "旧的「01-项目」残留 ⇒ 新根一个项目都认不出")
        self.assertEqual(_cfg(self.ds)["projectsDir"], ".")
        # depth 从 2 回到 1 也要真回去
        ds_tools.owner_set_workspace(self.ws, ".", 2, ds_root=self.ds)
        ds_tools.owner_set_workspace(self.ws, ".", 1, ds_root=self.ds)
        self.assertNotIn("projectsDepth", _cfg(self.ds))

    def test_p3_坏输入一律拒_且什么都不写(self):
        before = _cfg_bytes(self.ds)
        for args in (("相对/路径", ".", 1), (os.path.join(self.t, "没有"), ".", 1),
                     (self.ws, "../外面", 1), (self.ws, "a/b", 1), (self.ws, "C:x", 1),
                     (self.ws, ".", 3), (self.ws, ".", True), (self.ws, "", 1)):
            r = ds_tools.owner_set_workspace(*args, ds_root=self.ds)
            self.assertIn("error", r, f"{args} 应被拒:{r}")
        self.assertEqual(_cfg_bytes(self.ds), before)
        self.assertIn("error", ds_tools.preview_workspace("相对", ds_root=self.ds))
        self.assertIn("error", ds_tools.preview_workspace(os.path.join(self.t, "没有"), ds_root=self.ds))

    def test_p3b_与应用自己的目录重叠_预览和接入都拒(self):
        r = ds_tools.preview_workspace(self.ds, ds_root=self.ds)
        self.assertTrue(str(r.get("error", "")).startswith("工作区路径"), r)
        r = ds_tools.owner_set_workspace(self.ds, ".", 1, ds_root=self.ds)
        self.assertIn("error", r)

    def test_p5_模型碰不到_MCP工具表里没有这两个入口(self):
        try:
            import mcp  # noqa: F401
        except ImportError:
            self.skipTest("未装 mcp 包")
        import asyncio
        import ds_mcp
        os.environ["DS_ROOT"] = self.ds
        names = []
        for key in ("tools", "organize", "refs"):
            names += [t.name for t in asyncio.run(ds_mcp.build(key).list_tools())]
        for bad in ("owner_set_workspace", "preview_workspace"):
            self.assertFalse(any(bad in n for n in names), f"{bad} 被登记成了 MCP 工具:{names}")

    def test_p6_业主换了根_排队中的助手申请判过期(self):
        ds_tools.owner_set_workspace(self.ws, "01-项目", 1, ds_root=self.ds)
        pend = ds_tools.set_workspace(self.flat, ds_root=self.ds)
        self.assertTrue(pend.get("pending"), pend)
        ds_tools.owner_set_workspace(self.ws, ".", 2, ds_root=self.ds)     # 根没变:不算过期
        ds_tools.owner_set_workspace(os.path.join(self.ws, "2026"), ".", 1, ds_root=self.ds)
        r = ds_consent.resolve_pending(self.ds, pend["pending_id"], True, apply_fn=ds_tools.apply_pending)
        self.assertEqual(r.get("error"), "stale_pending", r)


@contextmanager
def _serve(ds_root):
    dist = tempfile.mkdtemp(prefix="wspick_dist_")
    with open(os.path.join(dist, "index.html"), "w") as fh:
        fh.write("<!doctype html>")
    httpd = ds_web.make_server(ds_root, dist, port=0)
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()
        shutil.rmtree(dist, ignore_errors=True)


def _post(port, path, body, ctype="application/json", headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    conn.request("POST", path, body=data, headers={"Content-Type": ctype, **(headers or {})})
    r = conn.getresponse()
    out = r.read()
    conn.close()
    return r.status, (json.loads(out.decode("utf-8")) if out else None)


class P4_针孔(unittest.TestCase):
    def setUp(self):
        self.t, self.ds, self.ws, self.flat = _mkws()

    def tearDown(self):
        shutil.rmtree(self.t, ignore_errors=True)

    def test_p4a_预览与确定走通(self):
        with _serve(self.ds) as port:
            st, r = _post(port, "/api/workspace/root/preview", {"root": self.ws})
            self.assertEqual(st, 200, r)
            auto = next(l for l in r["layouts"] if l["layout"] == "auto")
            st, r = _post(port, "/api/workspace/root",
                          {"root": self.ws, "projects_dir": auto["projects_dir"],
                           "projects_depth": auto["projects_depth"]})
            self.assertEqual((st, r.get("folder_count")), (200, 2), r)
        self.assertEqual(_cfg(self.ds)["projectsDir"], "01-项目")

    def test_p4b_posture_只收JSON_键白名单_跨站403(self):
        with _serve(self.ds) as port:
            before = _cfg_bytes(self.ds)
            ok_body = {"root": self.ws, "projects_dir": ".", "projects_depth": 1}
            self.assertEqual(_post(port, "/api/workspace/root", ok_body, ctype="text/plain")[0], 400)
            self.assertEqual(_post(port, "/api/workspace/root", {**ok_body, "extra": 1})[0], 400)
            self.assertEqual(_post(port, "/api/workspace/root", {**ok_body, "projects_depth": "1"})[0], 400)
            self.assertEqual(_post(port, "/api/workspace/root/preview", {"root": self.ws, "x": 1})[0], 400)
            st, _ = _post(port, "/api/workspace/root", ok_body,
                          headers={"Origin": "http://evil.example", "Sec-Fetch-Site": "cross-site"})
            self.assertEqual(st, 403, "别的网站不许替业主换工作区")
            self.assertEqual(_cfg_bytes(self.ds), before, "被拒的请求不许写任何东西")

    def test_p4c_错误码是给界面翻译的_不回栈(self):
        with _serve(self.ds) as port:
            st, r = _post(port, "/api/workspace/root/preview", {"root": os.path.join(self.t, "没有")})
            self.assertEqual((st, r.get("error")), (404, "root_not_dir"))
            st, r = _post(port, "/api/workspace/root", {"root": self.ws, "projects_dir": "../x", "projects_depth": 1})
            self.assertEqual((st, r.get("error")), (400, "layout_invalid"))
            st, r = _post(port, "/api/workspace/root/preview", {"root": self.ds})
            self.assertEqual((st, r.get("error")), (409, "location_overlap"))
            self.assertTrue(r.get("message", "").startswith("工作区路径"))


@unittest.skipIf(not hasattr(os, "symlink"), "平台不支持软链接")
class P7_总夹是软链接(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp(prefix="wspick_ln_")
        self.ds = os.path.join(self.t, "ds")
        os.makedirs(os.path.join(self.ds, "config"))
        os.makedirs(os.path.join(self.ds, "projects"))
        self.ws = os.path.join(self.t, "ws")
        os.makedirs(self.ws)

    def tearDown(self):
        shutil.rmtree(self.t, ignore_errors=True)

    def _link(self, target):
        for p in ("甲", "乙"):
            os.makedirs(os.path.join(target, p), exist_ok=True)
        try:
            os.symlink(target, os.path.join(self.ws, "01-项目"), target_is_directory=True)
        except OSError as e:          # Windows 没有开发者模式时建不了软链接
            self.skipTest(f"建不了软链接:{e}")

    def _preview_then_apply(self):
        pv = ds_tools.preview_workspace(self.ws, ds_root=self.ds)
        self.assertTrue(pv.get("ok"), pv)
        auto = next((l for l in pv["layouts"] if l["layout"] == "auto"), None)
        self.assertIsNotNone(auto, "根下有「01-项目」(哪怕是软链接)就该列出这种摆法")
        self.assertEqual(auto["projects_dir"], "01-项目", "总夹名要取根下那一项自己的名字,不是链接目标的")
        r = ds_tools.owner_set_workspace(self.ws, auto["projects_dir"], auto["projects_depth"], ds_root=self.ds)
        return auto, r

    def test_p7a_链接目标在工作区内_预览2个接入后也是2个(self):
        self._link(os.path.join(self.ws, "真实的项目夹"))
        auto, r = self._preview_then_apply()
        self.assertEqual(auto["count"], 2)
        self.assertEqual(r.get("folder_count"), auto["count"], f"预览说 {auto['count']} 个,接入后 {r}")
        self.assertEqual(_cfg(self.ds)["projectsDir"], "01-项目")

    def test_p7b_链接目标在工作区外_预览与接入结果一致(self):
        self._link(os.path.join(self.t, "工作区外面"))
        auto, r = self._preview_then_apply()
        self.assertEqual(r.get("folder_count"), auto["count"],
                         f"预览说 {auto['count']} 个,接入后 {r} —— 不许先说认得出、接上后变 0")


if __name__ == "__main__":
    unittest.main()
