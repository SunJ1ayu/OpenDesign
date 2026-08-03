#!/usr/bin/env python3
"""resolver eval:意图 → 工具路由测试(Skillify 纪律的轻量版,tool-audit track)。

把三个 MCP server 的工具名+docstring(AST 抽取=与真部署同源)喂给 MiMo,
给一组真实说法,断言它选对工具。假阴性(该触发没触发)/假阳性(触发错)分开报。

跑法:python3 tests/evals/resolver_eval.py   (需 /root/.local/share/mimocode/auth.json;
     不进 pytest——有网络与 key 依赖。新增工具/改 docstring/真机误路由后必跑。)
退出码:0=全过(探针不计),1=有失配,2=环境/上游不可用。
"""
import ast
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
AUTH = "/root/.local/share/mimocode/auth.json"
API = "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
MODEL = "mimo-v2.5"

# (说法, 期望工具;None=应拒/无工具。带 "?" 前缀 = 探针,只记录不计分)
CASES = [
    ("把兴顺明珠改名成星顺明珠", "rename_project"),
    ("把这几个重复的项目档案删掉", "delete_project"),
    ("记一下:张三家玄关柜改到 2.4 米", "append_change"),
    ("业主刚在微信发来一大段修改意见,我贴给你", "log_communication"),
    ("翡翠湾那个项目现在什么情况", "read_project"),
    ("有什么要跟进的", "list_todos"),
    ("我的项目文件夹在 D:\\设计工作区,接进来", "set_workspace"),
    ("那个 0605 的文件夹就是虎溪咖啡项目", "bind_project"),
    ("新业主王姐,电话13800000000", "create_client"),
    ("新建项目:万科城-802,业主王姐", "create_project"),
    ("C3 那条做完了", "set_change_status"),
    ("帮我整理一下桌面这个文件夹", "scan_dir"),
    ("存一下这张客厅参考图,奶油风", "add_ref"),
    ("找几张侘寂风卧室的图", "find_refs"),
    ("把这张图挂到翡翠湾项目用", "link_ref"),
    ("把桌面上那些没用的旧文件都删了", None),  # organize 无文件删除,应拒
    # 审计空格① 已补(client-tools track):原暗区探针翻转为计分断言
    ("业主王姐的电话是多少", "read_client"),
    ("王姐预算加到 45 万了", "update_client"),
    ("记住:王姐家别提上一家装修公司,雷区", "update_client"),
    # 审计空格② 已补(set-stage track)
    ("万科城今天开始量房了", "set_stage"),
    # 收件箱认领(opendesign-intake track):看箱=list_inbox;确认指派=stage_intake
    ("收件箱里有什么新东西", "list_inbox"),
    ("帮我整理一下收件箱", "list_inbox"),
    ("对,玄关那张归到翡翠湾的参考图,户型图放它的CAD", "stage_intake"),
    # PKB 体检 + 项目枚举(opendesign-pkb-lint track):盘点=list_projects;体检=lint_pkb
    ("我手上一共有哪些项目", "list_projects"),
    ("给我的档案做个体检,看有没有重复或断链", "lint_pkb"),
    # 采纳引擎(opendesign-adoption track):盘点现状=adopt_workspace;
    # 项目根散文件归位=stage_adoption
    ("接管我的工作区,先盘一盘现在什么情况", "adopt_workspace"),
    ("把翡翠湾项目文件夹根目录那些散文件归归位", "stage_adoption"),
]

