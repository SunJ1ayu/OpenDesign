"""搬运保真闸的共用件:搬运清单 + 从源文件精确取出某个顶层定义的源码。

track opendesign-structure-debt。**主 agent 亲写,执行腿逐字节 off-limits。**

为什么用 `ast` 而不是 `inspect.getsource`:取源码不需要 import 模块,
于是基线生成与校验都不受 import 副作用/循环依赖影响 —— 而"循环依赖"正是本单
要消灭的东西,判据自己不能依赖它。
"""
import ast
import hashlib
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(REPO, "bin")
BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "structure_moves_baseline.json")

# 搬运清单:每项 = (原模块, 新模块, 顶层定义名)。
# **这份清单就是本单的规格**;实现不许多搬也不许少搬。
MOVES = [
    # ── 第 ① 刀:taxonomy 规则表 → bin/ds_taxonomy.py ──────────────────────
    # 理由:4 个模块都在用它(ds_intake / ds_adopt / ds_web ×5 / ds_workspace),
    # 它是公共配置表,却寄居在"收件箱"里 —— 这是错位,也是循环依赖②的成因。
    ("ds_intake", "ds_taxonomy", "DEFAULT_TAXONOMY_PATH"),
    ("ds_intake", "ds_taxonomy", "USER_TAXONOMY_REL"),
    ("ds_intake", "ds_taxonomy", "_safe_rel_dir"),
    ("ds_intake", "ds_taxonomy", "_valid_taxonomy"),
    ("ds_intake", "ds_taxonomy", "load_taxonomy"),
    ("ds_intake", "ds_taxonomy", "suggest_category"),
    # ── 第 ② 刀:Windows 开文件夹/窗口置前 → bin/ds_openfolder.py ─────────
    # 理由:纯操作系统交互,与 HTTP 无关;且是全项目最难测的一块。
    # ⚠️ `Handler._open_folder` **不在清单里** —— 它是 HTTP 层(解析/鉴权/拼响应),
    # 留在 ds_web。边界画在「HTTP 语义 vs 操作系统语义」,不按行数切。
    #
    # 下面这两个"跟随常量"是 2026-08-02 panel-review 补进来的:subdeepseek 与 subkimi
    # **两腿独立命中**同一个洞 —— 它们随代码搬走了,却不在本清单里,于是逐字节闸和
    # "原模块不留副本"两条都不覆盖它们:实现者若改错这两行,三条判据全抓不住。
    # 补录时基线哈希取自**搬运前的 commit `39e7f4c`**(git show),不是取自搬完的工作树,
    # 否则又成了"实现的复印件"。
    ("ds_web", "ds_openfolder", "_FOLDER_WIN_CLASSES"),
    ("ds_web", "ds_openfolder", "_WIN_FOCUS"),
    ("ds_web", "ds_openfolder", "_pick_folder_window"),
    ("ds_web", "ds_openfolder", "_win_folder_windows"),
    ("ds_web", "ds_openfolder", "_win_activate"),
    ("ds_web", "ds_openfolder", "_win_focus_folder"),
    ("ds_web", "ds_openfolder", "_spawn_win_focus"),
    ("ds_web", "ds_openfolder", "_open_windows"),
    ("ds_web", "ds_openfolder", "_default_open_launcher"),
]


def module_path(mod: str) -> str:
    return os.path.join(BIN, mod + ".py")


def top_level_source(mod: str, name: str) -> str | None:
    """取 `mod` 里名为 `name` 的**顶层**定义(函数或赋值)的源码原文。

    找不到返回 None —— 调用方据此区分"还没搬过来"和"搬过来但被改了"。
    """
    path = module_path(mod)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src)
    for node in tree.body:                      # 只认顶层,嵌套定义随宿主一起搬
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name:
                return ast.get_source_segment(src, node)
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == name:
                    return ast.get_source_segment(src, node)
        elif isinstance(node, ast.AnnAssign):
            tgt = node.target
            if isinstance(tgt, ast.Name) and tgt.id == name:
                return ast.get_source_segment(src, node)
    return None


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
