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
CONFLICT_WORDS = ("冲突", "打架", "矛盾", "相反", "改主意", "推翻", "取代", "作废",
                  "关掉", "关闭", "要不要关", "是否关", "还留着", "重复")

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
                if name == "set_change_status" and args.get("status") == "已关闭":
                    closed.append(args.get("change_id", "?"))
                messages.append({"role": "tool", "tool_call_id": c["id"],
                                 "content": json.dumps(run_tool(name, args, ds_root),
                                                       ensure_ascii=False)})
        return {"reply": "\n".join(said), "trace": trace, "closed": closed,
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
        flagged = any(w in reply for w in CONFLICT_WORDS)
        named = "C1" in reply.upper() or SEED["content"][:4] in reply or "蓝色" in reply
        if case["want_conflict"]:
            if not flagged:
                bad.append("没说出这是冲突(回复里一个「冲突/打架/要不要关」都没有)")
            if not named:
                bad.append("没点名打架的那条(回复里既没 C1 也没「蓝色」)")
        elif flagged:
            bad.append(f"误报冲突:与 C1 无关的一条也扯上了({[w for w in CONFLICT_WORDS if w in reply]})")
        if r["closed"]:
            bad.append(f"替设计师拍板了:自己把 {r['closed']} 关掉了,不许")
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
