#!/usr/bin/env python3
"""方案 B 的机械闸:**把系统窗口框架接回来,同时不让它画出来**。

由来(2026-08-23 业主):「缩小和放大的动画还是没有」—— 0.92.0 的方案 A
(只贴 `MINIMIZEBOX|MAXIMIZEBOX|SYSMENU`)**真机证伪**:位确实贴上了
(业主机器 `STYLE=0x360B0000` 逐位对得上,Win+方向键、系统菜单都回来了),
但动画一点没有。

根因是 0.92 **问错了问题**:动画归 `WS_CAPTION`/`WS_THICKFRAME` 那一族管。
三条独立证据(见 tracks/opendesign-native-frame/evidence/):
  ① Electron 2014 PR #800 与它 2026 今天的代码,都是 `WS_CAPTION` 打底,
     且要关时 CAPTION 与 THICKFRAME **一起关** ⇒ 上游把这两个当不可分的一对;
  ② WinFormedge(同栈 WinForms+WebView2)`FormBase.cs:390` 接管 `WM_NCCALCSIZE`;
  ③ 业主机器上 5 个有动画的窗口,CAPTION 与 THICKFRAME **全都同时有**。

⇒ 本单的交易是:**加回会改变非客户区的位,再接管 `WM_NCCALCSIZE` 把它的
   视觉影响抵消掉**。外观承诺仍然是"零像素变化",只是兑现方式变了。

这道闸问的就是这笔交易的两头都在:
  - 位加了没有(n1/n2)—— 防的是有人为"外观安全"又把它砍回 0.92 那样;
  - 抵消做了没有(n3~n5)—— 少了这半边,标题栏会**真的画出来**。

**这道闸答不了"业主按下去有没有动画"** —— 0.92 的教训就是七条静态判据全绿、
产品照样是坏的。那只有真机答得了,已进真机清单。
"""
from __future__ import annotations

import ast
import copy
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, "bin", "ds_shell.py")

# winuser.h,逐个对表。抄错一位**不会报错**,只会安静地设成别的位。
EXPECTED_CONSTS = {
    "GWL_STYLE": -16,
    "GWLP_WNDPROC": -4,
    "WM_NCCALCSIZE": 0x0083,
    "WS_CAPTION": 0x00C00000,
    "WS_THICKFRAME": 0x00040000,
    "WS_MINIMIZEBOX": 0x00020000,
    "WS_MAXIMIZEBOX": 0x00010000,
    "WS_SYSMENU": 0x00080000,
}

# 本单**必须**加进 GWL_STYLE 的位。少任何一个 = 退回 0.92 那个被证伪的规格。
REQUIRED_STYLE_BITS = ("WS_CAPTION", "WS_THICKFRAME",
                       "WS_MINIMIZEBOX", "WS_MAXIMIZEBOX", "WS_SYSMENU")


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


def _consts(src: str) -> dict[str, int]:
    pat = re.compile(
        r"^\s*([A-Z][A-Z0-9_]+)\s*=\s*(-?(?:0[xX][0-9a-fA-F]+|\d+))\s*(?:#.*)?$", re.M)
    return {m.group(1): int(m.group(2), 0) for m in pat.finditer(src)}


def _or_operands(node: ast.AST) -> set[str]:
    """`A | B | C` 摊平成名字集合。"""
    out: set[str] = set()
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        out |= _or_operands(node.left) | _or_operands(node.right)
    elif isinstance(node, ast.Name):
        out.add(node.id)
    elif isinstance(node, ast.Attribute):
        out.add(node.attr)
    return out


def _code(node: ast.AST) -> str:
    """节点的**纯代码**文本:ast.unparse 天然丢注释,再手工剥掉 docstring。

    🔴 别用 ast.get_source_segment —— 它带回注释,判据就会把注释里出现的名字
    当成"代码用了它"。这个项目已经栽过三次(0.92 的 s3 第一版、R12b、n8 第一版)。
    """
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


def _idents(node: ast.AST) -> set[str]:
    """代码里真正**读取**到的名字,不含注释、docstring,**也不含常量定义本身**。

    🔴 只收 `ctx=Load` 的 Name。第一版连赋值目标(`GWLP_WNDPROC = -4` 那个
    左手边)也收,于是红检 F4 把使用处换成字面量 `-4` 之后,判据**照样绿** ——
    因为常量定义还在,名字还在集合里。"定义了"不等于"用了"。
    """
    out: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
            out.add(sub.id)
        elif isinstance(sub, ast.Attribute) and isinstance(sub.ctx, ast.Load):
            out.add(sub.attr)
    return out


def _callee(call: ast.Call) -> str:
    f = call.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return ""


def _calls_named(node: ast.AST, name: str) -> list[ast.Call]:
    return [n for n in ast.walk(node) if isinstance(n, ast.Call) and _callee(n) == name]


