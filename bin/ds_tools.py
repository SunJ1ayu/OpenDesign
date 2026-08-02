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

import json
import os
import re
import shutil
import stat
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import date

import ds_common  # 共享:防逃逸谓词/字段消毒/页脚锚定/加锁读改写(同目录模块)
import ds_lock    # 跨平台跨进程排他锁(workspace.json 的稳定旁路锁)
import ds_todo    # 主动提醒核心,同目录模块(list_todos 直调,不走 subprocess)
import ds_workspace  # PROJECT_NAME_RE 单一真相源(写侧与读侧/web key 闸同一套字符集)

# ── 契约常量 ────────────────────────────────────────────────────────────────
STATUSES = ("待确认", "进行中", "已完成", "已关闭")
# 业主档案可写字段白名单(update_client,替换语义)。`关联项目` 刻意不在:机器管理
# 字段(create_project 写入/rename_project 五处联动/delete_project 清点),开放给
# LLM 自由改写会打断改名/删除的记账。`备注` 走追加语义,单列。
CLIENT_FIELDS = ("联系方式", "预算区间", "风格偏好", "关键约束", "决策习惯")
_NOTE_FIELD = "备注"
_NOTE_HEADER = "## 备注"
# 全生命周期阶段词表(set_stage 闸;AGENTS.md「阶段词表」段与此一致,代码为真相源)。
# 不强制顺序:现实会跳/回退(返工回效果图、跳过软装),顺序校验=假保护。
PROJECT_STAGES = ("洽谈", "量房", "平面方案", "方案深化", "效果图", "施工图",
                  "施工交底", "施工跟进", "软装", "竣工验收", "售后")
# env DS_ROOT 缺失时基于 __file__ 推导(bin/ 的上一级):Linux/Windows 通用,不硬编码 /root
DEFAULT_DS_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# 变更行:  - [状态] C<n> ...   （前缀空格后 `- [`,ds-todo 也认这个前缀）
_CHANGE_RE = re.compile(r"^- \[(?P<status>[^\]]*)\]\s+C(?P<num>\d+)\b")
_CHANGE_HEADER = "## 变更记录"
_HISTORY_HEADER = "## 变更历史"  # edit_change 的留痕/备注独立段(不匹配 _CHANGE_RE ⇒ 不成待办)
_STAGE_HISTORY_HEADER = "## 阶段历史"
_BATCH_HEADER = "## 批次"       # T4b:一次记录动作的名字(同样不匹配 _CHANGE_RE ⇒ 不成待办)
# 批次行正则:单一真相源在 ds_common,读写共用(不设第二份,见那里的注释)。
_BATCH_RE = ds_common.BATCH_LINE_RE
_BATCH_TITLE_MAX = 24

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
_STAGE_HISTORY_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2}) (.+)$")

