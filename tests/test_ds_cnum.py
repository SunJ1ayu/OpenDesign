#!/usr/bin/env python3
"""变更号归一化的 oracle — track opendesign-cnum-zeropad(主 agent 拥有,不交执行腿)。

问的是一件事:**变更号是个数,读侧和写侧必须给出同一个答案。**
读侧一直是"捕获 `(\\d+)` 再 `int()`";写侧五处却把目标号码**拼进** pattern
(`C{num}\\b`)⇒ 业主手写的 `- [待确认] C03 …` / `- C03 备注:x` 在界面上读得到、却写不动。

跑法:  python3 tests/test_ds_cnum.py
不需要 nanobot / mcp SDK / 网络 —— 只测纯 Python 核心。

命名:A* = 复现形状(修之前必红);N* = 不许误伤 / 不许修过头。
A4/A5/N6/N7 是**派活前攻题**(gpt-5.6-sol 只读)打出来的,四条发现全部成立,
其中两条 HIGH 直接改了修法本身 —— 详见 tracks/opendesign-cnum-zeropad/design.md「五」。
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
FOOTER_DATE = "2026-08-01"

HEAD = """# 张三家

- 业主: [[张三]]
- 阶段: 方案深化

## 变更记录
"""
TAIL = f"""
## 沟通日志
- {FOOTER_DATE} 微信:太太提改推拉门

---
最后更新: {FOOTER_DATE}
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
    """档案里所有备注行(不管号码写成 C3 / C03 / C０３)—— 归一化做没做到位,看它的长度。

    半角/全角冒号两种都要数:读侧 `HISTORY_NOTE_RE` 收两种,只数半角的话,
    一行全角冒号的重复备注会从这个列表里溜掉 ⇒ 判据自己造假绿(首跑真踩过)。
    """
    return [ln for ln in text.split("\n") if " 备注:" in ln or " 备注：" in ln]


class CnumBase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="ds_cnum_")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════
# A 组:复现形状 —— 修之前必红
# ══════════════════════════════════════════════════════════════════════════

class NoteAnchor(CnumBase):
    """主变更行是规范的 C3,业主手写的**备注行**带了前导零。"""

    CHANGE = "- [待确认] C3 2026-08-01 客厅刷白"

    def test_a1_upsert_hits_zero_padded_note_and_keeps_its_bytes(self):
        """改备注:只剩一行、值是新的,**且那行的前缀字节没被动过**。

        现状(红):写侧 `^- C3 备注` 匹配不到 `- C03 备注`,于是另起一行追加 ⇒ 两行。
        前缀保留这一半是攻题 Q4 掰过来的:主变更行明明保字节,备注行没理由顺手规范化。
        """
        path = _write_project(self.root, [self.CHANGE], ["- C03 备注:老备注"])
        r = ds_tools.edit_change(SLUG, 3, note="新备注", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"改备注不该失败:{r}")
        notes = _note_lines(_read(path))
        self.assertEqual(notes, ["- C03 备注:新备注"],
                         "命中的那行只换值,前缀字节(含 C03)原样留着;且不许多出第二行")

    def test_a1b_full_width_colon_note(self):
        """手写档案还可能用**全角冒号**(读侧收两种),前缀同样保字节。"""
        path = _write_project(self.root, [self.CHANGE], ["- C03 备注：老备注"])
        r = ds_tools.edit_change(SLUG, 3, note="新备注", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"改备注不该失败:{r}")
        self.assertEqual(_note_lines(_read(path)), ["- C03 备注：新备注"],
                         "全角冒号那行也要被认出来、只换值,不许留成第二行")

    def test_a1c_mixed_duplicates_collapse_to_one(self):
        """脏数据归一:同一条变更的三种写法并存 ⇒ 改完只剩一行(0.83.0 那道归一化的本意)。"""
        path = _write_project(self.root, [self.CHANGE],
                              ["- C03 备注:第一次", "- C3 备注:第二次", "- C003 备注：第三次"])
        r = ds_tools.edit_change(SLUG, 3, note="最终备注", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"改备注不该失败:{r}")
        notes = _note_lines(_read(path))
        self.assertEqual(len(notes), 1, f"三行重复备注该归一成一行,现在:{notes}")
        self.assertTrue(notes[0].endswith("最终备注"), f"留下的那行得是新值:{notes}")
        self.assertEqual(ds_todo.parse_history(_read(path))[3]["note"], "最终备注")

    def test_a1d_mixed_duplicates_all_cleared(self):
        path = _write_project(self.root, [self.CHANGE],
                              ["- C03 备注:第一次", "- C3 备注:第二次", "- C003 备注：第三次"])
        ds_tools.edit_change(SLUG, 3, note="", ds_root=self.root, today=TODAY)
        self.assertEqual(_note_lines(_read(path)), [], "清空要把三行全带走,不能只删认得的那一行")

    def test_a2_clear_removes_zero_padded_note(self):
        """清空备注:那行**真的没了**,而且接口说自己改了 note。

        现状(红):`_delete_note` 一行都没删,却仍返回 ok ⇒ 业主看到的是
        「我删了它还在」—— 与 0.83.0 刚修好的那个 bug 同症状、不同入口。
        """
        path = _write_project(self.root, [self.CHANGE], ["- C03 备注:老备注"])
        r = ds_tools.edit_change(SLUG, 3, note="", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"清空备注不该失败:{r}")
        self.assertEqual(_note_lines(_read(path)), [], "清空之后档案里不该还留着备注行")
        self.assertIn("note", r.get("changed_fields", []),
                      f"真删掉了就得如实说自己改了 note,不许静默 no-op:{r}")
        self.assertIsNone(ds_todo.parse_history(_read(path)).get(3, {}).get("note"),
                          "读侧不该再读到老备注")


