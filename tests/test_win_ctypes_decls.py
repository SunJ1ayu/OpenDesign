#!/usr/bin/env python3
"""Windows API 调用的**声明闸**:句柄不许被 ctypes 静默截成 32 位。

ctypes 不声明 `argtypes` 的话,把 Python int 按 `c_int`(32 位)传。
64 位 Windows 上 HWND/HANDLE 一旦超过 2³¹,消息就发给了一个不存在的窗口 ——
**拖不动、改不了大小、关不掉,而且哪儿都不报错**。这是最难查的那类坏法:
没有异常、没有日志,真机上只表现为"点了没反应"。

`bin/ds_shell_core.py` 里那段 Job 代码已经为同一件事补过声明,注释写得明明白白
(「不声明 argtypes,64 位句柄会被截成 32 位 ⇒ 关的是别的东西」)。
2026-08-17 四审 subdeepseek F2 逮到:`bin/ds_shell.py` 的 `SendMessageW` 漏了同一件事,
而它恰恰是这一版要交付的功能(无边框窗口的拖动/改大小)的**唯一**出口。

⇒ 这道闸不看谁写得对,只机械地问:**每个 windll 调用点,声明过没有。**
   那一层在 Linux 上一行都跑不到,所以只能静态问 —— 但静态问得出来。
"""
from __future__ import annotations

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = [
    os.path.join(ROOT, "bin", "ds_shell.py"),
    os.path.join(ROOT, "bin", "ds_shell_core.py"),
]

# 🔴 这道闸的第一版**扫不到它要抓的那一行**:真正的调用点长这样 ——
#     user32 = ctypes.windll.user32      ← DLL 先落进一个变量
#     user32.SendMessageW(...)           ← 再从变量上调
# 只认 `windll.<dll>.<fn>(` 的写法在 ds_shell_core.py 上一个都扫不到(那边用
# `ctypes.WinDLL(...)`),而 F2 那一行也正好漏在射程外 —— **闸问不出它要问的东西**。
# 所以先找出所有"绑着一个 DLL 的变量名",再扫这些变量上的调用。
HANDLE_VAR = re.compile(r"(\w+)\s*=\s*ctypes\.(?:windll\.\w+|WinDLL\s*\()")
DIRECT_CALL = re.compile(r"ctypes\.windll\.\w+\.(\w+)\s*\(")
DECL = re.compile(r"(\w+)\.argtypes\s*=")
RESTYPE = re.compile(r"(\w+)\.restype\s*=\s*([\w.]+)")


def _called_win_apis(src: str) -> set[str]:
    names = set(DIRECT_CALL.findall(src))
    for var in set(HANDLE_VAR.findall(src)):
        names |= set(re.findall(rf"\b{re.escape(var)}\.(\w+)\s*\(", src))
    return names

# 豁免:**逐个点名 + 写清理由**,不许写通配。
# (自动放行等于把这道闸悄悄拆掉 —— 和 S1a 那次 pip 自动回退是同一种病。)
EXEMPT = {
    # 参数是 (NULL, str, str, uint):没有一个是需要 64 位的句柄。
    # 第一个实参在代码里写死 None ⇒ ctypes 传 NULL 指针,不经过 int 截断那条路。
    "MessageBoxW",
    # 无参数。
    "ReleaseCapture",
}


class WinCtypesDecls(unittest.TestCase):

    def test_every_windll_call_declares_its_argtypes(self):
        missing = []
        for path in SOURCES:
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            called = _called_win_apis(src)
            declared = set(DECL.findall(src))
            self.assertTrue(called, f"{os.path.basename(path)} 一个 windll 调用都没扫到 "
                                    "—— 这道闸问不出东西了(写法变了?)")
            for fn in sorted(called - declared - EXEMPT):
                missing.append(f"{os.path.basename(path)}: {fn}")
        self.assertEqual([], missing,
                         "这些 Windows API 没声明 argtypes ⇒ 64 位句柄会被截成 32 位,"
                         "真机上表现为「点了没反应」且不报错:\n  " + "\n  ".join(missing))

    def test_the_exemption_list_is_not_a_back_door(self):
        """豁免清单里的名字必须**真的还在被调用** —— 不然它就是一张空头支票,
        下一个人往里加名字时会以为"这里本来就很宽"。(新闸双向验:S1a 那次
        `win-deps-audit.py` 剥后缀剥错、任何包都判缺失,补完包它还在喊才露馅。)"""
        called = set()
        for path in SOURCES:
            with open(path, encoding="utf-8") as fh:
                called |= _called_win_apis(fh.read())
        self.assertEqual(set(), EXEMPT - called,
                         f"豁免清单里有已经不存在的调用:{sorted(EXEMPT - called)} ⇒ 该删掉")


    def test_functions_that_declare_argtypes_also_declare_restype(self):
        """**只声明 argtypes 是半截活。**

        ctypes 的默认 `restype` 是 `c_int`(32 位有符号)。返回句柄、指针、或者
        窗口样式那种 64 位值的 API,不声明 restype 就会被**静默截断** ——
        和这道闸原本要防的 argtypes 截断是同一种坏法,只是走的返回那一路。

        2026-08-23 panel(submimo)逮到的:`GetWindowLongPtrW` 的返回值就是窗口
        现有的样式,截断了就等于读错;读错的样式再或上新位写回去 ⇒ **窗口变形**,
        而那正是 `test_window_native_styles.py` 的 s2 拼命想防住的后果 ——
        它从另一条路溜进来了,s2 拦不着。

        规则做成通用的:**声明了 argtypes 的,也必须声明 restype。**
        (返回 BOOL/void 的函数写 restype 也不亏 —— 显式比默认可靠。)
        """
        missing = []
        for path in SOURCES:
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            declared_args = set(DECL.findall(src))
            declared_ret = {name for name, _ in RESTYPE.findall(src)}
            for fn in sorted(declared_args - declared_ret):
                missing.append(f"{os.path.basename(path)}: {fn}")
        self.assertEqual([], missing,
                         "这些 API 声明了 argtypes 却没声明 restype ⇒ 返回值按 c_int "
                         "取,64 位的值被静默截断(读错的样式写回去 = 窗口变形):\n  "
                         + "\n  ".join(missing))

    def test_pointer_width_apis_return_a_pointer_wide_type(self):
        """`...LongPtrW` 这一族按定义返回**指针宽度**,restype 必须跟上。

        写成 `c_int` 就是上一条说的那种截断,而且它看起来"声明过了" ——
        比压根不声明更难发现。
        """
        wrong = []
        for path in SOURCES:
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            for name, rt in RESTYPE.findall(src):
                if "LongPtr" in name and rt not in ("ctypes.c_ssize_t", "ctypes.c_size_t"):
                    wrong.append(f"{os.path.basename(path)}: {name}.restype = {rt}")
        self.assertEqual([], wrong,
                         "指针宽度的 API 用了窄类型当 restype ⇒ 64 位上截断:\n  "
                         + "\n  ".join(wrong))


if __name__ == "__main__":
    unittest.main(verbosity=2)
