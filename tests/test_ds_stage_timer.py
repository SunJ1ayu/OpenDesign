#!/usr/bin/env python3
"""track opendesign-stage-timer 的 oracle —— 主 agent 亲写并拥有,executor off-limits。

覆盖 design.md 的 D1–D4:
  D1  `## 阶段历史` 段 = 当前阶段起始日的**唯一**真相源(头部不加重复字段)
  D3  `set_stage(project, stage, since=None)` 的四格语义表 + 三个校验闸
  D4  `parse_stage_history` / `stage_timer`(读侧,诚实闸)

跑法:  python3 tests/test_ds_stage_timer.py
纯 stdlib、离线、不起端口。

red-check(未实现前该红成什么样):
  `ds_tools.parse_stage_history` / `stage_timer` 不存在 → AttributeError,读侧组全红;
  `set_stage` 不收 `since` → TypeError,写侧组全红;
  既有 `set_stage` 不写段 → 追加类断言全红。

──────────────────────────────────────────────────────────────────────────────
⚠️ 这份判据自己最可能虚在哪(写的时候就想清楚,别等收货):

**「阶段相同 + 无 since ⇒ 流水账一个字不动」那一格。**
如果夹具里段末那条的日期恰好 == today,那么"错误地追加了一条"和"正确地没动"
产出的文件会长得**一模一样**,断言照绿而实现是错的。
⇒ 夹具的段末日期必须是**明显的过去日期**(HIST_LAST = 2026-07-20,today = 2026-08-02),
   并且断言 **`## 阶段历史` 段逐字节相等**,不是断言"天数没变"。
史料:07-24 `columnCount === "3"` 全绿而正文被压成竖排;08-01 又抓到一次同类。
"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_tools  # noqa: E402

TODAY = "2026-08-02"
HIST_LAST = "2026-07-20"       # 段末条目的日期 —— 刻意 != TODAY,见文件头警告
HIST_PREV = "2026-06-01"       # 倒数第二条
DAYS_SINCE_LAST = 13           # 2026-07-20 → 2026-08-02

KEY = "云溪台-1203"
SECTION_HEADER = "## 阶段历史"

# 有阶段历史段的档案(新格式)
PROJ_WITH_HIST = f"""# {KEY}

- 业主: [[王五]]
- 阶段: 方案深化
- 开始日期: {HIST_PREV}

{SECTION_HEADER}

- {HIST_PREV} 洽谈
- {HIST_LAST} 方案深化

## 变更记录

- [待确认] C1 2026-07-25 主卧灯位右移

## 沟通日志

---
最后更新: 2026-07-25
"""

# 旧档案(没有阶段历史段)—— 零迁移与补录的主战场
PROJ_LEGACY = f"""# {KEY}

- 业主: [[王五]]
- 阶段: 方案深化
- 开始日期: {HIST_PREV}

## 变更记录

- [待确认] C1 2026-07-25 主卧灯位右移

## 沟通日志

