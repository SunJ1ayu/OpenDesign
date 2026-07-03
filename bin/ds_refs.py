#!/usr/bin/env python3
"""design-studio 参考图索引工具层 — track opendesign-ref-images design.md 的实现。

两层(同 ds_tools.py):纯 Python 核心 + 末尾 stdio FastMCP 包装(未装 mcp 不影响核心)。

契约铁律:
  - 工具只写索引 refs-index.md,**永远不碰图片文件本身**(移动图片走 organize 确认闸)。
  - 索引行:`- [r<n>] 风格|空间 | 来源:x | 文件:refs/... | 用于:proj1,proj2 | 备注:x`,
    只增不删,`r<n>\\b` 锚定,路径存储统一 / 分隔符(Windows/Linux 索引互通)。
  - **字段是单行且不含 ` | `**:source/note 在写入口消毒(折换行、竖线→/,
    ds_common.sanitize_field)——否则可伪造索引行/劫持字段;字段解析一律按
    ` | ` 分段取段(_used_segment),不做全行正则搜索(防字段内容里的字面
    `用于:` 劫持第一处匹配)。
  - 词表:空间**锁死**(无新增入口);风格**半开放**(add_style 可增,新增前 AGENTS.md
    约定先跟设计师确认)。词表落在 refs-vocab.md,首次使用自动生成。
"""
from __future__ import annotations

import os
import re

import ds_common  # 共享:防逃逸谓词/字段消毒/页脚锚定/加锁读改写(同目录模块)
import ds_lock    # add_style 走整文追加,单独用锁

# env DS_ROOT 缺失时基于 __file__ 推导(bin/ 的上一级):Linux/Windows 通用,不硬编码 /root
DEFAULT_DS_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

SPACES = ("玄关", "客厅", "餐厅", "厨房", "中西厨", "主卧", "次卧", "儿童房", "老人房",
          "书房", "主卫", "客卫", "衣帽间", "阳台", "家政区", "影音室", "健身房",
          "走廊", "庭院", "全屋")  # 锁死:工具不提供新增入口
DEFAULT_STYLES = ("奶油风", "侘寂风", "法式", "现代简约", "极简", "轻奢", "新中式",
                  "中古风", "原木风", "工业风", "美式", "日式", "北欧", "复古", "混搭")

_REF_RE = re.compile(r"^- \[r(?P<num>\d+)\]\s")
_SEG_SEP = " | "

_INDEX_HEADER = """# 参考图索引

> 每图一条,由 ds_refs 工具维护:只增不删。字段:风格|空间 | 来源 | 文件 | 用于 | 备注。

"""
_INDEX_TAIL = "\n---\n最后更新: {today}\n"

_VOCAB_TEMPLATE = """# 参考图词表(ds_refs 工具读写)

## 空间(锁死 —— 工具无新增入口,要改动手编辑本文件)
{spaces}

## 风格(半开放 —— add_style 可增,新增前先跟设计师确认)
{styles}
"""


def _index_path(ds_root: str) -> str:
    return os.path.join(ds_root, "refs-index.md")


def _vocab_path(ds_root: str) -> str:
    return os.path.join(ds_root, "refs-vocab.md")


# ── 词表 ────────────────────────────────────────────────────────────────────
def _ensure_vocab(ds_root: str) -> str:
    path = _vocab_path(ds_root)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(_VOCAB_TEMPLATE.format(
                spaces="\n".join(f"- {s}" for s in SPACES),
                styles="\n".join(f"- {s}" for s in DEFAULT_STYLES)))
    return path


def _load_styles(ds_root: str) -> list[str]:
    """从 refs-vocab.md 的「风格」节读词表(空间节固定用 SPACES 常量,锁死)。"""
    path = _ensure_vocab(ds_root)
    styles, in_styles = [], False
    with open(path, encoding="utf-8") as fh:
        for ln in fh:
            if ln.startswith("## "):
                in_styles = ln.startswith("## 风格")
                continue
            if in_styles and ln.startswith("- "):
                styles.append(ln[2:].strip())
    return styles


