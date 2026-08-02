"""MCP 工具表快照的共用件(track opendesign-mcp-registry)。

**主 agent 亲写,执行腿逐字节 off-limits。**

这一单动的是**助手能力的全部来源** —— 三个 MCP server 的 29 个工具。
搞砸的表现不是"某个功能不好用",是**用户下次用的时候助手什么都不会做了**。
所以判据的核心不是"代码没变",是「**助手看到的东西一个字没变**」:
工具的 `name` / 入参 schema / **description(即 docstring)** 全部逐字节比对。

**docstring 尤其不能动**:它是喂给模型的规格。改它 = 改产品行为,不是重构。

## 取快照的两条路(改造前后各一条)

- **改造前**(基线):三个业务模块各自的 `_run_mcp()` 里就地建 server。
  没有对外的构建口子,所以用「把 `FastMCP.run` 换成空操作 + 截获实例」取。
- **改造后**(目标契约,**本文件即规格**):统一入口 `bin/ds_mcp.py` 必须提供
  `build(key) -> FastMCP`,`key ∈ {"tools","organize","refs"}`;
  且 `python bin/ds_mcp.py <key>` 能直接把它跑起来(config 就指这个)。

⇒ 改造前跑本模块的 `snapshot_via_new_entry()` 必然红(`ds_mcp` 还不存在),这是对的。
"""
import asyncio
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(REPO, "bin")
BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "mcp_surface_baseline.json")

# 改造后 config 里的三条命令行,key → server 名。**这三个 server 名不许变**
# (它们是 config 里的键,改了等于要求用户再迁移一次)。
SERVER_KEYS = {
    "tools": "design-studio",
    "organize": "design-studio-organize",
    "refs": "design-studio-refs",
}


def _ensure_env():
    """两个 server 依赖环境变量才建得起来;取快照时给一个确定的值,
    免得快照里混进本机路径(那会让基线不可复现)。"""
    os.environ.setdefault("DS_ROOT", REPO)
    os.environ.setdefault("DS_ORGANIZE_ROOTS", REPO)
    if BIN not in sys.path:
        sys.path.insert(0, BIN)


def _describe(server) -> list[dict]:
    """一个 server 的工具表 → 可比对的普通结构(名序,避免注册顺序造成假红)。"""
    tools = asyncio.run(server.list_tools())
    out = []
    for t in sorted(tools, key=lambda x: x.name):
        out.append({
            "name": t.name,
            # description 就是工具函数的 docstring —— 喂给模型的规格,逐字比对
            "description": t.description or "",
            "inputSchema": t.inputSchema,
        })
    return out


def snapshot_via_legacy() -> dict:
    """**改造前**取基线:`FastMCP.run` 换成空操作,截获三个 `_run_mcp()` 建出的实例。

    不改任何产品代码 —— 基线必须取自**动手之前**的树,否则它只是实现的复印件。
    """
    _ensure_env()
    from mcp.server.fastmcp import FastMCP
    captured = []
    orig_init, orig_run = FastMCP.__init__, FastMCP.run
    try:
        def init(self, *a, **k):
            orig_init(self, *a, **k)
            captured.append(self)
        FastMCP.__init__ = init
        FastMCP.run = lambda self, *a, **k: None
        import ds_tools
        import ds_organize
        import ds_refs
        ds_tools._run_mcp()
        ds_organize._run_mcp()
        ds_refs._run_mcp()
    finally:
        FastMCP.__init__, FastMCP.run = orig_init, orig_run
    return {s.name: _describe(s) for s in captured}


def snapshot_via_new_entry() -> dict:
    """**改造后**取实际值:走统一入口 `ds_mcp.build(key)`。

    `ds_mcp` 不存在 / 没有 `build` → 抛异常,判据红。**这就是目标契约。**
    """
    _ensure_env()
    import ds_mcp
    out = {}
    for key, name in SERVER_KEYS.items():
        srv = ds_mcp.build(key)
        out[name] = _describe(srv)
    return out


def load_baseline() -> dict:
    with open(BASELINE, encoding="utf-8") as fh:
        return json.load(fh)


def dumps(obj) -> str:
    """比对用的稳定序列化(排序 + 不转义中文,diff 出来人能读)。"""
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)
