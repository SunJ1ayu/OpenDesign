#!/usr/bin/env python3
"""ds_taxonomy —— 类目规则表的加载与后缀→类目建议(track opendesign-structure-debt)。

从 ds_intake 搬出:实测 4 个模块都在用它(ds_intake / ds_adopt / ds_web / ds_workspace),
它是一张公共配置表,却寄居在"收件箱"模块里 —— 这既是错位,也是
ds_intake ⇄ ds_workspace 那个循环依赖的成因。
"""
from __future__ import annotations

import json
import os
import posixpath

import ds_common

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DEFAULT_TAXONOMY_PATH = os.path.join(REPO_ROOT, "config", "taxonomy.default.json")
USER_TAXONOMY_REL = os.path.join("config", "taxonomy.json")


# ── 规则表 ────────────────────────────────────────────────────────────────
def _safe_rel_dir(p: str) -> bool:
    """规则表里的目录值必须是相对路径且无 .. 段(工作区内寻址;GLM panel 建议的
    早期拒绝——下游 stage_plan 的 realpath+within 仍是权威闸,这里只是让坏配置
    在加载时就整体降级,不用等到奇怪的运行期报错)。"""
    if os.path.isabs(p) or (len(p) >= 2 and p[1] == ":"):  # C: 盘符=Windows 绝对
        return False
    return all(seg not in ("", ".", "..") for seg in p.replace("\\", "/").split("/"))


def _valid_taxonomy(raw) -> bool:
    if not isinstance(raw, dict):
        return False
    cats = raw.get("categories")
    # inboxDirs 及 adoption 附加的 archiveDirs/sharedDirs 同款:可选,但给了就必须是
    # 非空安全相对目录名列表(结构识别的候选名单;坏配置整体降级不静默猜)。
    for dirs_key in ("inboxDirs", "archiveDirs", "sharedDirs"):
        val = raw.get(dirs_key)
        if val is not None and (not isinstance(val, list)
                                or not all(isinstance(i, str) and i
                                           and _safe_rel_dir(i) for i in val)):
            return False
    if cats is not None:
        if not isinstance(cats, list):
            return False
        for c in cats:
            if not isinstance(c, dict):
                return False
            if not all(isinstance(c.get(k), str) and c.get(k)
                       for k in ("id", "scope", "dir", "mode")):
                return False
            if not _safe_rel_dir(c["dir"]):
                return False
            if c["scope"] not in ("project", "workspace"):
                return False
            if c["mode"] not in ("auto", "suggest"):
                return False
            exts = c.get("extensions")
            if (not isinstance(exts, list)
                    or not all(isinstance(e, str) and e.startswith(".")
                               for e in exts)):
                return False
    return True


def load_taxonomy(ds_root: str):
    """默认表 + 用户覆盖(顶层键整键替换)。默认表坏/缺 或 用户表存在但坏
    → None(功能整体降级,调用方按配置故障处理)。"""
    try:
        with open(DEFAULT_TAXONOMY_PATH, encoding="utf-8") as fh:
            tax = json.load(fh)
    except (OSError, ValueError):
        return None
    if not _valid_taxonomy(tax) or "inboxDirs" not in tax or "categories" not in tax:
        return None
    user_path = os.path.join(ds_common.data_root(ds_root), USER_TAXONOMY_REL)
    if os.path.exists(user_path):
        try:
            with open(user_path, encoding="utf-8") as fh:
                overlay = json.load(fh)
        except (OSError, ValueError):
            return None
        if not _valid_taxonomy(overlay):
            return None
        for key in ("inboxDirs", "categories", "archiveDirs", "sharedDirs"):
            if key in overlay:
                tax[key] = overlay[key]
    return tax


def suggest_category(name: str, taxonomy) -> dict | None:
    """扩展名(大小写不敏感)→ 类目 {"id","scope","dir","mode"};未知 → None。"""
    ext = posixpath.splitext(name)[1].lower()
    if not ext or taxonomy is None:
        return None
    for c in taxonomy["categories"]:
        if ext in (e.lower() for e in c["extensions"]):
            return {"id": c["id"], "scope": c["scope"],
                    "dir": c["dir"], "mode": c["mode"]}
    return None
