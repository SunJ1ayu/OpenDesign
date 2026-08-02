#!/usr/bin/env python3
"""ds_refs 核心的 oracle 矩阵 — 对齐 track opendesign-ref-images design.md。

跑法:  python3 tests/test_ds_refs.py
零依赖零网络。铁律:词表校验(空间锁死/风格半开放)、r<n> 锚定、不删行、
工具只写索引不碰图片文件、路径存储统一 / 分隔符。
"""
import os
import sys
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # design-studio/
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_refs  # noqa: E402

TODAY = "2026-07-02"


def _touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"\xff\xd8fakejpg")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class RefsOracle(unittest.TestCase):
    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dsrefs-")
        # 图库文件
        self.img1 = os.path.join(self.ds, "refs", "奶油风", "客厅", "a.jpg")
        self.img2 = os.path.join(self.ds, "refs", "侘寂风", "主卧", "b.jpg")
        _touch(self.img1)
        _touch(self.img2)
        # 一个真实项目文件(link_ref 校验用)
        proj = os.path.join(self.ds, "projects", "翡翠湾-1801.md")
        os.makedirs(os.path.dirname(proj), exist_ok=True)
        with open(proj, "w", encoding="utf-8") as fh:
            fh.write("# 翡翠湾-1801\n\n## 变更记录\n\n---\n最后更新: 2026-06-20\n")
        self.index = os.path.join(self.ds, "refs-index.md")

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def _add(self, file=None, style="奶油风", space="客厅", source="小红书",
             note="弧形吊顶"):
        return ds_refs.add_ref(file or "refs/奶油风/客厅/a.jpg", style, space,
                               source, note, ds_root=self.ds, today=TODAY)

    def _entries(self):
        if not os.path.exists(self.index):
            return []
        return [ln for ln in _read(self.index).split("\n")
                if ds_refs._REF_RE.match(ln)]

    # ① add 正常:r1、格式、索引自动建、最后更新
    def test_01_add_normal(self):
        r = self._add()
        self.assertTrue(r.get("ok"), msg=str(r))
        self.assertEqual(r["ref_id"], "r1")
        text = _read(self.index)
        self.assertIn("[r1] 奶油风|客厅", text)
        self.assertIn("来源:小红书", text)
        self.assertIn("文件:refs/奶油风/客厅/a.jpg", text)
        self.assertIn("弧形吊顶", text)
        self.assertIn(f"最后更新: {TODAY}", text)

    # ② 编号连续
    def test_02_numbering(self):
        self._add()
        r = self._add(file="refs/侘寂风/主卧/b.jpg", style="侘寂风", space="主卧",
                      source="Pinterest", note="")
        self.assertEqual(r["ref_id"], "r2")

    # ③ 词表外的风格/空间 → 拒 + 零改动
    def test_03_vocab_rejected(self):
        r = self._add(style="赛博朋克")
        self.assertEqual(r.get("error"), "style_unknown")
        r2 = self._add(space="太空舱")
        self.assertEqual(r2.get("error"), "space_unknown")
        self.assertEqual(self._entries(), [])

    # ④ add_style 后放行 + 幂等
    def test_04_add_style(self):
        r = ds_refs.add_style("赛博朋克", ds_root=self.ds)
        self.assertTrue(r.get("ok"), msg=str(r))
        r2 = ds_refs.add_style("赛博朋克", ds_root=self.ds)  # 幂等
        self.assertTrue(r2.get("ok"))
        r3 = self._add(style="赛博朋克")
        self.assertTrue(r3.get("ok"), msg=str(r3))

    # ⑤ 空间锁死:没有任何新增入口,unknown 恒拒
    def test_05_space_locked(self):
        self.assertFalse(hasattr(ds_refs, "add_space"))
        r = self._add(space="太空舱")
        self.assertEqual(r.get("error"), "space_unknown")

    # ⑥ 文件校验:不存在→file_not_found;逃逸→path_escape;refs/ 外→path_escape
    def test_06_file_validation(self):
        r = self._add(file="refs/奶油风/客厅/不存在.jpg")
        self.assertEqual(r.get("error"), "file_not_found")
        r2 = self._add(file="../../etc/passwd")
        self.assertEqual(r2.get("error"), "path_escape")
        outside = os.path.join(self.ds, "projects", "x.jpg")
        _touch(outside)
        r3 = self._add(file="projects/x.jpg")
        self.assertEqual(r3.get("error"), "path_escape")
        self.assertEqual(self._entries(), [])

    # ⑦ find:按风格/空间/项目/keyword 过滤,空参=全量
    def test_07_find(self):
        self._add()
        self._add(file="refs/侘寂风/主卧/b.jpg", style="侘寂风", space="主卧",
                  source="Pinterest", note="洞洞板")
        ds_refs.link_ref("r2", "翡翠湾-1801", ds_root=self.ds, today=TODAY)
        all_ = ds_refs.find_refs(ds_root=self.ds)
        self.assertEqual(len(all_["hits"]), 2)
        by_style = ds_refs.find_refs(style="奶油风", ds_root=self.ds)
        self.assertEqual(len(by_style["hits"]), 1)
        self.assertIn("r1", by_style["hits"][0])
        by_space = ds_refs.find_refs(space="主卧", ds_root=self.ds)
        self.assertEqual(len(by_space["hits"]), 1)
        by_proj = ds_refs.find_refs(project="翡翠湾-1801", ds_root=self.ds)
        self.assertEqual(len(by_proj["hits"]), 1)
        self.assertIn("r2", by_proj["hits"][0])
        by_kw = ds_refs.find_refs(keyword="洞洞板", ds_root=self.ds)
        self.assertEqual(len(by_kw["hits"]), 1)
        none = ds_refs.find_refs(style="法式", ds_root=self.ds)
        self.assertEqual(none["hits"], [])

    # ⑧ link:正常+去重+锚定+不存在拒
    def test_08_link(self):
        self._add()
        r = ds_refs.link_ref("r1", "翡翠湾-1801", ds_root=self.ds, today=TODAY)
        self.assertTrue(r.get("ok"), msg=str(r))
        self.assertIn("用于:翡翠湾-1801", _read(self.index))
        r2 = ds_refs.link_ref("r1", "翡翠湾-1801", ds_root=self.ds, today=TODAY)
        self.assertTrue(r2.get("ok"))
        self.assertEqual(_read(self.index).count("翡翠湾-1801"), 1)  # 去重
        r3 = ds_refs.link_ref("r99", "翡翠湾-1801", ds_root=self.ds, today=TODAY)
        self.assertEqual(r3.get("error"), "ref_not_found")
        r4 = ds_refs.link_ref("r1", "不存在的项目", ds_root=self.ds, today=TODAY)
        self.assertEqual(r4.get("error"), "project_not_found")

    # ⑧b r2 锚定不误伤 r12
    def test_08b_anchor(self):
        for i in range(12):  # r1..r12
            self._add()
        r = ds_refs.link_ref("r2", "翡翠湾-1801", ds_root=self.ds, today=TODAY)
        self.assertTrue(r.get("ok"))
        lines = self._entries()
        hit = [ln for ln in lines if "[r2]" in ln]
        others = [ln for ln in lines if "[r12]" in ln]
        self.assertIn("翡翠湾-1801", hit[0])
        self.assertNotIn("翡翠湾-1801", others[0])

    # ⑨ 不删行(精确计数 + 原有条目锚定仍在:替换行也算删)
    def test_09_no_deletion(self):
        self._add()
        n0 = len(self._entries())
        self._add(file="refs/侘寂风/主卧/b.jpg", style="侘寂风", space="主卧")
        self.assertEqual(len(self._entries()), n0 + 1)
        ds_refs.link_ref("r1", "翡翠湾-1801", ds_root=self.ds, today=TODAY)
        entries = self._entries()
        self.assertEqual(len(entries), n0 + 1)
        ids = [ln.split("]")[0] + "]" for ln in entries]
        self.assertEqual(ids, ["- [r1]", "- [r2]"])  # 原条目都在、顺序不变

    # ⑩ 多值标签(逗号分隔)
    def test_10_multi_space(self):
        r = self._add(space="客厅,餐厅")
        self.assertTrue(r.get("ok"), msg=str(r))
        by_dining = ds_refs.find_refs(space="餐厅", ds_root=self.ds)
        self.assertEqual(len(by_dining["hits"]), 1)
        r2 = self._add(space="客厅,太空舱")  # 多值里混词表外 → 整体拒
        self.assertEqual(r2.get("error"), "space_unknown")

    # ⑪ 路径存储统一 / 分隔符(Windows 互通)
    def test_11_path_sep(self):
        r = self._add(file=os.path.join("refs", "奶油风", "客厅", "a.jpg"))
        self.assertTrue(r.get("ok"))
        self.assertIn("文件:refs/奶油风/客厅/a.jpg", _read(self.index))
        self.assertNotIn("\\", self._entries()[0])

    # ⑬ 边界(submimo F4 补):空索引 find、非法 ref_id、多值风格、全角逗号
    def test_13_edges(self):
        r = ds_refs.find_refs(style="奶油风", ds_root=self.ds)  # 索引未建
        self.assertEqual(r["hits"], [])
        for bad in ("", "abc", "r0", "R1"):
            rr = ds_refs.link_ref(bad, "翡翠湾-1801", ds_root=self.ds, today=TODAY)
            self.assertEqual(rr.get("error"), "ref_not_found", msg=bad)
        r2 = self._add(style="奶油风,侘寂风")  # 多值风格
        self.assertTrue(r2.get("ok"), msg=str(r2))
        self.assertEqual(len(ds_refs.find_refs(style="侘寂风", ds_root=self.ds)["hits"]), 1)
        r3 = self._add(space="客厅，餐厅")  # 全角逗号
        self.assertTrue(r3.get("ok"), msg=str(r3))
        self.assertEqual(len(ds_refs.find_refs(space="餐厅", ds_root=self.ds)["hits"]), 1)

    # ⑧c M3(07-13 盲评):link_ref 的项目存在性检查走 _resolve/within,不给 `../` 逃逸。
    #    裸 join 时 `../index` 会命中 ds_root/index.md(PKB 里真存在)→ 被收进"用于:"段。
    def test_08c_link_project_traversal_rejected(self):
        self._add()
        # ds_root 下真放一个 index.md(PKB 常态),证明逃逸目标存在也不给绑
        with open(os.path.join(self.ds, "index.md"), "w", encoding="utf-8") as fh:
            fh.write("# 全局索引\n")
        r = ds_refs.link_ref("r1", "../index", ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "project_not_found")
        self.assertNotIn("../index", _read(self.index))

    # ⑫ MCP 表面恰好这 5 个工具(venv 有 mcp 才跑)
    #   2026-08-02 更正:原断言写死 4,而 update_ref_tool 在 3d70b6d 就作为第 5 个
    #   工具挂上了(skills/refs/SKILL.md 列为 #5,是有意的),这条从那时起一直红着。
    #   顺手改成断言**名字集合**:比数个数严,漏挂/改名/多挂都能抓到。
    def test_12_mcp_surface(self):
        try:
            import asyncio
            server = ds_refs._build_server(self.ds)
        except ImportError:
            self.skipTest("mcp not installed")
        tools = asyncio.run(server.list_tools())
        self.assertEqual({t.name for t in tools}, {
            "add_ref_tool", "find_refs_tool", "link_ref_tool",
            "add_style_tool", "update_ref_tool",
        })


