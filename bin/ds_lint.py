#!/usr/bin/env python3
"""ds_lint — PKB 自动体检(track opendesign-pkb-lint T3)。

Karpathy LLM-Wiki 九条自查第 VIII 条(健康检查)的确定性实现:只读、只报告、不修。
修复动作永远走既有工具(改名/删除/organize 确认闸),lint 不碰盘——这是刻意的:
自动修复=第二个能改 PKB 的写面,与"PKB 只经 MCP 工具读写"的铁律相悖。

十项检查 + 坏编码隔离(与 ds_todo.collect 的 M1 先例同哲学:逐文件 try,一个坏文件
计一条 unreadable finding 而不拖垮整轮):
  broken_link              [[X]] 既不是项目也不是业主档案
  duplicate_content        两份档案逐字节相同(07-16 改名事故的形状)
  bad_stage                `- 阶段:` 值不在 PROJECT_STAGES 词表
  duplicate_anchor         同一档案内 C<n> 编号撞车
  refs_dangling            refs 索引「用于:」段指向不存在的项目
  refs_missing_file        refs 索引「文件:」段指向不存在的文件
  workspace_dangling_mapping  workspace.json 显式映射指向不存在的文件夹
  deprecated_index         ds_root 下残留废弃的 index.md
  bad_stage_history        `## 阶段历史` 行格式/词表/乱序/未来日期(档案人可手改,写口拦不到)
  stage_history_mismatch   头部 `- 阶段:` 与阶段历史末条对不上 ⇒ 起始日不可信

词表/正则一律复用单一真相源,不自造第二份:
  - 阶段词表/头部字段解析 → ds_tools.PROJECT_STAGES / ds_tools._read_header_field
  - 变更行 C 编号        → ds_todo.parse_change
  - refs 索引行分段       → ds_refs.parse_ref_line(` | ` 分段、用于:/文件: 段)
  - workspace 配置        → ds_workspace.load_config

跑法:python3 tests/test_ds_lint.py(纯 Python 核心,不需 nanobot/mcp/网络)。
"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import date

import ds_common     # within(workspace 映射逃逸检查)
import ds_refs       # refs 索引行分段解析(parse_ref_line)
import ds_todo       # 变更行 C 编号解析(parse_change)
import ds_tools      # PROJECT_STAGES + 头部字段读取(_read_header_field)
import ds_workspace  # workspace.json 解析(load_config)

DEFAULT_DS_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# [[链接]] 抽取:非贪婪、禁套嵌 [ ](与 rename_project 的精确定界同心智)
_WIKILINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")


def _finding(check: str, target: str, detail: str) -> dict:
    return {"check": check, "target": target, "detail": detail}


def _md_files(dir_path: str) -> list[str]:
    """目录下 .md 文件名(名序);目录缺失 → 空。"""
    if not os.path.isdir(dir_path):
        return []
    return sorted(f for f in os.listdir(dir_path) if f.endswith(".md"))


def lint_pkb(ds_root: str = DEFAULT_DS_ROOT) -> dict:
    """PKB 全量体检。返回 {"ok": True, "findings": [{check,target,detail}...]}。
    只读:不写任何文件(oracle test_02 逐字节校验)。"""
    findings: list[dict] = []
    proj_dir = os.path.join(ds_root, "projects")
    client_dir = os.path.join(ds_root, "clients")
    proj_files = _md_files(proj_dir)
    client_files = _md_files(client_dir)
    # 链接可达性判据:[[X]] 命中 projects/X.md 或 clients/X.md 任一即算通
    project_slugs = {f[:-3] for f in proj_files}
    client_slugs = {f[:-3] for f in client_files}
    known = project_slugs | client_slugs

    # ── duplicate_content:全档案逐字节哈希分组(bytes 读,坏编码也能哈希)──────
    by_hash: dict[str, list[str]] = {}
    for kind, base, files in (("projects", proj_dir, proj_files),
                              ("clients", client_dir, client_files)):
        for fn in files:
            try:
                with open(os.path.join(base, fn), "rb") as fh:
                    h = hashlib.sha256(fh.read()).hexdigest()
            except OSError:
                continue  # 读不了字节的(权限/竞态)不参与查重,交给 unreadable 或跳过
            by_hash.setdefault(h, []).append(f"{kind}/{fn}")
    for rels in by_hash.values():
        if len(rels) > 1:
            rels = sorted(rels)
            findings.append(_finding(
                "duplicate_content", rels[0],
                "逐字节相同:" + "、".join(rels)))

    # ── 逐档案解码检查:broken_link / bad_stage(仅项目)/ duplicate_anchor ──────
    for kind, base, files in (("projects", proj_dir, proj_files),
                              ("clients", client_dir, client_files)):
        for fn in files:
            slug = fn[:-3]
            try:
                with open(os.path.join(base, fn), encoding="utf-8") as fh:
                    text = fh.read()
            except (OSError, UnicodeDecodeError):
                findings.append(_finding(
                    "unreadable", f"{kind}/{slug}", "文件读不了(坏编码或权限),已跳过其余检查"))
                continue
            lines = text.split("\n")

            # broken_link:全文所有 [[X]],X 不是已知项目/业主即断链
            for name in _WIKILINK_RE.findall(text):
                if name not in known:
                    findings.append(_finding(
                        "broken_link", f"{kind}/{slug}",
                        f"[[{name}]] 指向的项目/业主档案不存在"))

            if kind != "projects":
                continue  # 阶段/变更行是项目档案独有

            # bad_stage:头部 `- 阶段:` 值必须在词表(复用 _read_header_field + PROJECT_STAGES)
            stage = ds_tools._read_header_field(lines, "阶段")
            if stage and stage not in ds_tools.PROJECT_STAGES:
                findings.append(_finding(
                    "bad_stage", f"projects/{slug}",
                    f"阶段「{stage}」不在词表(应为 {'/'.join(ds_tools.PROJECT_STAGES)} 之一)"))

            bounds = ds_tools._section_bounds(lines, ds_tools._STAGE_HISTORY_HEADER)
            if bounds is not None:
                hidx, end = bounds
                valid_entries = []
                prev_date = None
                for ln in lines[hidx + 1:end]:
                    if not ln.strip():
                        continue
                    m = ds_tools._STAGE_HISTORY_RE.match(ln)
                    bad_detail = None
                    if not m:
                        bad_detail = f"阶段历史行格式不对:{ln}"
                    else:
                        d, hist_stage = m.group(1), m.group(2)
                        try:
                            date.fromisoformat(d)
                        except ValueError:
                            bad_detail = f"阶段历史日期不合法:{ln}"
                        if bad_detail is None and hist_stage not in ds_tools.PROJECT_STAGES:
                            bad_detail = f"阶段历史阶段「{hist_stage}」不在词表:{ln}"
                        if bad_detail is None and prev_date is not None and d < prev_date:
                            bad_detail = f"阶段历史日期乱序:{ln}"
                        # 未来日期:写口拦得住,**手改拦不住**。不报的话用户只能从
                        # 界面上一个诡异的天数去猜(读侧现在会归"未记录",更没线索)。
                        if bad_detail is None and d > ds_common.today_str(None):
                            bad_detail = f"阶段历史日期在未来:{ln}"
                        if bad_detail is None:
                            prev_date = d
                            valid_entries.append({"date": d, "stage": hist_stage})
                    if bad_detail is not None:
                        findings.append(_finding(
                            "bad_stage_history", f"projects/{slug}", bad_detail))
                if valid_entries and stage and valid_entries[-1]["stage"] != stage:
                    findings.append(_finding(
                        "stage_history_mismatch", f"projects/{slug}",
                        f"头部阶段「{stage}」与阶段历史末条「{valid_entries[-1]['stage']}」不一致"))

            # duplicate_anchor:同档案内 C<n> 撞车(锚定域=单文件;parse_change 单一真相源)
            seen: dict[int, int] = {}
            for ln in lines:
                c = ds_todo.parse_change(ln)
                if c is None or c["cnum"] is None:
                    continue
                seen[c["cnum"]] = seen.get(c["cnum"], 0) + 1
            for cnum, cnt in sorted(seen.items()):
                if cnt > 1:
                    findings.append(_finding(
                        "duplicate_anchor", f"projects/{slug}",
                        f"C{cnum} 出现 {cnt} 次(编号应唯一)"))

    # ── refs 索引:refs_dangling / refs_missing_file(parse_ref_line 单一真相源)──
    refs_path = os.path.join(ds_root, "refs-index.md")
    if os.path.isfile(refs_path):
        try:
            with open(refs_path, encoding="utf-8") as fh:
                refs_lines = fh.read().split("\n")
        except (OSError, UnicodeDecodeError):
            refs_lines = []
        for ln in refs_lines:
            parsed = ds_refs.parse_ref_line(ln)
            if parsed is None:
                continue
            for proj in parsed["used"]:
                if proj not in project_slugs:
                    findings.append(_finding(
                        "refs_dangling", parsed["id"],
                        f"用于:{proj} —— 该项目不存在"))
            rel = parsed["file"]
            if rel and not os.path.isfile(os.path.join(ds_root, rel)):
                findings.append(_finding(
                    "refs_missing_file", parsed["id"],
                    f"文件:{rel} —— 图片文件不存在"))

    # ── workspace 映射悬挂:显式映射指向不存在的文件夹(load_config 单一真相源)────
    cfg = ds_workspace.load_config(ds_root)
    if cfg is not None:
        root = cfg["root"]
        for key, rel in cfg["projects"].items():
            target = os.path.realpath(os.path.join(root, rel))
            if not ds_common.within(root, target) or not os.path.isdir(target):
                findings.append(_finding(
                    "workspace_dangling_mapping", key,
                    f"映射到「{rel}」—— 该文件夹不存在(或逃逸工作区根)"))

    # ── 废弃 index.md 残留 ────────────────────────────────────────────────────
    if os.path.isfile(os.path.join(ds_root, "index.md")):
        findings.append(_finding(
            "deprecated_index", "index.md",
            "index.md 已废弃(无人维护;项目盘点改用 list_projects),建议删除"))

    return {"ok": True, "findings": findings}
