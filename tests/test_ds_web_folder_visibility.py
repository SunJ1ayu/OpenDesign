#!/usr/bin/env python3
"""track opendesign-workspace-health 的 oracle(二)—— 工作区体检卡的读口与写口。
主 agent 亲写,executor off-limits。

  GET  /api/workspace/health           卡片要显示的整份现状(含 reviewId 快照)
  POST /api/workspace/folder-visibility  一次存**整份**「不显示」清单

本单的第一性诉求(proposal「真问题」):**别让我的猜测悄悄吞掉他的项目,
而他连纠正的入口都没有。** 猜错的两种后果严重程度差很远——没认出收件箱只是碍眼,
把真项目猜成结构目录 = 那个项目从列表里消失。判据一律按这个不对称来收紧。

## 形状为什么长这样(design.md A1~A7 的判据化)

- **A2 一次存整份清单,不是一次改一个名字**。`structural_dirs()` 的语义是
  「声明过就不再回落」——增量式写口在声明第一个名字的瞬间会让第②层整层关闭,
  其他被猜掉的目录**突然全部冒出来**。整份存从结构上绕过去(v09/v10)。
- **A3 名字只能来自服务端本次下发的集合**(v06)。网页传不了工作区路径/配置路径,
  路径永远服务端解析(v03)。
- **A3 reviewId 绑「配置内容 + 目录快照」**(v07a/v07b/v07c)。用户开着卡片时在
  资源管理器里新建了文件夹,按旧快照保存会**静默把新文件夹藏掉**。
- **A4 曾声明、当前不存在的目录必须保留**(v10/v11)。外接硬盘没插、临时改名时,
  一次保存不许静默抹掉用户过去的声明。
- **A5 项目在子目录下时不适用**(v14)。`excluded_structural()` 在
  `realpath(root) != projects_root` 时直接返回 `[]` —— 这批用户根本不存在误伤问题。
- **A6 猜出来的结果不预勾在「不显示」一侧**(v13,**最要紧的一条**)。
  依据是本仓自己写死的原则:「宁可多列一个,不可猜错让人家的真项目从列表里消失」。
  预勾之后用户随手一点保存,**猜测就固化成了正式声明** —— 恰好把本单要防的失败焊死。

## 「当前状态」与「默认不预勾」的张力,以及仲裁结果

A1 要求每行显示**当前状态 + 依据**,A6 要求**猜的不预勾**。这两条会打架:
一个被猜掉的目录,它「当前状态」就是没被列进项目列表,可开关初值又不许是「不显示」。

**仲裁(主 agent 定,design.md 补记)**:读口把两件事**分开成两个字段** ——
  - `currentlyHidden`:**事实**,它现在到底有没有被排除(含被猜掉的);
  - `preselect`:**开关初值**,`true` 当且仅当 `reason == "declared"`。
前端据此显示成「按常见名字猜的,现在没列进项目列表」而开关停在「显示」侧。
用户什么都不动直接保存 = 把所有猜测撤销、全部显示,符合 A6 的不对称取舍(v13/v13b)。

## 这个 oracle 能被什么骗过?

design.md 已经点名过一次,这里再钉一遍:**接口层断言全绿,但用户眼里
「我的项目还是不见了」**。因为本文件测的是「写口拒绝了非法输入」,测不到
「卡片显示的那份清单本身就是错的」—— 服务端下发集合若漏算了某个一级文件夹,
前端忠实显示、写口忠实接受、全绿,而那个文件夹从此消失。

v05 是能在接口层做的最接近的一层(下发集合必须**恰好**等于根下可见的一级目录,
含中文名/空格/标点,且不含点号目录、符号链接、普通文件)。**但它替代不了真机**:
拿一个真实工作区跑一遍、肉眼确认没声明过的真项目出现在「显示」侧。
史料:07-24 `columnCount==="3"` 全绿而正文被压成竖排。

跑法: python3 -m pytest tests/test_ds_web_folder_visibility.py
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

HEALTH = "/api/workspace/health"
SAVE = "/api/workspace/folder-visibility"
DEFAULT_INBOX = "00-收件箱"      # config/taxonomy.default.json 的 inboxDirs[0]


# ── 夹具 ──────────────────────────────────────────────────────────────────
def _mkdist():
    d = tempfile.mkdtemp(prefix="fvis-dist-")
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
    """→ (status, json)。连接被提前掐断 → (None, None),照算"被拒"。"""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    headers = {"Content-Type": ctype} if ctype else {}
    if body is None:
        data = b""
    elif isinstance(body, (bytes, bytearray)):
        data = body
    else:
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


class FolderVisibilityBase(unittest.TestCase):
    def setUp(self):
        self.tmps = []

    def tearDown(self):
        for p in self.tmps:
            shutil.rmtree(p, ignore_errors=True)

    def _env(self, folders=(), cfg=True, **cfg_extra):
        """建 DS_ROOT + 工作区;folders=工作区根下要建的一级目录名。
        cfg=False → 不写 workspace.json(未接入)。"""
        ds = tempfile.mkdtemp(prefix="fvis-ds-")
        ws = tempfile.mkdtemp(prefix="fvis-ws-")
        self.tmps += [ds, ws]
        os.makedirs(os.path.join(ds, "config"), exist_ok=True)
        os.makedirs(os.path.join(ds, "projects"), exist_ok=True)
        for name in folders:
            os.makedirs(os.path.join(ws, name), exist_ok=True)
        if cfg:
            # projectsDir="." → 项目夹直接在根一级(体检卡唯一适用的布局,见 A5)
            obj = {"root": ws, "projects": {}, "projectsDir": "."}
            obj.update(cfg_extra)
            self._write_cfg(ds, obj)
        return ds, ws

    @staticmethod
    def _cfg_path(ds):
        return os.path.join(ds, "config", "workspace.json")

    def _write_cfg(self, ds, obj):
        with open(self._cfg_path(ds), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=2)

    def _read_cfg(self, ds):
        with open(self._cfg_path(ds), encoding="utf-8") as fh:
            return json.load(fh)

    def _raw_bytes(self, ds):
        with open(self._cfg_path(ds), "rb") as fh:
            return fh.read()

    def _health(self, port):
        st, r = _get(port, HEALTH)
        self.assertEqual(st, 200, r)
        return r

    @staticmethod
    def _row(health, name):
        for row in health.get("folders") or []:
            if row.get("name") == name:
                return row
        return None


class RequestShape(FolderVisibilityBase):
    """写口的形状闸 —— posture 逐条照抄既有写针孔(⑨/⑭):
    CT=application/json(CSRF 纵深)→ 0 < Content-Length ≤ 上限 → JSON dict →
    键白名单 {review_id, hidden} → 类型/值域。每条拒绝路径都断**零副作用**。"""

    def test_v01_non_json_ct_rejected(self):
        ds, ws = self._env([DEFAULT_INBOX, "真项目"])
        before = self._raw_bytes(ds)
        with _serve(ds) as port:
            rid = self._health(port)["reviewId"]
            st, _ = _post(port, SAVE, {"review_id": rid, "hidden": []},
                          ctype="text/plain")
        self.assertIn(st, (400, None))
        self.assertEqual(self._raw_bytes(ds), before, "被拒时配置一个字节都不许变")

    def test_v02_empty_or_non_dict_body_rejected(self):
        ds, _ = self._env([DEFAULT_INBOX])
        before = self._raw_bytes(ds)
        with _serve(ds) as port:
            for body in (None, [], "x", 5, {}):
                st, _ = _post(port, SAVE, body)
                self.assertIn(st, (400, None), f"应拒:{body!r}")
        self.assertEqual(self._raw_bytes(ds), before)

    def test_v03_extra_keys_rejected_no_path_smuggling(self):
        """**网页传不了路径**:工作区路径/配置路径/ds_root 一律不是本口的参数,
        路径永远服务端解析。多一个键就拒(不许夹带走私)。"""
        ds, ws = self._env([DEFAULT_INBOX])
        before = self._raw_bytes(ds)
        with _serve(ds) as port:
            rid = self._health(port)["reviewId"]
            for extra in ({"root": "/etc"}, {"ds_root": "/etc"},
                          {"configPath": "/etc/passwd"}, {"path": ".."},
                          {"projectsDir": ".."}, {"x": 1}):
                body = {"review_id": rid, "hidden": []}
                body.update(extra)
                st, _ = _post(port, SAVE, body)
                self.assertIn(st, (400, None), f"应拒夹带:{extra}")
        self.assertEqual(self._raw_bytes(ds), before)

    def test_v04_hidden_must_be_a_list_of_clean_single_segment_names(self):
        """`hidden` 逐项过单段名闸(ds_workspace._SEG_RE:禁 / \\ % 与控制符,
        非 . / ..),且不许重复、不许空串。"""
        ds, ws = self._env([DEFAULT_INBOX, "真项目"])
        before = self._raw_bytes(ds)
        bad_lists = [
            "不是列表", 5, None, {},
            [1], [None], [["嵌套"]],
            [""],                                   # 空串
            [DEFAULT_INBOX, DEFAULT_INBOX],         # 重复
            ["深/收件箱"], ["深\\收件箱"],           # 多段
            [".."], ["."],                          # 父目录引用
            ["百分%号"], ["带\n换行"], ["带\x00空字节"],
            ["../../etc"],
        ]
        with _serve(ds) as port:
            rid = self._health(port)["reviewId"]
            for hidden in bad_lists:
                st, _ = _post(port, SAVE, {"review_id": rid, "hidden": hidden})
                self.assertIn(st, (400, None), f"应拒:{hidden!r}")
        self.assertEqual(self._raw_bytes(ds), before)

    def test_v04b_review_id_must_be_a_non_empty_string(self):
        ds, _ = self._env([DEFAULT_INBOX])
        before = self._raw_bytes(ds)
        with _serve(ds) as port:
            for rid in (None, "", 5, [], {}):
                st, _ = _post(port, SAVE, {"review_id": rid, "hidden": []})
                self.assertIn(st, (400, None), f"应拒 review_id={rid!r}")
            st, _ = _post(port, SAVE, {"hidden": []})       # 缺键
            self.assertIn(st, (400, None), "缺 review_id 应拒")
        self.assertEqual(self._raw_bytes(ds), before)

    def test_v04c_oversized_body_rejected(self):
        """请求体上限(既有写针孔同款):超限直接拒,不许先解析再说。"""
        ds, _ = self._env([DEFAULT_INBOX])
        before = self._raw_bytes(ds)
        with _serve(ds) as port:
            huge = {"review_id": "x", "hidden": [f"名{i}" for i in range(5000)]}
            st, _ = _post(port, SAVE, huge)
        self.assertIn(st, (400, 413, None))
        self.assertEqual(self._raw_bytes(ds), before)


    def test_v20_a_real_sized_whole_list_still_saves(self):
        """**整份清单**的请求体不能被「打开文件夹」那口的 4096 上限卡死。

        写口的语义是 A2「一次存整份」——用户过去声明过的名字**每次保存都要原样重报**。
        所以请求体大小与「已声明目录数」线性相关,而 `OPEN_BODY_MAX` 是给 open-folder
        (两个短字段)定的。真机是设计师的工作区,中文长目录名 ~34 字节:
        120 个就撑爆 4096,用户从此存不进去,拿到的还是一句无差别的 400。
        """
        names = [f"{i:03d}-归档 云栖佳苑项目资料" for i in range(120)]
        ds, _ = self._env(names)
        with _serve(ds) as port:
            h = self._health(port)
            st, r = _post(port, SAVE, {"review_id": h["reviewId"], "hidden": names})
        self.assertEqual(st, 200, r)
        self.assertEqual(sorted(self._read_cfg(ds)["structuralDirs"]), sorted(names))

    def test_v21_absurd_name_count_is_refused_by_an_explicit_cap(self):
        """design 明写「`hidden` 有**数量**与请求体上限」两条闸,不能只有后者。

        数量闸必须是**显式**的:靠请求体字节数间接封顶,等于把「能存几个目录」
        绑死在「名字有多长」上——中文名和 ASCII 名的上限会差三倍,而且 v20 一放宽
        请求体,这条就彻底没有了。
        """
        ds, _ = self._env(["00-收件箱"])
        before = self._raw_bytes(ds)
        with _serve(ds) as port:
            h = self._health(port)
            huge = {"review_id": h["reviewId"], "hidden": [f"n{i}" for i in range(5000)]}
            st, _ = _post(port, SAVE, huge)
        self.assertIn(st, (400, 413, None))
        self.assertEqual(self._raw_bytes(ds), before)


class ServerIssuedSet(FolderVisibilityBase):
    """读口:卡片显示什么、下发集合是什么。"""

    def test_v05_issued_set_is_exactly_the_visible_top_level_dirs(self):
        """**下发集合算错 = 那个文件夹从此消失**(design 点名的假绿源头)。

        判据:`folders` 恰好等于根下**可见的一级目录** —— 含中文名/空格/标点,
        且**不含**点号开头目录(.git 之类)、符号链接目录(不跟随,worktree 事故同源)、
        普通文件。多一个少一个都是红。
        """
        real = [DEFAULT_INBOX, "01 平面方案", "周宁 云栖佳苑 12#1802",
                "江畔雅苑(D区)", "共享素材"]
        ds, ws = self._env(real)
        os.makedirs(os.path.join(ws, ".git"))               # 点号目录:不列
        outside = tempfile.mkdtemp(prefix="fvis-out-")
        self.tmps.append(outside)
        os.symlink(outside, os.path.join(ws, "外链夹"))      # 符号链接:不列
        with open(os.path.join(ws, "散文件.dxf"), "wb") as fh:
            fh.write(b"x")                                   # 文件:不列
        with _serve(ds) as port:
            h = self._health(port)
        self.assertEqual(sorted(r["name"] for r in h["folders"]), sorted(real),
                         "下发集合必须恰好等于根下可见的一级目录")

    def test_v05b_health_reports_where_things_are(self):
        """卡片第一屏要回答「工作区在哪、项目从哪读、认出几个」。
        网页可以显示绝对路径(先例:test_ds_web_inbox_create c13 —— 网页要显示
        ≠ 模型要知道;本口不是 MCP 工具)。"""
        ds, ws = self._env([DEFAULT_INBOX, "真项目甲", "真项目乙"])
        with _serve(ds) as port:
            h = self._health(port)
        self.assertTrue(h.get("configured"))
        self.assertTrue(h.get("applicable"))
        self.assertEqual(os.path.realpath(h.get("root", "")), os.path.realpath(ws))
        self.assertEqual(os.path.realpath(h.get("projectsRoot", "")),
                         os.path.realpath(ws))
        # 收件箱被规则表猜掉 → 认出的项目是 2 个,与 /api/projects 同源
        self.assertEqual(h.get("projectCount"), 2)

    def test_v06_names_outside_the_issued_set_are_refused(self):
        """**A3 核心闸**:名字只能来自服务端本次下发的集合。
        凭空捏一个(哪怕是合法单段名)→ 拒,配置不变。"""
        ds, ws = self._env([DEFAULT_INBOX, "真项目"])
        before = self._raw_bytes(ds)
        with _serve(ds) as port:
            rid = self._health(port)["reviewId"]
            for hidden in ([("不存在的夹")], [DEFAULT_INBOX, "查无此夹"],
                           ["etc"], ["Users"]):
                st, r = _post(port, SAVE, {"review_id": rid, "hidden": hidden})
                self.assertIn(st, (400, 409), f"集合外的名字应拒:{hidden}")
        self.assertEqual(self._raw_bytes(ds), before)

    def test_v13_guessed_dirs_are_never_preselected_as_hidden(self):
        """**A6,本单最要紧的一条**。规则表猜中的目录:
          - `currentlyHidden` 为 **true**(事实:它现在确实没被列进项目列表)
          - `preselect` 为 **false**(开关初值停在「显示」侧)
          - `reason` = "guessed"(依据要写出来,用户得能分辨「我定的」和「它猜的」)
        预勾之后用户随手一点保存,猜测就固化成正式声明 —— 恰好把本单要防的失败焊死。
        """
        ds, ws = self._env([DEFAULT_INBOX, "真项目"])
        with _serve(ds) as port:
            h = self._health(port)
        self.assertFalse(h.get("declared"), "本例没声明过")
        inbox = self._row(h, DEFAULT_INBOX)
        self.assertIsNotNone(inbox)
        self.assertEqual(inbox["reason"], "guessed")
        self.assertTrue(inbox["currentlyHidden"], "事实层:它现在确实被猜掉了")
        self.assertFalse(inbox["preselect"],
                         "A6:猜出来的绝不许预勾在「不显示」一侧")
        proj = self._row(h, "真项目")
        self.assertEqual(proj["reason"], "default")   # 「没人说过,默认当项目」
        self.assertFalse(proj["currentlyHidden"])
        self.assertFalse(proj["preselect"])

    def test_v13b_declared_dirs_are_preselected_and_labelled_as_yours(self):
        """反面:用户**自己声明过**的,预勾 + 依据写「你声明过」。
        (别把 A6 修成"一律不预勾" —— 那样用户每次打开卡片都得重勾一遍。)"""
        ds, ws = self._env([DEFAULT_INBOX, "真项目", "共享素材"],
                           structuralDirs=[DEFAULT_INBOX, "共享素材"])
        with _serve(ds) as port:
            h = self._health(port)
        self.assertTrue(h.get("declared"))
        for name in (DEFAULT_INBOX, "共享素材"):
            row = self._row(h, name)
            self.assertEqual(row["reason"], "declared", name)
            self.assertTrue(row["currentlyHidden"], name)
            self.assertTrue(row["preselect"], f"{name}:声明过的必须预勾")
        self.assertFalse(self._row(h, "真项目")["preselect"])


class SaveSemantics(FolderVisibilityBase):
    """写口的语义:整份存、只动一个键、存量保留、立刻生效。"""

    def test_v09_saves_the_whole_list_verbatim(self):
        """**A2 整份存**:落盘的 `structuralDirs` 恰好等于提交的 `hidden`。"""
        ds, ws = self._env([DEFAULT_INBOX, "真项目", "共享素材"])
        with _serve(ds) as port:
            rid = self._health(port)["reviewId"]
            st, r = _post(port, SAVE,
                          {"review_id": rid, "hidden": [DEFAULT_INBOX, "共享素材"]})
        self.assertEqual(st, 200, r)
        self.assertEqual(sorted(self._read_cfg(ds)["structuralDirs"]),
                         sorted([DEFAULT_INBOX, "共享素材"]))

    def test_v09b_empty_list_is_a_legal_declaration_not_a_noop(self):
        """`hidden: []` = **显式声明「一个都不排除」**,把「猜」整层关掉
        (ds_workspace s09 的既定语义)。落盘必须是 `"structuralDirs": []`,
        **不是**删掉这个键 —— 删掉等于回到「没声明」,猜测层会重新接管。
        """
        ds, ws = self._env([DEFAULT_INBOX, "真项目"])
        with _serve(ds) as port:
            rid = self._health(port)["reviewId"]
            st, r = _post(port, SAVE, {"review_id": rid, "hidden": []})
            self.assertEqual(st, 200, r)
            st2, projects = _get(port, "/api/projects")
        raw = self._read_cfg(ds)
        self.assertIn("structuralDirs", raw, "空列表是声明,不许把键删掉")
        self.assertEqual(raw["structuralDirs"], [])
        self.assertEqual(projects.get("excludedStructural"), [],
                         "声明过之后不许再有「被猜掉」的条目")
        keys = {p["key"] for p in projects["projects"]}
        self.assertIn(DEFAULT_INBOX, keys, "猜测层关掉后收件箱应当出现在列表里")

    def test_v10_declared_but_missing_names_survive_a_save(self):
        """**A4**:曾声明、当前不存在的目录(外接硬盘没插/临时改名)
        必须在下发集合里、GET 标 `missing` 且 `preselect`,保存后**仍在**配置里。
        否则一次保存会静默抹掉用户过去的声明。"""
        ds, ws = self._env([DEFAULT_INBOX, "真项目"],
                           structuralDirs=["旧移动盘", DEFAULT_INBOX])
        with _serve(ds) as port:
            h = self._health(port)
            gone = self._row(h, "旧移动盘")
            self.assertIsNotNone(gone, "曾声明的名字必须仍然出现在卡片上")
            self.assertTrue(gone["missing"], "标成「已记住,目前没找到」")
            self.assertTrue(gone["preselect"], "默认保留 → 开关必须是勾上的")
            self.assertEqual(gone["reason"], "declared")
            # 前端照 preselect 提交
            keep = [r["name"] for r in h["folders"] if r["preselect"]]
            st, r = _post(port, SAVE, {"review_id": h["reviewId"], "hidden": keep})
        self.assertEqual(st, 200, r)
        self.assertIn("旧移动盘", self._read_cfg(ds)["structuralDirs"],
                      "不许静默抹掉用户过去的声明")

    def test_v11_user_can_still_remove_a_missing_declaration(self):
        """A4 是「默认保留」,不是「永远删不掉」:用户主动取消勾选就该删得掉。
        (别把 v10 修成"missing 的一律强行塞回去"。)"""
        ds, ws = self._env([DEFAULT_INBOX, "真项目"],
                           structuralDirs=["旧移动盘", DEFAULT_INBOX])
        with _serve(ds) as port:
            rid = self._health(port)["reviewId"]
            st, r = _post(port, SAVE, {"review_id": rid, "hidden": [DEFAULT_INBOX]})
        self.assertEqual(st, 200, r)
        self.assertEqual(self._read_cfg(ds)["structuralDirs"], [DEFAULT_INBOX])

    def test_v12_only_structural_dirs_key_is_touched(self):
        """只动 `structuralDirs`,其余键**逐字节**原样保留
        (root / projects / projectsDir / projectsDepth / galleryDepth,
        以及本工具不认识的用户手写键)。"""
        ds, ws = self._env([DEFAULT_INBOX, "分组甲"],
                           projects={"某项目": "分组甲"}, projectsDepth=2,
                           galleryDepth=4)
        # 用户手写的、本工具完全不认识的键:也不许弄丢
        raw = self._read_cfg(ds)
        raw["我自己加的备注"] = "别删我"
        self._write_cfg(ds, raw)
        before = self._read_cfg(ds)
        with _serve(ds) as port:
            rid = self._health(port)["reviewId"]
            st, r = _post(port, SAVE, {"review_id": rid, "hidden": [DEFAULT_INBOX]})
        self.assertEqual(st, 200, r)
        after = self._read_cfg(ds)
        for k, v in before.items():
            if k == "structuralDirs":
                continue
            self.assertEqual(after.get(k), v, f"键 {k} 不许被动")
        self.assertEqual(after["structuralDirs"], [DEFAULT_INBOX])

    def test_v15_save_takes_effect_immediately_and_keeps_real_projects(self):
        """**用户眼里的最终判据**:保存后
          ① 勾了「不显示」的名字不再出现在项目列表;
          ② **没勾的真项目一个都不许少**(本单要防的那个事故);
          ③ 不必重启(每请求现读)。
        """
        ds, ws = self._env([DEFAULT_INBOX, "真项目甲", "真项目乙", "共享素材"])
        with _serve(ds) as port:
            rid = self._health(port)["reviewId"]
            st, r = _post(port, SAVE,
                          {"review_id": rid, "hidden": [DEFAULT_INBOX, "共享素材"]})
            self.assertEqual(st, 200, r)
            st2, projects = _get(port, "/api/projects")
        self.assertEqual(st2, 200)
        keys = {p["key"] for p in projects["projects"]}
        self.assertNotIn(DEFAULT_INBOX, keys)
        self.assertNotIn("共享素材", keys)
        self.assertIn("真项目甲", keys, "没勾的真项目不许消失")
        self.assertIn("真项目乙", keys, "没勾的真项目不许消失")

    def test_v15b_saving_untouched_card_loses_no_project(self):
        """**A6 的端到端后果**:用户打开卡片什么都不动就按保存
        (= 只提交 preselect 为真的那些,本例为空)。
        结果是收件箱混进列表(碍眼),但**真项目一个都没少**(不是事故)。
        这个不对称就是 A6 推翻 GPT 预勾建议的全部理由。"""
        ds, ws = self._env([DEFAULT_INBOX, "真项目甲", "真项目乙"])
        with _serve(ds) as port:
            h = self._health(port)
            keep = [r["name"] for r in h["folders"] if r["preselect"]]
            self.assertEqual(keep, [], "没声明过 → 一个都不该预勾")
            st, r = _post(port, SAVE, {"review_id": h["reviewId"], "hidden": keep})
            self.assertEqual(st, 200, r)
            st2, projects = _get(port, "/api/projects")
        keys = {p["key"] for p in projects["projects"]}
        self.assertIn("真项目甲", keys)
        self.assertIn("真项目乙", keys)

    def test_v18_write_port_never_creates_or_deletes_anything(self):
        """**Non-goal 焊死**:本口不建目录、不改名、不搬文件。
        整轮跑完,工作区根下的条目集合必须一模一样。"""
        ds, ws = self._env([DEFAULT_INBOX, "真项目"])
        before = set(os.listdir(ws))
        with _serve(ds) as port:
            rid = self._health(port)["reviewId"]
            _post(port, SAVE, {"review_id": rid, "hidden": [DEFAULT_INBOX]})
            rid2 = self._health(port)["reviewId"]
            _post(port, SAVE, {"review_id": rid2, "hidden": []})
        self.assertEqual(set(os.listdir(ws)), before,
                         "写口不许在用户的工作区里造/删任何东西")


class SnapshotConflict(FolderVisibilityBase):
    """A3:reviewId 绑「配置内容 + 目录快照」,期间有变化 → 409。"""

    def test_v07a_new_folder_appearing_invalidates_the_review(self):
        """**用户开着卡片时在资源管理器里新建了文件夹** —— 按旧快照保存会把它
        静默藏掉(它不在旧集合里,前端也没显示过它)。必须 409,要求刷新后重选。"""
        ds, ws = self._env([DEFAULT_INBOX, "真项目"])
        with _serve(ds) as port:
            rid = self._health(port)["reviewId"]
            os.makedirs(os.path.join(ws, "刚拷进来的新项目"))
            before = self._raw_bytes(ds)
            st, r = _post(port, SAVE, {"review_id": rid, "hidden": [DEFAULT_INBOX]})
        self.assertEqual(st, 409, r)
        self.assertEqual(r.get("error"), "stale_review")
        self.assertEqual(self._raw_bytes(ds), before, "409 时配置不许被动")

    def test_v07b_config_changing_invalidates_the_review(self):
        """期间配置被别处改了(助手 bind_project / 用户手改)→ 409,不许按旧快照盖。"""
        ds, ws = self._env([DEFAULT_INBOX, "真项目"])
        with _serve(ds) as port:
            rid = self._health(port)["reviewId"]
            raw = self._read_cfg(ds)
            raw["projects"] = {"某项目": "真项目"}
            self._write_cfg(ds, raw)
            st, r = _post(port, SAVE, {"review_id": rid, "hidden": [DEFAULT_INBOX]})
        self.assertEqual(st, 409, r)
        self.assertEqual(r.get("error"), "stale_review")
        self.assertEqual(self._read_cfg(ds)["projects"], {"某项目": "真项目"},
                         "别处的改动不许被旧快照盖掉")

    def test_v07c_garbage_review_id_is_refused(self):
        ds, ws = self._env([DEFAULT_INBOX, "真项目"])
        before = self._raw_bytes(ds)
        with _serve(ds) as port:
            st, r = _post(port, SAVE,
                          {"review_id": "凭空捏的", "hidden": [DEFAULT_INBOX]})
        self.assertEqual(st, 409, r)
        self.assertEqual(self._raw_bytes(ds), before)

    def test_v07d_review_id_is_single_use(self):
        """保存成功之后配置就变了 → 同一个 reviewId 不能再用第二次。
        (卡片保存后必须刷新;否则第二次保存是按一份已经过期的清单写。)"""
        ds, ws = self._env([DEFAULT_INBOX, "真项目", "共享素材"])
        with _serve(ds) as port:
            rid = self._health(port)["reviewId"]
            st, r = _post(port, SAVE, {"review_id": rid, "hidden": [DEFAULT_INBOX]})
            self.assertEqual(st, 200, r)
            st2, r2 = _post(port, SAVE, {"review_id": rid, "hidden": ["共享素材"]})
        self.assertEqual(st2, 409, r2)
        self.assertEqual(self._read_cfg(ds)["structuralDirs"], [DEFAULT_INBOX],
                         "第二次(过期)保存不许生效")


class DegradedStates(FolderVisibilityBase):
    """降级:未接入、不适用、坏配置。一律不崩、不自动修、不覆盖用户手写内容。"""

    def test_v16_workspace_not_configured(self):
        ds, _ = self._env(cfg=False)
        with _serve(ds) as port:
            st, r = _get(port, HEALTH)
            self.assertIn(st, (200, 409))
            if st == 200:
                self.assertFalse(r.get("configured"))
            st2, r2 = _post(port, SAVE, {"review_id": "x", "hidden": []})
        self.assertEqual(st2, 409, r2)
        self.assertEqual(r2.get("error"), "workspace_not_configured")
        self.assertFalse(os.path.exists(self._cfg_path(ds)),
                         "未接入时不许顺手造一份配置出来")

    def test_v14_not_applicable_when_projects_live_in_a_subdir(self):
        """**A5**:项目放在 `01-项目/` 之类子目录下时,`excluded_structural()`
        直接返回 `[]` —— 这批用户根本不存在误伤问题,不该给他们显示确认区,
        更不该让他们从这里写 `structuralDirs`(那只会影响不到任何东西 / 造成误解)。
        """
        ds, ws = self._env([DEFAULT_INBOX, "01-项目"], projectsDir="01-项目")
        os.makedirs(os.path.join(ws, "01-项目", "真项目"))
        before = self._raw_bytes(ds)
        with _serve(ds) as port:
            h = self._health(port)
            self.assertFalse(h.get("applicable"),
                             "projects_root != root 时不适用")
            self.assertEqual(h.get("folders") or [], [], "不适用就别列确认区")
            st, r = _post(port, SAVE,
                          {"review_id": h.get("reviewId") or "x",
                           "hidden": [DEFAULT_INBOX]})
        self.assertEqual(st, 409, r)
        self.assertEqual(r.get("error"), "not_applicable")
        self.assertEqual(self._raw_bytes(ds), before)

    def test_v17_bad_config_degrades_and_is_never_clobbered(self):
        """坏配置 → 读口降级(可恢复状态,不 500)、写口拒;
        **不尝试顺手修好**,用户手写的原文一个字节不许动(Non-goal 明写)。"""
        ds, ws = self._env([DEFAULT_INBOX])
        for bad in ('{ 坏 json', '[]', '"字符串"', '{"root": 5}'):
            with self.subTest(cfg=bad):
                with open(self._cfg_path(ds), "w", encoding="utf-8") as fh:
                    fh.write(bad)
                before = self._raw_bytes(ds)
                with _serve(ds) as port:
                    st, r = _get(port, HEALTH)
                    self.assertIn(st, (200, 409), f"坏配置不许 500:{bad}")
                    if st == 200:
                        self.assertFalse(r.get("configured"))
                    st2, _ = _post(port, SAVE, {"review_id": "x", "hidden": []})
                self.assertIn(st2, (400, 409))
                self.assertEqual(self._raw_bytes(ds), before,
                                 "不许自动修复/覆盖用户手写的配置")

    def test_v17b_bad_structural_dirs_value_does_not_take_down_the_card(self):
        """`structuralDirs` 本身是坏值(非列表 / 带路径成分 / 非字符串)时,
        `load_config` 的既定语义是**忽略这一项、不让整份配置下线**
        —— 因为它天然是用户手填/体检卡写入的地方,一个错字不该把工作区功能关掉。
        卡片必须照常开出来,让用户能**从这里把它改回去**。"""
        ds, ws = self._env([DEFAULT_INBOX, "真项目"])
        for bad in ("不是列表", 5, ["深/收件箱"], [5, None], [".."]):
            with self.subTest(value=bad):
                raw = self._read_cfg(ds)
                raw["structuralDirs"] = bad
                self._write_cfg(ds, raw)
                with _serve(ds) as port:
                    st, r = _get(port, HEALTH)
                self.assertEqual(st, 200, f"坏 structuralDirs 不许让卡片打不开:{bad!r}")
                self.assertTrue(r.get("configured"))
                names = {row["name"] for row in r["folders"]}
                self.assertIn("真项目", names, "真项目必须照常出现在卡片上")


class Concurrency(FolderVisibilityBase):
    """与 oracle(一)呼应:这里打的是端到端 —— 网页写口是**第二个并发来源**。"""

    def test_v19_web_save_does_not_race_with_other_writers(self):
        """网页保存与助手侧写口(bind_project)并发,跑完之后:
          ① 配置必须还是合法 JSON(不然读侧整份降级 = 用户眼里项目全没了);
          ② 两边的改动都在(不丢更新)。
        """
        import ds_tools  # noqa: PLC0415 —— 只在本条用到

        ds, ws = self._env([DEFAULT_INBOX] + [f"项目{i}" for i in range(15)])
        for i in range(15):
            with open(os.path.join(ds, "projects", f"项目{i}.md"),
                      "w", encoding="utf-8") as fh:
                fh.write(f"# 项目{i}\n\n最后更新: 2026-07-26\n")
        crashes, saved = [], []

        def binder():
            for i in range(15):
                try:
                    ds_tools.bind_project(f"项目{i}", f"项目{i}", ds_root=ds)
                except Exception as e:
                    crashes.append(("bind", repr(e)))

        with _serve(ds) as port:
            def saver():
                for _ in range(15):
                    try:
                        h = self._health(port)
                        st, _r = _post(port, SAVE,
                                       {"review_id": h["reviewId"],
                                        "hidden": [DEFAULT_INBOX]})
                        saved.append(st)
                    except Exception as e:
                        crashes.append(("save", repr(e)))

            ts = [threading.Thread(target=binder), threading.Thread(target=saver)]
            for t in ts:
                t.start()
            for t in ts:
                t.join(90)
        self.assertEqual(crashes[:3], [], "并发期间不许抛")
        try:
            after = self._read_cfg(ds)
        except ValueError as e:
            self.fail(f"并发把 workspace.json 写坏了({e})")
        self.assertIsNotNone(ds_workspace.load_config(ds), "写坏的配置读侧直接下线")
        self.assertEqual(after.get("root"), ws)
        # 网页保存要么成功要么诚实 409(快照过期),不许有 5xx
        self.assertTrue(all(s in (200, 409) for s in saved), saved)
        self.assertIn(200, saved, "并发下网页保存不许一次都成不了")


if __name__ == "__main__":
    unittest.main()
