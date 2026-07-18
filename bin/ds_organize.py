#!/usr/bin/env python3
"""design-studio 文件整理工具层 — track opendesign-file-organizer design.md 的实现。

两层(同 ds_tools.py):
  1) 纯 Python 核心(scan_dir/stage_plan/apply_plan/approve_plan),只依赖标准库,
     可被 tests/ 直接调用做 oracle 验证。
  2) 末尾的 stdio MCP server 包装(需 `pip install mcp`,未装则不影响核心)。

契约铁律:
  - LLM 提方案 / 工具管校验+执行。MCP 只暴露 scan/stage/apply 三工具。
  - `.approved` 标记只能由人(bin/ds-approve)创建 —— 模型没有任何工具能造它,
    未批准的方案物理上执行不了。批准单 plan 生效,apply 一次即消耗。
  - MVP 原语只有 move/rename(delete 已被用户砍掉,收到即拒)。
  - stage 零改动;apply 先整体复验(存在性/不覆盖/size+mtime_ns 快照漂移),
    任一失败整个 plan 中止零执行;执行逐条落 audit.log。

安全:allowed_roots 白名单 + realpath 防逃逸;白名单为空 = 默认关死。
"""
from __future__ import annotations

import json
import os
import re
import secrets
import stat as stat_mod
import time
from datetime import datetime

import ds_common  # 共享:防逃逸谓词 within(),同目录模块
import ds_lock    # 跨平台排他锁(Linux fcntl / Windows msvcrt),同目录模块

# env DS_ROOT 缺失时基于 __file__ 推导(bin/ 的上一级):Linux/Windows 通用,不硬编码 /root
DEFAULT_DS_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
ALLOWED_OPS = ("move", "rename")  # 同一原语两个名字;delete 是 Non-goal
MAX_ENTRIES = 2000

_PLAN_ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{6}$")


def is_valid_plan_id(plan_id) -> bool:
    """plan_id 格式闸的公共出口(ds_web 针孔④ 复用;别再摸 _PLAN_ID_RE 私有件)。"""
    return isinstance(plan_id, str) and bool(_PLAN_ID_RE.match(plan_id))


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _plans_dir(ds_root: str) -> str:
    return os.path.join(ds_root, "organize", "plans")


def _audit_path(ds_root: str) -> str:
    return os.path.join(ds_root, "organize", "audit.log")


# ── 安全:根白名单 + 路径解析 ──────────────────────────────────────────────
def _resolve_root(root: str, allowed_roots: list[str] | None) -> str | None:
    """root 的 realpath 必须等于或落在某个允许根之内,否则 None(默认关死)。"""
    real = os.path.realpath(root)
    for a in allowed_roots or []:
        if ds_common.within(os.path.realpath(a), real):
            return real
    return None


def _resolve_in_root(root_real: str, rel: str, ds_root: str) -> str | None:
    """把 op 里的路径解析成绝对 realpath,并强制落在 root 内;逃逸返回 None。
    ds_root/organize 子树(plans/.approved/audit.log = 批准机关自身)硬排除:
    即使机主把 DS_ROOT 圈进白名单,整理对象也不能是闸的零件。"""
    raw = rel if os.path.isabs(rel) else os.path.join(root_real, rel)
    target = os.path.realpath(raw)
    if not ds_common.within(root_real, target):
        return None
    org = os.path.realpath(os.path.join(ds_root, "organize"))
    if ds_common.within(org, target):
        return None
    return target


def _is_ancestor(a: str, b: str) -> bool:
    return b.startswith(a + os.sep)


def _dst_parent_blocked(dst: str, root_real: str) -> bool:
    """dst 的已存在的最近祖先必须是目录,否则 makedirs 会在执行中途炸(部分执行)。"""
    p = os.path.dirname(dst)
    while p != root_real and not os.path.lexists(p):
        p = os.path.dirname(p)
    return not os.path.isdir(p)


