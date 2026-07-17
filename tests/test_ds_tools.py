#!/usr/bin/env python3
"""ds_tools 核心的 oracle 矩阵 — 对齐 docs/spec.md §8(主 agent 拥有,不交弱模型)。

跑法:  python3 tests/test_ds_tools.py
不需要 nanobot / mcp SDK / 网络 —— 只测纯 Python 核心。
"""
import json
import os
import re
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


def _section(text, header):
    """抽出某 `## 标题` 段(标题行起,到下一 `## `/`---` 或文件末)的原始文本,做逐字节比对用。"""
    lines = text.split("\n")
    hi = lines.index(header)
    end = next((j for j in range(hi + 1, len(lines))
                if lines[j].startswith("## ") or lines[j].startswith("---")), len(lines))
    return "\n".join(lines[hi:end])


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

    # ⑲ 空间字段回环(track p4 T1):append(space=玄关) → 行含【玄关】→ parse 回读
    def test_19_append_with_space(self):
        r = ds_tools.append_change(self.slug, "鞋柜改悬浮", space="玄关",
                                   ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        cid = r["change_id"]
        self.assertIn(f"- [待确认] {cid} {TODAY} 【玄关】鞋柜改悬浮", _read(self.path))
        import ds_todo
        c = ds_todo.parse_change(r["line"])
        self.assertEqual(c["space"], "玄关")
        self.assertEqual(c["text"], "鞋柜改悬浮")

    # ⑳ 空间注入:】/【/换行 进不了结构;超长截断;空串视同不带
    def test_20_space_injection(self):
        r = ds_tools.append_change(self.slug, "内容", space="玄】\n关【x",
                                   ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        import ds_todo
        c = ds_todo.parse_change(r["line"])
        self.assertIsNotNone(c)                      # 行结构完好
        self.assertNotIn("】", c["space"])           # 括号剥掉
        self.assertNotIn("【", c["space"])
        self.assertEqual(c["text"], "内容")          # 正文没被吞
        # 超长:截到 16 字仍可解析
        r2 = ds_tools.append_change(self.slug, "内容2", space="很" * 40,
                                    ds_root=self.ds, today=TODAY)
        c2 = ds_todo.parse_change(r2["line"])
        self.assertEqual(c2["space"], "很" * 16)
        # 空串/纯空白:视同不带 space,行格式与 0.4.0 逐字节一致(向后兼容物理证明)
        r3 = ds_tools.append_change(self.slug, "内容3", space="  ",
                                    ds_root=self.ds, today=TODAY)
        self.assertEqual(r3["line"], f"- [待确认] {r3['change_id']} {TODAY} 内容3")

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


class EditChangeOracle(unittest.TestCase):
    """edit_change 核心 oracle(track opendesign-todo-edit,design test 1–5/10/11)。

    改状态/改正文(保前缀字节 + 向独立 `## 变更历史` 段留痕)/加改备注。主 agent 拥有本 oracle。
    起始 SAMPLE 无 `## 变更历史` 段 ⇒ 首次改正文/加备注即触发建段(design test 11)。
    """

    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dstest-")
        self.slug = "翡翠湾-1801"
        self.default_changes = [
            "- [待确认] C1 2026-06-20 主卧衣柜改推拉门",
            "- [进行中] C2 2026-06-19 玄关增加到顶储物柜",
            "- [已完成] C3 2026-06-18 【客厅】客厅吊顶改平顶",
        ]
        self.path = _write_project(self.ds, self.slug, self.default_changes)

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    # ① 改状态:只动主行状态段,cnum/date/space/text 原样,页脚 bump
    def test_e01_edit_status(self):
        r = ds_tools.edit_change(self.slug, 1, new_status="已完成",
                                 ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        text = _read(self.path)
        self.assertIn("- [已完成] C1 2026-06-20 主卧衣柜改推拉门", text)
        self.assertIn(f"最后更新: {TODAY}", text)
        self.assertNotIn("## 变更历史", text)  # 纯改状态不建历史段

    # ② 改正文·前缀字节不变(BLOCK-2):带【空间】变更改正文,前缀逐字节==原值,仅尾段变
    def test_e02_edit_text_prefix_bytes(self):
        r = ds_tools.edit_change(self.slug, 3, new_text="客厅吊顶改回弧形造型",
                                 ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        text = _read(self.path)
        self.assertIn("- [已完成] C3 2026-06-18 【客厅】客厅吊顶改回弧形造型", text)
        # 前缀(状态/C号/日期/【空间】)逐字节不变
        self.assertNotIn("客厅吊顶改平顶", text.split("## 变更历史")[0])  # 主行旧尾段没了
        # 留痕落在独立历史段
        self.assertIn("## 变更历史", text)
        self.assertIn(f"- C3 改于 {TODAY}｜原:客厅吊顶改平顶", text)
        import ds_todo
        line = next(l for l in text.splitlines()
                    if l.startswith("- [已完成] C3"))
        c = ds_todo.parse_change(line)
        self.assertEqual(c["space"], "客厅")
        self.assertEqual(c["date"], "2026-06-18")
        self.assertEqual(c["text"], "客厅吊顶改回弧形造型")

    # ③ 改正文·no-op:new_text==旧 → 不写留痕、不建段(无 `原:X`==新值噪声)
    def test_e03_edit_text_noop(self):
        before = _read(self.path)
        r = ds_tools.edit_change(self.slug, 1, new_text="主卧衣柜改推拉门",
                                 ds_root=self.ds, today=TODAY)
        self.assertTrue(r.get("ok"))
        text = _read(self.path)
        self.assertNotIn("改于", text)
        self.assertNotIn("## 变更历史", text)
        self.assertEqual(text, before)  # 真 no-op:文件逐字节不动

    # ④ 多次改正文:累积多条 `- C{n} 改于…` 历史,顺序合理;parse 仍只见原变更数
    def test_e04_edit_text_multiple(self):
        ds_tools.edit_change(self.slug, 1, new_text="主卧门改到顶",
                             ds_root=self.ds, today="2026-07-01")
        ds_tools.edit_change(self.slug, 1, new_text="主卧门改推拉到顶",
                             ds_root=self.ds, today="2026-07-02")
        text = _read(self.path)
        self.assertIn("- C1 改于 2026-07-01｜原:主卧衣柜改推拉门", text)
        self.assertIn("- C1 改于 2026-07-02｜原:主卧门改到顶", text)
        self.assertIn("- [待确认] C1 2026-06-20 主卧门改推拉到顶", text)
        self.assertEqual(_change_count(text), 3)  # 主变更行仍 3 条
        lines = text.splitlines()
        i1 = next(i for i, l in enumerate(lines) if "原:主卧衣柜改推拉门" in l)
        i2 = next(i for i, l in enumerate(lines) if "原:主卧门改到顶" in l)
        self.assertLess(i1, i2)  # 早的在上,晚的在下

    # ⑤ 加/改备注:按 cnum 键追加/替换,不重复;parse 数不变
    def test_e05_note_add_and_replace(self):
        ds_tools.edit_change(self.slug, 2, note="业主还在犹豫要不要加大",
                             ds_root=self.ds, today=TODAY)
        text = _read(self.path)
        self.assertIn("- C2 备注:业主还在犹豫要不要加大", text)
        self.assertEqual(_change_count(text), 3)
        # 再次加备注 → 替换,不叠加
        ds_tools.edit_change(self.slug, 2, note="业主已确认加大到顶",
                             ds_root=self.ds, today=TODAY)
        text2 = _read(self.path)
        self.assertIn("- C2 备注:业主已确认加大到顶", text2)
        self.assertNotIn("业主还在犹豫要不要加大", text2)
        self.assertEqual(sum(1 for l in text2.splitlines()
                             if l.startswith("- C2 备注")), 1)

    # ⑩ 非法:未知 cnum→change_not_found;非法 status→invalid_status;空 new_text→empty_text;错误路径不碰文件
    def test_e10_invalid(self):
        before = _read(self.path)
        self.assertEqual(
            ds_tools.edit_change(self.slug, 99, new_status="已完成",
                                 ds_root=self.ds, today=TODAY).get("error"),
            "change_not_found")
        self.assertEqual(
            ds_tools.edit_change(self.slug, 1, new_status="done",
                                 ds_root=self.ds, today=TODAY).get("error"),
            "invalid_status")
        self.assertEqual(
            ds_tools.edit_change(self.slug, 1, new_text=" \n\r ",
                                 ds_root=self.ds, today=TODAY).get("error"),
            "empty_text")
        self.assertEqual(_read(self.path), before)  # 三条非法路径全程文件不变

    # ⑪ 段创建:无 `## 变更历史` 段的旧项目首次 edit → 正确建段(位置对,append 段边界不破)
    def test_e11_history_section_created(self):
        r = ds_tools.edit_change(self.slug, 1, new_text="主卧改推拉门到顶",
                                 ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        lines = _read(self.path).splitlines()
        self.assertIn("## 变更历史", lines)
        ci = lines.index("## 变更记录")
        hi = lines.index("## 变更历史")
        gi = lines.index("## 沟通日志")
        self.assertTrue(ci < hi < gi)  # 历史段夹在变更记录段与沟通日志之间
        # append_change 仍落在变更记录段内(段边界不破)
        r2 = ds_tools.append_change(self.slug, "新需求一条", ds_root=self.ds, today=TODAY)
        self.assertTrue(r2["ok"])
        lines2 = _read(self.path).splitlines()
        ni = next(i for i, l in enumerate(lines2)
                  if "新需求一条" in l and ds_tools._CHANGE_RE.match(l))
        hi2 = lines2.index("## 变更历史")
        self.assertLess(ni, hi2)  # 新变更行在历史段之前

    # ⑫ 非标准状态主行改正文不崩(main-agent finding A):line_re 能定位任意状态,前缀正则
    #    须同样容忍;只改正文(不带 new_status)时保前缀、正确留痕,不 NoneType.group 崩
    def test_e12_edit_text_nonstandard_status(self):
        slug = "畸形状态"
        _write_project(self.ds, slug, ["- [搁置] C1 2026-06-20 【客厅】老正文"])
        r = ds_tools.edit_change(slug, 1, new_text="新正文", ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        text = _read(os.path.join(self.ds, "projects", f"{slug}.md"))
        self.assertIn("- [搁置] C1 2026-06-20 【客厅】新正文", text)  # 前缀(含非标准状态)逐字节保留
        self.assertIn(f"- C1 改于 {TODAY}｜原:老正文", text)          # 留痕旧正文正确


class EditChangeRegressionLock(unittest.TestCase):
    """T2 回归锁(design test 6–9):`## 变更历史` 段的存在不干扰任何既有读/写路径。

    BLOCK-1 反向锁 —— append/set_status 逐字节不碰历史段;collect/parse 不把历史行当待办;
    多变更按 cnum 键隔离(BLOCK-3)。
    """

    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dstest-")
        self.slug = "翡翠湾-1801"
        self.default_changes = [
            "- [待确认] C1 2026-06-20 主卧衣柜改推拉门",
            "- [进行中] C2 2026-06-19 玄关增加到顶储物柜",
            "- [已完成] C3 2026-06-18 【客厅】客厅吊顶改平顶",
        ]
        self.path = _write_project(self.ds, self.slug, self.default_changes)

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    # ⑥ 历史段任何行都不成待办:collect 未办结数==仅按变更记录段
    def test_e06_history_section_not_todos(self):
        import ds_todo
        from datetime import date as _date
        ds_tools.edit_change(self.slug, 1, new_text="改门到顶", note="业主确认",
                             ds_root=self.ds, today=TODAY)
        ds_tools.edit_change(self.slug, 2, new_text="改储物柜", note="待定",
                             ds_root=self.ds, today=TODAY)
        data = ds_todo.collect(self.ds, today=_date.fromisoformat(TODAY))
        open_cnums = sorted(it["cnum"] for it in data["open"]
                            if it["project"] == self.slug)
        self.assertEqual(open_cnums, [1, 2])  # 仅两条未办结主变更(C3 已完成不算)
        for it in data["open"]:  # 历史段的 改于/备注 行绝不混进待办
            self.assertNotIn("改于", it["raw"])
            self.assertNotIn("备注", it["raw"])

    # ⑦ 多变更 cnum 隔离(BLOCK-3):改 C2 一字不碰 C5(主行/历史/备注)
    def test_e07_cnum_isolation(self):
        slug = "隔离测试"
        _write_project(self.ds, slug, [
            "- [待确认] C2 2026-06-20 玄关改鞋柜",
            "- [进行中] C5 2026-06-19 主卧改门",
        ])
        path = os.path.join(self.ds, "projects", f"{slug}.md")
        ds_tools.edit_change(slug, 2, new_text="玄关改到顶鞋柜", note="C2备注",
                             ds_root=self.ds, today="2026-07-01")
        ds_tools.edit_change(slug, 5, new_text="主卧改推拉门", note="C5备注",
                             ds_root=self.ds, today="2026-07-01")
        c5_before = [l for l in _read(path).splitlines() if "C5" in l]
        # 再改 C2(正文+备注)
        ds_tools.edit_change(slug, 2, new_text="玄关改嵌入鞋柜", note="C2新备注",
                             ds_root=self.ds, today="2026-07-02")
        c5_after = [l for l in _read(path).splitlines() if "C5" in l]
        self.assertEqual(c5_before, c5_after)  # C5 相关行一字未动
        text = _read(path)
        self.assertEqual(sum(1 for l in text.splitlines()
                             if l.startswith("- C2 备注")), 1)  # C2 备注替换不叠加
        self.assertEqual(sum(1 for l in text.splitlines()
                             if l.startswith("- C5 备注")), 1)
        self.assertIn("- C5 备注:C5备注", text)  # C5 备注原样

    # ⑧ append_change 逐字节不碰历史段(BLOCK-1 反向锁)+ 新行落在变更记录段内
    def test_e08_append_history_untouched(self):
        ds_tools.edit_change(self.slug, 3, new_text="新正文", note="备注",
                             ds_root=self.ds, today=TODAY)
        before_hist = _section(_read(self.path), "## 变更历史")
        r = ds_tools.append_change(self.slug, "新变更需求", ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        text = _read(self.path)
        self.assertEqual(_section(text, "## 变更历史"), before_hist)  # 历史段逐字节不变
        lines = text.split("\n")
        ni = next(i for i, l in enumerate(lines)
                  if "新变更需求" in l and ds_tools._CHANGE_RE.match(l))
        hi = lines.index("## 变更历史")
        self.assertLess(ni, hi)  # 新变更行落在历史段头之前(=变更记录段内)

    # ⑧b 变更记录行逐字节与"无历史段"孪生一致(历史段存在与否不影响 append 产物;
    #     比对变更行本身 —— 段间分隔空行属段边界排版,不算变更记录内容)
    def test_e08b_change_lines_bytewise_invariant(self):
        def change_lines(path):
            return [l for l in _read(path).split("\n") if ds_tools._CHANGE_RE.match(l)]

        slug_a = "孪生A"
        pa = _write_project(self.ds, slug_a, self.default_changes)
        ds_tools.append_change(slug_a, "统一新增", ds_root=self.ds, today=TODAY)

        slug_b = "孪生B"
        pb = _write_project(self.ds, slug_b, self.default_changes)
        ds_tools.edit_change(slug_b, 1, note="造个历史段", ds_root=self.ds, today=TODAY)
        ds_tools.append_change(slug_b, "统一新增", ds_root=self.ds, today=TODAY)

        self.assertEqual(change_lines(pa), change_lines(pb))  # 变更记录行逐字节相同

    # ⑨ set_change_status 不动历史段:只主行状态变
    def test_e09_set_status_history_untouched(self):
        ds_tools.edit_change(self.slug, 2, new_text="改正文", note="备注",
                             ds_root=self.ds, today=TODAY)
        before_hist = _section(_read(self.path), "## 变更历史")
        r = ds_tools.set_change_status(self.slug, "C2", "已完成",
                                       ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        text = _read(self.path)
        self.assertEqual(_section(text, "## 变更历史"), before_hist)  # 历史段不动
        self.assertIn("- [已完成] C2 2026-06-19 改正文", text)  # 只主行状态变


class WriteSideNameGate(unittest.TestCase):
    """H1(07-13 盲评):写侧名字必须过 ds_workspace.PROJECT_NAME_RE 单一真相源。

    根因=写侧"项目"定义(树内任意 .md)与读侧(一级 *.md)双真相:`小区/1801`
    落成 projects/小区/1801.md,写入成功但 collect/一级 listdir/web key 闸全都
    永远看不见——静默丢活。闸在 _resolve(写读同一咽喉),within 之后字符集之前
    不改 test_c08 钉死的 path_escape 契约。
    """

    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dstest-")
        os.makedirs(os.path.join(self.ds, "projects"), exist_ok=True)
        os.makedirs(os.path.join(self.ds, "clients"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def _no_nested(self):
        # 安全属性:projects/ 与 clients/ 下不允许出现任何子目录(嵌套=读不到)
        for sub in ("projects", "clients"):
            base = os.path.join(self.ds, sub)
            self.assertEqual(
                [e for e in os.listdir(base)
                 if os.path.isdir(os.path.join(base, e))], [],
                f"{sub}/ 出现嵌套目录")

    # ① create_project 拒 `/`,零落盘
    def test_h1_create_project_slash_rejected(self):
        r = ds_tools.create_project("翡翠湾/1801", "张三", ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "bad_name")
        self._no_nested()

    # ② create_client 拒 `\`(Linux 上是合法文件名但读视图/兄弟平台全看不见)
    def test_h1_create_client_backslash_rejected(self):
        r = ds_tools.create_client("张\\三", ds_root=self.ds)
        self.assertEqual(r.get("error"), "bad_name")
        self.assertEqual([e for e in os.listdir(os.path.join(self.ds, "clients"))], [])

    # ③ append/set_status 同闸(即使有人绕过工具已经造出嵌套文件,也不给续写)
    def test_h1_append_and_status_rejected(self):
        nested = os.path.join(self.ds, "projects", "翡翠湾")
        os.makedirs(nested)
        with open(os.path.join(nested, "1801.md"), "w", encoding="utf-8") as fh:
            fh.write("# 翡翠湾/1801\n\n## 变更记录\n\n---\n最后更新: 2026-01-01\n")
        r = ds_tools.append_change("翡翠湾/1801", "改厨房", ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "bad_name")
        r2 = ds_tools.set_change_status("翡翠湾/1801", "C1", "进行中",
                                        ds_root=self.ds, today=TODAY)
        self.assertEqual(r2.get("error"), "bad_name")

    # ④ 业主名走 create_project 的自动 stub 路径同样不落嵌套
    def test_h1_client_via_project_stub_rejected(self):
        r = ds_tools.create_project("正常项目", "李/四", ds_root=self.ds, today=TODAY)
        # 项目名合法、业主名非法:项目允许建(业主 stub 静默跳过,linked 悬空可后补),
        # 但 clients/ 下必须零落盘、零嵌套
        self.assertTrue(r.get("ok") or r.get("error") == "bad_name")
        self._no_nested()
        self.assertEqual(os.listdir(os.path.join(self.ds, "clients")), [])

    # ⑤ 真实命名约定(日期 地点 楼盘 楼栋#户号 + 括号/横线)必须照常全通
    def test_h1_real_naming_convention_passes(self):
        slug = "0712 汇景花园 8#1801(复尺)-二期"
        r = ds_tools.create_project(slug, "张三", ds_root=self.ds, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        r2 = ds_tools.append_change(slug, "客厅改开放式", ds_root=self.ds, today=TODAY)
        self.assertTrue(r2.get("ok"), r2)
        r3 = ds_tools.set_change_status(slug, "C1", "已完成", ds_root=self.ds, today=TODAY)
        self.assertTrue(r3.get("ok"), r3)
        self.assertTrue(ds_tools.read_project(slug, ds_root=self.ds).get("ok"))

    # ⑥ 逃逸仍是 path_escape(闸序不改 test_c08 契约)
    def test_h1_escape_still_path_escape(self):
        r = ds_tools.create_project("../../etc/evil", "张三", ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "path_escape")

    # ⑦ v2 黑名单化:中文全角标点 / & 等常见命名字符,写侧名字闸放行(不再误伤)
    def test_h1_fullwidth_punct_name_passes(self):
        slug = "汇景花园（复尺）& 二期！"  # 全角括号/&/全角叹号 —— 老白名单会误拒
        r = ds_tools.create_project(slug, "张三", ds_root=self.ds, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        self.assertTrue(ds_tools.append_change(slug, "客厅改开放式",
                                               ds_root=self.ds, today=TODAY).get("ok"))
        self.assertTrue(ds_tools.read_project(slug, ds_root=self.ds).get("ok"))
        self._no_nested()

    # ⑧ % 仍拒(URL 编码引信,黑名单保留)
    def test_h1_percent_name_rejected(self):
        r = ds_tools.create_project("坏名%线", "张三", ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "bad_name")
        self._no_nested()


class SetWorkspaceOracle(unittest.TestCase):
    """Track B/B1 set_workspace + B2 list_todos 未接入提醒的 oracle(主 agent 拥有)。

    red-check(commit message 附结果):
      注释 isabs 校验 → test_w02_reject_relative_root 变红
      注释坏 JSON 备份重写 → test_w05_bad_json_backup_not_crash 变红
      注释 os.replace 原子写(改直接 open(w) 覆写)→ test_w06_atomic_no_tmp_leftover 仍绿但
        test_w07 崩溃语义降级(此处以"无 .tmp 残留 + 合法 JSON"守)
      注释 list_todos 的 load_config prepend → test_w10_list_todos_hint_when_unconfigured 变红
      把 root 与 DS_ORGANIZE_ROOTS 绑一起写 → test_w12_invariant_no_organize_key 变红
    """

    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dsws-")
        os.makedirs(os.path.join(self.ds, "config"), exist_ok=True)
        self.ws = tempfile.mkdtemp(prefix="dswsroot-")  # 用户真实工作区根
        self.cfg_path = os.path.join(self.ds, "config", "workspace.json")

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)
        shutil.rmtree(self.ws, ignore_errors=True)

    def _write_cfg(self, obj):
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            fh.write(obj if isinstance(obj, str) else json.dumps(obj))

    def _read_cfg(self):
        with open(self.cfg_path, encoding="utf-8") as fh:
            return json.load(fh)

    # ① 正常写入 + folder_count(候选目录名 01-项目 下两个项目夹)
    def test_w01_basic_write_and_count(self):
        for d in ("01-项目/甲项目", "01-项目/乙项目"):
            os.makedirs(os.path.join(self.ws, *d.split("/")))
        r = ds_tools.set_workspace(self.ws, ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r["root"], os.path.realpath(self.ws))
        self.assertEqual(r["folder_count"], 2)
        cfg = self._read_cfg()
        self.assertEqual(cfg["root"], os.path.realpath(self.ws))
        self.assertEqual(cfg["projects"], {})

    # ② 拒相对路径(isabs)——不写文件
    def test_w02_reject_relative_root(self):
        r = ds_tools.set_workspace("relative/dir", ds_root=self.ds)
        self.assertEqual(r.get("error"), "root_not_absolute")
        self.assertFalse(os.path.exists(self.cfg_path))

    # ③ 拒不存在的 root
    def test_w03_reject_missing_root(self):
        r = ds_tools.set_workspace(os.path.join(self.ws, "nope"), ds_root=self.ds)
        self.assertEqual(r.get("error"), "root_not_dir")
        self.assertFalse(os.path.exists(self.cfg_path))

    # ④ 保留已有 projects 映射(核心:重接工作区不丢用户手写映射)
    def test_w04_preserve_projects_mapping(self):
        self._write_cfg({"root": "/old", "projects": {"甲": "01-项目/甲"},
                         "projectsDir": "01-项目"})
        r = ds_tools.set_workspace(self.ws, ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        cfg = self._read_cfg()
        self.assertEqual(cfg["projects"], {"甲": "01-项目/甲"})
        self.assertEqual(cfg["projectsDir"], "01-项目")  # 未显式传 → 保留
        self.assertEqual(cfg["root"], os.path.realpath(self.ws))

    # ⑤ 坏 JSON:备份 .bak + 写全新,不崩
    def test_w05_bad_json_backup_not_crash(self):
        self._write_cfg("{broken json")
        r = ds_tools.set_workspace(self.ws, ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertTrue(os.path.exists(self.cfg_path + ".bak"))
        cfg = self._read_cfg()               # 新文件合法
        self.assertEqual(cfg["projects"], {})

    # ⑥ 原子写:成功后无 .tmp 残留,且 workspace.json 是合法 JSON
    def test_w06_atomic_no_tmp_leftover(self):
        ds_tools.set_workspace(self.ws, ds_root=self.ds)
        self.assertFalse(os.path.exists(self.cfg_path + ".tmp"))
        self._read_cfg()  # 不抛 = 合法

    # ⑦ 固定写路径:只写 config/workspace.json,不因 root 内容而变
    def test_w07_fixed_write_path(self):
        ds_tools.set_workspace(self.ws, ds_root=self.ds)
        self.assertTrue(os.path.exists(self.cfg_path))

    # ⑧ projects_dir="." 认 root 级布局(项目夹直接摊在 root 一级)
    def test_w08_projects_dir_dot_root_level(self):
        for d in ("甲项目", "乙项目", "丙项目"):
            os.makedirs(os.path.join(self.ws, d))
        r0 = ds_tools.set_workspace(self.ws, ds_root=self.ds)  # 无 projects_dir → 认不出
        self.assertEqual(r0["folder_count"], 0)
        r1 = ds_tools.set_workspace(self.ws, projects_dir=".", ds_root=self.ds)
        self.assertEqual(r1["folder_count"], 3)
        self.assertEqual(self._read_cfg()["projectsDir"], ".")

    # ⑨ 写完免重启即时生效:load_config 立刻见新 root
    def test_w09_takes_effect_no_restart(self):
        import ds_workspace
        self.assertIsNone(ds_workspace.load_config(self.ds))
        ds_tools.set_workspace(self.ws, ds_root=self.ds)
        cfg = ds_workspace.load_config(self.ds)
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg["root"], os.path.realpath(self.ws))

    # ⑩ B2:未接入 → list_todos 文本前置提醒行
    def test_w10_list_todos_hint_when_unconfigured(self):
        shutil.copytree(os.path.join(ROOT, "bin"), os.path.join(self.ds, "bin"),
                        dirs_exist_ok=True)
        r = ds_tools.list_todos(7, ds_root=self.ds)
        self.assertTrue(r["ok"])
        self.assertIn("还没接入项目文件夹", r["text"])
        self.assertIn("未关闭事项", r["text"])  # render 原文仍在

    # ⑪ B2:已接入 → 不再提醒
    def test_w11_list_todos_no_hint_when_configured(self):
        shutil.copytree(os.path.join(ROOT, "bin"), os.path.join(self.ds, "bin"),
                        dirs_exist_ok=True)
        ds_tools.set_workspace(self.ws, ds_root=self.ds)
        r = ds_tools.list_todos(7, ds_root=self.ds)
        self.assertTrue(r["ok"])
        self.assertNotIn("还没接入项目文件夹", r["text"])

    # ⑫ 铁律不变量:set_workspace 只写 workspace 视图字段,绝不碰 organize 作用域
    def test_w12_invariant_no_organize_key(self):
        os.environ.pop("DS_ORGANIZE_ROOTS", None)
        ds_tools.set_workspace(self.ws, ds_root=self.ds)
        cfg = self._read_cfg()
        self.assertLessEqual(set(cfg.keys()),
                             {"root", "projects", "projectsDir", "projectsDepth"})
        # set_workspace 不得副作用式设置 organize 白名单 env
        self.assertNotIn("DS_ORGANIZE_ROOTS", os.environ)

    # ⑬ depth2 track:projects_depth=2 写入 + folder_count 跨分组计数
    def test_w13_depth2_write_and_count(self):
        for d in ("2025/0605 某项目", "2026/0315 某项目", "2026/0428 某项目"):
            os.makedirs(os.path.join(self.ws, *d.split("/")))
        r = ds_tools.set_workspace(self.ws, projects_dir=".", projects_depth=2,
                                   ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r["folder_count"], 3)  # 跨分组总项目数,非分组数
        self.assertEqual(self._read_cfg()["projectsDepth"], 2)

    # ⑭ 不传 depth → 保留旧值(与 projectsDir 同款语义)
    def test_w14_depth_preserved_when_omitted(self):
        self._write_cfg({"root": "/old", "projects": {},
                         "projectsDir": ".", "projectsDepth": 2})
        r = ds_tools.set_workspace(self.ws, ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(self._read_cfg()["projectsDepth"], 2)

    # ⑮ 显式传 1 = 回到默认:字段清掉不落盘(写不写等价,保持文件最小)
    def test_w15_depth1_clears_field(self):
        self._write_cfg({"root": "/old", "projects": {},
                         "projectsDir": ".", "projectsDepth": 2})
        r = ds_tools.set_workspace(self.ws, projects_dir=".", projects_depth=1,
                                   ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertNotIn("projectsDepth", self._read_cfg())

    # ⑯ 非法 depth 拒绝,不写文件(config 校验是严格的,写侧不能放脏值进去)
    def test_w16_depth_invalid_rejected(self):
        r = ds_tools.set_workspace(self.ws, projects_depth=3, ds_root=self.ds)
        self.assertEqual(r.get("error"), "depth_invalid")
        self.assertFalse(os.path.exists(self.cfg_path))


class BindProjectOracle(unittest.TestCase):
    """bind-project track:bind_project(project, folder) 写显式映射(主 agent 拥有)。

    red-check(commit message 附结果):
      注释 folder ∈ project_folders 成员闸 → test_b05 变红
      注释 project 档案存在闸 → test_b03 变红
    """

    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dsbind-")
        os.makedirs(os.path.join(self.ds, "config"), exist_ok=True)
        os.makedirs(os.path.join(self.ds, "projects"), exist_ok=True)
        self.ws = tempfile.mkdtemp(prefix="dsbindws-")
        self.cfg_path = os.path.join(self.ds, "config", "workspace.json")
        # PKB 档案:福清咖啡厅;工作区:depth2 两分组三文件夹
        with open(os.path.join(self.ds, "projects", "福清咖啡厅.md"), "w",
                  encoding="utf-8") as fh:
            fh.write("# 福清咖啡厅\n\n- 阶段: 深化\n")
        for rel in ("2025/0110 某项目 福清 咖啡厅", "2025/0605 某项目",
                    "2026/0315 某项目"):
            os.makedirs(os.path.join(self.ws, *rel.split("/")))
        self._write_cfg({"root": self.ws, "projects": {"旧项目": "2025/0605 某项目"},
                         "projectsDir": ".", "projectsDepth": 2})

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)
        shutil.rmtree(self.ws, ignore_errors=True)

    def _write_cfg(self, obj):
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False)

    def _read_cfg(self):
        with open(self.cfg_path, encoding="utf-8") as fh:
            return json.load(fh)

    # ① happy:keyed folder → rel 带组落盘,project_dir 立刻解析到文件夹
    def test_b01_bind_and_resolve(self):
        import ds_workspace
        r = ds_tools.bind_project("福清咖啡厅", "2025:0110 某项目 福清 咖啡厅",
                                  ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r["rel"], "2025/0110 某项目 福清 咖啡厅")
        cfg = self._read_cfg()
        self.assertEqual(cfg["projects"]["福清咖啡厅"],
                         "2025/0110 某项目 福清 咖啡厅")
        loaded = ds_workspace.load_config(self.ds)
        self.assertEqual(
            ds_workspace.project_dir(loaded, "福清咖啡厅"),
            os.path.realpath(os.path.join(self.ws, "2025", "0110 某项目 福清 咖啡厅")))

    # ② 重绑=覆盖(显式映射就是纠偏机制)
    def test_b02_rebind_overwrites(self):
        ds_tools.bind_project("福清咖啡厅", "2025:0110 某项目 福清 咖啡厅",
                              ds_root=self.ds)
        r = ds_tools.bind_project("福清咖啡厅", "2026:0315 某项目", ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(self._read_cfg()["projects"]["福清咖啡厅"],
                         "2026/0315 某项目")

    # ③ 项目档案不存在 → 拒,零写入(助手打错字必须被拦)
    def test_b03_project_not_found(self):
        before = self._read_cfg()
        r = ds_tools.bind_project("不存在的项目", "2026:0315 某项目", ds_root=self.ds)
        self.assertEqual(r.get("error"), "project_not_found")
        self.assertEqual(self._read_cfg(), before)

    # ④ 坏项目名(H1 咽喉字符集)→ bad_name
    def test_b04_bad_project_name(self):
        r = ds_tools.bind_project("小区/1801", "2026:0315 某项目", ds_root=self.ds)
        self.assertIn(r.get("error"), ("bad_name", "path_escape"))

    # ⑤ folder 非已发现文件夹 → 拒,零写入,且带候选名单(自愈回路:助手无
    #    枚举工具,不还名单它只能瞎猜)
    def test_b05_folder_not_found(self):
        before = self._read_cfg()
        for bad in ("2026:没这个文件夹", "没这个纯名",
                    "../逃逸", "2026/0315 某项目"):     # rel 路径形式也不收
            r = ds_tools.bind_project("福清咖啡厅", bad, ds_root=self.ds)
            self.assertEqual(r.get("error"), "folder_not_found", bad)
            self.assertIn("2026:0315 某项目", r.get("folders", []), bad)
        self.assertEqual(self._read_cfg(), before)

    # ⑤b 纯名唯一命中 → 绑(侧栏展示"名+组标"两段,用户念的是纯名);
    #    返回的 folder 归一为完整 key
    def test_b05b_pure_name_unique_binds(self):
        r = ds_tools.bind_project("福清咖啡厅", "0315 某项目", ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r["folder"], "2026:0315 某项目")
        self.assertEqual(self._read_cfg()["projects"]["福清咖啡厅"],
                         "2026/0315 某项目")

    # ⑤c 纯名跨组撞名 → folder_ambiguous + 候选,零写入(不猜)
    def test_b05c_pure_name_ambiguous(self):
        os.makedirs(os.path.join(self.ws, "2025", "0315 某项目"))
        before = self._read_cfg()
        r = ds_tools.bind_project("福清咖啡厅", "0315 某项目", ds_root=self.ds)
        self.assertEqual(r.get("error"), "folder_ambiguous")
        self.assertIn("2025:0315 某项目", r["folders"])
        self.assertIn("2026:0315 某项目", r["folders"])
        self.assertEqual(self._read_cfg(), before)

    # ⑥ workspace 未配置 → 拒
    def test_b06_workspace_not_configured(self):
        os.remove(self.cfg_path)
        r = ds_tools.bind_project("福清咖啡厅", "2026:0315 某项目", ds_root=self.ds)
        self.assertEqual(r.get("error"), "workspace_not_configured")
        self.assertFalse(os.path.exists(self.cfg_path))

    # ⑦ 其余字段与既有映射原样保留 + 原子无 .tmp 残留
    def test_b07_preserves_and_atomic(self):
        r = ds_tools.bind_project("福清咖啡厅", "2026:0315 某项目", ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        cfg = self._read_cfg()
        self.assertEqual(cfg["projects"]["旧项目"], "2025/0605 某项目")  # 既有映射不动
        self.assertEqual(cfg["root"], self.ws)
        self.assertEqual(cfg["projectsDir"], ".")
        self.assertEqual(cfg["projectsDepth"], 2)
        self.assertFalse(os.path.exists(self.cfg_path + ".tmp"))

    # ②b 同对重绑=幂等成功,文件结构不变(subsense NIT-3)
    def test_b02b_rebind_same_pair_idempotent(self):
        ds_tools.bind_project("福清咖啡厅", "2026:0315 某项目", ds_root=self.ds)
        first = self._read_cfg()
        r = ds_tools.bind_project("福清咖啡厅", "2026:0315 某项目", ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(self._read_cfg(), first)

    # ⑧ depth=1 布局:裸文件夹名即 key,照常绑
    def test_b08_depth1_plain_folder(self):
        os.makedirs(os.path.join(self.ws, "平铺项目夹"))
        self._write_cfg({"root": self.ws, "projects": {}, "projectsDir": "."})
        r = ds_tools.bind_project("福清咖啡厅", "平铺项目夹", ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(self._read_cfg()["projects"]["福清咖啡厅"], "平铺项目夹")


class RenameProjectOracle(unittest.TestCase):
    """rename-project track:rename_project(old, new) 五处一致改名(主 agent 拥有)。

    red-check(commit message 附结果):
      注释 new 已存在闸(name_taken)→ test_r02 变红
      refs 用于段"精确项匹配"改成子串替换 → test_r07 变红
    """

    OLD = "锦修外滩"
    NEW = "1206 福州 锦绣外滩"

    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dsren-")
        for d in ("config", "projects", "clients"):
            os.makedirs(os.path.join(self.ds, d), exist_ok=True)
        self.ws = tempfile.mkdtemp(prefix="dsrenws-")
        os.makedirs(os.path.join(self.ws, "2025", self.NEW))
        self._w(f"projects/{self.OLD}.md",
                f"# {self.OLD}\n\n- 业主: [[王五]]\n- 阶段: 深化\n\n"
                f"## 变更记录\n- [待确认] C1 2026-07-01 玄关改柜\n")
        self._w("clients/王五.md",
                f"# 王五\n\n- 关联项目: [[{self.OLD}]]\n\n## 备注\n"
                f"提过 [[{self.OLD}]] 的吊顶要快。\n")
        self._w("index.md",
                f"# 索引\n\n| [[{self.OLD}]] | 王五 | 深化 |\n")
        # 用于段含精确项 + 前缀陷阱项(锦修外滩二期,不得被误伤)
        self._w("refs-index.md",
                "# 参考图索引\n\n"
                f"- [r1] 奶油风|客厅 | 来源: | 文件:refs/a.png | 用于:{self.OLD},锦修外滩二期 | 备注:\n"
                f"- [r2] 侘寂风|主卧 | 来源: | 文件:refs/b.png | 用于:别家项目 | 备注:\n"
                # 尾位 + 重复项(panel S2/S3:行为对也要锁死防回归)
                f"- [r3] 极简|厨房 | 来源: | 文件:refs/c.png | 用于:别家项目,{self.OLD},{self.OLD} | 备注:\n")
        with open(os.path.join(self.ds, "config", "workspace.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"root": self.ws, "projects": {self.OLD: f"2025/{self.NEW}"},
                       "projectsDir": ".", "projectsDepth": 2}, fh, ensure_ascii=False)

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)
        shutil.rmtree(self.ws, ignore_errors=True)

    def _w(self, rel, text):
        p = os.path.join(self.ds, rel)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)

    def _r(self, rel):
        with open(os.path.join(self.ds, rel), encoding="utf-8") as fh:
            return fh.read()

    # ① happy:五处齐改 + 审计清单
    def test_r01_full_rename(self):
        r = ds_tools.rename_project(self.OLD, self.NEW, ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertFalse(os.path.exists(os.path.join(self.ds, "projects", f"{self.OLD}.md")))
        body = self._r(f"projects/{self.NEW}.md")
        self.assertTrue(body.startswith(f"# {self.NEW}\n"))
        self.assertIn("- [待确认] C1", body)             # 账本原样
        self.assertNotIn(f"[[{self.OLD}]]", self._r("clients/王五.md"))
        self.assertEqual(self._r("clients/王五.md").count(f"[[{self.NEW}]]"), 2)
        self.assertIn(f"[[{self.NEW}]]", self._r("index.md"))
        refs = self._r("refs-index.md")
        self.assertIn(f"用于:{self.NEW},锦修外滩二期", refs)  # 精确项换,前缀项不动
        with open(os.path.join(self.ds, "config", "workspace.json"), encoding="utf-8") as fh:
            cfg = json.load(fh)
        self.assertEqual(cfg["projects"], {self.NEW: f"2025/{self.NEW}"})
        self.assertEqual(r["updated"]["clients"], ["王五"])
        self.assertTrue(r["updated"]["workspace"])
        self.assertEqual(r["updated"]["refs"], 2)
        # r3:尾位+重复项全换,别家项目原样
        self.assertIn(f"用于:别家项目,{self.NEW},{self.NEW}", refs)

    # ② new 已存在 → 拒,零改动
    def test_r02_name_taken(self):
        self._w(f"projects/{self.NEW}.md", f"# {self.NEW}\n")
        r = ds_tools.rename_project(self.OLD, self.NEW, ds_root=self.ds)
        self.assertEqual(r.get("error"), "name_taken")
        self.assertIn(f"[[{self.OLD}]]", self._r("clients/王五.md"))  # 引用没被动

    # ③ old 不存在 → project_not_found
    def test_r03_old_not_found(self):
        r = ds_tools.rename_project("没这个项目", self.NEW, ds_root=self.ds)
        self.assertEqual(r.get("error"), "project_not_found")

    # ④ 坏 new 名:链接/分段定界符与逃逸全拒
    def test_r04_bad_new_name(self):
        for bad in ("有|竖线", "有,逗号", "有[[链接", "有]]链接", "../逃逸", "a/b"):
            r = ds_tools.rename_project(self.OLD, bad, ds_root=self.ds)
            self.assertIn(r.get("error"), ("bad_name", "path_escape"), bad)
        self.assertTrue(os.path.exists(os.path.join(self.ds, "projects", f"{self.OLD}.md")))

    # ⑤ old == new → same_name
    def test_r05_same_name(self):
        r = ds_tools.rename_project(self.OLD, self.OLD, ds_root=self.ds)
        self.assertEqual(r.get("error"), "same_name")

    # ⑥ 自定义 title(首标题 ≠ old)保留,只改文件名
    def test_r06_custom_title_kept(self):
        self._w(f"projects/{self.OLD}.md", "# 我的自定义标题\n\n- 阶段: 深化\n")
        r = ds_tools.rename_project(self.OLD, self.NEW, ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertTrue(self._r(f"projects/{self.NEW}.md").startswith("# 我的自定义标题"))
        self.assertFalse(r["updated"]["title"])

    # ⑦ refs 只换精确项(前缀陷阱 锦修外滩二期 必须原样)——red-check 锚点
    def test_r07_refs_exact_item_only(self):
        ds_tools.rename_project(self.OLD, self.NEW, ds_root=self.ds)
        self.assertIn("锦修外滩二期", self._r("refs-index.md"))
        self.assertNotIn(f"用于:{self.NEW}二期", self._r("refs-index.md"))

    # ⑧ 无 workspace 配置照常成功,workspace:false
    def test_r08_no_workspace_ok(self):
        os.remove(os.path.join(self.ds, "config", "workspace.json"))
        r = ds_tools.rename_project(self.OLD, self.NEW, ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertFalse(r["updated"]["workspace"])

    # ⑨ 引用已改、档案未挪的中断状态 → 重跑补齐(幂等语义)。
    #    panel S1 扩展:workspace 键已迁、title 已写 `# new` 的最深中断态也重跑得通
    def test_r09_rerun_after_partial(self):
        # 模拟:第一次跑到 os.replace 前崩——引用全改完+映射键已迁+title 已写
        for rel in ("clients/王五.md", "index.md", "refs-index.md"):
            self._w(rel, self._r(rel).replace(f"[[{self.OLD}]]", f"[[{self.NEW}]]")
                    .replace(f"用于:{self.OLD},", f"用于:{self.NEW},"))
        cfgp = os.path.join(self.ds, "config", "workspace.json")
        with open(cfgp, encoding="utf-8") as fh:
            cfg = json.load(fh)
        cfg["projects"] = {self.NEW: cfg["projects"].pop(self.OLD)}
        with open(cfgp, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False)
        self._w(f"projects/{self.OLD}.md",
                self._r(f"projects/{self.OLD}.md").replace(f"# {self.OLD}", f"# {self.NEW}", 1))
        r = ds_tools.rename_project(self.OLD, self.NEW, ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertTrue(os.path.exists(os.path.join(self.ds, "projects", f"{self.NEW}.md")))
        self.assertTrue(self._r(f"projects/{self.NEW}.md").startswith(f"# {self.NEW}"))
        self.assertEqual(self._r("clients/王五.md").count(f"[[{self.NEW}]]"), 2)
        with open(cfgp, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["projects"], {self.NEW: f"2025/{self.NEW}"})

    # ⑩ 悬空 new 映射键被覆盖=语义锁死(panel 双家点名;悬空键无档案=垃圾,
    #    新项目接管其名下映射是正确行为,不加闸)
    def test_r10_stray_new_mapping_overwritten(self):
        cfgp = os.path.join(self.ds, "config", "workspace.json")
        with open(cfgp, encoding="utf-8") as fh:
            cfg = json.load(fh)
        cfg["projects"][self.NEW] = "2025/别的悬空目标"
        with open(cfgp, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False)
        r = ds_tools.rename_project(self.OLD, self.NEW, ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        with open(cfgp, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["projects"], {self.NEW: f"2025/{self.NEW}"})


class LogCommunicationOracle(unittest.TestCase):
    """track opendesign-owner-feedback:业主原文存沟通日志。
    保真(多行逐字)+ 结构注入免疫(`  > ` 前缀失锚)+ 段缺失补建。"""

    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dstest-")
        self.slug = "翡翠湾-1801"
        self.path = _write_project(self.ds, self.slug, [
            "- [待确认] C1 2026-06-20 主卧衣柜改推拉门",
        ])

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    # ① 多行原文逐字保存:每行 `  > ` 前缀,头行带来源,插进沟通日志段
    def test_lc01_multiline_verbatim(self):
        raw = "师傅你好,想改几个地方\n主卧的门还是想改到顶\n\n另外阳台那个再想想"
        r = ds_tools.log_communication(self.slug, raw, source="微信",
                                       ds_root=self.ds, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r["lines"], 5)  # 头行 + 4 行原文(含空行)
        sect = _section(_read(self.path), "## 沟通日志")
        self.assertIn(f"- {TODAY} 业主原文(微信):", sect)
        self.assertIn("  > 师傅你好,想改几个地方", sect)
        self.assertIn("  > 主卧的门还是想改到顶", sect)
        self.assertIn("  >\n", sect + "\n")  # 空行保留为裸 `  >`
        self.assertIn("  > 另外阳台那个再想想", sect)
        # 既有条目不动,新条目在其后
        self.assertLess(sect.index("太太提改推拉门"), sect.index("业主原文"))

    # ② 无 source:头行不带括号
    def test_lc02_no_source(self):
        r = ds_tools.log_communication(self.slug, "单行原话", ds_root=self.ds, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        self.assertIn(f"- {TODAY} 业主原文:", _read(self.path))
        self.assertNotIn("业主原文()", _read(self.path))

    # ③ 项目不存在 / 空文本 / 逃逸名:拒,零副作用
    def test_lc03_errors(self):
        r = ds_tools.log_communication("不存在", "x", ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "project_not_found")
        before = _read(self.path)
        r = ds_tools.log_communication(self.slug, "  \n \n", ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "empty_text")
        self.assertEqual(_read(self.path), before)
        r = ds_tools.log_communication("../越狱", "x", ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "path_escape")  # _resolve 契约:within 闸在字符集闸前
        r = ds_tools.log_communication("坏%名", "x", ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "bad_name")

    # ④ 注入红检:原文含伪变更行/伪段头/伪 footer → 全部失锚
    def test_lc04_injection_immune(self):
        evil = ("- [待确认] C99 2026-01-01 伪造变更\n"
                "## 变更记录\n"
                "## 新段落\n"
                "---\n"
                "最后更新: 1999-01-01")
        before_changes = _section(_read(self.path), "## 变更记录")
        r = ds_tools.log_communication(self.slug, evil, source="微信",
                                       ds_root=self.ds, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        text = _read(self.path)
        # 变更段逐字节不变;CHANGE_RE 计数不变(伪 C99 有 `  > ` 前缀失锚)
        self.assertEqual(_section(text, "## 变更记录"), before_changes)
        self.assertEqual(_change_count(text), 1)
        # 伪 footer 失锚:真 footer 是 today,伪 1999 只以引用形式存在
        self.assertIn(f"最后更新: {TODAY}", text)
        self.assertNotRegex(text, r"(?m)^最后更新: 1999-01-01")
        # 伪段头失锚:行首无裸 `## 新段落`
        self.assertNotRegex(text, r"(?m)^## 新段落")
        # 原文逐字都在(引用形式)
        self.assertIn("  > ## 变更记录", text)
        self.assertIn("  > - [待确认] C99 2026-01-01 伪造变更", text)

    # ⑤ 沟通日志段缺失 → 页脚前自动补建
    def test_lc05_missing_section_created(self):
        body = ("# 老项目\n\n- 业主: [[张三]]\n\n## 变更记录\n"
                "- [待确认] C1 2026-06-20 某条\n\n---\n最后更新: 2026-06-20\n")
        p = os.path.join(self.ds, "projects", "老项目.md")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(body)
        r = ds_tools.log_communication("老项目", "原话", ds_root=self.ds, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        text = _read(p)
        self.assertIn("## 沟通日志", text)
        # 段在页脚之前、变更段之后;footer 正常 bump
        self.assertLess(text.index("## 变更记录"), text.index("## 沟通日志"))
        self.assertLess(text.index("## 沟通日志"), text.index("---\n最后更新"))
        self.assertIn(f"最后更新: {TODAY}", text)

    # ⑥ 连续两次追加:时序保持(后写在后)
    def test_lc06_append_order(self):
        ds_tools.log_communication(self.slug, "第一段", ds_root=self.ds, today="2026-07-10")
        ds_tools.log_communication(self.slug, "第二段", ds_root=self.ds, today="2026-07-16")
        sect = _section(_read(self.path), "## 沟通日志")
        self.assertLess(sect.index("第一段"), sect.index("第二段"))

    # ⑧ 段存在但全空 → 插到段头之后(panel 收:行为对但没锁)
    def test_lc08_empty_section(self):
        body = ("# 空段项目\n\n## 变更记录\n\n## 沟通日志\n\n---\n最后更新: 2026-06-20\n")
        p = os.path.join(self.ds, "projects", "空段项目.md")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(body)
        r = ds_tools.log_communication("空段项目", "第一句", ds_root=self.ds, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        sect = _section(_read(p), "## 沟通日志")
        self.assertIn(f"- {TODAY} 业主原文:", sect)
        self.assertIn("  > 第一句", sect)

    # ⑨ 无页脚且无沟通日志段的老文件 → 文件末补建,不崩;footer bump 无处落=no-op
    def test_lc09_no_footer_file(self):
        body = "# 裸项目\n\n## 变更记录\n- [待确认] C1 2026-06-20 某条"
        p = os.path.join(self.ds, "projects", "裸项目.md")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(body)
        r = ds_tools.log_communication("裸项目", "原话", ds_root=self.ds, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        text = _read(p)
        self.assertIn("## 沟通日志", text)
        self.assertLess(text.index("## 变更记录"), text.index("## 沟通日志"))
        self.assertIn("  > 原话", text)
        self.assertNotIn("最后更新", text)  # bump 无页脚不硬造(既有语义)

    # ⑩ source 消毒:括号剥净(头行格式不被污染)+ 换行折叠 + 超 16 截断
    def test_lc10_source_sanitized(self):
        r = ds_tools.log_communication(self.slug, "x", source="微(信)\n群（备注）abcdefghijklmn",
                                       ds_root=self.ds, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        text = _read(self.path)
        m = re.search(r"(?m)^- \S+ 业主原文\(([^)]*)\):$", text)
        self.assertIsNotNone(m)
        src = m.group(1)
        self.assertNotIn("(", src)
        self.assertNotIn("（", src)
        self.assertNotIn("）", src)
        self.assertLessEqual(len(src), 16)
        self.assertTrue(src.startswith("微信 群备注"))  # 换行→空格,括号剥净

    # ⑦ CRLF 归一:\r\n / \r 原文不产生裸 \r 落盘
    def test_lc07_crlf_normalized(self):
        r = ds_tools.log_communication(self.slug, "a\r\nb\rc", ds_root=self.ds, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        text = _read(self.path)
        self.assertNotIn("\r", text)
        self.assertIn("  > a", text)
        self.assertIn("  > b", text)
        self.assertIn("  > c", text)


class DeleteProjectOracle(unittest.TestCase):
    """track opendesign-delete-project(队列#7):回收站式删除。
    档案移 projects/.trash/ 不真删;映射摘除;引用只清点不改。"""

    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dstest-")
        self.slug = "翡翠湾-1801"
        self.path = _write_project(self.ds, self.slug, [
            "- [待确认] C1 2026-06-20 主卧衣柜改推拉门",
        ])
        # 业主档案带 [[引用]] + index 带引用(删除后应原样留存,只被清点)
        cdir = os.path.join(self.ds, "clients")
        os.makedirs(cdir, exist_ok=True)
        with open(os.path.join(cdir, "张三.md"), "w", encoding="utf-8") as fh:
            fh.write("# 张三\n\n- 关联项目: [[翡翠湾-1801]]\n")
        with open(os.path.join(self.ds, "index.md"), "w", encoding="utf-8") as fh:
            fh.write("# 索引\n\n- [[翡翠湾-1801]] 张三\n")

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def _trash_files(self):
        t = os.path.join(self.ds, "projects", ".trash")
        return sorted(os.listdir(t)) if os.path.isdir(t) else []

    # ① 正常删除:原档案消失,回收站有一份内容一致的
    def test_dp01_trash_not_delete(self):
        original = _read(self.path)
        r = ds_tools.delete_project(self.slug, ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertFalse(os.path.exists(self.path))
        trashed = self._trash_files()
        self.assertEqual(len(trashed), 1)
        self.assertTrue(trashed[0].startswith(self.slug))
        with open(os.path.join(self.ds, "projects", ".trash", trashed[0]),
                  encoding="utf-8") as fh:
            self.assertEqual(fh.read(), original)  # 逐字节保真,可捞回
        self.assertIn(".trash", r.get("trashed", ""))

    # ② 引用只清点不改动:业主/index 文件逐字节不变,计数返回
    def test_dp02_refs_counted_not_touched(self):
        cpath = os.path.join(self.ds, "clients", "张三.md")
        ipath = os.path.join(self.ds, "index.md")
        cbefore, ibefore = _read(cpath), _read(ipath)
        r = ds_tools.delete_project(self.slug, ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(_read(cpath), cbefore)
        self.assertEqual(_read(ipath), ibefore)
        self.assertEqual(r["refs_remaining"]["clients"], 1)
        self.assertEqual(r["refs_remaining"]["index"], 1)

    # ③ 工作区映射指向该项目 → 一并摘除,其余映射不动
    def test_dp03_mapping_removed(self):
        cfgdir = os.path.join(self.ds, "config")
        os.makedirs(cfgdir, exist_ok=True)
        cfgp = os.path.join(cfgdir, "workspace.json")
        with open(cfgp, "w", encoding="utf-8") as fh:
            json.dump({"root": "/tmp", "projects": {self.slug: "某文件夹", "别的": "别夹"}},
                      fh, ensure_ascii=False)
        r = ds_tools.delete_project(self.slug, ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertTrue(r.get("mapping_removed"))
        with open(cfgp, encoding="utf-8") as fh:
            cfg = json.load(fh)
        self.assertEqual(cfg["projects"], {"别的": "别夹"})
        self.assertEqual(cfg["root"], "/tmp")  # 其余字段保真

    # ④ 无映射:mapping_removed=False,config 不被硬造
    def test_dp04_no_mapping(self):
        r = ds_tools.delete_project(self.slug, ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertFalse(r.get("mapping_removed"))
        self.assertFalse(os.path.exists(os.path.join(self.ds, "config", "workspace.json")))

    # ⑤ 错误契约:不存在/逃逸/坏名,零副作用
    def test_dp05_errors(self):
        r = ds_tools.delete_project("不存在", ds_root=self.ds)
        self.assertEqual(r.get("error"), "project_not_found")
        r = ds_tools.delete_project("../越狱", ds_root=self.ds)
        self.assertEqual(r.get("error"), "path_escape")
        r = ds_tools.delete_project("坏%名", ds_root=self.ds)
        self.assertEqual(r.get("error"), "bad_name")
        self.assertTrue(os.path.exists(self.path))  # 原档案安然
        self.assertEqual(self._trash_files(), [])

    # ⑥ 同名两次进回收站不互相覆盖(时间戳+序号消歧)
    def test_dp06_trash_no_clobber(self):
        ds_tools.delete_project(self.slug, ds_root=self.ds)
        _write_project(self.ds, self.slug, ["- [待确认] C1 2026-07-01 第二份"])
        r = ds_tools.delete_project(self.slug, ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(len(self._trash_files()), 2)

    # ⑧ refs-index 计数走「用于:」段精确项:不误伤超串项目名(panel 双家同标)
    def test_dp08_refs_count_exact(self):
        with open(os.path.join(self.ds, "refs-index.md"), "w", encoding="utf-8") as fh:
            fh.write("# 参考图索引\n\n"
                      "- r1 2026-07-01 a.jpg | 空间:客厅 | 用于:翡翠湾-1801\n"
                      "- r2 2026-07-02 b.jpg | 空间:主卧 | 用于:翡翠湾-1801二期\n"
                      "- r3 2026-07-03 c.jpg | 空间:玄关 | 用于:别项目,翡翠湾-1801\n")
        r = ds_tools.delete_project(self.slug, ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r["refs_remaining"]["refs"], 2)  # r1+r3;r2 超串不算

    # ⑨ 坏 workspace.json:映射步静默跳过(不硬修不崩),删除本体照走,文件不动
    def test_dp09_corrupt_workspace_json(self):
        cfgdir = os.path.join(self.ds, "config")
        os.makedirs(cfgdir, exist_ok=True)
        cfgp = os.path.join(cfgdir, "workspace.json")
        with open(cfgp, "w", encoding="utf-8") as fh:
            fh.write("{not valid json")
        r = ds_tools.delete_project(self.slug, ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertFalse(r.get("mapping_removed"))
        self.assertEqual(_read(cfgp), "{not valid json")  # 坏 config 原样留给人
        self.assertFalse(os.path.exists(self.path))

    # ⑦ 删除后扫描侧看不见:collect 不再列出,.trash 不被当项目
    def test_dp07_invisible_after_delete(self):
        import ds_todo
        ds_tools.delete_project(self.slug, ds_root=self.ds)
        got = ds_todo.collect(self.ds)
        self.assertEqual([o for o in got["open"] if o["project"] == self.slug], [])
        projs = ds_tools.read_project(self.slug, ds_root=self.ds)
        self.assertEqual(projs.get("error"), "project_not_found")


class SetStageOracle(unittest.TestCase):
    """set_stage oracle — 项目阶段推进(tool-audit 空格②,原字段建档后冻结)。"""

    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dstest-")
        os.makedirs(os.path.join(self.ds, "projects"), exist_ok=True)
        os.makedirs(os.path.join(self.ds, "clients"), exist_ok=True)
        ds_tools.create_project("万科城-802", "王姐", ds_root=self.ds, today=TODAY)
        self.path = os.path.join(self.ds, "projects", "万科城-802.md")

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    # ① 替换:阶段行变、prev 回报、页脚 bump 到 today(超期计时重置)
    def test_ss01_replace_and_bump(self):
        r = ds_tools.set_stage("万科城-802", "施工跟进",
                               ds_root=self.ds, today="2026-07-17")
        self.assertTrue(r["ok"])
        self.assertEqual(r["stage"], "施工跟进")
        self.assertEqual(r["prev"], "洽谈")
        text = _read(self.path)
        self.assertIn("- 阶段: 施工跟进", text)
        self.assertNotIn("- 阶段: 洽谈", text)
        self.assertIn("最后更新: 2026-07-17", text)

    # ② 词表闸:不在词表拒,带自愈清单,文件零改动
    def test_ss02_bad_stage(self):
        before = _read(self.path)
        r = ds_tools.set_stage("万科城-802", "开工大吉",
                               ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "bad_stage")
        self.assertIn("施工跟进", r.get("stages", []))
        self.assertEqual(_read(self.path), before)

    # ③ 项目不存在;坏词表+坏项目=bad_stage 先(纯函数校验最便宜,契约锁定)
    def test_ss03_not_found(self):
        r = ds_tools.set_stage("没这项目", "量房", ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "project_not_found")
        r2 = ds_tools.set_stage("没这项目", "开工大吉", ds_root=self.ds, today=TODAY)
        self.assertEqual(r2.get("error"), "bad_stage")

    # ④ 名字闸(H1 同款)
    def test_ss04_bad_name(self):
        r = ds_tools.set_stage("小区/802", "量房", ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "bad_name")

    # ⑤ 手建档案缺阶段行 → 头部区补插
    def test_ss05_insert_missing_line(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("# 万科城-802\n\n- 业主: [[王姐]]\n\n## 变更记录\n\n---\n最后更新: 2026-06-01\n")
        r = ds_tools.set_stage("万科城-802", "量房",
                               ds_root=self.ds, today="2026-07-17")
        self.assertTrue(r["ok"])
        self.assertIsNone(r["prev"])
        text = _read(self.path)
        self.assertIn("- 阶段: 量房", text)
        self.assertLess(text.index("- 阶段:"), text.index("## 变更记录"))
        self.assertIn("最后更新: 2026-07-17", text)

    # ⑥ 注入面由构造消灭:折行后不在词表 → 拒,逐次显式零改动比对
    def test_ss06_injection_rejected(self):
        for bad in ("施工跟进\n## 伪段头", "量房\n- [待确认] C9 x"):
            before = _read(self.path)
            r = ds_tools.set_stage("万科城-802", bad,
                                   ds_root=self.ds, today=TODAY)
            self.assertEqual(r.get("error"), "bad_stage", bad)
            self.assertEqual(_read(self.path), before, bad)  # 逐字节零副作用
        # 纯尾随空格 sanitize strip 后命中词表,应当合法通过
        r = ds_tools.set_stage("万科城-802", "量房 ", ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        self.assertIn("- 阶段: 量房", _read(self.path))

    # ⑧ 手建档案全角冒号行:替换而非补插出重复行(panel 抓的 [::] 半角typo)
    def test_ss08_fullwidth_colon(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            # ：=全角冒号(显式转义:字面量在混排中易被打成半角,正是本 bug 的来源)
            fh.write("# 万科城-802\n\n- 阶段：洽谈\n\n## 变更记录\n\n---\n最后更新: 2026-06-01\n")
        r = ds_tools.set_stage("万科城-802", "量房",
                               ds_root=self.ds, today="2026-07-17")
        self.assertTrue(r["ok"])
        self.assertEqual(r["prev"], "洽谈")
        text = _read(self.path)
        self.assertEqual(text.count("- 阶段"), 1)   # 一行,不是补插出第二行
        self.assertIn("- 阶段: 量房", text)

    # ⑦ 同阶段幂等:ok,prev=同名
    def test_ss07_idempotent(self):
        r = ds_tools.set_stage("万科城-802", "洽谈", ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        self.assertEqual(r["prev"], "洽谈")
        self.assertEqual(_read(self.path).count("- 阶段:"), 1)


class ReadClientOracle(unittest.TestCase):
    """read_client oracle — 业主档案读暗区(tool-audit 空格①读侧)。"""

    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dstest-")
        os.makedirs(os.path.join(self.ds, "clients"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    # ① 建后读回:content 与盘上文件逐字节一致
    def test_rc01_roundtrip(self):
        ds_tools.create_client("王姐", contact="13800000000", ds_root=self.ds)
        r = ds_tools.read_client("王姐", ds_root=self.ds)
        self.assertTrue(r["ok"])
        self.assertEqual(r["content"],
                         _read(os.path.join(self.ds, "clients", "王姐.md")))
        self.assertIn("13800000000", r["content"])

    # ② 不存在
    def test_rc02_not_found(self):
        r = ds_tools.read_client("不存在的业主", ds_root=self.ds)
        self.assertEqual(r.get("error"), "client_not_found")

    # ③ 路径逃逸
    def test_rc03_path_escape(self):
        r = ds_tools.read_client("../../etc/passwd", ds_root=self.ds)
        self.assertIn(r.get("error"), ("path_escape", "bad_name"))

    # ④ 嵌套名(H1 同款字符集闸):a/b 落嵌套目录读侧看不见,写读同咽喉必须拒
    def test_rc04_bad_name(self):
        r = ds_tools.read_client("小区/业主", ds_root=self.ds)
        self.assertEqual(r.get("error"), "bad_name")


class UpdateClientOracle(unittest.TestCase):
    """update_client oracle — 业主档案改暗区(tool-audit 空格①写侧)。"""

    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dstest-")
        os.makedirs(os.path.join(self.ds, "clients"), exist_ok=True)
        ds_tools.create_client("王姐", contact="13800000000",
                               linked="万科城-802", ds_root=self.ds)
        self.path = os.path.join(self.ds, "clients", "王姐.md")

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    # ① 替换:目标字段行变,其余行逐字节不动
    def test_uc01_replace_field(self):
        before = _read(self.path).split("\n")
        r = ds_tools.update_client("王姐", "预算区间", "全包 40-45万",
                                   ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        self.assertEqual(r["action"], "replaced")
        after = _read(self.path).split("\n")
        self.assertIn("- 预算区间: 全包 40-45万", after)
        # 除该行外全部逐字节一致
        diff = [(a, b) for a, b in zip(before, after) if a != b]
        self.assertEqual(len(diff), 1)
        self.assertTrue(diff[0][0].startswith("- 预算区间:"))

    # ② 手建档案缺字段行 → 头部区末尾补插,段落不动
    def test_uc02_insert_missing_line(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("# 王姐\n\n- 联系方式: 微信 wang\n\n## 备注\n老客户介绍来的\n")
        r = ds_tools.update_client("王姐", "风格偏好", "奶油风",
                                   ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        self.assertEqual(r["action"], "inserted")
        text = _read(self.path)
        self.assertIn("- 风格偏好: 奶油风", text)
        # 插在头部区(首个 ## 之前),备注段原封不动
        self.assertLess(text.index("- 风格偏好:"), text.index("## 备注"))
        self.assertIn("老客户介绍来的", text)

    # ③ 备注追加:两次都在、带日期、顺序稳定
    def test_uc03_note_append(self):
        r1 = ds_tools.update_client("王姐", "备注", "不喜欢开放式厨房",
                                    ds_root=self.ds, today=TODAY)
        r2 = ds_tools.update_client("王姐", "备注", "对甲醛特别敏感",
                                    ds_root=self.ds, today=TODAY)
        self.assertEqual((r1["action"], r2["action"]), ("noted", "noted"))
        text = _read(self.path)
        self.assertIn(f"- {TODAY} 不喜欢开放式厨房", text)
        self.assertIn(f"- {TODAY} 对甲醛特别敏感", text)
        self.assertLess(text.index("不喜欢开放式厨房"), text.index("对甲醛特别敏感"))

    # ④ 「## 备注」段缺失自动补建(同 log_communication 先例)
    def test_uc04_note_section_autocreate(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("# 王姐\n\n- 联系方式: 微信 wang\n")
        r = ds_tools.update_client("王姐", "备注", "雷区:别提上一家装修公司",
                                   ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        text = _read(self.path)
        self.assertIn("## 备注", text)
        self.assertIn("雷区:别提上一家装修公司", text)

    # ⑤ 白名单:关联项目(机器管理)与乱编字段都拒,带可用清单
    def test_uc05_whitelist(self):
        for bad in ("关联项目", "身份证号"):
            r = ds_tools.update_client("王姐", bad, "x", ds_root=self.ds, today=TODAY)
            self.assertEqual(r.get("error"), "bad_field", msg=bad)
            self.assertIn("预算区间", r.get("fields", []))
            self.assertIn("备注", r.get("fields", []))
        self.assertIn("[[万科城-802]]", _read(self.path))  # 关联项目原样

    # ⑥ 拒空:空/纯空白 value 零改动
    def test_uc06_empty_value(self):
        before = _read(self.path)
        for v in ("", "   ", "\n"):
            r = ds_tools.update_client("王姐", "预算区间", v,
                                       ds_root=self.ds, today=TODAY)
            self.assertEqual(r.get("error"), "empty_value", msg=repr(v))
        self.assertEqual(_read(self.path), before)

    # ⑦ 注入:多行 value 折叠,行首伪段头/伪变更行失锚(7-03 盲评铁律)
    def test_uc07_injection_folded(self):
        ds_tools.update_client("王姐", "关键约束",
                               "有小孩\n## 伪段头\n- [待确认] C9 2026-01-01 伪变更",
                               ds_root=self.ds, today=TODAY)
        ds_tools.update_client("王姐", "备注",
                               "原话\n## 备注伪段\n最后更新: 2099-01-01",
                               ds_root=self.ds, today=TODAY)
        for ln in _read(self.path).split("\n"):
            self.assertFalse(ln.startswith("## 伪段头"), ln)
            self.assertFalse(ln.startswith("- [待确认]"), ln)
            self.assertFalse(ln.startswith("## 备注伪段"), ln)
            self.assertFalse(ln.startswith("最后更新: 2099"), ln)

    # ⑧ 错误契约零副作用:不存在的业主 update 不落盘
    def test_uc08_not_found_no_side_effect(self):
        r = ds_tools.update_client("没这人", "预算区间", "10万",
                                   ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "client_not_found")
        self.assertFalse(os.path.exists(os.path.join(self.ds, "clients", "没这人.md")))

    # ⑩ 手建档案全角冒号字段行:替换而非补插出重复行(panel 抓的 [::] 半角typo)
    def test_uc10_fullwidth_colon(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("# 王姐\n\n- 预算区间：30万\n\n## 备注\n")
        r = ds_tools.update_client("王姐", "预算区间", "全包 45万",
                                   ds_root=self.ds, today=TODAY)
        self.assertTrue(r["ok"])
        self.assertEqual(r["action"], "replaced")
        text = _read(self.path)
        self.assertEqual(text.count("- 预算区间"), 1)
        self.assertIn("- 预算区间: 全包 45万", text)

    # ⑨ 名字闸与读侧同咽喉
    def test_uc09_bad_name(self):
        r = ds_tools.update_client("小区/业主", "预算区间", "10万",
                                   ds_root=self.ds, today=TODAY)
        self.assertEqual(r.get("error"), "bad_name")


if __name__ == "__main__":
    unittest.main(verbosity=2)