def add_style(style: str, ds_root: str = DEFAULT_DS_ROOT) -> dict:
    style = (style or "").strip()
    # 单个词条:分隔符与换行都不许(换行 = 一次调用注入多个词表项)
    if not style or any(c in style for c in "|,\r\n"):
        return {"error": "bad_style"}
    path = _ensure_vocab(ds_root)
    if style in _load_styles(ds_root):
        return {"ok": True, "style": style, "note": "already_exists"}
    with open(path, "r+", encoding="utf-8") as fh, ds_lock.exclusive(fh):
        fh.seek(0)
        text = fh.read()
        # 追加到风格节末尾(= 文件末尾,风格是最后一节;简单可靠)
        if not text.endswith("\n"):
            text += "\n"
        text += f"- {style}\n"
        fh.seek(0)
        fh.truncate()
        fh.write(text)
    return {"ok": True, "style": style}


def _split_tags(value: str) -> list[str]:
    return [t.strip() for t in (value or "").replace("，", ",").split(",") if t.strip()]


def _used_segment(line: str) -> tuple[int, list[str]] | None:
    """按 ` | ` 分段找 `用于:` 段。返回 (段下标, 项目列表);没有该段返回 None。
    分段而不全行搜:字段内容已消毒不含 ` | `,段首匹配不会被字段里的字面量劫持。"""
    segs = line.split(_SEG_SEP)
    for j, seg in enumerate(segs):
        if seg.startswith("用于:"):
            return j, _split_tags(seg[len("用于:"):])
    return None


# ── 索引读改写 ──────────────────────────────────────────────────────────────
def _ensure_index(ds_root: str, today: str) -> str:
    path = _index_path(ds_root)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(_INDEX_HEADER + _INDEX_TAIL.format(today=today))
    return path


# ── 工具 1 add_ref ──────────────────────────────────────────────────────────
def add_ref(file: str, style: str, space: str, source: str = "",
            note: str = "", ds_root: str = DEFAULT_DS_ROOT,
            today: str | None = None) -> dict:
    today = ds_common.today_str(today)
    source = ds_common.sanitize_field(source, ban_pipe=True)
    note = ds_common.sanitize_field(note, ban_pipe=True)

    styles_vocab = _load_styles(ds_root)
    styles = _split_tags(style)
    spaces = _split_tags(space)
    if not styles or any(s not in styles_vocab for s in styles):
        return {"error": "style_unknown", "vocab": styles_vocab}
    if not spaces or any(s not in SPACES for s in spaces):
        return {"error": "space_unknown", "vocab": list(SPACES)}

    # 文件:必须真实存在于 DS_ROOT/refs/ 内(realpath 防逃逸 + 防手误)
    refs_base = os.path.realpath(os.path.join(ds_root, "refs"))
    target = os.path.realpath(os.path.join(ds_root, file))
    if not ds_common.within(refs_base, target):
        return {"error": "path_escape"}
    if not os.path.isfile(target):
        return {"error": "file_not_found", "file": file}
    rel = os.path.relpath(target, ds_root).replace(os.sep, "/")  # 统一 / 分隔符

    path = _ensure_index(ds_root, today)
    with ds_common.locked_rw(path) as box:
        lines = box["lines"]
        num = max((int(m.group("num")) for ln in lines
                   if (m := _REF_RE.match(ln))), default=0) + 1
        new_line = _SEG_SEP.join([
            f"- [r{num}] {','.join(styles)}|{','.join(spaces)}",
            f"来源:{source}", f"文件:{rel}", "用于:", f"备注:{note}"])
        # 插到最后一条索引行之后;无则插在头部区后(--- 之前)
        last = None
        for i, ln in enumerate(lines):
            if _REF_RE.match(ln):
                last = i
        if last is not None:
            lines.insert(last + 1, new_line)
        else:
            sep = next((i for i, ln in enumerate(lines) if ln.startswith("---")),
                       len(lines))
            lines.insert(sep, new_line)
        ds_common.bump_last_updated(lines, today)

    return {"ok": True, "ref_id": f"r{num}", "line": new_line}