# ── 工具 1 scan_dir(只读) ────────────────────────────────────────────────
def scan_dir(root: str, allowed_roots: list[str] | None,
             max_entries: int = MAX_ENTRIES) -> dict:
    root_real = _resolve_root(root, allowed_roots)
    if root_real is None:
        return {"error": "root_not_allowed"}
    if not os.path.isdir(root_real):
        return {"error": "not_a_dir"}

    entries: list[dict] = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root_real):
        dirnames.sort()
        filenames.sort()
        names = [(d, "dir") for d in dirnames] + [(f, "file") for f in filenames]
        for name, typ in names:
            p = os.path.join(dirpath, name)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            try:
                mtime = datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
            except (OSError, OverflowError, ValueError):
                mtime = "unknown"  # Windows 偶见 1970 前/损坏时间戳,单个坏文件不拖死扫描
            entries.append({
                "path": os.path.relpath(p, root_real),
                "type": typ,
                "size": st.st_size,
                "mtime": mtime,
            })
            if len(entries) >= max_entries:
                truncated = True
                break
        if truncated:
            break
    return {"ok": True, "root": root_real, "entries": entries, "truncated": truncated}


# ── 工具 2 stage_plan(校验 + 暂存,零改动) ────────────────────────────────
def _snapshot(path: str) -> dict:
    st = os.lstat(path)
    return {"size": st.st_size, "mtime_ns": st.st_mtime_ns,
            "is_dir": stat_mod.S_ISDIR(st.st_mode)}


def stage_plan(root: str, operations: list[dict], allowed_roots: list[str] | None,
               ds_root: str = DEFAULT_DS_ROOT) -> dict:
    root_real = _resolve_root(root, allowed_roots)
    if root_real is None:
        return {"error": "root_not_allowed"}
    if not operations:
        return {"error": "empty_plan"}

    resolved: list[dict] = []
    for i, op in enumerate(operations):
        kind = (op.get("op") or "").strip().lower()
        if kind not in ALLOWED_OPS:
            return {"error": "op_not_allowed", "index": i, "op": kind}
        src = _resolve_in_root(root_real, op.get("src") or "", ds_root)
        dst = _resolve_in_root(root_real, op.get("dst") or "", ds_root)
        if src is None or dst is None or dst == root_real:
            return {"error": "path_escape", "index": i}
        resolved.append({"op": kind, "src": src, "dst": dst})

    # op 之间的冲突先于存在性检查(与执行顺序无关的判定优先):
    # src/dst 重复、dst 撞 src(链式)、祖先重叠(动目录又动其内部)。
    # casefold 后比较:大小写不敏感 FS(NTFS)上,仅大小写不同的两个不存在 dst
    # realpath 不会归一 → 字符串查重放行 → 执行中途才撞 would_overwrite = 部分执行。
    # Linux 上这会误拒"同时动 A.TXT 和 a.txt"的极端 plan,接受(可拆两个 plan)。
    paths = [r["src"] for r in resolved] + [r["dst"] for r in resolved]
    paths_cf = [p.casefold() for p in paths]
    if len(set(paths_cf)) != len(paths_cf):
        return {"error": "conflict", "detail": "duplicate_or_case_collision"}
    for a in paths_cf:
        for b in paths_cf:
            if a != b and _is_ancestor(a, b):
                return {"error": "conflict", "detail": "nested_paths"}

    for i, r in enumerate(resolved):
        if not os.path.lexists(r["src"]):
            return {"error": "src_missing", "index": i,
                    "src": os.path.relpath(r["src"], root_real)}
        if os.path.lexists(r["dst"]):
            return {"error": "would_overwrite", "index": i,
                    "dst": os.path.relpath(r["dst"], root_real)}
        if _dst_parent_blocked(r["dst"], root_real):
            return {"error": "dst_parent_not_dir", "index": i,
                    "dst": os.path.relpath(r["dst"], root_real)}

    plan_id = time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
    ops_out = []
    lines = []
    for r in resolved:
        src_rel = os.path.relpath(r["src"], root_real)
        dst_rel = os.path.relpath(r["dst"], root_real)
        ops_out.append({"op": r["op"], "src_rel": src_rel, "dst_rel": dst_rel,
                        "src": r["src"], "dst": r["dst"],
                        "snapshot": _snapshot(r["src"])})
        lines.append(f"{r['op'].upper()}  {src_rel}  →  {dst_rel}")
    summary = "\n".join(lines)

    plans = _plans_dir(ds_root)
    os.makedirs(plans, exist_ok=True)
    plan = {"plan_id": plan_id, "root": root_real, "created": _now(),
            "operations": ops_out, "summary": summary, "applied_at": None}
    with open(os.path.join(plans, f"plan_{plan_id}.json"), "x", encoding="utf-8") as fh:
        json.dump(plan, fh, ensure_ascii=False, indent=1)

    return {"ok": True, "plan_id": plan_id, "count": len(ops_out), "summary": summary,
            "note": "零改动,已暂存。需人工在终端跑 `ds-approve " + plan_id +
                    "` 批准后才能 apply_plan。"}


