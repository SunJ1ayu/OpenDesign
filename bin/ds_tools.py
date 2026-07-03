#!/usr/bin/env python3
"""design-studio 工具层 — spec docs/spec.md §4/§5 的实现。

两层:
  1) 纯 Python 核心(下面的 append_change/set_change_status/read_project/list_todos),
     只依赖标准库,可被 tests/ 直接调用做 oracle 验证。
  2) 末尾的 stdio MCP server 包装(需 `pip install mcp`,未装则不影响核心与测试)。

契约铁律(spec §3):
  - 变更行:`- [状态] C<n> YYYY-MM-DD 内容`,状态 ∈ STATUSES。
  - 内容是单行:换行在写入口折叠(ds_common.sanitize_field)——多行 content 等于
    伪造任意账本行,词表/锚定/页脚三条铁律会一起被打穿。
  - 末行:`最后更新: YYYY-MM-DD`,每次写动作更新为今天(行首锚定、最后一处)。
  - 不删变更行(取消用 [已关闭])。

安全(spec §5):realpath allowlist 防路径逃逸 + 排他锁写串行化 + 状态词表校验 + 不删行。
"""
from __future__ import annotations

import os
import re

import ds_common  # 共享:防逃逸谓词/字段消毒/页脚锚定/加锁读改写(同目录模块)
import ds_todo    # 主动提醒核心,同目录模块(list_todos 直调,不走 subprocess)

# ── 契约常量 ────────────────────────────────────────────────────────────────
STATUSES = ("待确认", "进行中", "已完成", "已关闭")
# env DS_ROOT 缺失时基于 __file__ 推导(bin/ 的上一级):Linux/Windows 通用,不硬编码 /root
DEFAULT_DS_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# 变更行:  - [状态] C<n> ...   （前缀空格后 `- [`,ds-todo 也认这个前缀）
_CHANGE_RE = re.compile(r"^- \[(?P<status>[^\]]*)\]\s+C(?P<num>\d+)\b")
_CHANGE_HEADER = "## 变更记录"


# ── 安全:路径 allowlist ────────────────────────────────────────────────────
def _resolve(ds_root: str, subdir: str, name: str) -> tuple[str | None, dict | None]:
    """把 name 解析成 ds_root/subdir/<name>.md 的真实路径,并强制落在允许目录内。

    返回 (path, None) 或 (None, error_dict)。防 `../../etc/passwd` 之类逃逸。
    """
    base = os.path.realpath(os.path.join(ds_root, subdir))
    target = os.path.realpath(os.path.join(base, f"{name}.md"))
    if not ds_common.within(base, target):
        return None, {"error": "path_escape"}
    return target, None


def _max_change_num(lines: list[str]) -> int:
    m = 0
    for ln in lines:
        mo = _CHANGE_RE.match(ln)
        if mo:
            m = max(m, int(mo.group("num")))
    return m


# ── 工具 4.1 append_change ──────────────────────────────────────────────────
def append_change(project: str, content: str, ds_root: str = DEFAULT_DS_ROOT,
                  today: str | None = None) -> dict:
    today = ds_common.today_str(today)
    content = ds_common.sanitize_field(content)  # 折换行:单行契约的物理保证
    if not content:
        return {"error": "empty_content"}
    path, err = _resolve(ds_root, "projects", project)
    if err:
        return err
    if not os.path.exists(path):
        return {"error": "project_not_found"}

    with ds_common.locked_rw(path) as box:
        lines = box["lines"]
        next_num = _max_change_num(lines) + 1
        new_line = f"- [待确认] C{next_num} {today} {content}"

        # 找 ## 变更记录 区,插到该区最后一条变更行之后(无则紧跟标题)
        try:
            hdr = next(i for i, ln in enumerate(lines) if ln.startswith(_CHANGE_HEADER))
        except StopIteration:
            box["write"] = False
            return {"error": "no_change_section"}
        end = next((j for j in range(hdr + 1, len(lines)) if lines[j].startswith("## ")),
                   len(lines))
        last_change = None
        for i in range(hdr + 1, end):
            if _CHANGE_RE.match(lines[i]):
                last_change = i
        insert_at = (last_change + 1) if last_change is not None else hdr + 1
        lines.insert(insert_at, new_line)

        ds_common.bump_last_updated(lines, today)

    return {"ok": True, "change_id": f"C{next_num}", "line": new_line}


