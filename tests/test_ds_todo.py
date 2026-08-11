#!/usr/bin/env python3
"""ds_todo 特征化测试(golden)+ list_todos 错误路径 — track opendesign-windows-prep T2。

跑法:  python3 tests/test_ds_todo.py
golden 锁的是 2026-07-03 时 Python 版的既定行为(bash 原版已不存在,无从对照);
DS_TODAY 注入冻结"今天",保证跨日稳定。
"""
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # design-studio/
BIN = os.path.join(ROOT, "bin")
sys.path.insert(0, BIN)
import ds_todo  # noqa: E402
import ds_tools  # noqa: E402

TODAY = date(2026, 7, 3)

A_OPEN = """# a-open

## 变更记录
- [待确认] C1 2026-06-20 改推拉门
- [已完成] C2 2026-06-18 完事

---
最后更新: 2026-07-02
"""

B_STALE = """# b-stale

- [已关闭] C1 2026-06-01 旧事

---
最后更新: 2026-06-20
"""

C_CLEAN = """# c-clean

- [已完成] C1 2026-06-30 完事

---
最后更新: 2026-07-01
"""

GOLDEN_MIXED = """== 未关闭事项(待确认 / 进行中) ==
▸ a-open
    4:- [待确认] C1 2026-06-20 改推拉门

== 超过 7 天未更新的项目 ==
▸ b-stale — 13天未更新 (最后 2026-06-20)
"""

GOLDEN_CLEAN = """== 未关闭事项(待确认 / 进行中) ==
  (无)

== 超过 7 天未更新的项目 ==
  (无)
"""

GOLDEN_OPEN_ONLY = """== 未关闭事项(待确认 / 进行中) ==
▸ a-open
    4:- [待确认] C1 2026-06-20 改推拉门

== 超过 7 天未更新的项目 ==
  (无)
"""


def _mkroot(files: dict) -> str:
    d = tempfile.mkdtemp(prefix="ds_todo_test_")
    proj = os.path.join(d, "projects")
    os.makedirs(proj)
    for name, text in files.items():
        with open(os.path.join(proj, name), "w", encoding="utf-8") as fh:
            fh.write(text)
    return d


