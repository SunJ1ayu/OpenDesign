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

OPEN_RE = re.compile(r"^- \[(待确认|进行中)\]")
LASTUPD_RE = ds_common.LASTUPD_DATE_RE  # 行首锚定:沟通日志句中的"最后更新"不再误认
# env DS_ROOT 缺失时基于 __file__ 推导(bin/ 的上一级):Linux/Windows 通用,不硬编码 /root
DEFAULT_DS_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def _today() -> date:
    t = os.environ.get("DS_TODAY")
    return date.fromisoformat(t) if t else date.today()


def render(root: str, stale_days: int = 7, today: date | None = None) -> str:
    if today is None:
        today = _today()
    proj = os.path.join(root, "projects")
    files = sorted(f for f in (os.listdir(proj) if os.path.isdir(proj) else [])
                   if f.endswith(".md"))

    out = ["== 未关闭事项(待确认 / 进行中) =="]
    found = False
    texts = {}
    for f in files:
        with open(os.path.join(proj, f), encoding="utf-8") as fh:
            texts[f] = fh.read()
        hits = [(i, ln) for i, ln in enumerate(texts[f].split("\n"), 1) if OPEN_RE.match(ln)]
        if hits:
            out.append(f"▸ {f[:-3]}")
            out.extend(f"    {i}:{ln}" for i, ln in hits)
            found = True
    if not found:
        out.append("  (无)")

    out.append("")
    out.append(f"== 超过 {stale_days} 天未更新的项目 ==")
    sfound = False
    for f in files:
        dates = LASTUPD_RE.findall(texts[f])
        if not dates:
            continue
        try:
            last = date.fromisoformat(dates[-1])
        except ValueError:
            continue
        age = (today - last).days
        if age >= stale_days:
            out.append(f"▸ {f[:-3]} — {age}天未更新 (最后 {dates[-1]})")
            sfound = True
    if not sfound:
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
