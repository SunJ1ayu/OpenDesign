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

## 空间(锁死 —— 权威清单是 ds_refs.py 的 SPACES 常量;下面只是照抄一份供查阅,
## 改这里没用,要增删空间词得改 ds_refs.py)
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


def _parse_styles(text: str) -> list[str]:
    """从 refs-vocab.md 文本解析「风格」节词表(空间节固定用 SPACES 常量,锁死)。
    抽成纯函数:_load_styles(读文件)与 add_style 锁内复查(已持文本)同一口径。"""
    styles, in_styles = [], False
    for ln in text.splitlines():
        if ln.startswith("## "):
            in_styles = ln.startswith("## 风格")
            continue
        if in_styles and ln.startswith("- "):
            styles.append(ln[2:].strip())
    return styles


def _load_styles(ds_root: str) -> list[str]:
    path = _ensure_vocab(ds_root)
    with open(path, encoding="utf-8") as fh:
        return _parse_styles(fh.read())


def add_style(style: str, ds_root: str = DEFAULT_DS_ROOT) -> dict:
    style = (style or "").strip()
    # 单个词条:分隔符与换行都不许(换行 = 一次调用注入多个词表项)
    if not style or any(c in style for c in "|,\r\n"):
        return {"error": "bad_style"}
    path = _ensure_vocab(ds_root)
    with open(path, "r+", encoding="utf-8") as fh, ds_lock.exclusive(fh):
        fh.seek(0)
        text = fh.read()
        # L8(07-13 盲评):查重在锁内(持文本后),否则并发两次 add 同词都过锁外
        # 检查 → 词表出现重复行。持锁复查=唯一写者视角。
        if style in _parse_styles(text):
            return {"ok": True, "style": style, "note": "already_exists"}
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


def _prefixed_segment(line: str, prefix: str) -> str:
    """取以 prefix 开头的那段的值(同 _used_segment 的分段口径,防字段内字面量劫持)。"""
    for seg in line.split(_SEG_SEP):
        if seg.startswith(prefix):
            return seg[len(prefix):].strip()
    return ""


def parse_ref_line(line: str) -> dict | None:
    """索引行结构化(单一真相源:与 find_refs 共用 _REF_RE + 分段口径)。
    命中返回 {id, style, space, file, note, source, used};不命中返回 None。
    风格/空间按逗号拆成列表;找不到的段返回空串/空列表。"""
    m = _REF_RE.match(line)
    if not m:
        return None
    head = line.split(_SEG_SEP, 1)[0]                 # "- [rN] 风格,…|空间,…"
    tag_part = head.split("] ", 1)[1] if "] " in head else ""
    styles = _split_tags(tag_part.split("|")[0]) if "|" in tag_part else []
    spaces = _split_tags(tag_part.split("|")[1]) if "|" in tag_part else []
    seg = _used_segment(line)
    return {
        "id": f"r{m.group('num')}",
        "style": styles,
        "space": spaces,
        "file": _prefixed_segment(line, "文件:"),
        "note": _prefixed_segment(line, "备注:"),
        "source": _prefixed_segment(line, "来源:"),
        "used": seg[1] if seg else [],
    }


def list_project_refs(project: str, ds_root: str = DEFAULT_DS_ROOT) -> list[dict]:
    """某项目用到的参考图(结构化)。复用 find_refs 的过滤 + parse_ref_line 的解析,
    不另造第二套正则。索引缺失 → 空列表。"""
    hits = find_refs(project=project, ds_root=ds_root).get("hits", [])
    out = []
    for ln in hits:
        parsed = parse_ref_line(ln)
        if parsed is not None:
            out.append(parsed)
    return out


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
    # M3(07-13 盲评):存在性检查走 realpath+within,不给 `../` 逃逸。裸 join 时
    # `../index` 会命中 ds_root/index.md(PKB 里真存在)并被收进"用于:"段。
    pbase = os.path.realpath(os.path.join(ds_root, "projects"))
    ptarget = os.path.realpath(os.path.join(pbase, f"{project}.md"))
    if (not project or not ds_common.within(pbase, ptarget)
            or not os.path.isfile(ptarget)):
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


