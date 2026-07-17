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
]


def extract_tools():
    """从三个 MCP 文件抽 *_tool 函数名+docstring(与真部署同源的路由信号)。"""
    tools = []
    for f in ("ds_tools.py", "ds_organize.py", "ds_refs.py"):
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
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
