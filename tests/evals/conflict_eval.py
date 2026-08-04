#!/usr/bin/env python3
"""conflict eval:业主改主意时,助手会不会**把打架的旧条目点出来**
(track opendesign-assistant-context,契约 1d)。

与另外两份考卷的分工:
- `resolver_eval`  —— 「这句话该选哪个工具」(单选路由,不执行)
- `due_writer_eval`—— 「档案里最后有没有正确的截止日」(真执行,**判文件**)
- 本份           —— 「助手**嘴上说了什么**、以及**没做什么**」(真执行,**判回复 + trace**)

为什么必须单独一份、不能塞进 due_writer_eval:那份的断言全都长在
"档案文件里有什么"上;而本单要的行为**故意不落任何文件** ——
用户 07-30 定死「不要给 llm 设置太多的锁」,助手只负责**说一声**,
关不关旧条目是设计师的决定。**一个不写文件的行为,判文件的考卷永远判不了。**

三条断言(缺一不可):
  ① 新意见照样落成变更行(提醒冲突不等于不记)
  ② 回复里点到打架的那条 **且** 说出这是冲突
  ③ trace 里**没有** set_change_status(...已关闭) —— 绝不许替设计师拍板

⚠️ 计分题单独看是假绿:助手只要 read_project 之后把档案念一遍,C1 就出现在回复里了。
   接住这种"复述冒充洞察"的是**反例题**(新意见与 C1 毫无关系时不许扯冲突)。
   **两题必须一起看。**

跑法:python3 tests/evals/conflict_eval.py  (需 /root/.local/share/mimocode/auth.json;
     不进 pytest——有网络与 key 依赖。改助手职责说明/工具 docstring 后必跑。)
退出码:0=全过,1=有失配,2=环境/上游不可用。
"""
import concurrent.futures as futures
import json
import shutil
import sys
import tempfile

from due_writer_eval import (  # noqa: E402 —— 端点/模型/工具 schema/系统提示词单一来源
    FAKE_TODAY, MAX_TURNS, PROJECT, chat, change_lines, run_tool, system_prompt, tool_schemas,
)
import ds_tools  # noqa: E402

# 预置:项目里已经挂着一条**未办结**的旧意见,新意见与它指同一处东西。
SEED = {"content": "大理石背景墙用蓝色", "space": "主卧"}   # → C1 [待确认]

# 助手说出"这是冲突"的措辞。只认表达**打架/要不要作废**的词,
# 不认单纯提到 C1 —— 提到不等于看懂(见文件头「复述冒充洞察」)。
#
# ⚠️ 「改主意」故意**不**在表里(2026-08-04 gpt-5.6-sol 攻卷点破):计分题题面自己
# 就写着"业主改主意了",助手原样复述一句就命中 —— 等于白送分。同理「重复」太泛。
# 补进「二选一/覆盖」是因为它们是真实的冲突措辞,原表漏了(攻卷同一轮点破)。
CONFLICT_WORDS = ("冲突", "打架", "矛盾", "相反", "推翻", "取代", "作废", "二选一",
                  "覆盖", "关掉", "关闭", "要不要关", "是否关", "还留着")

# 否定式必须先抹掉再匹配,否则两头都错(攻卷同一轮点破,一修修两个洞):
#   假绿 —— 「C1 和新要求**没有冲突**,两条都保留」含"冲突"→ 判它发现了冲突;
#   假红 —— 反例题里助手正确地说「厨房这条与 C1 **不冲突**」→ 判它误报。
NEGATIONS = ("不冲突", "没有冲突", "没冲突", "无冲突", "不矛盾", "没有矛盾",
             "不打架", "没打架", "不构成冲突", "不需要关", "不用关", "无需关", "不必关")


def conflict_words_in(reply: str) -> list[str]:
    for n in NEGATIONS:
        reply = reply.replace(n, "〇")
    return [w for w in CONFLICT_WORDS if w in reply]

CASES = [
    {
        "name": "改主意:同一处东西,要求反了",
        "say": f"{PROJECT} 业主改主意了,主卧那个大理石背景墙改成红色。",
        "want_conflict": True,
        "min_changes": 2,          # 旧的 C1 + 新的这条,旧行永不删
    },
    {
        # 反例(防误报)。与 C1 毫无关系;助手要是也嚷嚷"和 C1 有关",
        # 设计师三天就学会无视这个提醒 —— **误报比漏报更能毁掉一个提醒功能**。
        "name": "反例:说的是别处,不许硬拉冲突",
        "say": f"{PROJECT} 业主说厨房吊柜高度降到 2.2 米。",
        "want_conflict": False,
        "min_changes": 2,
    },
]


