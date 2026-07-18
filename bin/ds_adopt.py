#!/usr/bin/env python3
"""ds_adopt —— 采纳引擎 v1(track opendesign-adoption)。

职责:把「存量世界」(已有项目夹/散文件/未绑定项目)变成一次只读盘点报告
(adopt_scan),再把「可安全整理」的项目根散文件变成 ds_organize 的 staged plan
(stage_adoption)。intake 覆盖「增量」(00-收件箱新文件),本模块覆盖「存量」。

本模块自己不发明任何执行路径,单一真相源全部复用:
  - 类目建议 = ds_intake.suggest_category / load_taxonomy;
  - 工作区解析 = ds_workspace(load_config / project_dir / projects_root /
    project_folders);
  - PKB 项目枚举 = ds_tools.list_projects;
  - 暂存/校验/冲突/快照/approve 硬闸 = ds_organize.stage_plan(唯一写面);
  - 路径安全 = ds_common.within。
adopt_scan 纯只读;唯一「写」是 stage_adoption 调 stage_plan 落 plan 文件。

契约(oracle 钉死):
- adopt_scan(ds_root):未配置 → {"ok":True,"configured":False};已配置 →
  {"ok":True,"configured":True,"structure":{inbox/projects_root/archive/shared},
  "projects":[{folder,bound,key,categories,loose_files}],"unbound_pkb":[keys]}。
  结构目录名相对工作区根,识别不到 = null。
- stage_adoption(project_key):auto 类目 → stage_plan(root=工作区根,src/dst
  相对工作区根);suggest 类目(CAD/SU/MAX/PSD 被引用风险)→ advice 口头建议,
  连 plan 都不进(比 intake 更保守一档);未知扩展名 → skipped;可暂存为空 →
  nothing_to_stage;未绑定/未配置 → project_not_bound / workspace_not_configured。
"""
from __future__ import annotations

import json
import os

import ds_common
import ds_intake
import ds_organize
import ds_tools
import ds_workspace

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DEFAULT_DS_ROOT = REPO_ROOT


# ── 结构识别(候选名单机制,复用 inbox 风格) ─────────────────────────────
def _find_struct_dir(root: str, candidates) -> str | None:
    """workspace root 下按候选名找结构目录 → 命中的候选名(相对 root)| None。
    与 ds_intake._find_inbox 同款:必须是目录、非 symlink、realpath 仍在 root 内
    (within 闸挡指到工作区外的候选;结构识别是纯读面,焊死列举侧)。"""
    for cand in candidates or []:
        p = os.path.join(root, cand)
        if not (os.path.isdir(p) and not os.path.islink(p)):
            continue
        real = os.path.realpath(p)
        if not ds_common.within(root, real):
            continue
        return cand
    return None


def _projects_root_rel(cfg) -> str | None:
    """项目根目录名(相对工作区根);复用 ds_workspace.projects_root 的候选/配置
    逻辑,只把它的 realpath 折回相对名。识别不到 → None。"""
    proot = ds_workspace.projects_root(cfg)
    if proot is None:
        return None
    try:
        return os.path.relpath(proot, cfg["root"])
    except ValueError:  # 跨盘符(Windows)relpath 会抛,视为识别不到
        return None


def _categories(fpath: str) -> list[str]:
    """项目夹下一级目录名(=类目,照现状认,不校验命名);点号开头跳过,名序。"""
    out = []
    try:
        entries = os.scandir(fpath)
    except OSError:
        return []
    for ent in entries:
        if ent.name.startswith("."):
            continue
        try:
            if ent.is_dir(follow_symlinks=False):
                out.append(ent.name)
        except OSError:
            continue
    return sorted(out)


def _loose_files(fpath: str) -> int:
    """项目夹根一层的散文件计数(仅常规文件;点号开头/symlink/目录不计)。"""
    n = 0
    try:
        entries = os.scandir(fpath)
    except OSError:
        return 0
    for ent in entries:
        if ent.name.startswith("."):
            continue
        try:
            if ent.is_file(follow_symlinks=False):
                n += 1
        except OSError:
            continue
    return n


