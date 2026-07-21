#!/usr/bin/env python3
"""ds_refs.update_ref 的 oracle — track opendesign-stage-history §8(新核心写工具)。

跑法:  python3 tests/test_ds_refs_update.py
零依赖零网络。

契约(design.md §8):
  update_ref(ref_id, style=None, space=None, note=None, ds_root=..., today=None)
  - ref_id 必须 r<n>;定位锚 `^- \\[r<num>\\]\\s`(r2 不误伤 r12/r20)
  - 三字段全 None → no_fields(不接受"只 bump 页脚"的假写)
  - style/space:逗号(含全角)拆 → 逐项过词表(_load_styles / SPACES);
    空列表或词表外 → style_unknown / space_unknown(带 vocab),**不自动建词**
  - note:sanitize_field(ban_pipe=True);空串 = 清空备注(与"不传=不动"区分)
  - **只重写头段(`- [rN] 风格|空间`)与 `备注:` 段;来源/文件/用于三段逐字节不变**
  - 缺 `备注:` 段的畸形行 → malformed_entry(不猜不补)
  - locked_rw 全程 + 末尾 bump_last_updated

铁律来源:PKB 写操作一律过核心(前端/ds_web 永不直改 markdown);词表是单一真相源,
建词有 add_style 专属工具,本函数不代劳。
"""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # design-studio/
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_refs  # noqa: E402

TODAY = "2026-07-21"
LATER = "2026-07-22"


def _touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"\xff\xd8fakejpg")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class UpdateRefBase(unittest.TestCase):
    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dsrefsupd-")
        _touch(os.path.join(self.ds, "refs", "奶油风", "客厅", "a.jpg"))
        _touch(os.path.join(self.ds, "refs", "侘寂风", "主卧", "b.jpg"))
        self.index = os.path.join(self.ds, "refs-index.md")
        # r1 / r2 两条:r2 存在是为了钉住"改 r1 不碰 r2"
        self.r1 = ds_refs.add_ref("refs/奶油风/客厅/a.jpg", "奶油风", "客厅",
                                  "小红书", "弧形吊顶", ds_root=self.ds, today=TODAY)
        self.r2 = ds_refs.add_ref("refs/侘寂风/主卧/b.jpg", "侘寂风", "主卧",
                                  "Pinterest", "原木床头", ds_root=self.ds, today=TODAY)
        self.assertTrue(self.r1.get("ok") and self.r2.get("ok"), "夹具:两条索引都应建成")

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def _line(self, ref_id):
        want = f"- [{ref_id}] "
        for ln in _read(self.index).split("\n"):
            if ln.startswith(want):
                return ln
        return None

    def _seg(self, ref_id, prefix):
        """取某条索引行里以 prefix 开头的那一段的值(与核心同分段口径)。"""
        for seg in self._line(ref_id).split(ds_refs._SEG_SEP):
            if seg.startswith(prefix):
                return seg[len(prefix):]
        return None

    def _parsed(self, ref_id):
        return ds_refs.parse_ref_line(self._line(ref_id))


class UpdateRefHappy(UpdateRefBase):
    def test_note_only(self):
        r = ds_refs.update_ref("r1", note="改成平顶", ds_root=self.ds, today=LATER)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual("r1", r.get("ref_id"))
        self.assertEqual("改成平顶", self._parsed("r1")["note"])
        # 标签没传 → 一个字都不许动
        self.assertEqual(["奶油风"], self._parsed("r1")["style"])
        self.assertEqual(["客厅"], self._parsed("r1")["space"])

    def test_style_only(self):
        ds_refs.add_style("侘寂风", ds_root=self.ds)
        r = ds_refs.update_ref("r1", style="侘寂风", ds_root=self.ds, today=LATER)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(["侘寂风"], self._parsed("r1")["style"])
        self.assertEqual("弧形吊顶", self._parsed("r1")["note"], "备注没传就不该动")

    def test_space_multi_and_fullwidth_comma(self):
        r = ds_refs.update_ref("r1", space="客厅，餐厅", ds_root=self.ds, today=LATER)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(["客厅", "餐厅"], self._parsed("r1")["space"])

    def test_all_three_at_once(self):
        ds_refs.add_style("侘寂风", ds_root=self.ds)
        r = ds_refs.update_ref("r1", style="侘寂风,奶油风", space="主卧",
                               note="床头背景", ds_root=self.ds, today=LATER)
        self.assertTrue(r.get("ok"), r)
        p = self._parsed("r1")
        self.assertEqual(["侘寂风", "奶油风"], p["style"])
        self.assertEqual(["主卧"], p["space"])
        self.assertEqual("床头背景", p["note"])

    def test_empty_note_clears(self):
        r = ds_refs.update_ref("r1", note="", ds_root=self.ds, today=LATER)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual("", self._parsed("r1")["note"], "空串=清空备注")
        self.assertIn("备注:", self._line("r1"), "清空是留空段,不是删段")

    def test_returns_new_line(self):
        r = ds_refs.update_ref("r1", note="新备注", ds_root=self.ds, today=LATER)
        self.assertEqual(self._line("r1"), r.get("line"), "回传的应是落盘后的整行")

    def test_bumps_last_updated(self):
        ds_refs.update_ref("r1", note="新备注", ds_root=self.ds, today=LATER)
        self.assertIn(LATER, _read(self.index), "页脚最后更新应 bump 到当天")


