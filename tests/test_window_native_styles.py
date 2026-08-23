#!/usr/bin/env python3
"""无边框窗口的**系统样式位闸**:窗口得先让 Windows 认它是正经窗口。

由来(2026-08-23 业主):「缩小按钮在页面上是直接消失,不会像成熟的产品一样有
向下缩小的动画,这个很重要,可以引导用户知道页面在底部」。

根因不是动画,是**身份**:`frameless=True` ⇒ pywebview 执行
`FormBorderStyle = None` ⇒ WinForms 的 `CreateParams` 把
`WS_SYSMENU / WS_MINIMIZEBOX / WS_MAXIMIZEBOX / WS_THICKFRAME / WS_CAPTION`
整批挂在 `if (formBorderStyle != None)` 底下一个都不发。Windows 的窗口待遇
(最小化动画、还原动画、系统菜单、Win+方向键)全是按这些位发的。

Electron 2014 年踩的是同一个坑(electron#751,当时的结论一字不差:
「问题是这个窗口没有被加上正确的样式」),补位就好、且实测**不冒边框**。

⇒ 这道闸问四件机器答得了的事:
   ① 常量值对不对(抄错一位 = 发给一个不存在的样式,而且不报错);
   ② 是**或上去**还是**整个覆盖**(覆盖会把窗口现有样式全清掉 ⇒ 窗口当场变形);
   ③ **有没有越界去碰会改变非客户区的位**(本单承诺"外观零变化",越界就作废);
   ④ 补位是不是**每次最小化之前都确保一遍**(pywebview 的 fullscreen 会改
      FormBorderStyle,那条路会重算样式、把我们加的位刷掉)。
   外加 A1:最小化之后托盘那条路必须先把窗口从最小化里捞出来再 Show。

按下去到底有没有动画 —— 那只有 Windows 真机答得了,已进真机清单。
"""
from __future__ import annotations

import ast
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, "bin", "ds_shell.py")


def _src() -> str:
    with open(SHELL, encoding="utf-8") as fh:
        return fh.read()


def _tree(src: str) -> ast.Module:
    return ast.parse(src)