# ── 工具 2 find_refs ────────────────────────────────────────────────────────
def find_refs(style: str = "", space: str = "", project: str = "",
              keyword: str = "", ds_root: str = DEFAULT_DS_ROOT) -> dict:
    path = _index_path(ds_root)
    if not os.path.exists(path):
        return {"ok": True, "hits": []}
    hits = []
    with open(path, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.rstrip("\n")
            if not _REF_RE.match(ln):
                continue
            # 标签段 = 第一段;用于段按段首匹配;keyword 全行模糊
            head = ln.split(_SEG_SEP, 1)[0]       # "- [rN] 风格,…|空间,…"
            tag_part = head.split("] ", 1)[1] if "] " in head else ""
            styles = _split_tags(tag_part.split("|")[0]) if "|" in tag_part else []
            spaces = _split_tags(tag_part.split("|")[1]) if "|" in tag_part else []
            seg = _used_segment(ln)
            used = seg[1] if seg else []
            if style and style.strip() not in styles:
                continue
            if space and space.strip() not in spaces:
                continue
            if project and project.strip() not in used:
                continue
            if keyword and keyword.strip() not in ln:
                continue
            hits.append(ln)
    return {"ok": True, "hits": hits, "count": len(hits)}


# ── 工具 3 link_ref ─────────────────────────────────────────────────────────
def link_ref(ref_id: str, project: str, ds_root: str = DEFAULT_DS_ROOT,
             today: str | None = None) -> dict:
    today = ds_common.today_str(today)
    m = re.fullmatch(r"r(\d+)", (ref_id or "").strip())
    if not m:
        return {"error": "ref_not_found"}
    num = m.group(1)
    # 消毒在存在性校验之前:带换行/竖线的名字折叠后对不上真实文件 → project_not_found,
    # 换行永远进不了"用于:"段(纵深防御;正常项目名不受影响)
    project = ds_common.sanitize_field(project, ban_pipe=True)
    if not project or not os.path.exists(
            os.path.join(ds_root, "projects", f"{project}.md")):
        return {"error": "project_not_found"}

    path = _index_path(ds_root)
    if not os.path.exists(path):
        return {"error": "ref_not_found"}
    line_re = re.compile(rf"^- \[r{num}\]\s")  # \[r<num>\] 整体锚定,防 r2 误伤 r12
    with ds_common.locked_rw(path) as box:
        lines = box["lines"]
        idx = [i for i, ln in enumerate(lines) if line_re.match(ln)]
        if len(idx) != 1:
            box["write"] = False
            return {"error": "ref_not_found" if not idx else "ambiguous_ref"}
        i = idx[0]
        seg = _used_segment(lines[i])
        if seg is None:
            box["write"] = False
            return {"error": "malformed_entry"}
        j, used = seg
        if project not in used:
            used.append(project)
            segs = lines[i].split(_SEG_SEP)
            segs[j] = "用于:" + ",".join(used)
            lines[i] = _SEG_SEP.join(segs)
        ds_common.bump_last_updated(lines, today)
        result = lines[i]
    return {"ok": True, "ref_id": f"r{num}", "line": result}


# ── stdio MCP server 包装(需 `pip install mcp`;未装不影响核心) ─────────────
def _build_server(ds_root: str):
    from mcp.server.fastmcp import FastMCP  # 延迟导入

    server = FastMCP("design-studio-refs")

    @server.tool()
    def add_ref_tool(file: str, style: str, space: str, source: str = "",
                     note: str = "") -> dict:
        """登记一张参考图到索引。file=refs/ 下相对路径(文件须已存在);
        style/space 须在词表内(可逗号分隔多值);source 如 小红书/Pinterest/Behance。"""
        return add_ref(file, style, space, source, note, ds_root=ds_root)

    @server.tool()
    def find_refs_tool(style: str = "", space: str = "", project: str = "",
                       keyword: str = "") -> dict:
        """按风格/空间/用过的项目/关键词查参考图,条件 AND,全空=全量。"""
        return find_refs(style, space, project, keyword, ds_root=ds_root)

    @server.tool()
    def link_ref_tool(ref_id: str, project: str) -> dict:
        """记录某张参考图(r<n>)用在了某个项目。"""
        return link_ref(ref_id, project, ds_root=ds_root)

    @server.tool()
    def add_style_tool(style: str) -> dict:
        """往风格词表新增一个风格。新增前必须先跟设计师确认过。"""
        return add_style(style, ds_root=ds_root)

    return server


def _run_mcp() -> None:
    _build_server(os.environ.get("DS_ROOT", DEFAULT_DS_ROOT)).run()


if __name__ == "__main__":
    _run_mcp()