# ── 工具 4 update_ref ───────────────────────────────────────────────────────
def update_ref(ref_id: str, style: str | None = None, space: str | None = None,
               note: str | None = None, ds_root: str = DEFAULT_DS_ROOT,
               today: str | None = None) -> dict:
    """就地改一条已有索引的标签/备注(track opendesign-stage-history §8)。

    只重写头段(`- [rN] 风格|空间`)与 `备注:` 段;`来源:`/`文件:`/`用于:` 三段
    逐字节不变(分段重组,不做整行正则替换)。style/space/note 三者缺省=不动;
    style/space 给了就必须逐项过词表(不自动建词,建词走 add_style);note 给了
    空串即清空(与"不传=不动"区分开)。"""
    today = ds_common.today_str(today)
    # 不 strip:"r1 "(尾随空白)必须被拒,不许被悄悄折成合法 id(与外层 ds_web
    # 键类型闸的字面值一一对应,同类值经不同调用路径进来结果要一致)。
    m = re.fullmatch(r"r(\d+)", ref_id or "")
    if not m:
        return {"error": "ref_not_found"}
    if style is None and space is None and note is None:
        return {"error": "no_fields"}
    num = m.group(1)

    new_styles = None
    if style is not None:
        styles_vocab = _load_styles(ds_root)
        new_styles = _split_tags(style)
        if not new_styles or any(s not in styles_vocab for s in new_styles):
            return {"error": "style_unknown", "vocab": styles_vocab}

    new_spaces = None
    if space is not None:
        new_spaces = _split_tags(space)
        if not new_spaces or any(s not in SPACES for s in new_spaces):
            return {"error": "space_unknown", "vocab": list(SPACES)}

    # 备注允许清空(空串)但不许拆段:折行 + 禁竖线(与 add_ref 同一消毒口径)
    new_note = ds_common.sanitize_field(note, ban_pipe=True) if note is not None else None

    path = _index_path(ds_root)
    if not os.path.exists(path):  # 读不到索引不许顺手建一个(与 link_ref 同口径)
        return {"error": "ref_not_found"}

    line_re = re.compile(rf"^- \[r{num}\]\s")  # 整体锚定,防 r2 误伤 r12
    with ds_common.locked_rw(path) as box:
        lines = box["lines"]
        idx = [i for i, ln in enumerate(lines) if line_re.match(ln)]
        if len(idx) != 1:
            box["write"] = False
            return {"error": "ref_not_found" if not idx else "ambiguous_ref"}
        i = idx[0]
        segs = lines[i].split(_SEG_SEP)
        # 畸形行(缺 `备注:` 段)不猜不补:段数不对/末段不是备注即拒
        if len(segs) != 5 or not segs[4].startswith("备注:"):
            box["write"] = False
            return {"error": "malformed_entry"}
        head_prefix, _, tag_part = segs[0].partition("] ")
        head_prefix += "] "
        cur_styles = _split_tags(tag_part.split("|")[0]) if "|" in tag_part else []
        cur_spaces = _split_tags(tag_part.split("|")[1]) if "|" in tag_part else []
        final_styles = new_styles if new_styles is not None else cur_styles
        final_spaces = new_spaces if new_spaces is not None else cur_spaces
        segs[0] = f"{head_prefix}{','.join(final_styles)}|{','.join(final_spaces)}"
        if new_note is not None:
            segs[4] = f"备注:{new_note}"
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

    @server.tool()
    def update_ref_tool(ref_id: str, style: str = "", space: str = "",
                        note: str | None = None) -> dict:
        """就地改一条已登记参考图(r<n>)的风格/空间/备注。三者都不传则报 no_fields
        (不接受只 bump 页脚的假写);style/space 给了必须在词表内(可逗号分隔多值,
        不自动建词);note 传空串会清空备注。没点名的字段(含来源/文件/用于)不动。"""
        return update_ref(ref_id, style=style or None, space=space or None,
                          note=note, ds_root=ds_root)

    return server


def _run_mcp() -> None:
    _build_server(os.environ.get("DS_ROOT", DEFAULT_DS_ROOT)).run()


if __name__ == "__main__":
    _run_mcp()