class TestDsTodo(unittest.TestCase):

    # ① golden:未关闭 + 超期同时在
    def test_01_golden_mixed(self):
        root = _mkroot({"a-open.md": A_OPEN, "b-stale.md": B_STALE, "c-clean.md": C_CLEAN})
        self.assertEqual(ds_todo.render(root, 7, TODAY), GOLDEN_MIXED)

    # ② golden:全干净
    def test_02_golden_clean(self):
        root = _mkroot({"c-clean.md": C_CLEAN})
        self.assertEqual(ds_todo.render(root, 7, TODAY), GOLDEN_CLEAN)

    # ③ golden:只有未关闭,无超期
    def test_03_golden_open_only(self):
        root = _mkroot({"a-open.md": A_OPEN})
        self.assertEqual(ds_todo.render(root, 7, TODAY), GOLDEN_OPEN_ONLY)

    # ④ CLI 薄入口:输出与 render 一致,DS_TODAY 生效
    def test_04_cli_entry(self):
        root = _mkroot({"a-open.md": A_OPEN, "b-stale.md": B_STALE, "c-clean.md": C_CLEAN})
        env = dict(os.environ, DS_ROOT=root, DS_TODAY="2026-07-03")
        proc = subprocess.run([sys.executable, os.path.join(BIN, "ds-todo"), "7"],
                              capture_output=True, encoding="utf-8", env=env, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, GOLDEN_MIXED)

    # ⑤ list_todos 直调:ok + 文本与 render 一致(DS_TODAY 冻结)
    def test_05_list_todos_ok(self):
        root = _mkroot({"a-open.md": A_OPEN, "b-stale.md": B_STALE})
        os.environ["DS_TODAY"] = "2026-07-03"
        try:
            r = ds_tools.list_todos(7, ds_root=root)
        finally:
            del os.environ["DS_TODAY"]
        self.assertTrue(r.get("ok"))
        self.assertIn("▸ a-open", r["text"])
        self.assertIn("▸ b-stale — 13天未更新", r["text"])

    # ⑦ collect 结构化输出(track opendesign-workbench T1):字段齐全、与 golden 同源
    def test_07_collect_structured(self):
        root = _mkroot({"a-open.md": A_OPEN, "b-stale.md": B_STALE, "c-clean.md": C_CLEAN})
        d = ds_todo.collect(root, 7, TODAY)
        self.assertEqual(d["today"], "2026-07-03")
        self.assertEqual(d["stale_days"], 7)
        self.assertEqual(d["open"], [{
            "project": "a-open", "line": 4, "status": "待确认", "cnum": 1,
            "date": "2026-06-20", "space": None, "text": "改推拉门", "due": None,
            "raw": "- [待确认] C1 2026-06-20 改推拉门",
            "batch": None,  # T4b:没有 `## 批次` 段的旧档案 → 恒 None(零迁移)
        }])
        self.assertEqual(d["stale"], [{"project": "b-stale", "days": 13,
                                       "last": "2026-06-20"}])

    # ⑧ collect 容忍残缺变更行:状态在、C/日期缺 → None,不炸不丢
    def test_08_collect_partial_line(self):
        root = _mkroot({"x.md": "# x\n- [进行中] 没编号没日期\n\n---\n最后更新: 2026-07-03\n"})
        d = ds_todo.collect(root, 7, TODAY)
        self.assertEqual(len(d["open"]), 1)
        it = d["open"][0]
        self.assertEqual(it["status"], "进行中")
        self.assertIsNone(it["cnum"])
        self.assertIsNone(it["date"])
        self.assertEqual(it["text"], "没编号没日期")

    # ⑨ 空间字段(track p4 T1):【空间】前缀 → space 键;旧行 space=None 且 text 不变
    def test_09_parse_space(self):
        c = ds_todo.parse_change("- [待确认] C3 2026-07-12 【玄关】柜子改到 2.4 米")
        self.assertEqual(c["space"], "玄关")
        self.assertEqual(c["text"], "柜子改到 2.4 米")
        self.assertEqual(c["cnum"], 3)
        # 旧格式行(无【】前缀):向后兼容,text 一个字不动
        old = ds_todo.parse_change("- [进行中] C2 2026-06-19 玄关增加到顶储物柜")
        self.assertIsNone(old["space"])
        self.assertEqual(old["text"], "玄关增加到顶储物柜")
        # 契约:头部【1-16字】一律读作空间槽——0.4.0 之前正文恰好以短【】开头的旧行,
        # 解析后 text 会剥掉该前缀(磁盘一字不动,仅展示归组变化;panel p4 subglm 指出后钉死)
        legacy = ds_todo.parse_change("- [进行中] C2 2026-06-19 【玄关】增加到顶储物柜")
        self.assertEqual(legacy["space"], "玄关")
        self.assertEqual(legacy["text"], "增加到顶储物柜")
        # 正文里出现的孤立】留在 text 里,不破坏解析
        tail = ds_todo.parse_change("- [待确认] C5 2026-07-12 【玄关】柜子改】到 2.4 米")
        self.assertEqual(tail["space"], "玄关")
        self.assertEqual(tail["text"], "柜子改】到 2.4 米")

    # ⑩ 空间字段结构不可破:空/超长【】不吞正文;collect 透传 space
    def test_10_space_structure(self):
        # 空【】不是合法空间标注 → 整段落回 text
        c = ds_todo.parse_change("- [待确认] C1 2026-07-12 【】留空括号")
        self.assertIsNone(c["space"])
        self.assertEqual(c["text"], "【】留空括号")
        # 超过 16 字的【…】不按空间解析(空间是短词表,长括号=正文自带)
        long = "【" + "长" * 17 + "】尾巴"
        c2 = ds_todo.parse_change(f"- [待确认] C1 2026-07-12 {long}")
        self.assertIsNone(c2["space"])
        self.assertEqual(c2["text"], long)
        # collect 透传:待办条目带 space
        root = _mkroot({"s.md": "# s\n- [待确认] C1 2026-07-01 【客厅】电视墙改岩板\n"
                                "\n---\n最后更新: 2026-07-02\n"})
        d = ds_todo.collect(root, 7, TODAY)
        self.assertEqual(d["open"][0]["space"], "客厅")
        self.assertEqual(d["open"][0]["text"], "电视墙改岩板")

    # ⑪ track opendesign-owner-review-0808:第五态「已删除」(delete_change 专用出口,
    # 不进 STATUSES,只在 ds_todo 这层的解析词表里)。正则必须认得它——不认得就等于
    # 这一行对全仓所有扫描它的代码"隐形"(不是被过滤掉,是解析直接失败),design.md
    # 明确要求"可见但被过滤",不是"对解析器隐形"。
    def test_11_deleted_status_recognized_by_parser(self):
        c = ds_todo.parse_change("- [已删除] C9 2026-07-01 【玄关】误建的一条")
        self.assertIsNotNone(c, "已删除 状态必须能被 parse_change 命中")
        self.assertEqual(c["status"], "已删除")
        self.assertEqual(c["cnum"], 9)
        self.assertEqual(c["date"], "2026-07-01")
        self.assertEqual(c["space"], "玄关")
        self.assertEqual(c["text"], "误建的一条")
        self.assertIn("已删除", ds_todo.STATUS_WORDS)

    # ⑫ 已删除的条目不出现在 list_todos 的未办结列表里(哪怕它是唯一一行)
    def test_12_deleted_excluded_from_open(self):
        root = _mkroot({"only-deleted.md":
                        "# only-deleted\n\n## 变更记录\n"
                        "- [已删除] C1 2026-07-01 误建的一条\n"
                        "\n---\n最后更新: 2026-07-01\n"})
        d = ds_todo.collect(root, 7, TODAY)
        self.assertEqual(d["open"], [])  # 全项目唯一一行也是已删除 → 未办结空表,不报错

    # ⑬ 混合场景:已删除与其它状态并存,只有已删除被过滤,其余照常
    def test_13_deleted_mixed_with_open(self):
        root = _mkroot({"mix.md":
                        "# mix\n\n## 变更记录\n"
                        "- [待确认] C1 2026-07-01 正常待办\n"
                        "- [已删除] C2 2026-07-01 误建的一条\n"
                        "\n---\n最后更新: 2026-07-01\n"})
        d = ds_todo.collect(root, 7, TODAY)
        cnums = [it["cnum"] for it in d["open"]]
        self.assertEqual(cnums, [1])

    # ⑥ list_todos 错误路径:核心崩溃 → 显式 error,不得静默 ok:true
    def test_06_list_todos_error(self):
        orig = ds_todo.render
        ds_todo.render = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            r = ds_tools.list_todos(7, ds_root="/nonexistent")
        finally:
            ds_todo.render = orig
        self.assertNotIn("ok", r)
        self.assertIn("error", r)
        self.assertIn("boom", r["error"])

