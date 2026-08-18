#!/usr/bin/env python3
"""业主同意闸 oracle — track opendesign-owner-consent(O1–O8)。

跑法:  python3 tests/test_ds_consent.py

**主 agent 亲写。判据即规格 —— 实现要照这份写,不是反过来。**

## 这一单在防什么(别把它读成"加个弹窗")

0.80 给了助手读 `01-资料` 里文档的能力。而 `set_workspace` 至今**零确认**,
于是有了一条三步全是现成能力的链:

    一份被读的文档里藏一句话 → 助手改工作区根 → 读走工作区外的业主文档 → 上云

所以本单的核心判据**不是"有没有弹窗"**,是 **O2/O7:待确认期间,助手无论调哪个
工具,都拿不到新根里的任何东西**。弹窗只是让业主看见;真正挡住的是"不落盘"。

## 判据自己的两条铁律(都是第一版栽过之后加的)

1. **走模型真正走的那条路。** 第一版全部直调 `ds_tools.set_workspace()` 这样的
   核心函数,而模型调的是 MCP 包装层 `set_workspace_tool`。攻题当场给出坏实现:
   只在包装层开后门(`if os.path.isabs(root): set_mode(ALLOW)`),25 条照样全绿。
   ⇒ 现在关键路径一律**从 `ds_mcp.build()` 建出的真 server 上 `call_tool`**。
2. **canary 优先于清单。** 第一版靠一张"工具→读不读工作区根"的分类表。它拦得住
   "新加工具",拦不住**已有工具悄悄扩权**(把未批准的 root 当"预览根"读一把)。
   而且实测那张表我自己就分错了 6 个。⇒ 主闸改成**行为 canary**:三个根各放一份
   唯一的文件,真调全部工具,断言返回里**一个字节的新根 canary 都不许出现**。
   分类表降级成辅助闸(仍在,用来逼新工具回来分类)。

纯 stdlib、离线、端口 0,不烧 LLM。
"""
import asyncio
import http.client
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # design-studio/
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tests/ 自己
import _tmpreg  # noqa: E402  临时目录登记表,见 tests/_tmpreg.py
import ds_consent    # noqa: E402  ← 本单新增;判据先行时它还不存在,整份红是对的
import ds_documents  # noqa: E402
import ds_tools      # noqa: E402
import ds_web        # noqa: E402
import ds_workspace  # noqa: E402

PROJ_IN = "20260612 周宁 云栖佳苑 12#1802"   # 旧根(业主确认过的)里的项目
PROJ_OUT = "20260701 福州 机密别墅 A#0101"   # 新根(未经确认)里的项目

# ── canary:三个根各一份,文件名与正文都唯一 ──────────────────────────────────
# 断言的形状是"新根的 canary 一个字节都不许出现在任何工具的返回里"。
# 文件名也算泄露(合同标题本身就是信息),所以名字和正文都当 canary。
CANARY_OLD_NAME, CANARY_OLD_BODY = "旧根公开件.txt", "OLDCANARY一份无所谓的说明"
CANARY_NEW_NAME, CANARY_NEW_BODY = "业主合同绝密.txt", "NEWCANARY总价128万尾款3月1日"
CANARY_NEW = (CANARY_NEW_NAME, CANARY_NEW_BODY)

PENDING_ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{6}$")

# ── O7a 的分类清单(**辅助闸**,主闸是下面的 canary)──────────────────────────
# 每个 MCP 工具必须落进两个集合之一。新加工具 ⇒ 两边都不在 ⇒ O7a 红,逼你回答
# "它读到的东西,根是不是来自 workspace.json"。
#
# ⚠️ **这张表本身会分错 —— 它不是安全的承重墙。** 第一版我分错了 6 个:
#   `list_projects_tool` 其实只读 `<ds_root>/projects/*.md`(ds_tools.py:665),
#   我却当成读工作区的;而 `list_inbox_tool`(ds_intake.py:73)、
#   `adopt_workspace_tool`(ds_adopt.py:108)、`stage_adoption_tool`(:186)、
#   `stage_intake_tool`(ds_intake.py:121)、`lint_pkb_tool`(ds_lint.py:195)
#   都真的走 `ds_workspace.load_config`,我却放进了"不读"那一堆。
#   下面这版是逐个 grep `load_config` 核过的。
# ⇒ 正因为人分类会错,承重的是 canary(O7b),不是这张表。
WORKSPACE_READ_TOOLS = frozenset({
    "list_project_documents_tool",   # 列 01-资料 的文档(带文件名进对话)
    "read_project_document_tool",    # 读文档正文(**本单要防的主角**)
    "set_workspace_tool",            # 改根本体(本单要闸住的动作)
    "bind_project_tool",             # 把项目名指到根内某文件夹(本单一并受闸)
    "list_inbox_tool",               # ds_intake.list_inbox → load_config
    "adopt_workspace_tool",          # ds_adopt.adopt_scan → load_config
    "stage_adoption_tool",           # ds_adopt.stage_adoption → load_config
    "stage_intake_tool",             # ds_intake.stage_intake → load_config
    "lint_pkb_tool",                 # ds_lint 查 workspace 映射悬挂 → load_config
})
OUTSIDE_WORKSPACE_ROOT = frozenset({
    # 根是 <ds_root>/(档案本体,始终在程序自己的目录下)
    "append_change_tool", "create_client_tool", "create_project_tool",
    "delete_change_tool", "delete_project_tool", "list_projects_tool",
    "list_todos_tool", "log_communication_tool", "read_client_tool",
    "read_project_tool", "rename_project_tool", "set_change_status_tool",
    "set_due_date_tool", "set_stage_tool", "update_client_tool",
    # 纯计算,不碰盘
    "resolve_date_tool",
    # DS_ORGANIZE_ROOTS / allowed_roots 白名单(独立授权边界,set_workspace 够不着;
    # 写面还走 ds-approve 终端闸 —— proposal 明写不动这条线)
    "apply_plan_tool", "scan_dir_tool", "stage_plan_tool",
    # refs:共享图库,根同样来自 ds_root(ds_refs.py 零处 load_config)
    "add_ref_tool", "add_style_tool", "find_refs_tool", "link_ref_tool",
    "update_ref_tool",
})

# 已知覆盖不到的(记账,别假装全覆盖):这两个要非空的 assignments 数组才跑得动,
# 参数猜测器造不出来 ⇒ canary 闸照不到它们。两者都读 workspace 根,但都是**写面**、
# 且经 allowed_roots 二次限制。留给四审看要不要补。
CANARY_BLIND_SPOTS = frozenset({"stage_intake_tool", "stage_adoption_tool"})

# 必须**真的跑到业务逻辑**的工具(不是被参数校验早退)。没有这条下界,参数猜测器
# 哪天失灵,O5/O7b 会静默退化成"调了 66 次、66 次都在第一行返回 error"的空转 ——
# 看着在枚举真相源,实际什么都没验证。攻题原话:"异常还在循环里全部吞掉"。
#
# ⚠️ **不手抄。** 第一版这里是一张手写的 9 个工具的名单 —— 那就是又一张会烂的表,
# 而且烂法是**静默的**:某个真实读面既不在名单里、又跑不起来,canary 闸对它空转
# 而没有任何人会知道。现在直接由分类表减去明账盲区推出来:
# 「凡是我认定读工作区根的工具,都必须真被调到」。
# 于是两张表只剩一个真相源 —— O7a 保证分类完整,这条保证读面都真被打过。
MUST_REALLY_RUN = WORKSPACE_READ_TOOLS - CANARY_BLIND_SPOTS


