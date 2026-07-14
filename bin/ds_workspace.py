#!/usr/bin/env python3
"""ds_workspace —— 用户真实文件工作区的只读视图(track opendesign-workbench-p5)。

职责:解析 config/workspace.json(工作区根 + PKB项目key→项目夹映射),按
docs/workspace-taxonomy.md v1.0 的"项目夹下一级目录=类目"约定做只读扫描:
类目计数概览、图片列举、open-folder 用的子目录解析。

契约:
- 本模块零写面(纯读盘);坏配置一律返回 None 降级,不 raise 不炸调用方。
- 所有 key/映射/sub 解析必须过 realpath + ds_common.within 权威闸,
  字符集白名单只是纵深;返回路径一律 realpath 后的绝对路径。
- 点号开头目录(.opendesign/.git 等)不扫描不计数;扫描有深度与每类目数量上限,
  超限诚实置 capped,不假装全量。
"""
import json
import os
import posixpath
import re
import stat

import ds_common

CONFIG_REL = os.path.join("config", "workspace.json")
# 图片扩展白名单(与 ds_web 参考图 Gate C 同集合;svg 排除=直开可执行脚本)
IMG_EXTS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
MAX_DEPTH = 4           # 相对项目根的最大路径段数(类目算 1 段)
MAX_PER_CAT = 2000      # 每类目扫描上限
# ── 单段/路径名闸 Gate A(M2 v2,07-14:字符白名单 → 危险字符黑名单)────────────
# 单段文件/目录名 + 项目名 + 参考图相对路径的单一真相源。老版是字符白名单
# (\w .()#\-),但 \w 不含中文全角标点(（）！？，。、【】)也不含 & + 等常见命名字符,
# 结果真实文件在枚举侧被静默过滤 —— 用户看不见自己的文件,且白名单要不断补字符(打地鼠)。
# 改黑名单:Gate A 只挡会破坏「单段路径语义」或 URL 解码的字符,放行其余(含中文标点)。
# 逃逸的权威判定始终是 realpath+within(Gate B);可读类型由扩展白名单兜(Gate C);
# Gate A 只是纵深防御第一层。黑名单 = 路径分隔符 / \、URL 百分号 %(编码引信)、
# 控制字符(\n\r\t、NUL 等 <0x20);另拒整段恰为 . 或 ..(父目录引用)。收尾 \Z 不用 $
# (\Z 才真正锚到串尾,$ 会在结尾换行前也匹配,放过 `a.png\n`)。
_SEG_RE = re.compile(r"^(?!\.\.?\Z)[^/\\%\x00-\x1f]+\Z")  # 单段:禁 / \ % 与控制符,非 ./..
_SUB_RE = _SEG_RE                 # 子目录名(resolve_sub 用)同闸
# 可寻址项目名 —— 单一真相源(p7):文件夹名成为路由 key 后「能列出」与「能寻址」必须同集合;
# ds_web._PROJ_KEY_RE 直接引用本常量,两边永不漂移。写侧 H1 名字闸(ds_tools)亦复用本闸。
PROJECT_NAME_RE = _SEG_RE


def relpath_ok(rel: str) -> bool:
    """多段参考图相对路径闸(允许 /):逐段过 _SEG_RE —— 整体禁 \\ % 与控制符,
    且无空段、无 . / .. 段(.. 段在此直接拒,不必等 Gate B)。与单段闸同规则,只是
    多段用 / 连接,故仍是单一真相源;ds_web 参考图/文件服务复用本函数。"""
    parts = rel.split("/")
    return bool(parts) and all(_SEG_RE.match(p) for p in parts)
# projectsDir 未配置时的候选目录名(taxonomy v1.0 写 01项目,真机模板用 01-项目)
_PROJECTS_DIR_CANDIDATES = ("01项目", "01-项目", "01_项目", "01 项目")


