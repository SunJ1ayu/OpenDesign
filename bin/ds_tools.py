#!/usr/bin/env python3
"""design-studio 工具层 — spec docs/spec.md §4/§5 的实现。

两层:
  1) 纯 Python 核心(下面的 append_change/set_change_status/read_project/list_todos),
     只依赖标准库,可被 tests/ 直接调用做 oracle 验证。
  2) 末尾的 stdio MCP server 包装(需 `pip install mcp`,未装则不影响核心与测试)。

契约铁律(spec §3):
  - 变更行:`- [状态] C<n> YYYY-MM-DD 【空间】内容`,状态 ∈ STATUSES;【空间】可选
    (1-16字,space 参数写入,值内全角括号剥除防伪造闭合)。
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
import ds_workspace  # PROJECT_NAME_RE 单一真相源(写侧与读侧/web key 闸同一套字符集)

# ── 契约常量 ────────────────────────────────────────────────────────────────
STATUSES = ("待确认", "进行中", "已完成", "已关闭")
# env DS_ROOT 缺失时基于 __file__ 推导(bin/ 的上一级):Linux/Windows 通用,不硬编码 /root
DEFAULT_DS_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# 变更行:  - [状态] C<n> ...   （前缀空格后 `- [`,ds-todo 也认这个前缀）
_CHANGE_RE = re.compile(r"^- \[(?P<status>[^\]]*)\]\s+C(?P<num>\d+)\b")
_CHANGE_HEADER = "## 变更记录"
_HISTORY_HEADER = "## 变更历史"  # edit_change 的留痕/备注独立段(不匹配 _CHANGE_RE ⇒ 不成待办)

# 改正文时"只替尾段、绝不重拼主行"的前缀捕获正则(BLOCK-2):group(1)=状态/C号/日期/
# 【空间】前缀(逐字节保留),group(2)=正文尾段。
# 状态类用 `[^\]]*`(非 4 词集):line_re 定位的是任意 `- [x] C{n}` 主行,若这里钉死 4 词集,
# 对非标准状态的手改行(只改正文、不带 new_status 时)会 match=None → 崩(main-agent finding A)。
# 空间子模式**镜像 parse_change** 的 `【[^【】\s][^【】]{0,15}】`:更松会把畸形 `【 】` 当前缀吞掉,
# 与读侧拆分漂移(finding B)。两处对齐 ⇒ old_text 与读侧/前端逐字节一致。
_EDIT_PREFIX_RE = re.compile(
    r"^(- \[[^\]]*\]"
    r"(?:\s+C\d+\b)?(?:\s+\d{4}-\d{2}-\d{2})?\s*"
    r"(?:【[^【】\s][^【】]{0,15}】\s*)?)(?P<text>.*)$")

# `## 变更历史` 段两类行的读侧正则(与 edit_change 的写侧格式同处定义,防漂移):
#   留痕:  - C{n} 改于 {date}｜原:{旧正文}
#   备注:  - C{n} 备注:{内容}
_HISTORY_EDIT_RE = re.compile(r"^- C(\d+) 改于 (\d{4}-\d{2}-\d{2})｜原:(.*)$")
_HISTORY_NOTE_RE = re.compile(r"^- C(\d+) 备注[:：](.*)$")

# 新建骨架模板 —— 必须含 `## 变更记录` 头(append_change 靠它定位)与 `最后更新:` 页脚
# (ds_todo 靠它判超期),否则新项目建出来后 append/提醒都接不上(这正是首用暴露的洞)。
_PROJECT_TEMPLATE = """# {slug}

- 业主: [[{client}]]
- 阶段: {stage}
- 地址/户型: {address}
- 开始日期: {today}
- 当前状态: 新建,待完善

## 变更记录

## 沟通日志

---
最后更新: {today}
"""
_CLIENT_TEMPLATE = """# {name}

- 联系方式: {contact}
- 关联项目: {linked}
- 预算区间:
- 风格偏好:
- 关键约束:
- 决策习惯:

