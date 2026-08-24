#!/usr/bin/env python3
"""0.94.0 的机械闸:**方案 B 默认关掉,只留在实验开关后面**。

由来(2026-08-24 业主真机):0.93.0 装上之后「打开全是白的什么都没有了」。

本地已核实到的事实(tracks/opendesign-native-frame/tasks.md 有全文):
  - 他装的确实是 0.93.0(发布物 digest 与本地 exe 逐字节一致);
  - 包里前端产物完好,且与 0.92 的包**逐字节相同**;
  - `ds_web.py` 在两版之间只改了 VERSION 注释;
  ⇒ 从"看得见"到"全白",唯一的功能性差量就是 `ds_shell.py` 的方案 B。

**为什么不直接猜一个修法**:方案 B 的 ctypes 类型声明、常量、WM_NCCALCSIZE
的两条 wParam 路都逐条读过,没有笔误 —— 病在方案 B 与 WebView2 的运行时交互,
而那一层 Linux 上一行都跑不到。0.92 与 0.93 连着两版都死在"把推论当结论发出去",
这一版不再赌:**默认路径退回 0.92 那套已被真机证明能用的代码**,方案 B 收进
一个默认关闭的实验开关,打开时额外写诊断日志 —— 一趟真机既能用、又能定位。

这道闸问的是这笔交易的每一头:
  - f1~f4  开关本身:默认必须是**关**,而且读不到环境时也必须是关(fail-safe);
  - f5~f7  三个会改变窗口边框计算的动作,**一个都不许出现在默认路径上**;
  - f8     开关必须写成正向 `if frame_experiment_on():`(f5~f7 的分析靠它成立);
  - f9     实验路径必须留下诊断:光知道"白了"没用,要知道白的时候窗口长什么样。

⚠️ **这道闸答不了"页面还画不画得出来"** —— 那一层只有 Windows 答得了。
它能答的是**更弱但真的能机械保证的那一条**:默认路径一个边框计算都不碰,
所以默认路径的行为就是 0.92 的行为,而 0.92 在业主机器上是好的。
"""
from __future__ import annotations

import ast
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, "bin", "ds_shell.py")
sys.path.insert(0, os.path.join(ROOT, "bin"))

FLAG_FN = "frame_experiment_on"

# 会**真的改变窗口非客户区尺寸**的东西。默认路径上一个都不许有。
FRAME_BITS = ("WS_CAPTION", "WS_THICKFRAME")


def _src() -> str:
    with open(SHELL, encoding="utf-8") as fh:
        return fh.read()


def _tree() -> ast.Module:
    return ast.parse(_src())