def _funcs(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    """所有函数/方法,按名字索引(同名取第一个 —— 本文件里没有同名的)。"""
    out: dict[str, ast.FunctionDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name not in out:
            out[node.name] = node
    return out


def _calls(node: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(node) if isinstance(n, ast.Call)]


def _callee_name(call: ast.Call) -> str:
    """`user32.SetWindowLongPtrW(...)` -> "SetWindowLongPtrW";裸函数 -> 它的名字。"""
    f = call.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return ""


def _or_operands(node: ast.AST) -> set[str]:
    """把 `A | B | C` 摊平成 {"A","B","C"}(只收名字,数字字面量另算)。"""
    names: set[str] = set()
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        names |= _or_operands(node.left)
        names |= _or_operands(node.right)
    elif isinstance(node, ast.Name):
        names.add(node.id)
    elif isinstance(node, ast.Attribute):
        names.add(node.attr)
    return names


def _find_call(tree: ast.Module, name: str) -> ast.Call | None:
    for call in _calls(tree):
        if _callee_name(call) == name:
            return call
    return None


def _owning_func(tree: ast.Module, call: ast.Call) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and call in _calls(node):
            return node
    return None


# 🔴 值抄错一位不会报错,只会安静地不生效 —— 所以逐个对表。
# 出处:winuser.h。GWL_STYLE 是负数(-16),别写成 0x10。
EXPECTED_CONSTS = {
    "GWL_STYLE": -16,
    "WS_MINIMIZEBOX": 0x00020000,
    "WS_MAXIMIZEBOX": 0x00010000,
    "WS_SYSMENU": 0x00080000,
    "SWP_NOSIZE": 0x0001,
    "SWP_NOMOVE": 0x0002,
    "SWP_NOZORDER": 0x0004,
    "SWP_NOACTIVATE": 0x0010,
    "SWP_FRAMECHANGED": 0x0020,
}

# 🔴 **本单的边界,机械化。** 这几位会真的改变窗口的非客户区尺寸
# (Windows 要给边框留位置)⇒ 内容会被挤、边缘可能冒出一条线。
# 那是方案 B(接管 WM_NCCALCSIZE)的活,不是这一单的。
# 这一单对业主的承诺是"外观一个像素都不变",而那个承诺只有在
# **只贴不影响绘制的位**时才成立 —— 所以越界必须是红的,不是"顺手多修一条"。
FORBIDDEN_STYLES = {
    "WS_THICKFRAME": 0x00040000,
    "WS_CAPTION": 0x00C00000,
    "WS_BORDER": 0x00800000,
    "WS_DLGFRAME": 0x00400000,
    "WS_OVERLAPPEDWINDOW": 0x00CF0000,
}

CONST_DEF = re.compile(r"^\s*(_?)([A-Z][A-Z0-9_]+)\s*=\s*(-?(?:0[xX][0-9a-fA-F]+|\d+))\s*(?:#.*)?$",
                       re.M)


class WindowNativeStyles(unittest.TestCase):

    def setUp(self):
        self.src = _src()
        self.tree = _tree(self.src)
        self.funcs = _funcs(self.tree)
        self.consts = {name: int(val, 0)
                       for _, name, val in CONST_DEF.findall(self.src)}

    # ── s1 常量值 ────────────────────────────────────────────────
    def test_s1_style_constants_have_the_right_values(self):
        """抄错一位 = 设了一个别的位,而且哪儿都不报错(最难查的那类)。"""
        wrong = []
        for name, want in EXPECTED_CONSTS.items():
            got = self.consts.get(name)
            if got is None:
                wrong.append(f"{name}: 没定义")
            elif got != want:
                wrong.append(f"{name}: 写的是 {got:#x},winuser.h 是 {want:#x}")
        self.assertEqual([], wrong,
                         "窗口样式常量对不上 winuser.h ⇒ 设的是别的位,真机上表现为"
                         "「改了等于没改」且不报错:\n  " + "\n  ".join(wrong))

    # ── s2 或上去,不是覆盖 ──────────────────────────────────────
    def test_s2_style_is_or_ed_onto_the_existing_style_not_overwritten(self):
        """直接赋值会把窗口**现有**的样式全清掉 ⇒ 窗口当场变形/消失。"""
        setcall = _find_call(self.tree, "SetWindowLongPtrW")
        self.assertIsNotNone(setcall, "找不到 SetWindowLongPtrW 调用 —— 样式位根本没在补")
        self.assertGreaterEqual(len(setcall.args), 3,
                                "SetWindowLongPtrW 得是 (hwnd, GWL_STYLE, 新样式) 三个实参")

        owner = _owning_func(self.tree, setcall)
        self.assertIsNotNone(owner, "SetWindowLongPtrW 不在任何函数里?")
        got_names = {_callee_name(c) for c in _calls(owner)}
        self.assertIn("GetWindowLongPtrW", got_names,
                      "补样式位之前**没有先把旧样式读出来** ⇒ 那就是在覆盖,不是在补。")

        new_style = setcall.args[2]
        self.assertIsInstance(
            new_style, ast.BinOp,
            "传给 SetWindowLongPtrW 的新样式不是 `旧样式 | 要加的位` 这种或运算 ⇒ "
            "窗口原有的样式会被整个抹掉")
        self.assertIsInstance(new_style.op, ast.BitOr, "新样式必须是按位或(|)")

        added = _or_operands(new_style)
        for want in ("WS_MINIMIZEBOX", "WS_MAXIMIZEBOX", "WS_SYSMENU"):
            self.assertIn(want, added,
                          f"{want} 没被或进去。三个都要:MINIMIZEBOX 管动画,"
                          "SYSMENU 管系统菜单(且 MINIMIZEBOX 按 winuser.h 必须和它同在),"
                          "MAXIMIZEBOX 管 Win+↑ 那一组。")

    # ── s3 本单的边界 ───────────────────────────────────────────
    def test_s3_does_not_touch_styles_that_resize_the_non_client_area(self):
        """越界就作废「外观零变化」那句承诺 —— 那是方案 B 的活。"""
        hits = []
        for name, value in FORBIDDEN_STYLES.items():
            if re.search(rf"\b{name}\b", self.src):
                hits.append(f"{name}(出现在源码里)")
            if re.search(rf"0[xX]0*{value:X}\b", self.src):
                hits.append(f"{name} 的值 {value:#x}")
        self.assertEqual(
            [], hits,
            "这一单只许贴**不影响绘制**的样式位。下面这些会改变窗口非客户区的尺寸,"
            "内容会被挤、边缘可能冒出一条线 ⇒ 属于方案 B(接管 WM_NCCALCSIZE),"
            "要单独一单、单独一趟真机:\n  " + "\n  ".join(hits))

    # ── s4 SetWindowPos 的旗标 ──────────────────────────────────
    def test_s4_frame_change_is_announced_without_moving_or_stealing_focus(self):
        """改完样式不通知,Windows 不会重算;通知时顺手动了位置/焦点就是新 bug。"""
        poscall = _find_call(self.tree, "SetWindowPos")
        self.assertIsNotNone(poscall,
                             "改了 GWL_STYLE 却没有 SetWindowPos(SWP_FRAMECHANGED) ⇒ "
                             "Windows 不会重新算这个窗口的边框,改了可能不生效")
        flags = _or_operands(poscall.args[-1])
        for want in ("SWP_FRAMECHANGED", "SWP_NOMOVE", "SWP_NOSIZE",
                     "SWP_NOZORDER", "SWP_NOACTIVATE"):
            self.assertIn(want, flags,
                          f"SetWindowPos 的旗标里少了 {want}。FRAMECHANGED 是这次调用的"
                          "**目的**;另外四个 NO* 是保证它**只**重算边框 —— 少一个就会"
                          "顺手移动窗口 / 改大小 / 抢层级 / 抢焦点。")

    # ── s5 A1:托盘那条路要先把窗口捞出来 ────────────────────────
    def test_s5_show_window_restores_before_showing(self):
        """pywebview 的 show() = Form.Show() + Activate(),**不还原最小化**。

        窗口在最小化状态时,`SetForegroundWindow` 不会把它捞回来 ⇒ 业主点托盘图标、
        或再双击一次桌面图标,窗口都不回来(pywebview issue #1749 报的正是这条)。
        """
        fn = self.funcs.get("show_window")
        self.assertIsNotNone(fn, "Shell.show_window 不见了?")
        body = ast.get_source_segment(self.src, fn) or ""

        show_at = body.find(".show()")
        self.assertNotEqual(-1, show_at, "show_window 里没有 .show()?")

        restore_at = min(
            (i for i in (body.find("restore"), body.find("Normal")) if i != -1),
            default=-1)
        self.assertNotEqual(
            -1, restore_at,
            "show_window 里没有任何「把窗口从最小化里捞出来」的动作 ⇒ 缩小之后"
            "点托盘图标 / 再双击桌面图标,窗口回不来。")
        self.assertLess(
            restore_at, show_at,
            "还原动作写在 .show() **后面**了 —— 顺序反了等于没写:"
            "Show/Activate 对最小化窗口不生效,之后再还原也已经错过那一下。")

    # ── s6 每次最小化前都确保一遍 ───────────────────────────────
    def test_s6_styles_are_ensured_before_every_minimize(self):
        """只在开窗口时补一次是不够的。

        pywebview 的 fullscreen 那条路会改 `FormBorderStyle`,WinForms 会照
        `CreateParams` 重算窗口样式 —— 我们加的位会被安静地刷掉。补位很便宜
        (两次系统调用),所以每次最小化之前都确保一遍,坏不了、也不会被刷没。
        """
        setcall = _find_call(self.tree, "SetWindowLongPtrW")
        self.assertIsNotNone(setcall, "样式位根本没在补")
        ensure = _owning_func(self.tree, setcall)
        self.assertIsNotNone(ensure)

        fn = self.funcs.get("minimize")
        self.assertIsNotNone(fn, "WindowApi.minimize 不见了?")
        body = ast.get_source_segment(self.src, fn) or ""

        self.assertIn(
            ensure.name, body,
            f"minimize 里没有先叫一次 {ensure.name}() ⇒ 只要 pywebview 那边重算过"
            "一次窗口样式,我们补的位就没了,而业主看到的是「有时有动画有时没有」。")
        self.assertLess(
            body.find(ensure.name), body.find("Minimized"),
            "确保样式位写在**真正最小化之后**了 —— 顺序反了等于没补:"
            "这一次最小化仍然没有动画。")


if __name__ == "__main__":
    unittest.main(verbosity=2)
