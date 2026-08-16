#!/usr/bin/env python3
"""发货代码里「这个名字根本不存在」的静态闸。

2026-08-16 业主真机(D:\\AI\\OpenDesign,0.88.0):填完 key 之后**每一次打开**都是

    File "ds\\bin\\ds_shell.py", line 202, in start_backend
      missing = core.missing_env_refs(json.load(f), env)
    NameError: name 'env' is not defined. Did you mean: 'envs'?

一个重构漏改的名字(`env` → `envs`),把装好的应用变成了开不了机。

为什么五段总跑全绿、四审三腿 PASS、17 份收据都没碰过它:
  ① 那一行在 `if "网关" in plan["start"]` 里 —— **只有有 key 的机器才执行**,
     而判据机上没有 key.txt,走的永远是另一条;
  ② `bin/ds_shell.py` 那层在 Linux 上一条行为判据都跑不了(pywebview / pystray /
     WebView2 要 Windows 桌面会话)⇒ 已有的 test_ds_shell_wiring.py 是 AST 静态闸,
     它只问「有没有调用 service_envs / 传没传 lock_port」,不问名字存不存在。
Python 只在**执行到**那一行时才抛 NameError ⇒ 行为判据够不着的分支里,一个拼错的
名字可以一路绿着出厂。这就是这道闸要堵的洞。

它**不问**跑起来对不对(那是行为判据的活),只问一件机器答得了的事:
**每个被读到的名字,在这个模块里到底存不存在。**

只用标准库 `symtable`,不引 pyflakes:装了包才跑的闸,在没装的解释器上会整块 SKIP,
而「没跑被印成绿」是本仓库栽过三次的假绿形态(见 tests/run-all.sh 文件头)。
落地当天拿 pyflakes 3.4.0 对过一遍(29 个 bin/*.py + 全部 tests/*.py):两者结论一致
—— 同一条 `ds_shell.py:202`,零误报、无遗漏。
"""
from __future__ import annotations

import ast
import builtins
import glob
import os
import symtable
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 发货的 python:装机之后真的在业主机器上跑的那些。
SHIPPED = ["bin/*.py", "installer/*.py"]


def _module_bindings(top: symtable.SymbolTable, tree: ast.AST) -> set[str]:
    """模块顶层真正**建立**了的名字(赋值 / import / def / class)。

    只算「建立」,不算「读到」:顶层一句 `print(nope)` 也会在符号表里留下 `nope`,
    把它当成绑定,就等于替一个不存在的名字作保。
    """
    names = {
        s.get_name()
        for s in top.get_symbols()
        if s.is_assigned() or s.is_imported() or s.is_namespace() or s.is_declared_global()
    }
    # 函数里 `global X` 再赋值,也是在给模块建名字 —— 顶层符号表看不见它。
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            names.update(node.names)
    return names


def _undefined(scope: symtable.SymbolTable, bindings: set[str], chain: tuple[str, ...]):
    for sym in scope.get_symbols():
        # is_global():这个名字在本作用域里没有绑定,运行时要去模块/内置里找。
        # 找不到 = 执行到那一行就是 NameError。
        if not (sym.is_global() and sym.is_referenced()):
            continue
        name = sym.get_name()
        if name in bindings or hasattr(builtins, name) or name.startswith("__"):
            continue
        yield "→".join(chain + (scope.get_name(),)), name
    for child in scope.get_children():
        yield from _undefined(child, bindings, chain + (scope.get_name(),))


class ShippedNamesExist(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = sorted(
            p for pat in SHIPPED for p in glob.glob(os.path.join(ROOT, pat))
        )

    def test_n1_the_gate_actually_has_files_to_look_at(self):
        """空扫描是最安静的假绿:路径改了名,这道闸会一直"全绿"。"""
        self.assertGreaterEqual(len(self.files), 20,
                                f"发货 python 只扫到 {len(self.files)} 个,路径多半改了")
        self.assertIn(os.path.join(ROOT, "bin", "ds_shell.py"), self.files)

    def test_n2_no_star_imports_to_blind_the_gate(self):
        """`from x import *` 会让"这个名字哪来的"无从判断 ⇒ 只能放过整片名字。
        本仓库现在一处都没有;真要加,就得先想清楚这道闸怎么办。"""
        offenders = []
        for path in self.files:
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=path)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
                    offenders.append(f"{os.path.relpath(path, ROOT)}:{node.lineno}")
        self.assertEqual([], offenders, f"星号 import 会让本闸失明:{offenders}")

    def test_n3_every_name_read_by_shipped_code_exists(self):
        """这一条就是 08-16 真机那次开不了机。"""
        bad = []
        for path in self.files:
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            tree = ast.parse(src, filename=path)
            top = symtable.symtable(src, path, "exec")
            bindings = _module_bindings(top, tree)
            rel = os.path.relpath(path, ROOT)
            for child in top.get_children():
                for where, name in _undefined(child, bindings, ()):
                    bad.append(f"{rel}: {where}() 里读了 `{name}`,但这个名字不存在")
        self.assertEqual([], bad, "发货代码里有读不到的名字(执行到就是 NameError):\n"
                                 + "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
