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

    def test_s05_bad_declaration_still_falls_back_to_defaults(self):
        """声明写坏(整键类型不对)→ 该层作废,但回落层照常兜底。
        (与 s10 对照:**合法声明**会关掉回落层,坏声明不算声明。)"""
        ds, _ = self._env(["00-收件箱", "新文件", PROJ_A],
                          {"structuralDirs": "不是列表"})
        got = self._folder_names(ds)
        self.assertEqual(sorted(got), sorted(["新文件", PROJ_A]), got)

    def test_s06_non_list_value_is_not_a_declaration_falls_back(self):
        """**不是列表**(字符串/数字/对象)= 压根没在声明这件事 → 走回落层,不炸。"""
        for bad in ("00-收件箱", 123, {"a": 1}, None, True):
            ds, _ = self._env(["00-收件箱", PROJ_A], {"structuralDirs": bad})
            got = self._folder_names(ds)
            self.assertEqual(got, [PROJ_A], f"structuralDirs={bad!r} → {got}")

    def test_s06b_list_of_garbage_counts_as_declared_empty(self):
        """**是列表但内容全非法**([1,2] / [""])= 他确实在声明、只是写错了 →
        按"声明了空"算,于是一个都不排除。
        ⚠️ 这条判据是我加了 s09(声明即关闭猜测)之后**回头改的** —— 原本它期望
        "坏值 → 回落"。改的依据是本单反复讲的那条优先级:**宁可多列一个(用户看得见、
        能自己收拾),不可猜错让人家的真项目从列表里消失(用户只会觉得东西丢了)**。
        记在这里是因为"改判据去迁就实现"正是假绿的经典路径,必须留痕给评审看。"""
        for bad in ([1, 2], [""], [None]):
            ds, _ = self._env(["00-收件箱", PROJ_A], {"structuralDirs": bad})
            got = self._folder_names(ds)
            self.assertEqual(sorted(got), sorted(["00-收件箱", PROJ_A]),
                             f"structuralDirs={bad!r} → {got}")

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


    def test_s09_declaring_the_key_at_all_turns_off_the_guessing_layer(self):
        """**给用户一个关掉猜测的开关**:只要 `structuralDirs` 这个键出现了(哪怕是
        空列表),就完全按声明算、不再回落到规则表候选。
        为什么要这条:回落层是按名字猜的,万一某人真有个项目夹叫「归档项目」,
        它会被静默吃掉 —— 而用户不会来报 bug,只会觉得"我那个项目不见了"。
        有了这条,他写一行 `"structuralDirs": []` 就能把猜测整层关掉。"""
        ds, _ = self._env(["00-收件箱", "归档项目", PROJ_A], {"structuralDirs": []})
        got = self._folder_names(ds)
        self.assertEqual(sorted(got), sorted(["00-收件箱", "归档项目", PROJ_A]), got)

    def test_s10_explicit_declaration_does_not_silently_add_defaults(self):
        """声明了「新文件」→ 只排它;同在根下的 00-收件箱 **不再**被自动排除
        (与 s05 的"并集"相反 —— s05 的前提是没声明键,这里是显式声明)。"""
        ds, _ = self._env(["00-收件箱", "新文件", PROJ_A],
                          {"structuralDirs": ["新文件"]})
        got = self._folder_names(ds)
        self.assertEqual(sorted(got), sorted(["00-收件箱", PROJ_A]), got)

    def test_s11_user_taxonomy_override_is_honoured_by_the_fallback(self):
        """**subglm 的 BLOCK 顺出来的真 bug**:回落层要按 **这台机器的 DS_ROOT** 读规则表。
        我原来用 `__file__` 反推仓根去找 taxonomy —— 于是用户在
        `<DS_ROOT>/config/taxonomy.json` 里把收件箱改名成「新文件」时,排除逻辑
        **读不到他的覆盖**,还在按仓库自带的默认名排。那正是"写死"换了个马甲。"""
        ds, ws = self._env(["新文件", PROJ_A])
        user_tax = os.path.join(ds, "config", "taxonomy.json")
        with open(user_tax, "w", encoding="utf-8") as fh:
            json.dump({"inboxDirs": ["新文件"]}, fh, ensure_ascii=False)
        got = self._folder_names(ds)
        self.assertEqual(got, [PROJ_A], f"用户覆盖后的名字要被认出来:{got}")

    def test_s12_excluded_by_guessing_is_reported_not_silent(self):
        """**两条腿共同指出的**:被"猜"排掉的目录必须让人看得见 ——
        否则用户只会觉得"我那个文件夹怎么不见了",而他不是程序员、不会去翻配置。
        显式声明排掉的不报(那是他自己写的,他知道)。"""
        ds, _ = self._env(["00-收件箱", "03-共享资源", PROJ_A])
        with _serve(ds) as port:
            st, r = _get(port, "/api/projects")
        self.assertEqual(st, 200)
        self.assertEqual(sorted(r.get("excludedStructural") or []),
                         ["00-收件箱", "03-共享资源"], r.get("excludedStructural"))

    def test_s13_explicitly_declared_exclusions_are_not_nagged_about(self):
        ds, _ = self._env(["新文件", PROJ_A], {"structuralDirs": ["新文件"]})
        with _serve(ds) as port:
            st, r = _get(port, "/api/projects")
        self.assertEqual(st, 200)
        self.assertEqual(r.get("excludedStructural") or [], [],
                         "自己声明的不用再提醒他")

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
