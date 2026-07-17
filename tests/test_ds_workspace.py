#!/usr/bin/env python3
"""ds_workspace oracle — track opendesign-workbench-p5 T1(design.md Test strategy #1)。

跑法:  python3 tests/test_ds_workspace.py
覆盖:workspace.json 解析(正常/缺文件/坏 json/root 不存在/projects 非 dict)、
key→项目夹解析(合法/未映射/映射逃逸/映射指向文件/symlink 外指)、
类目扫描 overview(计数/嵌套/深度上限/每类目上限截断/.opendesign 跳过/散文件归 ""/
最近文件按 mtime 降序)、图片列举 images(扩展白名单/rel 用 //类目)、
resolve_sub(单层类目名白名单/逃逸/多层/不存在)。

red-check(commit message 附结果):
  注释 project_dir 的 within 闸 → test_project_dir_mapping_escape / _symlink_escape 变红
  注释 resolve_sub 的 within 闸 → test_resolve_sub_symlink_escape 变红
  注释 images 扩展过滤 → test_images_ext_whitelist 变红

纯 stdlib、离线,夹具 = tmpdir 按 docs/workspace-taxonomy.md v1.0 造样例树。
"""
import json
import os
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_workspace  # noqa: E402

PROJ_REL = "01-项目/20260612 周宁 龙腾世纪 12#1802"
KEY = "龙腾世纪-1802"


def _touch(path, mtime=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"x")
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def make_workspace(tmp):
    """taxonomy v1.0 样例树。返回 (ds_root, ws_root)。"""
    ds_root = os.path.join(tmp, "ds")
    ws_root = os.path.join(tmp, "ws")
    proj = os.path.join(ws_root, *PROJ_REL.split("/"))
    base = time.time() - 86400
    _touch(os.path.join(proj, "01-资料", "户型图.dwg"), base + 10)
    _touch(os.path.join(proj, "01-资料", "量房", "IMG_001.jpg"), base + 20)
    _touch(os.path.join(proj, "02-参考图", "客厅参考.jpg"), base + 30)
    _touch(os.path.join(proj, "03-CAD", "平面.dwg"), base + 40)
    _touch(os.path.join(proj, "06-效果图", "定稿", "客厅终版.png"), base + 50)
    _touch(os.path.join(proj, "06-效果图", "notes.txt"), base + 5)
    _touch(os.path.join(proj, "散文件.txt"), base + 1)
    _touch(os.path.join(proj, ".opendesign", "index.json"), base)
    # 深度超限:类目下 4 层(项目根起第 5 层)不计
    _touch(os.path.join(proj, "01-资料", "a", "b", "c", "太深.jpg"), base)
    os.makedirs(os.path.join(ds_root, "config"), exist_ok=True)
    with open(os.path.join(ds_root, "config", "workspace.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"root": ws_root, "projects": {KEY: PROJ_REL}}, fh,
                  ensure_ascii=False)
    return ds_root, ws_root


class LoadConfigTest(unittest.TestCase):
    def test_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds_root, ws_root = make_workspace(tmp)
            cfg = ds_workspace.load_config(ds_root)
            self.assertIsNotNone(cfg)
            self.assertEqual(os.path.realpath(ws_root), cfg["root"])
            self.assertEqual({KEY: PROJ_REL}, cfg["projects"])

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(ds_workspace.load_config(tmp))

    def test_bad_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "config"))
            with open(os.path.join(tmp, "config", "workspace.json"), "w") as fh:
                fh.write("{broken")
            self.assertIsNone(ds_workspace.load_config(tmp))

    def test_root_not_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "config"))
            with open(os.path.join(tmp, "config", "workspace.json"), "w") as fh:
                json.dump({"root": os.path.join(tmp, "nope"), "projects": {}}, fh)
            self.assertIsNone(ds_workspace.load_config(tmp))

    def test_projects_not_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "config"))
            with open(os.path.join(tmp, "config", "workspace.json"), "w") as fh:
                json.dump({"root": tmp, "projects": ["x"]}, fh)
            self.assertIsNone(ds_workspace.load_config(tmp))


