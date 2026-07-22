#!/usr/bin/env python3
"""track opendesign-todo-duedate oracle(主 agent 拥有,off-limits 给执行腿)。

契约:每条变更可加行尾截止日 token `⏳YYYY-MM-DD`(design.md)。核心 = 共享
helper ds_common.split_due / format_due_suffix,读侧 ds_todo.parse_change 透出 due,
写侧 ds_tools.set_due_date 设/清(保其余字节)+ edit_change 改正文保留截止日。

跑法:  python3 tests/test_ds_duedate.py
red-check:实现前 ds_common 无 split_due、ds_tools 无 set_due_date、parse_change 无 due → 整体红。
"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_common  # noqa: E402
import ds_todo    # noqa: E402
import ds_tools   # noqa: E402

TODAY = "2026-07-01"

HEAD = """# {slug}

- 业主: [[张三]]
- 阶段: 方案深化

## 变更记录
"""
TAIL = """
## 沟通日志

---
最后更新: 2026-06-20
"""


def _write_project(ds_root, slug, change_lines):
    projdir = os.path.join(ds_root, "projects")
    os.makedirs(projdir, exist_ok=True)
    body = HEAD.format(slug=slug) + "\n".join(change_lines) + TAIL
    path = os.path.join(projdir, f"{slug}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return path


def _line_for(path, num):
    with open(path, encoding="utf-8") as fh:
        for ln in fh.read().splitlines():
            m = ds_todo.CHANGE_RE.match(ln)
            if m and m.group(2) == str(num):
                return ln
    return None


# ── 1. 共享 helper ────────────────────────────────────────────────────────────
class TestSplitDue(unittest.TestCase):
    def test_no_due_returns_original(self):
        self.assertEqual(ds_common.split_due("玄关柜改高"), ("玄关柜改高", None))

    def test_trailing_due_split(self):
        self.assertEqual(ds_common.split_due("玄关柜改高 ⏳2026-07-31"),
                         ("玄关柜改高", "2026-07-31"))

    def test_due_only_anchored_at_end(self):
        # 正文中间的 ⏳日期 不当截止日(仅行尾)
        text = "参考 ⏳2026-01-01 那版的做法"
        self.assertEqual(ds_common.split_due(text), (text, None))

    def test_format_due_suffix(self):
        self.assertEqual(ds_common.format_due_suffix("2026-07-31"), " ⏳2026-07-31")
        self.assertEqual(ds_common.format_due_suffix(None), "")
        self.assertEqual(ds_common.format_due_suffix(""), "")

    def test_roundtrip(self):
        text, due = "玄关柜改高", "2026-07-31"
        line = text + ds_common.format_due_suffix(due)
        self.assertEqual(ds_common.split_due(line), (text, due))


# ── 2. 读侧 parse_change ──────────────────────────────────────────────────────
class TestParseChangeDue(unittest.TestCase):
    def test_due_extracted_text_clean(self):
        c = ds_todo.parse_change("- [待确认] C7 2026-07-15 【玄关】玄关柜改高 ⏳2026-07-31")
        self.assertEqual(c["due"], "2026-07-31")
        self.assertEqual(c["space"], "玄关")
        self.assertEqual(c["text"], "玄关柜改高")  # 不含 ⏳

    def test_no_due_is_none_text_unchanged(self):
        c = ds_todo.parse_change("- [待确认] C7 2026-07-15 【玄关】玄关柜改高")
        self.assertIsNone(c["due"])
        self.assertEqual(c["text"], "玄关柜改高")

    def test_due_without_space(self):
        c = ds_todo.parse_change("- [进行中] C3 2026-07-10 电视墙放样 ⏳2026-08-01")
        self.assertEqual(c["due"], "2026-08-01")
        self.assertIsNone(c["space"])
        self.assertEqual(c["text"], "电视墙放样")


# ── 3. 写侧 set_due_date ──────────────────────────────────────────────────────
class TestSetDueDate(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.path = _write_project(self.d, "翡翠湾-1801", [
            "- [待确认] C1 2026-07-15 【玄关】玄关柜改高",
            "- [进行中] C2 2026-07-10 电视墙放样",
        ])

    def tearDown(self):
        import shutil
        shutil.rmtree(self.d, ignore_errors=True)

    def test_set_preserves_all_other_bytes(self):
        r = ds_tools.set_due_date("翡翠湾-1801", 1, "2026-07-31", ds_root=self.d, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(_line_for(self.path, 1),
                         "- [待确认] C1 2026-07-15 【玄关】玄关柜改高 ⏳2026-07-31")

    def test_update_replaces_not_appends(self):
        ds_tools.set_due_date("翡翠湾-1801", 1, "2026-07-31", ds_root=self.d, today=TODAY)
        ds_tools.set_due_date("翡翠湾-1801", 1, "2026-08-15", ds_root=self.d, today=TODAY)
        self.assertEqual(_line_for(self.path, 1),
                         "- [待确认] C1 2026-07-15 【玄关】玄关柜改高 ⏳2026-08-15")

    def test_clear_with_none_and_empty(self):
        ds_tools.set_due_date("翡翠湾-1801", 1, "2026-07-31", ds_root=self.d, today=TODAY)
        ds_tools.set_due_date("翡翠湾-1801", 1, None, ds_root=self.d, today=TODAY)
        self.assertEqual(_line_for(self.path, 1),
                         "- [待确认] C1 2026-07-15 【玄关】玄关柜改高")
        ds_tools.set_due_date("翡翠湾-1801", 1, "2026-07-31", ds_root=self.d, today=TODAY)
        ds_tools.set_due_date("翡翠湾-1801", 1, "", ds_root=self.d, today=TODAY)
        self.assertEqual(_line_for(self.path, 1),
                         "- [待确认] C1 2026-07-15 【玄关】玄关柜改高")

    def test_invalid_due_rejected(self):
        r = ds_tools.set_due_date("翡翠湾-1801", 1, "下周五", ds_root=self.d, today=TODAY)
        self.assertEqual(r.get("error"), "invalid_due")
        r2 = ds_tools.set_due_date("翡翠湾-1801", 1, "2026-13-40", ds_root=self.d, today=TODAY)
        self.assertEqual(r2.get("error"), "invalid_due")

    def test_change_not_found(self):
        r = ds_tools.set_due_date("翡翠湾-1801", 99, "2026-07-31", ds_root=self.d, today=TODAY)
        self.assertEqual(r.get("error"), "change_not_found")

    def test_roundtrip_read_back(self):
        ds_tools.set_due_date("翡翠湾-1801", 2, "2026-08-01", ds_root=self.d, today=TODAY)
        c = ds_todo.parse_change(_line_for(self.path, 2))
        self.assertEqual(c["due"], "2026-08-01")
        self.assertEqual(c["text"], "电视墙放样")


# ── 4. edit_change 改正文保留截止日 ───────────────────────────────────────────
class TestEditChangePreservesDue(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.path = _write_project(self.d, "云山-2302", [
            "- [待确认] C1 2026-07-15 【玄关】玄关柜改高 ⏳2026-07-31",
        ])

    def tearDown(self):
        import shutil
        shutil.rmtree(self.d, ignore_errors=True)

    def test_edit_text_keeps_due(self):
        r = ds_tools.edit_change("云山-2302", 1, new_text="玄关柜改到 2.4 米",
                                 ds_root=self.d, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        line = _line_for(self.path, 1)
        c = ds_todo.parse_change(line)
        self.assertEqual(c["text"], "玄关柜改到 2.4 米")
        self.assertEqual(c["due"], "2026-07-31")  # 截止日未丢

    def test_history_original_excludes_due(self):
        ds_tools.edit_change("云山-2302", 1, new_text="玄关柜改到 2.4 米",
                             ds_root=self.d, today=TODAY)
        with open(self.path, encoding="utf-8") as fh:
            body = fh.read()
        # 历史留痕 `原:` 应是不含 ⏳ 的旧正文
        self.assertIn("原:玄关柜改高", body)
        self.assertNotIn("原:玄关柜改高 ⏳", body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
