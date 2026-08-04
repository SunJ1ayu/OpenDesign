"""相对日期换算 —— 确定性,零副作用(track opendesign-date-arithmetic,2026-08-04)。

**为什么有这个模块**:业主说「这周五之前」「上周三」,这些要变成 `YYYY-MM-DD` 存进档案。
在这之前,换算完全由助手(LLM)心算 —— 实测同一道「上周三」连答 6 遍错 3 遍,
给出的 07-27(周一)、07-28(周二)**两种读法都不成立,是纯算错**;
而 `set_due_date` 只校验格式,错的日期和对的日期在它眼里一样合法,下游零复核。

**分工**:模型负责**听懂**(「上周三」= 上一周的星期三,语言理解是它的强项),
本模块负责**算**(数格子,模型的弱项),并把星期几一起回报 ——
让设计师一眼看得出算错没有。

**宁可不认,不许猜**:词表有界。不认识的说法返回 `unknown_expr`,
助手照契约问设计师一句。理由写在契约里:**编一个日期比空着更糟**,
待办页会把一个不存在的死线排到所有事情最前面。
"""
import calendar
import re
from datetime import date, timedelta

WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

_WD_CHAR = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}
_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

# 相对日。「大后天」= +3(今天→明天→后天→大后天),反向同理。
_DAY_WORDS = {"今天": 0, "今日": 0, "明天": 1, "明日": 1, "后天": 2, "大后天": 3,
              "昨天": -1, "昨日": -1, "前天": -2, "大前天": -3}

# 周偏移。**顺序有讲究**:正则里「上上」必须排在「上」前面,否则「上上周三」
# 会先被「上」吃掉、剩下的再匹配一次,答案差整整一周。
_WEEK_OFFSET = {"这": 0, "本": 0, "该": 0, "上上": -2, "上": -1, "下下": 2, "下": 1}

_RE_WEEK = re.compile(r"^(这|本|该|上上|上|下下|下)(?:周|週|星期|礼拜)([一二三四五六日天])$")
_RE_NDAY = re.compile(r"^(\d{1,3}|[一二三四五六七八九十])天(以前|以后|以内|以內|前|后|後|内|內)$")
_RE_MD = re.compile(r"^(\d{1,2})月(\d{1,2})(?:号|號|日)$")
_RE_MONTH_END = re.compile(r"^(这个|这|本|下个|下|下一个)?月(?:底|末)$")

# 尾巴词:业主原话常带「之前/前/以前」——语义是"最晚不超过那天",与不带同解。
# **不剥它等于逼助手自己剥**,而剥词就是又把判断塞回模型脑子里,正是本模块要拿走的东西。
# ⚠️ 长的必须排在短的前面(「之前」在「前」之前),否则「之前」只会被剥掉一个「前」。
_TAILS = ("之前", "以前", "之内", "以内", "以內", "前", "内", "內")

RECOGNIZED = ["今天/明天/后天/大后天/昨天/前天/大前天", "N天后/N天前/N天内",
              "这周X/上周X/上上周X/下周X/下下周X(X=一~六/日/天)",
              "月底/月末/本月底/下月底", "M月D号/M月D日"]


def _cn_int(s: str) -> int:
    return int(s) if s.isdigit() else _CN_NUM[s]


def _month_last_day(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def _parse(expr: str, anchor: date):
    """认得出就返回 date,认不出返回 None。**任何一条路径都不许猜。**"""
    if expr in _DAY_WORDS:
        return anchor + timedelta(days=_DAY_WORDS[expr])

    mo = _RE_NDAY.match(expr)
    if mo:
        n = _cn_int(mo.group(1))
        # 「N天内」= 最晚那天,与「N天后」同解(业主说"三天内给我"= 最迟第三天)
        sign = -1 if mo.group(2) in ("前", "以前") else 1
        return anchor + timedelta(days=sign * n)

    mo = _RE_WEEK.match(expr)
    if mo:
        # ISO:周一为一周之始。见 design.md「上周三的两读」——
        # 这是个**被选定的**读法,不是唯一正确的读法,所以返回里必须带星期几让人复核。
        monday = anchor - timedelta(days=anchor.isoweekday() - 1)
        return (monday + timedelta(weeks=_WEEK_OFFSET[mo.group(1)])
                + timedelta(days=_WD_CHAR[mo.group(2)] - 1))

    mo = _RE_MONTH_END.match(expr)
    if mo:
        nxt = (mo.group(1) or "") in ("下个", "下", "下一个")
        y, m = anchor.year, anchor.month
        if nxt:
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        return _month_last_day(y, m)

    mo = _RE_MD.match(expr)
    if mo:
        m, d = int(mo.group(1)), int(mo.group(2))
        try:
            return date(anchor.year, m, d)   # 取锚点的年份;跨年推断留给设计师,不猜
        except ValueError:
            return "invalid_date"
    return None


def resolve(expr: str, anchor: str = "") -> dict:
    """把一个相对日期说法换算成确切日期。

    expr   业主原话里那个说法,原样传(「上周三」「这周五之前」「月底前」)
    anchor 锚点日 YYYY-MM-DD = **业主说这句话那天**(契约 1c);留空 = 今天
    """
    raw = expr
    expr = (expr or "").strip().strip("　").strip()

    if anchor:
        # 锚点非法**必须报错,不许默默退回今天** —— 那会把"助手传错锚点"这个 bug
        # 变成一个看起来正常的日期,正是本模块要消灭的那种静默错。
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", anchor):
            return {"error": "invalid_anchor", "anchor": anchor}
        try:
            base = date.fromisoformat(anchor)
        except ValueError:
            return {"error": "invalid_anchor", "anchor": anchor}
    else:
        base = date.today()

    got = _parse(expr, base)
    if got is None:                      # 剥掉尾巴词再试一次(「这周五之前」→「这周五」)
        for tail in _TAILS:
            if expr.endswith(tail) and len(expr) > len(tail):
                got = _parse(expr[: -len(tail)], base)
                if got is not None:
                    break
    if got is None:
        return {"error": "unknown_expr", "expr": raw, "recognized": RECOGNIZED}
    if got == "invalid_date":
        return {"error": "invalid_date", "expr": raw}

    return {"date": got.isoformat(), "weekday": WEEKDAY_CN[got.weekday()],
            "anchor": base.isoformat(), "anchor_weekday": WEEKDAY_CN[base.weekday()],
            "expr": raw}
