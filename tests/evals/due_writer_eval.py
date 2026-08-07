#!/usr/bin/env python3
"""due-writer eval:助手会不会把业主说的期限**真的写进档案**(track opendesign-due-writer)。

与 resolver_eval 的分工:那份问「这句话该选哪个工具」(单选路由,不执行);
本份**真跑一遍工具循环** —— 把 ds_tools 的工具原样交给模型(schema 从 AST 抽,
与真部署同源),模型调什么就在一个临时 DS_ROOT 上真执行什么,最后**读档案文件**,
断言那条变更行尾上有没有 `⏳YYYY-MM-DD`。

为什么必须执行、不能只看"计划":设截止日是**两步**(append_change 拿到 `C7` →
set_due_date 用这个号)。只问计划,模型可以先编一个 `C1` 蒙对格式;只有真跑,
才知道它会不会读返回值、会不会把号记串。**用户眼里的成功 = 档案里有截止日**,
这份考卷判的就是这个,不是判它嘴上说要设。

跑法:python3 tests/evals/due_writer_eval.py   (需 /root/.local/share/mimocode/auth.json;
     不进 pytest——有网络与 key 依赖,单次约 3-6 分钟。改助手职责说明/工具 docstring 后必跑。)
退出码:0=全过(探针不计),1=有失配,2=环境/上游不可用。
"""
import ast
import concurrent.futures as futures
import inspect
import json
import os
import shutil
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))

from resolver_eval import API, AUTH, MODEL  # noqa: E402  —— 端点/模型/key 路径单一来源
import ds_tools  # noqa: E402
import ds_common  # noqa: E402

# nanobot 每轮注入的格式(nanobot/agent/context.py:143 → utils/helpers.py:250)。
# 固定成 2026-08-04 周二:相对期限才有唯一正确答案——不选周日,周日说"这周五"
# 中文本身就有歧义,歧义题不拿来当计分题。
FAKE_TODAY = "2026-08-04"
NOW_LINE = f"Current Time: {FAKE_TODAY} 10:30 (Tuesday) (Asia/Shanghai, UTC+08:00)"
PROJECT = "翡翠湾-1801"
MAX_TURNS = 8

# want_dues = 跑完后档案里应有的截止日,每项 (日期, 该日期必须挂在哪条上的关键词候选)。
#   日期集合要完全相等(多设、少设、设错日期都红),**并且**每个日期所在那行的正文
#   必须命中它的关键词之一 —— 光对日期不查挂在哪条,是第一版的洞(见 dated_lines 注释)。
# min_changes = 至少落下几条变更行(只在"一批多条"那题用得上)。
CASES = [
    {
        "say": f"{PROJECT} 业主刚说:主卧衣柜改成到顶的,8 月 10 号之前要看到效果图。",
        "want_dues": [("2026-08-10", ("衣柜", "效果图"))],
    },
    {
        "say": f"{PROJECT} 业主说客厅电视墙的石材换成木饰面,这周五之前改好发给他。",
        "want_dues": [("2026-08-07", ("电视墙", "石材", "木饰面"))],
    },
    {
        "say": f"{PROJECT} 业主要把儿童房的书桌加长到 1.5 米,下周五前给他方案。",
        "want_dues": [("2026-08-14", ("书桌",))],
    },
    {
        # 反例:催促不是期限。编一个日期比空着更糟——待办页会把不存在的死线排到最前面。
        # (题面不许出现"那条":指代已有条目时,助手先 read_project 去找是合理的,
        #  那样红的是我的题面不是它的行为——第一次跑就栽在这上面。)
        "say": f"{PROJECT} 业主催得急,厨房吊柜高度降到 2.2 米,尽快改。",
        "want_dues": [],
    },
    {
        # 反例:普通一条修改意见,一个字都没提时间。
        "say": f"{PROJECT} 业主说玄关柜的门板颜色换成浅一点的橡木色。",
        "want_dues": [],
    },
    {
        # 一批三条只有一条带期限:不许把期限扩散到整批,也不许漏掉那一条。
        "say": (f"{PROJECT} 业主发来一段:①主卧床头背景板改造型;②客厅窗帘换成双层的;"
                "③效果图这周五之前要看到。"),
        "want_dues": [("2026-08-07", ("效果图",))],
        "min_changes": 3,
    },
    {
        # 时间锚点(2026-08-04,track opendesign-assistant-context)。
        # 贴的是**上周三**(07-29)收到的记录,业主原话「这周五」= 说话那周的周五 07-31,
        # **不是**录入那周的 08-07。差整整一周,不报错、不崩,待办页照样一脸自信地排序。
        # 这题在改 AGENTS.md 契约 1c 之前必红 —— 现状写死了「按最上面那行 Current Time 换算」。
        # 与第 2 题(同样说「这周五」但没交代时间 → 08-07)成对:一题验新规则生效,
        # 一题验它没把常见路径带跑。**只看其中一题都是假绿。**
        "say": (f"{PROJECT} 这是上周三收到的微信记录,我今天才腾出手整理:"
                "业主说客厅电视墙的石材换成木饰面,效果图这周五之前要看到。"),
        "want_dues": [("2026-07-31", ("效果图", "电视墙", "木饰面", "石材"))],
    },
    {
        "probe": True,
        "say": f"{PROJECT} 业主说月底前把全套图纸整理出来给他。",
        "want_dues": [("2026-08-31", ("图纸",))],
    },
    {
        # 探针:"下个月初"本身就模糊——记录模型是编一个日期还是不设。
        # min_changes=0:"再定"是待议不是改动,一条都不落也说得通,这里只看它编不编日期。
        "probe": True,
        "say": f"{PROJECT} 业主说下个月初再定阳台的方案。",
        "want_dues": [],
        "min_changes": 0,
    },
]

