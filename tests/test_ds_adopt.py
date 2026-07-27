#!/usr/bin/env python3
"""track opendesign-adoption 的 oracle — 主 agent 拥有,executor off-limits。

覆盖:T1 ds_adopt.adopt_scan(只读全盘盘点)/ T3 ds_adopt.stage_adoption
(项目根散文件按 taxonomy 暂存;auto→plan,suggest→advice,未知→skipped)。

跑法:  python3 tests/test_ds_adopt.py
不需要 nanobot / mcp SDK / 网络 —— 只测纯 Python 核心。
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # design-studio/
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_adopt  # noqa: E402  ← 新模块,不存在即全红

PROJECT_MD = """# {slug}

- 业主: [[张三]]
- 阶段: 方案深化

## 变更记录

---
最后更新: 2026-07-01
"""


def _w(base, rel, content=""):
    path = os.path.join(base, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


class _Fixture(unittest.TestCase):
    """ds_root(PKB)+ 独立工作区根,taxonomy 用仓内 default(永远存在)。"""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="dsadopt-pkb-")
        self.ws = tempfile.mkdtemp(prefix="dsadopt-ws-")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        # 工作区骨架(taxonomy v1.0 命名)
        self.folder = "20260612 周宁 龙腾世纪 12#1802"
        for d in ("00-收件箱", f"01-项目/{self.folder}",
                  "01-项目/20260101 城南 老盘 3#301",
                  "02-归档项目/2026", "03-共享资源/参考图库"):
            os.makedirs(os.path.join(self.ws, d))
        # PKB:翡翠湾-1801 显式绑定到 folder;没夹的项目=反向未绑定
        _w(self.base, "projects/翡翠湾-1801.md", PROJECT_MD.format(slug="翡翠湾-1801"))
        _w(self.base, "projects/没夹的项目.md", PROJECT_MD.format(slug="没夹的项目"))
        _w(self.base, "config/workspace.json", json.dumps({
            "root": self.ws, "projectsDir": "01-项目",
            "projects": {"翡翠湾-1801": f"01-项目/{self.folder}"},
        }, ensure_ascii=False))
        self.proj_abs = os.path.join(self.ws, "01-项目", self.folder)


class TestAdoptScan(_Fixture):
    def test_01_unconfigured(self):
        empty = tempfile.mkdtemp(prefix="dsadopt-empty-")
        self.addCleanup(shutil.rmtree, empty, ignore_errors=True)
        r = ds_adopt.adopt_scan(empty)
        self.assertTrue(r.get("ok"), r)
        self.assertFalse(r["configured"])

    def test_02_structure_recognition(self):
        r = ds_adopt.adopt_scan(self.base)
        self.assertTrue(r.get("ok"), r)
        self.assertTrue(r["configured"])
        st = r["structure"]
        self.assertEqual(st["inbox"], "00-收件箱")
        self.assertEqual(st["projects_root"], "01-项目")
        self.assertEqual(st["archive"], "02-归档项目")
        self.assertEqual(st["shared"], "03-共享资源")

    def test_03_structure_missing_is_null(self):
        shutil.rmtree(os.path.join(self.ws, "02-归档项目"))
        r = ds_adopt.adopt_scan(self.base)
        self.assertIsNone(r["structure"]["archive"])

    def test_04_projects_bound_and_unbound(self):
        r = ds_adopt.adopt_scan(self.base)
        rows = {p["folder"]: p for p in r["projects"]}
        self.assertIn(self.folder, rows)
        self.assertTrue(rows[self.folder]["bound"])
        self.assertEqual(rows[self.folder]["key"], "翡翠湾-1801")
        other = rows["20260101 城南 老盘 3#301"]
        self.assertFalse(other["bound"])
        self.assertIsNone(other["key"])

    def test_05_unbound_pkb_reverse(self):
        r = ds_adopt.adopt_scan(self.base)
        self.assertEqual(r["unbound_pkb"], ["没夹的项目"])

    def test_06_categories_and_loose_files(self):
        os.makedirs(os.path.join(self.proj_abs, "03-CAD"))
        os.makedirs(os.path.join(self.proj_abs, "自定义类目"))
        _w(self.ws, f"01-项目/{self.folder}/户型图.pdf", "x")
        _w(self.ws, f"01-项目/{self.folder}/03-CAD/平面.dwg", "x")  # 类目内,不算散
        r = ds_adopt.adopt_scan(self.base)
        row = next(p for p in r["projects"] if p["folder"] == self.folder)
        self.assertEqual(sorted(row["categories"]), ["03-CAD", "自定义类目"])
        self.assertEqual(row["loose_files"], 1)

    def test_07_scan_readonly(self):
        _w(self.ws, f"01-项目/{self.folder}/户型图.pdf", "x")
        before = sorted(os.walk(self.ws))
        ds_adopt.adopt_scan(self.base)
        self.assertEqual(sorted(os.walk(self.ws)), before)


class TestStageAdoption(_Fixture):
    def setUp(self):
        super().setUp()
        _w(self.ws, f"01-项目/{self.folder}/户型图.pdf", "pdf")   # auto → 01-资料
        _w(self.ws, f"01-项目/{self.folder}/灵感.jpg", "jpg")     # auto → 共享参考图库
        _w(self.ws, f"01-项目/{self.folder}/平面.dwg", "dwg")     # suggest → advice
        _w(self.ws, f"01-项目/{self.folder}/奇怪.xyz", "xyz")     # 未知 → skipped

    def stage(self, key="翡翠湾-1801"):
        return ds_adopt.stage_adoption(key, ds_root=self.base,
                                       allowed_roots=[self.ws])

    def test_01_stages_auto_only(self):
        """存量整理只暂存**留在项目夹内**的 auto 类目。

        2026-07-27 真机反馈改判:原来这里断言 `灵感.jpg` 也被暂存,dst 是工作区级的
        `03-共享资源/参考图库` —— 即**把用户项目里的图片搬出项目**。用户的原话是
        「项目文件夹其他的图片会突然出现在收件箱」。
        判据翻面的理由(不是为了让实现好过):**收养处理的是用户从没要求过任何人
        动的存量文件**,而「所有图片=参考图」这个分类只看后缀,分不出「通用参考图」
        和「这个项目自己的效果图/现场照」。在分不清的地方自动搬 = 拿猜测动用户文件,
        猜错的代价(项目图片失联)远大于收益(省一次点击)。
        收件箱那条路**刻意不动**:那里的文件是用户主动放进暂存区的,自动归位合理。
        守门判据在 `test_ds_intake.py::test_workspace_scope_needs_no_project`
        —— 改坏它就等于把用户的正常流程也一起关了,那条必须始终绿。
        """
        r = self.stage()
        self.assertTrue(r.get("ok"), r)
        staged_srcs = [op["src_rel"] for op in r["staged"]]
        self.assertEqual(len(staged_srcs), 1, f"只该暂存户型图.pdf,实际 {staged_srcs}")
        self.assertTrue(any("户型图.pdf" in s for s in staged_srcs))
        self.assertFalse(any("灵感.jpg" in s for s in staged_srcs),
                         "项目夹里的图片不许被自动搬走")
        dst_by_src = {op["src_rel"]: op["dst_rel"] for op in r["staged"]}
        pdf_dst = next(v for k, v in dst_by_src.items() if "户型图" in k)
        self.assertIn("01-资料", pdf_dst)
        self.assertIn(self.folder, pdf_dst)          # 项目内类目

    def test_01b_workspace_scoped_never_leaves_the_project(self):
        """通则,不只是图片:**任何 workspace 级类目在存量整理里都只给建议**。
        判据打在「会不会离开项目夹」这条线上,而不是打在「参考图」这个名字上 ——
        以后规则表新增一个工作区级类目,这条闸自动罩住它。"""
        r = self.stage()
        self.assertTrue(any("灵感.jpg" in a["file"] for a in r["advice"]),
                        f"图片该进 advice 口头建议,实际 advice={r['advice']}")
        for op in r["staged"]:
            self.assertIn(self.folder, op["dst_rel"],
                          f"存量整理的落点必须留在项目夹内:{op}")
        # 文件还在原处,一个字节都没动
        self.assertTrue(os.path.exists(
            os.path.join(self.ws, "01-项目", self.folder, "灵感.jpg")))

    def test_02_suggest_goes_to_advice_not_plan(self):
        r = self.stage()
        self.assertTrue(any("平面.dwg" in a["file"] for a in r["advice"]))
        self.assertFalse(any("平面.dwg" in op["src_rel"] for op in r["staged"]))

    def test_03_unknown_ext_skipped(self):
        r = self.stage()
        self.assertTrue(any("奇怪.xyz" in s for s in r["skipped"]))

    def test_04_plan_written_root_is_workspace(self):
        r = self.stage()
        plan_path = os.path.join(self.base, "organize", "plans",
                                 f"plan_{r['plan_id']}.json")
        self.assertTrue(os.path.exists(plan_path))
        with open(plan_path, encoding="utf-8") as fh:
            plan = json.load(fh)
        self.assertEqual(os.path.realpath(plan["root"]),
                         os.path.realpath(self.ws))

    def test_05_stage_moves_nothing(self):
        self.stage()
        for fn in ("户型图.pdf", "灵感.jpg", "平面.dwg", "奇怪.xyz"):
            self.assertTrue(
                os.path.exists(os.path.join(self.proj_abs, fn)),
                f"{fn} 在暂存阶段就被动了")

    def test_06_nothing_to_stage(self):
        for fn in ("户型图.pdf", "灵感.jpg"):
            os.remove(os.path.join(self.proj_abs, fn))
        r = self.stage()
        self.assertEqual(r.get("error"), "nothing_to_stage")
        self.assertTrue(any("平面.dwg" in a["file"] for a in r.get("advice", [])))

    def test_07_project_not_bound(self):
        r = self.stage("没夹的项目")
        self.assertEqual(r.get("error"), "project_not_bound")

    def test_08_workspace_not_configured(self):
        os.remove(os.path.join(self.base, "config", "workspace.json"))
        r = self.stage()
        self.assertEqual(r.get("error"), "workspace_not_configured")


if __name__ == "__main__":
    unittest.main(verbosity=2)
