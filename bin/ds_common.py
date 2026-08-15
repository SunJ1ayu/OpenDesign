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

# T4b 批次行 `- C{起}-C{止} {日期} {标题}` 的唯一定义 —— 读侧(ds_todo.collect)与
# 写侧(ds_tools._upsert_batch_line)共用这一份。本项目自己立过"同一个命中不设第二个
# 正则,双正则会漂移"的规矩(见 ds_todo 顶部),批次行不破例。
# 行首是 `- C` 而非 `- [状态]`,所以变更行正则永远命中不了它(反之亦然)。
BATCH_LINE_RE = re.compile(
    r"^- C(?P<from>\d+)-C(?P<to>\d+) (?P<date>\d{4}-\d{2}-\d{2}) (?P<title>.*)$")

# 变更行尾截止日 token(track opendesign-todo-duedate):行尾锚定,正文中间的
# ⏳日期 不误伤;读写两侧(ds_todo.parse_change / ds_tools.set_due_date)共用本 helper,
# 消漂移。
DUE_SUFFIX_RE = re.compile(r"\s*⏳(\d{4}-\d{2}-\d{2})\s*$")

DATA_ROOT_ENV = "DS_DATA_ROOT"


class DataRootError(Exception):
    """数据根不可用。"""


# 装出来的形态才有的东西(启动器 exe 与包内 python 都在 ds/ 的**同级**)。
# 用它来判"上一级到底是不是安装目录"。
_INSTALL_MARKERS = ("OpenDesign.exe", os.path.join("python", "pythonw.exe"))


def _deletable_roots(ds_root: str) -> list[str]:
    """卸载/更新会整棵删掉的地方 —— 业主的东西一样都不许落在这里面。

    - `ds_root` 本身:更新时整棵替换,永远危险。
    - 它的上一级:**只在装出来的形态下**才是安装目录($INSTDIR 底下还有 python\\ 和
      启动器 exe)。开发仓 / 考卷台架里上一级只是个无辜目录,拦它就是误报 ——
      而 2026-08-15 实测,这个误报当场把两条真联跑考卷打红,并且把我引向了
      一个根本没发生的"实现写错了"。**误报和假绿一样坏。**
    """
    real = os.path.realpath(ds_root)
    roots = [real]
    parent = os.path.dirname(real)
    if parent and parent != real and any(
            os.path.exists(os.path.join(parent, m)) for m in _INSTALL_MARKERS):
        roots.append(parent)
    return roots


def data_root(ds_root: str) -> str:
    """返回业主数据根。

    环境变量缺席时保持旧行为;显式配置错误时 fail closed,
    绝不回退到安装目录。
    """
    if DATA_ROOT_ENV not in os.environ:
        return ds_root

    configured = os.environ[DATA_ROOT_ENV]
    if configured == "":
        raise DataRootError(f"{DATA_ROOT_ENV} 已设置但是空串")

    try:
        resolved = os.path.realpath(configured)
        # 无效路径在创建前先拒绝,连空目录也不留在会被删掉的地方。
        for danger in _deletable_roots(ds_root):
            if within(os.path.normcase(danger), os.path.normcase(resolved)):
                raise DataRootError(f"数据根不能放在会被卸载删掉的地方: {resolved}")
        os.makedirs(resolved, exist_ok=True)
    except DataRootError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise DataRootError(f"数据根无法创建或访问: {configured}: {exc}") from exc

    if not os.path.isdir(resolved):
        raise DataRootError(f"数据根不是目录: {resolved}")
    return resolved


_LEGACY_DATA_DIRS = ("projects", "clients", "refs", "organize")
_LEGACY_DATA_FILES = ("index.md", "refs-index.md", "refs-vocab.md")
_LEGACY_CONFIG_ENTRIES = (
    "workspace.json",
    "workspace.json.lock",
    "workspace.json.bak",
    "consent.json",
    "pending.lock",
    "pending",
    "taxonomy.json",
)


def _move_legacy_entry(source: str, target: str, relative: str, report: dict) -> None:
    """同名不覆盖的同卷递归搬运。"""
    rel = relative.replace(os.sep, "/")
    if os.path.isdir(source) and not os.path.islink(source):
        if os.path.lexists(target) and (not os.path.isdir(target)
                                           or os.path.islink(target)):
            report["skipped"].append(rel)
            return
        try:
            os.makedirs(target, exist_ok=True)
            names = sorted(os.listdir(source))
        except OSError as exc:
            report["failed"].append({"path": rel, "error": str(exc)})
            return
        if not names:
            report["moved"].append(rel + "/")
        for name in names:
            _move_legacy_entry(
                os.path.join(source, name),
                os.path.join(target, name),
                os.path.join(relative, name),
                report,
            )
        try:
            os.rmdir(source)  # 只删已搬空的目录;有跳过/失败项时会自然保留。
        except OSError:
            pass
        return

    if os.path.lexists(target):
        report["skipped"].append(rel)
        return
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        os.rename(source, target)  # 两边都在 %LOCALAPPDATA%,同卷直接搬。
        report["moved"].append(rel)
    except OSError as exc:
        report["failed"].append({"path": rel, "error": str(exc)})


