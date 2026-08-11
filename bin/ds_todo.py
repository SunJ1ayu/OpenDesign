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

# 变更行的唯一闸门 + 结构化提取(SCHEMA 变更行 `- [状态] C<n> 日期 内容`):
# 单正则,不设第二个"命中"正则 —— 双正则会漂移(panel 7-06 GLM 指出的缺陷类)。
# 五状态全覆盖(ds_web /api/.../changes 要全量减已删除,ds_todo 只取未办结 → 读侧
# 过滤,同一正则单一真相源);C/日期残缺时各组为 None;\b 防 "C5面板" 无空格粘连误拆。
# `已删除`(track opendesign-owner-review-0808)是 delete_change 专用的第五态,不在
# ds_tools.STATUSES 里(那是词表内四态互转用的)——**这里必须认得它**,不认得就等于
# 这一行对全仓所有扫描 CHANGE_RE 的代码隐形(不是"被过滤",是"解析直接失败");
# design.md 明确要求"可见但被过滤",过滤动作在读侧各自做(OPEN_STATUS 天然不含它;
# ds_web._changes 显式排除)。
STATUS_WORDS = ("待确认", "进行中", "已完成", "已关闭", "已删除")
OPEN_STATUS = ("待确认", "进行中")  # 未办结 = ds_todo 主动提醒的范围
CHANGE_RE = re.compile(
    r"^- \[(待确认|进行中|已完成|已关闭|已删除)\]"
    r"(?:\s+C(\d+)\b)?(?:\s+(\d{4}-\d{2}-\d{2}))?\s*"
    r"(?:【([^【】\s][^【】]{0,15})】\s*)?(.*)$")  # 可选【空间】前缀(track p4):1-16字,空/超长落回正文
LASTUPD_RE = ds_common.LASTUPD_DATE_RE  # 行首锚定:沟通日志句中的"最后更新"不再误认
# T4b 批次行:与写侧共用 ds_common 的那一份(不设第二个命中正则)。
# 缺 `[状态]` ⇒ CHANGE_RE 命中不了 ⇒ 批次行永远不会被收成待办。
BATCH_RE = ds_common.BATCH_LINE_RE
HISTORY_HEADER = "## 变更历史"
HISTORY_EDIT_RE = re.compile(r"^- C(\d+) 改于 (\d{4}-\d{2}-\d{2})｜原:(.*)$")
HISTORY_NOTE_RE = re.compile(r"^- C(\d+) 备注[:：](.*)$")


def parse_batches(text: str) -> list[tuple[int, int, str]]:
    """抽出全部批次区间 [(起, 止, 标题)],按文件出现序。坏行只跳过,不拖垮 collect
    (与 M1「一个坏文件不该让端点全灭」同哲学)。标题为空的行视为坏行。"""
    out = []
    for ln in text.split("\n"):
        m = BATCH_RE.match(ln)
        if not m:
            continue
        lo, hi = int(m.group("from")), int(m.group("to"))
        title = m.group("title").strip()
        if title and lo <= hi:
            out.append((lo, hi, title))
    return out


def _batch_of(batches: list[tuple[int, int, str]], cnum: int | None) -> dict | None:
    """cnum 落在哪个批次里。区间重叠(手写坏档案)时**后写的赢** —— 与"最后一次命名
    说了算"一致,且绝不抛。没有 cnum 的残缺行天然无批次。"""
    if cnum is None:
        return None
    hit = None
    for lo, hi, title in batches:
        if lo <= cnum <= hi:
            hit = {"id": f"C{lo}-C{hi}", "title": title}
    return hit


def parse_change(line: str) -> dict | None:
    """变更行结构化(单一真相源):ds_todo.collect 与 ds_web changes 端点都吃它。
    命中返回 {status, cnum, date, space, text, due}(cnum/date/space/due 残缺为 None),
    不命中返回 None。space=内容头部可选【空间】前缀(旧行天然 None,零迁移)。
    due=正文尾部可选 ⏳YYYY-MM-DD 截止日(ds_common.split_due 切出,text 不含 ⏳)。"""
    m = CHANGE_RE.match(line)
    if not m:
        return None
    text, due = ds_common.split_due(m.group(5))
    return {"status": m.group(1),
            "cnum": int(m.group(2)) if m.group(2) else None,
            "date": m.group(3),
            "space": m.group(4),
            "text": text,
            "due": due}


def history_bounds(lines: list[str]) -> tuple[int, int] | None:
    """`## 变更历史` 段边界(通用扫描器在 ds_common,读写两侧共用同一份)。"""
    return ds_common.section_bounds(lines, HISTORY_HEADER)


def parse_history(text: str) -> dict:
    """解析 `## 变更历史` 段,按 cnum 分桶(读侧单一真相源:ds_web changes 端点吃它)。

    返回 {cnum(int): {"note": str|None, "history": [{"date","old"}, …]}}。只扫历史段内的行
    (遇下一 `## `/`---` 即止 ⇒ 隔离天然);段缺失或无匹配行返回空/缺桶。留痕按出现顺序(=时序)。
    """
    lines = text.split("\n")
    b = history_bounds(lines)
    if b is None:
        return {}
    hidx, end = b
    out: dict[int, dict] = {}
    for ln in lines[hidx + 1:end]:
        m = HISTORY_EDIT_RE.match(ln)
        if m:
            bucket = out.setdefault(int(m.group(1)), {"note": None, "history": []})
            bucket["history"].append({"date": m.group(2), "old": m.group(3)})
            continue
        m = HISTORY_NOTE_RE.match(ln)
        if m:
            bucket = out.setdefault(int(m.group(1)), {"note": None, "history": []})
            bucket["note"] = m.group(2)
    return out


def note_line_re(num: str) -> re.Pattern:
    """该 cnum 的备注行锚(写侧唯一定义,`_upsert_note`/`_delete_note` 共用)。
    `C{num}` 后必须是一个空格 ⇒ 清 C1 不会误伤 C12;全角冒号与读侧
    `HISTORY_NOTE_RE` 同口径(读侧收两种,写侧只写半角)。"""
    return re.compile(rf"^- C{num} 备注[:：]")


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
    errors = []  # M1(07-13 盲评):坏编码/读失败的文件记这里,不拖垮整个 collect
    for f in files:
        try:
            with open(os.path.join(proj, f), encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            errors.append(f)  # 一个坏文件不该让 todos/projects 双端点全灭
            continue
        name = f[:-3]
        batches = parse_batches(text)  # T4b:助手记录时起的名(段不存在 = 空表 = 全 None)
        history = parse_history(text)
        for i, ln in enumerate(text.split("\n"), 1):
            c = parse_change(ln)
            if c is None or c["status"] not in OPEN_STATUS:
                continue  # collect 只收未办结;全量交给 changes 端点
            item = {
                "project": name, "line": i, "raw": ln,
                "status": c["status"],
                "cnum": c["cnum"],
                "date": c["date"],
                "space": c["space"],
                "text": c["text"],
                "due": c["due"],
                "batch": _batch_of(batches, c["cnum"]),
            }
            h = history.get(c["cnum"]) if c["cnum"] is not None else None
            if h and h["note"] is not None:
                item["note"] = h["note"]
            open_items.append(item)
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
            "open": open_items, "stale": stale_items, "errors": errors}


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