class ChangeLineAnchor(CnumBase):
    """业主把**主变更行**手写成了 C03 —— 界面显示成 C3,五个写口却全都够不着。"""

    CHANGE = "- [待确认] C03 2026-08-01 客厅刷白"

    def test_a3_status(self):
        path = _write_project(self.root, [self.CHANGE])
        r = ds_tools.edit_change(SLUG, 3, new_status="进行中", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"改状态够不着 C03:{r}")
        self.assertIn("- [进行中] C03 2026-08-01 客厅刷白", _read(path))

    def test_a3_text(self):
        path = _write_project(self.root, [self.CHANGE])
        r = ds_tools.edit_change(SLUG, 3, new_text="客厅刷米白", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"改正文够不着 C03:{r}")
        self.assertIn("客厅刷米白", _read(path))

    def test_a3_note(self):
        path = _write_project(self.root, [self.CHANGE])
        r = ds_tools.edit_change(SLUG, 3, note="记一笔", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"加备注够不着 C03:{r}")
        self.assertEqual(_note_lines(_read(path)), ["- C3 备注:记一笔"],
                         "**新建**的备注行用规范形式(保字节只针对已存在的行)")

    def test_a3_due_date(self):
        path = _write_project(self.root, [self.CHANGE])
        r = ds_tools.set_due_date(SLUG, 3, "2026-09-01", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"设截止日够不着 C03:{r}")
        self.assertIn("⏳2026-09-01", _read(path))

    def test_a3_set_change_status(self):
        """MCP 那条老路径(与删除按钮共用 `_rewrite_change_status`)。"""
        path = _write_project(self.root, [self.CHANGE])
        r = ds_tools.set_change_status(SLUG, "C3", "已完成", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"set_change_status 够不着 C03:{r}")
        self.assertIn("- [已完成] C03", _read(path))

    def test_a3_delete_change(self):
        """界面上的**删除按钮**(攻题发现 3:我原先的 scope 漏了这第五个写口)。"""
        path = _write_project(self.root, [self.CHANGE])
        r = ds_tools.delete_change(SLUG, 3, ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"删除按钮够不着 C03:{r}")
        self.assertIn("- [已删除] C03 2026-08-01 客厅刷白", _read(path))