# ── 人工闸 approve_plan(仅供 bin/ds-approve 调用,不进 MCP) ───────────────
def approve_plan(plan_id: str, ds_root: str = DEFAULT_DS_ROOT) -> dict:
    if not _PLAN_ID_RE.match(plan_id or ""):
        return {"error": "bad_plan_id"}
    plan_path = os.path.join(_plans_dir(ds_root), f"plan_{plan_id}.json")
    if not os.path.exists(plan_path):
        return {"error": "plan_not_found"}
    with open(plan_path, encoding="utf-8") as fh:
        plan = json.load(fh)
    if plan.get("applied_at"):
        return {"error": "already_applied"}
    if plan.get("superseded_at"):
        return {"error": "plan_superseded"}
    marker = os.path.join(_plans_dir(ds_root), f"plan_{plan_id}.approved")
    with open(marker, "w", encoding="utf-8") as fh:
        fh.write(_now() + "\n")
    return {"ok": True, "plan_id": plan_id, "summary": plan["summary"]}


# ── 工具 3 apply_plan(仅批准后;先整体复验,后执行) ────────────────────────
def apply_plan(plan_id: str, allowed_roots: list[str] | None,
               ds_root: str = DEFAULT_DS_ROOT) -> dict:
    if not _PLAN_ID_RE.match(plan_id or ""):
        return {"error": "bad_plan_id"}
    plan_path = os.path.join(_plans_dir(ds_root), f"plan_{plan_id}.json")
    if not os.path.exists(plan_path):
        return {"error": "plan_not_found"}

    # 全局 apply 锁:两个"都被批准"的 plan 并发 apply 会互相打穿 dst 复验
    # (POSIX rename 静默覆盖),串行化后这类窗口只剩工具外部的进程。
    lock_path = os.path.join(os.path.dirname(_plans_dir(ds_root)), ".apply.lock")
    # "a" 不截断:Windows 上对他人持锁文件截断行为不确定,追加模式零成本回避
    with open(lock_path, "a") as lockfh, ds_lock.exclusive(lockfh):
        with open(plan_path, "r+", encoding="utf-8") as fh:
            plan = json.load(fh)
            if plan.get("applied_at"):
                return {"error": "already_applied"}
            if plan.get("superseded_at"):
                return {"error": "plan_superseded"}
            marker = os.path.join(_plans_dir(ds_root), f"plan_{plan_id}.approved")
            if not os.path.exists(marker):
                return {"error": "not_approved",
                        "note": f"需人工在终端跑 `ds-approve {plan_id}`。"}
            root_real = _resolve_root(plan["root"], allowed_roots)
            if root_real is None:
                return {"error": "root_not_allowed"}

            # 整体复验,任一失败零执行。plan 文件不作免检信任:containment/
            # organize 排除/casefold 查重都在这里重跑一遍(stage 时校验过,
            # 但 apply 只应依赖自己看得见的当下状态)。
            org = os.path.realpath(os.path.join(ds_root, "organize"))
            all_cf = [p.casefold() for op in plan["operations"]
                      for p in (op["src"], op["dst"])]
            if len(set(all_cf)) != len(all_cf):
                return {"error": "conflict", "detail": "duplicate_or_case_collision"}
            # R2-L5:嵌套检查与 stage 对齐(plan 文件不作免检信任)——伪造的嵌套 plan
            # (D 与 D/x 同在一批)否则会 op1 落盘后 op2 src 消失 = 部分执行
            for a in all_cf:
                for b in all_cf:
                    if a != b and _is_ancestor(a, b):
                        return {"error": "conflict", "detail": "nested_paths"}
            for op in plan["operations"]:
                src, dst = op["src"], op["dst"]
                for p in (src, dst):
                    if not ds_common.within(root_real, p) or ds_common.within(org, p):
                        return {"error": "path_escape", "src": op["src_rel"]}
                if not os.path.lexists(src):
                    return {"error": "src_missing", "src": op["src_rel"]}
                # 组件被换成指向外部的符号链接 → realpath 变 → 视为漂移
                if os.path.realpath(src) != src or os.path.realpath(dst) != dst:
                    return {"error": "plan_drift", "src": op["src_rel"]}
                snap = _snapshot(src)
                if snap != op["snapshot"]:
                    return {"error": "plan_drift", "src": op["src_rel"]}
                if os.path.lexists(dst):
                    return {"error": "would_overwrite", "dst": op["dst_rel"]}
                if _dst_parent_blocked(dst, root_real):
                    return {"error": "dst_parent_not_dir", "dst": op["dst_rel"]}

            # 执行 + audit。中途失败不回滚(回滚本身可能再失败),但:
            # 已执行部分逐条在 audit.log,且随错误原样返回,恢复有据可查。
            applied = []
            with open(_audit_path(ds_root), "a", encoding="utf-8") as audit:
                for op in plan["operations"]:
                    parent = os.path.dirname(op["dst"])
                    try:
                        os.makedirs(parent, exist_ok=True)
                        # rename 前再验一次(makedirs 之后的最后窗口)
                        if os.path.lexists(op["dst"]):
                            return {"error": "would_overwrite", "dst": op["dst_rel"],
                                    "executed": applied}
                        rp = os.path.realpath(parent)
                        if not ds_common.within(root_real, rp):
                            return {"error": "path_escape", "dst": op["dst_rel"],
                                    "executed": applied}
                        os.rename(op["src"], op["dst"])
                    except OSError as exc:
                        return {"error": "apply_failed", "at": op["src_rel"],
                                "detail": str(exc), "executed": applied,
                                "note": "已执行部分见 executed 与 audit.log,未回滚。"}
                    audit.write(f"{_now()}\t{plan_id}\t{op['op']}\t"
                                f"{op['src']}\t{op['dst']}\n")
                    audit.flush()
                    applied.append(f"{op['src_rel']} → {op['dst_rel']}")

            plan["applied_at"] = _now()
            fh.seek(0)
            fh.truncate()
            json.dump(plan, fh, ensure_ascii=False, indent=1)

    return {"ok": True, "plan_id": plan_id, "applied": applied}