## 备注
"""


# ── 安全:路径 allowlist ────────────────────────────────────────────────────
def _resolve(ds_root: str, subdir: str, name: str) -> tuple[str | None, dict | None]:
    """把 name 解析成 ds_root/subdir/<name>.md 的真实路径,并强制落在允许目录内。

    返回 (path, None) 或 (None, error_dict)。防 `../../etc/passwd` 之类逃逸。
    """
    base = os.path.realpath(os.path.join(ds_root, subdir))
    target = os.path.realpath(os.path.join(base, f"{name}.md"))
    if not ds_common.within(base, target):
        return None, {"error": "path_escape"}
    # H1(07-13 盲评):字符集闸,PROJECT_NAME_RE 单一真相源。`小区/1801` 这类名字
    # within 过得了(落成嵌套 .md),但读侧(一级 listdir/collect/web key 闸)永远
    # 看不见=写成功即丢活。写读共用本咽喉,拒之;顺序在 within 之后,path_escape 契约不变。
    if not ds_workspace.PROJECT_NAME_RE.match(name or ""):
        return None, {"error": "bad_name"}
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
                  today: str | None = None, space: str = "") -> dict:
    today = ds_common.today_str(today)
    content = ds_common.sanitize_field(content)  # 折换行:单行契约的物理保证
    if not content:
        return {"error": "empty_content"}
    # 空间(可选):消毒后再剥全角括号(防伪造闭合注入结构)、截 16 字;空串视同不带,
    # 此时行格式与 0.4.0 逐字节相同(向后兼容,oracle test_20 锁定)
    space = ds_common.sanitize_field(space).replace("【", "").replace("】", "")[:16]
    path, err = _resolve(ds_root, "projects", project)
    if err:
        return err
    if not os.path.exists(path):
        return {"error": "project_not_found"}

    with ds_common.locked_rw(path) as box:
        lines = box["lines"]
        next_num = _max_change_num(lines) + 1
        prefix = f"【{space}】" if space else ""
        new_line = f"- [待确认] C{next_num} {today} {prefix}{content}"

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


# ── 工具 4.2b edit_change ────────────────────────────────────────────────────
def _history_bounds(lines: list[str]) -> tuple[int, int] | None:
    """`## 变更历史` 段的 (标题行下标, 段尾下标)。段尾=其后第一条 `## `/`---` 或文件末。
    段缺失返回 None。"""
    hidx = next((i for i, l in enumerate(lines) if l.startswith(_HISTORY_HEADER)), None)
    if hidx is None:
        return None
    end = next((j for j in range(hidx + 1, len(lines))
                if lines[j].startswith("## ") or lines[j].startswith("---")), len(lines))
    return hidx, end


def parse_history(text: str) -> dict:
    """解析 `## 变更历史` 段,按 cnum 分桶(读侧单一真相源:ds_web changes 端点吃它)。

    返回 {cnum(int): {"note": str|None, "history": [{"date","old"}, …]}}。只扫历史段内的行
    (遇下一 `## `/`---` 即止 ⇒ 隔离天然);段缺失或无匹配行返回空/缺桶。留痕按出现顺序(=时序)。
    """
    lines = text.split("\n")
    b = _history_bounds(lines)
    if b is None:
        return {}
    hidx, end = b
    out: dict[int, dict] = {}
    for ln in lines[hidx + 1:end]:
        m = _HISTORY_EDIT_RE.match(ln)
        if m:
            bucket = out.setdefault(int(m.group(1)), {"note": None, "history": []})
            bucket["history"].append({"date": m.group(2), "old": m.group(3)})
            continue
        m = _HISTORY_NOTE_RE.match(ln)
        if m:
            bucket = out.setdefault(int(m.group(1)), {"note": None, "history": []})
            bucket["note"] = m.group(2)
    return out


def _create_history_section(lines: list[str], entries: list[str]) -> None:
    """建 `## 变更历史` 段并写入 entries,置于 `## 变更记录` 段之后(其后第一条 `## `/`---` 前)。
    保证 append_change 的段边界(遇下一个 `## ` 即止)不被破坏。"""
    hdr = next((i for i, l in enumerate(lines) if l.startswith(_CHANGE_HEADER)), None)
    if hdr is None:  # 无变更记录段的畸形文件:退到页脚/末尾前
        pos = next((j for j in range(len(lines)) if lines[j].startswith("---")), len(lines))
    else:
        pos = next((j for j in range(hdr + 1, len(lines))
                    if lines[j].startswith("## ") or lines[j].startswith("---")), len(lines))
    block = [_HISTORY_HEADER] + entries + [""]
    if pos > 0 and lines[pos - 1].strip():  # 与上一段之间补一空行(源文件无空行时)
        block = [""] + block
    lines[pos:pos] = block


def _append_history_entry(lines: list[str], entry: str) -> None:
    """向 `## 变更历史` 段末追加一行(段缺则先建)。"""
    b = _history_bounds(lines)
    if b is None:
        _create_history_section(lines, [entry])
        return
    hidx, end = b
    last = hidx
    for k in range(hidx + 1, end):
        if lines[k].strip():
            last = k
    lines.insert(last + 1, entry)


def _upsert_note(lines: list[str], num: str, note_line: str) -> None:
    """按 cnum 键在 `## 变更历史` 段内追加/替换该变更的备注行(BLOCK-3:非位置扫描)。"""
    note_re = re.compile(rf"^- C{num} 备注[:：]")
    b = _history_bounds(lines)
    if b is None:
        _create_history_section(lines, [note_line])
        return
    hidx, end = b
    last = hidx
    for k in range(hidx + 1, end):
        if note_re.match(lines[k]):
            lines[k] = note_line
            return
        if lines[k].strip():
            last = k
    lines.insert(last + 1, note_line)


def edit_change(project: str, cnum, new_status: str | None = None,
                new_text: str | None = None, note: str | None = None,
                ds_root: str = DEFAULT_DS_ROOT, today: str | None = None) -> dict:
    """行内编辑一条变更:改状态 / 改正文(保前缀字节 + 向 `## 变更历史` 段留痕) / 加改备注。

    只读铁律的受控写口。定位复用 set_change_status 口径(CHANGE_RE 命中且 cnum 相等);
    改正文用前缀捕获正则只替尾段(状态/C号/日期/【空间】逐字节不变,BLOCK-2)。全程 locked_rw。
    """
    today = ds_common.today_str(today)
    # cnum 容差:接受 3 / "3" / "C3"
    mo = re.fullmatch(r"C?(\d+)", str(cnum).strip())
    if not mo:
        return {"error": "change_not_found"}
    num = mo.group(1)

    if new_status is not None and new_status not in STATUSES:
        return {"error": "invalid_status"}
    new_text_s = None
    if new_text is not None:
        new_text_s = ds_common.sanitize_field(new_text)  # 折换行,不 ban 竖线(同 append_change)
        if not new_text_s:
            return {"error": "empty_text"}
    note_s = ds_common.sanitize_field(note) if note is not None else None

    path, err = _resolve(ds_root, "projects", project)
    if err:
        return err
    if not os.path.exists(path):
        return {"error": "project_not_found"}

    # 定位主变更行(与 set_change_status 同锚:C<num>\b 防 C2 误伤 C12/C20)
    line_re = re.compile(rf"^(- \[)(?P<old>[^\]]*)(\]\s+C{num}\b)")

    with ds_common.locked_rw(path) as box:
        lines = box["lines"]
        hits = [i for i, ln in enumerate(lines) if line_re.match(ln)]
        if len(hits) != 1:
            box["write"] = False
            return {"error": "change_not_found" if not hits else "ambiguous_change"}
        i = hits[0]
        changed = False

        if new_status is not None:
            lines[i] = line_re.sub(rf"\g<1>{new_status}\g<3>", lines[i], count=1)
            changed = True

        if new_text_s is not None:
            pm = _EDIT_PREFIX_RE.match(lines[i])
            old_text = pm.group("text")
            if new_text_s != old_text:  # no-op(==旧)不留痕,避免 `原:X`==新值噪声
                lines[i] = pm.group(1) + new_text_s
                _append_history_entry(lines, f"- C{num} 改于 {today}｜原:{old_text}")
                changed = True

        if note_s:  # 空备注视同不带(不写 `- Cn 备注:` 空行)
            _upsert_note(lines, num, f"- C{num} 备注:{note_s}")
            changed = True

        if changed:
            ds_common.bump_last_updated(lines, today)
            result_line = lines[i]
        else:
            box["write"] = False  # 纯 no-op:文件逐字节不动
            result_line = lines[i]

    return {"ok": True, "cnum": int(num), "line": result_line}


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


# ── 工具 4.5 create_client ──────────────────────────────────────────────────
def create_client(name: str, contact: str = "", linked: str = "",
                   ds_root: str = DEFAULT_DS_ROOT) -> dict:
    """新建业主档案 clients/<name>.md(按 SCHEMA 骨架)。已存在则拒绝覆盖。"""
    name = ds_common.sanitize_field(name)      # 折换行:防伪造账本/索引行(承 7-03 盲评铁律)
    if not name:
        return {"error": "empty_name"}
    contact = ds_common.sanitize_field(contact)
    linked = ds_common.sanitize_field(linked)
    path, err = _resolve(ds_root, "clients", name)   # realpath allowlist 防路径逃逸
    if err:
        return err
    if os.path.exists(path):
        return {"error": "client_exists"}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    body = _CLIENT_TEMPLATE.format(
        name=name, contact=contact, linked=(f"[[{linked}]]" if linked else ""))
    with open(path, "x", encoding="utf-8") as fh:   # "x":原子创建,已存在即抛(不覆盖)
        fh.write(body)
    return {"ok": True, "client": name}


# ── 工具 4.6 create_project ─────────────────────────────────────────────────
def create_project(project: str, client: str, stage: str = "洽谈", address: str = "",
                   ds_root: str = DEFAULT_DS_ROOT, today: str | None = None) -> dict:
    """新建项目 projects/<project>.md(按 SCHEMA 骨架,含变更记录头+页脚)。已存在则拒绝
    覆盖;业主档案缺失时自动补一个最小 stub,避免悬空 [[链接]]。之后 append_change 可直接接上。
    """
    today = ds_common.today_str(today)
    project = ds_common.sanitize_field(project)   # 同时作文件名与标题:消毒后一致
    client = ds_common.sanitize_field(client)
    stage = ds_common.sanitize_field(stage)
    address = ds_common.sanitize_field(address)
    if not project or not client:
        return {"error": "empty_name"}
    path, err = _resolve(ds_root, "projects", project)
    if err:
        return err
    if os.path.exists(path):
        return {"error": "project_exists"}
    # 业主档案不存在则先补最小 stub(用消毒后的 client 名;逃逸/已存在都安全跳过)
    cpath, cerr = _resolve(ds_root, "clients", client)
    if not cerr and not os.path.exists(cpath):
        create_client(client, linked=project, ds_root=ds_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    body = _PROJECT_TEMPLATE.format(
        slug=project, client=client, stage=stage, address=address, today=today)
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(body)
    return {"ok": True, "project": project, "client": client, "stage": stage}


# ── stdio MCP server 包装(需 `pip install mcp`;未装不影响以上核心) ────────
def _run_mcp() -> None:
    from mcp.server.fastmcp import FastMCP  # 延迟导入:未装时上面的核心与 tests 照常可用

    ds_root = os.environ.get("DS_ROOT", DEFAULT_DS_ROOT)
    server = FastMCP("design-studio")

    @server.tool()
    def create_client_tool(name: str, contact: str = "", linked: str = "") -> dict:
        """新建业主档案。name=业主称呼;contact=联系方式(可选);linked=关联项目slug(可选)。"""
        return create_client(name, contact=contact, linked=linked, ds_root=ds_root)

    @server.tool()
    def create_project_tool(project: str, client: str, stage: str = "洽谈",
                            address: str = "") -> dict:
        """新建项目(业主不存在会自动补档)。记录任何变更/待办前,项目必须先经此工具建好。
        project=项目slug;client=业主称呼;stage=阶段(默认洽谈);address=地址/户型(可选)。"""
        return create_project(project, client, stage=stage, address=address, ds_root=ds_root)

    @server.tool()
    def append_change_tool(project: str, content: str, space: str = "") -> dict:
        """追加一条业主新提的修改需求(自动编号,标记 [待确认])。项目须已存在(见 create_project)。
        space=所属空间(可选但尽量带,如 玄关/客厅/主卧/厨房/卫生间/阳台;听得出就填)。"""
        return append_change(project, content, ds_root=ds_root, space=space)

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
