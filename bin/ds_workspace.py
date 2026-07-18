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
DEFAULT_MAX_DEPTH = 6   # 相对项目根的最大路径段数(类目算 1 段);可经 workspace.json galleryDepth 覆盖
DEPTH_MIN, DEPTH_MAX = 2, 8  # galleryDepth 钳位区间
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
    # 可选:projectsDepth(depth2 track)。1=项目直接在 projectsDir 下(默认);
    # 2=中间隔一层"分组"夹(年份/客户/地区……中性容器,不写死语义)。
    # null=未配置(同 projectsDir);非 bool 的 int 且 ∈{1,2} 才合法,否则整体降级
    # (与 root/projects 同款严格:坏配置=功能下线,不静默猜)。bool 单独拒:
    # isinstance(True, int) 为真,JSON true 会伪装成 1。
    depth = raw.get("projectsDepth")
    if depth is None:
        depth = 1
    elif isinstance(depth, bool) or not isinstance(depth, int) or depth not in (1, 2):
        return None
    # 可选:galleryDepth(图墙/文件区扫描深度)。与 projectsDepth 的严格不同——
    # 这是纯 display 旋钮(不参与项目解析/安全),坏值不该让整份配置下线:
    # 合法非 bool int 钳到 [DEPTH_MIN, DEPTH_MAX],缺失/坏类型回落 DEFAULT_MAX_DEPTH。
    gd = raw.get("galleryDepth")
    if isinstance(gd, bool) or not isinstance(gd, int):
        gallery_depth = DEFAULT_MAX_DEPTH
    else:
        gallery_depth = max(DEPTH_MIN, min(DEPTH_MAX, gd))
    root = os.path.realpath(root)
    if not os.path.isdir(root):
        return None
    return {"root": root, "projects": projects, "projectsDir": projects_dir,
            "projectsDepth": depth, "galleryDepth": gallery_depth}


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


def _dir_entries(path):
    """path 下可作项目/分组的一级子目录 [(name, DirEntry)] 名序:点号开头跳过
    (同 _scan);名字不过 PROJECT_NAME_RE 者跳过(路由 key 字符集寻址不到,
    列了也点不开);symlink 目录跳过(follow_symlinks=False,外指零风险)。"""
    try:
        entries = sorted(os.scandir(path), key=lambda e: e.name)
    except OSError:
        return []
    out = []
    for ent in entries:
        if ent.name.startswith(".") or not PROJECT_NAME_RE.match(ent.name):
            continue
        try:
            if not ent.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue
        out.append((ent.name, ent))
    return out


def project_folders(cfg):
    """自动发现的项目夹 [(key, realpath)] 序;projects-dir 缺失 → []。
    projectsDepth=1(默认):项目夹直接在 projects_root 一级,key=文件夹名。
    projectsDepth=2(depth2 track):一级=分组夹(年份/客户等中性容器),
    二级=项目夹,key=`分组:项目名`(`:` 为 NTFS 禁字,Windows 真机零碰撞;
    _SEG_RE 本就放行,URL 链 unquote 后照常寻址),分组名序→项目名序;
    空分组无条目、分组下散文件忽略,两级同过 _dir_entries 闸。
    key 直接被 project_dir ②级"名==key"消费,寻址链零改动。"""
    proot = projects_root(cfg)
    if proot is None:
        return []
    if cfg.get("projectsDepth", 1) != 2:
        return [(name, os.path.realpath(ent.path))
                for name, ent in _dir_entries(proot)]
    out = []
    for gname, gent in _dir_entries(proot):
        for pname, pent in _dir_entries(gent.path):
            out.append((f"{gname}:{pname}", os.path.realpath(pent.path)))
    return out


def _scan(proj_dir: str, max_per_cat: int, max_depth: int = DEFAULT_MAX_DEPTH):
    """单次遍历:{类目名: {"files": [(rel_posix, name, mtime, size)], "capped": bool}}。
    类目 = 项目夹下一级目录;顶层散文件归 ""。点号开头的目录/文件跳过;
    深度(相对项目根的路径段数)> max_depth 不进。
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
            _walk_cat(bucket(ent.name), ent.name, ent.path, 1, max_per_cat, max_depth)
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


def _walk_cat(cat, rel_dir, abs_dir, depth, max_per_cat, max_depth):
    try:
        entries = sorted(os.scandir(abs_dir), key=lambda e: e.name)
    except OSError:
        return
    for ent in entries:
        if ent.name.startswith(".") or not _SEG_RE.match(ent.name):  # 字符集闸(M2)
            continue
        if ent.is_file(follow_symlinks=False):
            if depth + 1 <= max_depth:
                _add(cat, rel_dir, ent, max_per_cat)
        elif ent.is_dir(follow_symlinks=False) and depth + 1 < max_depth:
            _walk_cat(cat, posixpath.join(rel_dir, ent.name), ent.path,
                      depth + 1, max_per_cat, max_depth)
        if cat["capped"]:
            return


def overview(proj_dir: str, recent_n: int = 8, max_per_cat: int = MAX_PER_CAT,
             max_depth: int = DEFAULT_MAX_DEPTH):
    """{"categories": [{"name","count","capped","latest_mtime"}...(按名序;
    latest_mtime=类目最新文件 mtime,capped 时 None)],
    "recent": [{"name","category","mtime","size"}...(mtime 降序,前 recent_n)]}"""
    cats = _scan(proj_dir, max_per_cat, max_depth)
    # latest_mtime=类目活跃度(cockpit);capped 时名序截断后 max 不可信 → None 宁缺勿假
    categories = [{"name": name, "count": len(c["files"]), "capped": c["capped"],
                   "latest_mtime": (max(f[2] for f in c["files"])
                                    if c["files"] and not c["capped"] else None)}
                  for name, c in sorted(cats.items()) if c["files"] or c["capped"]]
    allf = [(mtime, name, cat_name, size)
            for cat_name, c in cats.items()
            for (_rel, name, mtime, size) in c["files"]]
    allf.sort(key=lambda t: (-t[0], t[1]))
    recent = [{"name": name, "category": cat_name, "mtime": mtime, "size": size}
              for mtime, name, cat_name, size in allf[:recent_n]]
    return {"categories": categories, "recent": recent}


def images(proj_dir: str, max_per_cat: int = MAX_PER_CAT,
           max_depth: int = DEFAULT_MAX_DEPTH):
    """[{"rel","category","mtime"}...(rel 名序)] —— 扩展白名单内的图片。"""
    cats = _scan(proj_dir, max_per_cat, max_depth)
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
