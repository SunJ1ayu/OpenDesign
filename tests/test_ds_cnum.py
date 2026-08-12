#!/usr/bin/env python3
"""变更号归一化的 oracle — track opendesign-cnum-zeropad(主 agent 拥有,不交执行腿)。

问的是一件事:**变更号是个数,读侧和写侧必须给出同一个答案。**
读侧一直是 `int("03") == 3`,写侧却把它当字符串拼进正则(`C{num}\\b`)⇒
业主手写的 `- [待确认] C03 …` / `- C03 备注:x` 在界面上读得到、却写不动。

跑法:  python3 tests/test_ds_cnum.py
不需要 nanobot / mcp SDK / 网络 —— 只测纯 Python 核心。

命名:A* = 三个复现形状(修之前必红);N* = 不许误伤(修之前就绿,防的是修过头)。
"""
import os
import sys
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # design-studio/
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_todo   # noqa: E402  读侧(本单不动它,N5 钉住)
import ds_tools  # noqa: E402  写侧(本单改的就是它的定位口径)

TODAY = "2026-08-12"
SLUG = "张三家"

HEAD = """# 张三家

- 业主: [[张三]]
- 阶段: 方案深化

## 变更记录
"""
TAIL = """
## 沟通日志
- 2026-08-01 微信:太太提改推拉门

---
最后更新: 2026-08-01
"""


def _write_project(ds_root, change_lines, history_lines=()):
    """造一份档案。history_lines 非空时补一个 `## 变更历史` 段(手写档案的形状)。"""
    projdir = os.path.join(ds_root, "projects")
    os.makedirs(projdir, exist_ok=True)
    body = HEAD + "\n".join(change_lines) + "\n"
    if history_lines:
        body += "\n## 变更历史\n" + "\n".join(history_lines) + "\n"
    body += TAIL
    path = os.path.join(projdir, f"{SLUG}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return path


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _note_lines(text):
    """档案里所有备注行(不管写成 C3 还是 C03)—— 归一化做没做到位,看这个列表的长度。

    半角/全角冒号两种都要数:读侧 `HISTORY_NOTE_RE` 收两种,只数半角的话,
    一行全角冒号的重复备注会从这个列表里溜掉 ⇒ 判据自己造假绿。
    """
    return [ln for ln in text.split("\n") if " 备注:" in ln or " 备注：" in ln]


class CnumZeroPadBase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="ds_cnum_")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)


class NoteAnchor(CnumZeroPadBase):
    """A1/A2:主变更行是规范的 C3,业主手写的**备注行**带了前导零。"""

    CHANGE = "- [待确认] C3 2026-08-01 客厅刷白"
    OLD_NOTE = "- C03 备注:老备注"

    def test_a1_upsert_normalizes_zero_padded_note(self):
        """改备注:档案里**只剩一行**备注,且是新值。

        现状(红):写侧 `^- C3 备注` 匹配不到 `- C03 备注`,于是**另起一行**追加,
        档案里同一条变更留下两行备注 —— 0.83.0 刚立的"归一重复行"对它整个失效。
        """
        path = _write_project(self.root, [self.CHANGE], [self.OLD_NOTE])
        r = ds_tools.edit_change(SLUG, 3, note="新备注", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"改备注不该失败:{r}")
        text = _read(path)
        notes = _note_lines(text)
        self.assertEqual(len(notes), 1,
                         f"同一条变更只该有一行备注,现在有 {len(notes)} 行:{notes}")
        self.assertEqual(notes[0], "- C3 备注:新备注",
                         "命中的旧行要被写回规范形式(不带前导零)")
        self.assertEqual(ds_todo.parse_history(text)[3]["note"], "新备注",
                         "读侧读到的必须是新值")

    def test_a1b_full_width_colon_note_also_normalized(self):
        """手写档案还可能用**全角冒号**(读侧收两种)。前导零 + 全角冒号同时出现时,
        写侧一样要认得它、并归一成一行半角。"""
        path = _write_project(self.root, [self.CHANGE], ["- C03 备注：老备注"])
        r = ds_tools.edit_change(SLUG, 3, note="新备注", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"改备注不该失败:{r}")
        self.assertEqual(_note_lines(_read(path)), ["- C3 备注:新备注"],
                         "全角冒号的旧行也要被归一掉,不许留成第二行")

    def test_a2_clear_removes_zero_padded_note(self):
        """清空备注:那行**真的没了**,而且接口说自己改了 note。

        现状(红):`_delete_note` 一行都没删,却仍返回 ok ⇒ 业主看到的是
        「我删了它还在」—— 与 0.83.0 刚修好的那个 bug 同一个症状,只是入口不同。
        """
        path = _write_project(self.root, [self.CHANGE], [self.OLD_NOTE])
        r = ds_tools.edit_change(SLUG, 3, note="", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"清空备注不该失败:{r}")
        text = _read(path)
        self.assertEqual(_note_lines(text), [], "清空之后档案里不该还留着备注行")
        self.assertIn("note", r.get("changed_fields", []),
                      f"真删掉了就得如实说自己改了 note,不许静默 no-op:{r}")
        self.assertIsNone(ds_todo.parse_history(text).get(3, {}).get("note"),
                          "读侧不该再读到老备注")