# 多步用例(2026-08-04,track opendesign-date-arithmetic):除了「档案里的日期对不对」,
# 还要**看调用轨迹里有没有真的调那个工具**。
#
# 为什么这几道非放这份不可:相对日期改完之后是**两步**(resolve_date 算 → set_due_date 落)。
# `resolver_eval` 是单选路由器,只让答一个工具名,**结构上问不出两步行为**
# (那边试过三遍全红,红的是题面不是模型,已在那边留痕搬走)。
# 这份真跑工具循环、trace 全在手里,是唯一能判"它到底心算了没有"的地方。
MULTI_STEP_CASES = [
    {
        "name": "相对期限:必须先调 resolve_date,不许心算",
        "say": (f"{PROJECT} 业主说主卧衣柜改到顶,这周五之前要看到效果图。"),
        "must_call": "resolve_date",
        "want_dues": [("2026-08-07", ("衣柜", "效果图"))],
    },
    {
        # 护栏:确切日期不许绕道。新工具最典型的副作用是"逢日期必调",
        # 把最常见的路径凭空变慢一倍。
        "name": "护栏:确切日期直接落,不许绕 resolve_date",
        "say": f"{PROJECT} 业主说玄关柜门板换浅橡木色,2026-08-20 之前改完。",
        "must_not_call": "resolve_date",
        "want_dues": [("2026-08-20", ("玄关", "门板"))],
    },
]

_PY_TYPES = {"int": "integer", "bool": "boolean", "float": "number"}


def tool_schemas() -> list[dict]:
    """从 bin/ds_tools_server.py 的 *_tool 定义抽 OpenAI function schema(与真部署同源)。

    2026-08-03(track opendesign-mcp-registry):登记层搬到 `bin/ds_tools_server.py`,
    这里跟着改;**执行仍打在业务模块 `ds_tools` 上**(下面 `call_tool` 的 getattr),
    因为搬走的只是 `@server.tool()` 那层壳,纯 Python 核心没动。
    """
    tree = ast.parse(
        open(os.path.join(ROOT, "bin", "ds_tools_server.py"), encoding="utf-8").read())
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name.endswith("_tool")):
            continue
        args = node.args.args
        ndef = len(node.args.defaults)
        required = [a.arg for a in args[:len(args) - ndef]]
        props = {}
        for a in args:
            ann = getattr(a.annotation, "id", None) if a.annotation else None
            props[a.arg] = {"type": _PY_TYPES.get(ann, "string")}
        out.append({"type": "function", "function": {
            "name": node.name[:-5],
            "description": " ".join((ast.get_docstring(node) or "").split()),
            "parameters": {"type": "object", "properties": props, "required": required},
        }})
    return out


def run_tool(name: str, args: dict, ds_root: str) -> dict:
    """在临时 DS_ROOT 上真执行。未知工具/未知参数照真部署的样子报错回去,让模型自己纠。"""
    fn = getattr(ds_tools, name, None)
    if fn is None or not callable(fn):
        return {"error": f"unknown_tool: {name}"}
    accepted = inspect.signature(fn).parameters
    unknown = [k for k in args if k not in accepted]
    if unknown:
        return {"error": f"unexpected_argument: {', '.join(unknown)}"}
    kwargs = dict(args)
    if "ds_root" in accepted:
        kwargs["ds_root"] = ds_root
    if "today" in accepted:
        kwargs["today"] = FAKE_TODAY      # 与 NOW_LINE 对齐,记录日期不跟考题打架
    try:
        return fn(**kwargs)
    except Exception as e:  # noqa: BLE001 —— 工具异常也是模型该看到的现实
        return {"error": f"{type(e).__name__}: {e}"}


