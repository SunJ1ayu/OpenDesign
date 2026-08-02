#!/usr/bin/env python3
"""track opendesign-pkb-lint 的 oracle — 主 agent 拥有,executor off-limits。

覆盖三块:
  T3 ds_lint.lint_pkb  — PKB 自动体检(只读,只报告不修)
  T1 ds_tools.list_projects — 聊天大脑的项目枚举(index.md 的真实替身)
  T4 create_project stage 词表闸(对齐 set_stage)

跑法:  python3 tests/test_ds_lint.py
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
import ds_tools  # noqa: E402
import ds_lint   # noqa: E402  ← 新模块,不存在即全红

TODAY = "2026-07-17"

PROJECT_OK = """# {slug}

- 业主: [[{client}]]
- 阶段: {stage}
- 开始日期: 2026-07-01
- 当前状态: 正常

## 变更记录
{changes}
## 沟通日志

---
最后更新: {updated}
"""

CLIENT_OK = """# {name}

- 联系方式: 微信
- 关联项目: [[{linked}]]

## 备注
"""


def _mk_pkb(base):
    """最小干净 PKB:1 业主 + 1 项目,互相链接,阶段合法,锚不重复。"""
    os.makedirs(os.path.join(base, "projects"))
    os.makedirs(os.path.join(base, "clients"))
    _w(base, "projects/翡翠湾-1801.md", PROJECT_OK.format(
        slug="翡翠湾-1801", client="张三", stage="方案深化",
        changes="- [待确认] C1 2026-07-01 主卧衣柜改推拉门\n",
        updated="2026-07-01"))
    _w(base, "clients/张三.md", CLIENT_OK.format(name="张三", linked="翡翠湾-1801"))
    return base


def _w(base, rel, content, mode="w"):
    path = os.path.join(base, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode, encoding=(None if "b" in mode else "utf-8")) as fh:
        fh.write(content)
    return path


def _checks(result, slug):
    return [f for f in result["findings"] if f["check"] == slug]


class TestLintPkb(unittest.TestCase):
    def setUp(self):
        self.base = _mk_pkb(tempfile.mkdtemp(prefix="dslint-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)

    def lint(self):
        result = ds_lint.lint_pkb(self.base)
        self.assertTrue(result.get("ok"), result)
        self.assertIsInstance(result["findings"], list)
        for f in result["findings"]:
            self.assertIn("check", f)
            self.assertIn("target", f)
            self.assertIn("detail", f)
        return result

    # ── 基线 ──────────────────────────────────────────────────────────
    def test_01_clean_pkb_no_findings(self):
        self.assertEqual(self.lint()["findings"], [])

    def test_02_readonly(self):
        """lint 是只读的:跑完后 PKB 每个文件字节不变。"""
        snap = {}
        for dirpath, _, files in os.walk(self.base):
            for fn in files:
                p = os.path.join(dirpath, fn)
                with open(p, "rb") as fh:
                    snap[p] = fh.read()
        self.lint()
        for p, blob in snap.items():
            with open(p, "rb") as fh:
                self.assertEqual(fh.read(), blob, f"lint 改了 {p}")

    # ── 断链 ──────────────────────────────────────────────────────────
    def test_03_broken_link_in_project(self):
        _w(self.base, "projects/幽灵楼盘.md", PROJECT_OK.format(
            slug="幽灵楼盘", client="不存在的业主", stage="洽谈",
            changes="", updated="2026-07-01"))
        hits = _checks(self.lint(), "broken_link")
        self.assertEqual(len(hits), 1)
        self.assertIn("不存在的业主", hits[0]["detail"])
        self.assertIn("幽灵楼盘", hits[0]["target"])

    def test_03b_empty_client_project_is_not_broken_link(self):
        """track opendesign-intake-simplify:空业主建出来的档案(`- 业主:` 值为空)
        必须**零** broken_link —— 若 create_project 图省事写成 `- 业主: [[]]`,
        这条就红。这是"空业主不写链接"这个决定的判据,不是文案偏好。"""
        r = ds_tools.create_project("云玺台-1203", "", ds_root=self.base,
                                    today="2026-07-25")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(_checks(self.lint(), "broken_link"), [])

    def test_04_link_to_project_is_valid(self):
        """[[X]] 指向 projects/X.md 或 clients/X.md 都算通(clients 的关联项目链)。"""
        self.assertEqual(_checks(self.lint(), "broken_link"), [])

    # ── 重复档案(改名事故形状) ───────────────────────────────────────
    def test_05_duplicate_content(self):
        body = PROJECT_OK.format(slug="万科城-802", client="张三", stage="洽谈",
                                 changes="", updated="2026-07-01")
        _w(self.base, "projects/万科城-802.md", body)
        _w(self.base, "projects/万科城802旧.md", body)  # 同字节内容
        hits = _checks(self.lint(), "duplicate_content")
        self.assertEqual(len(hits), 1)
        joined = hits[0]["target"] + hits[0]["detail"]
        self.assertIn("万科城-802", joined)
        self.assertIn("万科城802旧", joined)

    def test_06_different_content_not_duplicate(self):
        self.assertEqual(_checks(self.lint(), "duplicate_content"), [])

    # ── 坏 stage(手改档案) ──────────────────────────────────────────
    def test_07_bad_stage(self):
        _w(self.base, "projects/手改.md", PROJECT_OK.format(
            slug="手改", client="张三", stage="随便写的阶段",
            changes="", updated="2026-07-01"))
        hits = _checks(self.lint(), "bad_stage")
        self.assertEqual(len(hits), 1)
        self.assertIn("随便写的阶段", hits[0]["detail"])

    def test_08_all_vocab_stages_pass(self):
        for st in ds_tools.PROJECT_STAGES:
            _w(self.base, f"projects/阶段{st}.md", PROJECT_OK.format(
                slug=f"阶段{st}", client="张三", stage=st,
                changes="", updated="2026-07-01"))
        self.assertEqual(_checks(self.lint(), "bad_stage"), [])

    # ── C<n> 锚重复 ───────────────────────────────────────────────────
    def test_09_duplicate_anchor(self):
        _w(self.base, "projects/撞锚.md", PROJECT_OK.format(
            slug="撞锚", client="张三", stage="洽谈",
            changes=("- [待确认] C2 2026-07-01 改灯位\n"
                     "- [进行中] C2 2026-07-02 改插座\n"),
            updated="2026-07-02"))
        hits = _checks(self.lint(), "duplicate_anchor")
        self.assertEqual(len(hits), 1)
        self.assertIn("C2", hits[0]["detail"])
        self.assertIn("撞锚", hits[0]["target"])

    def test_10_anchors_unique_across_files_ok(self):
        """不同项目各自有 C1 不算撞(锚定域是单文件)。"""
        _w(self.base, "projects/另一家.md", PROJECT_OK.format(
            slug="另一家", client="张三", stage="洽谈",
            changes="- [待确认] C1 2026-07-01 拆墙\n", updated="2026-07-01"))
        self.assertEqual(_checks(self.lint(), "duplicate_anchor"), [])

    # ── refs 索引 ─────────────────────────────────────────────────────
    def test_11_refs_dangling_project(self):
        _w(self.base, "refs/图.jpg", "x")
        _w(self.base, "refs-index.md",
           "# 参考图索引\n\n"
           "- [r1] 原木|客厅 | 来源:小红书 | 文件:refs/图.jpg | 用于:早没了的项目 | 备注:\n")
        hits = _checks(self.lint(), "refs_dangling")
        self.assertEqual(len(hits), 1)
        self.assertIn("早没了的项目", hits[0]["detail"])

    def test_12_refs_missing_file(self):
        _w(self.base, "refs-index.md",
           "# 参考图索引\n\n"
           "- [r1] 原木|客厅 | 来源:小红书 | 文件:refs/丢了.jpg | 用于:翡翠湾-1801 | 备注:\n")
        hits = _checks(self.lint(), "refs_missing_file")
        self.assertEqual(len(hits), 1)
        self.assertIn("refs/丢了.jpg", hits[0]["detail"] + hits[0]["target"])

    def test_13_refs_ok_no_findings(self):
        _w(self.base, "refs/图.jpg", "x")
        _w(self.base, "refs-index.md",
           "# 参考图索引\n\n"
           "- [r1] 原木|客厅 | 来源:小红书 | 文件:refs/图.jpg | 用于:翡翠湾-1801 | 备注:\n")
        r = self.lint()
        self.assertEqual(_checks(r, "refs_dangling"), [])
        self.assertEqual(_checks(r, "refs_missing_file"), [])

    # ── workspace 映射 ────────────────────────────────────────────────
    def test_14_workspace_dangling_mapping(self):
        wsroot = os.path.join(self.base, "真工作区")
        os.makedirs(os.path.join(wsroot, "在的夹"))
        _w(self.base, "config/workspace.json", json.dumps({
            "root": wsroot,
            "projects": {"翡翠湾-1801": "在的夹", "幽灵映射": "没这个夹"},
        }, ensure_ascii=False))
        hits = _checks(self.lint(), "workspace_dangling_mapping")
        self.assertEqual(len(hits), 1)
        self.assertIn("幽灵映射", hits[0]["target"] + hits[0]["detail"])

    def test_15_workspace_absent_ok(self):
        """未配置 workspace.json 不算病(未接入工作区是合法状态)。"""
        self.assertEqual(_checks(self.lint(), "workspace_dangling_mapping"), [])

    # ── 废弃 index.md 残留 ────────────────────────────────────────────
    def test_16_deprecated_index(self):
        _w(self.base, "index.md", "# 旧索引\n- [[张三]]\n")
        hits = _checks(self.lint(), "deprecated_index")
        self.assertEqual(len(hits), 1)

    # ── 坏编码不拖垮(M1 先例) ──────────────────────────────────────
    def test_17_unreadable_file_isolated(self):
        with open(os.path.join(self.base, "projects", "坏.md"), "wb") as fh:
            fh.write(b"\xff\xfe\x00 broken \x81")
        r = self.lint()  # 不抛异常
        hits = _checks(r, "unreadable")
        self.assertEqual(len(hits), 1)
        self.assertIn("坏", hits[0]["target"])
        # 其余检查照常跑完(干净项目不产生别的 findings)
        self.assertEqual([f for f in r["findings"] if f["check"] != "unreadable"], [])


# ══ track opendesign-stage-timer 追加(D1/D4:`## 阶段历史` 段的体检)═════════
# 档案是**人可以手改的纯文本**(refs-vocab 那单栽过),所以段的格式要有体检。
# 两个新码:
#   bad_stage_history      —— 段内行格式不合 / 阶段名不在词表 / 日期乱序
#   stage_history_mismatch —— 段末那条的阶段名 != 头部 `- 阶段:`(起始日不可信)
# red-check:未实现前 ds_lint 不认识这两个码 → 期望命中的用例全红。

PROJECT_WITH_HIST = """# {slug}