# ── T4b 读侧:collect 把批次附到每条待办上 ────────────────────────────────────
# 主 agent 亲写,执行腿逐字节 off-limits。设计见
# tracks/opendesign-due-picker/design-t4b.md。
#
# 契约:解析可选段 `## 批次` 的 `- C{起}-C{止} {日期} {标题}` 行,给每个 open item 附
#   batch = {"id": "C2-C4", "title": "效果图修改"};不在任何区间里的条目 batch=None。
#   段不存在(旧档案)= 全部 None,零迁移。坏行忽略,不许拖垮整个 collect。

BATCH_DOC = """# p1

- 业主: [[张三]]

## 变更记录
- [待确认] C1 2026-07-28 效果图改浅色
- [待确认] C2 2026-07-28 餐桌换圆桌
- [进行中] C3 2026-07-28 厨房加插座
- [待确认] C4 2026-07-28 没人认领的一条

## 批次
- C1-C2 2026-07-28 效果图修改
- C3-C3 2026-07-28 水电改动

---
最后更新: 2026-07-28
"""


class TestBatchSection(unittest.TestCase):

    def _open(self, doc="p1.md", text=BATCH_DOC):
        root = _mkroot({doc: text})
        return {it["cnum"]: it for it in ds_todo.collect(root, 7, TODAY)["open"]}

    def test_b01_items_get_their_batch(self):
        got = self._open()
        self.assertEqual(got[1]["batch"], {"id": "C1-C2", "title": "效果图修改"})
        self.assertEqual(got[2]["batch"], {"id": "C1-C2", "title": "效果图修改"})
        self.assertEqual(got[3]["batch"], {"id": "C3-C3", "title": "水电改动"})

    def test_b02_item_outside_any_range_is_none(self):
        self.assertIsNone(self._open()[4]["batch"], "没被任何批次覆盖的条目 batch=None")

    def test_b03_no_section_means_all_none(self):
        text = BATCH_DOC.split("## 批次")[0] + "---\n最后更新: 2026-07-28\n"
        got = self._open("old.md", text)
        self.assertTrue(all(it["batch"] is None for it in got.values()),
                        "旧档案没有批次段 → 全 None,零迁移")

    def test_b04_bad_lines_ignored_not_fatal(self):
        text = BATCH_DOC.replace("- C3-C3 2026-07-28 水电改动",
                                 "- C第三-C啥 不是日期 坏行\n- C3-C3 2026-07-28 水电改动")
        got = self._open("bad.md", text)
        self.assertEqual(got[3]["batch"]["title"], "水电改动", "坏行只被跳过,好行照读")

    def test_b05_batch_line_is_not_a_change(self):
        # 批次行绝不能被当成待办收进来(否则待办页会冒出假条目)
        got = self._open()
        self.assertEqual(sorted(got), [1, 2, 3, 4])

    def test_b06_later_range_wins_on_overlap(self):
        # 手写坏档案可能让区间重叠;取**后写的那条**(与"最后一次命名说了算"一致),
        # 且绝不许抛异常。
        text = BATCH_DOC.replace("- C3-C3 2026-07-28 水电改动",
                                 "- C1-C4 2026-07-28 全都算一批")
        got = self._open("ovl.md", text)
        self.assertEqual(got[1]["batch"]["title"], "全都算一批")
        self.assertEqual(got[4]["batch"]["title"], "全都算一批")