class AmbiguityTable(CnumBase):
    """A4(攻题 HIGH-1):`C3` 与 `C03` 并存时,**每一种入参写法**都必须拒写。

    只测整数 `3` 是不够的 —— "只改正则、不做入口归一"那种半吊子修法能骗过它,
    而传 `"03"` 时它会安静地改错一行(`C0*03` 只命中 `C03`)。
    """

    LINES = ["- [待确认] C3 2026-08-01 客厅刷白",
             "- [待确认] C03 2026-08-02 主卧换灯"]
    INPUTS = (3, "3", "03", "C3", "C03", " C03 ")

    def test_a4_every_input_form_is_ambiguous(self):
        for arg in self.INPUTS:
            with self.subTest(cnum=arg):
                path = _write_project(self.root, self.LINES)
                before = _read(path)
                r = ds_tools.edit_change(SLUG, arg, new_status="进行中",
                                         ds_root=self.root, today=TODAY)
                self.assertEqual(r.get("error"), "ambiguous_change",
                                 f"入参 {arg!r} 该判歧义,实际:{r}")
                self.assertEqual(_read(path), before, f"入参 {arg!r} 判了歧义就不许写")

    def test_a4b_every_input_form_reaches_the_single_change(self):
        """反过来:只有一行时,同样这些入参**都得够得着它**(等价性)。"""
        for arg in (3, "3", "03", "C3", "C03"):
            with self.subTest(cnum=arg):
                path = _write_project(self.root, ["- [待确认] C3 2026-08-01 客厅刷白"])
                r = ds_tools.edit_change(SLUG, arg, new_status="进行中",
                                         ds_root=self.root, today=TODAY)
                self.assertNotIn("error", r, f"入参 {arg!r} 该够得着 C3:{r}")
                self.assertIn("- [进行中] C3", _read(path))

    def test_a4c_delete_and_due_date_share_the_same_tolerance(self):
        """另外两个双面工具(删除按钮 / 截止日)入参口径必须一致。"""
        for arg in ("03", "C03"):
            with self.subTest(cnum=arg):
                path = _write_project(self.root, ["- [待确认] C3 2026-08-01 客厅刷白"])
                self.assertNotIn("error", ds_tools.set_due_date(
                    SLUG, arg, "2026-09-01", ds_root=self.root, today=TODAY))
                self.assertNotIn("error", ds_tools.delete_change(
                    SLUG, arg, ds_root=self.root, today=TODAY))
                self.assertIn("- [已删除] C3", _read(path))


class FullWidthDigits(CnumBase):
    """A5(攻题 HIGH-2):`C０３` —— 读侧 `\\d`/`int()` 本来就吃全角数字。

    ASCII 的 `C0*3` 够不着它 ⇒ 同一个 bug 换个字符就复活,而且同样能骗过歧义检查。
    这条也是"按数比对"这个修法白捡的:不用为它单开一种字符规则。
    """

    def test_a5_read_side_already_treats_it_as_3(self):
        self.assertEqual(ds_todo.parse_change("- [待确认] C０３ 2026-08-01 客厅刷白")["cnum"], 3)

    def test_a5b_write_side_reaches_it(self):
        path = _write_project(self.root, ["- [待确认] C０３ 2026-08-01 客厅刷白"])
        r = ds_tools.edit_change(SLUG, 3, new_status="进行中", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"写侧够不着全角数字的 C０３:{r}")
        self.assertIn("- [进行中] C０３", _read(path), "C 号字节照旧不动")

    def test_a5c_ambiguous_with_ascii_sibling(self):
        path = _write_project(self.root, ["- [待确认] C3 2026-08-01 客厅刷白",
                                          "- [待确认] C０３ 2026-08-02 主卧换灯"])
        before = _read(path)
        r = ds_tools.edit_change(SLUG, 3, new_status="进行中", ds_root=self.root, today=TODAY)
        self.assertEqual(r.get("error"), "ambiguous_change",
                         f"两行都被读成 3 号,写侧就必须判歧义:{r}")
        self.assertEqual(_read(path), before)

    def test_a5d_note_line_with_full_width_digits(self):
        path = _write_project(self.root, ["- [待确认] C3 2026-08-01 客厅刷白"],
                              ["- C０３ 备注:老备注"])
        ds_tools.edit_change(SLUG, 3, note="", ds_root=self.root, today=TODAY)
        self.assertEqual(_note_lines(_read(path)), [], "全角数字的备注行也得被清掉")