class WindowNativeFrame(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _src()
        cls.tree = _tree()
        cls.funcs = _funcs(cls.tree)
        cls.consts = _consts(cls.src)

    # ── n1 常量对表 ────────────────────────────────────────────
    def test_n1_constants_match_winuser_h(self):
        """抄错一位不报错,只会安静地设成别的位 —— 只能逐个对表。"""
        for name, want in EXPECTED_CONSTS.items():
            self.assertIn(name, self.consts,
                          f"{name} 没定义。本单要用到它,别就地写字面量 —— "
                          "字面量没法对表,下一个人也看不出它是什么。")
            self.assertEqual(
                want, self.consts[name],
                f"{name} 的值和 winuser.h 对不上:代码 {self.consts.get(name):#x} "
                f"≠ 应为 {want:#x}。GWL_STYLE / GWLP_WNDPROC 是负数,别写成正的。")

    # ── n2 五个位一个都不能少(直接钉死 0.92 的错误规格)────────
    def test_n2_style_bits_include_caption_and_thickframe(self):
        """**这条是本单的核心。**

        0.92 只贴三个位、特意排除 CAPTION/THICKFRAME,真机证明那个规格是错的。
        谁要是为了"外观安全"再把这两位砍掉,这条必须红。
        """
        fn = self.funcs.get("_apply_native_styles_unsafe")
        self.assertIsNotNone(fn, "_apply_native_styles_unsafe 不见了")

        added: set[str] = set()
        for node in ast.walk(fn):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
                added |= _or_operands(node)

        for want in REQUIRED_STYLE_BITS:
            self.assertIn(
                want, added,
                f"{want} 没被或进 GWL_STYLE。五个位缺一不可:\n"
                "  CAPTION + THICKFRAME 才是动画那一族(0.92 缺的就是它们,已被真机证伪);\n"
                "  MINIMIZEBOX/MAXIMIZEBOX/SYSMENU 管 Win+方向键与系统菜单(0.92 已验有效)。\n"
                "证据:evidence/premise-attack-upstream-b.md 三条独立来源。")

    # ── n3 加了位就必须接管 NCCALCSIZE(否则标题栏会真的画出来)──
    def test_n3_caption_requires_nccalcsize_takeover(self):
        """本单的交易两头必须同时在。**只做前半边 = 窗口长出标题栏。**"""
        idents = _idents(self.tree)
        uses_caption = "WS_CAPTION" in idents
        handles_nc = "WM_NCCALCSIZE" in idents and "GWLP_WNDPROC" in idents
        self.assertEqual(
            uses_caption, handles_nc,
            "WS_CAPTION 与 WM_NCCALCSIZE 接管必须同生共死:\n"
            f"  用了 WS_CAPTION = {uses_caption}\n"
            f"  接管了 NCCALCSIZE = {handles_nc}\n"
            "只加位不接管 ⇒ Windows 会给这个窗口画一条真的标题栏,业主的外观当场变;\n"
            "只接管不加位 ⇒ 白接管,动画还是没有(0.92 的复刻)。")

    # ── n4 wParam 真分支必须吃掉非客户区且不回原 proc ──────────
    def test_n4_nccalcsize_true_branch_returns_zero(self):
        """P1 探针实测:`wParam` 真时 `return 0` ⇒ ClientSize == Size。

        要是这条分支还去 CallWindowProcW,原来那层会把标题栏的位置重新留出来,
        等于没接管 —— 而窗口看起来"正常",最难查。
        """
        fn = self.funcs.get("_wndproc")
        self.assertIsNotNone(
            fn, "_wndproc 不见了。窗口过程本体必须是一个具名方法 —— "
                "写成 lambda 或闭包的话,这道闸和下一个人都读不到它。")

        src_fn = _code(fn)
        self.assertIn("WM_NCCALCSIZE", src_fn,
                      "_wndproc 里没有 WM_NCCALCSIZE 分支")

        # 真分支里必须有 `return 0`,且该分支内不许调 CallWindowProcW
        found = False
        for node in ast.walk(fn):
            if not isinstance(node, ast.If):
                continue
            test_src = _code(node.test)
            if "WM_NCCALCSIZE" not in test_src:
                continue
            body_returns_zero = any(
                isinstance(s, ast.Return) and isinstance(s.value, ast.Constant)
                and s.value.value == 0
                for s in ast.walk(node) if isinstance(s, ast.Return))
            self.assertTrue(
                body_returns_zero,
                "WM_NCCALCSIZE 分支没有 `return 0`。P1 探针实测:返回 0 才会把"
                "标题栏那块非客户区吃掉(ClientSize 从 384 变成 400 == Size)。")
            self.assertEqual(
                [], _calls_named(node, "CallWindowProcW"),
                "WM_NCCALCSIZE 的接管分支里调了 CallWindowProcW —— "
                "原来那层会把标题栏的位置重新留出来,等于没接管,"
                "而且窗口看起来一切正常,是最难查的那种。")
            found = True
        self.assertTrue(found, "找不到 WM_NCCALCSIZE 的 if 分支")

    # ── n5 不接管的消息要交回原 proc,不是 DefWindowProc ────────
    def test_n5_other_messages_go_back_to_the_original_proc(self):
        """WinForms 自己那层还在下面,绕过它 = 悄悄弄坏一堆它负责的行为。"""
        fn = self.funcs.get("_wndproc")
        self.assertIsNotNone(fn)
        self.assertTrue(
            _calls_named(fn, "CallWindowProcW"),
            "_wndproc 没有把消息交回 CallWindowProcW。我们是挂在 WinForms 那层"
            "**上面**的第二层,不交回去 = WinForms 负责的事情全部静默失效。")
        self.assertEqual(
            [], _calls_named(fn, "DefWindowProcW"),
            "_wndproc 用了 DefWindowProcW —— 那会绕过 WinForms 那一层。"
            "子类化的规矩是交回**你替换掉的那个** proc,不是系统默认的。")

    # ── n6 回调对象必须活着(P1 的血泪细节)────────────────────
    def test_n6_wndproc_callback_is_kept_on_the_instance(self):
        """回调对象被 GC ⇒ Windows 回调进一片野内存 ⇒ **崩**,而且是随机时刻崩。"""
        src = self.src
        self.assertTrue(
            re.search(r"self\.\w*(?:hook|wndproc|proc)\w*\s*=\s*WNDPROC\(", src, re.I)
            or re.search(r"self\.\w*(?:hook|wndproc|proc)\w*\s*=\s*\w*WNDPROC\w*\(", src, re.I),
            "没看到把 WNDPROC(...) 的结果存到 self 上。存成局部变量的话,函数一返回"
            "它就可能被 GC —— 之后 Windows 每发一条消息都是在往野内存里跳。"
            "P1 探针里靠局部变量 hook 撑住只是因为它活到函数结束;实现里不行。")

    # ── n7 D3:最大化改回真的,别再自己设 Bounds ────────────────
    def test_n7_maximize_uses_window_state_not_bounds(self):
        """"假最大化"(自己算工作区设 Bounds)结构上不可能有放大动画。

        业主本轮原话是「缩小**和放大**的动画还是没有」—— 放大那半边就死在这里。
        """
        fn = self.funcs.get("toggle_maximize")
        self.assertIsNotNone(fn, "toggle_maximize 不见了")
        body = _code(fn)
        self.assertIn(
            "WindowState", body,
            "toggle_maximize 还没改成用 WindowState。自己设 Bounds 的'假最大化',"
            "系统压根不知道发生了最大化 ⇒ 永远没有放大动画,"
            "而这正是业主本轮点名的那一半。")
        self.assertNotIn(
            "form.Bounds = ", body,
            "toggle_maximize 里还在直接设 form.Bounds —— 假最大化没拆干净。")

    # ── n8 D3 连带:show_window 别把最大化窗口打回小窗 ──────────
    def test_n8_show_window_does_not_unmaximize(self):
        """0.92 那句注释「我们的最大化 WindowState 一直是 Normal ⇒ restore 幂等」

        在 D3 之后**不再成立**:restore() 会把最大化的窗口打回小窗。
        不一起改就是亲手退回 0.92 修好的那个 A1 bug。
        """
        fn = self.funcs.get("show_window")
        self.assertIsNotNone(fn, "show_window 不见了")

        restores = [n for n in ast.walk(fn)
                    if isinstance(n, ast.Call) and _callee(n) == "restore"]
        if not restores:
            return                       # 压根不 restore 也就无所谓打回小窗

        # 🔴 第一版这条只检查"函数体里提到过 Minimized",红检当场证明它**咬不动**:
        #    把 `if minimized:` 改成 `if True:` 它照样绿。真正要问的是
        #    **每一个 restore() 调用都被一个"条件里真的在问最小化"的 if 包着**。
        guarded: set[int] = set()
        for node in ast.walk(fn):
            if not isinstance(node, ast.If):
                continue
            cond = _code(node.test)
            if not re.search(r"[Mm]inimi", cond):
                continue                 # `if True:` 这种恒真条件不算数
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and _callee(sub) == "restore":
                    guarded.add(id(sub))

        for call in restores:
            self.assertIn(
                id(call), guarded,
                "show_window 里有一个 restore() 不在「判断是否最小化」的 if 里面。\n"
                "D3 把最大化改成真的之后,无条件 restore() 会把最大化的窗口"
                "打回小窗;而恒真的条件(if True)等于没判断。")


if __name__ == "__main__":
    unittest.main(verbosity=2)