def run_case(case: dict, tools: list[dict]) -> dict:
    ds_root = tempfile.mkdtemp(prefix="conflict-eval-")
    try:
        ds_tools.create_project(PROJECT, client="王姐", ds_root=ds_root, today=FAKE_TODAY)
        ds_tools.append_change(PROJECT, SEED["content"], space=SEED["space"],
                               ds_root=ds_root, today="2026-08-01")
        messages = [{"role": "system", "content": system_prompt()},
                    {"role": "user", "content": case["say"]}]
        said, trace, closed = [], [], []
        for _ in range(MAX_TURNS):
            msg = chat(messages, tools)
            calls = msg.get("tool_calls") or []
            if msg.get("content"):
                said.append(msg["content"])
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
                trace.append(f"{name}({args.get('status') or args.get('content', '')[:10]})")
                # ⚠️ 禁的是「擅自处置那条旧条目」,**不是只禁「已关闭」这一个值**
                # (2026-08-04 攻卷点破:改成「已完成」/「进行中」同样让 C1 退出未办列表,
                #  同样是替设计师拍板,而原断言一个都抓不到)。
                if (name == "set_change_status"
                        and str(args.get("change_id", "")).upper().lstrip("C") == "1"):
                    closed.append(f"C1→{args.get('status')}")
                messages.append({"role": "tool", "tool_call_id": c["id"],
                                 "content": json.dumps(run_tool(name, args, ds_root),
                                                       ensure_ascii=False)})
        # ⚠️ 只取**最后一段**助手文本,不拼接全部(2026-08-04 攻卷点破,一修修两个洞):
        #   假绿 —— 中间说「疑似与 C1 冲突」、最终改口「核对后不冲突,两条都做」,
        #            拼接版把早期的关键词留着,判绿;
        #   假红 —— 反例题里中间说一句「我先读一下,看有没有冲突」就被判成误报。
        # 设计师**只会读最后那段**,判据就该判那一段。
        return {"reply": said[-1] if said else "", "trace": trace, "closed": closed,
                "changes": change_lines(ds_root), "error": None}
    except Exception as e:  # noqa: BLE001 —— 上游/环境错走环境码,不冒充失分
        return {"reply": "", "trace": [], "closed": [], "changes": 0,
                "error": f"{type(e).__name__}: {e}"}
    finally:
        shutil.rmtree(ds_root, ignore_errors=True)


def main() -> int:
    tools = tool_schemas()
    print(f"工具 {len(tools)} 个;{len(CASES)} 题(每题一个临时 DS_ROOT,预置 C1 后真执行)…\n")
    with futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda c: run_case(c, tools), CASES))

    if all(r["error"] for r in results):
        print(f"上游/环境不可用:{results[0]['error']}", file=sys.stderr)
        return 2

    fails = 0
    for case, r in zip(CASES, results):
        bad = []
        if r["error"]:
            bad.append(f"跑挂了:{r['error']}")
        reply = r["reply"]
        hits = conflict_words_in(reply)
        # 「点名」只认**旧条目独有**的特征:C1 / 蓝色。
        # 原版还认旧正文前四字「大理石背」—— 而新意见里也有「大理石背景墙」,
        # 复述一遍新意见就命中(2026-08-04 攻卷点破)。共有的词证明不了它看见了旧的。
        named = "C1" in reply.upper() or "蓝色" in reply
        if case["want_conflict"]:
            if not hits:
                bad.append("没说出这是冲突(最后那段回复里一个「冲突/打架/要不要关」都没有)")
            if not named:
                bad.append("没点名打架的那条(回复里既没 C1 也没「蓝色」)")
        elif hits:
            bad.append(f"误报冲突:与 C1 无关的一条也扯上了({hits})")
        if r["closed"]:
            bad.append(f"擅自处置旧条目:{r['closed']} —— 关不关、推不推是设计师的决定")
        if r["changes"] < case["min_changes"]:
            bad.append(f"档案里只有 {r['changes']} 条变更行,期望 ≥{case['min_changes']}"
                       "(提醒冲突不等于不记,旧行也永不删)")
        if bad:
            fails += 1
        print(f"{'ok  ' if not bad else 'FAIL'} {case['name']}")
        print(f"      调用: {' → '.join(r['trace']) or '(没调工具)'}")
        print(f"      回复: {reply[:100].replace(chr(10), ' ')}…")
        if bad:
            print(f"      失配: {'; '.join(bad)}")
    print(f"\n{'ALL PASS' if fails == 0 else f'{fails} FAIL'} / {len(CASES)} 用例")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
