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

import ds_common
import ds_organize
import ds_workspace

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DEFAULT_TAXONOMY_PATH = os.path.join(REPO_ROOT, "config", "taxonomy.default.json")
USER_TAXONOMY_REL = os.path.join("config", "taxonomy.json")
MAX_INBOX_ENTRIES = 500  # 收件箱一屏拿不下 500 个也没意义,诚实置 truncated

_SEG_RE = ds_workspace.PROJECT_NAME_RE  # 单段名闸,单一真相源


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
    user_path = os.path.join(ds_root, USER_TAXONOMY_REL)
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
    """workspace root 下按候选名找收件箱夹 →(名字, realpath)| None。
    候选名来自规则表(用户可覆盖),within 闸拒绝指到工作区外的候选
    (写面本就被 stage_plan 拦,这里把读面/列举也焊死,panel 纵深建议)。"""
    for cand in taxonomy["inboxDirs"]:
        p = os.path.join(cfg["root"], cand)
        if not (os.path.isdir(p) and not os.path.islink(p)):
            continue
        real = os.path.realpath(p)
        if not ds_common.within(cfg["root"], real):
            continue
        return cand, real
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
        src_abs = os.path.join(inbox_real, name)
        if not os.path.lexists(src_abs):
            return {"error": "file_not_in_inbox", "index": i, "name": name}
        # symlink 不认领(与 list_inbox 跳过对称,MiMo panel 抓的不对称):
        # stage_plan 会 realpath 到链接目标,移走的是真身留下悬空链接
        if os.path.islink(src_abs):
            return {"error": "file_not_in_inbox", "index": i, "name": name}
        cat_id = a.get("category")
        if not isinstance(cat_id, str):  # dict/list 会让 dict.get 抛 unhashable
            return {"error": "unknown_category", "index": i}
        cat = cats.get(cat_id)
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


# ── 自动扫描:采纳「确定性建议」自动暂存 ──────────────────────────────────
def stage_inbox_auto(allowed_roots, ds_root: str) -> dict:
    """list_inbox 的建议里,只挑「确定」的自动认领:
    - 目录 → skipped(not_a_file);未知类型(无类目建议)→ skipped(unknown_type);
    - project 级类目但无唯一项目建议 → skipped(ambiguous_project);
    - 其余(workspace 级,或 project 级已有唯一项目)→ 收进 assignments。
    一条都没有 → 不落 plan(plan_id=None,staged=0);否则过 stage_intake 落 plan。"""
    listing = list_inbox(ds_root)
    if not listing.get("ok"):
        return listing

    assignments = []
    skipped = []
    for ent in listing["entries"]:
        name = ent["name"]
        if ent["type"] != "file":
            skipped.append({"name": name, "reason": "not_a_file"})
            continue
        cat = ent["category"]
        if cat is None:
            skipped.append({"name": name, "reason": "unknown_type"})
            continue
        # mode=suggest(CAD/SU/MAX/PSD 被引用类目):xref/贴图/材质链一动就断,引擎永不
        # 自动动(与 ds_adopt.stage_adoption:219 同铁律、taxonomy `mode` 语义同源)——
        # 留 skipped 交人工确认 stage,自动扫描不碰。(四审 subdeepseek/subkimi 抓的漏,
        # 主审 oracle 曾错误编码成自动暂存。)
        if cat["mode"] == "suggest":
            skipped.append({"name": name, "reason": "referenced_type"})
            continue
        project = ent["project"]
        if cat["scope"] == "project" and not project:
            skipped.append({"name": name, "reason": "ambiguous_project"})
            continue
        assignments.append({"name": name, "category": cat["id"], "project": project})

    if not assignments:
        return {"ok": True, "plan_id": None, "staged": 0, "skipped": skipped}

    res = stage_intake(assignments, allowed_roots, ds_root)
    if not res.get("ok"):
        return res
    return {"ok": True, "plan_id": res["plan_id"], "staged": len(assignments),
            "skipped": skipped}