# 新建骨架模板 —— 必须含 `## 变更记录` 头(append_change 靠它定位)与 `最后更新:` 页脚
# (ds_todo 靠它判超期),否则新项目建出来后 append/提醒都接不上(这正是首用暴露的洞)。
#
# 2026-07-28 删掉了 `- 当前状态: 新建,待完善` 这一行。**教训值得留在这儿**:
# 它是本模板里唯一一个**没有任何写口**的字段(阶段有 set_stage、客户字段有 update_client、
# 变更/待办/沟通各有写口),建档填一次之后永不改变,却被伴随列拿去当"项目速览"显示
# —— 用户看到的永远是「新建,待完善」。**模板的默认值把"没人维护"伪装成了"有内容"**,
# 这正是它能活这么久的原因。
# ⇒ **往模板加字段前先问:谁写它?没有写口就别加默认值,宁可留空让它当场暴露。**
# (`地址/户型` 也没有更新写口,但它是建档参数、且从不上界面 —— 风险等级不同,暂留。)
_PROJECT_TEMPLATE = """# {slug}

- 业主: {client}
- 阶段: {stage}
- 地址/户型: {address}
- 开始日期: {today}

## 阶段历史

- {today} {stage}

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


def _clean_batch_title(title: str) -> str:
    """批次标题消毒:折单行(sanitize_field 只做这个,不剥前缀 —— 别指望它代劳)→
    剥【】(防伪造空间前缀)→ 剥行首的 - / [ / # / >(防伪造成变更行或段头)→ 截 24。
    标题写在行尾,行首恒为 `- C{n}-C{m} `,所以这层剥离是纵深防御不是唯一防线。"""
    t = ds_common.sanitize_field(title).replace("【", "").replace("】", "")
    t = re.sub(r"^[-\[\]#>\s]+", "", t)
    return t[:_BATCH_TITLE_MAX].strip()


def _upsert_batch_line(lines: list[str], cnum: int, title: str, today: str) -> None:
    """把 cnum 归进 `## 批次` 段。段末那行**标题相同且区间末尾+1 == cnum** → 末尾延一格;
    否则新起一行。段缺失则补建到页脚 `---` 之前(与 log_communication 同策略)——
    **绝不插进 `## 变更记录` 中间**:append_change 找插入点以下一个 `## ` 为界,
    插错位置会让后续变更掉进批次段(oracle test_b11 钉这条)。"""
    hdr = next((i for i, ln in enumerate(lines) if ln.startswith(_BATCH_HEADER)), None)
    if hdr is None:
        foot = next((i for i in range(len(lines) - 1, -1, -1)
                     if lines[i].startswith("---")), len(lines))
        lines[foot:foot] = [_BATCH_HEADER, f"- C{cnum}-C{cnum} {today} {title}", ""]
        return
    end = next((j for j in range(hdr + 1, len(lines))
                if lines[j].startswith("## ") or lines[j].startswith("---")), len(lines))
    last = None
    for i in range(hdr + 1, end):
        if _BATCH_RE.match(lines[i]):
            last = i
    if last is not None:
        m = _BATCH_RE.match(lines[last])
        # 三条件全中才延段:同标题 + 号相连 + **同一天**。
        # 「一批 = 一次记录动作」,换了一天就是另一次记录动作 —— 少了日期这条,
        # 昨天那批会被延到今天,而批次行日期停在昨天,前端按(日期,批次)分组时
        # 同一个 id 会裂成两组、顶着同一个名字(四审 subdeepseek 挑出,根因在规格)。
        if (m.group("title") == title and int(m.group("to")) + 1 == cnum
                and m.group("date") == today):
            lines[last] = f"- C{m.group('from')}-C{cnum} {today} {title}"
            return
    insert_at = (last + 1) if last is not None else hdr + 1
    lines.insert(insert_at, f"- C{cnum}-C{cnum} {today} {title}")


# ── 工具 4.1 append_change ──────────────────────────────────────────────────
def append_change(project: str, content: str, ds_root: str = DEFAULT_DS_ROOT,
                  today: str | None = None, space: str = "",
                  batch_title: str = "") -> dict:
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

        # T4b:带标题才动批次段。空标题(或消毒后空)= 一行都不写,前端走兜底。
        clean_title = _clean_batch_title(batch_title)
        if clean_title:
            _upsert_batch_line(lines, next_num, clean_title, today)

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


# ── 工具 4.1b set_due_date(track opendesign-todo-duedate)────────────────────
def set_due_date(project: str, cnum, due: str | None,
                 ds_root: str = DEFAULT_DS_ROOT, today: str | None = None) -> dict:
    """设/清一条变更的截止日(行尾 ⏳YYYY-MM-DD token)。定位镜像 set_change_status
    (line_re `C{num}\\b` 命中且唯一)。due=None/"" 视为清除;否则须 YYYY-MM-DD 且
    date.fromisoformat 合法,非法 → invalid_due。只动尾 token,其余字节不变(用
    ds_common.DUE_SUFFIX_RE.sub 剥旧尾 + format_due_suffix 补新尾)。no-op(due 与
    现值相同)不写。"""
    if due:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due):
            return {"error": "invalid_due"}
        try:
            date.fromisoformat(due)
        except ValueError:
            return {"error": "invalid_due"}
    else:
        due = None  # "" 与 None 同义:清除

    today = ds_common.today_str(today)
    path, err = _resolve(ds_root, "projects", project)
    if err:
        return err
    if not os.path.exists(path):
        return {"error": "project_not_found"}

    mo = re.fullmatch(r"C?(\d+)", str(cnum).strip())
    if not mo:
        return {"error": "change_not_found"}
    num = mo.group(1)
    # 锚定 C<num>\b:与 set_change_status 同口径
    line_re = re.compile(rf"^(- \[)(?P<old>[^\]]*)(\]\s+C{num}\b)")

    with ds_common.locked_rw(path) as box:
        lines = box["lines"]
        hits = [i for i, ln in enumerate(lines) if line_re.match(ln)]
        if len(hits) != 1:
            box["write"] = False
            return {"error": "change_not_found" if not hits else "ambiguous_change"}
        i = hits[0]
        _, cur_due = ds_common.split_due(lines[i])
        if cur_due == due:
            box["write"] = False  # no-op:文件逐字节不动
            result_line = lines[i]
        else:
            base = ds_common.DUE_SUFFIX_RE.sub("", lines[i]).rstrip()
            lines[i] = base + ds_common.format_due_suffix(due)
            ds_common.bump_last_updated(lines, today)
            result_line = lines[i]

    return {"ok": True, "cnum": int(num), "due": due, "line": result_line}


# ── 工具 4.2b edit_change ────────────────────────────────────────────────────
def _section_bounds(lines: list[str], header: str) -> tuple[int, int] | None:
    """指定二级段的 (标题行下标, 段尾下标)。段尾=其后第一条 `## `/`---` 或文件末。
    段缺失返回 None。"""
    hidx = next((i for i, l in enumerate(lines) if l.startswith(header)), None)
    if hidx is None:
        return None
    end = next((j for j in range(hidx + 1, len(lines))
                if lines[j].startswith("## ") or lines[j].startswith("---")), len(lines))
    return hidx, end


def _history_bounds(lines: list[str]) -> tuple[int, int] | None:
    return _section_bounds(lines, _HISTORY_HEADER)


def _valid_stage_history_line(ln: str) -> dict | None:
    m = _STAGE_HISTORY_RE.match(ln)
    if not m:
        return None
    d, stage = m.group(1), m.group(2)
    try:
        date.fromisoformat(d)
    except ValueError:
        return None
    if stage not in PROJECT_STAGES:
        return None
    return {"date": d, "stage": stage}


def _stage_history_entries_with_lines(lines: list[str]) -> list[dict]:
    b = _section_bounds(lines, _STAGE_HISTORY_HEADER)
    if b is None:
        return []
    hidx, end = b
    out = []
    for i in range(hidx + 1, end):
        e = _valid_stage_history_line(lines[i])
        if e is not None:
            out.append({**e, "line_index": i})
    return out


def parse_stage_history(text: str) -> list[dict]:
    """解析 `## 阶段历史` 段。坏行/词表外阶段跳过,不拖垮整段。"""
    return [
        {"date": e["date"], "stage": e["stage"]}
        for e in _stage_history_entries_with_lines(text.split("\n"))
    ]


def stage_timer(text: str, today: str | None = None) -> dict:
    """当前阶段起始日与已停留天数。算不准时返回 None,不拿其它日期顶替。"""
    lines = text.split("\n")
    entries = parse_stage_history(text)
    if not entries:
        return {"since": None, "days": None}
    last = entries[-1]
    if last["stage"] != _read_header_field(lines, "阶段"):
        return {"since": None, "days": None}
    today_s = ds_common.today_str(today)
    try:
        days = (date.fromisoformat(today_s) - date.fromisoformat(last["date"])).days
    except ValueError:
        return {"since": None, "days": None}
    return {"since": last["date"], "days": days}


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
            old_full = pm.group("text")
            old_text, due = ds_common.split_due(old_full)  # 截止日不参与比较/留痕
            if new_text_s != old_text:  # no-op(==旧)不留痕,避免 `原:X`==新值噪声
                lines[i] = pm.group(1) + new_text_s + ds_common.format_due_suffix(due)
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


# ── 工具 4.2c log_communication(owner-feedback track)──────────────────────────
_COMM_HEADER = "## 沟通日志"


def log_communication(project: str, text: str, source: str = "",
                      ds_root: str = DEFAULT_DS_ROOT, today: str | None = None) -> dict:
    """业主原话存入「沟通日志」段:多行**逐字保真**(与 sanitize_field 的单行契约相反
    ——原文保真是本工具的存在理由),每行加 `  > ` 引用前缀,让 `^-`(CHANGE_RE)/
    `^## `(段界)/`^最后更新`(footer 锚)全部失锚,结构注入面焊死。
    段缺失自动补建到页脚 `---` 前(旧手写档案兼容)。"""
    today = ds_common.today_str(today)
    # 剥括号(防伪造闭合污染头行格式,同 append_change 剥【】先例)+ 截 16
    source = (ds_common.sanitize_field(source)
              .replace("(", "").replace(")", "")
              .replace("（", "").replace("）", ""))[:16]
    text = re.sub(r"\r\n?", "\n", text or "").strip()
    if not text:
        return {"error": "empty_text"}
    path, err = _resolve(ds_root, "projects", project)
    if err:
        return err
    if not os.path.exists(path):
        return {"error": "project_not_found"}

    head = f"- {today} 业主原文({source}):" if source else f"- {today} 业主原文:"
    entry = [head] + [("  > " + ln).rstrip() for ln in text.split("\n")]

    with ds_common.locked_rw(path) as box:
        lines = box["lines"]
        hdr = next((i for i, ln in enumerate(lines) if ln.startswith(_COMM_HEADER)), None)
        if hdr is None:
            # 补建:插到页脚分隔线前(从尾找,引用行 `  > ---` 不会误锚);无页脚则文件末
            foot = next((i for i in range(len(lines) - 1, -1, -1)
                         if lines[i].startswith("---")), len(lines))
            lines[foot:foot] = [_COMM_HEADER, *entry, ""]
        else:
            # 段界 = 下一 `^## ` 或页脚 `^---`;插到段内最后一条非空行之后
            end = next((j for j in range(hdr + 1, len(lines))
                        if lines[j].startswith("## ") or lines[j].startswith("---")),
                       len(lines))
            insert_at = hdr + 1
            for i in range(hdr + 1, end):
                if lines[i].strip():
                    insert_at = i + 1
            lines[insert_at:insert_at] = entry
        ds_common.bump_last_updated(lines, today)

    return {"ok": True, "project": project, "date": today, "lines": len(entry)}


# ── 工具 4.3 read_project ───────────────────────────────────────────────────
def read_project(name: str, ds_root: str = DEFAULT_DS_ROOT,
                 today: str | None = None) -> dict:
    path, err = _resolve(ds_root, "projects", name)
    if err:
        return err
    if not os.path.exists(path):
        return {"error": "project_not_found"}
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    timer = stage_timer(text, today=today)
    return {"ok": True, "content": text,
            "stage_since": timer["since"], "stage_days": timer["days"]}


# ── 工具 4.3b list_projects ─────────────────────────────────────────────────
# 聊天大脑的项目枚举(index.md 的真实替身:index.md 靠人手挂行、内置文件工具已禁用=
# 架构上无人维护,故废弃;此工具现读 projects/ 一级,永远真)。只读、不改盘。
# 头部字段解析复用 _read_header_field(与写侧 upsert 同源),页脚日期复用
# ds_common.LASTUPD_DATE_RE(与 ds_todo 同源),不自造第二份解析。
_LINK_RE = re.compile(r"^\[\[(.+?)\]\]$")


def list_projects(ds_root: str = DEFAULT_DS_ROOT, today: str | None = None) -> dict:
    """枚举所有项目:project/client/stage/last_updated,按项目名排序。
    坏编码文件进 errors(不拖垮整表,M1 先例);目录缺失/空 → 空表。"""
    proj_dir = os.path.join(ds_root, "projects")
    files = sorted(f for f in (os.listdir(proj_dir) if os.path.isdir(proj_dir) else [])
                   if f.endswith(".md"))
    projects = []
    errors = []
    for fn in files:
        slug = fn[:-3]
        try:
            with open(os.path.join(proj_dir, fn), encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            errors.append(slug)  # 一个坏文件不该让整表灭(list_todos.collect 同哲学)
            continue
        lines = text.split("\n")
        raw_client = _read_header_field(lines, "业主")
        m = _LINK_RE.match(raw_client)
        client = m.group(1) if m else raw_client        # `[[张三]]` → 张三;裸值原样
        stage = _read_header_field(lines, "阶段")
        dates = ds_common.LASTUPD_DATE_RE.findall(text)  # 行首锚定、取最后一处(页脚)
        timer = stage_timer(text, today=today)
        projects.append({
            "project": slug, "client": client, "stage": stage,
            "last_updated": dates[-1] if dates else "",
            "stage_since": timer["since"], "stage_days": timer["days"],
        })
    projects.sort(key=lambda p: p["project"])
    return {"ok": True, "projects": projects, "errors": errors}


# ── 工具 4.4 list_todos ─────────────────────────────────────────────────────
# 未接入工作区的主动提醒(Track B/B2)。agent 开场必跑 list_todos(AGENTS.md 规则3),
# 故把"没接入项目文件夹"信号免费搭车塞进这里——不靠弱模型记得另调工具。
# 落点在此而非 ds_todo.render():render() 被 test_ds_todo.py golden 逐字节锁死,插行会全红;
# 它是"纯格式化壳",接入状态属工具层职责。仅 prepend 一行,render 文本与其 golden 全不动。
_NO_WORKSPACE_HINT = (
    "⚠️ 还没接入项目文件夹。告诉我它们放在哪(例如 D:\\设计工作区),我帮你接上,"
    "以后工作台能直接看文件和参考图。\n\n"
)


def list_todos(stale_days: int = 7, ds_root: str = DEFAULT_DS_ROOT) -> dict:
    # 直调同目录 ds_todo(不走 subprocess:消灭 Windows 管道编码面,崩溃显式暴露)
    try:
        text = ds_todo.render(ds_root, int(stale_days))
    except Exception as e:
        return {"error": f"ds_todo_failed: {type(e).__name__}: {e}"}
    # 每请求现读 workspace.json(零缓存):load_config 为 None = 未接入/坏配置,提醒前置
    if ds_workspace.load_config(ds_root) is None:
        text = _NO_WORKSPACE_HINT + text
    return {"ok": True, "text": text}


# 重入闸用的 thread-local(见 locked_workspace_json):记本线程已持有哪几份配置的锁。
_ws_lock_held = threading.local()


def _replace_with_retry(src: str, dst: str, attempts: int = 20,
                        pause: float = 0.02) -> None:
    """`os.replace` 的 Windows 加固:目标被别人打开着时重试若干次再放弃。

    **2026-07-27 用户 Windows 真机实测抓到的**(判据 t06,Linux 上永远绿):
    POSIX 上 rename 覆盖一个"正被读的文件"完全合法;**Windows 上直接
    `PermissionError(13, '拒绝访问。')`** —— 只要有任何人把 workspace.json
    打开着(哪怕只是 `load_config` 那零点几毫秒),写者的原子替换就当场炸。
    真机是 MCP server + ds-web 两进程、ds-web 自己还是多线程,撞上不是小概率。
    用户看到的现象=**保存莫名其妙失败**,而锁一点忙都帮不上:读者根本不拿锁。

    为什么不是"让读者也拿锁":读遍布全仓(每次 `load_config` 都是一次读),
    全部上锁既贵又会把 Windows 那条「重试约 10 次后抛 OSError」的争用面放大。
    重试是标准解:读者的打开窗口是毫秒级,20 次 × 20ms ≈ 0.4s 足够跨过去。

    最后一次仍失败就照抛 —— 不吞异常,写失败必须让调用方知道。
    """
    for i in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(pause)


def _write_workspace_json(cfg_path: str, obj: dict) -> None:
    """workspace.json 原子写(同目录唯一 tmp + os.replace,读者看不到半文件)。

    tmp 不能写死成 workspace.json.tmp:即使调用方漏锁,两个写者也不该互相
    replace 掉对方的临时文件。finally 清理失败路径,正常写完不留 .tmp 残骸。
    """
    # 权限位:NamedTemporaryFile 建的临时文件是 0600,os.replace 之后会整个
    # 继承过去 —— 于是每写一次就把用户的配置**悄悄收紧**一次(四审 subdeepseek
    # BLOCK-1 / subkimi L2,实测 0644→0600)。写文件不该顺手改它的权限:
    # 文件已存在就原样保留它的位,新建才用 0644(= 老实现 open(w) 在默认 umask
    # 下的结果)。判据 t12。
    try:
        mode = stat.S_IMODE(os.stat(cfg_path).st_mode)
    except OSError:
        mode = 0o644
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=os.path.dirname(cfg_path),
                prefix=".workspace.json.", suffix=".tmp", delete=False) as fh:
            tmp = fh.name
            json.dump(obj, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.chmod(tmp, mode)
        _replace_with_retry(tmp, cfg_path)
        tmp = None
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass


@contextmanager
def locked_workspace_json(ds_root: str):
    """锁住 workspace.json 的整段读改写;yield {"raw": dict|None, "write": bool}。

    锁落在 config/ 下的稳定旁路文件,不能锁 workspace.json 本体:后者被
    os.replace 后锁仍挂在旧 inode,下一个写者会绕过互斥。目标 JSON 仍用原子
    替换,所以不持锁的只读侧也只会看到替换前或替换后的完整文件。

    **不可重入,且是故意的。** 嵌套进入同一个 ds_root 会当场抛 RuntimeError,
    不会挂起。别把它改成可重入 —— 那会让「锁内再调另一个写口」这种真正危险的
    写法悄悄合法化(锁内调 set_workspace/bind_project 之类,等于把两次独立的
    读改写焊成一次,语义是错的)。**锁内不许调用任何其他 workspace.json 写口。**

    **平台差异(真机是 Windows,这条要当心)**:Linux 的 fcntl.flock 是无限阻塞
    排队;Windows 的 msvcrt.locking 每秒重试、约 10 次后**抛 OSError**(见
    ds_lock 模块头)。也就是说长争用在两个平台上的失败形态不一样 ——
    Linux 是慢,Windows 是炸。而 bind_project 在锁内要扫整棵项目树,
    工作区放在慢速外接盘/网络盘时持锁时间可能不短。
    """
    config_dir = os.path.join(ds_root, "config")
    os.makedirs(config_dir, exist_ok=True)
    cfg_path = os.path.join(config_dir, "workspace.json")
    lock_path = os.path.join(config_dir, "workspace.json.lock")
    # 重入闸(四审 subdeepseek W1 + subkimi M1 两腿独立命中):flock 按 open file
    # description 计,同线程嵌套 = 第二个 fd 永久阻塞,实测 timeout 直接 124
    # —— 无超时、无报错、无从恢复,真机表现是 ds-web 那条线程整个挂死。
    # 编程错误就该当场炸给开发者,而不是变成一个没有任何线索的挂起。判据 t11。
    held = getattr(_ws_lock_held, "roots", None)
    if held is None:
        held = _ws_lock_held.roots = set()
    key = os.path.realpath(config_dir)
    if key in held:
        raise RuntimeError(
            "locked_workspace_json 不可重入:本线程已经持有这份 workspace.json 的锁。"
            "锁内不许再调用任何 workspace.json 写口"
            "(set_workspace / bind_project / rename_project / delete_project)。")
    held.add(key)
    try:
        yield from _locked_workspace_json_inner(cfg_path, lock_path)
    finally:
        held.discard(key)


def _locked_workspace_json_inner(cfg_path: str, lock_path: str):
    """locked_workspace_json 的锁体;拆出来是为了让重入闸的 finally 一定跑到。"""
    with open(lock_path, "a+b") as lock_fh, ds_lock.exclusive(lock_fh):
        try:
            with open(cfg_path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError):
            raw = None
        if not isinstance(raw, dict):
            raw = None
        box = {"raw": raw, "write": True}
        yield box
        # 安全网:raw 不是 dict 就绝不落盘。调用方进了块、raw 保持 None(坏配置)
        # 又忘了置 write=False 时,原来会把字面量 `null` 写进去 —— 用户手写的配置
        # 当场被毁,而读侧对坏 JSON 的反应是整份降级,现象是"我的项目全没了"。
        # 四个既有写口各自都守住了,但把网收在这里,新写口就不必每个都记得。
        if box["write"] and isinstance(box["raw"], dict):
            _write_workspace_json(cfg_path, box["raw"])


# ── 工具 4.4b set_workspace(Track B/B1)────────────────────────────────────────
# 让用户不碰 JSON、不找开发者就能把工作台接到自己电脑的项目文件夹。写/更新
# <ds_root>/config/workspace.json 的 root(+可选 projectsDir),保留已有 projects 映射。
# 安全(design.md B5):此 root 只 scope 只读文件视图(ds_web 文件/图墙 + open-folder),
# 不拓宽 LLM 能读并上云的内容。铁律不变量:workspace.json.root 与 DS_ORGANIZE_ROOTS
# 永远独立——ds_organize(能碰任意机器文件的写/搬面)由独立 env 白名单管、走 ds-approve;
# 本工具够不到它。谁把两者绑一起 = 把 set_workspace 变成真 exfil 杠杆。
def set_workspace(root: str, projects_dir: str = "", projects_depth: int = 0,
                  ds_root: str = DEFAULT_DS_ROOT) -> dict:
    """把工作台接到用户电脑的项目文件夹根目录。
    root:项目文件夹根的绝对路径;projects_dir:可选,项目夹所在子目录(相对 root,
    "."=项目夹直接在 root 一级);projects_depth:可选(depth2 track),
    1=项目直接在 projects_dir 下(默认),2=中间隔一层分组夹(按年份/客户等分组的
    结构),0=不传保留旧值。保留已有 projects 映射;返回 folder_count(自动认出的
    项目夹数,depth=2 时为跨分组总数)。"""
    if not isinstance(root, str) or not os.path.isabs(root):
        # 拒相对路径:MCP server CWD 不可预测,相对 root 会解析到意外位置
        return {"error": "root_not_absolute"}
    if isinstance(projects_depth, bool) or not isinstance(projects_depth, int) \
            or projects_depth not in (0, 1, 2):
        # 写侧闸:load_config 校验是严格的(坏值=整体降级),脏值不能从这里落盘
        return {"error": "depth_invalid"}
    real_root = os.path.realpath(root)
    if not os.path.isdir(real_root):
        return {"error": "root_not_dir"}  # 不回显路径细节

    cfg_path = os.path.join(ds_root, "config", "workspace.json")
    # 从读旧值到原子替换全程持同一把锁,否则 set_workspace 会用旧 projects
    # 覆盖并发 bind_project 刚写入的映射。
    with locked_workspace_json(ds_root) as box:
        old = box["raw"]
        # 坏 JSON:备份原文,避免静默丢用户手写的映射。复制也在锁内,保证备份
        # 对应本轮实际读到的文件;顶层非 dict 同属坏配置,一并保全。
        if old is None and os.path.exists(cfg_path):
            try:
                shutil.copyfile(cfg_path, cfg_path + ".bak")
            except OSError:
                pass

        # 读旧配置保留 projects/projectsDir/projectsDepth。
        projects: dict = {}
        kept_projects_dir = None
        kept_depth = 0
        if isinstance(old, dict):
            op = old.get("projects")
            if isinstance(op, dict) and all(
                    isinstance(k, str) and isinstance(v, str) for k, v in op.items()):
                projects = op
            opd = old.get("projectsDir")
            if isinstance(opd, str):
                kept_projects_dir = opd
            odp = old.get("projectsDepth")
            if not isinstance(odp, bool) and odp in (1, 2):
                kept_depth = odp

        new_cfg = {"root": real_root, "projects": projects}
        pd = projects_dir if projects_dir else kept_projects_dir  # 显式传优先,否则保留旧值
        if pd:
            new_cfg["projectsDir"] = pd
        # depth 同款语义:显式传优先(1=回默认,清字段不落盘;写不写等价,文件保持最小),
        # 0=不传保留旧值
        depth = projects_depth if projects_depth else kept_depth
        if depth == 2:
            new_cfg["projectsDepth"] = 2
        box["raw"] = new_cfg

    # folder_count 走与前端同一条解析(每请求现读,写完即时生效,无需重启)
    reloaded = ds_workspace.load_config(ds_root)
    folder_count = len(ds_workspace.project_folders(reloaded)) if reloaded else 0
    return {"ok": True, "root": real_root, "folder_count": folder_count}


# ── 工具 4.4c bind_project(bind-project track)──────────────────────────────────
# 自动绑定三级(显式映射/名字直等/token 唯一)对不上真实命名时,项目列表会出现
# "建档项目 + 同名文件夹"两行——保守不绑是对的(绑错比不绑重),本工具就是那个
# 缺失的合并动作:把显式映射写进 workspace.json(显式映射永远优先=纠偏机制)。
# 写侧四闸全复用既有单一真相源,folder 只认已发现的文件夹 key(已发现=已过两级
# PROJECT_NAME_RE+无 symlink+realpath;列不出的文件夹绑了 web 侧也寻址不到)。
def bind_project(project: str, folder: str, ds_root: str = DEFAULT_DS_ROOT) -> dict:
    """把已建档项目与工作区文件夹关联(合并项目列表里的重复条目)。
    project=项目档案 key;folder=项目列表里未建档条目的名字(按年份/客户分组时
    形如 `2026:0315 某项目`,平铺时就是文件夹名)。重绑=覆盖旧映射。"""
    # 闸① project 必须是已建档项目(_resolve=H1 咽喉:within+字符集)
    path, err = _resolve(ds_root, "projects", project)
    if err:
        return err
    if not os.path.exists(path):
        return {"error": "project_not_found"}
    # 闸②~④连同原始 JSON 的读改写都在锁内:folder 的解析根与最终写回的
    # 配置必须来自同一快照,且并发写者不能在两者之间插入更新。
    with locked_workspace_json(ds_root) as box:
        raw = box["raw"]
        cfg = ds_workspace.load_config(ds_root)
        if cfg is None or raw is None:
            box["write"] = False
            return {"error": "workspace_not_configured"}
        # folder 只认已发现的文件夹(不开第二条路径解析面)。两级匹配:
        # 精确 key → 纯名唯一命中(侧栏把 `组:名` 拆成"名+组标"两段展示,
        # 用户念的是纯名;唯一才绑,撞名不猜)。
        folders = ds_workspace.project_folders(cfg)
        matches = [(n, p) for n, p in folders if n == folder]
        if not matches:
            matches = [(n, p) for n, p in folders
                       if ":" in n and n.split(":", 1)[1] == folder]
        if len(matches) != 1:
            box["write"] = False
            return {"error": "folder_ambiguous" if matches else "folder_not_found",
                    "folders": [n for n, _ in folders][:50]}
        folder, target = matches[0]
        rel = os.path.relpath(target, cfg["root"]).replace(os.sep, "/")
        if not isinstance(raw.get("projects"), dict):
            raw["projects"] = {}
        raw["projects"][project] = rel
    return {"ok": True, "project": project, "folder": folder, "rel": rel}


# ── 工具 4.4d rename_project(rename-project track)──────────────────────────────
# 项目名活在五处:档案文件名+首标题、clients/*.md 与 index.md 的 [[链接]]、
# refs-index.md "用于:"段、workspace.json 映射键。改名必须五处齐动,否则映射键
# 悬空(合并重新裂开)、链接断掉——这就是"手改 md 文件"方案被否的原因。
# 执行顺序=引用先改(全幂等),档案 os.replace 最后(=提交点):中途崩 old 档案
# 还在,重跑一遍补齐;反序崩后 old 已消失无法重跑。跨文件无整体原子性=接受的
# deviation(单用户本地盘,窗口毫秒级),返回审计清单如实报改了什么。
def rename_project(old: str, new: str, ds_root: str = DEFAULT_DS_ROOT,
                   today: str | None = None) -> dict:
    """项目改名,五处引用一致更新(变更历史/沟通日志正文里的旧名不动=账本语义)。
    old/new=项目档案名。返回 updated 审计清单(title/clients/index/refs/workspace)。"""
    today = ds_common.today_str(today)
    old = (old or "").strip()
    new = (new or "").strip()
    old_path, err = _resolve(ds_root, "projects", old)
    if err:
        return err
    if not os.path.exists(old_path):
        return {"error": "project_not_found"}
    if new == old:
        return {"error": "same_name"}
    new_path, err = _resolve(ds_root, "projects", new)
    if err:
        return err
    # 链接/分段定界符闸:| 是 refs 分段符、, 是"用于"列表分隔、[ ] 是 [[链接]]
    # 定界(NTFS 本就禁 |,真实文件夹名零成本)。进了这些字符五处一致性就碎了。
    if any(c in new for c in "|,[]"):
        return {"error": "bad_name"}
    if os.path.exists(new_path):
        return {"error": "name_taken"}
    # 档案本体先读(fail fast):坏编码在这里就拒,绝不在引用改到一半后才发现
    # ——否则留下"引用已改、档案没挪"且重跑无法自愈的卡死态。
    try:
        with open(old_path, encoding="utf-8") as fh:
            body = fh.read()
    except (OSError, UnicodeDecodeError):
        return {"error": "project_unreadable"}

    updated = {"title": False, "clients": [], "index": False,
               "refs": 0, "workspace": False}

    # ① clients/*.md + index.md:[[old]] → [[new]](精确定界,散文里的链接也跟走)
    link_old, link_new = f"[[{old}]]", f"[[{new}]]"
    client_dir = os.path.join(ds_root, "clients")
    targets = []
    if os.path.isdir(client_dir):
        targets = [os.path.join(client_dir, f) for f in sorted(os.listdir(client_dir))
                   if f.endswith(".md")]
    index_path = os.path.join(ds_root, "index.md")
    if os.path.isfile(index_path):
        targets.append(index_path)
    for path in targets:
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue  # 坏编码单文件跳过(M1 同哲学),审计里自然不出现
        if link_old not in text:
            continue
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace(link_old, link_new))
        if path == index_path:
            updated["index"] = True
        else:
            updated["clients"].append(os.path.splitext(os.path.basename(path))[0])

    # ② refs-index.md:"用于:"段逗号列表精确项替换(复用 ds_refs 分段真相源,
    # 不子串误伤"锦修外滩二期")
    refs_path = os.path.join(ds_root, "refs-index.md")
    if os.path.isfile(refs_path):
        import ds_refs
        with ds_common.locked_rw(refs_path) as box:
            changed = 0
            lines = box["lines"]
            for i, ln in enumerate(lines):
                seg = ds_refs._used_segment(ln)
                if seg is None:
                    continue
                j, used = seg
                if old not in used:
                    continue
                segs = ln.split(ds_refs._SEG_SEP)
                segs[j] = "用于:" + ",".join(new if u == old else u for u in used)
                lines[i] = ds_refs._SEG_SEP.join(segs)
                changed += 1
            if changed == 0:
                box["write"] = False
            else:
                ds_common.bump_last_updated(lines, today)  # 与 link_ref 同礼数
            updated["refs"] = changed

    # ③ workspace.json:映射键 old→new(值不动;无配置/无该键=跳过)
    with locked_workspace_json(ds_root) as box:
        raw = box["raw"]
        if isinstance(raw, dict) and isinstance(raw.get("projects"), dict) \
                and old in raw["projects"]:
            raw["projects"][new] = raw["projects"].pop(old)
            updated["workspace"] = True
        else:
            box["write"] = False

    # ④ 档案本体:首标题恰好 `# old` 才改(自定义 title 不动);os.replace=提交点
    # (body 已在闸后预读,fail fast)
    first_nl = body.find("\n")
    first_line = body if first_nl == -1 else body[:first_nl]
    if first_line.strip() == f"# {old}":
        body = f"# {new}" + ("" if first_nl == -1 else body[first_nl:])
        updated["title"] = True
        with open(old_path, "w", encoding="utf-8") as fh:
            fh.write(body)
    os.replace(old_path, new_path)
    return {"ok": True, "old": old, "new": new, "updated": updated}


# ── 工具 4.4e delete_project(delete-project track,队列#7)───────────────────────
def delete_project(project: str, ds_root: str = DEFAULT_DS_ROOT,
                   now: str | None = None) -> dict:
    """回收站式删除:档案移 projects/.trash/<name>-<ts>.md(**不真删**,删错可整文件
    捞回);workspace 映射指向该项目则一并摘除(防悬空);clients/index/refs 里的
    [[引用]] **只清点不改动**(账本语义,残留计数返回给助手播报)。"""
    path, err = _resolve(ds_root, "projects", project)
    if err:
        return err
    if not os.path.exists(path):
        return {"error": "project_not_found"}

    # 顺序有讲究:**先摘映射,后挪档案**。两步不原子,中间崩溃时——此序的残局
    # =档案还在+映射掉了(可见的重复行态,重跑 delete 或 bind 都能修);反序的
    # 残局=档案没了+映射悬空(文件夹被悬空映射吃掉,从列表里隐形)。
    mapping_removed = False
    with locked_workspace_json(ds_root) as box:
        raw = box["raw"]
        if (isinstance(raw, dict) and isinstance(raw.get("projects"), dict)
                and project in raw["projects"]):
            del raw["projects"][project]
            mapping_removed = True
        else:
            box["write"] = False

    trash_dir = os.path.join(ds_root, "projects", ".trash")
    os.makedirs(trash_dir, exist_ok=True)
    if now is None:
        from datetime import datetime
        now = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(trash_dir, f"{project}-{now}.md")
    n = 0
    while os.path.exists(dest):  # 同秒同名不互相覆盖(回收站保真第一),序号 -1 起
        n += 1
        dest = os.path.join(trash_dir, f"{project}-{now}-{n}.md")
    os.replace(path, dest)  # 同分区原子移动

    # 引用清点(不改):clients/*.md 与 index.md 数 [[name]];refs-index.md 走
    # ds_refs 分段真相源数「用于:」精确项(panel 双家同标:裸名子串会误伤
    # "翡翠湾-1801二期"这类超串,与 rename ② 同口径)
    link = f"[[{project}]]"
    refs_remaining = {"clients": 0, "index": 0, "refs": 0}
    client_dir = os.path.join(ds_root, "clients")
    if os.path.isdir(client_dir):
        for f in sorted(os.listdir(client_dir)):
            if not f.endswith(".md"):
                continue
            try:
                with open(os.path.join(client_dir, f), encoding="utf-8") as fh:
                    refs_remaining["clients"] += fh.read().count(link)
            except (OSError, UnicodeDecodeError):
                continue  # 坏编码单文件跳过(M1 同哲学)
    index_path = os.path.join(ds_root, "index.md")
    if os.path.isfile(index_path):
        try:
            with open(index_path, encoding="utf-8") as fh:
                refs_remaining["index"] = fh.read().count(link)
        except (OSError, UnicodeDecodeError):
            pass
    refs_path = os.path.join(ds_root, "refs-index.md")
    if os.path.isfile(refs_path):
        import ds_refs
        try:
            with open(refs_path, encoding="utf-8") as fh:
                for ln in fh.read().split("\n"):
                    seg = ds_refs._used_segment(ln)
                    if seg is not None and project in seg[1]:
                        refs_remaining["refs"] += 1
        except (OSError, UnicodeDecodeError):
            pass

    rel = os.path.relpath(dest, ds_root).replace(os.sep, "/")
    return {"ok": True, "project": project, "trashed": rel,
            "mapping_removed": mapping_removed, "refs_remaining": refs_remaining}


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


def read_client(name: str, ds_root: str = DEFAULT_DS_ROOT) -> dict:
    """读取业主档案原文(镜像 read_project;clients/ 走同一 _resolve 咽喉)。"""
    path, err = _resolve(ds_root, "clients", name)
    if err:
        return err
    if not os.path.exists(path):
        return {"error": "client_not_found"}
    with open(path, encoding="utf-8") as fh:
        return {"ok": True, "content": fh.read()}


# ── 头部字段 upsert / read(update_client + set_stage 单一实现，防漂移）─────────
# 「头部区找字段行替换、缺行补插」在 update_client 与 set_stage 里逐字节重复过两份
# （tool-audit 遗留）；收敛成一处。头部区 = 首个 `## ` 段头之前，字段行只在这里
# 找/插，段落正文永不误锚。全角冒号显式转义 ：（字面量在中英混排里易被打成
# 半角，panel 抓过一次，硬教训=全角标点必须 \uXXXX），两侧必须同源。
def _header_field_re(field: str) -> "re.Pattern[str]":
    return re.compile(rf"^- {re.escape(field)}[:\uff1a]\s*(?P<val>.*)$")


def _upsert_header_field(lines: list[str], field: str, value: str) -> str | None:
    """头部区里把 `- {field}: {value}` 写进去：命中该字段行→替换并返回旧值原文
    （可能为空串）；缺行→插到头部区末尾并返回 None。调用方据「返回 None 与否」区分
    inserted/replaced，据旧值算 prev。零行为变化（现有套件即回归 oracle）。"""
    field_re = _header_field_re(field)
    head_end = next((i for i, ln in enumerate(lines)
                     if ln.startswith("## ")), len(lines))
    idx = next((i for i in range(head_end) if field_re.match(lines[i])), None)
    if idx is not None:
        prev = field_re.match(lines[idx]).group("val")
        lines[idx] = f"- {field}: {value}"
        return prev
    insert_at = 0
    for i in range(head_end):
        if lines[i].startswith("- "):
            insert_at = i + 1
        elif lines[i].startswith("# ") and insert_at == 0:
            insert_at = i + 1
    lines[insert_at:insert_at] = [f"- {field}: {value}"]
    return None


def _read_header_field(lines: list[str], field: str) -> str:
    """头部区里读 `- {field}:` 的值（缺行返回空串）。_upsert 的只读镜像，
    同一 head_end/字段行定位口径（list_projects / ds_lint 复用，不另造第二套解析）。"""
    field_re = _header_field_re(field)
    head_end = next((i for i, ln in enumerate(lines)
                     if ln.startswith("## ")), len(lines))
    for i in range(head_end):
        m = field_re.match(lines[i])
        if m:
            return m.group("val").strip()
    return ""


def update_client(name: str, field: str, value: str,
                  ds_root: str = DEFAULT_DS_ROOT, today: str | None = None) -> dict:
    """改业主档案。两档语义:白名单字段(CLIENT_FIELDS)=替换头部字段行的值,
    行缺失(手建档案)则补插头部区末尾;`备注` = 追加一行 `- 日期 内容` 到段尾
    (积累不覆盖,段缺失自动补建,同 log_communication 先例)。
    value 经 sanitize_field 折成单行(多行 = 伪造字段行/段头,7-03 盲评铁律);
    拒空 value(静默清空比显式拒绝更危险,要清让设计师给个"无")。"""
    today = ds_common.today_str(today)
    field = ds_common.sanitize_field(field)
    value = ds_common.sanitize_field(value)
    path, err = _resolve(ds_root, "clients", name)
    if err:
        return err
    if field != _NOTE_FIELD and field not in CLIENT_FIELDS:
        return {"error": "bad_field", "fields": [*CLIENT_FIELDS, _NOTE_FIELD]}
    if not value:
        return {"error": "empty_value"}
    if not os.path.exists(path):
        return {"error": "client_not_found"}

    action = ""
    with ds_common.locked_rw(path) as box:
        lines = box["lines"]
        if field == _NOTE_FIELD:
            entry = f"- {today} {value}"
            hdr = next((i for i, ln in enumerate(lines)
                        if ln.startswith(_NOTE_HEADER)), None)
            if hdr is None:
                if lines and lines[-1].strip():
                    lines.append("")
                lines.extend([_NOTE_HEADER, entry])
            else:
                # 段界 = 下一 `^## `(client 档案无页脚,`---` 一并防御);
                # 插到段内最后一条非空行之后 —— 同 log_communication 的段内定位
                end = next((j for j in range(hdr + 1, len(lines))
                            if lines[j].startswith("## ") or lines[j].startswith("---")),
                           len(lines))
                insert_at = hdr + 1
                for i in range(hdr + 1, end):
                    if lines[i].strip():
                        insert_at = i + 1
                lines[insert_at:insert_at] = [entry]
            action = "noted"
        else:
            # 头部字段 upsert 单一实现(_upsert_header_field):返回 None=缺行补插=inserted,
            # 返回旧值(含空串)=命中替换=replaced。
            prev = _upsert_header_field(lines, field, value)
            action = "inserted" if prev is None else "replaced"
    return {"ok": True, "client": name, "field": field, "action": action}


def _validate_since(since: str | None, today: str) -> tuple[str | None, str | None]:
    if since in (None, ""):
        return None, None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", since):
        return None, "invalid_since"
    try:
        date.fromisoformat(since)
        today_d = date.fromisoformat(today)
    except ValueError:
        return None, "invalid_since"
    if date.fromisoformat(since) > today_d:
        return None, "since_in_future"
    return since, None


def _create_stage_history_section(lines: list[str], entry: str) -> None:
    """补建 `## 阶段历史`:优先落在第一个二级段前,也就是 `## 变更记录` 之前。"""
    pos = next((i for i, ln in enumerate(lines) if ln.startswith("## ")), None)
    if pos is None:
        pos = next((i for i in range(len(lines) - 1, -1, -1)
                    if lines[i].startswith("---")), len(lines))
    block = [_STAGE_HISTORY_HEADER, "", entry, ""]
    if pos > 0 and lines[pos - 1].strip():
        block = [""] + block
    lines[pos:pos] = block


def _append_stage_history_entry(lines: list[str], entry: str) -> None:
    b = _section_bounds(lines, _STAGE_HISTORY_HEADER)
    if b is None:
        _create_stage_history_section(lines, entry)
        return
    hidx, end = b
    last = hidx
    for i in range(hidx + 1, end):
        if lines[i].strip():
            last = i
    lines.insert(last + 1, entry)


def set_stage(project: str, stage: str,
              since: str | None = None,
              ds_root: str = DEFAULT_DS_ROOT, today: str | None = None) -> dict:
    """推进/补录项目阶段。`## 阶段历史` 是当前阶段起始日的唯一真相源。"""
    today = ds_common.today_str(today)
    stage = ds_common.sanitize_field(stage)
    path, err = _resolve(ds_root, "projects", project)
    if err:
        return err
    if stage not in PROJECT_STAGES:
        return {"error": "bad_stage", "stages": list(PROJECT_STAGES)}
    since, err_code = _validate_since(since, today)
    if err_code:
        return {"error": err_code}
    if not os.path.exists(path):
        return {"error": "project_not_found"}

    with ds_common.locked_rw(path) as box:
        lines = box["lines"]
        prev = _read_header_field(lines, "阶段") or None
        current_same = prev == stage
        entries = _stage_history_entries_with_lines(lines)

        if current_same and since is None:
            box["write"] = False
            timer = stage_timer("\n".join(lines), today=today)
            return {"ok": True, "project": project, "stage": stage, "prev": prev,
                    "since": timer["since"], "days": timer["days"]}

        if current_same and since is not None and entries and entries[-1]["stage"] == stage:
            lower = entries[-2]["date"] if len(entries) >= 2 else None
            if lower is not None and since < lower:
                box["write"] = False
                return {"error": "since_before_prev"}
            lines[entries[-1]["line_index"]] = f"- {since} {stage}"
        else:
            lower = entries[-1]["date"] if entries else None
            entry_date = since or today
            if lower is not None and entry_date < lower:
                box["write"] = False
                return {"error": "since_before_prev"}
            else:
                _upsert_header_field(lines, "阶段", stage)
                _append_stage_history_entry(lines, f"- {entry_date} {stage}")
        ds_common.bump_last_updated(lines, today)
        timer = stage_timer("\n".join(lines), today=today)
    return {"ok": True, "project": project, "stage": stage, "prev": prev,
            "since": timer["since"], "days": timer["days"]}


# ── 工具 4.6 create_project ─────────────────────────────────────────────────
def create_project(project: str, client: str = "", stage: str = "洽谈", address: str = "",
                   ds_root: str = DEFAULT_DS_ROOT, today: str | None = None) -> dict:
    """新建项目 projects/<project>.md(按 SCHEMA 骨架,含变更记录头+页脚)。已存在则拒绝
    覆盖;业主档案缺失时自动补一个最小 stub,避免悬空 [[链接]]。之后 append_change 可直接接上。

    **业主可空**(track opendesign-intake-simplify,真机反馈 2026-07-24 #3:建档表单
    只填项目名)。空业主时:①不写 `[[链接]]`,只留空字段行 `- 业主: ` —— 写成 `[[]]`
    会被 ds_lint 判 broken_link,等于新档案自带一条体检报错;②不建业主 stub(不猜业主
    叫什么)。项目名仍必填。

    ⚠️ 空业主的**后补边界**(panel subkimi 指出我原先的说法失真,已改正):业主信息本身
    可以随时用 `create_client(name, linked=项目)` / `update_client` 记在 clients/ 那侧
    (关联关系从业主档案指回项目);但**项目档案头上这行 `- 业主:` 目前没有任何工具能改**
    —— `_upsert_header_field` 只被 update_client(业主档案字段)与 set_stage(阶段)调用。
    也就是说:建档时没填,项目档案里这行就一直空着(界面上目前不渲染该字段,无可见影响)。
    要让它可补,需要另开一个对称的项目字段写口(follow-up,新写口按规矩走独立四审)。
    """
    today = ds_common.today_str(today)
    project = ds_common.sanitize_field(project)   # 同时作文件名与标题:消毒后一致
    client = ds_common.sanitize_field(client)     # 折行 + strip:空白串等于"没填"
    stage = ds_common.sanitize_field(stage)
    address = ds_common.sanitize_field(address)
    if not project:
        return {"error": "empty_name"}
    # stage 词表闸(对齐 set_stage;tool-audit 遗留的不对称):非词表值直接拒、不建文件、
    # 不补业主 stub。sanitize 折行后只有词表字面量能落盘,注入面由构造消灭。
    if stage not in PROJECT_STAGES:
        return {"error": "bad_stage", "stages": list(PROJECT_STAGES)}
    path, err = _resolve(ds_root, "projects", project)
    if err:
        return err
    if os.path.exists(path):
        return {"error": "project_exists"}
    # 业主档案不存在则先补最小 stub(用消毒后的 client 名;逃逸/已存在都安全跳过)。
    # 空业主直接短路:没有名字就没有档案可建,也不编一个。
    if client:
        cpath, cerr = _resolve(ds_root, "clients", client)
        if not cerr and not os.path.exists(cpath):
            create_client(client, linked=project, ds_root=ds_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # 有名才写 [[链接]](与 _CLIENT_TEMPLATE 的 linked 同款写法,不发明第二套)
    body = _PROJECT_TEMPLATE.format(
        slug=project, client=(f"[[{client}]]" if client else ""),
        stage=stage, address=address, today=today)
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(body)
    return {"ok": True, "project": project, "client": client, "stage": stage}


# ── stdio MCP server 包装(需 `pip install mcp`;未装不影响以上核心) ────────
def _run_mcp() -> None:
    from mcp.server.fastmcp import FastMCP  # 延迟导入:未装时上面的核心与 tests 照常可用
    import ds_lint  # 延迟导入:ds_lint 反向 import ds_tools,顶层导会成环;仅 MCP 运行期需要

    ds_root = os.environ.get("DS_ROOT", DEFAULT_DS_ROOT)
    server = FastMCP("design-studio")

    @server.tool()
    def create_client_tool(name: str, contact: str = "", linked: str = "") -> dict:
        """新建业主档案。name=业主称呼;contact=联系方式(可选);linked=关联项目slug(可选)。"""
        return create_client(name, contact=contact, linked=linked, ds_root=ds_root)

    @server.tool()
    def create_project_tool(project: str, client: str = "", stage: str = "洽谈",
                            address: str = "") -> dict:
        """新建项目(业主不存在会自动补档)。记录任何变更/待办前,项目必须先经此工具建好。
        project=项目slug;client=业主称呼——**知道就填,不知道就留空,绝对不要猜或编**
        (编一个假名字会污染业主档案)。⚠️ 留空的代价:项目档案里「业主」那行会一直空着,
        **现在没有工具能事后改它**;业主本人的信息倒是可以随时用 create_client/update_client
        记在业主档案那侧。所以设计师这次说得出业主名就填上。
        stage=阶段(默认洽谈);address=地址/户型(可选)。"""
        return create_project(project, client, stage=stage, address=address, ds_root=ds_root)

    @server.tool()
    def append_change_tool(project: str, content: str, space: str = "",
                           batch_title: str = "") -> dict:
        """追加一条业主新提的修改需求(自动编号,标记 [待确认])。项目须已存在(见 create_project)。
        space=所属空间(可选但尽量带,如 玄关/客厅/主卧/厨房/卫生间/阳台;听得出就填)。

        batch_title=这一批的主题(可选,4-10 字的人话,如「效果图修改」「水电改动」)。
        设计师一次贴进来的一段业主原话往往包含好几条修改——**把它们当作一批,
        每一条都传完全相同的 batch_title**,待办页就会用这句话当这批的小标题,
        而不是干巴巴的日期。
        同一段原话里如果明显是两件不相干的事(比如既说效果图又说水电),
        就分成两批、各用各的标题。不传 = 不起名,界面会自动拿第一条内容凑一个。

        **哪条带期限,记完立刻用 set_due_date 补上**(track opendesign-due-writer):
        一段原话里常常只有其中一条说了"这周五之前""8 月 10 号前"。
        本工具**不收截止日**,返回里的 `change_id` 就是给你接着调 set_due_date 用的。
        一批记好几条时最容易在这里掉链子——**记完这一批,回头看哪条有期限,
        一条一条把日期设上**;期限只写在正文里等于没记,待办页看不见。"""
        return append_change(project, content, ds_root=ds_root, space=space,
                             batch_title=batch_title)

    @server.tool()
    def set_change_status_tool(project: str, change_id: str, status: str) -> dict:
        """推进某条变更状态。status 必须是:待确认/进行中/已完成/已关闭。"""
        return set_change_status(project, change_id, status, ds_root=ds_root)

    @server.tool()
    def set_due_date_tool(project: str, cnum, due: str = "") -> dict:
        """给一条变更设/清截止日。cnum=变更编号(如 3 或 "C3",就是 append_change 返回的
        change_id);due=YYYY-MM-DD,传空串清除。

        **业主话里出现期限,就是你的活**(track opendesign-due-writer):
        「8 月 10 号之前」「这周五之前」「下周五前」「月底前」——记完那条变更,
        **紧接着**用它的编号把日期设上,别只把期限写进正文,写进正文的日期
        待办页看不见,那条待办仍然算"没有截止日"。
        相对说法你自己换算成具体日期:上下文最上面那行 `Current Time` 就是今天几号、
        星期几,按它算。
        ⚠️ **业主没给期限就别设**:「尽快」「催得急」「有空改一下」不是期限,
        **编一个日期比空着更糟**——待办页会把这条不存在的死线排到所有事情最前面。
        真拿不准是哪天,就问设计师一句,别猜。"""
        return set_due_date(project, cnum, due or None, ds_root=ds_root)

    @server.tool()
    def log_communication_tool(project: str, text: str, source: str = "") -> dict:
        """把业主的原话逐字存进项目「沟通日志」(多行原样保留)。
        设计师贴来一段业主的修改意见/聊天记录时,按三步走:
        ①先用本工具存原文(text=原话原样,别改写;source=来源,如 微信/电话/现场,可选);
        ②其中**确定要做的**,逐条总结成短句 append_change(一条一件事,去掉客套和废话,
        能听出空间就带 space);
        ③业主**还在摇摆/没拍板的**,不要记变更——把那几句原文引用贴回对话,请设计师定,
        定了再 append_change。
        回复设计师时报清楚:存了原文、落了哪几条(C 编号)、哪几句在等拍板。"""
        return log_communication(project, text, source=source, ds_root=ds_root)

    @server.tool()
    def read_project_tool(name: str) -> dict:
        """读取某个项目的完整记录(业主、阶段、变更、沟通日志)。"""
        return read_project(name, ds_root=ds_root)

    @server.tool()
    def set_stage_tool(project: str, stage: str, since: str = "") -> dict:
        """项目已经进入某阶段时改阶段。stage 必须是词表之一:洽谈/量房/平面方案/
        方案深化/效果图/施工图/施工交底/施工跟进/软装/竣工验收/售后。
        若说了进入日期(含上周三/7 月 20 号等相对说法),换算成 YYYY-MM-DD 传 since。
        拿不准就问,不要猜日期。"准备进/打算进/下周进"表示还没进,不许调用。"""
        return set_stage(project, stage, since=since or None, ds_root=ds_root)

    @server.tool()
    def read_client_tool(name: str) -> dict:
        """读取业主档案(联系方式/关联项目/预算区间/风格偏好/关键约束/决策习惯/备注)。
        被问某业主的情况、或聊到一个项目想先回顾业主偏好和雷区时用。
        name=业主称呼(clients/ 下的档案名)。回答业主相关问题一律先读档案,不要凭记忆猜。"""
        return read_client(name, ds_root=ds_root)

    @server.tool()
    def update_client_tool(name: str, field: str, value: str) -> dict:
        """更新业主档案。业主信息有变(改预算/换电话/偏好变了),或听到值得记住的
        性格、雷区、沟通要点时用。field 必须是其一:联系方式/预算区间/风格偏好/
        关键约束/决策习惯(=整字段改成新值 value)或 备注(=追加一条带日期的记录,
        原有备注不动;性格雷区类零碎观察记这档)。业主关联哪个项目是机器维护的字段,
        建项目/项目改名时自动更新。"""
        return update_client(name, field, value, ds_root=ds_root)

    @server.tool()
    def delete_project_tool(project: str) -> dict:
        """删除项目档案。设计师要求删除某个项目档案时用——**典型场景:清理误建的
        重复档案**("把重复的删掉"就是在叫这个工具)。回收站式:移入 projects/.trash/,
        不真删,删错可捞回。**纪律:调用前先复述项目名得到设计师确认**;设计师没提出
        删除时,绝不主动提议或自作主张删任何档案。删完把返回里的 trashed 路径和
        refs_remaining(业主/索引里残留的引用数)报给设计师。"""
        return delete_project(project, ds_root=ds_root)

    @server.tool()
    def list_todos_tool(stale_days: int = 7) -> dict:
        """列出所有项目的未关闭事项 + 超期未更新项目。"""
        return list_todos(stale_days, ds_root=ds_root)

    @server.tool()
    def list_projects_tool() -> dict:
        """列出手上所有项目:被问"有哪些项目/项目列表/所有项目/一共几个项目/都在做什么"
        时用。返回每个项目的 业主/阶段/最后更新,按项目名排序。只读,回答项目盘点问题
        先调这个,不要凭记忆报。"""
        return list_projects(ds_root=ds_root)

    @server.tool()
    def lint_pkb_tool() -> dict:
        """给项目/业主档案做一次体检(健康检查):设计师问"检查一下档案/有没有问题/
        帮我体检/档案还正常吗/有没有重复或断链"时用。确定性只读扫描,只报告不改动,
        查:断链、重复档案、坏阶段、C 编号撞车、参考图索引悬挂/丢文件、工作区映射悬挂、
        废弃 index.md 残留、坏编码文件。返回 findings 清单(每条含 check/target/detail),
        照它逐条播报,修复动作仍走对应工具(改名/删除/organize 闸),别自己手改文件。"""
        return ds_lint.lint_pkb(ds_root)

    @server.tool()
    def set_workspace_tool(root: str, projects_dir: str = "",
                           projects_depth: int = 0) -> dict:
        """把工作台接到用户电脑的项目文件夹根目录(以后能直接看文件和参考图)。
        root=项目文件夹根的绝对路径(直接传用户说的路径即可,反斜杠不用转义);
        projects_dir=可选,项目夹所在子目录(相对 root);若接上后 folder_count=0 且用户说
        项目就直接放在这个文件夹里,再传 projects_dir="."。
        projects_depth=可选:项目夹直接摆在 projects_dir 下不用传;用户的项目按
        年份/客户等先分了一层文件夹(如 2026/0315 某项目)再传 2,所有分组下的项目
        会一起认出。返回 folder_count=认出的项目夹数(depth=2 时为跨分组总数)。"""
        return set_workspace(root, projects_dir=projects_dir,
                             projects_depth=projects_depth, ds_root=ds_root)

    @server.tool()
    def rename_project_tool(old: str, new: str) -> dict:
        """项目改名(档案/业主链接/参考图索引/工作区映射五处一致更新)。
        设计师要求改项目名、或项目名与文件夹名对齐时用。old=现在的项目名,
        new=新名。变更历史正文里的旧名不改(账本,历史读起来是当时的名字,正常)。
        返回 updated 清单,照它播报改了哪些地方。"""
        return rename_project(old, new, ds_root=ds_root)

    @server.tool()
    def bind_project_tool(project: str, folder: str) -> dict:
        """把已建档项目与工作区文件夹关联(合并项目列表里的重复条目)。
        用户说"那个文件夹就是 XX 项目"、或项目列表出现同名两行(一个建档一个
        未建档)时用。project=项目档案名;folder=用户念的文件夹名即可(纯名唯一
        就绑;按年份分组撞名/没找到时,返回里有 folders 候选名单,从中挑准确的
        `组:名` 重试一次,别自己编)。重绑=覆盖,绑错再绑一次即可。"""
        return bind_project(project, folder, ds_root=ds_root)

    server.run()


if __name__ == "__main__":
    _run_mcp()
