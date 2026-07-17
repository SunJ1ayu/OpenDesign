#!/usr/bin/env python3
"""ds_intake —— 收件箱认领核心(track opendesign-intake)。

职责:把「00-收件箱里丢了什么」变成确定性的归类建议,把「文件→项目+类目」的
指派变成 ds_organize 的 staged plan。本模块自己不发明任何执行路径:
校验/冲突检查/快照/approve 硬闸/审计全部复用 ds_organize;工作区解析全部
复用 ds_workspace。

契约:
- 规则表 = <仓根>/config/taxonomy.default.json(进仓,永远存在)+
  <ds_root>/config/taxonomy.json 可选覆盖(顶层键整键替换)。坏用户配置 =
  功能整体降级(None),不静默猜(load_config 同款严格)。
- 建议是确定性的:扩展名→类目;项目 = 文件名对项目夹名 token 唯一命中才建议,
  歧义留空(误绑窗口=零)。mode=suggest 的类目(CAD/SU/MAX/PSD)只给建议,
  引擎层面永不自动动 —— v1 里所有移动本就要人工确认,该标志是给 agent/UI 的
  被引用风险提示 + 未来自动化的闸。
- stage 零改动;真正移动只发生在 approve(人)+ apply(快照复验)之后。
"""
from __future__ import annotations

import json
import os
import posixpath
import stat as stat_mod

import ds_organize
import ds_workspace

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DEFAULT_TAXONOMY_PATH = os.path.join(REPO_ROOT, "config", "taxonomy.default.json")
USER_TAXONOMY_REL = os.path.join("config", "taxonomy.json")
MAX_INBOX_ENTRIES = 500  # 收件箱一屏拿不下 500 个也没意义,诚实置 truncated

_SEG_RE = ds_workspace.PROJECT_NAME_RE  # 单段名闸,单一真相源


# ── 规则表 ────────────────────────────────────────────────────────────────
def _valid_taxonomy(raw) -> bool:
    if not isinstance(raw, dict):
        return False
    inbox = raw.get("inboxDirs")
    cats = raw.get("categories")
    if inbox is not None and (not isinstance(inbox, list)
                              or not all(isinstance(i, str) and i for i in inbox)):
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
    user_path = os.path.join(ds_root, USER_TAXONOMY_REL)
    if os.path.exists(user_path):
        try:
            with open(user_path, encoding="utf-8") as fh:
                overlay = json.load(fh)
        except (OSError, ValueError):
            return None
        if not _valid_taxonomy(overlay):
            return None
        for key in ("inboxDirs", "categories"):
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


# ── 项目建议(确定性 token 匹配) ─────────────────────────────────────────
def _project_tokens(folder_name: str) -> list[str]:
    """项目夹名(`日期 地点 楼盘 楼栋#户号`)→ 可匹配 token:空格分段,
    去掉纯数字段(日期/编号,撞文件名里的数字太容易=误绑),长度≥2。"""
    return [t for t in folder_name.split()
            if len(t) >= 2 and not t.replace("#", "").isdigit()]


def suggest_project(name: str, folders) -> str | None:
    """文件名含某项目的任一 token → 该项目命中;恰好唯一项目命中才建议。
    folders = ds_workspace.project_folders(cfg) 的 [(key, path)]。"""
    hit_keys = []
    for key, path in folders:
        tokens = _project_tokens(os.path.basename(path))
        if any(t in name for t in tokens):
            hit_keys.append(key)
    return hit_keys[0] if len(hit_keys) == 1 else None


# ── 收件箱清单 ────────────────────────────────────────────────────────────
def _find_inbox(cfg, taxonomy):
    """workspace root 下按候选名找收件箱夹 →(名字, realpath)| None。"""
    for cand in taxonomy["inboxDirs"]:
        p = os.path.join(cfg["root"], cand)
        if os.path.isdir(p) and not os.path.islink(p):
            return cand, os.path.realpath(p)
    return None


