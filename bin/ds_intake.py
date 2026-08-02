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
import stat as stat_mod
from datetime import datetime

import ds_common
import ds_lock
import ds_organize
import ds_taxonomy
import ds_workspace

MAX_INBOX_ENTRIES = 500  # 收件箱一屏拿不下 500 个也没意义,诚实置 truncated

_SEG_RE = ds_workspace.PROJECT_NAME_RE  # 单段名闸,单一真相源


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
    taxonomy = ds_taxonomy.load_taxonomy(ds_root)
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
        cat = ds_taxonomy.suggest_category(ent.name, taxonomy) if typ == "file" else None
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
    taxonomy = ds_taxonomy.load_taxonomy(ds_root)
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


# ── 单条纠偏:剔除 staged plan 里的某几行,剩余重新暂存 ──────────────────
def _plan_path(ds_root: str, plan_id: str) -> str:
    return os.path.join(ds_root, "organize", "plans", f"plan_{plan_id}.json")


def _valid_drop(drop, n: int) -> bool:
    if not isinstance(drop, list) or not drop:
        return False
    for i in drop:
        # bool 是 int 子类,必须先排除;True/False 不是合法下标
        if isinstance(i, bool) or not isinstance(i, int):
            return False
        if i < 0 or i >= n:
            return False
    return len(set(drop)) == len(drop)


def amend_plan(plan_id, drop, allowed_roots, ds_root: str) -> dict:
    """收件箱卡片单条纠偏(track opendesign-frontend-p1 design §②)。
    drop = 要剔除的 operations 下标列表。剩余行用旧 plan 的 src_rel/dst_rel
    原样构造 operations,过 ds_organize.stage_plan 全套复验重新暂存
    ——存在性/冲突/overwrite 检查免费复用,本函数自己不发明校验路径。
    stage 失败 → 旧 plan 一字不动,原样回传错误。stage 成功(或剩余 0 行=
    整案取消)→ 旧 plan 写 superseded_at + superseded_by,不删文件(审计留痕)。
    已 applied / 已 superseded 的 plan 拒绝再纠偏。"""
    if not ds_organize.is_valid_plan_id(plan_id):
        return {"error": "bad_plan_id"}
    plan_path = _plan_path(ds_root, plan_id)
    if not os.path.exists(plan_path):
        return {"error": "plan_not_found"}
    # 与 apply_plan 同一把锁串行化(四审 subkimi M1):不持锁的读-改-写会与并发
    # approve+apply 交错——amend 读到 applied_at=None,apply 落盘后 amend 把内存里
    # 的旧 dict 整体回写,applied_at 被抹掉(plan 档案与 audit.log 矛盾);两个并发
    # amend 也会各自 stage 出重复新案。锁内重读拿最新状态,already_applied 诚实拒。
    lock_path = os.path.join(ds_root, "organize", ".apply.lock")
    with open(lock_path, "a") as lockfh, ds_lock.exclusive(lockfh):
        with open(plan_path, encoding="utf-8") as fh:
            plan = json.load(fh)
        if plan.get("applied_at"):
            return {"error": "already_applied"}
        if plan.get("superseded_at"):
            return {"error": "plan_superseded"}

        operations = plan.get("operations") or []
        if not _valid_drop(drop, len(operations)):
            return {"error": "bad_drop"}
        drop_set = set(drop)
        remaining = [op for i, op in enumerate(operations) if i not in drop_set]

        # 畸形 plan(手工改坏)→ 干净 bad_plan 不抛 KeyError(四审三腿独立标):
        # 核心契约 = 永远回 error dict,500 面留给真正的意外
        root = plan.get("root")
        if not isinstance(root, str) or not root:
            return {"error": "bad_plan"}
        try:
            new_ops = [{"op": op["op"], "src": op["src_rel"], "dst": op["dst_rel"]}
                       for op in remaining]
        except (KeyError, TypeError):
            return {"error": "bad_plan"}

        new_plan_id = None
        if remaining:
            res = ds_organize.stage_plan(root, new_ops, allowed_roots,
                                         ds_root=ds_root)
            if not res.get("ok"):
                return res  # 旧 plan 一字不动
            new_plan_id = res["plan_id"]

        plan["superseded_at"] = datetime.now().isoformat(timespec="seconds")  # 格式同 ds_organize._now()
        plan["superseded_by"] = new_plan_id
        # 原子写(subkimi M1 的另一半):直接 open("w") 截断后写,进程中途死=坏 JSON
        tmp_path = plan_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(plan, fh, ensure_ascii=False, indent=1)
        os.replace(tmp_path, plan_path)

    return {"ok": True, "plan_id": new_plan_id, "count": len(remaining),
            "dropped": len(drop)}