# ── 工具 1 adopt_scan(纯只读全盘盘点) ────────────────────────────────────
def adopt_scan(ds_root: str = DEFAULT_DS_ROOT) -> dict:
    cfg = ds_workspace.load_config(ds_root)
    if cfg is None:
        return {"ok": True, "configured": False}
    root = cfg["root"]
    # 坏 taxonomy(默认表永远有效,仅默认表损坏才 None)→ 结构候选整体退化为空,
    # 不炸盘点:结构识别不到 = null,项目/未绑定照常报。
    taxonomy = ds_intake.load_taxonomy(ds_root) or {}

    structure = {
        "inbox": _find_struct_dir(root, taxonomy.get("inboxDirs", [])),
        "projects_root": _projects_root_rel(cfg),
        "archive": _find_struct_dir(root, taxonomy.get("archiveDirs", [])),
        "shared": _find_struct_dir(root, taxonomy.get("sharedDirs", [])),
    }

    # PKB 项目名(单一真相源=ds_tools.list_projects,读 projects/ 一级)
    pkb_names = {p["project"] for p in
                 ds_tools.list_projects(ds_root).get("projects", [])}

    # 显式映射:folder realpath → PKB key(权威绑定,可纠偏)。用 within 复核,
    # 逃逸工作区根/非目录的坏映射不算命中。
    explicit = {}
    for key, rel in cfg["projects"].items():
        if not rel:
            continue
        target = os.path.realpath(os.path.join(root, rel))
        if ds_common.within(root, target) and os.path.isdir(target):
            explicit[target] = key

    projects = []
    bound_keys = set()
    for _fkey, fpath in ds_workspace.project_folders(cfg):
        fname = os.path.basename(fpath)
        # bound 判定:①显式映射 realpath 命中 → ②文件夹名直等 PKB 项目名。
        # token 匹配(intake 的 suggest_project/project_dir ③级)有意不用在报告里
        # ——歧义宁缺勿猜,报告要么确定绑定要么留白让大脑引导 bind_project。
        if fpath in explicit:
            key, bound = explicit[fpath], True
        elif fname in pkb_names:
            key, bound = fname, True
        else:
            key, bound = None, False
        if bound:
            bound_keys.add(key)
        projects.append({"folder": fname, "bound": bound, "key": key,
                         "categories": _categories(fpath),
                         "loose_files": _loose_files(fpath)})

    # 反向未绑定:有 PKB 档案但没有任何文件夹绑到它(改名/归档了,提示 bind 或忽略)
    unbound_pkb = sorted(n for n in pkb_names if n not in bound_keys)

    return {"ok": True, "configured": True, "structure": structure,
            "projects": projects, "unbound_pkb": unbound_pkb}


# ── 工具 2 stage_adoption(项目根散文件 → staged plan) ─────────────────────
def _read_staged(ds_root: str, plan_id: str) -> list[dict]:
    """从落盘的 plan 读回权威 ops(src_rel/dst_rel 由 stage_plan 算),给报告用。"""
    plan_path = os.path.join(ds_root, "organize", "plans", f"plan_{plan_id}.json")
    try:
        with open(plan_path, encoding="utf-8") as fh:
            plan = json.load(fh)
        return [{"op": o["op"], "src_rel": o["src_rel"], "dst_rel": o["dst_rel"]}
                for o in plan.get("operations", [])]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def stage_adoption(project_key: str, ds_root: str = DEFAULT_DS_ROOT,
                   allowed_roots=None) -> dict:
    """某已绑定项目【项目夹根一层】的散文件按 taxonomy 暂存归位。
    auto → stage_plan(root=工作区根;项目类目 dst 在项目夹内,workspace 级类目
    如参考图库 dst 在工作区级共享夹——故 plan root 用工作区根、src/dst 均相对
    工作区根,plan root=项目夹时 dst 出不了夹);suggest → advice(口头,不进
    plan);未知扩展名 → skipped。"""
    cfg = ds_workspace.load_config(ds_root)
    if cfg is None:
        return {"error": "workspace_not_configured"}
    taxonomy = ds_intake.load_taxonomy(ds_root)
    if taxonomy is None:
        return {"error": "taxonomy_bad"}
    proj_dir = ds_workspace.project_dir(cfg, project_key)
    if proj_dir is None:
        return {"error": "project_not_bound"}

    root = cfg["root"]
    proj_rel = os.path.relpath(proj_dir, root)   # 项目夹相对工作区根,如 01-项目/xxx
    advice: list[dict] = []
    skipped: list[str] = []
    operations: list[dict] = []
    try:
        entries = sorted(os.scandir(proj_dir), key=lambda e: e.name)
    except OSError:
        return {"error": "project_unreadable"}

    for ent in entries:
        if ent.name.startswith("."):
            continue
        try:
            if not ent.is_file(follow_symlinks=False):  # 只认根一层散文件,类目夹不动
                continue
        except OSError:
            continue
        name = ent.name
        cat = ds_intake.suggest_category(name, taxonomy)
        if cat is None:                       # 未知扩展名 → 诚实 skipped
            skipped.append(name)
            continue
        # 目标目录(相对工作区根):project 级在项目夹内,workspace 级在共享夹
        dst_dir = (os.path.join(proj_rel, cat["dir"])
                   if cat["scope"] == "project" else cat["dir"])
        if cat["mode"] == "suggest":          # 被引用类目:口头建议,永不进 plan
            advice.append({"file": name, "category": cat["id"], "dir": dst_dir})
            continue
        operations.append({"op": "move",
                           "src": os.path.join(proj_rel, name),
                           "dst": os.path.join(dst_dir, name)})

    if not operations:
        return {"error": "nothing_to_stage", "advice": advice, "skipped": skipped}

    # 唯一写面:root=工作区根,src/dst 相对工作区根,过 stage_plan 全部校验闸。
    res = ds_organize.stage_plan(root, operations, allowed_roots, ds_root=ds_root)
    if not res.get("ok"):
        return res                            # 冲突/逃逸/覆盖 等 error 原样透传
    return {"ok": True, "plan_id": res["plan_id"],
            "staged": _read_staged(ds_root, res["plan_id"]),
            "advice": advice, "skipped": skipped}