# ── 备注的唯一真相源 = 档案(track opendesign-note-source)──────────────────────
# 业主 08-11:「我觉得还是直接按第一性原理整理掉」。在这之前待办页的备注来自浏览器
# 会话里的 `noted` 映射 —— 刷新就没。契约:`collect()` 的每个未办结条目,若档案的
# `## 变更历史` 段里有它的备注行,就带 `note` 键(**有才带**,与 /changes 同约定)。
#
# 判据写死**具体字符串**,不写成"等于 parse_history 的结果" —— 后者是同源相等题,
# 两边一起漏掉 note 它照样全绿(规划双出点破的假绿形状)。

NOTE_DOC = """# n1

## 变更记录
- [待确认] C1 2026-07-01 主卧衣柜改推拉门
- [进行中] C12 2026-07-01 玄关增加到顶储物柜
- [待确认] C3 2026-07-01 阳台加洗衣柜
- [进行中] 没编号的残缺行

## 变更历史
- C1 改于 2026-07-02｜原:主卧衣柜改平开门
- C1 备注:业主书面确认
- C12 备注:邻居锚,不许被 C1 的正则误伤
- C1 改于 2026-07-02｜原:主卧衣柜改折叠门

---
最后更新: 2026-07-03
"""

# 另一个项目里**同样有 C1 且同样有备注** —— 备注必须按项目内的 cnum 关联,不许串号。
OTHER_DOC = """# n2

## 变更记录
- [待确认] C1 2026-07-01 另一个项目的第一条

## 变更历史
- C1 备注:这条属于 n2,不属于 n1

---
最后更新: 2026-07-03
"""