# ── 工具 4.2 set_change_status ──────────────────────────────────────────────
def set_change_status(project: str, change_id: str, status: str,
                      ds_root: str = DEFAULT_DS_ROOT, today: str | None = None) -> dict:
    if status not in STATUSES:
        return {"error": "invalid_status"}
    today = ds_common.today_str(today)
    path, err = _resolve(ds_root, "projects", project)
    if err:
        return err
    if not os.path.exists(path):
        return {"error": "project_not_found"}

    m = re.fullmatch(r"C(\d+)", change_id.strip())
    if not m:
        return {"error": "change_not_found"}
    num = m.group(1)
    # 锚定 C<num>\b:`\b` 防 C2 误伤 C12/C20;`\s+` 与 _CHANGE_RE 同容差
    line_re = re.compile(rf"^(- \[)(?P<old>[^\]]*)(\]\s+C{num}\b)")

    with ds_common.locked_rw(path) as box:
        lines = box["lines"]
        hits = [i for i, ln in enumerate(lines) if line_re.match(ln)]
        if len(hits) != 1:
            box["write"] = False
            return {"error": "change_not_found" if not hits else "ambiguous_change"}
        i = hits[0]
        old_status = line_re.match(lines[i]).group("old")
        lines[i] = line_re.sub(rf"\g<1>{status}\g<3>", lines[i], count=1)
        ds_common.bump_last_updated(lines, today)
        result_line = lines[i]

    return {"ok": True, "old_status": old_status, "new_status": status, "line": result_line}


# ── 工具 4.3 read_project ───────────────────────────────────────────────────
def read_project(name: str, ds_root: str = DEFAULT_DS_ROOT) -> dict:
    path, err = _resolve(ds_root, "projects", name)
    if err:
        return err
    if not os.path.exists(path):
        return {"error": "project_not_found"}
    with open(path, encoding="utf-8") as fh:
        return {"ok": True, "content": fh.read()}


# ── 工具 4.4 list_todos ─────────────────────────────────────────────────────
def list_todos(stale_days: int = 7, ds_root: str = DEFAULT_DS_ROOT) -> dict:
    # 直调同目录 ds_todo(不走 subprocess:消灭 Windows 管道编码面,崩溃显式暴露)
    try:
        return {"ok": True, "text": ds_todo.render(ds_root, int(stale_days))}
    except Exception as e:
        return {"error": f"ds_todo_failed: {type(e).__name__}: {e}"}


# ── stdio MCP server 包装(需 `pip install mcp`;未装不影响以上核心) ────────
def _run_mcp() -> None:
    from mcp.server.fastmcp import FastMCP  # 延迟导入:未装时上面的核心与 tests 照常可用

    ds_root = os.environ.get("DS_ROOT", DEFAULT_DS_ROOT)
    server = FastMCP("design-studio")

    @server.tool()
    def append_change_tool(project: str, content: str) -> dict:
        """追加一条业主新提的修改需求(自动编号,标记 [待确认])。"""
        return append_change(project, content, ds_root=ds_root)

    @server.tool()
    def set_change_status_tool(project: str, change_id: str, status: str) -> dict:
        """推进某条变更状态。status 必须是:待确认/进行中/已完成/已关闭。"""
        return set_change_status(project, change_id, status, ds_root=ds_root)

    @server.tool()
    def read_project_tool(name: str) -> dict:
        """读取某个项目的完整记录(业主、阶段、变更、沟通日志)。"""
        return read_project(name, ds_root=ds_root)

    @server.tool()
    def list_todos_tool(stale_days: int = 7) -> dict:
        """列出所有项目的未关闭事项 + 超期未更新项目。"""
        return list_todos(stale_days, ds_root=ds_root)

    server.run()


if __name__ == "__main__":
    _run_mcp()
