#!/usr/bin/env python3
"""注释里提到的名字必须真的存在(track opendesign-update-duplicate-facts)。

**为什么值得有这道闸**:上一单(`opendesign-startup-not-blocked-by-update`)自己立的规矩之一
是"界面和注释不许说谎",而它第 3 轮把 `machine_blocker` 改名成 `why_not_auto` 之后,
`bin/ds_web.py` 里有两处注释仍写着旧名字 —— 规矩立了,自己当场就破了一次,
而且是外部评审腿在第 4 轮才报出来的(还只报了 1 处,另 1 处是我全仓扫出来的)。

注释里的过期名字不会让任何东西变红,但它是**下一个人会当真的假话**:他去 grep
`machine_blocker`,什么也找不到,于是要么以为注释描述的是别的东西,要么以为代码被删过。

**这道闸只查一种、而且是误报率为零的那一种**:形如 `ds_<模块>.<名字>` 的**限定引用**。
开这道闸之前先量过全仓:26 处命中里 25 处是注释在写**文件名**(`ds_xxx.py`)、
1 处是真的过期名字(就是 `machine_blocker` 那条)⇒ 排掉扩展名与带尾下划线的前缀之后,
**0 误报、1 真命中**(读数在本单 design.md)。

🔴 **不查裸名字**(比如注释里光写 `machine_blocker` 不带模块前缀)。中文注释里大量出现的是
概念词不是标识符,连坐进来误报率会高到把人养成"一律 --no-verify"的习惯 ——
那比没有这道闸更坏。裸名字那一半靠下面第二条题单点钉住,不假装能通用。
"""
import ast
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")

#: 注释里写 `ds_web.py` 是在说一个**文件**,不是在引用一个属性。
_EXTENSIONS = {"py", "ps1", "md", "json", "txt", "exe", "sh", "js", "ts", "mjs"}
# 大写开头的名字(类名 / 常量)也要查:2026-09-20 外审 subcursor 指出原来的
# `[a-z_]` 看不见 `ds_web.Handler` 这种。实测把大写放进来之后全仓**仍然 0 误报**,
# 等于白捡的覆盖面。
_QUALIFIED = re.compile(r"\b(ds_[a-z0-9_]+)\.([A-Za-z_][A-Za-z0-9_]*)\b")


def _py_files():
    return sorted(f for f in os.listdir(BIN) if f.endswith(".py"))


def _names_defined_in(path):
    """这个模块里**出现过**的所有名字(定义、赋值、形参、属性、import)。

    故意放宽到"出现过"而不是"顶层定义":这道闸要抓的是**已经不存在**的名字,
    宁可漏报也不误报 —— 一个会误报的守卫,三天之内就会被绕过去。
    """
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


def _comment_chunks(src):
    """这个文件里的全部注释文本:`#` 注释 + 所有 docstring。

    docstring 也算注释 —— 本仓库最长的那些"为什么这么写"的说明都住在 docstring 里,
    而上一单被抓到的两处假话,一处正是 docstring 旁边的块注释。
    """
    chunks = []
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node)
            if doc:
                chunks.append(doc)
    for line in src.splitlines():
        i = line.find("#")
        # 粗判"这个 # 在字符串里吗":前面的引号成对才算真注释。够用,且宁可漏不可误。
        if i >= 0 and line[:i].count('"') % 2 == 0 and line[:i].count("'") % 2 == 0:
            chunks.append(line[i:])
    return chunks


class CommentReferences(unittest.TestCase):

    def test_qualified_module_references_in_comments_exist(self):
        defined = {f[:-3]: _names_defined_in(os.path.join(BIN, f)) for f in _py_files()}
        stale = []
        for f in _py_files():
            with open(os.path.join(BIN, f), encoding="utf-8") as fh:
                src = fh.read()
            for chunk in _comment_chunks(src):
                for mod, attr in _QUALIFIED.findall(chunk):
                    if attr in _EXTENSIONS or attr.endswith("_"):
                        continue
                    if mod in defined and attr not in defined[mod]:
                        stale.append("bin/%s 的注释写着 %s.%s,而 bin/%s.py 里没有这个名字"
                                     % (f, mod, attr, mod))
        self.assertEqual(sorted(set(stale)), [],
                         "🔴 注释引用了不存在的名字 —— 下一个人会当真:\n  "
                         + "\n  ".join(sorted(set(stale))))

    def test_machine_blocker_is_gone(self):
        """单点钉:`machine_blocker` 2026-09-20 已改名 `why_not_auto`。

        上面那道通用闸看得见 `ds_auto_update.machine_blocker`,看不见光写 `machine_blocker`
        的那一处(`ds_web.py:1342`)。裸名字没有通用查法,所以这里就老实地钉这一个名字,
        不假装它是通用规则。**这条题的寿命 = 这个旧名字被彻底忘掉之前。**
        """
        hits = []
        for f in _py_files():
            with open(os.path.join(BIN, f), encoding="utf-8") as fh:
                for n, line in enumerate(fh, 1):
                    if "machine_blocker" in line:
                        hits.append("bin/%s:%d: %s" % (f, n, line.strip()))
        self.assertEqual(hits, [], "🔴 旧名字还在:\n  " + "\n  ".join(hits))


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