# ══════════════════════════════════════════════════════════════════════════
# N 组:不许误伤 / 不许修过头
# ══════════════════════════════════════════════════════════════════════════

class NoCollateralDamage(CnumBase):

    def test_n1_does_not_touch_c13(self):
        _write_project(self.root, ["- [待确认] C13 2026-08-01 客厅刷白"])
        r = ds_tools.edit_change(SLUG, 3, new_status="进行中", ds_root=self.root, today=TODAY)
        self.assertEqual(r.get("error"), "change_not_found", f"3 不该够到 C13:{r}")

    def test_n2_does_not_touch_c30(self):
        _write_project(self.root, ["- [待确认] C30 2026-08-01 客厅刷白"])
        r = ds_tools.edit_change(SLUG, 3, new_status="进行中", ds_root=self.root, today=TODAY)
        self.assertEqual(r.get("error"), "change_not_found", f"3 不该够到 C30:{r}")

    def test_n2b_note_anchor_does_not_touch_c30(self):
        path = _write_project(self.root, ["- [待确认] C3 2026-08-01 客厅刷白"],
                              ["- C30 备注:别人的备注"])
        ds_tools.edit_change(SLUG, 3, note="", ds_root=self.root, today=TODAY)
        self.assertIn("- C30 备注:别人的备注", _read(path), "清 C3 的备注不许删掉 C30 的")

    def test_n3_reaches_c003(self):
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
        self.assertEqual(ds_todo.parse_history("## 变更历史\n- C03 备注:老备注\n")[3]["note"],
                         "老备注")

    def test_n6_same_value_is_still_a_noop(self):
        """攻题 Q4:保存同值 ⇒ 不写、不 bump「最后更新」、不谎报 changed_fields。

        0.83.0 立的契约(`_upsert_note` 的 docstring),这一单不许把它撞坏 ——
        "顺手把 C03 规范化成 C3" 正好会撞坏它:内容没变、文件却变了。
        """
        path = _write_project(self.root, ["- [待确认] C3 2026-08-01 客厅刷白"],
                              ["- C03 备注:老备注"])
        before = _read(path)
        r = ds_tools.edit_change(SLUG, 3, note="老备注", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"同值保存不该失败:{r}")
        self.assertNotIn("note", r.get("changed_fields", []),
                         f"值没变就不该说自己改了 note:{r}")
        self.assertEqual(_read(path), before,
                         "同值保存必须逐字节不写(含页脚「最后更新」不许 bump)")

    def test_n9_write_must_round_trip(self):
        """🔴 四审 subdeepseek(孤腿 BLOCK)抓到的:**写完必须还读得回来。**

        `- [待确认] C03-1 …` 这种带后缀的行,读侧把正文切在 `-1` 那里(界面上就这么显示),
        写侧切在同一个位置 —— 边界一致没问题。**坏在结果行**:替换完变成
        `- [待确认] C03客厅刷米白`(C 号与正文之间的空格被吃掉),再读回来
        **`cnum` 是 None** ⇒ 这条变更从此没有编号,任何工具都再也定位不到它。
        改动前这条路是安全拒写的(旧锚 `C3\b` 够不着 `C03-1`),是本单放开的。

        钉的是一条**通用不变量**:任何写口写完之后,这一行必须还能被读侧读成同一条变更;
        保证不了就 fail closed、档案逐字节不动。不是"给这一种形状打补丁"。
        """
        line = "- [待确认] C03-1 2026-08-01 厨房插座第一小项"
        path = _write_project(self.root, [line])
        before = _read(path)
        r = ds_tools.edit_change(SLUG, 3, new_text="客厅刷米白",
                                 ds_root=self.root, today=TODAY)
        self.assertIn("error", r, f"保证不了读得回来就必须拒写,不许静默毁行:{r}")
        self.assertNotEqual(r.get("error"), "change_not_found",
                            "错误话术要指得出真原因,不许again说'找不到'(本单 proposal 就在骂这个)")
        self.assertEqual(_read(path), before, "拒写就得逐字节不动")

    def test_n9b_normal_text_edit_still_works(self):
        """反面:正常行的改正文一个都不许被这道保险误伤(含【空间】前缀与截止日)。"""
        line = "- [待确认] C3 2026-08-01 【客厅】客厅刷白 ⏳2026-09-01"
        path = _write_project(self.root, [line])
        r = ds_tools.edit_change(SLUG, 3, new_text="客厅刷米白",
                                 ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"正常行的改正文不该被误伤:{r}")
        txt = _read(path)
        self.assertIn("- [待确认] C3 2026-08-01 【客厅】客厅刷米白 ⏳2026-09-01", txt)
        self.assertEqual(ds_todo.parse_change(
            [l for l in txt.split("\n") if l.startswith("- [")][0])["cnum"], 3)

    def test_n8_hand_written_status_tolerance_is_uniform(self):
        """主 agent 亲读 diff 抓到的回归(腿没提,判据原先也问不出):

        业主手写的**非词表状态**行(`- [搁置] C3 …`),改动前 `delete_change` /
        `set_change_status` / `edit_change` 三个写口**都够得着**;改动后只有
        `edit_change` 还够得着(它单独加了回退),共用的 `_rewrite_change_status` 没加
        ⇒ 同一次改动里三个写口的容差自相矛盾,而且**收紧的正是"手写档案"这条路** ——
        恰恰是本单要救的那类档案。这里钉的是"三个写口容差一致",不是"该不该容忍"。
        """
        line = "- [搁置] C3 2026-08-01 客厅刷白"
        for op in ("edit", "status", "delete"):
            with self.subTest(op=op):
                path = _write_project(self.root, [line])
                if op == "edit":
                    r = ds_tools.edit_change(SLUG, 3, new_text="客厅刷米白",
                                             ds_root=self.root, today=TODAY)
                elif op == "status":
                    r = ds_tools.set_change_status(SLUG, "C3", "已完成",
                                                   ds_root=self.root, today=TODAY)
                else:
                    r = ds_tools.delete_change(SLUG, 3, ds_root=self.root, today=TODAY)
                self.assertNotIn("error", r,
                                 f"{op} 够不着手写状态行 —— 三个写口容差必须一致:{r}")

    def test_n7_read_and_write_agree_on_suffixed_numbers(self):
        """`C03-1` 这种带后缀的形状:钉的不是"它合不合法",而是**两侧给同一个答案**。

        读侧 `C(\\d+)\\b` 一直把它读成 3 号(界面上就显示成 C3),那么写侧也必须够得着它;
        否则又是一条"读得到、写不动"—— 正是本单要消灭的形状。
        要不要禁掉这种写法是另一个产品问题,不在这一单。
        """
        line = "- [待确认] C03-1 2026-08-01 厨房插座第一小项"
        self.assertEqual(ds_todo.parse_change(line)["cnum"], 3, "读侧的既有行为")
        path = _write_project(self.root, [line])
        r = ds_tools.edit_change(SLUG, 3, new_status="进行中", ds_root=self.root, today=TODAY)
        self.assertNotIn("error", r, f"读侧认它是 3 号,写侧就得够得着:{r}")
        self.assertIn("- [进行中] C03-1", _read(path))
        # ⚠️ 只有"改状态/改截止日/删除/改备注"这几口是够得着的(它们不重写正文段)。
        #    **改正文**这一口对这种行必须拒写 —— 见 N9(四审孤腿 BLOCK 抓到的毁行路径)。


if __name__ == "__main__":
    unittest.main(verbosity=2)
