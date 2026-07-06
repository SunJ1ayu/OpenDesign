#!/usr/bin/env python3
"""ds_todo — 主动提醒核心:扫所有项目的未关闭变更 + 超期未更新项目(跨平台)。

CLI 入口是同目录 `ds-todo`(薄 wrapper);MCP 侧 ds_tools.list_todos 直接 import 本模块
(不走 subprocess,避免 Windows 管道编码问题)。
环境变量:DS_ROOT 定根目录;DS_TODAY(YYYY-MM-DD)冻结"今天",测试/复现用。
依赖 SCHEMA 的两处格式:变更行 `- [状态] ...`、文件末 `最后更新: YYYY-MM-DD`
"""
import os
import re
import sys
from datetime import date

import ds_common  # 页脚锚定语义的唯一定义(与写侧 bump_last_updated 同源)

# 未关闭变更行的唯一闸门 + 结构化提取(SCHEMA 变更行 `- [状态] C<n> 日期 内容`):
# 单正则,不设第二个"命中"正则 —— 双正则会漂移(panel 7-06 GLM 指出的缺陷类)。
# C/日期残缺时各组为 None;\b 防 "C5面板" 这类无空格粘连被误拆。
FIELDS_RE = re.compile(
    r"^- \[(待确认|进行中)\](?:\s+C(\d+)\b)?(?:\s+(\d{4}-\d{2}-\d{2}))?\s*(.*)$")
LASTUPD_RE = ds_common.LASTUPD_DATE_RE  # 行首锚定:沟通日志句中的"最后更新"不再误认
# env DS_ROOT 缺失时基于 __file__ 推导(bin/ 的上一级):Linux/Windows 通用,不硬编码 /root
DEFAULT_DS_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def _today() -> date:
    t = os.environ.get("DS_TODAY")
    return date.fromisoformat(t) if t else date.today()


def collect(root: str, stale_days: int = 7, today: date | None = None) -> dict:
    """结构化核心(唯一真相源):render 与 ds_web /api/todos 都吃这个。
    返回 {"today", "stale_days", "open": [...], "stale": [...]};open 条目含
    project/line/status/cnum/date/text/raw,残缺行 cnum/date 为 None。"""
    if today is None:
        today = _today()
    proj = os.path.join(root, "projects")
    files = sorted(f for f in (os.listdir(proj) if os.path.isdir(proj) else [])
                   if f.endswith(".md"))

    open_items = []
    stale_items = []
    for f in files:
        with open(os.path.join(proj, f), encoding="utf-8") as fh:
            text = fh.read()
        name = f[:-3]
        for i, ln in enumerate(text.split("\n"), 1):
            m = FIELDS_RE.match(ln)
            if not m:
                continue
            open_items.append({
                "project": name, "line": i, "raw": ln,
                "status": m.group(1),
                "cnum": int(m.group(2)) if m.group(2) else None,
                "date": m.group(3),
                "text": m.group(4),
            })
        dates = LASTUPD_RE.findall(text)
        if not dates:
            continue
        try:
            last = date.fromisoformat(dates[-1])
        except ValueError:
            continue
        age = (today - last).days
        if age >= stale_days:
            stale_items.append({"project": name, "days": age, "last": dates[-1]})

    return {"today": today.isoformat(), "stale_days": stale_days,
            "open": open_items, "stale": stale_items}


def render(root: str, stale_days: int = 7, today: date | None = None) -> str:
    """collect 的纯格式化壳 —— golden 文本逐字节不变(特征化测试锁定)。"""
    data = collect(root, stale_days, today)

    out = ["== 未关闭事项(待确认 / 进行中) =="]
    cur = None
    for it in data["open"]:
        if it["project"] != cur:
            out.append(f"▸ {it['project']}")
            cur = it["project"]
        out.append(f"    {it['line']}:{it['raw']}")
    if not data["open"]:
        out.append("  (无)")

    out.append("")
    out.append(f"== 超过 {data['stale_days']} 天未更新的项目 ==")
    for s in data["stale"]:
        out.append(f"▸ {s['project']} — {s['days']}天未更新 (最后 {s['last']})")
    if not data["stale"]:
        out.append("  (无)")
    return "\n".join(out) + "\n"


def main(argv: list | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    root = os.environ.get("DS_ROOT", DEFAULT_DS_ROOT)
    stale_days = int(argv[0]) if argv else 7
    # Windows 控制台(cp936)编码不了 "▸" 会 UnicodeEncodeError:降级成 ? 而不是崩
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    sys.stdout.write(render(root, stale_days))
    return 0


if __name__ == "__main__":
    sys.exit(main())