# 装什么样就该一直是什么样的那些 —— 它们**不是**"没认识的数据",报出来只会淹掉真货。
# (闸③ 实测:不排除的话,真安装包里 unknown 是几千条 bin/*.py 与 web/dist/**,
#  而 canary 就在里面。一份谁都不会读的报告不算报告。)
_CODE_TOP = ("bin", "web", "assets", "workspace", "installer", "docs", "schema", "skills")
_CODE_FILES = ("版本号.txt", "README.md")
_CODE_CONFIG_PREFIX = ("nanobot.config", "taxonomy.default.json", "workspace.example.json")


def _unknown_legacy_entries(legacy_root: str) -> list[str]:
    """列出迁移清单未覆盖的文件,避免未来新数据种类被静默遗忘。

    **只报数据形状的东西**:代码那一份按上面的名单排除掉,否则 canary 会被噪音淹掉。
    """
    known_top = set(_LEGACY_DATA_DIRS) | set(_LEGACY_DATA_FILES) \
        | set(_CODE_TOP) | set(_CODE_FILES)
    known_config = set(_LEGACY_CONFIG_ENTRIES)
    unknown: list[str] = []
    try:
        top_names = sorted(os.listdir(legacy_root))
    except OSError as exc:
        return [f"<scan failed: {exc}>"]

    for top in top_names:
        if top in known_top:
            continue
        top_path = os.path.join(legacy_root, top)
        if top == "config" and os.path.isdir(top_path):
            for base, dirs, files in os.walk(top_path):
                rel_base = os.path.relpath(base, top_path)
                if rel_base == ".":
                    dirs[:] = [d for d in dirs if d not in known_config]
                    files = [f for f in files if f not in known_config
                             and not f.startswith(_CODE_CONFIG_PREFIX)]
                for name in files:
                    rel = os.path.relpath(os.path.join(base, name), legacy_root)
                    unknown.append(rel.replace(os.sep, "/"))
            continue
        if os.path.isdir(top_path) and not os.path.islink(top_path):
            found = False
            for base, _dirs, files in os.walk(top_path):
                for name in files:
                    found = True
                    rel = os.path.relpath(os.path.join(base, name), legacy_root)
                    unknown.append(rel.replace(os.sep, "/"))
            if not found:
                unknown.append(top.replace(os.sep, "/") + "/")
        else:
            unknown.append(top.replace(os.sep, "/"))
    return unknown


def migrate_legacy_data(ds_root: str) -> dict:
    """当数据根已外置时,把 ds_root 下的遗留业主数据幂等搬过去。"""
    target_root = data_root(ds_root)
    report = {
        "data_root": target_root,
        "moved": [],
        "skipped": [],
        "unknown": [],
        "failed": [],
    }
    legacy_root = os.path.realpath(ds_root)
    if os.path.realpath(target_root) == legacy_root:
        return report

    for name in _LEGACY_DATA_DIRS + _LEGACY_DATA_FILES:
        source = os.path.join(legacy_root, name)
        if os.path.lexists(source):
            _move_legacy_entry(source, os.path.join(target_root, name), name, report)

    for name in _LEGACY_CONFIG_ENTRIES:
        source = os.path.join(legacy_root, "config", name)
        if os.path.lexists(source):
            _move_legacy_entry(
                source,
                os.path.join(target_root, "config", name),
                os.path.join("config", name),
                report,
            )

    report["unknown"] = _unknown_legacy_entries(legacy_root)
    return report


def split_due(text: str) -> tuple[str, str | None]:
    """把行尾 ⏳YYYY-MM-DD 从正文切出。无则原文返回、due=None。"""
    m = DUE_SUFFIX_RE.search(text)
    if not m:
        return text, None
    return text[:m.start()], m.group(1)


def format_due_suffix(due: str | None) -> str:
    return f" ⏳{due}" if due else ""


def section_bounds(lines: list[str], header: str) -> tuple[int, int] | None:
    """指定二级段的 (标题行下标, 段尾下标)。段尾=其后第一条 `## `/`---` 或文件末。
    段缺失返回 None。

    单一真相源:`ds_tools`(阶段历史/变更历史写侧)与 `ds_todo`(变更历史读侧)共用。
    track opendesign-note-source 把读模型搬进 ds_todo 时,这个通用扫描器一度在两个
    模块里各留了一份 —— 一件事两处定义,正是这一单要消灭的形状,所以收到这儿。
    """
    hidx = next((i for i, l in enumerate(lines) if l.startswith(header)), None)
    if hidx is None:
        return None
    end = next((j for j in range(hidx + 1, len(lines))
                if lines[j].startswith("## ") or lines[j].startswith("---")), len(lines))
    return hidx, end


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