# ── stdio MCP server 包装(需 `pip install mcp`;未装不影响以上核心) ────────
def _build_server(ds_root: str, allowed_roots: list[str]):
    from mcp.server.fastmcp import FastMCP  # 延迟导入

    server = FastMCP("design-studio-organize")

    @server.tool()
    def scan_dir_tool(root: str) -> dict:
        """整理文件夹的第一步:设计师说"帮我整理/归类这个文件夹/批量改名/归档旧文件"
        时先调这个——只读列出 root 下的文件/子目录(相对路径、类型、大小、修改时间),
        看清现状再 stage_plan 出方案。本身零改动,放心调。"""
        return scan_dir(root, allowed_roots=allowed_roots)

    @server.tool()
    def stage_plan_tool(root: str, operations: list[dict]) -> dict:
        """暂存一份整理方案(零改动)。operations=[{op: move|rename, src, dst}],
        路径相对 root。返回 plan_id + 给人看的清单;需用户在终端 ds-approve 批准。"""
        return stage_plan(root, operations, allowed_roots=allowed_roots,
                          ds_root=ds_root)

    @server.tool()
    def apply_plan_tool(plan_id: str) -> dict:
        """执行一份已经人工批准的方案。未批准会被拒绝——请用户在终端跑
        `ds-approve <plan_id>`,聊天里说"确认"不算数。"""
        return apply_plan(plan_id, allowed_roots=allowed_roots, ds_root=ds_root)

    import ds_intake  # 同目录模块;收件箱认领两工具(track opendesign-intake)

    @server.tool()
    def list_inbox_tool() -> dict:
        """看收件箱:设计师问"收件箱里有什么/有没有新文件/帮我整理收件箱"时先调
        这个——列出工作区 00-收件箱 里的文件,带确定性建议(扩展名→类目,文件名
        含项目名→建议项目;歧义留空,要问用户别猜)。只读零改动,放心调。"""
        return ds_intake.list_inbox(ds_root)

    @server.tool()
    def stage_intake_tool(assignments: list[dict]) -> dict:
        """把收件箱文件的归类指派暂存成方案(零改动):设计师确认了"这个文件归
        哪个项目哪个类目"之后调用。assignments=[{name: 收件箱内文件名,
        project: 项目名(参考图等工作区级类目可为 null), category: 类目 id}]。
        返回 plan_id;真正移动要用户在工作台收件箱卡片点「确认执行」,
        聊天里说"确认"不算数,也不要自己调 apply_plan_tool 替用户确认。"""
        return ds_intake.stage_intake(assignments, allowed_roots=allowed_roots,
                                      ds_root=ds_root)

    import ds_adopt  # 同目录模块;采纳引擎两工具(track opendesign-adoption)

    @server.tool()
    def adopt_workspace_tool() -> dict:
        """接管我的工作区 / 盘点工作区 / 首装 / 看看工作区什么情况 / 采纳现状:
        一次只读盘点整个工作区——识别收件箱/项目根/归档/共享结构,列出每个项目夹的
        绑定状态、类目、根层散文件数,以及有档案却没绑文件夹的项目。零改动。据此
        引导设计师逐个 bind_project,再对项目内散文件调 stage_adoption。"""
        return ds_adopt.adopt_scan(ds_root)

    @server.tool()
    def stage_adoption_tool(project_key: str) -> dict:
        """把某个已绑定项目【项目夹根一层】的散文件按 taxonomy 暂存归位(零改动):
        auto 类目(资料/参考图)进方案,suggest 类目(CAD/SU/MAX/PSD 被引用风险)
        只在 advice 里口头建议、永不自动动,未知扩展名进 skipped。返回 plan_id;
        真正移动要设计师在工作台卡片点「确认执行」,你不能替他确认也别自己调
        apply_plan_tool。"""
        return ds_adopt.stage_adoption(project_key, allowed_roots=allowed_roots,
                                       ds_root=ds_root)

    return server


def _run_mcp() -> None:
    ds_root = os.environ.get("DS_ROOT", DEFAULT_DS_ROOT)
    # os.pathsep:Linux 冒号 / Windows 分号(Windows 路径自带盘符冒号,不能拿冒号切)
    allowed = [p for p in os.environ.get("DS_ORGANIZE_ROOTS", "").split(os.pathsep) if p]
    _build_server(ds_root, allowed).run()


if __name__ == "__main__":
    _run_mcp()
