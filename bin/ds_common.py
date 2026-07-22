#!/usr/bin/env python3
"""ds_common — 三个工具层共享的最小公共件。

只收"改一处必须处处同步"的东西,别往这里堆:
  - within():全项目唯一的防逃逸谓词(realpath containment)。
  - sanitize_field():字段消毒 —— 单行契约的物理保证。账本/索引都是"一行一条"
    的追加式文本,字段里的换行等于伪造整行(状态词表/锚定/页脚全被打穿),
    必须在写入口折叠掉;竖线是 refs 索引的字段分隔符,同理可选禁掉。
  - bump_last_updated() / LASTUPD_DATE_RE:页脚锚定语义的唯一定义 ——
    **行首锚定 + 取最后一处(页脚)**,写侧读侧共用,防两侧分叉。
  - locked_rw():排他锁读改写;错误路径置 box["write"]=False 则完全不碰文件。
"""
from __future__ import annotations

import os
import re
from contextlib import contextmanager
from datetime import date

import ds_lock  # 跨平台排他锁,同目录模块

_LASTUPD_LINE_RE = re.compile(r"^最后更新[:：]")
# 读侧(ds_todo)用:行首锚定,提取日期
LASTUPD_DATE_RE = re.compile(r"^最后更新[:：]\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)

# 变更行尾截止日 token(track opendesign-todo-duedate):行尾锚定,正文中间的
# ⏳日期 不误伤;读写两侧(ds_todo.parse_change / ds_tools.set_due_date)共用本 helper,
# 消漂移。
DUE_SUFFIX_RE = re.compile(r"\s*⏳(\d{4}-\d{2}-\d{2})\s*$")


def split_due(text: str) -> tuple[str, str | None]:
    """把行尾 ⏳YYYY-MM-DD 从正文切出。无则原文返回、due=None。"""
    m = DUE_SUFFIX_RE.search(text)
    if not m:
        return text, None
    return text[:m.start()], m.group(1)


def format_due_suffix(due: str | None) -> str:
    return f" ⏳{due}" if due else ""


def within(base: str, target: str) -> bool:
    """target 是否等于 base 或落在 base 之下。两参都必须已经 realpath。"""
    return target == base or target.startswith(base + os.sep)


def sanitize_field(value: str, ban_pipe: bool = False) -> str:
    """折叠成单行:换行/回车 → 空格;ban_pipe 时竖线 → /(不可注入字段分隔符)。"""
    s = re.sub(r"[\r\n]+", " ", value or "").strip()
    if ban_pipe:
        s = s.replace("|", "/")
    return s


def today_str(today: str | None) -> str:
    return today or date.today().isoformat()


def bump_last_updated(lines: list[str], today: str) -> None:
    """更新页脚:行首锚定、最后一处。无则不硬造(真实文件恒有;保持不删行原则)。"""
    for i in range(len(lines) - 1, -1, -1):
        if _LASTUPD_LINE_RE.match(lines[i]):
            lines[i] = f"最后更新: {today}"
            return


@contextmanager
def locked_rw(path: str):
    """以排他锁打开文件做读改写。yield box:改 box["lines"];
    错误路径先置 box["write"] = False 再 return,文件将原封不动(mtime 也不碰)。"""
    with open(path, "r+", encoding="utf-8") as fh, ds_lock.exclusive(fh):
        fh.seek(0)
        box = {"lines": fh.read().split("\n"), "write": True}
        yield box
        if box["write"]:
            fh.seek(0)
            fh.truncate()
            fh.write("\n".join(box["lines"]))