class Truncated(RuntimeError):
    """这一遍**作废**,不是行为红 —— 要和普通异常分开,否则守卫只做了一半。

    2026-08-07 三轮四审 subdeepseek F4:上一版抛的是裸 `RuntimeError`,
    被 `run_case` 的兜底 `except Exception` 收走 → `check_dues` 记成"跑挂了" → **算失分**,
    只有**全部**用例都截断时 `main()` 才走 `return 2`。也就是说这条守卫
    恰恰在最要命的那种情况(只有一两道题被吃空)下不起作用 —— 而那正是它要治的病。
    单独一个类型,让 `main()` 认得出:任何一道题截断 ⇒ 整遍作废(exit 2)。
    """


def chat(messages: list[dict], tools: list[dict]) -> dict:
    key = json.load(open(AUTH))["xiaomi"]["key"]
    body = json.dumps({
        # MiMo 是 reasoning 模型:思考也计 max_tokens,给足额度防 content 被吃空
        # (6000 就会被吃空——本卷第一版栽过,输出全空)
        "model": MODEL, "temperature": 0, "max_tokens": 20000,
        "messages": messages, "tools": tools,
    }, ensure_ascii=False).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        choice = json.load(r)["choices"][0]
    # **截断不许伪装成"模型选择什么都不做"。** 2026-08-07:一遍跑里两道题
    # 判成"没调工具",而 MiMo 是 reasoning 模型、思考也计 max_tokens ——
    # 被吃空和"它决定不动手"在返回里长得一模一样(本卷第一版就栽过一次,
    # 那次是 max_tokens=6000)。契约每长一点,这个坑就更近一点,
    # 于是"契约压垮了旧行为"和"这一遍被截断了"会混成同一条红。
    # 这里让它自己说出来:这一遍作废,不是行为退化。
    if choice.get("finish_reason") == "length":
        raise Truncated(
            "模型输出被 max_tokens 截断(finish_reason=length)—— 这一遍作废,"
            "**不是**行为红。要么调大 max_tokens,要么把系统提示词缩短。")
    return choice["message"]


def system_prompt() -> str:
    def read(*p):
        return open(os.path.join(ROOT, *p), encoding="utf-8").read()
    return (f"{NOW_LINE}\n\n" + read("workspace", "SOUL.md") + "\n\n"
            + read("workspace", "AGENTS.md"))


def dated_lines(ds_root: str) -> list[tuple[str, str]]:
    """档案里带截止日的变更行 → [(日期, 该行正文)]。

    ⚠️ 为什么要连正文一起收(2026-08-02 补强,gpt-5.6-sol 发散时点破的洞):
    第一版只收"整份档案出现了哪些日期",**根本没查日期挂在哪一条上**。
    模型把「这周五」挂到窗帘那条、而不是效果图那条,照样判绿 ——
    而待办页会拿着这条错挂的日期一脸自信地展示,比偶尔漏设更危险。
    """
    path = os.path.join(ds_root, "projects", f"{PROJECT}.md")
    if not os.path.exists(path):
        return []
    found = []
    for ln in open(path, encoding="utf-8").read().splitlines():
        if ds_tools._CHANGE_RE.match(ln):
            text, due = ds_common.split_due(ln)
            if due:
                found.append((due, text))
    return sorted(found)


def change_lines(ds_root: str) -> int:
    path = os.path.join(ds_root, "projects", f"{PROJECT}.md")
    if not os.path.exists(path):
        return 0
    return sum(1 for ln in open(path, encoding="utf-8").read().splitlines()
               if ds_tools._CHANGE_RE.match(ln))


def run_case(case: dict, tools: list[dict]) -> dict:
    ds_root = tempfile.mkdtemp(prefix="due-eval-")
    try:
        ds_tools.create_project(PROJECT, client="王姐", ds_root=ds_root, today=FAKE_TODAY)
        messages = [{"role": "system", "content": system_prompt()},
                    {"role": "user", "content": case["say"]}]
        trace, called = [], set()   # called:工具名集合,给 must_call / must_not_call 用
        for _ in range(MAX_TURNS):
            msg = chat(messages, tools)
            calls = msg.get("tool_calls") or []
            messages.append({"role": "assistant", "content": msg.get("content") or "",
                             "tool_calls": calls})
            if not calls:
                break
            for c in calls:
                name = c["function"]["name"]
                try:
                    args = json.loads(c["function"]["arguments"] or "{}")
                except ValueError:
                    args = {}
                res = run_tool(name, args, ds_root)
                called.add(name)
                trace.append(f"{name}({args.get('due') or args.get('content', '')[:12]})")
                messages.append({"role": "tool", "tool_call_id": c["id"],
                                 "content": json.dumps(res, ensure_ascii=False)})
        return {"dated": dated_lines(ds_root), "changes": change_lines(ds_root),
                "trace": trace, "called": called, "error": None}
    except Truncated:
        raise           # 作废整遍,**不许**被下面那行收编成"这道题失分"(三轮 subdeepseek F4)
    except Exception as e:  # noqa: BLE001 —— 上游/环境错走环境码,不冒充失分
        return {"dated": [], "changes": 0, "trace": [], "called": set(),
                "error": f"{type(e).__name__}: {e}"}
    finally:
        shutil.rmtree(ds_root, ignore_errors=True)


