#!/usr/bin/env python3
"""0.95 的机械闸:**方案 B 挪到"用的时候"才装,而且装完不对就自己退回去**。

由来(2026-08-24 业主真机日志):

    17:54:47 窗口打开:http://127.0.0.1:8766/?shell=1
    17:54:48 [窗口] 窗口过程已挂上(尚未收到消息)
    17:54:48 [窗口] 非客户区接管已生效(收到第一条 WM_NCCALCSIZE)
    17:54:48 [窗口] 已把 CAPTION/THICKFRAME/... 贴回窗口

**一条报错都没有,然后画面是白的。** 业主答"打开就白"。
⇒ 方案 B **完全按设计跑通了**,结果却是错的 —— 排掉"没装上/抛异常"一整族。

新假设(**未证实,别写成结论**):**时机撞车**。动窗口边框发生在窗口打开后
**一秒之内**,而那正是 WebView2 还在初始化、还在算自己该多大的时候。
0.92 同样早却没事,因为它贴的三个位**不改变非客户区**。

这一版的做法与它对应,而且**无论假设对不对都有收获**:

  - 挪晚了**还白** ⇒ 不是时机,是方案 B 和这套 WebView2 根本不兼容;
  - 挪晚了**好了** ⇒ 是时机,而且业主当场拿到动画。

配一层自动撤销,把最坏情况从"白屏"降级成"没有动画"。
⚠️ **这一层抓不住"几何正常但就是不画"** —— 别把它说成"保证不白"。
"""
from __future__ import annotations

import ast
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, "bin", "ds_shell.py")
FLAG_FN = "frame_animation_on"


def _src() -> str:
    with open(SHELL, encoding="utf-8") as fh:
        return fh.read()


def _funcs(tree):
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name not in out:
            out[node.name] = node
    return out


def _callees(node) -> set[str]:
    """这个函数里**够得着**的方法名 —— 调用和引用都算。

    🔴 只收 `ast.Call` 是不够的,而且那个洞正好开在最要命的地方:
    `ensure_native_styles` 的写法是 `self._on_ui(self._apply_native_styles_and_frame)`
    —— 那是**引用**不是调用,只看 Call 的话 h1 的禁止清单对 0.93/0.94 的写法
    **完全是瞎的**(集合里只有 `_on_ui`,禁的那几个名字一个都不在,于是空过)。
    是实现改好之后 h1 报"连安全位都不贴了"才暴露出来的。
    """
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            out.add(f.attr if isinstance(f, ast.Attribute)
                    else f.id if isinstance(f, ast.Name) else "")
        elif isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load):
            out.add(n.attr)
    return out