def load_config(ds_root: str):
    """读 <ds_root>/config/workspace.json →
    {"root": <realpath>, "projects": {key: rel}};缺文件/坏 json/结构不对/
    root 非目录 → None(功能整体降级,调用方按"未配置"处理)。"""
    path = os.path.join(ds_root, CONFIG_REL)
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    root, projects = raw.get("root"), raw.get("projects")
    if not isinstance(root, str) or not isinstance(projects, dict):
        return None
    if not all(isinstance(k, str) and isinstance(v, str)
               for k, v in projects.items()):
        return None
    projects_dir = raw.get("projectsDir")  # 可选:项目夹所在目录(相对 root,"."=root)
    if projects_dir is not None and not isinstance(projects_dir, str):
        return None
    root = os.path.realpath(root)
    if not os.path.isdir(root):
        return None
    return {"root": root, "projects": projects, "projectsDir": projects_dir}


def project_dir(cfg, key: str):
    """key → 项目夹 realpath;解析三级(p7 design D2,前者优先):
    ①显式映射(权威,可纠偏)→ ②扫描文件夹名 == key → ③key 按 `-` 切 token,
    全部 token 均为文件夹名子串且恰好唯一命中(歧义不绑,误绑自保护)。
    未命中/映射逃逸工作区根/非目录(含 symlink 外指)→ None。cfg 为 load_config 产物。"""
    if cfg is None:
        return None
    rel = cfg["projects"].get(key)
    if isinstance(rel, str) and rel:
        target = os.path.realpath(os.path.join(cfg["root"], rel))
        if not ds_common.within(cfg["root"], target) or not os.path.isdir(target):
            return None
        return target
    folders = project_folders(cfg)
    for name, path in folders:
        if name == key:
            return path
    tokens = [t for t in key.split("-") if t]
    if not tokens:
        return None
    hits = [path for name, path in folders
            if all(t in name for t in tokens)]
    return hits[0] if len(hits) == 1 else None


def projects_root(cfg):
    """项目夹所在目录 realpath;projectsDir 显式配置(within 闸,"."=root)
    优先,否则候选名取首个存在者;都没有 → None(自动发现整体降级)。"""
    if cfg is None:
        return None
    rel = cfg.get("projectsDir")
    if isinstance(rel, str) and rel:
        target = os.path.realpath(os.path.join(cfg["root"], rel))
        if ds_common.within(cfg["root"], target) and os.path.isdir(target):
            return target
        return None
    for cand in _PROJECTS_DIR_CANDIDATES:
        target = os.path.join(cfg["root"], cand)
        if os.path.isdir(target):
            return os.path.realpath(target)
    return None


def project_folders(cfg):
    """自动发现的项目夹 [(name, realpath)] 名序;projects-dir 缺失 → []。
    只取一级目录;点号开头跳过(同 _scan);symlink 目录跳过
    (follow_symlinks=False,外指零风险);名字不过 PROJECT_NAME_RE 白名单者跳过
    (路由 key 字符集寻址不到,列了也点不开)。"""
    proot = projects_root(cfg)
    if proot is None:
        return []
    out = []
    try:
        entries = sorted(os.scandir(proot), key=lambda e: e.name)
    except OSError:
        return []
    for ent in entries:
        if ent.name.startswith(".") or not PROJECT_NAME_RE.match(ent.name):
            continue
        try:
            if not ent.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue
        out.append((ent.name, os.path.realpath(ent.path)))
    return out


def _scan(proj_dir: str, max_per_cat: int):
    """单次遍历:{类目名: {"files": [(rel_posix, name, mtime, size)], "capped": bool}}。
    类目 = 项目夹下一级目录;顶层散文件归 ""。点号开头的目录/文件跳过;
    深度(相对项目根的路径段数)> MAX_DEPTH 不进。
    读盘 OSError(权限/竞态删除)= 该目录/文件静默跳过,部分结果照常返回——
    只读视图宁缺勿炸,与 ds_web 500 自愈哲学一致。"""
    cats = {}

    def bucket(name):
        return cats.setdefault(name, {"files": [], "capped": False})

    try:
        entries = sorted(os.scandir(proj_dir), key=lambda e: e.name)
    except OSError:
        return cats
    for ent in entries:
        # 点号开头跳过;字符集闸(M2):列出的段必须过 _SEG_RE,否则服务/寻址端 404
        if ent.name.startswith(".") or not _SEG_RE.match(ent.name):
            continue
        if ent.is_file(follow_symlinks=False):
            _add(bucket(""), "", ent, max_per_cat)
        elif ent.is_dir(follow_symlinks=False):
            _walk_cat(bucket(ent.name), ent.name, ent.path, 1, max_per_cat)
    return cats