def check_dues(case: dict, r: dict) -> list[str]:
    """两份用例共用的「档案里的截止日对不对」判定。"""
    bad = []
    if r["error"]:
        bad.append(f"跑挂了:{r['error']}")
    got_dates = sorted(d for d, _ in r["dated"])
    want_dates = sorted(d for d, _ in case["want_dues"])
    if got_dates != want_dates:
        bad.append(f"档案里的截止日 {got_dates or '无'},期望 {want_dates or '无'}")
    else:
        for date, keys in case["want_dues"]:      # 日期对了,再查挂在哪一条上
            line = next((t for d, t in r["dated"] if d == date), "")
            if not any(k in line for k in keys):
                bad.append(f"{date} 挂错了条目:挂在「{line[:24]}」,应是含 {'/'.join(keys)} 的那条")
    if r["changes"] < case.get("min_changes", 1):
        bad.append(f"只落下 {r['changes']} 条变更行,期望 ≥{case.get('min_changes', 1)}")
    return bad


def run_multi_step(tools: list[dict]) -> int:
    """多步用例:除了判档案,还判**调用轨迹里有没有调那个工具**。

    这是 resolver_eval 判不了的那一半 —— 那份是单选路由器,问不出两步行为。
    """
    print("\n── 多步用例(date-arithmetic:判轨迹,不只判档案)" + "─" * 20)
    with futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda c: run_case(c, tools), MULTI_STEP_CASES))
    fails = 0
    for case, r in zip(MULTI_STEP_CASES, results):
        bad = check_dues(case, r)
        must = case.get("must_call")
        if must and must not in r["called"]:
            bad.append(f"没调 {must} —— 日期是心算出来的(算对了也不算数:"
                       f"下次就未必对,而下游没有任何一道闸看得出来)")
        never = case.get("must_not_call")
        if never and never in r["called"]:
            bad.append(f"多绕了一趟 {never}:话里已经是确切日期,直接落就行")
        if bad:
            fails += 1
        print(f"{'ok  ' if not bad else 'FAIL'} {case['name']}")
        print(f"      调用: {' → '.join(r['trace']) or '(没调工具)'}")
        if bad:
            print(f"      失配: {'; '.join(bad)}")
    print(f"{'ALL PASS' if fails == 0 else f'{fails} FAIL'} / {len(MULTI_STEP_CASES)} 多步用例")
    return fails


def main() -> int:
    tools = tool_schemas()
    print(f"工具 {len(tools)} 个;{len(CASES)} 题(每题一个临时 DS_ROOT,真执行)…\n")
    with futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda c: run_case(c, tools), CASES))

    if all(r["error"] for r in results):
        print(f"上游/环境不可用:{results[0]['error']}", file=sys.stderr)
        return 2

    fails = 0
    scored = sum(1 for c in CASES if not c.get("probe"))
    for case, r in zip(CASES, results):
        bad = check_dues(case, r)
        probe = case.get("probe", False)
        mark = "ok  " if not bad else ("probe" if probe else "FAIL")
        if bad and not probe:
            fails += 1
        print(f"{mark} {case['say'][:36]}…")
        print(f"      调用: {' → '.join(r['trace']) or '(没调工具)'}")
        if bad:
            print(f"      失配: {'; '.join(bad)}")
    print(f"\n{'ALL PASS' if fails == 0 else f'{fails} FAIL'} / {scored} 计分用例")
    fails += run_multi_step(tools)
    return 1 if fails else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Truncated as e:
        # 退出码 2 = 环境/上游不可用,**不是** 1(有失配)。
        # 对比跑基线时,"这一遍作废"必须能和"这一遍红了"分开数,否则
        # 一遍被吃空会被记进"劣化"那一栏,而那正是这条守卫要防的事。
        print(f"这一遍作废:{e}", file=sys.stderr)
        sys.exit(2)