class ChangeLineAnchor(CnumZeroPadBase):
    """A3:业主把**主变更行**手写成了 C03 —— 界面显示成 C3,四个写口却全都够不着。"""

    CHANGE = "- [待确认] C03 2026-08-01 客厅刷白"

    def test_a3_status_edit_reaches_zero_padded_change(self):
        path = _write_project(self.root, [self.CHANGE])
        r = ds_tools.edit_change(SLUG, 3, new_status="进行中", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"改状态够不着 C03:{r}")
        self.assertIn("- [进行中] C03 2026-08-01 客厅刷白", _read(path))

    def test_a3_text_edit_reaches_zero_padded_change(self):
        path = _write_project(self.root, [self.CHANGE])
        r = ds_tools.edit_change(SLUG, 3, new_text="客厅刷米白", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"改正文够不着 C03:{r}")
        self.assertIn("客厅刷米白", _read(path))

    def test_a3_note_reaches_zero_padded_change(self):
        path = _write_project(self.root, [self.CHANGE])
        r = ds_tools.edit_change(SLUG, 3, note="记一笔", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"加备注够不着 C03:{r}")
        self.assertEqual(_note_lines(_read(path)), ["- C3 备注:记一笔"],
                         "新写的备注行一律用规范形式")

    def test_a3_due_date_reaches_zero_padded_change(self):
        path = _write_project(self.root, [self.CHANGE])
        r = ds_tools.set_due_date(SLUG, 3, "2026-09-01", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"设截止日够不着 C03:{r}")
        self.assertIn("⏳2026-09-01", _read(path))

    def test_a3_set_change_status_reaches_zero_padded_change(self):
        """另一个写口(MCP 那条老路径),口径必须和 edit_change 一致。"""
        path = _write_project(self.root, [self.CHANGE])
        r = ds_tools.set_change_status(SLUG, "C3", "已完成", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"set_change_status 够不着 C03:{r}")
        self.assertIn("- [已完成] C03", _read(path))

    def test_a4_ambiguous_when_both_forms_present(self):
        """`C3` 与 `C03` 并存(手抄重号)⇒ 拒写并说清是歧义,档案一个字节不许动。"""
        path = _write_project(self.root, [
            "- [待确认] C3 2026-08-01 客厅刷白",
            "- [待确认] C03 2026-08-02 主卧换灯",
        ])
        before = _read(path)
        r = ds_tools.edit_change(SLUG, 3, new_status="进行中", ds_root=self.root, today=TODAY)
        self.assertEqual(r.get("error"), "ambiguous_change", f"两行同号该判歧义:{r}")
        self.assertEqual(_read(path), before, "判了歧义就不许写")


class NoCollateralDamage(CnumZeroPadBase):
    """N*:放宽匹配之后不许误伤。这几条**修之前就是绿的** —— 它们防的是修过头。"""

    def test_n1_does_not_touch_c13(self):
        _write_project(self.root, ["- [待确认] C13 2026-08-01 客厅刷白"])
        r = ds_tools.edit_change(SLUG, 3, new_status="进行中", ds_root=self.root, today=TODAY)
        self.assertEqual(r.get("error"), "change_not_found", f"C3 不该够到 C13:{r}")

    def test_n2_does_not_touch_c30(self):
        _write_project(self.root, ["- [待确认] C30 2026-08-01 客厅刷白"])
        r = ds_tools.edit_change(SLUG, 3, new_status="进行中", ds_root=self.root, today=TODAY)
        self.assertEqual(r.get("error"), "change_not_found", f"C3 不该够到 C30:{r}")

    def test_n2b_note_anchor_does_not_touch_c30(self):
        """备注锚点同样不许越界(它有自己的一份正则,得单独问一枪)。"""
        path = _write_project(self.root, ["- [待确认] C3 2026-08-01 客厅刷白"],
                              ["- C30 备注:别人的备注"])
        ds_tools.edit_change(SLUG, 3, note="", ds_root=self.root, today=TODAY)
        self.assertIn("- C30 备注:别人的备注", _read(path), "清 C3 的备注不许删掉 C30 的")

    def test_n3_reaches_c003(self):
        """前导零不止一个也得认(`0*`,不是 `0?`)。"""
        path = _write_project(self.root, ["- [待确认] C003 2026-08-01 客厅刷白"])
        r = ds_tools.edit_change(SLUG, 3, new_status="进行中", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"C003 也是 3 号:{r}")
        self.assertIn("- [进行中] C003", _read(path))

    def test_n4_change_line_bytes_preserved(self):
        """BLOCK-2 铁律:改状态时,状态词以外的字节逐字节不变 ——
        手写的 `C03` 不许被"顺手规范化"成 `C3`(那是在改业主的档案)。"""
        line = "- [待确认] C03 2026-08-01 【客厅】客厅刷白 ⏳2026-09-01"
        path = _write_project(self.root, [line])
        ds_tools.edit_change(SLUG, 3, new_status="进行中", ds_root=self.root, today=TODAY)
        self.assertIn(line.replace("待确认", "进行中"), _read(path),
                      "除状态词外整行必须逐字节不变")

    def test_n5_read_side_unchanged(self):
        """读侧本来就是对的那一半,这一单不许动它。"""
        self.assertEqual(ds_todo.parse_change("- [待确认] C03 2026-08-01 客厅刷白")["cnum"], 3)
        self.assertEqual(ds_todo.parse_change("- [待确认] C3 2026-08-01 客厅刷白")["cnum"], 3)
        h = ds_todo.parse_history("## 变更历史\n- C03 备注:老备注\n")
        self.assertEqual(h[3]["note"], "老备注")


if __name__ == "__main__":
    unittest.main(verbosity=2)