def list_inbox(ds_root: str) -> dict:
    cfg = ds_workspace.load_config(ds_root)
    if cfg is None:
        return {"error": "workspace_not_configured"}
    taxonomy = load_taxonomy(ds_root)
    if taxonomy is None:
        return {"error": "taxonomy_bad"}
    found = _find_inbox(cfg, taxonomy)
    if found is None:
        return {"error": "inbox_not_found", "candidates": taxonomy["inboxDirs"]}
    inbox_name, inbox_real = found

    folders = ds_workspace.project_folders(cfg)
    entries = []
    truncated = False
    try:
        items = sorted(os.scandir(inbox_real), key=lambda e: e.name)
    except OSError:
        return {"error": "inbox_unreadable"}
    for ent in items:
        if ent.name.startswith(".") or not _SEG_RE.match(ent.name):
            continue
        try:
            st = ent.stat(follow_symlinks=False)
        except OSError:
            continue
        if stat_mod.S_ISDIR(st.st_mode):
            typ = "dir"
        elif stat_mod.S_ISREG(st.st_mode):
            typ = "file"
        else:
            continue  # symlink/特殊文件不认领
        cat = suggest_category(ent.name, taxonomy) if typ == "file" else None
        proj = suggest_project(ent.name, folders) if typ == "file" else None
        entries.append({"name": ent.name, "type": typ, "size": st.st_size,
                        "mtime": int(st.st_mtime), "category": cat,
                        "project": proj})
        if len(entries) >= MAX_INBOX_ENTRIES:
            truncated = True
            break
    return {"ok": True, "inbox": inbox_name, "entries": entries,
            "truncated": truncated}


# ── 指派 → staged plan ───────────────────────────────────────────────────
def stage_intake(assignments, allowed_roots, ds_root: str) -> dict:
    """assignments: [{"name": 收件箱内单段名, "project": key|None, "category": id}]
    → 构造 move operations → ds_organize.stage_plan(零改动,返回 plan_id)。
    校验顺序:配置 → 每条指派(名字闸/在箱内/类目存在/项目按 scope)→ stage。"""
    cfg = ds_workspace.load_config(ds_root)
    if cfg is None:
        return {"error": "workspace_not_configured"}
    taxonomy = load_taxonomy(ds_root)
    if taxonomy is None:
        return {"error": "taxonomy_bad"}
    found = _find_inbox(cfg, taxonomy)
    if found is None:
        return {"error": "inbox_not_found", "candidates": taxonomy["inboxDirs"]}
    inbox_name, inbox_real = found
    if not isinstance(assignments, list) or not assignments:
        return {"error": "empty_plan"}

    cats = {c["id"]: c for c in taxonomy["categories"]}
    operations = []
    for i, a in enumerate(assignments):
        if not isinstance(a, dict):
            return {"error": "bad_assignment", "index": i}
        name = a.get("name")
        if (not isinstance(name, str) or not name
                or "/" in name or "\\" in name or name in (".", "..")
                or not _SEG_RE.match(name)):
            return {"error": "bad_name", "index": i}
        if not os.path.lexists(os.path.join(inbox_real, name)):
            return {"error": "file_not_in_inbox", "index": i, "name": name}
        cat = cats.get(a.get("category"))
        if cat is None:
            return {"error": "unknown_category", "index": i}
        if cat["scope"] == "project":
            key = a.get("project")
            if not isinstance(key, str) or not key:
                return {"error": "project_required", "index": i, "name": name}
            proj_dir = ds_workspace.project_dir(cfg, key)
            if proj_dir is None:
                return {"error": "project_not_found", "index": i, "project": key}
            dst_base = os.path.relpath(proj_dir, cfg["root"])
            dst_rel = os.path.join(dst_base, cat["dir"], name)
        else:  # workspace 级类目(如参考图库):项目字段忽略
            dst_rel = os.path.join(cat["dir"], name)
        operations.append({"op": "move",
                           "src": os.path.join(inbox_name, name),
                           "dst": dst_rel})

    return ds_organize.stage_plan(cfg["root"], operations, allowed_roots,
                                  ds_root=ds_root)
