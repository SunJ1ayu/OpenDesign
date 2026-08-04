#!/usr/bin/env python3
"""ds_dates 的 oracle — 相对日期换算(track opendesign-date-arithmetic)。

**为什么这份判据值钱**:日期算术是这个仓库里少数**能被证明**的东西。
行为考卷(tests/evals/*)判的是"模型这次答对没有",天然带方差、只能抽样;
这一份给定锚点后**答案唯一**,穷举全绿就是全绿。
—— 但也正因为它这么硬,**它对本单最可能的失败方式是瞎的**:
助手压根不调这个工具、继续心算。那一半只有 resolver_eval 的行为题接得住。

跑法:  python3 tests/test_ds_dates.py     (纯 Python,零依赖、零网络)

⚠️ 锚点固定 2026-08-02(**星期日**)不是随手挑的:周日是「上周X」两读分歧
最大的一天(见 design.md「上周三的两读」)。选它当主锚点,是让规格里那个
选择**每次跑都被检验一次**,而不是躲开它。
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_dates  # noqa: E402

SUN = "2026-08-02"   # 星期日;本周一 = 07-27
WED = "2026-07-29"   # 星期三,同一周,用来验"锚点在周中时同一批说法照样对"

# (锚点, 说法, 期望日期)。**答案唯一**,不给"两个都算对"的余地——
# 考卷可以模糊,确定性函数不行(design.md 已把这个选择写在明处)。
CASES = [
    # ── 相对日 ──────────────────────────────────────────────
    (SUN, "今天",   "2026-08-02"),
    (SUN, "明天",   "2026-08-03"),
    (SUN, "后天",   "2026-08-04"),
    (SUN, "大后天", "2026-08-05"),
    (SUN, "昨天",   "2026-08-01"),
    (SUN, "前天",   "2026-07-31"),
    (SUN, "大前天", "2026-07-30"),
    # ── N 天 ───────────────────────────────────────────────
    (SUN, "3天后",  "2026-08-05"),
    (SUN, "3天内",  "2026-08-05"),   # 「内」= 最晚那天,与「后」同解
    (SUN, "3天前",  "2026-07-30"),
    (SUN, "三天后", "2026-08-05"),   # 中文数字
    (SUN, "十天后", "2026-08-12"),
    (SUN, "15天后", "2026-08-17"),   # 两位数
    # ── 周 X:锚点是周日,这是「上周X」两读分歧最大的一天 ────────
    (SUN, "这周三", "2026-07-29"),
    (SUN, "本周三", "2026-07-29"),
    (SUN, "这周五", "2026-07-31"),
    (SUN, "这周日", "2026-08-02"),   # 就是锚点当天
    (SUN, "这周天", "2026-08-02"),   # 「周天」= 周日
    (SUN, "上周三", "2026-07-22"),   # ⬅ ISO 读法。实测模型给过 07-27/07-28,两读都不成立
    (SUN, "上周一", "2026-07-20"),
    (SUN, "上上周三", "2026-07-15"),
    (SUN, "下周三", "2026-08-05"),
    (SUN, "下周五", "2026-08-07"),
    (SUN, "下下周五", "2026-08-14"),
    # ── 同一批说法,锚点换到周中(周三)────────────────────────
    (WED, "这周三", "2026-07-29"),   # 锚点当天
    (WED, "这周一", "2026-07-27"),   # 本周里已经过去的那天,仍是"这周"
    (WED, "这周五", "2026-07-31"),
    (WED, "上周三", "2026-07-22"),
    (WED, "下周三", "2026-08-05"),
    # ── 月底 ───────────────────────────────────────────────
    (SUN, "月底",     "2026-08-31"),
    (SUN, "月末",     "2026-08-31"),
    (SUN, "本月底",   "2026-08-31"),
    (SUN, "这个月底", "2026-08-31"),
    (SUN, "下月底",   "2026-09-30"),
    (SUN, "下个月底", "2026-09-30"),
    # ── 具体日期(取锚点的年份)──────────────────────────────
    (SUN, "8月20号", "2026-08-20"),
    (SUN, "8月20日", "2026-08-20"),
    (SUN, "12月1号", "2026-12-01"),
]

# 边界:跨月/跨年/闰年。这些是"日期算术"最爱出错的地方,而模型心算时它们全无保护。
EDGE_CASES = [
    ("2026-01-31", "月底",   "2026-01-31"),   # 锚点就是月末
    ("2026-01-31", "下月底", "2026-02-28"),   # 2 月只有 28 天(非闰年)
    ("2028-01-31", "下月底", "2028-02-29"),   # 闰年
    ("2026-12-31", "明天",   "2027-01-01"),   # 跨年
    ("2026-01-01", "昨天",   "2025-12-31"),   # 反向跨年
    ("2026-12-31", "下月底", "2027-01-31"),   # 跨年 + 月底
    ("2026-12-30", "下周三", "2027-01-06"),   # 跨年 + 周
    ("2026-03-01", "上周日", "2026-02-22"),   # 反向跨月,且落在周日
    ("2026-08-31", "月底",   "2026-08-31"),   # 幂等
]

# 故意不认的:它们**本身就不精确**,而契约写死了「编一个日期比空着更糟」。
# 报错交回助手 → 助手问设计师一句,这正是我们要的行为。
# ⚠️ 这一组是**规格的一部分**,不是"还没做的功能"。有人日后想让它们"聪明一点",
#    得先回答:凭什么替业主决定「月初」是几号?
UNKNOWN = ["月初", "下个月初", "这周末", "过几天", "尽快", "有空改一下",
           "催得急", "", "下周", "以后", "国庆前"]


class TestResolveDate(unittest.TestCase):
    def test_cases(self):
        for anchor, expr, want in CASES:
            with self.subTest(anchor=anchor, expr=expr):
                got = ds_dates.resolve(expr, anchor)
                self.assertNotIn("error", got, f"{expr} 应该认识,却报了 {got.get('error')}")
                self.assertEqual(got["date"], want)

    def test_edges(self):
        for anchor, expr, want in EDGE_CASES:
            with self.subTest(anchor=anchor, expr=expr):
                got = ds_dates.resolve(expr, anchor)
                self.assertNotIn("error", got)
                self.assertEqual(got["date"], want)

    def test_unknown_never_guesses(self):
        """不认识的说法必须**明确报错**,绝不返回一个猜出来的日期。

        这是本单的安全底线:一个错日期会被待办页一脸自信地排到最前面,
        而一个 error 只会让助手多问设计师一句话。
        """
        for expr in UNKNOWN:
            with self.subTest(expr=expr):
                got = ds_dates.resolve(expr, SUN)
                self.assertEqual(got.get("error"), "unknown_expr",
                                 f"「{expr}」不该被认出来,却给了 {got}")
                self.assertNotIn("date", got)

    def test_weekday_is_reported(self):
        """返回必须带星期几 —— 这是**让算错看得见**的唯一手段。

        ISO 两读那件事(周日时「上周三」是 07-22 还是 07-29)判据永远判我选的那读为对;
        设计师能纠正的前提,是助手把「7 月 22 日(星期三)」说出来。
        weekday 一旦没了,这条链就断了,所以焊在判据里。
        """
        got = ds_dates.resolve("上周三", SUN)
        self.assertEqual(got["date"], "2026-07-22")
        self.assertEqual(got["weekday"], "星期三")
        self.assertEqual(got["anchor"], SUN)
        self.assertEqual(got["anchor_weekday"], "星期日")
        self.assertEqual(got["expr"], "上周三")

    def test_anchor_defaults_to_today(self):
        """anchor 留空 = 今天。契约里"没有时间线索就按今天算"那条的机械保证。"""
        got = ds_dates.resolve("今天", "")
        from datetime import date
        self.assertEqual(got["date"], date.today().isoformat())

    def test_bad_anchor_is_an_error(self):
        """锚点本身非法 → 报错,不许默默退回今天。

        默默退回 = 把"助手传错了锚点"这个 bug 变成一个看起来正常的日期,
        正是本单要消灭的那种静默错。
        """
        for bad in ["2026-13-01", "8/2", "上周三", "20260802"]:
            with self.subTest(anchor=bad):
                got = ds_dates.resolve("今天", bad)
                self.assertEqual(got.get("error"), "invalid_anchor")

    def test_whitespace_tolerated(self):
        """模型偶尔会带上空格/全角空格,不该因此报 unknown。"""
        for expr in ["  上周三", "上周三  ", "　上周三"]:
            with self.subTest(expr=expr):
                self.assertEqual(ds_dates.resolve(expr, SUN)["date"], "2026-07-22")

    def test_trailing_particles_tolerated(self):
        """业主原话常带「之前/前/以前」这类尾巴:「这周五之前」「月底前」。

        语义上"最晚不超过那天" ⇒ 与不带尾巴同解。**不认这些等于逼助手自己剥词**,
        剥词就是又把判断塞回模型脑子里 —— 那正是本单要拿走的东西。
        """
        for expr, want in [("这周五之前", "2026-07-31"), ("这周五前", "2026-07-31"),
                           ("月底前", "2026-08-31"), ("下周五前", "2026-08-07"),
                           ("8月20号之前", "2026-08-20")]:
            with self.subTest(expr=expr):
                self.assertEqual(ds_dates.resolve(expr, SUN)["date"], want)


if __name__ == "__main__":
    unittest.main(verbosity=2)