# ══ 参数级用例(track opendesign-stage-timer)═══════════════════════════════
# 上面那组只判**选没选对工具**。set_stage 加了可选 `since` 之后,D6 职责说明的
# 全部效果都在"助手到底传不传、算不算得对参数"上 —— 而原来一道题都没有。
# (这个空白是 gpt-5.6-sol 规划双出点出来的。)
#
# 断言口径:(说法, 期望工具, 期望 args 的子集)。**只查子集**,不要求逐键相等 ——
# 模型多传一个 project 名是正常的,少传/传错 since 才是要抓的。
# 值的三种写法:
#   None      该键**必须不出现或为空**
#   "字符串"   必须精确等于
#   ("a","b") 命中其一即可;成员 "" 表示"留空也行"
EVAL_TODAY = "2026-08-02"          # 星期日;上周三 = 2026-07-22,本周三 = 2026-07-29
PARAM_CASES = [
    # ① 相对日期要换算 —— 这是 D6 第 2 条的核心。
    #    ⚠️ 「上周三」在中文里本来就有两读(上一周的周三 07-22 / 最近过去的那个周三
    #    07-29),两个都认。**这不是为了让它变绿而放水**:实测 MiMo 给的是 07-27,
    #    那天是星期一,**两种读法都不成立**,照样红。
    ("翡翠湾上周三进的方案深化", "set_stage",
     {"stage": "方案深化", "since": ("2026-07-22", "2026-07-29")}),
    # ② 同阶段 + 明确日期 = 补录路径(界面「设起始日」的等价说法)
    ("翡翠湾还是方案深化,不过其实 7 月 10 号就进了", "set_stage",
     {"stage": "方案深化", "since": "2026-07-10"}),
    # ③ 说的是将来 ⇒ **不许现在就改档案**。编一个未来的起始日比空着更糟:
    #    待办页会把假死线/假计时排最前(due-writer 单已吃过这个亏)。
    ("翡翠湾下周准备进效果图", None, {}),
    # ④ 设计师说的就是「今天」⇒ 留空(走默认今天)或显式传今天,**语义等价,都算对**。
    #    原来我只认"留空",那是过严:实测 MiMo 传了 2026-08-02,那是对的行为,
    #    是我的期望写错了。真正要抓的是"没说日期却编一个过去的日子"。
    ("万科城今天开始量房了", "set_stage", {"stage": "量房", "since": ("", EVAL_TODAY)}),
]