def _write(path, content="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def _mkdist() -> str:
    d = _tmpreg.mkdtemp("ds_consent_dist_")
    _write(os.path.join(d, "index.html"), "<!doctype html><div>x</div>")
    return d


def _mkfixture():
    """ds_root + 两个工作区根:old(业主确认过的)、new(助手想换过去的)。

    new 根里那份 canary 就是这一单要防止被读走的东西。
    """
    ds = tempfile.mkdtemp(prefix="ds_consent_ds_")
    old = _tmpreg.mkdtemp("ds_consent_old_")
    new = _tmpreg.mkdtemp("ds_consent_new_")
    for root, proj, (name, body) in (
            (old, PROJ_IN, (CANARY_OLD_NAME, CANARY_OLD_BODY)),
            (new, PROJ_OUT, (CANARY_NEW_NAME, CANARY_NEW_BODY))):
        docs = os.path.join(root, "01-项目", proj, "01-资料")
        os.makedirs(docs)
        _write(os.path.join(docs, name), body)
        os.makedirs(os.path.join(root, "00-收件箱"), exist_ok=True)
    _write(os.path.join(ds, "config", "workspace.json"),
           json.dumps({"root": old, "projects": {}, "projectsDir": "01-项目"},
                      ensure_ascii=False))
    _write(os.path.join(ds, "projects", PROJ_IN + ".md"),
           f"# {PROJ_IN}\n\n- 阶段:方案\n")
    return ds, old, new


def _snapshot(ds_root: str) -> dict:
    """把"这道闸保护的全部状态"抓成一份可逐字节比对的快照。

    不只是 workspace.json —— 攻题第 6 条:坏工具可以只改 `config/pending/*.json`
    里记的**执行参数**(不碰批准位),业主看到的还是旧卡片,后端却按篡改后的参数执行。
    所以 pending 目录整个进快照。
    """
    out = {}
    for rel in ("config/workspace.json", "config/consent.json"):
        p = os.path.join(ds_root, rel)
        out[rel] = open(p, "rb").read() if os.path.exists(p) else None
    pdir = os.path.join(ds_root, "config", "pending")
    if os.path.isdir(pdir):
        for name in sorted(os.listdir(pdir)):
            with open(os.path.join(pdir, name), "rb") as fh:
                out[f"config/pending/{name}"] = fh.read()
    return out


@contextmanager
def _mcp(ds_root: str, organize_roots: str | None = None):
    """从真相源建出三个真 MCP server,并保证**枚举和调用都在同一环境生效期内**。

    `organize_roots` 默认指到 ds_root(= organize 系工具够不着两个工作区根,
    绝大多数用例要的就是这个)。O11 要复现的是**生产形态**:真机白名单是
    `Desktop;Downloads`,新根很可能就落在里面 —— 那种形态下 organize 系能做什么,
    必须真调一遍才算数,不能靠夹具把它屏蔽掉再宣布"验过了"。

    ⚠️ 第一版这里是普通函数、在 `finally` 里就把 DS_ROOT 恢复了,而工具是在函数
    返回**之后**才被 `call_tool` 调的。后果:O5 那条"模型碰不到开关"的闸,造一个
    真去写 consent.json 的工具都咬不住(它写到别处去了)—— 一条永远绿的摆设闸。
    """
    import ds_mcp
    old = {k: os.environ.get(k) for k in ("DS_ROOT", "DS_ORGANIZE_ROOTS")}
    os.environ["DS_ROOT"] = ds_root
    os.environ["DS_ORGANIZE_ROOTS"] = organize_roots or ds_root
    try:
        tools = []
        for key in ("tools", "organize", "refs"):
            server = ds_mcp.build(key)
            for t in asyncio.run(server.list_tools()):
                tools.append((server, t))
        yield tools
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _flatten(r) -> str:
    """FastMCP 的 `call_tool` 回的是 `list[TextContent]`(不是 dict),正文在
    每个块的 `.text` 里。**必须真解出来** —— 直接 `json.dumps(r, default=str)`
    拿到的是对象 repr,canary 搜索凑巧还能命中,但 `"error":` 判定会被转义
    带偏,于是"成功了没有"整个算错,下界闸跟着失效。"""
    if isinstance(r, dict):
        return json.dumps(r, ensure_ascii=False, default=str)
    parts = []
    for item in (r if isinstance(r, (list, tuple)) else [r]):
        t = getattr(item, "text", None)
        parts.append(t if isinstance(t, str)
                     else json.dumps(item, ensure_ascii=False, default=str))
    return "\n".join(parts)


def _call(server, name: str, args: dict):
    """调一个 MCP 工具,返回 (成功?, 返回值的字符串形式)。

    "成功" = 真跑到了业务逻辑(没抛异常、返回里没有 error 键)。这个判定要
    保守 —— 宁可少算,也不能把"早退"算成"跑过了",否则下界闸就白设了。
    """
    try:
        r = asyncio.run(server.call_tool(name, args))
    except Exception as e:                       # 参数校验抛出 = 没跑到业务逻辑
        return False, f"<exception {type(e).__name__}: {e}>"
    text = _flatten(r)
    ok = not re.search(r'"error"\s*:', text)
    return ok, text


def _args_for(tool_name: str, schema: dict, new_root: str, proj: str) -> dict:
    """按**参数名**造语义有效的参数(不是按工具名手抄清单 —— 那张表会烂)。

    值一律选"攻击者会传的那个":`root` 指向未经确认的新根,`project` 指向新根
    里的项目。工具要是真把它们当路径用了,canary 就会出现在返回里。
    """
    props = (schema or {}).get("properties") or {}
    by_name = {
        "root": new_root,
        "dir": new_root,
        "path": new_root,
        "project": proj,
        "project_key": proj,
        "name": proj,
        # folder 必须跟着 proj 一起变:bind_project 要求 folder 在**当前生效的**根里
        # 真实存在,写死成 PROJ_OUT 会让它永远在文件夹校验处早退(实测过)。
        "folder": proj,
        # rel 也跟着 proj 走:PROJ_IN 那遍要读**旧根里真实存在**的那份,
        # 好让 read_project_document_tool 真跑到业务逻辑(下界闸要的就是这个);
        # PROJ_OUT 那遍指向新根的机密件,试探"闸挡不挡得住"。
        "rel": CANARY_OLD_NAME if proj == PROJ_IN else CANARY_NEW_NAME,
        "file": CANARY_OLD_NAME if proj == PROJ_IN else CANARY_NEW_NAME,
    }
    args = {}
    for pname, spec in props.items():
        typ = spec.get("type")
        if pname in by_name:
            args[pname] = by_name[pname]
        elif typ in ("integer", "number"):
            args[pname] = 1
        elif typ == "boolean":
            args[pname] = True
        elif typ == "array":
            args[pname] = []
        elif typ == "object":
            args[pname] = {}
        else:
            args[pname] = ""
    return args


def _call_every_tool(ds_root: str, new_root: str):
    """真调全部工具,回 [(name, ok, text)]。

    **调两遍**:`project` 参数一遍给新根里的项目(PROJ_OUT,试探"能不能读到
    未批准的根"),一遍给已建档的项目(PROJ_IN,让 `bind_project_tool` 这类
    "项目必须先存在"的工具真的跑到业务逻辑)。只调一遍的话,本单明确要闸住的
    `bind_project_tool` 会在项目名校验处早退,canary 闸对它等于空转。

    ⚠️ **工具之间会互相拆台**:这一堆里混着 `delete_project_tool` /
    `rename_project_tool` 这种破坏性工具,它们会把档案删掉,于是排在后面的
    `bind_project_tool` 永远 `project_not_found`(实测:两遍都早退)。
    所以**每次调用前复原夹具**,别依赖 `list_tools()` 的顺序 —— 顺序一变,
    判据的覆盖面就会静默缩水。
    """
    out = []
    with _mcp(ds_root) as tools:
        for proj in (PROJ_OUT, PROJ_IN):
            for s, t in tools:
                _restore_fixture(ds_root)
                out.append((t.name, *_call(s, t.name,
                                           _args_for(t.name, t.inputSchema,
                                                     new_root, proj))))
    return out


def _restore_fixture(ds_root: str):
    """把档案侧的夹具复原(只碰 `projects/`,**不碰 `config/`** ——
    O5b 的快照断言正是在比对 config/ 下的东西,复原动了它就成了自欺)。"""
    _write(os.path.join(ds_root, "projects", PROJ_IN + ".md"),
           f"# {PROJ_IN}\n\n- 阶段:方案\n")


def _mcp_set_workspace(case: unittest.TestCase, ds_root: str, root: str):
    """**走模型真正走的那条路**改工作区根 —— MCP 包装层,不是核心函数。

    攻题第 1 条:判据只打核心函数时,恶意实现只要在包装层开后门就能全绿。
    """
    with _mcp(ds_root) as tools:
        server, tool = next((s, t) for s, t in tools
                            if t.name == "set_workspace_tool")
        ok, text = _call(server, tool.name, {"root": root})
    case.assertTrue(ok, f"set_workspace_tool 没跑起来,后面考不了:{text[:200]}")
    case.assertTrue(text.strip().startswith("{"),
                    f"set_workspace_tool 的返回不是 JSON 对象:{text[:200]}")
    return json.loads(text)


def _expect_pending(case: unittest.TestCase, r: dict, what: str) -> str:
    """从一个工具返回里取 pending_id。**带显式前置断言,不许直接 `[...]` 取键。**

    出处:第一版判据到处写 `set_workspace(...)["pending_id"]`,拿假实现红检时
    8 条全部红成 `KeyError` —— 红在前置塌了,真正要考的东西(掉包、重放、
    同意后可读)一条都没被考到。「红在 TypeError 上等于没红检过」的又一例。
    ⚠️ 修完之后我**又在新写的 o3e 里犯了同一次**(`r["pending_id"]`)——
    所以这里抽成唯一出口,别再各写各的。
    """
    case.assertIsInstance(r, dict, f"前置不成立:{what} 没回一个 dict:{r!r:.200}")
    case.assertTrue(r.get("pending"),
                    f"前置不成立:{what} 没排队就直接生效了 —— 后面那条根本考不了")
    case.assertIn("pending_id", r, f"前置不成立:{what} 排了队却没给 pending_id")
    return r["pending_id"]


def _pending_id(case: unittest.TestCase, ds_root: str, root: str) -> str:
    """经核心函数排一条 set_workspace 待确认并取回 id。"""
    return _expect_pending(case, ds_tools.set_workspace(root, ds_root=ds_root),
                           "set_workspace")


def _ws_bytes(ds_root: str) -> bytes:
    with open(os.path.join(ds_root, "config", "workspace.json"), "rb") as fh:
        return fh.read()


@contextmanager
def _serve(ds_root: str):
    httpd = ds_web.make_server(ds_root, _mkdist(), port=0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get_json(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", path)
    r = conn.getresponse()
    body = r.read()
    conn.close()
    return r.status, (json.loads(body.decode("utf-8")) if body else None)


def _post(port, path, body=None, ctype="application/json", raw=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    data = raw if raw is not None else json.dumps(body or {}).encode("utf-8")
    conn.request("POST", path, body=data, headers={"Content-Type": ctype})
    r = conn.getresponse()
    out = r.read()
    conn.close()
    return r.status, (json.loads(out.decode("utf-8")) if out else None)


# ══════════════════════════════════════════════════════════════════════════════
# O1 默认要问
# ══════════════════════════════════════════════════════════════════════════════
class O1_默认要问(unittest.TestCase):
    def setUp(self):
        self.ds, self.old, self.new = _mkfixture()

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def test_o1a_没有配置文件时默认是问(self):
        self.assertFalse(os.path.exists(
            os.path.join(self.ds, "config", "consent.json")))
        self.assertEqual(ds_consent.load_mode(self.ds), ds_consent.MODE_ASK)

    def test_o1b_配置坏掉也是问_fail_closed(self):
        for bad in ("{不是 json", '{"mode": "allow_everything"}', '"allow"', "[]"):
            _write(os.path.join(self.ds, "config", "consent.json"), bad)
            self.assertEqual(ds_consent.load_mode(self.ds), ds_consent.MODE_ASK,
                             f"坏配置 {bad!r} 必须 fail-closed 到 ask")

    def test_o1c_默认档下走真实mcp入口也不落盘(self):
        """**走 MCP 包装层**,不是核心函数 —— 攻题第 1 条要的就是这条。"""
        before = _ws_bytes(self.ds)
        r = _mcp_set_workspace(self, self.ds, self.new)
        self.assertTrue(r.get("pending"), "默认档必须产生待确认,不许直接生效")
        self.assertTrue(PENDING_ID_RE.match(r.get("pending_id", "")),
                        "pending_id 要有格式闸(照抄 plan_id 形状)")
        # 助手**拿不到"已生效"的任何证据**
        self.assertNotIn("root", r)
        self.assertNotIn("folder_count", r)
        self.assertEqual(_ws_bytes(self.ds), before, "待确认期间配置必须逐字节未变")

    def test_o1d_核心函数这一层也要挡住(self):
        """包装层挡住了还不够:核心函数是共用件,别处也在调它。"""
        before = _ws_bytes(self.ds)
        r = ds_tools.set_workspace(self.new, ds_root=self.ds)
        self.assertTrue(r.get("pending"))
        self.assertEqual(_ws_bytes(self.ds), before)

    def test_o1e_bind_project同样受闸(self):
        before = _ws_bytes(self.ds)
        r = ds_tools.bind_project(PROJ_IN, PROJ_IN, ds_root=self.ds)
        self.assertTrue(r.get("pending"), "bind_project 也要走同意闸")
        self.assertEqual(_ws_bytes(self.ds), before)


# ══════════════════════════════════════════════════════════════════════════════
# O2 不落盘是真的 —— **本单的核心,不是"有没有弹窗"**
# ══════════════════════════════════════════════════════════════════════════════
class O2_待确认期间读面读不到新根(unittest.TestCase):
    def setUp(self):
        self.ds, self.old, self.new = _mkfixture()

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def test_o2a_待确认期间配置逐字节未变(self):
        before = _ws_bytes(self.ds)
        _mcp_set_workspace(self, self.ds, self.new)
        self.assertEqual(_ws_bytes(self.ds), before)
        self.assertEqual(ds_workspace.load_config(self.ds)["root"],
                         os.path.realpath(self.old))

    def test_o2b_待确认期间读不到新根的文档_这条才是真正要防的(self):
        _mcp_set_workspace(self, self.ds, self.new)
        listed = ds_documents.list_documents(PROJ_OUT, ds_root=self.ds)
        self.assertFalse(listed.get("ok"),
                         "待确认期间必须读不到新根下的项目 —— 这条红了就是那条 exfil 链通了")
        self.assertEqual(listed.get("error"), "project_not_bound")

    def test_o2c_待确认期间连文件名都不该漏(self):
        _mcp_set_workspace(self, self.ds, self.new)
        r = ds_documents.read_document(PROJ_OUT, CANARY_NEW_NAME, ds_root=self.ds)
        self.assertFalse(r.get("ok"))
        blob = json.dumps(r, ensure_ascii=False)
        for canary in CANARY_NEW:
            self.assertNotIn(canary, blob)

    def test_o2d_旧根照常可读_闸不许误伤(self):
        """误报是这道闸的死法:挡住新根的同时不许把正常使用挡了。"""
        _mcp_set_workspace(self, self.ds, self.new)
        listed = ds_documents.list_documents(PROJ_IN, ds_root=self.ds)
        self.assertTrue(listed.get("ok"), "旧根(业主确认过的)必须照常能读")
        self.assertEqual([d["rel"] for d in listed["documents"]], [CANARY_OLD_NAME])


# ══════════════════════════════════════════════════════════════════════════════
# O3 确认后照 pending 里记的参数执行(防"确认后掉包")
# ══════════════════════════════════════════════════════════════════════════════
class O3_照记录参数执行(unittest.TestCase):
    def setUp(self):
        self.ds, self.old, self.new = _mkfixture()
        self.other = tempfile.mkdtemp(prefix="ds_consent_other_")

    def tearDown(self):
        for d in (self.ds, self.other):
            shutil.rmtree(d, ignore_errors=True)

    def test_o3a_同意后按记录的根生效(self):
        pid = _pending_id(self, self.ds, self.new)
        with _serve(self.ds) as port:
            st, r = _post(port, "/api/consent/resolve",
                          {"pending_id": pid, "approve": True})
        self.assertEqual(st, 200)
        self.assertTrue(r.get("ok"))
        self.assertEqual(ds_workspace.load_config(self.ds)["root"],
                         os.path.realpath(self.new))

    def test_o3b_助手中途再提一条不影响已在排队的那条(self):
        """确认后掉包:先提一个看着无害的根骗到同意,再改成别的。"""
        pid = _pending_id(self, self.ds, self.new)
        ds_tools.set_workspace(self.other, ds_root=self.ds)  # 第二条,另一个根
        with _serve(self.ds) as port:
            st, _ = _post(port, "/api/consent/resolve",
                          {"pending_id": pid, "approve": True})
        self.assertEqual(st, 200)
        self.assertEqual(ds_workspace.load_config(self.ds)["root"],
                         os.path.realpath(self.new),
                         "必须按 pending 里记的根生效,不许被后一条掉包")

    def test_o3c_拒绝之后什么都没发生(self):
        before = _ws_bytes(self.ds)
        pid = _pending_id(self, self.ds, self.new)
        with _serve(self.ds) as port:
            st, r = _post(port, "/api/consent/resolve",
                          {"pending_id": pid, "approve": False})
        self.assertEqual(st, 200)
        self.assertFalse(r.get("applied"))
        self.assertEqual(_ws_bytes(self.ds), before)

    def test_o3d_卡片内容来自落盘记录_不经助手转述(self):
        """design 硬性①:卡片由 pending json 渲染,前端只带 id。"""
        _pending_id(self, self.ds, self.new)
        with _serve(self.ds) as port:
            st, r = _get_json(port, "/api/consent")
        self.assertEqual(st, 200)
        self.assertEqual(r["mode"], ds_consent.MODE_ASK)
        self.assertEqual(len(r["pending"]), 1)
        card = r["pending"][0]
        self.assertEqual(card["action"], "set_workspace")
        self.assertEqual(card["params"]["root"], os.path.realpath(self.new))

    def test_o3e_bind_project走完整条链(self):
        """攻题第 8 条:bind 原来只测了"会排队",批准/生效那半条没测 ——
        "会排队但永远批不对"能全绿。"""
        pid = _expect_pending(
            self, ds_tools.bind_project(PROJ_IN, PROJ_IN, ds_root=self.ds),
            "bind_project")
        with _serve(self.ds) as port:
            st, _ = _post(port, "/api/consent/resolve",
                          {"pending_id": pid, "approve": True})
        self.assertEqual(st, 200)
        cfg = ds_workspace.load_config(self.ds)
        self.assertIn(PROJ_IN, cfg["projects"], "bind 同意之后必须真的写进映射")
        # 断言**寻址得到**,不是断言映射里存的那个字符串长什么样。
        # (我第一版写死成 `== PROJ_IN`,红了 —— 而 bind_project 本来就存的是
        # 相对工作区根的 rel(`01-项目/<名>`)。**这是判据的期望值错,不是实现的 bug**;
        # 按"红了先问是不是真 bug"查了既有行为才认出来。顺手把断言提到语义层:
        # 内部表示以后要是变了,这条不该跟着红。)
        self.assertEqual(
            ds_workspace.project_dir(cfg, PROJ_IN),
            os.path.realpath(os.path.join(self.old, "01-项目", PROJ_IN)),
            "bind 生效之后必须能寻址到旧根里那个真实文件夹")


# ══════════════════════════════════════════════════════════════════════════════
# O4 一次性:批过/拒过的不可重放
# ══════════════════════════════════════════════════════════════════════════════
class O4_一次性(unittest.TestCase):
    def setUp(self):
        self.ds, self.old, self.new = _mkfixture()

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def test_o4a_同意过的不能再放一次(self):
        pid = _pending_id(self, self.ds, self.new)
        with _serve(self.ds) as port:
            st1, _ = _post(port, "/api/consent/resolve",
                           {"pending_id": pid, "approve": True})
            st2, r2 = _post(port, "/api/consent/resolve",
                            {"pending_id": pid, "approve": True})
        self.assertEqual(st1, 200)
        self.assertEqual(st2, 409)
        self.assertEqual(r2["error"], "already_resolved")

    def test_o4b_拒绝过的也不能翻案(self):
        pid = _pending_id(self, self.ds, self.new)
        with _serve(self.ds) as port:
            _post(port, "/api/consent/resolve", {"pending_id": pid, "approve": False})
            st, r = _post(port, "/api/consent/resolve",
                          {"pending_id": pid, "approve": True})
        self.assertEqual(st, 409)
        self.assertEqual(r["error"], "already_resolved")
        self.assertEqual(ds_workspace.load_config(self.ds)["root"],
                         os.path.realpath(self.old))

    def test_o4c_已决的不再出现在卡片上(self):
        pid = _pending_id(self, self.ds, self.new)
        with _serve(self.ds) as port:
            _post(port, "/api/consent/resolve", {"pending_id": pid, "approve": False})
            st, r = _get_json(port, "/api/consent")
        self.assertEqual(st, 200)
        self.assertEqual(r["pending"], [])

    def test_o4d_并发批准只许生效一次(self):
        """攻题第 8 条:朴素的 check-then-act(读记录 → 看没决过 → 执行 → 标记)
        两个线程能同时越过检查。design 硬性②写死了"一次性",这条钉住它。"""
        pid = _pending_id(self, self.ds, self.new)
        codes = []
        lock = threading.Lock()

        with _serve(self.ds) as port:
            def go():
                st, _ = _post(port, "/api/consent/resolve",
                              {"pending_id": pid, "approve": True})
                with lock:
                    codes.append(st)
            threads = [threading.Thread(target=go) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        # 断言形状要**咬得住"一次性"、又不制造抖动**:核心是"恰好生效一次",
        # 不是"其余三个必须正好是 409"。后者把 HTTP 状态码的细节焊死进判据,
        # 实现换个错误码、或某个线程撞上锁超时回 500,都会让这条无缘无故地红 ——
        # 判据自己造抖动,比没有这条更糟(记忆:「判据自己会造抖动」)。
        self.assertEqual(codes.count(200), 1, f"恰好一个请求该成功,实际 {codes}")
        self.assertNotIn(200, codes[codes.index(200) + 1:],
                         f"只许有一个 200,实际 {codes}")
        # 而"只生效了一次"的真正证据在状态里,不在状态码里
        self.assertEqual(ds_workspace.load_config(self.ds)["root"],
                         os.path.realpath(self.new))
        rec = ds_consent.get_pending(self.ds, pid)
        self.assertIsNotNone(rec.get("resolved_at"), "批准之后必须落一次已决标记")


# ══════════════════════════════════════════════════════════════════════════════
# O5 模型碰不到开关 —— 从真相源枚举,逐个**真调**一遍
# ══════════════════════════════════════════════════════════════════════════════
class O5_模型碰不到开关(unittest.TestCase):
    def setUp(self):
        self.ds, self.old, self.new = _mkfixture()
        ds_consent.set_mode(self.ds, ds_consent.MODE_ASK)

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def test_o5a_参数猜测器没失灵_关键工具真的跑起来了(self):
        """**下界闸。** 没有它,参数猜测器一失灵,O5/O7b 就静默退化成
        "调了 33 次、33 次都在第一行 return error" —— 看着在枚举真相源,
        实际一个字节都没验证到。攻题原话:"异常还在循环里全部吞掉"。

        注意它同时也是一条**前提闸**:`bind_project_tool` 只有在"根没被换掉"
        时才跑得到业务逻辑。所以闸一旦失效(根真被换到新根),这条会跟着红 ——
        那是**诚实的红**:前提塌了,O5b/O7b 的结论本来也就不作数了。
        (实测:拿放行一切的假实现跑,这条确实红;闸生效时它绿。)"""
        results = _call_every_tool(self.ds, self.new)
        self.assertGreaterEqual(len(results), 66, "工具表真相源没读到(33 个工具 × 两遍)")
        ran = {name for name, ok, _t in results if ok}
        self.assertEqual(MUST_REALLY_RUN - ran, set(),
                         f"这些工具没真跑起来,判据等于空转;实际跑起来的:{sorted(ran)}")

    def test_o5b_全量工具真调一遍_受保护状态逐字节未变(self):
        """不只看开关文件 —— pending 里记的**执行参数**被改掉同样致命:
        业主看到的还是旧卡片,后端却按篡改后的参数执行(攻题第 6 条)。"""
        _pending_id(self, self.ds, self.new)
        before = _snapshot(self.ds)
        _call_every_tool(self.ds, self.new)
        after = _snapshot(self.ds)
        # 开关与工作区配置:**逐字节不变**
        for key in ("config/consent.json", "config/workspace.json"):
            self.assertEqual(after.get(key), before.get(key),
                             f"有 MCP 工具动了 {key} —— 注入只要先关掉开关,"
                             f"整道闸就是摆设")
        # 待确认记录:**已存在的一条都不许被改**(攻题第 6 条:只改执行参数、
        # 不碰批准位,业主看到的还是旧卡片,后端却按篡改后的参数执行)。
        # ⚠️ 但**允许新增** —— `set_workspace_tool` 本来就是合法产生 pending 的工具。
        # 第一版这里写的是整份快照全等,把"合法排队"也算成违规;执行腿为了让它绿,
        # 加了一条"已有未决卡就不再追加新卡"的逻辑 —— **那是我的判据逼出来的行为**,
        # 而且它会让第二次请求静默返回别人的 pending_id。判据错在先,已改。
        for key, val in before.items():
            if key.startswith("config/pending/"):
                self.assertEqual(after.get(key), val,
                                 f"有 MCP 工具改了已在排队的 {key} —— "
                                 f"业主看到的卡片和真正会执行的东西就对不上了")

    def test_o5c_开关必须住在约定的位置_且不许在workspace_json里(self):
        """两件事一起钉:

        ① 不许把锁挂在门里侧 —— `set_workspace` 自己就写 `workspace.json`;
        ② **开关必须真的落在 `config/consent.json`**。这条不是形式主义:
           O5b 那道"调完全部工具、config/ 快照逐字节不变"的闸,如果实现把档位
           藏到 `config/` 以外(快照照不到的地方),前后都是 None、断言照样绿 ——
           一个"藏别处"的实现能同时骗过 O5b 和 O5c 第一半。"""
        ds_consent.set_mode(self.ds, ds_consent.MODE_ALLOW)
        cpath = os.path.join(self.ds, "config", "consent.json")
        self.assertTrue(os.path.exists(cpath),
                        "档位必须落在 config/consent.json —— 藏别处会让 O5b 那道"
                        "快照闸整个照不到")
        self.assertIn("allow", open(cpath, encoding="utf-8").read(),
                      "consent.json 要能反映当前档位,不能是个空壳")
        raw = json.loads(_ws_bytes(self.ds).decode("utf-8"))
        self.assertNotIn("consent", raw)
        self.assertNotIn("mode", raw)


# ══════════════════════════════════════════════════════════════════════════════
# O6 关掉开关后回到今天的行为 + 两个针孔的 posture
# ══════════════════════════════════════════════════════════════════════════════
class O6_关掉开关(unittest.TestCase):
    def setUp(self):
        self.ds, self.old, self.new = _mkfixture()

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def test_o6a_不用问档下立即生效(self):
        ds_consent.set_mode(self.ds, ds_consent.MODE_ALLOW)
        r = ds_tools.set_workspace(self.new, ds_root=self.ds)
        self.assertTrue(r.get("ok"))
        self.assertNotIn("pending", r)
        self.assertEqual(r["root"], os.path.realpath(self.new))
        self.assertEqual(ds_workspace.load_config(self.ds)["root"],
                         os.path.realpath(self.new))

    def test_o6b_档位只能走ds_web的口改(self):
        with _serve(self.ds) as port:
            st, r = _post(port, "/api/consent/mode", {"mode": ds_consent.MODE_ALLOW})
        self.assertEqual(st, 200)
        self.assertEqual(r["mode"], ds_consent.MODE_ALLOW)
        self.assertEqual(ds_consent.load_mode(self.ds), ds_consent.MODE_ALLOW)

    def test_o6c_档位针孔的posture照抄针孔四(self):
        with _serve(self.ds) as port:
            st, _ = _post(port, "/api/consent/mode", {"mode": "ask"},
                          ctype="text/plain")
            self.assertEqual(st, 400, "CT 闸")
            st, _ = _post(port, "/api/consent/mode", {"mode": "ask", "x": 1})
            self.assertEqual(st, 400, "键白名单")
            st, _ = _post(port, "/api/consent/mode", {"mode": "allow_everything"})
            self.assertEqual(st, 400, "档位值白名单")
            st, _ = _post(port, "/api/consent/mode",
                          raw=b'{"mode":"' + b"a" * 100000 + b'"}')
            self.assertEqual(st, 400, "body 上限")

    def test_o6d_resolve针孔的posture也要照抄_不许只有id格式闸(self):
        """攻题第 7 条:第一版只测了 pending_id 格式,把 resolve 的 CT / body 上限 /
        键白名单 / approve 类型全漏了。坏实现可以从 body 里夹带一个 root,
        或者拿字符串 `"false"`(truthy)冒充批准,而正常路径照样全绿。"""
        pid = _pending_id(self, self.ds, self.new)
        with _serve(self.ds) as port:
            for bad in ("", "../../etc/passwd", "x" * 200, "20260810-120000-ZZZZZZ"):
                st, _ = _post(port, "/api/consent/resolve",
                              {"pending_id": bad, "approve": True})
                self.assertEqual(st, 400, f"坏 pending_id {bad!r} 必须被格式闸拦下")
            st, _ = _post(port, "/api/consent/resolve",
                          {"pending_id": pid, "approve": True}, ctype="text/plain")
            self.assertEqual(st, 400, "CT 闸")
            st, _ = _post(port, "/api/consent/resolve",
                          {"pending_id": pid, "approve": True, "root": "/tmp"})
            self.assertEqual(st, 400, "键白名单:不许从 body 夹带执行参数")
            st, _ = _post(port, "/api/consent/resolve",
                          {"pending_id": pid, "approve": "false"})
            self.assertEqual(st, 400, "approve 必须是真布尔,字符串一律拒")
            st, _ = _post(port, "/api/consent/resolve",
                          raw=b'{"pending_id":"' + b"a" * 100000 + b'"}')
            self.assertEqual(st, 400, "body 上限")
        # 上面全被拒之后,状态必须一点没动
        self.assertEqual(ds_workspace.load_config(self.ds)["root"],
                         os.path.realpath(self.old))

    def test_o6e_批准不许顺手把开关关掉(self):
        """攻题第 5 条:resolve 里偷偷 set_mode(ALLOW),此后再不弹卡 ——
        业主只点了一次同意,却把闸永久关了。"""
        pid = _pending_id(self, self.ds, self.new)
        with _serve(self.ds) as port:
            _post(port, "/api/consent/resolve", {"pending_id": pid, "approve": True})
        self.assertEqual(ds_consent.load_mode(self.ds), ds_consent.MODE_ASK,
                         "批准一条不等于把闸关了")
        # 再来一次,照样要排队
        r = ds_tools.set_workspace(self.old, ds_root=self.ds)
        self.assertTrue(r.get("pending"), "下一次仍然必须问")


# ══════════════════════════════════════════════════════════════════════════════
# O7 读面回归闸 —— 本单最值钱的一条
# ══════════════════════════════════════════════════════════════════════════════
class O7_读面不许绕过同意闸(unittest.TestCase):
    def setUp(self):
        self.ds, self.old, self.new = _mkfixture()

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def test_o7a_每个工具都必须被分类_新工具会让这条红(self):
        """**辅助闸**(主闸是 o7b 的 canary)。它拦得住"新加工具",拦不住
        "已有工具悄悄扩权" —— 而且这张表我自己就分错过 6 个。别高估它。"""
        with _mcp(self.ds) as tools:
            actual = {t.name for _s, t in tools}
        classified = WORKSPACE_READ_TOOLS | OUTSIDE_WORKSPACE_ROOT
        self.assertEqual(
            actual - classified, set(),
            "有新 MCP 工具没被分类。回答一个问题:它读到的东西,根是不是来自 "
            "workspace.json?是 → 加进 WORKSPACE_READ_TOOLS 并给它补 canary 断言;"
            "否 → 加进 OUTSIDE_WORKSPACE_ROOT 并写清它的根是谁给的。")
        self.assertEqual(classified - actual, set(),
                         "分类清单里有已经不存在的工具 —— 清单比代码旧了,删掉它。")

    def test_o7b_主闸_待确认期间任何工具都不许吐出新根的canary(self):
        """**不变量:「助手能读到的根」⊆「业主确认过的根」。**

        这条不依赖"我有没有把工具分类分对" —— 它真调全部工具,逐个搜返回值。
        谁把未批准的 root 当"预览根"读一把(攻题第 3 条的坏实现),当场现形。
        """
        _mcp_set_workspace(self, self.ds, self.new)
        results = _call_every_tool(self.ds, self.new)
        ran = {name for name, ok, _t in results if ok}
        self.assertEqual(MUST_REALLY_RUN - ran, set(),
                         "关键工具没真跑起来 —— 这条 canary 闸等于空转")
        for name, _ok, text in results:
            for canary in CANARY_NEW:
                self.assertNotIn(
                    canary, text,
                    f"{name} 的返回里出现了**未经业主确认的新根**里的东西"
                    f"({canary!r})—— 那条 exfil 链就是从这儿通的")

    def test_o7c_业主点头之后才读得到(self):
        """闸的边界:它挡不住"业主自己点了同意",只把攻击成本抬到
        "得骗过业主眼皮底下的一张卡"。也顺带证明这道闸不是把功能焊死了。"""
        pid = _pending_id(self, self.ds, self.new)
        with _serve(self.ds) as port:
            _post(port, "/api/consent/resolve", {"pending_id": pid, "approve": True})
        listed = ds_documents.list_documents(PROJ_OUT, ds_root=self.ds)
        self.assertTrue(listed.get("ok"))
        self.assertEqual([d["rel"] for d in listed["documents"]], [CANARY_NEW_NAME])


# ══════════════════════════════════════════════════════════════════════════════
# O10 卡片显示的 = 实际执行的(跨卡片版)
# ══════════════════════════════════════════════════════════════════════════════
class O10_排队期间根变了就不许再照原样执行(unittest.TestCase):
    """四审 subdeepseek 中危发现(2026-08-11)。design 硬性②说的是「执行时用
    pending 里记的参数」,但 `bind_project` 的参数是**文件夹名**,而名字要靠
    当时的工作区根才解析得成路径。

    于是两张卡同时排队时:先批 set_workspace(根换了)→ 再批 bind,
    bind 会拿**新根**去解析那个名字 —— 新根里恰好有同名夹就绑到**物理上另一个
    文件夹**,而业主在卡上只看见过一个名字。这正是本单要防的
    「卡片显示的和实际执行的不是一回事」,只是发生在两张卡之间。

    定的规矩:pending 记下它被创建时的工作区根;批准时根若已经变了,
    **拒绝执行**(`stale_pending`),让业主重新提一次 —— 重提的成本很低,
    而"绑错文件夹"是静默的。
    """

    def setUp(self):
        self.ds, self.old, self.new = _mkfixture()
        # 新根里也放一个**同名**项目夹:这就是"名字一样、物理上是另一个"的陷阱
        os.makedirs(os.path.join(self.new, "01-项目", PROJ_IN, "01-资料"))
        _write(os.path.join(self.new, "01-项目", PROJ_IN, "01-资料", "冒牌件.txt"), "X")

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def test_o10a_根换掉之后旧的bind卡不许再执行(self):
        bind_pid = _expect_pending(
            self, ds_tools.bind_project(PROJ_IN, PROJ_IN, ds_root=self.ds), "bind_project")
        ws_pid = _pending_id(self, self.ds, self.new)
        with _serve(self.ds) as port:
            st, _ = _post(port, "/api/consent/resolve",
                          {"pending_id": ws_pid, "approve": True})
            self.assertEqual(st, 200, "前置:换根那张卡该批得过")
            st2, r2 = _post(port, "/api/consent/resolve",
                            {"pending_id": bind_pid, "approve": True})
        self.assertNotEqual(st2, 200,
                            "根都换了,这张卡上的文件夹名已经指向另一个地方,不许照批")
        self.assertEqual((r2 or {}).get("error"), "stale_pending")
        cfg = ds_workspace.load_config(self.ds)
        self.assertNotIn(PROJ_IN, cfg.get("projects", {}),
                         "不许把项目绑到新根里那个同名的冒牌文件夹")

    def test_o10b_根没变时照常批得过_不许误伤(self):
        """误报是这道闸的死法:没换根的正常情形必须一路畅通。"""
        pid = _expect_pending(
            self, ds_tools.bind_project(PROJ_IN, PROJ_IN, ds_root=self.ds), "bind_project")
        with _serve(self.ds) as port:
            st, _ = _post(port, "/api/consent/resolve", {"pending_id": pid, "approve": True})
        self.assertEqual(st, 200)
        cfg = ds_workspace.load_config(self.ds)
        self.assertEqual(ds_workspace.project_dir(cfg, PROJ_IN),
                         os.path.realpath(os.path.join(self.old, "01-项目", PROJ_IN)))

    def test_o10c_过期的卡也不许被拒绝以外的方式留着(self):
        """过期 ≠ 卡死:业主还得能把它拒掉清屏。"""
        bind_pid = _expect_pending(
            self, ds_tools.bind_project(PROJ_IN, PROJ_IN, ds_root=self.ds), "bind_project")
        ws_pid = _pending_id(self, self.ds, self.new)
        with _serve(self.ds) as port:
            _post(port, "/api/consent/resolve", {"pending_id": ws_pid, "approve": True})
            st, _ = _post(port, "/api/consent/resolve",
                          {"pending_id": bind_pid, "approve": False})
        self.assertEqual(st, 200, "过期的卡必须还能被拒绝掉")


# ══════════════════════════════════════════════════════════════════════════════
# O9 锁序:不许出现 AB-BA 死锁
# ══════════════════════════════════════════════════════════════════════════════
class O9_锁序不许成环(unittest.TestCase):
    """四审 subdeepseek **孤腿 BLOCK**(2026-08-11)—— 我自己审 diff 时没看出来。

    本单一下子有了两把锁,而它们被两条路径以**相反的顺序**获取:

      resolve_pending: pending.lock → (apply_fn) → workspace.lock
      bind_project   : workspace.lock → (create_pending) → pending.lock

    经典 AB-BA。Linux 的 flock 无限阻塞、`resolve_pending` 又没有超时 ⇒
    **两边永久挂死**,而且挂死的那条 ds_web 线程从此占死 pending.lock,
    之后所有待确认的创建与批准全部卡住,只能重启。

    为什么不能当"罕见竞态"放过:威胁模型里的助手是**被注入控制**的,
    它可以连续狂调 `bind_project_tool`,只要在业主点卡的那几百毫秒里抢到一次
    workspace.lock 就死锁 —— **窗口小,但攻击者可以让它必然撞上**。
    这把"业主点头"这个唯一的人工通道变成了可被 DoS 的目标。

    判据形状:不去真的制造死锁(那会让判据自己挂住),而是钉**结构不变量**:
    `create_pending` 永远不许在持有 workspace 锁的时候被调用。
    """

    def setUp(self):
        self.ds, self.old, self.new = _mkfixture()

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def _held_roots(self):
        """当前线程持有的 workspace 锁(ds_tools 的重入闸用的那个 thread-local)。"""
        return set(getattr(ds_tools._ws_lock_held, "roots", set()) or set())

    def test_o9a_bind排队时不许还攥着workspace锁(self):
        seen = {}
        real = ds_consent.create_pending

        def spy(ds_root, action, params):
            seen["held"] = self._held_roots()
            return real(ds_root, action, params)

        ds_consent.create_pending = spy
        try:
            r = ds_tools.bind_project(PROJ_IN, PROJ_IN, ds_root=self.ds)
        finally:
            ds_consent.create_pending = real
        self.assertTrue(r.get("pending"), f"前置不成立:没排队,这条考不了({r})")
        self.assertEqual(
            seen.get("held"), set(),
            "bind 在**持着 workspace 锁**的时候去拿 pending 锁 —— 与 resolve_pending "
            "的锁序正好相反,构成 AB-BA 死锁(Linux 上是永久挂死)")

    def test_o9b_set_workspace排队时同样不许攥着锁(self):
        seen = {}
        real = ds_consent.create_pending

        def spy(ds_root, action, params):
            seen["held"] = self._held_roots()
            return real(ds_root, action, params)

        ds_consent.create_pending = spy
        try:
            r = ds_tools.set_workspace(self.new, ds_root=self.ds)
        finally:
            ds_consent.create_pending = real
        self.assertTrue(r.get("pending"), f"前置不成立:没排队({r})")
        self.assertEqual(seen.get("held"), set(),
                         "set_workspace 排队时攥着 workspace 锁")

    def test_o9c_两条路径真并发跑不许挂死(self):
        """结构闸之外再来一发行为闸:一边狂调 bind、一边批准,限时跑完。

        真挂死的话这条会**超时红**(不是永远挂住:用带 timeout 的 join 判定)。
        """
        pid = _pending_id(self, self.ds, self.new)
        stop = threading.Event()
        errors = []

        def hammer():                      # 模拟被注入的助手连续触发受闸工具
            while not stop.is_set():
                try:
                    ds_tools.bind_project(PROJ_IN, PROJ_IN, ds_root=self.ds)
                except Exception as e:     # noqa: BLE001
                    errors.append(repr(e))
                    return

        def approve():
            with _serve(self.ds) as port:
                _post(port, "/api/consent/resolve",
                      {"pending_id": pid, "approve": True})

        t1 = threading.Thread(target=hammer, daemon=True)
        t2 = threading.Thread(target=approve, daemon=True)
        t1.start()
        t2.start()
        t2.join(timeout=25)
        alive = t2.is_alive()
        stop.set()
        t1.join(timeout=10)
        self.assertFalse(alive, "批准那条线程 25 秒没回来 —— 锁序成环挂死了")
        self.assertEqual(errors, [], f"并发里出了异常:{errors}")


# ══════════════════════════════════════════════════════════════════════════════
# O8 网页那一侧:GET 必须是纯展示
# ══════════════════════════════════════════════════════════════════════════════
class O8_GET不许有副作用(unittest.TestCase):
    def setUp(self):
        self.ds, self.old, self.new = _mkfixture()

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def test_o8a_反复取卡片不许改变任何状态(self):
        """攻题第 2 条(严重):`_get_consent` 里顺手把所有卡片 approve 掉、
        再把执行**之前**抓到的列表返回出去 —— O3d 那种"只看返回 JSON"的断言
        完全看不见,而现实中网页轮询一轮就已经换了根,业主一次都没点。"""
        _pending_id(self, self.ds, self.new)
        before = _snapshot(self.ds)
        with _serve(self.ds) as port:
            for _ in range(3):
                st, r = _get_json(port, "/api/consent")
                self.assertEqual(st, 200)
                self.assertEqual(len(r["pending"]), 1, "取一次就少一张卡?")
        self.assertEqual(_snapshot(self.ds), before,
                         "GET /api/consent 改动了状态 —— 它必须是纯展示")
        self.assertEqual(ds_workspace.load_config(self.ds)["root"],
                         os.path.realpath(self.old))

    def test_o8b_只读铁律没被这两个针孔破坏(self):
        """新开两个 POST 针孔,不许把别的写方法一起放开。"""
        with _serve(self.ds) as port:
            for path in ("/api/consent", "/api/consent/mode", "/api/consent/resolve"):
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                conn.request("PUT", path, body=b"{}",
                             headers={"Content-Type": "application/json"})
                st = conn.getresponse().status
                conn.close()
                self.assertEqual(st, 405, f"PUT {path} 必须维持 405")


# ══════════════════════════════════════════════════════════════════════════════
# O11 生产形态下的 organize 白名单:文件名枚举得到,正文一个字都不许
# ══════════════════════════════════════════════════════════════════════════════
class O11_organize白名单是一条明账边界(unittest.TestCase):
    """四审 subdeepseek 的 Q1/Q3:**别的用例把这个形状屏蔽掉了**。

    其余用例的夹具把 `DS_ORGANIZE_ROOTS` 设成 ds_root(一个与两个工作区根都无关的
    临时目录)⇒ `scan_dir_tool(新根)` 必然 `root_not_allowed` 早退,canary 闸对它
    **空转**。而真机模板 `config/nanobot.config.windows.jsonc` 的白名单是
    `Desktop;Downloads` —— 业主的设计项目文件夹十有八九就在里面。

    所以这道闸不复现生产形态就等于没验。复现之后,事实是两句话:

    - **文件名/大小/修改时间:枚举得到。** organize 是**另一条独立授权线**
      (白名单 + 终端 `ds-approve`),proposal 明写这一单不动它。
      于是"待确认期间新根一个字都读不到"这句话,**准确说法是"正文一个字都读不到"**。
      这是本单**接受的边界**,写在 verify.md 的 Accepted deviations 里。
    - **正文:一个字都不许。** 这条是承重的 —— 哪天有人给 scan_dir 加个"顺手预览
      前 200 字"的好意,o11b 当场红。

    ⚠️ o11a 断言的是**今天接受的边界**(名字确实列得出来)。哪天把 organize 也纳入
    同意闸,它会红 —— **那是好消息**:改断言,并在 verify 里记一笔边界收窄了。
    """

    def setUp(self):
        self.ds, self.old, self.new = _mkfixture()
        # 生产白名单是 Desktop 这类**祖先目录**,不是新根本身。用父目录才复现得出
        # "新根恰好落在白名单里"的形状。
        self.desk = os.path.dirname(os.path.realpath(self.new))

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def _scan_new_root_while_pending(self):
        """排一条待确认(闸还没放行),然后在生产白名单下真调一次 scan_dir_tool。"""
        _mcp_set_workspace(self, self.ds, self.new)
        self.assertEqual(ds_workspace.load_config(self.ds)["root"],
                         os.path.realpath(self.old),
                         "前置不成立:根已经换过去了,这条考的就不是待确认期间")
        with _mcp(self.ds, organize_roots=self.desk) as tools:
            server, tool = next((s, t) for s, t in tools if t.name == "scan_dir_tool")
            return _call(server, tool.name, {"root": self.new})

    def test_o11a_明账边界_白名单覆盖到新根时文件名枚举得到(self):
        ok, text = self._scan_new_root_while_pending()
        self.assertTrue(ok, f"前置不成立:scan_dir_tool 没跑到业务逻辑:{text[:200]}")
        self.assertIn(CANARY_NEW_NAME, text,
                      "这条断言钉的是**今天接受的边界**。它红了通常意味着 organize "
                      "也被纳入了同意闸 —— 那是好消息:改这条断言,并在 verify.md "
                      "的 Accepted deviations 里把这条边界划掉。")

    def test_o11b_承重_scan_dir只回名字_正文一个字都不许(self):
        ok, text = self._scan_new_root_while_pending()
        self.assertTrue(ok, f"前置不成立:scan_dir_tool 没跑到业务逻辑:{text[:200]}")
        self.assertNotIn(
            CANARY_NEW_BODY, text,
            "scan_dir 把**未经业主确认的新根**里的文件正文吐出来了 —— "
            "同意闸挡的就是这条链,organize 那条独立授权线不许在这里破口")

    def test_o11c_同意闸本身没塌_正经读面仍然读不到新根(self):
        """把 o11a/o11b 摆在一起才有意义:名字列得出来 ≠ 闸塌了。"""
        self._scan_new_root_while_pending()
        r = ds_documents.read_document(PROJ_OUT, CANARY_NEW_NAME, ds_root=self.ds)
        self.assertFalse(r.get("ok"), f"待确认期间读到了新根的文档:{r!r:.200}")
        for canary in CANARY_NEW:
            self.assertNotIn(canary, json.dumps(r, ensure_ascii=False, default=str))


if __name__ == "__main__":
    unittest.main(verbosity=2)