def _funcs(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    out: dict[str, ast.FunctionDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name not in out:
            out[node.name] = node
    return out


def _idents(node: ast.AST) -> set[str]:
    """代码里真正**读取**到的名字。只收 ctx=Load —— 常量定义的左手边不算"用了"
    (n_series 的 _idents 栽过这个坑,这里照抄它的结论)。"""
    out: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
            out.add(sub.id)
        elif isinstance(sub, ast.Attribute) and isinstance(sub.ctx, ast.Load):
            out.add(sub.attr)
    return out


def _code(node: ast.AST) -> str:
    """节点的**纯代码**文本:ast.unparse 天然丢注释,再手工剥掉 docstring。

    🔴 少了剥 docstring 这一步,f9 会**靠注释绿** —— 那个函数的 docstring 里
    正好写着 GetWindowRect / GetClientRect / EnumChildWindows 三个词。
    这个项目已经在"判据把注释当代码"上栽过三次(0.92 的 s3 第一版、R12b、n8 第一版),
    这是第四次。**是写红检 M9 时读出来的,不是红检先咬到的**;
    随后做了对照实验:f9 退回 ast.unparse 再跑 M9 → "判据全绿,这条变异下它是瞎的"。
    """
    import copy

    n = copy.deepcopy(node)
    body = getattr(n, "body", None)
    if isinstance(body, list) and body:
        first = body[0]
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            n.body = body[1:]
    if isinstance(getattr(n, "body", None), list) and not n.body:
        return ""
    return ast.unparse(n)


def _callee(call: ast.Call) -> str:
    f = call.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return ""


def _parents(root: ast.AST) -> dict:
    p = {}
    for node in ast.walk(root):
        for child in ast.iter_child_nodes(node):
            p[id(child)] = node
    return p


def _guarded_by_flag(node: ast.AST, root: ast.AST) -> bool:
    """这个节点是不是被 `if frame_experiment_on():` 的**真分支**包着。

    🔴 一层层往上走,而不是"函数里出现过这个 if 就算" —— 后者会被
    `if flag(): pass` + 危险动作写在外面 这种改法骗过去(变异 M3 咬它)。
    """
    parents = _parents(root)
    cur = node
    while id(cur) in parents:
        parent = parents[id(cur)]
        if isinstance(parent, ast.If) and FLAG_FN in _idents(parent.test):
            for stmt in parent.body:          # 只认真分支,orelse 不算
                if stmt is cur:
                    return True
        cur = parent
    return False


class FrameExperimentSwitch(unittest.TestCase):
    """f1~f4:开关本身。这四条是**真跑**的,不是读源码。"""

    def setUp(self):
        import ds_shell
        self.ds = ds_shell

    def _with_appdata(self, root: str):
        os.environ["LOCALAPPDATA"] = root

    def test_f1_switch_function_exists(self):
        self.assertTrue(
            hasattr(self.ds, FLAG_FN),
            f"ds_shell 里没有 {FLAG_FN}() —— 方案 B 就没有开关,"
            "等于 0.93 原样再发一次。")

    def test_f2_default_is_off(self):
        """**本单最重要的一条。** 业主什么都不做的时候,方案 B 必须是关的。"""
        old = os.environ.get("LOCALAPPDATA")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                self._with_appdata(tmp)          # 干净目录 = 没有标志文件
                self.assertFalse(
                    getattr(self.ds, FLAG_FN)(),
                    "标志文件不存在时 frame_experiment_on() 返回了真 ⇒ "
                    "方案 B 默认开着。0.93 真机就是这么白的。")
        finally:
            if old is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old

    def test_f3_flag_file_turns_it_on(self):
        """开关得真的打得开 —— 否则我永远拿不到诊断数据。"""
        old = os.environ.get("LOCALAPPDATA")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                self._with_appdata(tmp)
                d = Path(tmp) / self.ds.APP
                d.mkdir(parents=True, exist_ok=True)
                (d / self.ds.EXPERIMENT_FLAG).write_text("", encoding="utf-8")
                self.assertTrue(
                    getattr(self.ds, FLAG_FN)(),
                    f"标志文件 {self.ds.EXPERIMENT_FLAG} 就在 {d},"
                    "frame_experiment_on() 却还是假 —— 开关是坏的。")
        finally:
            if old is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old

    def test_f4_unreadable_environment_is_off_not_on(self):
        """读不到环境时必须**倒向关**。

        🔴 方向是有讲究的:猜错成"关"最多是没有动画(业主本来也没有);
        猜错成"开"是整个窗口白掉,他连界面都看不见。
        """
        tree = _tree()
        fn = _funcs(tree).get(FLAG_FN)
        self.assertIsNotNone(fn, f"{FLAG_FN} 不见了")
        handlers = [n for n in ast.walk(fn) if isinstance(n, ast.ExceptHandler)]
        self.assertTrue(
            handlers,
            f"{FLAG_FN}() 没有 try/except。它读环境变量和文件系统,"
            "抛出去就会把 shown 回调带走 —— 窗口一起来就崩。")
        for h in handlers:
            returns = [n for n in ast.walk(h) if isinstance(n, ast.Return)]
            self.assertTrue(
                returns and all(
                    isinstance(r.value, ast.Constant) and r.value.value is False
                    for r in returns),
                "except 分支必须 `return False`(倒向关)。"
                "返回真或者什么都不返回(None 也是假、但那是碰巧对)都不算。")


class FrameWorkStaysBehindTheSwitch(unittest.TestCase):
    """f5~f9:三个会改变窗口边框计算的动作,一个都不许落在默认路径上。"""

    @classmethod
    def setUpClass(cls):
        cls.tree = _tree()
        cls.funcs = _funcs(cls.tree)

    def test_f5_wndproc_install_is_behind_the_switch(self):
        """接管 WM_NCCALCSIZE 是方案 B 的核心动作,默认路径不许碰。"""
        entry = self.funcs.get("_apply_native_styles_and_frame")
        self.assertIsNotNone(entry, "_apply_native_styles_and_frame 不见了")
        calls = [n for n in ast.walk(entry)
                 if isinstance(n, ast.Call) and _callee(n) == "_install_wndproc"]
        self.assertTrue(
            calls, "入口里根本没有 _install_wndproc 调用 —— 方案 B 被整个删了?"
                   "本单要的是'收进开关',不是'删掉'(删了就永远查不出白屏的原因)。")
        for c in calls:
            self.assertTrue(
                _guarded_by_flag(c, entry),
                f"_install_wndproc 的调用不在 `if {FLAG_FN}():` 真分支里。\n"
                "0.93 真机结论:这个接管一旦默认生效,业主打开就是一片白。")

    def test_f6_frame_style_bits_are_behind_the_switch(self):
        """WS_CAPTION / WS_THICKFRAME 会真的改变非客户区尺寸。

        判的是**入口的分派**,不是那两个位在源码里出现过没有 ——
        它们当然还得在(实验路径要用),n2 守着那一头。
        """
        entry = self.funcs.get("_apply_native_styles_and_frame")
        self.assertIsNotNone(entry, "_apply_native_styles_and_frame 不见了")

        unguarded = []
        for node in ast.walk(entry):
            if not (isinstance(node, ast.Call)):
                continue
            name = _callee(node)
            # 贴五个位那条路(方案 B)必须在开关里;贴三个安全位那条不必。
            if name in ("_apply_native_styles", "_apply_native_styles_unsafe"):
                if not _guarded_by_flag(node, entry):
                    unguarded.append(name)
        self.assertEqual(
            [], unguarded,
            "下面这些调用会把 WS_CAPTION|WS_THICKFRAME 贴上窗口,却不在开关里:\n  "
            + "\n  ".join(unguarded) +
            "\n默认路径只许贴 0.92 那三个不参与绘制的位。")

    def test_f7_default_path_uses_fake_maximize(self):
        """默认路径必须用 Bounds 的"假最大化"。

        ⚠️ **这条与 n7 是一对,别把它读成 n7 被推翻了。**
        n7 说的是"想要放大动画就必须用 WindowState" —— 那句话今天仍然成立,
        只是它的适用范围缩到了**实验路径**。
        真最大化在没有 WM_NCCALCSIZE 接管时会连任务栏一起盖住
        (0.92 的注释里写着这个理由,D3 拆掉它的前提是接管生效 ——
        而 0.93 真机证明接管这条路现在不能默认走)。
        """
        fn = self.funcs.get("toggle_maximize")
        self.assertIsNotNone(fn, "toggle_maximize 不见了")

        maxi = [n for n in ast.walk(fn)
                if isinstance(n, ast.Attribute) and n.attr == "Maximized"]
        self.assertTrue(
            maxi, "toggle_maximize 里没有 WindowState.Maximized —— "
                  "实验路径的放大动画被删了(n7 守着它必须在)。")
        for node in maxi:
            self.assertTrue(
                _guarded_by_flag(node, fn),
                "真最大化(WindowState.Maximized)不在开关里。"
                "没有 NCCALCSIZE 接管时它会盖住任务栏。")

        bounds = [n for n in ast.walk(fn)
                  if isinstance(n, ast.Attribute) and n.attr == "Bounds"
                  and isinstance(n.ctx, ast.Store)]
        self.assertTrue(
            bounds,
            "默认路径没有设 form.Bounds ⇒ 开关关掉之后最大化按钮什么都不做。"
            "0.92 那份实现是现成的,照抄回来。")

    def test_f8_switch_is_written_in_the_positive_form(self):
        """开关必须写成 `if frame_experiment_on():`,不许 `if not ...:`。

        🔴 这不是洁癖:f5~f7 判的是"危险动作在不在真分支里"。写成否定式的话
        真分支装的是**默认路径**,那三条闸会**反过来放行**危险动作 ——
        闸还是绿的,产品是坏的。宁可多这一条,不要一个会撒谎的闸。
        """
        # 🔴 不能只看**最外层**是不是 `not`。0.95 之后条件长这样:
        #    `if frame_experiment_on() and not self._frame_gave_up:` —— 是个 BoolOp,
        #    于是"把开关取反"(`not frame_experiment_on() and …`)会从这条闸底下溜过去。
        #    红检 M7 当场照出来的:那条变异下 f8 全绿。
        #    正确的问法是:**整棵条件树里,有没有哪个 `not` 底下罩着这个开关**。
        bad = []
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.If):
                continue
            if FLAG_FN not in _idents(node.test):
                continue
            for sub in ast.walk(node.test):
                if (isinstance(sub, ast.UnaryOp) and isinstance(sub.op, ast.Not)
                        and FLAG_FN in _idents(sub.operand)):
                    bad.append(ast.unparse(node.test))
                    break
        self.assertEqual(
            [], bad,
            "开关被写成了否定式,f5~f7 会因此反向放行:\n  " + "\n  ".join(bad))

    def test_f9_experiment_path_leaves_diagnostics(self):
        """打开实验开关时必须把窗口的实际几何写进日志。

        0.93 那趟真机的教训:业主报"全白",而我手上**一个数字都没有** ——
        窗口多大、客户区多大、WebView2 那个子窗口还在不在、它的矩形是什么,
        全都不知道,于是只能再要一趟。这条闸就是不让那件事重演。
        """
        fn = self.funcs.get("_log_frame_diagnostics")
        self.assertIsNotNone(
            fn, "没有 _log_frame_diagnostics —— 开关打开也拿不到任何数据,"
                "业主白跑一趟。")
        # 🔴 问的是"**真的被调用了**",不是"名字在源码里出现过"。
        #    这条断言在同一个坑里栽过两次:
        #      ① 第一版扫 ast.unparse ⇒ 连 docstring 里写的名字都算(红检 M9 证实);
        #      ② 改成 _code() 之后仍然是子串匹配 ⇒ 后来给这些调用补了
        #         `user32.EnumChildWindows.argtypes = [...]`,名字又出现了,
        #         把调用整个删掉它照样绿(红检 M9 第二次照出来 —— 而那行 argtypes
        #         正是我自己为了修另一个 bug 加的:**加一道防线顺手拆了另一道**)。
        #    所以这里认 ast.Call 的被调方名字,属性赋值不算数。
        called = {_callee(n) for n in ast.walk(fn) if isinstance(n, ast.Call)}
        for must in ("GetWindowRect", "GetClientRect", "EnumChildWindows"):
            self.assertIn(
                must, called,
                f"诊断里没有 {must}。三样缺一不可:\n"
                "  窗口矩形 + 客户区矩形 ⇒ 看得出接管有没有把客户区铺满;\n"
                "  子窗口列表 ⇒ 看得出 WebView2 那块还在不在、矩形对不对"
                "(白屏最可能就死在这)。")

        entry = self.funcs.get("_apply_native_styles_and_frame")
        calls = [n for n in ast.walk(entry)
                 if isinstance(n, ast.Call) and _callee(n) == "_log_frame_diagnostics"]
        self.assertTrue(calls, "_log_frame_diagnostics 写了却没人叫。")
        for c in calls:
            self.assertTrue(
                _guarded_by_flag(c, entry),
                "诊断日志也必须在开关里 —— 默认路径不该为一个关着的实验写盘。")


if __name__ == "__main__":
    unittest.main()
