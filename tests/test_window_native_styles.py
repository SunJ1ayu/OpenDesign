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


def _code_identifiers(tree: ast.Module) -> set[str]:
    """源码里**真正被当作标识符用**的名字。

    🔴 第一版这道闸是拿正则扫整个文件的文本 —— 于是我在实现里写下
    「`WS_THICKFRAME` 会改非客户区尺寸,所以这一单不加它」这句**正当的注释**,
    闸当场红了。带误报的闸最坏的地方不是烦:它会逼出「把话说得含糊一点好过闸」
    的习惯,而那正是这道闸想拦的方向。⇒ 只问代码,不问注释和文档字符串。
    """
    names: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            names.add(n.id)
        elif isinstance(n, ast.Attribute):
            names.add(n.attr)
    return names


def _int_literals(tree: ast.Module) -> set[int]:
    """代码里的整数字面量(躲开注释,也躲开 docstring —— 那些是 str)。"""
    return {n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, int)
            and not isinstance(n.value, bool)}


def _body_without_docstring(fn: ast.FunctionDef) -> list[ast.stmt]:
    body = fn.body
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    return body


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

# 🔴 **2026-08-23 修订(track opendesign-native-frame):`WS_THICKFRAME` 与
# `WS_CAPTION` 从这份禁止清单里移出去了。** 这是动判卷防线,理由必须留在这儿:
#
#   原来禁它们,是因为 0.92.0 对业主的承诺是"外观一个像素都不变",而当时
#   我认定那个承诺只有"只贴不影响绘制的位"才成立。**真机把这个规格证伪了**:
#   位确实贴上了(业主机器 STYLE=0x360B0000 逐位对得上),动画一点没有 ——
#   因为动画恰恰归 CAPTION/THICKFRAME 那一族管。
#
#   三条独立证据(tracks/opendesign-native-frame/evidence/):Electron 2014 PR #800
#   与它今天的代码都是 CAPTION 打底且与 THICKFRAME 同生共死;WinFormedge(同栈)
#   接管 WM_NCCALCSIZE;业主机器上 5 个有动画的窗口两位全有。
#
#   ⚠️ **这不是放水。** 保护"外观零变化"的责任**搬到了更强的地方**:
#   tests/test_window_native_frame.py 的 n2(五个位一个都不能少)与
#   n3(加了 CAPTION 就必须接管 NCCALCSIZE,否则标题栏会真的画出来)。
#   原来这条只能一刀切禁止,**问不出"加了位但忘了抵消"这个真实的失败形态**;
#   n3 问得出。
#
# 下面留下的三个仍然该禁:它们是 CAPTION 的**拆散写法或过宽写法**,
# 用它们等于绕开 n2 那份显式清单(WS_OVERLAPPEDWINDOW 一把带进 5 个位,
# 谁都看不出到底要了哪些)。
FORBIDDEN_STYLES = {
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

        # 🔴 红检 N2 逮到的洞:只问「是不是或运算 + 三个位在不在」是不够的 ——
        #    把 `style |` 删掉之后剩下的 `WS_A | WS_B | WS_C` **照样是或运算、
        #    照样含三个位**,而那正是最危险的那种坏法(窗口现有样式被整个清掉 ⇒
        #    当场变形)。所以还得问一句:读出来的旧样式,有没有真的被或回去。
        added = _or_operands(new_style)
        old_style_var = None
        for node in ast.walk(owner):
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and any(_callee_name(c) == "GetWindowLongPtrW"
                            for c in _calls(node))):
                old_style_var = node.targets[0].id
        self.assertIsNotNone(
            old_style_var,
            "GetWindowLongPtrW 的返回值没被接进一个变量 ⇒ 读了等于没读")
        self.assertIn(
            old_style_var, added,
            f"新样式里没有 `{old_style_var}`(读出来的旧样式)⇒ 这是**覆盖**不是**补**:"
            "窗口现有的样式会被整个抹掉,真机上当场变形。")

        for want in ("WS_MINIMIZEBOX", "WS_MAXIMIZEBOX", "WS_SYSMENU"):
            self.assertIn(want, added,
                          f"{want} 没被或进去。三个都要:MINIMIZEBOX 管动画,"
                          "SYSMENU 管系统菜单(且 MINIMIZEBOX 按 winuser.h 必须和它同在),"
                          "MAXIMIZEBOX 管 Win+↑ 那一组。")

    # ── s3 本单的边界 ───────────────────────────────────────────
    def test_s3_does_not_touch_styles_that_resize_the_non_client_area(self):
        """禁止 CAPTION 的拆散/过宽写法 —— 要哪几位必须显式列出来,由 n2 对表。

        (2026-08-23:CAPTION/THICKFRAME 本身已移出禁止清单,理由见
        FORBIDDEN_STYLES 上方那段。保护外观的责任搬到了 n2/n3。)
        """
        idents = _code_identifiers(self.tree) | set(self.consts)
        literals = _int_literals(self.tree)
        hits = []
        for name, value in FORBIDDEN_STYLES.items():
            if name in idents:
                hits.append(f"{name}(代码里用到了这个名字)")
            if value in literals:
                hits.append(f"{name} 的值 {value:#x}(代码里出现了这个字面量)")
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

        🔴 **这条的第一版是瞎的**(红检 N5):它拿 `body.find("Normal")` 和
        `body.find(".show()")` 比字符位置 —— 而我自己在函数开头的注释里写着
        「WindowState 一直是 Normal」,那个 "Normal" 的位置永远比 `.show()` 早,
        于是把 restore 挪到 show 后面它照样绿。**判据被它要守的那段代码的注释骗了**,
        和 s3 第一版是同一个病:拿文本搜索冒充代码结构。改用 ast 行号。
        """
        fn = self.funcs.get("show_window")
        self.assertIsNotNone(fn, "Shell.show_window 不见了?")

        at: dict[str, int] = {}
        for call in _calls(fn):
            name = _callee_name(call)
            if name in ("restore", "show"):
                at.setdefault(name, call.lineno)

        self.assertIn("show", at, "show_window 里没有 .show()?")
        self.assertIn(
            "restore", at,
            "show_window 里没有任何「把窗口从最小化里捞出来」的动作 ⇒ 缩小之后"
            "点托盘图标 / 再双击桌面图标,窗口回不来。")
        self.assertLess(
            at["restore"], at["show"],
            "还原动作写在 .show() **后面**了 —— 顺序反了等于没写:"
            "Show/Activate 对最小化窗口不生效,之后再还原也已经错过那一下。")

    # ── s6 每次最小化前都确保一遍 ───────────────────────────────
    def test_s6_styles_are_ensured_before_every_minimize(self):
        """只在开窗口时补一次是不够的。

        pywebview 的 fullscreen 那条路会改 `FormBorderStyle`,WinForms 会照
        `CreateParams` 重算窗口样式 —— 我们加的位会被安静地刷掉。补位很便宜
        (两次系统调用),所以每次最小化之前都确保一遍,坏不了、也不会被刷没。
        """
        fn = self.funcs.get("minimize")
        self.assertIsNotNone(fn, "WindowApi.minimize 不见了?")

        # 🔴 第一版把「做 SetWindowLongPtrW 的那个函数」直接当成「minimize 该叫的
        #    那个函数」——**自审 F-G 把补位拆成「兜异常的外层 + 干活的内层」之后
        #    这个假设当场不成立了**,判据红在一个完全正确的实现上。
        #    ⇒ 别锚在某一个函数名上,问的是**可达性**:minimize 叫的那个入口,
        #      顺着调用链走得到 SetWindowLongPtrW 就行,拆几层都不关判据的事。
        entry_at, entry_name = None, None
        for call in _calls(fn):
            name = _callee_name(call)
            if "native_styles" in name:
                entry_at, entry_name = call.lineno, name
                break
        self.assertIsNotNone(
            entry_at,
            "minimize 里没有先叫一次补样式位的函数 ⇒ 只要 pywebview 那边重算过"
            "一次窗口样式,我们补的位就没了,而业主看到的是「有时有动画有时没有」。")

        reached: set[str] = set()
        frontier = [entry_name]
        while frontier:
            name = frontier.pop()
            if name in reached:
                continue
            reached.add(name)
            f = self.funcs.get(name)
            if f is not None:
                frontier += [_callee_name(c) for c in _calls(f)]
        self.assertIn(
            "SetWindowLongPtrW", reached,
            f"minimize 叫的 {entry_name}() 顺着调用链走不到 SetWindowLongPtrW ——"
            "它没有在补样式位,只是名字像。")

        minimize_at = next(
            (n.lineno for n in ast.walk(fn)
             if isinstance(n, ast.Assign)
             and isinstance(n.value, ast.Attribute) and n.value.attr == "Minimized"),
            None)
        self.assertIsNotNone(minimize_at, "minimize 里没有把 WindowState 设成 Minimized?")
        self.assertLess(
            entry_at, minimize_at,
            "确保样式位写在**真正最小化之后**了 —— 顺序反了等于没补:"
            "这一次最小化仍然没有动画。")


    # ── s7 贴样式位绝不能拖累「最小化」本身 ─────────────────────
    def test_s7_applying_styles_can_never_break_minimize_itself(self):
        """**自审 F-G。** minimize() 是先叫一遍补位、再设 WindowState=Minimized。

        补位那一句要是把异常抛出去,后面那行就跑不到 ⇒ **业主按下缩小按钮毫无反应**。
        拿「缩小」这个功能本身去赌「缩小的动画」,是这一单最不该犯的错 ——
        新加的那点好处,不许把本来好用的东西弄坏。

        `_on_ui` 那层的 except 也不算数:它印的是「回不到 UI 线程」,而这里失败的
        原因五花八门(缺 API / 句柄没了 / 权限),那句话只会把真机排查带偏。
        """
        setcall = _find_call(self.tree, "SetWindowLongPtrW")
        self.assertIsNotNone(setcall, "样式位根本没在补")

        fn = self.funcs.get("minimize")
        self.assertIsNotNone(fn, "WindowApi.minimize 不见了?")
        called = {_callee_name(c) for c in _calls(fn)}
        entry_names = [n for n in called if "native_styles" in n]
        self.assertTrue(
            entry_names,
            "minimize 里没有叫任何补样式位的函数(s6 应该已经红了)")

        entry = self.funcs.get(entry_names[0])
        self.assertIsNotNone(entry, f"找不到 {entry_names[0]} 的定义")

        body = _body_without_docstring(entry)
        self.assertEqual(
            1, len(body),
            f"{entry.name} 的函数体不是「整个包在一个 try 里」—— 只要有一条语句"
            "落在 try 外面,它就可能把异常抛给 minimize,那一次缩小就没了。")
        self.assertIsInstance(
            body[0], ast.Try,
            f"{entry.name} 的函数体没有包在 try 里 ⇒ 贴样式位失败会连带把"
            "「缩小」本身弄坏(按下去毫无反应)。")

        caught = []
        for h in body[0].handlers:
            if h.type is None:
                caught.append("bare")
            elif isinstance(h.type, ast.Name):
                caught.append(h.type.id)
        self.assertTrue(
            any(c in ("bare", "Exception", "BaseException") for c in caught),
            f"{entry.name} 的 except 只接住了 {caught} —— 接不住的那些照样会"
            "把「缩小」带走。这里要的就是宽口径地兜住。")


if __name__ == "__main__":
    unittest.main(verbosity=2)
