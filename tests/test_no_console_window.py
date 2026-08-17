#!/usr/bin/env python3
"""**无控制台窗口闸**:GUI 程序发起的子进程,不许弹出黑窗口。

业主 2026-08-17 装完 0.89.0 的第一句话:「为什么打开这个软件还会跳出命令行呢」。
两个黑窗口(网关一个、工作台一个),而且**关掉一个就等于杀掉一条腿** ——
他关掉网关那个,界面当场报"断开连接"。无边框窗口刚把唯一的出口焊死在右上角三个
按钮上,旁边却杵着两个一关就坏事的窗口。

根因不是"某一行漏了个参数",是**每个调用点各自决定平台标志**:
`_spawn` 记得写 `creationflags`(但只写了半套),`_kill_tree` 的 taskkill 一个字没写。
这个仓库为**同一种病**已经付过一次学费 —— ctypes 的 `argtypes`:
`ds_shell_core` 那处写对了、`ds_shell` 那处漏了,拖到四审才逮到
(见 `tests/test_win_ctypes_decls.py` 的开头)。

⇒ 这道闸不看谁写得对,只机械地问:**`bin/` 下每个子进程创建点,是不是走了那个
   唯一来源 `spawn_kwargs()`。** 走不了的要在**调用点旁边**写一行
   `# no-console-exempt: <为什么它弹不出窗口>`。
   (问"走没走唯一来源"而不是"带没带某个标志":带没带是结果,各写各的才是病。)

射程边界(说清楚,免得被当成比它强的东西):
  · 它问的是"标志有没有传",**不是"Windows 有没有听我的"** —— 后者只有真机答得了;
  · 它只扫 `bin/*.py` 的字面调用;经由第三方库拉起的进程(nanobot 的 3 个 MCP 工具服务)
    不在射程内。那 3 个由 MCP 库自己带 `CREATE_NO_WINDOW`(`mcp/os/win32/utilities.py`),
    **是别人替我们守的,不是我们守的** —— 换了库要重新确认。
"""
from __future__ import annotations

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")

# 子进程创建点。`Popen` 之外的几个最终都走 Popen,但**豁免要逐个说**,
# 所以这里全都扫,不做"反正它内部会走 Popen"的推理。
SPAWN_CALL = re.compile(r"subprocess\.(Popen|run|call|check_call|check_output)\s*\(")

# 豁免标记:写在**调用点自己那一行(或紧邻的注释里)**,不放在远处的名单里。
#
# 🔴 第一版是个 `{(文件名, 第几个调用): 理由}` 的字典 —— **自审当场毙掉**:
#    谁在前面插一个新的 subprocess 调用,序号就整体后移,豁免会静静地盖到
#    下一个**不该**豁免的调用点头上;而"双向验"只查得出"名单比代码多",
#    查不出错位。远处按序号索引的名单是埋着等人踩的东西。
#    写在调用点旁边则:不可能错位、理由就在读代码的人眼前、也不存在"过期条目"。
EXEMPT_MARK = "no-console-exempt:"


def _sources() -> list[str]:
    return sorted(f for f in os.listdir(BIN) if f.endswith(".py"))


def _load_core():
    """加载 `bin/ds_shell_core.py`。

    🔴 第一版用 `spec_from_file_location` 想"不污染 sys.path",结果它 `import ds_common`
    时找不到同目录的兄弟模块,整条判据**红在 ModuleNotFoundError 上** ——
    红在自己身上等于没红检过。`bin/` 是个平铺目录,老老实实把它放进 sys.path。
    """
    import sys

    if BIN not in sys.path:
        sys.path.insert(0, BIN)
    import ds_shell_core

    return ds_shell_core


def _enclosing_def(src: str, pos: int) -> str:
    """包住 `pos` 这个调用点的那个 `def` 的整段函数体。

    🔴 闸的第一版问的是**调用点的实参里有没有 `creationflags=`** —— 它红在了
    已经写对的代码上:`_spawn` 是把参数塞进一个 dict 再 `**kwargs` 展开的,
    调用点上一个字都看不见。**闸要问的是"有没有走那个唯一来源",不是"有没有把字
    打在这一行上"** —— 后者是在规定代码长什么样,不是在守不变量。
    """
    head = src.rfind("\ndef ", 0, pos)
    method = src.rfind("\n    def ", 0, pos)
    at = max(head, method)
    if at < 0:
        return src[:pos]
    indent = len(src[at + 1:src.index("def ", at)])
    j = at + 1
    while True:
        nl = src.find("\n", j)
        if nl < 0:
            return src[at:]
        line = src[j:nl]
        if j > at + 1 and line.strip() and (len(line) - len(line.lstrip())) <= indent \
                and line.lstrip().startswith(("def ", "class ", "@")):
            return src[at:j]
        j = nl + 1


class NoConsoleWindow(unittest.TestCase):
    def test_every_spawn_site_goes_through_the_one_source(self):
        """每个子进程创建点,平台参数都必须来自那个唯一来源 `spawn_kwargs()`。

        为什么这么问而不是问"带没带 CREATE_NO_WINDOW":带没带是**结果**,
        各写各的才是**病**。只要还允许调用点自己拼,下一个人就会漏一位,
        而漏了本机一条判据都不会红(那一位只在 Windows 上有意义)。

        豁免:在调用点上方 3 行内写 `# no-console-exempt: <为什么它弹不出窗口>`。
        """
        naked = []
        for name in _sources():
            with open(os.path.join(BIN, name), encoding="utf-8") as fh:
                src = fh.read()
            lines = src.splitlines()
            for m in SPAWN_CALL.finditer(src):
                lineno = src.count("\n", 0, m.start())          # 0 起
                near = "\n".join(lines[max(0, lineno - 3):lineno + 1])
                if EXEMPT_MARK in near:
                    reason = near.split(EXEMPT_MARK, 1)[1].strip()
                    self.assertTrue(reason, f"{name}:{lineno + 1} 的豁免标记没写理由")
                    continue
                if "spawn_kwargs" not in _enclosing_def(src, m.start()):
                    naked.append(f"{name}:{lineno + 1}")
        self.assertEqual([], naked,
                         "这些子进程创建点没走 spawn_kwargs() ⇒ 平台标志又回到各调用点"
                         "自己拼了,Windows 上漏一位就是一个黑窗口,而业主关掉它"
                         "就杀掉那个进程:\n  " + "\n  ".join(naked))

    def test_the_flag_values_are_the_real_windows_ones(self):
        """数值必须是 Windows 真值,而且写死在实现里。

        🔴 这条堵的是一条**假绿**路线:Linux 的 `subprocess` 里没有这两个常量,
        实现若写成 `getattr(subprocess, "CREATE_NO_WINDOW", 0)`,本机拿到 0 ——
        而 0 和"没设"一模一样,上面那条闸和 c23 会全部转绿,真机照样弹窗口。
        所以数值**写死在判据里**,不从被测模块导入。
        """
        core = _load_core()
        for attr, want in (("CREATE_NO_WINDOW", 0x08000000),
                           ("CREATE_NEW_PROCESS_GROUP", 0x00000200),
                           ("WINDOWS_SPAWN_FLAGS", 0x08000200)):
            got = getattr(core, attr, None)
            self.assertEqual(want, got,
                             f"{attr} = {got!r},应为 {want:#x}。"
                             "取 0 或缺失都会让本机全绿而真机照弹黑窗口")


if __name__ == "__main__":
    unittest.main()