class UpdateRefPreservesOtherSegments(UpdateRefBase):
    """本函数的核心不变量:没点名的段一个字节都不许动。"""

    def test_source_file_used_untouched(self):
        # 让「用于:」段非空(link_ref 是它的专属工具),才谈得上"不许被 update 动"
        proj = os.path.join(self.ds, "projects", "翡翠湾-1801.md")
        os.makedirs(os.path.dirname(proj), exist_ok=True)
        with open(proj, "w", encoding="utf-8") as fh:
            fh.write("# 翡翠湾-1801\n\n## 变更记录\n\n---\n最后更新: 2026-06-20\n")
        self.assertTrue(ds_refs.link_ref("r1", "翡翠湾-1801", ds_root=self.ds,
                                         today=TODAY).get("ok"), "夹具:link 应成功")
        before_source = self._seg("r1", "来源:")
        before_file = self._seg("r1", "文件:")
        before_used = self._seg("r1", "用于:")
        ds_refs.add_style("侘寂风", ds_root=self.ds)
        ds_refs.update_ref("r1", style="侘寂风", space="主卧", note="全改一遍",
                           ds_root=self.ds, today=LATER)
        self.assertEqual(before_source, self._seg("r1", "来源:"))
        self.assertEqual(before_file, self._seg("r1", "文件:"))
        self.assertEqual(before_used, self._seg("r1", "用于:"))

    def test_other_entry_untouched(self):
        before_r2 = self._line("r2")
        ds_refs.update_ref("r1", note="只改 r1", ds_root=self.ds, today=LATER)
        self.assertEqual(before_r2, self._line("r2"), "改 r1 不许碰 r2")

    def test_segment_order_stable(self):
        before = self._line("r1").split(ds_refs._SEG_SEP)
        ds_refs.update_ref("r1", note="换个备注", ds_root=self.ds, today=LATER)
        after = self._line("r1").split(ds_refs._SEG_SEP)
        self.assertEqual([s.split(":", 1)[0] for s in before],
                         [s.split(":", 1)[0] for s in after], "段序不许变")

    def test_r1_anchor_does_not_hit_r12(self):
        """改 r1 不得误伤 r12(锚定整体 `[rN]`,同 link_ref 先例)。"""
        r12 = ("- [r12] 奶油风|餐厅 | 来源:站酷 | "
               "文件:refs/奶油风/客厅/a.jpg | 用于: | 备注:第12条")
        text = _read(self.index)
        with open(self.index, "w", encoding="utf-8") as fh:
            fh.write(text.replace(self._line("r2"), self._line("r2") + "\n" + r12, 1))
        self.assertEqual(r12, self._line("r12"), "夹具:r12 应写进索引")
        ds_refs.update_ref("r1", note="只改 r1", ds_root=self.ds, today=LATER)
        self.assertEqual(r12, self._line("r12"), "r12 必须逐字节不变")


