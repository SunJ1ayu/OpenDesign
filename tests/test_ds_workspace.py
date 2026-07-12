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


if __name__ == "__main__":
    unittest.main(verbosity=2)