class ProjectDirTest(unittest.TestCase):
    def test_mapped(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds_root, ws_root = make_workspace(tmp)
            cfg = ds_workspace.load_config(ds_root)
            d = ds_workspace.project_dir(cfg, KEY)
            self.assertEqual(
                os.path.realpath(os.path.join(ws_root, *PROJ_REL.split("/"))), d)

    def test_unmapped(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds_root, _ = make_workspace(tmp)
            cfg = ds_workspace.load_config(ds_root)
            self.assertIsNone(ds_workspace.project_dir(cfg, "不存在的项目"))

    def test_mapping_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds_root, ws_root = make_workspace(tmp)
            os.makedirs(os.path.join(tmp, "outside"))
            cfg = ds_workspace.load_config(ds_root)
            cfg["projects"]["恶意"] = "../outside"
            self.assertIsNone(ds_workspace.project_dir(cfg, "恶意"))

    def test_mapping_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds_root, ws_root = make_workspace(tmp)
            cfg = ds_workspace.load_config(ds_root)
            cfg["projects"]["文件"] = PROJ_REL + "/散文件.txt"
            self.assertIsNone(ds_workspace.project_dir(cfg, "文件"))

    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds_root, ws_root = make_workspace(tmp)
            outside = os.path.join(tmp, "outside")
            os.makedirs(outside)
            os.symlink(outside, os.path.join(ws_root, "link"))
            cfg = ds_workspace.load_config(ds_root)
            cfg["projects"]["链"] = "link"
            self.assertIsNone(ds_workspace.project_dir(cfg, "链"))


class OverviewTest(unittest.TestCase):
    def _proj(self, tmp):
        ds_root, ws_root = make_workspace(tmp)
        cfg = ds_workspace.load_config(ds_root)
        return ds_workspace.project_dir(cfg, KEY)

    def test_categories_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            ov = ds_workspace.overview(self._proj(tmp))
            cats = {c["name"]: c for c in ov["categories"]}
            # .opendesign 不是类目;散文件归 ""(未分类)
            self.assertNotIn(".opendesign", cats)
            self.assertEqual(2, cats["01-资料"]["count"])  # 深度超限的太深.jpg 不计
            self.assertEqual(1, cats["02-参考图"]["count"])
            self.assertEqual(1, cats["03-CAD"]["count"])
            self.assertEqual(2, cats["06-效果图"]["count"])
            self.assertEqual(1, cats[""]["count"])
            names = [c["name"] for c in ov["categories"]]
            self.assertEqual(sorted(names), names)  # 类目名序稳定

    def test_recent_order_and_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            ov = ds_workspace.overview(self._proj(tmp), recent_n=3)
            recent = ov["recent"]
            self.assertEqual(3, len(recent))
            self.assertEqual("客厅终版.png", recent[0]["name"])  # 最新在前
            self.assertEqual("06-效果图", recent[0]["category"])
            mt = [r["mtime"] for r in recent]
            self.assertEqual(sorted(mt, reverse=True), mt)
            for r in recent:
                for k in ("name", "category", "mtime", "size"):
                    self.assertIn(k, r)

    def test_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._proj(tmp)
            ov = ds_workspace.overview(proj, max_per_cat=1)
            cats = {c["name"]: c for c in ov["categories"]}
            self.assertTrue(cats["01-资料"]["capped"])
            self.assertEqual(1, cats["01-资料"]["count"])
            self.assertFalse(cats["02-参考图"]["capped"])

    def test_opendesign_skipped_in_recent(self):
        with tempfile.TemporaryDirectory() as tmp:
            ov = ds_workspace.overview(self._proj(tmp), recent_n=50)
            self.assertNotIn("index.json", [r["name"] for r in ov["recent"]])

    # cockpit T1:类目活跃度 = 该类目最新文件 mtime
    def test_latest_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._proj(tmp)
            mark = 2_000_000_000  # 显式钉一个未来值,断言不依赖夹具的相对时序
            os.utime(os.path.join(proj, "01-资料", "户型图.dwg"), (mark, mark))
            ov = ds_workspace.overview(proj)
            cats = {c["name"]: c for c in ov["categories"]}
            self.assertEqual(mark, cats["01-资料"]["latest_mtime"])
            # 每个未截断类目:latest_mtime = recent 口径下该类目文件的最大 mtime
            ov_all = ds_workspace.overview(proj, recent_n=10_000)
            by_cat = {}
            for r in ov_all["recent"]:
                by_cat[r["category"]] = max(by_cat.get(r["category"], 0), r["mtime"])
            for c in ov["categories"]:
                if not c["capped"]:
                    self.assertEqual(by_cat[c["name"]], c["latest_mtime"], c["name"])

    # cockpit T1:capped 类目名序截断后 max 不可信 → 置 None(宁缺勿假)
    def test_latest_mtime_capped_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._proj(tmp)
            ov = ds_workspace.overview(proj, max_per_cat=1)
            cats = {c["name"]: c for c in ov["categories"]}
            self.assertTrue(cats["01-资料"]["capped"])
            self.assertIsNone(cats["01-资料"]["latest_mtime"])
            self.assertIsNotNone(cats["02-参考图"]["latest_mtime"])


class ImagesTest(unittest.TestCase):
    def test_ext_whitelist_and_rel(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds_root, _ = make_workspace(tmp)
            cfg = ds_workspace.load_config(ds_root)
            proj = ds_workspace.project_dir(cfg, KEY)
            imgs = ds_workspace.images(proj)
            rels = sorted(i["rel"] for i in imgs)
            self.assertEqual(
                ["01-资料/量房/IMG_001.jpg", "02-参考图/客厅参考.jpg",
                 "06-效果图/定稿/客厅终版.png"], rels)
            by_rel = {i["rel"]: i for i in imgs}
            self.assertEqual("02-参考图", by_rel["02-参考图/客厅参考.jpg"]["category"])
            for i in imgs:
                self.assertIn("mtime", i)
                self.assertNotIn("\\", i["rel"])  # URL 友好:统一正斜杠


class ResolveSubTest(unittest.TestCase):
    def _proj(self, tmp):
        ds_root, _ = make_workspace(tmp)
        cfg = ds_workspace.load_config(ds_root)
        return ds_workspace.project_dir(cfg, KEY)

    def test_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._proj(tmp)
            self.assertEqual(os.path.realpath(os.path.join(proj, "03-CAD")),
                             ds_workspace.resolve_sub(proj, "03-CAD"))

    def test_none_sub_returns_proj(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._proj(tmp)
            self.assertEqual(proj, ds_workspace.resolve_sub(proj, None))
            self.assertEqual(proj, ds_workspace.resolve_sub(proj, ""))

    def test_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._proj(tmp)
            for bad in ("..", "../x", "a/b", "a\\b", "不存在", "散文件.txt",
                        ".opendesign", "/abs", "a\x00b"):
                self.assertIsNone(ds_workspace.resolve_sub(proj, bad), bad)

    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._proj(tmp)
            outside = os.path.join(tmp, "outside2")
            os.makedirs(outside)
            os.symlink(outside, os.path.join(proj, "外链"))
            self.assertIsNone(ds_workspace.resolve_sub(proj, "外链"))


class CharsetConvergenceTest(unittest.TestCase):
    """M2(07-13 盲评 + 07-14 v2 黑名单化):列出=可寻址,单段闸 _SEG_RE 单一真相源。

    v1 用字符白名单只补了 #,但 & / 中文全角标点(（）等)仍被枚举侧静默过滤=用户
    看不见自己的文件。v2 改黑名单:Gate A 只挡 / \\ % 与控制符,放行其余常见命名字符;
    权威逃逸闸仍是 realpath+within。只有真·危险字符(%)才诚实缺席(既不列也不寻址)。
    """

    def _proj(self, tmp):
        ds_root, _ = make_workspace(tmp)
        cfg = ds_workspace.load_config(ds_root)
        return ds_workspace.project_dir(cfg, KEY)

    def test_hash_and_punct_listed_and_addressable(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._proj(tmp)
            _touch(os.path.join(proj, "08-交付#归档", "12#1802-客厅.png"))
            _touch(os.path.join(proj, "02-参考图（复尺）", "报价&终稿.png"))  # 全角括号+&
            imgs = [i["rel"] for i in ds_workspace.images(proj)]
            self.assertIn("08-交付#归档/12#1802-客厅.png", imgs)
            self.assertIn("02-参考图（复尺）/报价&终稿.png", imgs)
            self.assertIsNotNone(ds_workspace.resolve_sub(proj, "08-交付#归档"))
            self.assertIsNotNone(ds_workspace.resolve_sub(proj, "02-参考图（复尺）"))

    def test_unservable_chars_not_listed(self):
        # % 是 URL 编码引信 → 黑名单拒;含 % 的文件/目录枚举侧诚实缺席
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._proj(tmp)
            _touch(os.path.join(proj, "02-参考图", "报价%终稿.png"))
            _touch(os.path.join(proj, "素材%杂", "ok.png"))
            blob = json.dumps({"o": ds_workspace.overview(proj),
                               "i": ds_workspace.images(proj)}, ensure_ascii=False)
            self.assertNotIn("%", blob)


class AutoDiscoveryTest(unittest.TestCase):
    """p7:projects_root / project_folders / project_dir 三级绑定。
    red-check:注释 project_dir 的唯一命中判断(len(hits)==1)→ token_ambiguous 红;
    注释 project_folders 的 _FOLDER_RE 过滤 → folders_charset 红;
    注释 projects_root 显式 projectsDir 的 within 闸 → projects_root_escape 红。"""

    def _cfg(self, tmp, mapping=None, projects_dir=None, extra_folders=()):
        ds_root, ws_root = make_workspace(tmp)
        for name in extra_folders:
            os.makedirs(os.path.join(ws_root, "01-项目", name), exist_ok=True)
        raw = {"root": ws_root, "projects": mapping or {}}
        if projects_dir is not None:
            raw["projectsDir"] = projects_dir
        with open(os.path.join(ds_root, "config", "workspace.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(raw, fh, ensure_ascii=False)
        return ds_workspace.load_config(ds_root), ws_root

    def test_projects_root_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, ws_root = self._cfg(tmp)
            self.assertEqual(ds_workspace.projects_root(cfg),
                             os.path.realpath(os.path.join(ws_root, "01-项目")))

    def test_projects_root_explicit_and_dot(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, ws_root = self._cfg(tmp, projects_dir="01-项目")
            self.assertEqual(ds_workspace.projects_root(cfg),
                             os.path.realpath(os.path.join(ws_root, "01-项目")))
            cfg2, ws_root2 = self._cfg(tmp, projects_dir=".")
            self.assertEqual(ds_workspace.projects_root(cfg2),
                             os.path.realpath(ws_root2))

    def test_projects_root_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "outside"), exist_ok=True)
            cfg, _ = self._cfg(tmp, projects_dir="../outside")
            self.assertIsNone(ds_workspace.projects_root(cfg))

    def test_projects_root_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, ws_root = self._cfg(tmp)
            os.rename(os.path.join(ws_root, "01-项目"),
                      os.path.join(ws_root, "项目都在这"))
            self.assertIsNone(ds_workspace.projects_root(cfg))
            self.assertEqual(ds_workspace.project_folders(cfg), [])

    def test_project_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, ws_root = self._cfg(tmp, extra_folders=("20260701 平湖 翡翠湾 3#1801",))
            pdir = os.path.join(ws_root, "01-项目")
            _touch(os.path.join(pdir, "散文件.txt"))          # 文件不列
            os.makedirs(os.path.join(pdir, ".回收"))           # 点号开头不列
            os.symlink(tmp, os.path.join(pdir, "外链夹"))       # symlink 不列
            names = [n for n, _ in ds_workspace.project_folders(cfg)]
            self.assertEqual(names, ["20260612 周宁 龙腾世纪 12#1802",
                                     "20260701 平湖 翡翠湾 3#1801"])

    def test_project_folders_charset(self):
        # v2 黑名单:含 % 的文件夹名(URL 编码引信)仍被过滤;| & 等普通字符已放行
        with tempfile.TemporaryDirectory() as tmp:
            cfg, ws_root = self._cfg(tmp, extra_folders=("坏名%线", "正常&楼盘"))
            names = [n for n, _ in ds_workspace.project_folders(cfg)]
            self.assertNotIn("坏名%线", names)
            self.assertIn("正常&楼盘", names)  # & 是合法命名字符,应列出

    def test_project_dir_explicit_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            # 显式映射指向另一个文件夹,token 明明命中默认夹也不用
            cfg, ws_root = self._cfg(
                tmp, mapping={KEY: "01-项目/手工指定"}, extra_folders=("手工指定",))
            self.assertEqual(ds_workspace.project_dir(cfg, KEY),
                             os.path.realpath(os.path.join(ws_root, "01-项目", "手工指定")))

    def test_project_dir_direct_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, ws_root = self._cfg(tmp)
            name = "20260612 周宁 龙腾世纪 12#1802"
            self.assertEqual(ds_workspace.project_dir(cfg, name),
                             os.path.realpath(os.path.join(ws_root, "01-项目", name)))

    def test_project_dir_token_unique(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, ws_root = self._cfg(tmp)  # 无映射:靠 token 龙腾世纪+1802 唯一命中
            self.assertEqual(
                ds_workspace.project_dir(cfg, KEY),
                os.path.realpath(os.path.join(
                    ws_root, "01-项目", "20260612 周宁 龙腾世纪 12#1802")))

    def test_project_dir_token_ambiguous(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, _ = self._cfg(tmp, extra_folders=("20270101 周宁 龙腾世纪 12#1802 二期",))
            self.assertIsNone(ds_workspace.project_dir(cfg, KEY))

    def test_project_dir_no_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, _ = self._cfg(tmp)
            self.assertIsNone(ds_workspace.project_dir(cfg, "翡翠湾-1801"))


class GroupedProjectsTest(unittest.TestCase):
    """depth2 track:projectsDepth=2 两层扫描(分组/项目,key=`组:名`)。
    red-check(commit message 附结果):
      把 depth=2 扫描改回一层 → test_g01/g02 红;
      去掉分组名 PROJECT_NAME_RE 过滤 → test_g03 红;
      去掉 load_config 的 projectsDepth 取值校验 → test_g06 红。"""

    def _cfg(self, tmp, depth=2, mapping=None):
        """root 即两层根(如 D:\\G2 DESIGN GROUP):projectsDir="."。
        树:2024(空组)/2025{0108 欧派, 0605 某项目}/2026{0315 某项目, 0605 某项目}
        + 干扰项(散文件/点头组/坏名组/坏名项目/symlink 组)。"""
        ds_root = os.path.join(tmp, "ds")
        ws_root = os.path.join(tmp, "ws")
        for rel in ("2024",
                    "2025/0108 某项目 欧派", "2025/0605 某项目",
                    "2026/0315 某项目", "2026/0605 某项目",
                    ".回收/x", "坏名%组/项目A", "2026/坏名%项目"):
            os.makedirs(os.path.join(ws_root, *rel.split("/")), exist_ok=True)
        _touch(os.path.join(ws_root, "根散文件.txt"))
        _touch(os.path.join(ws_root, "2026", "组内散文件.txt"))
        if not os.path.lexists(os.path.join(ws_root, "外链组")):
            os.symlink(tmp, os.path.join(ws_root, "外链组"))  # g06 复用 tmp 容忍
        if not os.path.lexists(os.path.join(ws_root, "2026", "外链项目")):
            # submimo S3:分组「内」的 symlink 项目也要被拒(两级同闸的第二级凭证)
            os.symlink(tmp, os.path.join(ws_root, "2026", "外链项目"))
        os.makedirs(os.path.join(ds_root, "config"), exist_ok=True)
        raw = {"root": ws_root, "projects": mapping or {},
               "projectsDir": ".", "projectsDepth": depth}
        with open(os.path.join(ds_root, "config", "workspace.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(raw, fh, ensure_ascii=False)
        return ds_workspace.load_config(ds_root), ws_root

    # ① keyed 名单:组名序→项目名序;空组无条目;散文件/点头/symlink 全跳
    def test_g01_keyed_listing_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, ws_root = self._cfg(tmp)
            folders = ds_workspace.project_folders(cfg)
            self.assertEqual([n for n, _ in folders],
                             ["2025:0108 某项目 欧派", "2025:0605 某项目",
                              "2026:0315 某项目", "2026:0605 某项目"])
            self.assertEqual(
                folders[2][1],
                os.path.realpath(os.path.join(ws_root, "2026", "0315 某项目")))

    # ② keyed key 直等命中 project_dir(②级解析零改动即通)
    def test_g02_project_dir_keyed_direct(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, ws_root = self._cfg(tmp)
            self.assertEqual(
                ds_workspace.project_dir(cfg, "2025:0605 某项目"),
                os.path.realpath(os.path.join(ws_root, "2025", "0605 某项目")))

    # ③ 坏名分组整组跳过(组名不过 PROJECT_NAME_RE → 其下项目不列)
    def test_g03_bad_group_name_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, _ = self._cfg(tmp)
            names = [n for n, _ in ds_workspace.project_folders(cfg)]
            self.assertFalse(any("项目A" in n for n in names))
            self.assertFalse(any("坏名%项目" in n for n in names))
            self.assertFalse(any("外链项目" in n for n in names))  # 组内 symlink 拒

    # ④ 跨组重名:裸名 token 双命中 → 歧义不绑;token 唯一 → 命中
    def test_g04_cross_group_ambiguity(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, ws_root = self._cfg(tmp)
            self.assertIsNone(ds_workspace.project_dir(cfg, "0605-某项目"))
            self.assertEqual(
                ds_workspace.project_dir(cfg, "0315-某项目"),
                os.path.realpath(os.path.join(ws_root, "2026", "0315 某项目")))

    # ⑤ 显式映射优先,指向分组内项目夹照常命中
    def test_g05_explicit_mapping_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, ws_root = self._cfg(tmp, mapping={"某项目-0605": "2025/0605 某项目"})
            self.assertEqual(
                ds_workspace.project_dir(cfg, "某项目-0605"),
                os.path.realpath(os.path.join(ws_root, "2025", "0605 某项目")))

    # ⑥ config 校验:非 int / 取值 3 / 字符串 "2" / bool → 整体 None;
    #    缺省或 null → 归一成 1(同 projectsDir:null=未配置)
    def test_g06_depth_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            for bad in ("2", 3, 0, 1.5, True):
                cfg, _ = self._cfg(tmp, depth=bad)
                self.assertIsNone(cfg, f"projectsDepth={bad!r} 应整体降级")
            cfg, _ = self._cfg(tmp, depth=None)  # JSON null = 未配置
            self.assertIsNotNone(cfg)
            self.assertEqual(cfg["projectsDepth"], 1)
            ds_root, ws_root = make_workspace(tmp)
            cfg = ds_workspace.load_config(ds_root)  # 缺省字段
            self.assertEqual(cfg["projectsDepth"], 1)

    # ⑦ depth=1 显式写也合法,行为=现行一层(回归护栏)
    def test_g07_depth1_explicit_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, ws_root = self._cfg(tmp, depth=1)
            names = [n for n, _ in ds_workspace.project_folders(cfg)]
            # 一层视角:分组夹本身被当项目列出,无 keyed 条目
            self.assertIn("2025", names)
            self.assertFalse(any(":" in n for n in names))


if __name__ == "__main__":
    unittest.main(verbosity=2)