---
最后更新: 2026-07-25
"""


def _mkroot(body: str = PROJ_WITH_HIST, key: str = KEY) -> str:
    d = tempfile.mkdtemp(prefix="ds_stage_timer_")
    os.makedirs(os.path.join(d, "projects"), exist_ok=True)
    with open(os.path.join(d, "projects", f"{key}.md"), "w", encoding="utf-8") as fh:
        fh.write(body)
    return d


def _md(root: str, key: str = KEY) -> str:
    with open(os.path.join(root, "projects", f"{key}.md"), encoding="utf-8") as fh:
        return fh.read()


def _doc(since: str, stage: str = "方案深化") -> str:
    """构造一份只有一条阶段历史的最小档案 —— 天数边界用,免得被夹具里
    别的日期干扰(段末那条才是被读的)。"""
    return (f"# {KEY}\n\n- 业主: [[王五]]\n- 阶段: {stage}\n\n"
            f"{SECTION_HEADER}\n\n- {since} {stage}\n\n"
            f"## 变更记录\n\n---\n最后更新: 2026-07-25\n")


def _entries(text: str):
    """段内被 ds_tools 认可的条目 —— 直接用被测函数,读写同源。"""
    return ds_tools.parse_stage_history(text)


# ── D4 读侧:parse_stage_history ────────────────────────────────────────────
class ParseStageHistory(unittest.TestCase):
    def test_parses_entries_in_order(self):
        got = ds_tools.parse_stage_history(PROJ_WITH_HIST)
        self.assertEqual(
            [{"date": HIST_PREV, "stage": "洽谈"},
             {"date": HIST_LAST, "stage": "方案深化"}], got,
            "段内两条应按出现顺序(=时序)返回")

    def test_missing_section_is_empty(self):
        self.assertEqual([], ds_tools.parse_stage_history(PROJ_LEGACY))

    def test_skips_malformed_lines_but_keeps_good_ones(self):
        """单行坏不拖垮整段(ds_todo.collect 同哲学)。"""
        text = PROJ_WITH_HIST.replace(
            f"- {HIST_PREV} 洽谈",
            "\n".join([
                "- 2026-6-1 洽谈",          # 日期非零填充 → 跳过
                "- 2026-06-01",             # 缺阶段名 → 跳过
                "- 2026-06-01 开工大吉",     # 阶段名不在词表 → 跳过
                "随便一行不带减号",           # 非条目 → 跳过
                f"- {HIST_PREV} 洽谈",       # 唯一合法的
            ]))
        self.assertEqual(
            [{"date": HIST_PREV, "stage": "洽谈"},
             {"date": HIST_LAST, "stage": "方案深化"}],
            ds_tools.parse_stage_history(text))

    def test_section_boundary_isolates_other_sections(self):
        """段界 = 下一个 `## ` / `---`:变更记录里的行、页脚都不许漏进来。"""
        got = ds_tools.parse_stage_history(PROJ_WITH_HIST)
        self.assertTrue(all(e["stage"] in ds_tools.PROJECT_STAGES for e in got))
        self.assertEqual(2, len(got), "只收段内的两条,不许把别段的 `- ` 行算进来")


# ── D4 读侧:stage_timer(诚实闸) ──────────────────────────────────────────
class StageTimer(unittest.TestCase):
    def test_reads_last_entry(self):
        r = ds_tools.stage_timer(PROJ_WITH_HIST, today=TODAY)
        self.assertEqual(HIST_LAST, r["since"])
        self.assertEqual(DAYS_SINCE_LAST, r["days"],
                         "天数按注入的 today 算,不许依赖机器时区/UTC(0.35 栽过)")

    def test_header_mismatch_returns_unknown_not_a_wrong_number(self):
        """段末阶段名 != 头部 `- 阶段:` ⇒ 起始日不可信 ⇒ 说"不知道",不给假数字。"""
        text = PROJ_WITH_HIST.replace("- 阶段: 方案深化", "- 阶段: 效果图")
        r = ds_tools.stage_timer(text, today=TODAY)
        self.assertIsNone(r["since"])
        self.assertIsNone(r["days"])

    def test_missing_section_is_unknown(self):
        r = ds_tools.stage_timer(PROJ_LEGACY, today=TODAY)
        self.assertIsNone(r["since"])
        self.assertIsNone(r["days"])

    def test_all_lines_malformed_is_unknown(self):
        text = PROJ_WITH_HIST.replace(f"- {HIST_PREV} 洽谈", "- 坏行") \
                             .replace(f"- {HIST_LAST} 方案深化", "- 又一条坏行")
        r = ds_tools.stage_timer(text, today=TODAY)
        self.assertIsNone(r["since"])
        self.assertIsNone(r["days"])

    def test_never_falls_back_to_start_date(self):
        """**不许拿建档日期顶替**(proposal Non-goals 的硬约束):
        旧档案有 `- 开始日期: 2026-06-01`,读侧绝不能把它当阶段起始日。"""
        r = ds_tools.stage_timer(PROJ_LEGACY, today=TODAY)
        self.assertIsNone(r["since"], "拿开始日期顶替 = 把「建档三个月」算成阶段泡了三个月")

    def test_read_does_not_touch_the_file(self):
        """旧档案零迁移:读一次不许改盘(逐字节)。"""
        root = _mkroot(PROJ_LEGACY)
        before = _md(root)
        ds_tools.list_projects(ds_root=root, today=TODAY)
        ds_tools.read_project(KEY, ds_root=root)
        self.assertEqual(before, _md(root), "读侧写盘 = 静默迁移,不许")


# ── D4 读侧:天数算法的边界 ────────────────────────────────────────────────
class DaysBoundaries(unittest.TestCase):
    """**只测"当天"会把 off-by-one 藏住**(gpt-5.6-sol 规划双出点名的骗过面)。

    天数口径 = **日历日相减**,不是 24 小时滚动:当天进入 = 0 天,隔一天 = 1 天。
    全部注入 today,不依赖机器时区(0.35 那单在 UTC 上栽过)。"""

    def _days(self, since: str, today: str):
        return ds_tools.stage_timer(_doc(since), today=today)["days"]

    def test_same_day_is_zero_not_one(self):
        self.assertEqual(0, self._days("2026-08-02", "2026-08-02"),
                         "当天进入必须是 0 天;算成 1 天就是 off-by-one")

    def test_next_day_is_one(self):
        self.assertEqual(1, self._days("2026-08-01", "2026-08-02"))

    def test_across_month_end(self):
        # 2026 非闰年,2 月 28 天:02-28 → 03-03 = 3 天
        self.assertEqual(3, self._days("2026-02-28", "2026-03-03"))

    def test_across_leap_day(self):
        # 2024 闰年,2 月 29 天:02-28 → 03-01 = 2 天(不是 1 天)
        self.assertEqual(2, self._days("2024-02-28", "2024-03-01"),
                         "闰日必须被算进去 —— 手写 30/31 天的月表会在这里错")

    def test_across_year_boundary(self):
        self.assertEqual(1, self._days("2025-12-31", "2026-01-01"))

    def test_long_span(self):
        # 一整年(2025 非闰年)
        self.assertEqual(365, self._days("2025-08-02", "2026-08-02"))


# ── D3 写侧:语义表四格 ─────────────────────────────────────────────────────
class SetStageSemantics(unittest.TestCase):
    def test_grid1_different_stage_no_since_appends_today(self):
        root = _mkroot()
        r = ds_tools.set_stage(KEY, "效果图", ds_root=root, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual("方案深化", r.get("prev"))
        self.assertEqual(TODAY, r.get("since"))
        self.assertEqual(0, r.get("days"))
        text = _md(root)
        self.assertIn("- 阶段: 效果图", text)
        self.assertEqual(
            [{"date": HIST_PREV, "stage": "洽谈"},
             {"date": HIST_LAST, "stage": "方案深化"},
             {"date": TODAY, "stage": "效果图"}], _entries(text),
            "换阶段 = 追加一条,旧条目一条不许动")
        self.assertIn(f"最后更新: {TODAY}", text, "页脚照旧 bump")

    def test_grid2_different_stage_with_since_appends_that_date(self):
        root = _mkroot()
        r = ds_tools.set_stage(KEY, "效果图", since="2026-07-28",
                               ds_root=root, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual("2026-07-28", r.get("since"))
        self.assertEqual(5, r.get("days"), "2026-07-28 → 2026-08-02 = 5 天")
        self.assertEqual(
            [{"date": HIST_PREV, "stage": "洽谈"},
             {"date": HIST_LAST, "stage": "方案深化"},
             {"date": "2026-07-28", "stage": "效果图"}], _entries(_md(root)))

    def test_grid3_same_stage_no_since_is_strict_noop_whole_file(self):
        """★ 防误点重置计时:重复点同一个阶段 ⇒ **整个文件逐字节不动**。

        比"段不动"更严:页脚 `最后更新` 也不许 bump。否则弱模型多调一次
        会把「⛑ N 天没动静」也洗成零 —— 一次误点毁掉的是**两个**指标。
        已核既有判据 `test_ds_tools.py::test_ss07_idempotent` 没断言页脚 bump,
        所以这条不与任何既有考卷冲突。
        (夹具段末日期 != today,所以"错误追加一条"与"正确没动"产出不同 —— 见文件头。)"""
        root = _mkroot()
        before = _md(root)
        r = ds_tools.set_stage(KEY, "方案深化", ds_root=root, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        after = _md(root)
        self.assertEqual(before, after,
                         "阶段没变还写盘 = 既重置计时风险,又洗掉「N 天没动静」")
        self.assertIn("最后更新: 2026-07-25", after, "页脚必须还是原来那天,不许 bump")
        self.assertEqual(HIST_LAST, r.get("since"), "回传的仍是原起始日")
        self.assertEqual(DAYS_SINCE_LAST, r.get("days"))
        self.assertEqual(2, len(_entries(after)), "绝不许追加第二条「方案深化」")

    def test_grid4_same_stage_with_since_edits_last_entry_not_appends(self):
        """补录/纠正入口:只改段末那条的日期,不新增条目。"""
        root = _mkroot()
        r = ds_tools.set_stage(KEY, "方案深化", since="2026-07-10",
                               ds_root=root, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual("2026-07-10", r.get("since"))
        self.assertEqual(23, r.get("days"), "2026-07-10 → 2026-08-02 = 23 天")
        self.assertEqual(
            [{"date": HIST_PREV, "stage": "洽谈"},
             {"date": "2026-07-10", "stage": "方案深化"}], _entries(_md(root)),
            "改最后一条,不是追加第三条")

    def test_grid4_on_legacy_file_creates_section_and_backfills(self):
        """★ 旧项目补录的主路径:段不存在 + 阶段没变 + 给了 since ⇒ 建段写一条。
        用户界面上「设起始日」和助手说「这项目是 7 月 20 号进的方案深化」走的就是这条。"""
        root = _mkroot(PROJ_LEGACY)
        r = ds_tools.set_stage(KEY, "方案深化", since=HIST_LAST,
                               ds_root=root, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(HIST_LAST, r.get("since"))
        self.assertEqual(DAYS_SINCE_LAST, r.get("days"))
        text = _md(root)
        self.assertEqual([{"date": HIST_LAST, "stage": "方案深化"}], _entries(text))
        self.assertIn("- 阶段: 方案深化", text, "头部不许被这条补录改坏")

    def test_legacy_file_stage_change_creates_section_with_one_entry(self):
        """旧档案换阶段:旧阶段何时开始无从得知 ⇒ 只写新阶段一条,不编造历史。"""
        root = _mkroot(PROJ_LEGACY)
        r = ds_tools.set_stage(KEY, "施工图", ds_root=root, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual([{"date": TODAY, "stage": "施工图"}], _entries(_md(root)),
                         "不许替旧阶段编一个起始日")

    def test_section_is_created_before_changes_section(self):
        """段落落点:`## 阶段历史` 在 `## 变更记录` 之前(design D1)。"""
        root = _mkroot(PROJ_LEGACY)
        ds_tools.set_stage(KEY, "施工图", ds_root=root, today=TODAY)
        text = _md(root)
        self.assertLess(text.index(SECTION_HEADER), text.index("## 变更记录"))

    def test_existing_sections_survive_creation(self):
        """补建段不许打坏既有段:变更记录/沟通日志/页脚原样还在,变更行仍可被解析。"""
        root = _mkroot(PROJ_LEGACY)
        ds_tools.set_stage(KEY, "施工图", ds_root=root, today=TODAY)
        text = _md(root)
        self.assertIn("- [待确认] C1 2026-07-25 主卧灯位右移", text)
        self.assertIn("## 沟通日志", text)
        self.assertIn("最后更新:", text)

    def test_empty_string_since_means_none(self):
        """`""` 与 None 同义(照 set_due_date 既有口径)⇒ 走"无 since"那两格,
        同阶段时同样是**整个文件**严格 no-op。"""
        root = _mkroot()
        before = _md(root)
        r = ds_tools.set_stage(KEY, "方案深化", since="", ds_root=root, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(before, _md(root))


# ── D3 写侧:三个校验闸(拒绝时文件逐字节不变) ─────────────────────────────
class SinceValidation(unittest.TestCase):
    def _rejects(self, since, code, today=TODAY, stage="效果图"):
        root = _mkroot()
        before = _md(root)
        r = ds_tools.set_stage(KEY, stage, since=since, ds_root=root, today=today)
        self.assertEqual(code, r.get("error"), r)
        self.assertNotIn("ok", r, "拒绝的调用不许同时报 ok")
        self.assertEqual(before, _md(root),
                         "校验不过就写盘 = 半截写入,档案会自相矛盾")

    def test_invalid_format(self):
        for bad in ("2026-8-2", "26-08-02", "2026/08/02", "昨天", "2026-08-02T00:00",
                    " 2026-08-02", "2026-08-02 "):
            with self.subTest(bad=bad):
                self._rejects(bad, "invalid_since")

    def test_invalid_calendar_date(self):
        for bad in ("2026-13-01", "2026-02-30", "2026-00-10"):
            with self.subTest(bad=bad):
                self._rejects(bad, "invalid_since")

    def test_future_is_rejected(self):
        self._rejects("2026-08-03", "since_in_future")

    def test_today_itself_is_allowed(self):
        """边界:== today 是合法的(只拒"晚于今天")。"""
        root = _mkroot()
        r = ds_tools.set_stage(KEY, "效果图", since=TODAY, ds_root=root, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(0, r.get("days"))

    def test_append_earlier_than_last_entry_is_rejected(self):
        """追加场景的下限 = 段末那条的日期(否则"最后一条"不再等于"最新")。"""
        self._rejects("2026-07-19", "since_before_prev")

    def test_append_equal_to_last_entry_is_allowed(self):
        """边界:同一天连推两个阶段是真事的(量房当天出平面),不许拒。"""
        root = _mkroot()
        r = ds_tools.set_stage(KEY, "效果图", since=HIST_LAST,
                               ds_root=root, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(3, len(_entries(_md(root))))

    def test_edit_last_earlier_than_second_to_last_is_rejected(self):
        """改末条场景的下限 = **倒数第二条**(HIST_PREV),不是段末自己。"""
        self._rejects("2026-05-31", "since_before_prev", stage="方案深化")

    def test_edit_last_between_prev_and_itself_is_allowed(self):
        """改末条可以往前挪,只要不越过倒数第二条 —— 补录纠错的正常用法。"""
        root = _mkroot()
        r = ds_tools.set_stage(KEY, "方案深化", since=HIST_PREV,
                               ds_root=root, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual([{"date": HIST_PREV, "stage": "洽谈"},
                          {"date": HIST_PREV, "stage": "方案深化"}],
                         _entries(_md(root)))

    def test_bad_stage_still_rejected_and_checked_before_writing(self):
        """既有词表闸不许被 since 绕过。"""
        root = _mkroot()
        before = _md(root)
        r = ds_tools.set_stage(KEY, "开工大吉", since="2026-07-25",
                               ds_root=root, today=TODAY)
        self.assertEqual("bad_stage", r.get("error"), r)
        self.assertEqual(before, _md(root))


# ── 不变量:头部与段末永远一致(防"两边一起错") ────────────────────────────
class HeaderSectionInvariant(unittest.TestCase):
    def test_sequence_of_writes_never_desyncs(self):
        """任意一串写之后,`stage_timer` 都不该因 mismatch 返回 None ——
        头部 `- 阶段:` 与段末条目的阶段名由同一次写保证一致。
        (这是锚断言:没有它,"头部和段一起写错成同一个错值"会照绿。)"""
        root = _mkroot(PROJ_LEGACY)
        seq = [("施工图", None), ("施工图", "2026-07-15"), ("施工交底", None),
               ("施工交底", None), ("软装", "2026-08-01")]
        for stage, since in seq:
            r = ds_tools.set_stage(KEY, stage, since=since, ds_root=root, today=TODAY)
            self.assertTrue(r.get("ok"), (stage, since, r))
            text = _md(root)
            t = ds_tools.stage_timer(text, today=TODAY)
            self.assertIsNotNone(t["since"], f"写完 {stage}/{since} 后头部与段对不上了")
            entries = ds_tools.parse_stage_history(text)
            self.assertEqual(stage, entries[-1]["stage"])
            self.assertEqual(t["since"], entries[-1]["date"])
            # 锚:头部字段本身也要是这个阶段(别只看段)
            self.assertIn(f"- 阶段: {stage}", text)
        # 时序单调(校验闸的累积效果)
        dates = [e["date"] for e in ds_tools.parse_stage_history(_md(root))]
        self.assertEqual(sorted(dates), dates, "流水账日期必须非递减")


# ── 建档:create_project 写首条 ─────────────────────────────────────────────
class CreateProjectWritesFirstEntry(unittest.TestCase):
    def test_new_project_has_section_with_today(self):
        d = tempfile.mkdtemp(prefix="ds_stage_timer_new_")
        r = ds_tools.create_project("新项目-101", client="赵六", stage="洽谈",
                                    ds_root=d, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        text = _md(d, "新项目-101")
        self.assertEqual([{"date": TODAY, "stage": "洽谈"}],
                         ds_tools.parse_stage_history(text),
                         "建档当天进该阶段是真事实,不是编造")
        self.assertLess(text.index(SECTION_HEADER), text.index("## 变更记录"))
        t = ds_tools.stage_timer(text, today=TODAY)
        self.assertEqual(TODAY, t["since"])
        self.assertEqual(0, t["days"])

    def test_non_default_stage_is_recorded(self):
        d = tempfile.mkdtemp(prefix="ds_stage_timer_new2_")
        ds_tools.create_project("新项目-102", stage="施工图", ds_root=d, today=TODAY)
        self.assertEqual([{"date": TODAY, "stage": "施工图"}],
                         ds_tools.parse_stage_history(_md(d, "新项目-102")))


# ── 读侧透出:list_projects / read_project ─────────────────────────────────
class ReadSideExposure(unittest.TestCase):
    def test_list_projects_exposes_since_and_days(self):
        root = _mkroot()
        r = ds_tools.list_projects(ds_root=root, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        p = next(x for x in r["projects"] if x["project"] == KEY)
        self.assertEqual(HIST_LAST, p["stage_since"])
        self.assertEqual(DAYS_SINCE_LAST, p["stage_days"])

    def test_list_projects_legacy_is_null_not_zero(self):
        """旧档案要显式"未记录"(None),**不是 0** —— 0 会在界面上显示成「0 天」。"""
        root = _mkroot(PROJ_LEGACY)
        p = ds_tools.list_projects(ds_root=root, today=TODAY)["projects"][0]
        self.assertIsNone(p["stage_since"])
        self.assertIsNone(p["stage_days"])

    def test_read_project_exposes_since_and_days(self):
        """助手拿到算好的天数就不用自己算 —— due-writer 单已证它会算错相对日期。"""
        root = _mkroot()
        r = ds_tools.read_project(KEY, ds_root=root, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(HIST_LAST, r["stage_since"])
        self.assertEqual(DAYS_SINCE_LAST, r["stage_days"])
        self.assertIn("content", r, "既有 content 字段不许丢")


if __name__ == "__main__":
    unittest.main(verbosity=2)
