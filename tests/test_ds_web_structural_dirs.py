#!/usr/bin/env python3
"""track opendesign-chat-image-p2 的 oracle(一)——
① 结构文件夹不再被当成"待建档项目";② 打开收件箱(open-folder 的 inbox 分支)。
主 agent 亲写,executor off-limits。

**用户原话(第一性,判据照它写)**:
- 「收件箱在我的项目列表也会出现让我建档,这也算 bug 吧」
- 「不要写死目录名,因为用户的目录名不一定跟我的一样」

所以排除规则的判据分三层,**第一层必须是"用户自己声明的名字"**:
1. `workspace.json.structuralDirs` 里声明了什么就排除什么 —— 名字随便叫,
   叫「新文件」也照排(s03)。这是根治"写死"的那一层。
2. 没声明时,回落到"规则表候选里**确实存在**的那几个"(s01)——让今天就能用,
   不必等用户先去配置。
3. **两层都不命中就不排除**(s04):用户把收件箱叫「新文件」又没声明,
   它就是会出现在待建档列表里 —— 这是诚实,不是 bug。**我们不猜。**

跑法: python3 -m pytest tests/test_ds_web_structural_dirs.py
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
import ds_web  # noqa: E402
import ds_workspace  # noqa: E402

PROJ_A = "20260612 周宁 龙腾世纪 12#1802"
PROJ_B = "20260619 福州 融侨外滩D区1#2604"


def _mkenv(dirs, cfg_extra=None):
    """建 DS_ROOT + 工作区(projectsDir=".":项目直接放在工作区根,
    = 用户真机的形态,也正是本 bug 的发生条件)。"""
    ds = tempfile.mkdtemp(prefix="struct-ds-")
    ws = tempfile.mkdtemp(prefix="struct-ws-")
    os.makedirs(os.path.join(ds, "config"), exist_ok=True)
    os.makedirs(os.path.join(ds, "projects"), exist_ok=True)
    for d in dirs:
        os.makedirs(os.path.join(ws, d), exist_ok=True)
    cfg = {"root": ws, "projects": {}, "projectsDir": "."}
    cfg.update(cfg_extra or {})
    with open(os.path.join(ds, "config", "workspace.json"), "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False)
    return ds, ws


def _mkdist():
    d = tempfile.mkdtemp(prefix="struct-dist-")
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<!doctype html><div>x</div>")
    return d


@contextmanager
def _serve(ds_root):
    srv = ds_web.make_server(ds_root, _mkdist(), port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield srv.server_address[1]
    finally:
        srv.shutdown()
        srv.server_close()


def _post(port, path, body, ctype="application/json"):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    headers = {"Content-Type": ctype} if ctype else {}
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    try:
        conn.request("POST", path, body=data, headers=headers)
        r = conn.getresponse()
        b = r.read()
        return r.status, (json.loads(b.decode("utf-8")) if b else None)
    except (BrokenPipeError, ConnectionResetError, http.client.RemoteDisconnected):
        return None, None
    finally:
        conn.close()


def _get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    conn.request("GET", path)
    r = conn.getresponse()
    b = r.read()
    conn.close()
    return r.status, (json.loads(b.decode("utf-8")) if b else None)


class StructuralDirsNotProjects(unittest.TestCase):
    def setUp(self):
        self.tmps = []

    def tearDown(self):
        for p in self.tmps:
            shutil.rmtree(p, ignore_errors=True)

    def _env(self, dirs, cfg_extra=None):
        ds, ws = _mkenv(dirs, cfg_extra)
        self.tmps += [ds, ws]
        return ds, ws

    def _folder_names(self, ds):
        cfg = ds_workspace.load_config(ds)
        return [n for n, _ in ds_workspace.project_folders(cfg)]

    def test_s01_default_named_structural_dirs_excluded(self):
        """规则表候选名(00-收件箱/02-归档项目/03-共享资源)存在 → 不算项目。
        用户实机就是这三个名字,这条一绿他的 bug 就没了。"""
        ds, _ = self._env(["00-收件箱", "02-归档项目", "03-共享资源", PROJ_A, PROJ_B])
        got = self._folder_names(ds)
        self.assertEqual(sorted(got), sorted([PROJ_A, PROJ_B]), got)

    def test_s02_still_visible_in_api_projects_as_nothing(self):
        """端到端:/api/projects 的待建档列表里不许出现结构夹。"""
        ds, _ = self._env(["00-收件箱", "03-共享资源", PROJ_A])
        with _serve(ds) as port:
            st, r = _get(port, "/api/projects")
        self.assertEqual(st, 200)
        keys = [p["key"] for p in r["projects"]]
        self.assertIn(PROJ_A, keys)
        for bad in ("00-收件箱", "03-共享资源"):
            self.assertNotIn(bad, keys, f"{bad} 不该出现在项目列表里")

    def test_s03_user_declared_names_win_whatever_they_are(self):
        """**根治写死那条**:用户把收件箱叫「新文件」、归档叫「老项目」,
        只要在 workspace.json.structuralDirs 里声明了,就照排 —— 名字随便他起。"""
        ds, _ = self._env(["新文件", "老项目", PROJ_A],
                          {"structuralDirs": ["新文件", "老项目"]})
        got = self._folder_names(ds)
        self.assertEqual(got, [PROJ_A], got)

    def test_s04_undeclared_custom_name_is_NOT_guessed(self):
        """两层都不命中 → 照常列出来(诚实,不猜)。
        这条同时防"排除逻辑越写越聪明"——猜错就等于用户的真项目消失在列表里。"""
        ds, _ = self._env(["新文件", PROJ_A])
        got = self._folder_names(ds)
        self.assertEqual(sorted(got), sorted(["新文件", PROJ_A]), got)

    def test_s05_declared_plus_default_are_unioned(self):
        """声明的 ∪ 规则表里存在的,两层并集(声明了新名字不代表放弃默认名)。"""
        ds, _ = self._env(["00-收件箱", "新文件", PROJ_A],
                          {"structuralDirs": ["新文件"]})
        got = self._folder_names(ds)
        self.assertEqual(got, [PROJ_A], got)

    def test_s06_bad_structuralDirs_type_degrades_not_crashes(self):
        """配置写坏(不是字符串列表)→ 忽略这一层,不炸;仍走规则表回落。"""
        for bad in ("00-收件箱", 123, [1, 2], [""], {"a": 1}):
            ds, _ = self._env(["00-收件箱", PROJ_A], {"structuralDirs": bad})
            got = self._folder_names(ds)
            self.assertEqual(got, [PROJ_A], f"structuralDirs={bad!r} → {got}")

    def test_s07_structural_names_with_path_parts_ignored(self):
        """声明里混进带路径成分的值 → 忽略那一条(只认单段名),不影响其余。"""
        ds, _ = self._env(["新文件", PROJ_A],
                          {"structuralDirs": ["../外面", "a/b", "新文件"]})
        got = self._folder_names(ds)
        self.assertEqual(got, [PROJ_A], got)

    def test_s08_projects_under_a_projects_dir_unaffected(self):
        """项目放在 01-项目 里的用户:结构夹是兄弟目录、本来就不在扫描范围,
        行为一字不变(别为了修 bug 把另一种布局改坏)。"""
        ds = tempfile.mkdtemp(prefix="struct-ds-")
        ws = tempfile.mkdtemp(prefix="struct-ws-")
        self.tmps += [ds, ws]
        os.makedirs(os.path.join(ds, "config"))
        os.makedirs(os.path.join(ds, "projects"))
        os.makedirs(os.path.join(ws, "00-收件箱"))
        os.makedirs(os.path.join(ws, "01-项目", PROJ_A))
        with open(os.path.join(ds, "config", "workspace.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"root": ws, "projects": {}}, fh, ensure_ascii=False)
        self.assertEqual(self._folder_names(ds), [PROJ_A])


class OpenInboxBranch(unittest.TestCase):
    """「打开收件箱」:open-folder 的 inbox 分支。
    **路径永远由服务端 `_find_inbox` 解析,调用方给不了路径** —— 这是这条新口
    唯一值得担心的事(否则就成了"网页能让 Windows 打开任意目录")。"""

    def setUp(self):
        self.opened = []
        self._real = ds_web.OPEN_LAUNCHER
        ds_web.OPEN_LAUNCHER = self.opened.append   # 不真开资源管理器
        self.tmps = []

    def tearDown(self):
        ds_web.OPEN_LAUNCHER = self._real
        for p in self.tmps:
            shutil.rmtree(p, ignore_errors=True)

    def _env(self, dirs):
        ds, ws = _mkenv(dirs)
        self.tmps += [ds, ws]
        return ds, ws

    def test_o01_opens_the_inbox_resolved_by_server(self):
        ds, ws = self._env(["00-收件箱"])
        with _serve(ds) as port:
            st, r = _post(port, "/api/open-folder", {"inbox": True})
        self.assertEqual(st, 200, r)
        self.assertEqual([os.path.realpath(p) for p in self.opened],
                         [os.path.realpath(os.path.join(ws, "00-收件箱"))])

    def test_o02_caller_cannot_name_the_path(self):
        """带路径类的键一律拒,且**零启动**(不许"顺手"开点什么)。"""
        ds, _ = self._env(["00-收件箱"])
        with _serve(ds) as port:
            for body in ({"inbox": "/etc"}, {"inbox": True, "sub": "x"},
                         {"inbox": True, "rel": "x"}, {"inbox": True, "path": "/etc"},
                         {"inbox": True, "key": "任意项目"}):
                st, _r = _post(port, "/api/open-folder", body)
                self.assertIn(st, (400, 404), f"应拒:{body}")
        self.assertEqual(self.opened, [], "被拒时一次都不许启动")

    def test_o03_no_inbox_dir_404_and_no_launch(self):
        ds, _ = self._env([])
        with _serve(ds) as port:
            st, _r = _post(port, "/api/open-folder", {"inbox": True})
        self.assertIn(st, (404, 409))
        self.assertEqual(self.opened, [])

    def test_o04_non_json_ct_rejected(self):
        ds, _ = self._env(["00-收件箱"])
        with _serve(ds) as port:
            st, _r = _post(port, "/api/open-folder", {"inbox": True}, ctype="text/plain")
        self.assertEqual(st, 400)
        self.assertEqual(self.opened, [])

    def test_o05_old_key_branch_untouched(self):
        """回归:老的 {key} 分支一字不变(本单只加分支,不改既有行为)。"""
        ds, ws = self._env(["00-收件箱", PROJ_A])
        cfgp = os.path.join(ds, "config", "workspace.json")
        cfg = json.load(open(cfgp, encoding="utf-8"))
        cfg["projects"] = {PROJ_A: PROJ_A}
        json.dump(cfg, open(cfgp, "w", encoding="utf-8"), ensure_ascii=False)
        with _serve(ds) as port:
            st, r = _post(port, "/api/open-folder", {"key": PROJ_A})
        self.assertEqual(st, 200, r)
        self.assertEqual([os.path.realpath(p) for p in self.opened],
                         [os.path.realpath(os.path.join(ws, PROJ_A))])


if __name__ == "__main__":
    unittest.main()