def _add(cat, rel_dir, ent, max_per_cat):
    if cat["capped"] or len(cat["files"]) >= max_per_cat:
        cat["capped"] = True
        return
    try:
        st = ent.stat(follow_symlinks=False)
    except OSError:
        return
    if not stat.S_ISREG(st.st_mode):
        return
    rel = posixpath.join(rel_dir, ent.name) if rel_dir else ent.name
    cat["files"].append((rel, ent.name, int(st.st_mtime), st.st_size))


def _walk_cat(cat, rel_dir, abs_dir, depth, max_per_cat):
    try:
        entries = sorted(os.scandir(abs_dir), key=lambda e: e.name)
    except OSError:
        return
    for ent in entries:
        if ent.name.startswith(".") or not _SEG_RE.match(ent.name):  # 字符集闸(M2)
            continue
        if ent.is_file(follow_symlinks=False):
            if depth + 1 <= MAX_DEPTH:
                _add(cat, rel_dir, ent, max_per_cat)
        elif ent.is_dir(follow_symlinks=False) and depth + 1 < MAX_DEPTH:
            _walk_cat(cat, posixpath.join(rel_dir, ent.name), ent.path,
                      depth + 1, max_per_cat)
        if cat["capped"]:
            return


def overview(proj_dir: str, recent_n: int = 8, max_per_cat: int = MAX_PER_CAT):
    """{"categories": [{"name","count","capped"}...(按名序)],
    "recent": [{"name","category","mtime","size"}...(mtime 降序,前 recent_n)]}"""
    cats = _scan(proj_dir, max_per_cat)
    categories = [{"name": name, "count": len(c["files"]), "capped": c["capped"]}
                  for name, c in sorted(cats.items()) if c["files"] or c["capped"]]
    allf = [(mtime, name, cat_name, size)
            for cat_name, c in cats.items()
            for (_rel, name, mtime, size) in c["files"]]
    allf.sort(key=lambda t: (-t[0], t[1]))
    recent = [{"name": name, "category": cat_name, "mtime": mtime, "size": size}
              for mtime, name, cat_name, size in allf[:recent_n]]
    return {"categories": categories, "recent": recent}


def images(proj_dir: str, max_per_cat: int = MAX_PER_CAT):
    """[{"rel","category","mtime"}...(rel 名序)] —— 扩展白名单内的图片。"""
    cats = _scan(proj_dir, max_per_cat)
    out = []
    for cat_name, c in cats.items():
        for rel, _name, mtime, _size in c["files"]:
            if posixpath.splitext(rel)[1].lower() in IMG_EXTS:
                out.append({"rel": rel, "category": cat_name, "mtime": mtime})
    out.sort(key=lambda i: i["rel"])
    return out


def resolve_sub(proj_dir: str, sub):
    """open-folder 目标解析:sub 空 → 项目夹本身;否则单段类目名
    (字符集白名单 → realpath within → isdir)。非法/逃逸/不存在 → None。"""
    if not sub:
        return proj_dir
    if ("/" in sub or "\\" in sub or ".." in sub or sub.startswith(".")
            or any(ord(ch) < 0x20 for ch in sub) or not _SUB_RE.match(sub)):
        return None
    target = os.path.realpath(os.path.join(proj_dir, sub))
    if not ds_common.within(proj_dir, target) or not os.path.isdir(target):
        return None
    return target