class FrameAppliedLate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _src()
        cls.tree = ast.parse(cls.src)
        cls.funcs = _funcs(cls.tree)

    def test_h1_shown_path_does_not_touch_the_window_frame(self):
        """**本单的核心。** 窗口刚出来那条路上,一个边框动作都不许有。

        `ensure_native_styles` 是挂在 `shown` 上的(main 里),0.93 就是从这里
        在窗口打开一秒内动了边框。这一版它只许贴**不改变非客户区**的安全位。
        """
        fn = self.funcs.get("ensure_native_styles")
        self.assertIsNotNone(fn, "ensure_native_styles 不见了")
        called = _callees(fn)
        for banned in ("_apply_native_styles_and_frame", "_install_wndproc",
                       "_apply_native_styles"):
            self.assertNotIn(
                banned, called,
                f"`shown` 那条路上还在叫 {banned} —— 0.93 就是这么白的。\n"
                "窗口刚出来的一秒钟是 WebView2 最忙的时候,这条路只许贴安全位。")
        self.assertIn(
            "_apply_safe_styles", called,
            "`shown` 路上连安全位都不贴了 —— 0.92 修好的系统菜单/Win+方向键会丢。")

    def test_h2_frame_is_applied_on_first_real_use(self):
        """挪晚了不等于不做:业主点缩小/最大化时必须装上,否则永远没有动画。"""
        for name in ("minimize", "toggle_maximize"):
            fn = self.funcs.get(name)
            self.assertIsNotNone(fn, f"{name} 不见了")
            self.assertIn(
                "_apply_native_styles_and_frame", _callees(fn),
                f"{name} 里没有装框架那一步 —— 挪晚了之后就再也没人装了,"
                "动画永远不会出现。")

    def test_h3_apply_is_immediately_followed_by_a_measurement(self):
        """装完必须**当场量一次**。

        0.93 那趟的教训:业主报"全白"而我手上一个数字都没有,只能再要一趟。
        """
        fn = self.funcs.get("_apply_native_styles_and_frame")
        self.assertIsNotNone(fn, "_apply_native_styles_and_frame 不见了")
        called = _callees(fn)
        self.assertTrue(
            {"_frame_looks_sane", "_log_frame_diagnostics"} & called,
            "装完框架之后没有任何测量 —— 又会变成'白了但没有数字'。")

    def test_h4_bad_measurement_triggers_an_automatic_revert(self):
        """量出来不对必须**自动退回去**,而不是留给业主一个白窗口。"""
        fn = self.funcs.get("_apply_native_styles_and_frame")
        called = _callees(fn)
        self.assertIn(
            "_revert_native_frame", called,
            "没有自动撤销 —— 那这一版对业主的最坏情况还是白屏,和 0.93 一样。")

        revert = self.funcs.get("_revert_native_frame")
        self.assertIsNotNone(revert, "_revert_native_frame 没写")

        # 🔴 撤销必须**两头都做**:解挂窗口过程 + 去掉那两个样式位。
        #    只做一半 = 位还在而没人接管 NCCALCSIZE ⇒ 窗口长出一条真的标题栏,
        #    那是比白屏更难解释的坏状态(n3 讲的就是这对同生共死)。
        rsrc = ast.unparse(revert)
        self.assertIn(
            "uninstall_wndproc", _callees(revert),
            "撤销时没有解挂窗口过程 —— 回调还在,而样式位没了。")
        self.assertRegex(
            rsrc, r"WS_CAPTION|WS_THICKFRAME",
            "撤销时没有去掉 CAPTION/THICKFRAME —— 位还在而接管没了,"
            "窗口会长出一条真的标题栏。")
        self.assertIn(
            "SetWindowPos", _callees(revert),
            "改完样式没有 SWP_FRAMECHANGED 通知 —— Windows 不会重算边框,撤销等于没做。")

    def test_h5_revert_is_remembered_so_it_does_not_retry_forever(self):
        """撤销过一次之后,这一轮就别再装了。

        不记住的话:业主每点一次缩小 → 装上 → 量出不对 → 撤销,
        每次都闪一下,而且日志被刷满。
        """
        src = self.src
        self.assertRegex(
            src, r"_frame_gave_up",
            "没有'已经放弃过'的记号 —— 会每点一次就装一次、撤一次。")
        fn = self.funcs.get("_apply_native_styles_and_frame")
        self.assertRegex(
            ast.unparse(fn), r"_frame_gave_up",
            "装框架那一步没有先看'放弃过没有'。")

    def test_h6_the_measurement_never_breaks_the_window(self):
        """量归量,**绝不能因为量不出来就把窗口搞坏**。

        `_frame_looks_sane` 拿不到数据时必须**倾向于'没问题'** ——
        撤销是有代价的(闪一下、没有动画),不能因为一次读不到就误撤。
        """
        fn = self.funcs.get("_frame_looks_sane")
        self.assertIsNotNone(fn, "_frame_looks_sane 没写")
        handlers = [n for n in ast.walk(fn) if isinstance(n, ast.ExceptHandler)]
        self.assertTrue(handlers, "_frame_looks_sane 没有 try/except —— 它跑在 UI 线程上。")
        for h in handlers:
            rets = [n for n in ast.walk(h) if isinstance(n, ast.Return)]
            self.assertTrue(
                rets and all(
                    isinstance(r.value, ast.Constant) and r.value.value is True
                    for r in rets),
                "量不出来的时候必须 `return True`(当成没问题)。"
                "误撤的代价是白闪一下 + 没动画,而它换不来任何好处。")


if __name__ == "__main__":
    unittest.main()
