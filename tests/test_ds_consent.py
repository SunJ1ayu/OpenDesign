#!/usr/bin/env python3
"""业主同意闸 oracle — track opendesign-owner-consent(O1–O7)。

跑法:  python3 tests/test_ds_consent.py

**主 agent 亲写。判据即规格 —— 实现要照这份写,不是反过来。**

## 这一单在防什么(别把它读成"加个弹窗")

0.80 给了助手读 `01-资料` 里文档的能力。而 `set_workspace` 至今**零确认**,
于是有了一条三步全是现成能力的链:

    一份被读的文档里藏一句话 → 助手改工作区根 → 读走工作区外的业主文档 → 上云

所以本单的核心判据**不是"有没有弹窗"**,是 **O2/O7:待确认期间,读面读到的
仍然是旧根**。弹窗只是让业主看见;真正挡住的是"不落盘"。

## 两条"不许手抄清单"的闸(anydoc 那单栽过)

- **O5**:从工具表真相源枚举全部 MCP 工具,**逐个真调一遍**,断言开关文件
  逐字节未变、没有任何待确认项被批准。不是 grep 源码,是真打一遍。
- **O7a**:全量工具名必须与本文件的分类清单**完全相等**。谁新加一个工具而
  不回来分类,这条当场红 —— 这就是"下一个扩读面的人会被拦住"的机械实现,
  不靠他记得回来看注释。

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
import ds_consent    # noqa: E402  ← 本单新增;判据先行时它还不存在,整份红是对的
import ds_documents  # noqa: E402
import ds_tools      # noqa: E402
import ds_web        # noqa: E402
import ds_workspace  # noqa: E402

PROJ_IN = "20260612 周宁 云栖佳苑 12#1802"   # 旧根(业主确认过的)里的项目
PROJ_OUT = "20260701 福州 机密别墅 A#0101"   # 新根(未经确认)里的项目
SECRET = "业主合同-绝密.txt"

PENDING_ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{6}$")

# ── O7a 的分类清单 ────────────────────────────────────────────────────────────
# 每个 MCP 工具必须落进下面两个集合之一。**新加工具 ⇒ 两边都不在 ⇒ O7a 红。**
# 那时候要回答的问题只有一个:**它读到的东西,根是不是来自 workspace.json?**
# 是 → 进 WORKSPACE_READ_TOOLS,并给它补一条 O7b 那样的行为断言;
# 否 → 进 OUTSIDE_WORKSPACE_ROOT,并在下面写清楚它的根是谁给的。
#
# 为什么要有这张表:0.80 加 read_project_document_tool 时,`set_workspace` 头上
# 那条"不拓宽 LLM 能读并上云的内容"的安全论证**当场失效了,却没人发现** ——
# 因为没有任何东西逼那次改动回头看它。这张表就是那个"逼"。
WORKSPACE_READ_TOOLS = frozenset({
    # 读根 = workspace.json.root → 受本单的同意闸保护
    "list_project_documents_tool",   # 列 01-资料 的文档(带文件名进对话)
    "read_project_document_tool",    # 读文档正文(**本单要防的主角**)
    "list_projects_tool",            # 扫工作区下的项目夹名
    "bind_project_tool",             # 把项目名指到根内某文件夹(本单一并受闸)
    "set_workspace_tool",            # 改根本体(本单要闸住的动作)
})
OUTSIDE_WORKSPACE_ROOT = frozenset({
    # 读写根**不是** workspace.json.root,因此改根影响不到它们:
    # ── ds_root/(档案本体,始终在程序自己的目录下)
    "append_change_tool", "create_client_tool", "create_project_tool",
    "delete_change_tool", "delete_project_tool", "lint_pkb_tool",
    "list_todos_tool", "log_communication_tool", "read_client_tool",
    "read_project_tool", "rename_project_tool", "set_change_status_tool",
    "set_due_date_tool", "set_stage_tool", "update_client_tool",
    # ── 纯计算,不碰盘
    "resolve_date_tool",
    # ── DS_ORGANIZE_ROOTS 白名单(独立 env,set_workspace 够不着;
    #    且写面走 ds-approve 终端闸,比本单的网页闸更强 —— proposal 明写不动它)
    "adopt_workspace_tool", "apply_plan_tool", "list_inbox_tool",
    "scan_dir_tool", "stage_adoption_tool", "stage_intake_tool",
    "stage_plan_tool",
    # ── refs:共享图库,根同样来自 ds_root
    "add_ref_tool", "add_style_tool", "find_refs_tool", "link_ref_tool",
    "update_ref_tool",
})


def _write(path, content="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def _mkdist() -> str:
    d = tempfile.mkdtemp(prefix="ds_consent_dist_")
    _write(os.path.join(d, "index.html"), "<!doctype html><div>x</div>")
    return d


def _mkfixture():
    """ds_root + 两个工作区根:old(业主确认过的)、new(助手想换过去的)。

    new 根里放一份"业主合同",它就是这一单要防止被读走的东西。
    """
    ds = tempfile.mkdtemp(prefix="ds_consent_ds_")
    old = tempfile.mkdtemp(prefix="ds_consent_old_")
    new = tempfile.mkdtemp(prefix="ds_consent_new_")
    os.makedirs(os.path.join(old, "01-项目", PROJ_IN, "01-资料"))
    _write(os.path.join(old, "01-项目", PROJ_IN, "01-资料", "公开说明.txt"), "无所谓")
    os.makedirs(os.path.join(new, "01-项目", PROJ_OUT, "01-资料"))
    _write(os.path.join(new, "01-项目", PROJ_OUT, "01-资料", SECRET),
           "总价 128 万,尾款 3 月 1 日前付清。")
    _write(os.path.join(ds, "config", "workspace.json"),
           json.dumps({"root": old, "projects": {}, "projectsDir": "01-项目"},
                      ensure_ascii=False))
    return ds, old, new


def _pending_id(case: unittest.TestCase, ds_root: str, root: str) -> str:
    """排一条待确认并取回它的 id。**带显式前置断言,不许直接 `[...]` 取键。**

    出处(红检时自己撞见的):第一版这里是
    `pid = ds_tools.set_workspace(...)["pending_id"]`。拿假实现红检时,O3/O4/O7c
    共 8 条全部红成 `KeyError: 'pending_id'` —— 红是红了,但**红在前置塌了**,
    它们真正要考的东西(掉包、重放、同意后可读)一条都没被考到。
    记忆里那条「红在 TypeError 上等于没红检过」的又一例,这次是我自己写的判据。
    """
    r = ds_tools.set_workspace(root, ds_root=ds_root)
    case.assertTrue(r.get("pending"),
                    "前置不成立:默认档没有排队就直接生效了 —— 后面那条根本考不了")
    case.assertIn("pending_id", r, "前置不成立:排了队却没给 pending_id")
    return r["pending_id"]


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
        # 坏 JSON / 认不出的档位,都必须退到"问",不许退到"放行"。
        for bad in ("{不是 json", '{"mode": "allow_everything"}', '"allow"', "[]"):
            _write(os.path.join(self.ds, "config", "consent.json"), bad)
            self.assertEqual(ds_consent.load_mode(self.ds), ds_consent.MODE_ASK,
                             f"坏配置 {bad!r} 必须 fail-closed 到 ask")

    def test_o1c_默认档下set_workspace不落盘只产生待确认(self):
        before = _ws_bytes(self.ds)
        r = ds_tools.set_workspace(self.new, ds_root=self.ds)
        self.assertTrue(r.get("pending"), "默认档必须产生待确认,不许直接生效")
        self.assertTrue(PENDING_ID_RE.match(r.get("pending_id", "")),
                        "pending_id 要有格式闸(照抄 plan_id 形状)")
        # 助手**拿不到"已生效"的任何证据**:不回 root、不回 folder_count
        self.assertNotIn("root", r)
        self.assertNotIn("folder_count", r)
        self.assertEqual(_ws_bytes(self.ds), before, "待确认期间配置必须逐字节未变")

    def test_o1d_bind_project同样受闸(self):
        _write(os.path.join(self.ds, "projects", PROJ_IN + ".md"), "# x\n")
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
        ds_tools.set_workspace(self.new, ds_root=self.ds)
        self.assertEqual(_ws_bytes(self.ds), before)
        self.assertEqual(ds_workspace.load_config(self.ds)["root"],
                         os.path.realpath(self.old))

    def test_o2b_待确认期间读不到新根的文档_这条才是真正要防的(self):
        ds_tools.set_workspace(self.new, ds_root=self.ds)
        listed = ds_documents.list_documents(PROJ_OUT, ds_root=self.ds)
        self.assertFalse(listed.get("ok"),
                         "待确认期间必须读不到新根下的项目 —— 这条红了就是那条 exfil 链通了")
        self.assertEqual(listed.get("error"), "project_not_bound")

    def test_o2c_待确认期间连文件名都不该漏(self):
        # 只列文件名也是泄露(合同标题本身就是信息)。
        ds_tools.set_workspace(self.new, ds_root=self.ds)
        r = ds_documents.read_document(PROJ_OUT, SECRET, ds_root=self.ds)
        self.assertFalse(r.get("ok"))
        self.assertNotIn(SECRET, json.dumps(r, ensure_ascii=False))

    def test_o2d_旧根照常可读_闸不许误伤(self):
        # 误报是这道闸的死法:挡住新根的同时不许把正常使用挡了。
        ds_tools.set_workspace(self.new, ds_root=self.ds)
        listed = ds_documents.list_documents(PROJ_IN, ds_root=self.ds)
        self.assertTrue(listed.get("ok"), "旧根(业主确认过的)必须照常能读")
        self.assertEqual([d["rel"] for d in listed["documents"]], ["公开说明.txt"])


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
        """确认后掉包:助手先提一个看着无害的根骗到同意,再改成别的。
        执行必须照**第一条 pending 里记的参数**,不是助手最后一次说的。"""
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
        """design 硬性①:卡片由 pending json 渲染。前端只带 id,
        所以 GET 必须自己把"要干什么"说清楚。"""
        ds_tools.set_workspace(self.new, ds_root=self.ds)
        with _serve(self.ds) as port:
            st, r = _get_json(port, "/api/consent")
        self.assertEqual(st, 200)
        self.assertEqual(r["mode"], ds_consent.MODE_ASK)
        self.assertEqual(len(r["pending"]), 1)
        card = r["pending"][0]
        self.assertEqual(card["action"], "set_workspace")
        self.assertEqual(card["params"]["root"], os.path.realpath(self.new))


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


# ══════════════════════════════════════════════════════════════════════════════
# O5 模型碰不到开关 —— 从真相源枚举,逐个真调一遍
# ══════════════════════════════════════════════════════════════════════════════
@contextmanager
def _mcp_tools(ds_root: str):
    """(server, tool) 全量,来自 ds_mcp.build —— **真相源,不手抄**。

    `build(key)` 只收一个参数,ds_root 走 DS_ROOT 环境变量(ds_*_server.build
    的默认值就是读它)。这里显式覆盖,免得判据打到真仓库上。

    ⚠️ **为什么是 contextmanager 而不是普通函数**(攻我自己的题时抓到的判据 bug):
    第一版写成 `_all_tools()` 返回列表、在 `finally` 里就把 DS_ROOT 恢复了 ——
    而工具是在函数**返回之后**才被 `call_tool` 调用的。于是任何在**调用时**
    读 DS_ROOT 的代码都会打到错误的根上。实测后果:O5a 那条"模型碰不到开关"
    的闸,**造一个真去写 consent.json 的工具都咬不住它**(它写到别处去了)——
    一条永远绿的摆设闸,而且绿得理直气壮。
    ⇒ 枚举**和调用**必须都在环境生效期内。
    """
    import ds_mcp
    old_ds, old_org = os.environ.get("DS_ROOT"), os.environ.get("DS_ORGANIZE_ROOTS")
    os.environ["DS_ROOT"] = ds_root
    os.environ["DS_ORGANIZE_ROOTS"] = ds_root
    try:
        out = []
        for key in ("tools", "organize", "refs"):
            server = ds_mcp.build(key)
            for t in asyncio.run(server.list_tools()):
                out.append((server, t))
        yield out
    finally:
        for k, v in (("DS_ROOT", old_ds), ("DS_ORGANIZE_ROOTS", old_org)):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _dummy_args(schema: dict) -> dict:
    """按 inputSchema 造一组"类型合法但内容恶意"的参数。
    目的不是让工具成功,是让它**真的跑起来**,好看看它碰不碰得到开关。"""
    props = (schema or {}).get("properties") or {}
    args = {}
    for name, spec in props.items():
        typ = spec.get("type")
        if typ == "integer" or typ == "number":
            args[name] = 1
        elif typ == "boolean":
            args[name] = True
        elif typ == "array":
            args[name] = []
        elif typ == "object":
            args[name] = {}
        else:
            # 字符串位一律塞"指着开关文件"的值 —— 谁把入参当路径直接用,这里就会现形
            args[name] = "../config/consent.json"
    return args


class O5_模型碰不到开关(unittest.TestCase):
    def setUp(self):
        self.ds, self.old, self.new = _mkfixture()
        ds_consent.set_mode(self.ds, ds_consent.MODE_ASK)

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def test_o5a_全量工具真调一遍_开关文件逐字节未变(self):
        cpath = os.path.join(self.ds, "config", "consent.json")
        with open(cpath, "rb") as fh:
            before = fh.read()
        with _mcp_tools(self.ds) as tools:
            self.assertGreaterEqual(len(tools), 33, "工具表真相源没读到,判据等于没跑")
            for server, t in tools:
                try:
                    asyncio.run(server.call_tool(t.name, _dummy_args(t.inputSchema)))
                except Exception:
                    pass  # 参数不合法而失败是预期的;只关心它有没有碰到开关
        with open(cpath, "rb") as fh:
            self.assertEqual(fh.read(), before,
                             "有 MCP 工具改到了同意开关 —— 注入只要先关掉它,整道闸就是摆设")

    def test_o5b_全量工具真调一遍_不许批准任何待确认项(self):
        pid = _pending_id(self, self.ds, self.new)
        with _mcp_tools(self.ds) as tools:
            for server, t in tools:
                try:
                    asyncio.run(server.call_tool(t.name, _dummy_args(t.inputSchema)))
                except Exception:
                    pass
        rec = ds_consent.get_pending(self.ds, pid)
        self.assertIsNotNone(rec)
        self.assertIsNone(rec.get("resolved_at"), "有工具把待确认项自己批了")
        self.assertEqual(ds_workspace.load_config(self.ds)["root"],
                         os.path.realpath(self.old))

    def test_o5c_开关不许住在workspace_json里(self):
        """把锁挂在门里侧:set_workspace 自己就写 workspace.json。"""
        ds_consent.set_mode(self.ds, ds_consent.MODE_ALLOW)
        raw = json.loads(_ws_bytes(self.ds).decode("utf-8"))
        self.assertNotIn("consent", raw)
        self.assertNotIn("mode", raw)


# ══════════════════════════════════════════════════════════════════════════════
# O6 关掉开关后回到今天的行为
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
            st2, _ = _get_json(port, "/api/consent")
        self.assertEqual(st2, 200)
        self.assertEqual(ds_consent.load_mode(self.ds), ds_consent.MODE_ALLOW)

    def test_o6c_档位针孔的posture照抄针孔四(self):
        with _serve(self.ds) as port:
            # CT 闸
            st, _ = _post(port, "/api/consent/mode", {"mode": "ask"},
                          ctype="text/plain")
            self.assertEqual(st, 400)
            # 键白名单
            st, _ = _post(port, "/api/consent/mode", {"mode": "ask", "x": 1})
            self.assertEqual(st, 400)
            # 档位值白名单
            st, _ = _post(port, "/api/consent/mode", {"mode": "allow_everything"})
            self.assertEqual(st, 400)
            # body 上限
            st, _ = _post(port, "/api/consent/mode",
                          raw=b'{"mode":"' + b"a" * 100000 + b'"}')
            self.assertEqual(st, 400)

    def test_o6d_resolve针孔的id格式闸(self):
        with _serve(self.ds) as port:
            for bad in ("", "../../etc/passwd", "x" * 200, "20260810-120000-ZZZZZZ"):
                st, _ = _post(port, "/api/consent/resolve",
                              {"pending_id": bad, "approve": True})
                self.assertEqual(st, 400, f"坏 pending_id {bad!r} 必须被格式闸拦下")


# ══════════════════════════════════════════════════════════════════════════════
# O7 读面回归闸 —— 本单最值钱的一条
# ══════════════════════════════════════════════════════════════════════════════
class O7_读面不许绕过同意闸(unittest.TestCase):
    def setUp(self):
        self.ds, self.old, self.new = _mkfixture()

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def test_o7a_每个工具都必须被分类_新工具会让这条红(self):
        """**这条就是"下一个扩读面的人会被拦住"的机械实现。**

        0.80 加读文档能力时,`set_workspace` 头上那条"不拓宽 LLM 能读并上云的
        内容"的论证当场失效却没人发现 —— 因为没有任何东西逼那次改动回头看它。
        现在有了:新工具不在下面两个集合里,这条当场红。
        """
        with _mcp_tools(self.ds) as tools:
            actual = {t.name for _s, t in tools}
        classified = WORKSPACE_READ_TOOLS | OUTSIDE_WORKSPACE_ROOT
        self.assertEqual(
            actual - classified, set(),
            "有新 MCP 工具没被分类。回答一个问题:它读到的东西,根是不是来自 "
            "workspace.json?是 → 加进 WORKSPACE_READ_TOOLS 并补一条行为断言;"
            "否 → 加进 OUTSIDE_WORKSPACE_ROOT 并写清它的根是谁给的。")
        self.assertEqual(
            classified - actual, set(),
            "分类清单里有已经不存在的工具 —— 清单比代码旧了,删掉它。")

    def test_o7b_不变量_读到的根必须是业主确认过的根(self):
        """不变量一句话:**「read_document 能读到的根」⊆「业主确认过的根」。**

        这里逐个走一遍 WORKSPACE_READ_TOOLS 里的读面,断言待确认期间它们
        看到的都还是旧根。"""
        ds_tools.set_workspace(self.new, ds_root=self.ds)
        confirmed = os.path.realpath(self.old)
        # 读面一:列文档
        self.assertFalse(ds_documents.list_documents(PROJ_OUT, ds_root=self.ds)["ok"])
        # 读面二:读文档正文
        self.assertFalse(ds_documents.read_document(
            PROJ_OUT, SECRET, ds_root=self.ds)["ok"])
        # 读面三:列项目(扫的是根下的文件夹名)
        cfg = ds_workspace.load_config(self.ds)
        self.assertEqual(cfg["root"], confirmed)
        # project_folders 回的是 [(key, realpath)] 元组序,**不是名字序** ——
        # 直接 assertNotIn(名字, 元组序) 永远通过,那是一条假绿断言(写这份判据
        # 时我第一版就是这么写的,核 API 时抓到)。必须先解包出 key 再断言。
        keys = [k for k, _path in ds_workspace.project_folders(cfg)]
        self.assertIn(PROJ_IN, keys, "旧根的项目该在(证明这条断言真的看得见东西)")
        self.assertNotIn(PROJ_OUT, keys,
                         "未经确认的新根下的项目夹名不许出现在任何读面上")

    def test_o7c_业主点头之后才读得到(self):
        """闸不许把正常使用也挡死:业主同意了就该能读 —— 这也是这道闸的边界
        (它挡不住"业主自己点了同意",只把攻击成本抬到"得骗过眼皮底下一张卡")。"""
        pid = _pending_id(self, self.ds, self.new)
        with _serve(self.ds) as port:
            _post(port, "/api/consent/resolve", {"pending_id": pid, "approve": True})
        listed = ds_documents.list_documents(PROJ_OUT, ds_root=self.ds)
        self.assertTrue(listed.get("ok"))
        self.assertEqual([d["rel"] for d in listed["documents"]], [SECRET])


if __name__ == "__main__":
    unittest.main(verbosity=2)
