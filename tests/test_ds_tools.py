#!/usr/bin/env python3
"""ds_tools 核心的 oracle 矩阵 — 对齐 docs/spec.md §8(主 agent 拥有,不交弱模型)。

跑法:  python3 tests/test_ds_tools.py
不需要 nanobot / mcp SDK / 网络 —— 只测纯 Python 核心。
"""
import os
import sys
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # design-studio/
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_tools  # noqa: E402

TODAY = "2026-07-01"

SAMPLE_HEAD = """# {slug}

- 业主: [[张三]]
- 阶段: 方案深化

## 变更记录
"""
SAMPLE_TAIL = """
## 沟通日志
- 2026-06-20 微信:太太提改推拉门

---
最后更新: 2026-06-20
"""


def _write_project(ds_root, slug, change_lines):
    projdir = os.path.join(ds_root, "projects")
    os.makedirs(projdir, exist_ok=True)
    body = SAMPLE_HEAD.format(slug=slug) + "\n".join(change_lines) + SAMPLE_TAIL
    path = os.path.join(projdir, f"{slug}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return path


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _change_count(text):
    return sum(1 for ln in text.splitlines() if ds_tools._CHANGE_RE.match(ln))


class OracleMatrix(unittest.TestCase):
    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dstest-")
        self.slug = "翡翠湾-1801"
        self.default_changes = [
            "- [待确认] C1 2026-06-20 主卧衣柜改推拉门",
            "- [进行中] C2 2026-06-19 玄关增加到顶储物柜",
            "- [已完成] C3 2026-06-18 客厅吊顶改平顶",
            "- [已关闭] C4 2026-06-15 阳台封改开放式厨房",
        ]
        self.path = _write_project(self.ds, self.slug, self.default_changes)

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    # ① append 正常
    def test_01_append_normal(self):
        before = _change_count(_read(self.path))
        r = ds_tools.append_change(self.slug, "主卧门改到顶", ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        self.assertEqual(r["change_id"], "C5")
        text = _read(self.path)
        self.assertIn(f"- [待确认] C5 {TODAY} 主卧门改到顶", text)
        self.assertEqual(_change_count(text), before + 1)
        self.assertIn(f"最后更新: {TODAY}", text)

    # ② append 项目不存在
    def test_02_append_missing_project(self):
        r = ds_tools.append_change("不存在的项目", "x", ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "project_not_found")
        self.assertFalse(os.path.exists(os.path.join(self.ds, "projects", "不存在的项目.md")))

    # ③ id 连续
    def test_03_append_id_continuous(self):
        r = ds_tools.append_change(self.slug, "再来一条", ds_root=self.ds, today=TODAY)
        self.assertEqual(r["change_id"], "C5")  # 已有 C1..C4 → C5

    # ④ set_status 正常:只改方括号
    def test_04_set_status_normal(self):
        r = ds_tools.set_change_status(self.slug, "C1", "已完成", ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        self.assertEqual(r["old_status"], "待确认")
        self.assertIn("- [已完成] C1 2026-06-20 主卧衣柜改推拉门", _read(self.path))

    # ⑤ 非法 status
    def test_05_set_status_invalid(self):
        before = _read(self.path)
        r = ds_tools.set_change_status(self.slug, "C1", "done", ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "invalid_status")
        self.assertEqual(_read(self.path), before)  # 文件不变

    # ⑥ change_id 不存在
    def test_06_set_status_missing_id(self):
        before = _read(self.path)
        r = ds_tools.set_change_status(self.slug, "C99", "已完成", ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "change_not_found")
        self.assertEqual(_read(self.path), before)

    # ⑦ C2 不误伤 C12/C20
    def test_07_set_status_anchor(self):
        _write_project(self.ds, self.slug, [
            "- [待确认] C2 2026-06-20 目标行",
            "- [待确认] C12 2026-06-20 不该被碰",
            "- [待确认] C20 2026-06-20 也不该被碰",
        ])
        r = ds_tools.set_change_status(self.slug, "C2", "已完成", ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        text = _read(self.path)
        self.assertIn("- [已完成] C2 2026-06-20 目标行", text)
        self.assertIn("- [待确认] C12 2026-06-20 不该被碰", text)
        self.assertIn("- [待确认] C20 2026-06-20 也不该被碰", text)

    # ⑧ 命中多行(重复 id)
    def test_08_set_status_ambiguous(self):
        _write_project(self.ds, self.slug, [
            "- [待确认] C2 2026-06-20 第一条",
            "- [进行中] C2 2026-06-19 重复的编号",
        ])
        before = _read(self.path)
        r = ds_tools.set_change_status(self.slug, "C2", "已完成", ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "ambiguous_change")
        self.assertEqual(_read(self.path), before)

    # ⑨ 任意写操作不减少变更行(精确计数 + C 编号集不变:替换行也算删)
    def test_09_no_line_deletion(self):
        n0 = _change_count(_read(self.path))
        ds_tools.append_change(self.slug, "加一条", ds_root=self.ds, today=TODAY)
        self.assertEqual(_change_count(_read(self.path)), n0 + 1)
        ds_tools.set_change_status(self.slug, "C4", "已完成", ds_root=self.ds, today=TODAY)
        text = _read(self.path)
        self.assertEqual(_change_count(text), n0 + 1)
        ids = sorted(int(ds_tools._CHANGE_RE.match(ln).group("num"))
                     for ln in text.splitlines() if ds_tools._CHANGE_RE.match(ln))
        self.assertEqual(ids, [1, 2, 3, 4, 5])  # 原编号都在、只多不少

    # ⑩ 路径逃逸
    def test_10_path_escape(self):
        r = ds_tools.read_project("../../../etc/passwd", ds_root=self.ds)
        self.assertEqual(r.get("error"), "path_escape")
        r2 = ds_tools.append_change("../../../tmp/pwn", "x", ds_root=self.ds, today=TODAY)
        self.assertEqual(r2.get("error"), "path_escape")
        self.assertFalse(os.path.exists("/tmp/pwn.md"))

    # ⑪ 端到端冒烟 A:业主口述 → append(工具层断言;真 e2e 需接大脑)
    def test_11_smoke_append(self):
        r = ds_tools.append_change(self.slug, "太太想把主卧门改到顶", ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        self.assertIn("太太想把主卧门改到顶", _read(self.path))

    # ⑫ 端到端冒烟 B:C2 改成已完成
    def test_12_smoke_set_status(self):
        r = ds_tools.set_change_status(self.slug, "C2", "已完成", ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        self.assertEqual(r["new_status"], "已完成")
        self.assertIn("- [已完成] C2 2026-06-19 玄关增加到顶储物柜", _read(self.path))

    # 附:list_todos 冒烟(调真 ds-todo,需其存在)
    def test_13_list_todos(self):
        shutil.copytree(os.path.join(ROOT, "bin"), os.path.join(self.ds, "bin"),
                        dirs_exist_ok=True)
        r = ds_tools.list_todos(7, ds_root=self.ds)
        self.assertTrue(r["ok"])
        self.assertIn("未关闭事项", r["text"])


class InjectionOracle(unittest.TestCase):
    """字段注入面(2026-07-03 全库盲评 #1 后落的铁律 oracle):
    content 带换行 = 伪造任意账本行(词表/编号/页脚三铁律被打穿),必须在写入口折叠。"""

    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dstest-")
        self.slug = "翡翠湾-1801"
        self.path = _write_project(self.ds, self.slug, [
            "- [待确认] C1 2026-06-20 主卧衣柜改推拉门",
        ])

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    # ⑭ 换行注入被折叠:伪造行/伪造页脚都进不了文件
    def test_14_newline_injection_folded(self):
        payload = "改门\n- [已完成] C99 2026-01-01 伪造行\n最后更新: 2020-01-01"
        r = ds_tools.append_change(self.slug, payload, ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        self.assertEqual(r["change_id"], "C2")  # 编号不被伪造的 C99 顶跳
        text = _read(self.path)
        self.assertEqual(_change_count(text), 2)  # 恰好 +1,没有多出伪造行
        # 后置不变量:文件里所有变更行的状态都在词表内,且 append 只能产出 [待确认]
        self.assertNotRegex(text, r"(?m)^- \[已完成\]")
        for ln in text.splitlines():
            m = ds_tools._CHANGE_RE.match(ln)
            if m:
                self.assertIn(m.group("status"), ds_tools.STATUSES)
        # 页脚唯一且被正确更新(伪造的"最后更新"只能以行内文本存在)
        footers = [ln for ln in text.splitlines() if ln.startswith("最后更新")]
        self.assertEqual(footers, [f"最后更新: {TODAY}"])
        # 编号连续性未被污染
        r2 = ds_tools.append_change(self.slug, "下一条", ds_root=self.ds, today=TODAY)
        self.assertEqual(r2["change_id"], "C3")

    # ⑮ 全空白 content 折叠后为空 → 拒绝,文件不动
    def test_15_empty_content_rejected(self):
        before = _read(self.path)
        r = ds_tools.append_change(self.slug, " \n\r\n ", ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "empty_content")
        self.assertEqual(_read(self.path), before)

    # ⑯ set_change_status 也更新页脚(此前只有 append 路径有断言)
    def test_16_set_status_bumps_footer(self):
        r = ds_tools.set_change_status(self.slug, "C1", "已完成",
                                       ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        self.assertIn(f"最后更新: {TODAY}", _read(self.path))

    # ⑰ 错误路径完全不碰文件(内容和 mtime 都不变;此前会原样重写)
    def test_17_error_path_no_rewrite(self):
        before = _read(self.path)
        mtime0 = os.stat(self.path).st_mtime_ns
        r = ds_tools.set_change_status(self.slug, "C99", "已完成",
                                       ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "change_not_found")
        self.assertEqual(_read(self.path), before)
        self.assertEqual(os.stat(self.path).st_mtime_ns, mtime0)

    # ⑱ 页脚锚定写读同源:正文里行首出现"最后更新"时,更新的是最后一处(真页脚)
    def test_18_footer_anchor_last_occurrence(self):
        with open(self.path, "r+", encoding="utf-8") as fh:
            text = fh.read().replace(
                "## 沟通日志", "## 沟通日志\n最后更新: 2020-01-01 (手编混入的行)")
            fh.seek(0)
            fh.truncate()
            fh.write(text)
        ds_tools.append_change(self.slug, "新变更", ds_root=self.ds, today=TODAY)
        lines = _read(self.path).splitlines()
        footers = [ln for ln in lines if ln.startswith("最后更新")]
        self.assertEqual(len(footers), 2)
        self.assertIn("2020-01-01", footers[0])          # 混入行原样保留(不删行)
        self.assertEqual(footers[1], f"最后更新: {TODAY}")  # 真页脚被更新
        # 读侧(ds_todo)取的也是最后一处(=今天)→ 不因混入的旧日期误报超期
        import ds_todo
        from datetime import date as _date
        out = ds_todo.render(self.ds, 7, today=_date.fromisoformat(TODAY))
        self.assertNotIn(f"▸ {self.slug} —", out)


class CreateProjectClient(unittest.TestCase):
    """create_project / create_client oracle — 覆盖首用暴露的"无新建工具"洞。"""

    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dstest-")
        os.makedirs(os.path.join(self.ds, "projects"), exist_ok=True)
        os.makedirs(os.path.join(self.ds, "clients"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def _proj(self, slug):
        return _read(os.path.join(self.ds, "projects", f"{slug}.md"))

    # ① 新建项目:落在 projects/ 且结构可被 append/ds_todo 接上
    def test_c01_create_project_structure(self):
        r = ds_tools.create_project("保利中央公园-2803", "张三", ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        self.assertTrue(os.path.exists(os.path.join(self.ds, "projects", "保利中央公园-2803.md")))
        text = self._proj("保利中央公园-2803")
        self.assertIn("## 变更记录", text)           # append_change 定位靠它
        self.assertIn(f"最后更新: {TODAY}", text)      # ds_todo 判超期靠它
        self.assertIn("- 业主: [[张三]]", text)
        self.assertIn("- 阶段: 洽谈", text)

    # ② 新建后 append_change 无缝接上(集成:这正是首用断掉的链)
    def test_c02_append_after_create(self):
        ds_tools.create_project("保利中央公园-2803", "张三", ds_root=self.ds, today=TODAY)
        r = ds_tools.append_change("保利中央公园-2803", "客厅改开放式厨房",
                                   ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        self.assertEqual(r["change_id"], "C1")
        self.assertIn(f"- [待确认] C1 {TODAY} 客厅改开放式厨房", self._proj("保利中央公园-2803"))

    # ③ 新建后 ds_todo/list_todos 扫得到(首用"扫不到"的正解)
    def test_c03_listed_by_todo_after_create(self):
        ds_tools.create_project("保利中央公园-2803", "张三", ds_root=self.ds, today=TODAY)
        ds_tools.append_change("保利中央公园-2803", "客厅改开放式厨房",
                               ds_root=self.ds, today=TODAY)
        out = ds_tools.list_todos(ds_root=self.ds)["text"]
        self.assertIn("保利中央公园-2803", out)
        self.assertIn("客厅改开放式厨房", out)

    # ④ 自动补业主 stub(避免悬空 [[链接]])
    def test_c04_autocreate_client_stub(self):
        ds_tools.create_project("保利中央公园-2803", "李四", ds_root=self.ds, today=TODAY)
        cpath = os.path.join(self.ds, "clients", "李四.md")
        self.assertTrue(os.path.exists(cpath))
        self.assertIn("[[保利中央公园-2803]]", _read(cpath))

    # ⑤ 不覆盖已存在项目
    def test_c05_no_overwrite_project(self):
        ds_tools.create_project("保利中央公园-2803", "张三", ds_root=self.ds, today=TODAY)
        ds_tools.append_change("保利中央公园-2803", "先记一条", ds_root=self.ds, today=TODAY)
        r = ds_tools.create_project("保利中央公园-2803", "张三", ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "project_exists")
        self.assertIn("先记一条", self._proj("保利中央公园-2803"))  # 原内容原封不动

    # ⑥ create_client 独立可用 + 不覆盖
    def test_c06_create_client(self):
        r = ds_tools.create_client("王五", contact="微信 wangwu", ds_root=self.ds)
        self.assertTrue(r["ok"])
        self.assertIn("微信 wangwu", _read(os.path.join(self.ds, "clients", "王五.md")))
        r2 = ds_tools.create_client("王五", ds_root=self.ds)
        self.assertEqual(r2.get("error"), "client_exists")

    # ⑦ 已有业主不被 create_project 的 stub 覆盖
    def test_c07_existing_client_not_clobbered(self):
        ds_tools.create_client("张三", contact="电话 138", ds_root=self.ds)
        ds_tools.create_project("保利中央公园-2803", "张三", ds_root=self.ds, today=TODAY)
        self.assertIn("电话 138", _read(os.path.join(self.ds, "clients", "张三.md")))

    # ⑧ 路径逃逸被拒
    def test_c08_path_escape_rejected(self):
        r = ds_tools.create_project("../../etc/evil", "张三", ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "path_escape")
        self.assertFalse(os.path.exists(os.path.join(self.ds, "..", "..", "etc", "evil.md")))

    # ⑨ 字段注入:业主名带换行不能伪造账本行(折成单行)
    def test_c09_field_injection_folded(self):
        ds_tools.create_project(
            "注入测试", "恶意\n- [待确认] C99 2020-01-01 伪造", ds_root=self.ds, today=TODAY)
        text = self._proj("注入测试")
        # 安全属性 = 没有任何一行是可被解析的伪造账本行(换行折叠后伪造串只作行内子串,行首不匹配):
        self.assertEqual(sum(1 for ln in text.splitlines()
                             if ds_tools._CHANGE_RE.match(ln)), 0)   # _CHANGE_RE 行首锚定,零命中
        self.assertFalse(any(ln.lstrip().startswith("- [待确认]")
                             for ln in text.splitlines()))            # 无独立的伪造变更行

    # ⑩ 空名拒绝
    def test_c10_empty_name(self):
        self.assertEqual(ds_tools.create_project("", "张三", ds_root=self.ds).get("error"),
                         "empty_name")
        self.assertEqual(ds_tools.create_project("有名", "", ds_root=self.ds).get("error"),
                         "empty_name")
        self.assertEqual(ds_tools.create_client("", ds_root=self.ds).get("error"),
                         "empty_name")


if __name__ == "__main__":
    unittest.main(verbosity=2)