class UpdateRefRejects(UpdateRefBase):
    def test_no_fields(self):
        before = _read(self.index)
        r = ds_refs.update_ref("r1", ds_root=self.ds, today=LATER)
        self.assertEqual("no_fields", r.get("error"), r)
        self.assertEqual(before, _read(self.index), "拒绝路径零落盘")

    def test_bad_ref_id(self):
        for bad in ("", "  ", "1", "R1", "r", "rr1", "r1x", "../r1", None):
            with self.subTest(bad=bad):
                before = _read(self.index)
                r = ds_refs.update_ref(bad, note="x", ds_root=self.ds, today=LATER)
                self.assertEqual("ref_not_found", r.get("error"), r)
                self.assertEqual(before, _read(self.index))

    def test_missing_ref(self):
        before = _read(self.index)
        r = ds_refs.update_ref("r999", note="x", ds_root=self.ds, today=LATER)
        self.assertEqual("ref_not_found", r.get("error"), r)
        self.assertEqual(before, _read(self.index))

    def test_style_unknown(self):
        before = _read(self.index)
        r = ds_refs.update_ref("r1", style="赛博朋克风", ds_root=self.ds, today=LATER)
        self.assertEqual("style_unknown", r.get("error"), r)
        self.assertIn("vocab", r, "拒的时候要把词表回给调用方")
        self.assertEqual(before, _read(self.index), "不自动建词、零落盘")

    def test_space_unknown(self):
        before = _read(self.index)
        r = ds_refs.update_ref("r1", space="停机坪", ds_root=self.ds, today=LATER)
        self.assertEqual("space_unknown", r.get("error"), r)
        self.assertIn("vocab", r)
        self.assertEqual(before, _read(self.index))

    def test_partial_unknown_rejects_whole(self):
        """多值里只要有一个不在词表,整次调用拒 —— 不许"过滤掉坏的写好的"。"""
        before = _read(self.index)
        r = ds_refs.update_ref("r1", space="客厅,停机坪", ds_root=self.ds, today=LATER)
        self.assertEqual("space_unknown", r.get("error"), r)
        self.assertEqual(before, _read(self.index))

    def test_empty_tag_lists_rejected(self):
        """标签不许清空(索引行会退化成无检索维度的死条目);备注才允许清空。"""
        for kwargs in ({"style": ""}, {"style": " , "}, {"space": ""}, {"space": "，"}):
            with self.subTest(kwargs=kwargs):
                before = _read(self.index)
                r = ds_refs.update_ref("r1", ds_root=self.ds, today=LATER, **kwargs)
                self.assertIn(r.get("error"), ("style_unknown", "space_unknown"), r)
                self.assertEqual(before, _read(self.index))

    def test_note_pipe_and_newline_sanitized(self):
        """`|` 是分段符、换行是行界 —— 二者都不许进索引行。"""
        r = ds_refs.update_ref("r1", note="前 | 后\n第二行", ds_root=self.ds, today=LATER)
        self.assertTrue(r.get("ok"), r)
        line = self._line("r1")
        self.assertEqual(5, len(line.split(ds_refs._SEG_SEP)), "段数不许被备注撑开")
        self.assertNotIn("\n", line)
        self.assertIsNotNone(ds_refs.parse_ref_line(line), "改完仍要能被解析回来")
        self.assertEqual(1, len([ln for ln in _read(self.index).split("\n")
                                 if ln.startswith("- [r1] ")]), "不许裂成两行")

    def test_style_injection_via_pipe_rejected(self):
        """`奶油风|客厅` 这类想撑开头段的值:拆词后不在词表 → 拒。"""
        before = _read(self.index)
        r = ds_refs.update_ref("r1", style="奶油风|客厅", ds_root=self.ds, today=LATER)
        self.assertEqual("style_unknown", r.get("error"), r)
        self.assertEqual(before, _read(self.index))

    def test_malformed_entry_missing_note_segment(self):
        """手写的畸形行(没有 `备注:` 段)→ malformed_entry,不猜不补。"""
        text = _read(self.index).replace(
            " | 备注:弧形吊顶", "", 1)
        with open(self.index, "w", encoding="utf-8") as fh:
            fh.write(text)
        before = _read(self.index)
        r = ds_refs.update_ref("r1", note="补一个", ds_root=self.ds, today=LATER)
        self.assertEqual("malformed_entry", r.get("error"), r)
        self.assertEqual(before, _read(self.index))

    def test_ambiguous_ref(self):
        """索引里手写重复了同一个 id → ambiguous_ref,零落盘(同 link_ref 口径)。"""
        line = self._line("r1")
        text = _read(self.index).replace(line, line + "\n" + line, 1)
        with open(self.index, "w", encoding="utf-8") as fh:
            fh.write(text)
        before = _read(self.index)
        r = ds_refs.update_ref("r1", note="改不了", ds_root=self.ds, today=LATER)
        self.assertEqual("ambiguous_ref", r.get("error"), r)
        self.assertEqual(before, _read(self.index))

    def test_no_index_file(self):
        os.remove(self.index)
        r = ds_refs.update_ref("r1", note="x", ds_root=self.ds, today=LATER)
        self.assertEqual("ref_not_found", r.get("error"), r)
        self.assertFalse(os.path.exists(self.index), "读不到索引不许顺手建一个")


class UpdateRefWiring(UpdateRefBase):
    def test_mcp_tool_registered(self):
        """MCP 工具与核心同源(聊天里也能改),缺 mcp 包时跳过。"""
        try:
            server = ds_refs._build_server(self.ds)
        except ImportError:
            self.skipTest("mcp 未安装")
        names = set()
        tools = getattr(server, "_tool_manager", None)
        if tools is not None and hasattr(tools, "_tools"):
            names = set(tools._tools)
        self.assertIn("update_ref_tool", names,
                      f"update_ref_tool 应注册进 MCP;现有:{sorted(names)}")

    def test_parse_roundtrip_after_update(self):
        ds_refs.add_style("侘寂风", ds_root=self.ds)
        ds_refs.update_ref("r1", style="侘寂风", space="主卧,客厅", note="回环",
                           ds_root=self.ds, today=LATER)
        hits = ds_refs.find_refs(style="侘寂风", ds_root=self.ds).get("hits", [])
        self.assertEqual(1, len(hits), "改完的行必须能被 find_refs 按新标签检索到")
        p = ds_refs.parse_ref_line(hits[0])
        self.assertEqual(["主卧", "客厅"], p["space"])
        self.assertEqual("回环", p["note"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