def extract_tools():
    """从三个 MCP 登记层抽 *_tool 函数名+docstring(与真部署同源的路由信号)。

    2026-08-03(track opendesign-mcp-registry):登记层从业务模块搬到
    `bin/ds_*_server.py`,这里跟着改。**搬家当天这份 eval 没跟上,抽到的是空表**
    —— 它不进 pytest,所以没有任何测试会因此变红(闸 `EvalHarnessesFollowedTheMove`
    就是为这个补的)。改这里的文件名前先看那条闸。
    """
    tools = []
    for f in ("ds_tools_server.py", "ds_organize_server.py", "ds_refs_server.py"):
        tree = ast.parse(open(os.path.join(ROOT, "bin", f), encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.endswith("_tool"):
                doc = ast.get_docstring(node) or ""
                tools.append((node.name[:-5], " ".join(doc.split())))
    return tools


def call_mimo(prompt: str) -> str:
    key = json.load(open(AUTH))["xiaomi"]["key"]
    body = json.dumps({
        # MiMo 是 reasoning 模型:思考也计 max_tokens,给足额度防 content 被吃空
        "model": MODEL, "temperature": 0, "max_tokens": 6000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["choices"][0]["message"]["content"]


def main() -> int:
    tools = extract_tools()
    listing = "\n".join(f"- {n}: {d[:180]}" for n, d in tools)
    intents = [c[0].lstrip("?") for c in CASES]
    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(intents))
    prompt = (
        "你是室内设计师助手的工具路由器。工具清单:\n" + listing +
        "\n\n对下面每条设计师的话,选一个最该调用的工具名;没有合适工具就写 none。"
        "\n只输出 JSON 对象,键为题号字符串,值为工具名或 \"none\",不要任何其他文字。"
        "\n\n" + numbered
    )
    for attempt in range(3):
        try:
            raw = call_mimo(prompt)
            break
        except Exception as e:  # noqa: BLE001 —— 上游抖动重试,最终失败走环境码
            if attempt == 2:
                print(f"上游不可用: {e}", file=sys.stderr)
                return 2
    # 剥 ``` 围栏/前后闲话:取第一个 { 到最后一个 } 的整段
    s, e = raw.find("{"), raw.rfind("}")
    try:
        picked = json.loads(raw[s:e + 1]) if s >= 0 <= e else json.loads(raw)
    except ValueError:
        print(f"模型输出非 JSON:\n{raw[:500]}", file=sys.stderr)
        return 2

    fails = 0
    for i, (case, expect) in enumerate(CASES):
        probe = case.startswith("?")
        got = str(picked.get(str(i + 1), "<缺>")).strip()
        want = expect or "none"
        ok = got == want
        mark = "ok  " if ok else ("probe" if probe else "FAIL")
        if not ok and not probe:
            fails += 1
        kind = ""
        if not ok and not probe:
            kind = "(假阴性:该触发没触发)" if got == "none" else "(假阳性:触发错)"
        print(f"{mark} #{i+1:2d} {case.lstrip('?')!r} -> {got} (期望 {want}) {kind}")
    print(f"\n{'ALL PASS' if fails == 0 else f'{fails} FAIL'} / {sum(1 for c in CASES if not c[0].startswith('?'))} 计分用例")

    fails += run_param_cases(listing)
    return 1 if fails else 0


def run_param_cases(listing: str) -> int:
    """参数级:不只问"调哪个工具",还要它把 args 填出来。

    red-check(实现前该红成什么样):`set_stage_tool` 的签名/docstring 里还没有
    `since`,模型无从传起 ⇒ ①②必红;③④取决于模型,可能天然绿(它们是护栏)。
    """
    print("\n── 参数级用例(stage-timer)" + "─" * 40)
    numbered = "\n".join(f"{i+1}. {c[0]}" for i, c in enumerate(PARAM_CASES))
    prompt = (
        "你是室内设计师助手的工具路由器。工具清单(含参数说明):\n" + listing +
        f"\n\n当前时间:{EVAL_TODAY}(星期日)。"
        "\n\n对下面每条设计师的话,输出该调用的工具名和参数。"
        "\n只输出 JSON 对象,键为题号字符串,值为 {\"tool\": 工具名, \"args\": {...}};"
        "没有合适工具就写 {\"tool\": \"none\", \"args\": {}}。不要任何其他文字。"
        "\n\n" + numbered
    )
    for attempt in range(3):
        try:
            raw = call_mimo(prompt)
            break
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                print(f"上游不可用: {e}", file=sys.stderr)
                return 1
    s, e = raw.find("{"), raw.rfind("}")
    try:
        picked = json.loads(raw[s:e + 1]) if s >= 0 <= e else json.loads(raw)
    except ValueError:
        print(f"模型输出非 JSON:\n{raw[:500]}", file=sys.stderr)
        return 1

    fails = 0
    for i, (case, want_tool, want_args) in enumerate(PARAM_CASES):
        got = picked.get(str(i + 1)) or {}
        tool = str(got.get("tool", "<缺>")).strip()
        args = got.get("args") if isinstance(got.get("args"), dict) else {}
        want = want_tool or "none"
        probs = []
        if tool != want:
            probs.append(f"工具 {tool}(期望 {want})")
        for k, v in want_args.items():
            actual = args.get(k)
            got_s = "" if actual is None else str(actual).strip()
            if v is None:
                if got_s:
                    probs.append(f"{k} 应留空,实得 {actual!r}(猜日期比空着更糟)")
            elif isinstance(v, tuple):
                if got_s not in v:
                    probs.append(f"{k}={actual!r}(期望 {' 或 '.join(x or '留空' for x in v)})")
            elif got_s != v:
                probs.append(f"{k}={actual!r}(期望 {v!r})")
        if probs:
            fails += 1
            print(f"FAIL #{i+1} {case!r}: " + "; ".join(probs))
        else:
            print(f"ok   #{i+1} {case!r} -> {tool} {args}")
    print(f"{'ALL PASS' if fails == 0 else f'{fails} FAIL'} / {len(PARAM_CASES)} 参数级用例")
    return fails


if __name__ == "__main__":
    sys.exit(main())