- 业主: [[{client}]]
- 阶段: {stage}
- 开始日期: 2026-07-01

## 阶段历史

{history}

## 变更记录

## 沟通日志

---
最后更新: 2026-07-01
"""


class TestLintStageHistory(unittest.TestCase):
    """⚠️ 本组里所有「**不该报**」的用例(legacy/空段/同天/合法段/缺段不算不一致)
    **红检阶段天然是绿的** —— ds_lint 现在还不认识这两个码,自然一条也不报。
    它们是护栏(防实现后误报把体检淹掉),不是判别式。
    真正证明这份判据活着的是那 5 条「**该报**」的用例,现在全红。"""

    def setUp(self):
        self.base = _mk_pkb(tempfile.mkdtemp(prefix="dslint-sh-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)

    def lint(self):
        return ds_lint.lint_pkb(self.base)

    def _write(self, slug, stage, history):
        _w(self.base, f"projects/{slug}.md", PROJECT_WITH_HIST.format(
            slug=slug, client="张三", stage=stage, history=history))

    # ── 不报的情况(比报得准更要紧)────────────────────────────────────
    def test_legacy_file_without_section_is_not_a_finding(self):
        """★ 旧档案**没有**这一段是正常的,不许报。

        上线当天全仓都是旧档案 —— 这条要是错了,体检结果会被几十条噪音淹掉,
        用户从此不看体检。**这是本组最重要的一条。**"""
        self.assertEqual([], _checks(self.lint(), "bad_stage_history"))
        self.assertEqual([], _checks(self.lint(), "stage_history_mismatch"))

    def test_wellformed_section_is_clean(self):
        self._write("干净", "方案深化",
                    "- 2026-06-01 洽谈\n- 2026-07-20 方案深化")
        r = self.lint()
        self.assertEqual([], _checks(r, "bad_stage_history"), r)
        self.assertEqual([], _checks(r, "stage_history_mismatch"), r)

    def test_empty_section_is_not_a_finding(self):
        """段建了但还没有条目(补建后的中间态)⇒ 读侧当"未记录",体检不报。"""
        self._write("空段", "方案深化", "")
        self.assertEqual([], _checks(self.lint(), "bad_stage_history"))

    # ── bad_stage_history ────────────────────────────────────────────
    def test_malformed_line_is_reported(self):
        self._write("坏行", "方案深化",
                    "- 2026-6-1 洽谈\n- 2026-07-20 方案深化")
        hits = _checks(self.lint(), "bad_stage_history")
        self.assertEqual(1, len(hits), hits)
        self.assertIn("2026-6-1", hits[0]["detail"],
                      "detail 要指出是哪一行,否则用户不知道去改什么")

    def test_stage_not_in_vocab_is_reported(self):
        self._write("词表外", "方案深化",
                    "- 2026-06-01 开工大吉\n- 2026-07-20 方案深化")
        hits = _checks(self.lint(), "bad_stage_history")
        self.assertEqual(1, len(hits), hits)
        self.assertIn("开工大吉", hits[0]["detail"])

    def test_out_of_order_dates_are_reported(self):
        """乱序 ⇒ "最后一条"不再等于"最新",天数会算错 —— 必须报。"""
        self._write("乱序", "方案深化",
                    "- 2026-07-20 洽谈\n- 2026-06-01 方案深化")
        hits = _checks(self.lint(), "bad_stage_history")
        self.assertEqual(1, len(hits), hits)

    def test_same_date_twice_is_not_out_of_order(self):
        """边界:同一天连推两个阶段是真事(量房当天出平面),不许报。"""
        self._write("同天", "平面方案",
                    "- 2026-07-20 量房\n- 2026-07-20 平面方案")
        self.assertEqual([], _checks(self.lint(), "bad_stage_history"))

    # ── stage_history_mismatch ───────────────────────────────────────
    def test_header_and_section_tail_mismatch_is_reported(self):
        """头部说效果图、段末说方案深化 ⇒ 起始日不可信,读侧会显示"未记录"。
        体检要把这种档案指出来,否则用户只看到天数消失、不知道为什么。"""
        self._write("对不上", "效果图",
                    "- 2026-06-01 洽谈\n- 2026-07-20 方案深化")
        hits = _checks(self.lint(), "stage_history_mismatch")
        self.assertEqual(1, len(hits), hits)
        self.assertIn("效果图", hits[0]["detail"])
        self.assertIn("方案深化", hits[0]["detail"],
                      "两边的值都要写出来,用户才知道该改哪一边")

    def test_mismatch_not_reported_when_section_absent(self):
        """没段就没有"对不上"可言(旧档案)—— 不许把缺段说成不一致。"""
        self.assertEqual([], _checks(self.lint(), "stage_history_mismatch"))

    def test_mismatch_and_bad_line_are_separate_codes(self):
        """两个码各管各的,不许一个吞掉另一个(否则修完一个另一个还在藏)。"""
        self._write("双错", "效果图",
                    "- 2026-6-1 洽谈\n- 2026-07-20 方案深化")
        r = self.lint()
        self.assertEqual(1, len(_checks(r, "bad_stage_history")), r)
        self.assertEqual(1, len(_checks(r, "stage_history_mismatch")), r)


class TestListProjects(unittest.TestCase):
    def setUp(self):
        self.base = _mk_pkb(tempfile.mkdtemp(prefix="dslist-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)

    def test_01_basic_listing(self):
        r = ds_tools.list_projects(ds_root=self.base)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r["errors"], [])
        self.assertEqual(len(r["projects"]), 1)
        row = r["projects"][0]
        self.assertEqual(row["project"], "翡翠湾-1801")
        self.assertEqual(row["client"], "张三")
        self.assertEqual(row["stage"], "方案深化")
        self.assertEqual(row["last_updated"], "2026-07-01")

    def test_02_sorted_and_missing_fields_empty(self):
        _w(self.base, "projects/A空头.md", "# A空头\n\n## 变更记录\n")
        r = ds_tools.list_projects(ds_root=self.base)
        names = [p["project"] for p in r["projects"]]
        self.assertEqual(names, sorted(names))
        row = next(p for p in r["projects"] if p["project"] == "A空头")
        self.assertEqual(row["client"], "")
        self.assertEqual(row["stage"], "")
        self.assertEqual(row["last_updated"], "")

    def test_03_ignores_non_md_and_empty_dir(self):
        _w(self.base, "projects/notes.txt", "不是档案")
        r = ds_tools.list_projects(ds_root=self.base)
        self.assertEqual(len(r["projects"]), 1)
        empty = tempfile.mkdtemp(prefix="dslist-empty-")
        self.addCleanup(shutil.rmtree, empty, ignore_errors=True)
        os.makedirs(os.path.join(empty, "projects"))
        r2 = ds_tools.list_projects(ds_root=empty)
        self.assertTrue(r2.get("ok"))
        self.assertEqual(r2["projects"], [])

    def test_04_unreadable_goes_to_errors(self):
        with open(os.path.join(self.base, "projects", "坏.md"), "wb") as fh:
            fh.write(b"\xff\xfe\x00 broken \x81")
        r = ds_tools.list_projects(ds_root=self.base)
        self.assertTrue(r.get("ok"))
        self.assertEqual(len(r["projects"]), 1)  # 好档案照常列出
        self.assertEqual(len(r["errors"]), 1)
        self.assertIn("坏", r["errors"][0])


class TestCreateProjectStageGate(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="dsgate-")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)

    def test_01_bad_stage_rejected_no_file(self):
        r = ds_tools.create_project("新盘", "张三", stage="不存在的阶段",
                                    ds_root=self.base, today=TODAY)
        self.assertEqual(r.get("error"), "bad_stage")
        self.assertEqual(r.get("stages"), list(ds_tools.PROJECT_STAGES))
        self.assertFalse(
            os.path.exists(os.path.join(self.base, "projects", "新盘.md")))

    def test_02_vocab_stage_accepted(self):
        r = ds_tools.create_project("新盘", "张三", stage="量房",
                                    ds_root=self.base, today=TODAY)
        self.assertTrue(r.get("ok"), r)
        with open(os.path.join(self.base, "projects", "新盘.md"),
                  encoding="utf-8") as fh:
            self.assertIn("- 阶段: 量房", fh.read())

    def test_03_default_stage_still_works(self):
        r = ds_tools.create_project("默认盘", "张三",
                                    ds_root=self.base, today=TODAY)
        self.assertTrue(r.get("ok"), r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