class InjectionOracle(unittest.TestCase):
    """字段注入面(2026-07-03 全库盲评 #2 后落的铁律 oracle):
    source/note 带换行 = 伪造索引行;带 `|` 或字面 `用于:` = 劫持字段解析。"""

    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dsrefs-")
        self.img = os.path.join(self.ds, "refs", "奶油风", "客厅", "a.jpg")
        _touch(self.img)
        proj = os.path.join(self.ds, "projects", "翡翠湾-1801.md")
        os.makedirs(os.path.dirname(proj), exist_ok=True)
        with open(proj, "w", encoding="utf-8") as fh:
            fh.write("# 翡翠湾-1801\n\n## 变更记录\n\n---\n最后更新: 2026-06-20\n")
        self.index = os.path.join(self.ds, "refs-index.md")

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def _add(self, source="小红书", note=""):
        return ds_refs.add_ref("refs/奶油风/客厅/a.jpg", "奶油风", "客厅",
                               source, note, ds_root=self.ds, today=TODAY)

    def _entries(self):
        return [ln for ln in _read(self.index).split("\n")
                if ds_refs._REF_RE.match(ln)]

    # ⑮ note 换行注入被折叠:伪造不出第二条索引行,编号不被顶跳
    def test_15_newline_injection_folded(self):
        r = self._add(note="真备注\n- [r50] 奶油风|客厅 | 来源:x | 文件:refs/伪 | 用于: | 备注:伪")
        self.assertTrue(r.get("ok"), msg=str(r))
        self.assertEqual(r["ref_id"], "r1")
        self.assertEqual(len(self._entries()), 1)  # 恰好一条,没有伪造行
        r2 = self._add()
        self.assertEqual(r2["ref_id"], "r2")  # 不被伪造的 r50 顶跳

    # ⑯ source 里的字面"用于:"劫持不了字段:查询不假命中,link 写的是真字段
    def test_16_literal_used_field_not_hijacked(self):
        r = self._add(source="用于:翡翠湾-1801")
        self.assertTrue(r.get("ok"), msg=str(r))
        # 劫持成功的话这里会假命中
        hits = ds_refs.find_refs(project="翡翠湾-1801", ds_root=self.ds)
        self.assertEqual(hits["count"], 0)
        # link 写进真"用于:"字段,之后才可检索到
        lr = ds_refs.link_ref("r1", "翡翠湾-1801", ds_root=self.ds, today=TODAY)
        self.assertTrue(lr.get("ok"), msg=str(lr))
        hits2 = ds_refs.find_refs(project="翡翠湾-1801", ds_root=self.ds)
        self.assertEqual(hits2["count"], 1)

    # ⑰ source/note 里的竖线被换成 /:段分隔符不可注入
    def test_17_pipe_banned_in_fields(self):
        r = self._add(source="a|b", note="c | 用于:翡翠湾-1801")
        self.assertTrue(r.get("ok"), msg=str(r))
        line = self._entries()[0]
        self.assertIn("来源:a/b", line)
        self.assertEqual(len(line.split(" | ")), 5)  # 段数恒为 5,注不进第 6 段
        hits = ds_refs.find_refs(project="翡翠湾-1801", ds_root=self.ds)
        self.assertEqual(hits["count"], 0)

    # ⑲ link_ref 的 project 名带换行/竖线 → 折叠后对不上真实文件,安全拒绝
    def test_19_link_ref_project_sanitized(self):
        self._add()
        r = ds_refs.link_ref("r1", "翡翠湾-1801\n- [r50] 伪造", ds_root=self.ds,
                             today=TODAY)
        self.assertEqual(r.get("error"), "project_not_found")
        self.assertEqual(len(self._entries()), 1)
        self.assertNotIn("\n- [r50]", _read(self.index))

    # ⑱ add_style 拒换行:一次调用注入不了多个词表项
    def test_18_add_style_rejects_newline(self):
        r = ds_refs.add_style("风A\n- 风B", ds_root=self.ds)
        self.assertEqual(r.get("error"), "bad_style")
        self.assertNotIn("风A", ds_refs._load_styles(self.ds))


if __name__ == "__main__":
    unittest.main(verbosity=2)