class TestCollectNote(unittest.TestCase):
    """`/api/todos` 的载荷带持久备注 —— 待办页刷新后还看得见的根据。"""

    def _open(self, files=None):
        root = _mkroot(files or {"n1.md": NOTE_DOC, "n2.md": OTHER_DOC})
        return root, ds_todo.collect(root, 7, TODAY)["open"]

    def _by(self, items, project, cnum):
        hit = [it for it in items if it["project"] == project and it["cnum"] == cnum]
        self.assertEqual(len(hit), 1, f"{project} C{cnum} 应恰好一条")
        return hit[0]

    # ① 有备注 ⇒ 带 note,且等于档案里那行的具体内容
    def test_n01_note_from_archive(self):
        _, items = self._open()
        self.assertEqual(self._by(items, "n1", 1)["note"], "业主书面确认")

    # ② 无备注 ⇒ **没有 note 键**(不是 None、不是空串;与 /changes 同约定)
    def test_n02_absent_when_no_note(self):
        _, items = self._open()
        self.assertNotIn("note", self._by(items, "n1", 3))

    # ③ 邻居锚:C1 的备注不许被 C12 认领,反之亦然(`C1\b` 不匹配 C12)
    def test_n03_neighbour_cnum_not_confused(self):
        _, items = self._open()
        self.assertEqual(self._by(items, "n1", 12)["note"], "邻居锚,不许被 C1 的正则误伤")

    # ④ 跨项目同号不串:n1 的 C1 和 n2 的 C1 各拿各的
    def test_n04_no_cross_project_bleed(self):
        _, items = self._open()
        self.assertEqual(self._by(items, "n1", 1)["note"], "业主书面确认")
        self.assertEqual(self._by(items, "n2", 1)["note"], "这条属于 n2,不属于 n1")

    # ⑤ 残缺行(cnum=None)不许认领任何备注
    def test_n05_partial_line_claims_nothing(self):
        _, items = self._open()
        broken = [it for it in items if it["cnum"] is None]
        self.assertEqual(len(broken), 1)
        self.assertNotIn("note", broken[0])

    # ⑥ 清空之后读不到了 —— 0.83.0 修的"存得进去"与本单修的"读得出来"接上
    def test_n06_cleared_note_disappears_from_collect(self):
        root, items = self._open()
        self.assertEqual(self._by(items, "n1", 1)["note"], "业主书面确认")
        r = ds_tools.edit_change("n1", 1, note="", ds_root=root, today="2026-07-03")
        self.assertTrue(r.get("ok"), r)
        again = ds_todo.collect(root, 7, TODAY)["open"]
        self.assertNotIn("note", self._by(again, "n1", 1))

    # ⑦ 读模型住在 ds_todo:`parse_history` 从这儿导出(ds_todo 不许 import ds_tools,
    #    那是环;test_no_import_cycles 会红)。这条锚住"新家在哪",搬回去就红。
    def test_n07_parse_history_lives_here(self):
        hist = ds_todo.parse_history(NOTE_DOC)
        self.assertEqual(hist[1]["note"], "业主书面确认")
        self.assertEqual([h["old"] for h in hist[1]["history"]],
                         ["主卧衣柜改平开门", "主卧衣柜改折叠门"])
        self.assertEqual(hist[12]["note"], "邻居锚,不许被 C1 的正则误伤")
        self.assertEqual(hist[12]["history"], [])   # C12 有备注、无留痕

    # ⑧ 每个项目文件只解析一次历史段(别写成对每条变更行各解析一遍 = O(n²))
    def test_n08_parses_history_once_per_file(self):
        root = _mkroot({"n1.md": NOTE_DOC})
        calls = []
        real = ds_todo.parse_history

        def counting(text):
            calls.append(len(text))
            return real(text)

        ds_todo.parse_history = counting
        try:
            ds_todo.collect(root, 7, TODAY)
        finally:
            ds_todo.parse_history = real
        self.assertEqual(len(calls), 1, f"n1.md 里有 4 条变更行,历史段只该解析 1 次(实际 {len(calls)})")


if __name__ == "__main__":
    unittest.main(verbosity=2)
