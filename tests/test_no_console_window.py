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
    2026-08-17 亲读那份库确认:主路径带(第 173 行),但它有**两层 fallback 会把这一位
    丢掉**(第 182 行 `except Exception` 整个不带标志重来、第 219 行同理)。
    触发面很窄(带标志的 CreateProcess 得先抛异常),但"别人替我们守"守的是什么形状,
    到此为止是查清楚的,不是推的。

  · 而"扫得到"本身有前提:扫描器只认字面的 `subprocess.X(`。**换个写法它就瞎了**,
    而瞎了的表现是**全绿**(不是报警)—— 所以下面第三条闸专门守它自己的射程。
"""
from __future__ import annotations

import ast
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")

# 子进程创建点。`Popen` 之外的几个最终都走 Popen,但**豁免要逐个说**,
# 所以这里全都扫,不做"反正它内部会走 Popen"的推理。
SPAWN_CALL = re.compile(r"subprocess\.(Popen|run|call|check_call|check_output)\s*\(")
SPAWN_ATTRS = {"Popen", "run", "call", "check_call", "check_output"}

# 豁免标记:写在**调用点自己那一行(或紧邻的注释里)**,不放在远处的名单里。
#
# 🔴 第一版是个 `{(文件名, 第几个调用): 理由}` 的字典 —— **自审当场毙掉**:
#    谁在前面插一个新的 subprocess 调用,序号就整体后移,豁免会静静地盖到
#    下一个**不该**豁免的调用点头上;而"双向验"只查得出"名单比代码多",
#    查不出错位。远处按序号索引的名单是埋着等人踩的东西。
#    写在调用点旁边则:不可能错位、理由就在读代码的人眼前、也不存在"过期条目"。
EXEMPT_MARK = "no-console-exempt:"

# 扫描器看不见的起进程写法。**它们不是"另一种风格",是让上面那条闸静静地变瞎的写法** ——
# 而瞎掉的表现是全绿。所以把"别用这些写法"本身立成不变量,谁要用就在调用点旁边说理由。
#
# 发现渠道:2026-08-17 那轮四审里 subkimi 断线前的半截日志(它正要问"闸的射程到哪儿")。
# 又一次印证「失败腿的日志也要读」—— 这条不在任何一份交上来的裁决里。
BLIND_FORMS = (
    (re.compile(r"^\s*from\s+subprocess\s+import\b", re.M),
     "`from subprocess import Popen` ⇒ 之后写 `Popen(...)`,扫描器认的是 `subprocess.` 前缀"),
    (re.compile(r"^\s*import\s+subprocess\s+as\s+\w+", re.M),
     "`import subprocess as sp` ⇒ 之后写 `sp.Popen(...)`,同上"),
    (re.compile(r"\bos\.(system|popen|spawn\w*)\s*\("),
     "os.system / os.popen / os.spawn* 会自己起进程,而上面那条闸一个字都看不见"),
    (re.compile(r"\bos\.startfile\s*\("),
     "os.startfile 交给 shell 去开,弹不弹窗口不归我们决定 —— 要逐个说清楚"),
    # ↓ 三条腿各自补上来的(两条独立命中前两项)。它们**长得像自己人**:
    #   `subprocess.getoutput` 明明带 `subprocess.` 前缀,却不在闸① 的五个函数名里,
    #   于是两道闸都不管它 —— 而它在 Windows 上经 cmd.exe 起进程,照弹。
    (re.compile(r"\bsubprocess\.(getoutput|getstatusoutput)\s*\("),
     "subprocess.getoutput/getstatusoutput 走 shell(Windows 上是 cmd.exe),"
     "却不在闸① 认的五个函数名里 —— 两道闸中间的缝"),
    (re.compile(r"\basyncio\.create_subprocess_(exec|shell)\s*\("),
     "asyncio 那套起进程接口,闸① 的 `subprocess.` 前缀完全看不见"),
    (re.compile(r"\bos\.(execv?[lpe]*|posix_spawn\w*)\s*\("),
     "os.exec*/posix_spawn:Windows 上没有真正的 exec 语义,CPython 用起新进程实现"),
)


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


def _exemption(lines: list[str], lineno: int) -> str | None:
    """这个调用点的豁免理由;没有标记返回 `None`,标记没写理由返回 `""`。

    🔴 三审同时指出的两个洞,病根是同一个"就近 3 行"窗口:
      ① **豁免会串到隔壁调用点** —— 一行标记会顺带豁免它下方 3 行内的**另一个**
         创建点。这正是本文件开头自述"按序号索引的名单"被毙掉的那个病,
         被 3 行窗口缩小后请了回来。
      ② **`no-console-exempt:` 后面一个字不写也能过** —— 老实现拿的是
         "窗口里标记之后的全部文本",里面还有下一行代码,`.strip()` 当然非空。
         **判据自己在撒谎:它写着"必须给理由",实际上不给也放行。**
    ⇒ 现在只认两处:调用点**自己那一行**的行尾注释,或**紧贴其上**的连续注释块
      (遇到第一个非注释行就停)。两者之间隔着任何一行代码,豁免就够不着。
    """
    own = lines[lineno]
    block: list[str] = []
    i = lineno - 1
    while i >= 0 and lines[i].lstrip().startswith("#"):
        block.append(lines[i])
        i -= 1
    for text in (own, "\n".join(reversed(block))):
        if EXEMPT_MARK in text:
            tail = text.split(EXEMPT_MARK, 1)[1]
            return tail.replace("#", " ").strip()
    return None


def _uses_the_one_source(call: ast.Call, func: ast.AST | None, src: str) -> bool:
    """**这一次调用**的平台参数是不是来自 `spawn_kwargs()`。

    🔴 三条评审腿独立命中同一处:老实现问的是"包住它的那个 def 里出现过
    `spawn_kwargs` 这几个字吗"。于是**同一个函数里再加一个裸调用就白拿豁免**
    (第一个合法调用替它作了保),函数外的模块级调用点更是拿到整段文件头、
    永远绿。**闸问的必须是这次调用,不是它的邻居。**

    实现用 `ast` 而不是正则找边界:今天已经栽过两次"正则找不准边界"
    (箭头函数的 `>`),Python 有现成的、精确的答案就别再猜。

    🔴 更早还栽过一次相反方向的:**第一版问的是"调用点实参里有没有
    `creationflags=`"**,于是红在了已经写对的代码上(`_spawn` 把参数塞进 dict 再
    `**kwargs` 展开,调用点上一个字都看不见)。所以这里对 `**名字` 要回到函数里
    追一步 —— 既不能只看这一行的字面,也不能宽到"函数里提过就算"。
    """
    seg = ast.get_source_segment(src, call) or ""
    if "spawn_kwargs" in seg:
        return True
    # `subprocess.Popen(argv, **kwargs)` 这种:去它所在的函数里看 kwargs 喂过什么。
    star = [kw.value.id for kw in call.keywords
            if kw.arg is None and isinstance(kw.value, ast.Name)]
    if not star or func is None:
        return False
    fsrc = ast.get_source_segment(src, func) or ""
    return any("spawn_kwargs" in line and name in line
               for name in star for line in fsrc.splitlines())


def _walk_with_owner(tree: ast.AST):
    """产出 (节点, 包住它的函数节点或 None)。"""
    def rec(node, owner):
        for child in ast.iter_child_nodes(node):
            nxt = child if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else owner
            yield child, owner
            yield from rec(child, nxt)
    yield from rec(tree, None)


class NoConsoleWindow(unittest.TestCase):
    def test_every_spawn_site_goes_through_the_one_source(self):
        """每个子进程创建点,平台参数都必须来自那个唯一来源 `spawn_kwargs()`。

        为什么这么问而不是问"带没带 CREATE_NO_WINDOW":带没带是**结果**,
        各写各的才是**病**。只要还允许调用点自己拼,下一个人就会漏一位,
        而漏了本机一条判据都不会红(那一位只在 Windows 上有意义)。

        豁免:在调用点自己那一行、或紧贴它上方的注释块里写
        `# no-console-exempt: <为什么它弹不出窗口>`(理由不许空着)。
        """
        naked = []
        for name in _sources():
            with open(os.path.join(BIN, name), encoding="utf-8") as fh:
                src = fh.read()
            lines = src.splitlines()
            for node, func in _walk_with_owner(ast.parse(src)):
                if not (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr in SPAWN_ATTRS
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "subprocess"):
                    continue
                lineno = node.lineno - 1                        # 0 起
                reason = _exemption(lines, lineno)
                if reason is not None:
                    self.assertTrue(reason, f"{name}:{lineno + 1} 的豁免标记没写理由")
                    continue
                if not _uses_the_one_source(node, func, src):
                    naked.append(f"{name}:{lineno + 1}")
        self.assertEqual([], naked,
                         "这些子进程创建点没走 spawn_kwargs() ⇒ 平台标志又回到各调用点"
                         "自己拼了,Windows 上漏一位就是一个黑窗口,而业主关掉它"
                         "就杀掉那个进程:\n  " + "\n  ".join(naked))

    def test_the_gate_can_see_every_spawn_site(self):
        """守**上面那条闸自己的射程**:`bin/` 里不许有它看不见的起进程写法。

        为什么单立一条:上面那条闸失效的方式不是报错,是**安静地扫不到**。
        `from subprocess import Popen` 之后的 `Popen(...)`、`os.system(...)`、
        `os.spawnv(...)` —— 每一条都能起出一个黑窗口,而闸①一声不吭地全绿。
        **一个查不到东西的检查和一个通过的检查,在收据上长得一模一样。**

        豁免用的是同一个标记(调用点旁边写理由),所以真需要时不会把人堵死,
        但**必须逐个说清楚为什么它弹不出窗口**。
        """
        blind = []
        for name in _sources():
            with open(os.path.join(BIN, name), encoding="utf-8") as fh:
                src = fh.read()
            lines = src.splitlines()
            for pat, why in BLIND_FORMS:
                for m in pat.finditer(src):
                    lineno = src.count("\n", 0, m.start())      # 0 起
                    reason = _exemption(lines, lineno)
                    if reason is not None:
                        self.assertTrue(reason, f"{name}:{lineno + 1} 的豁免标记没写理由")
                        continue
                    blind.append(f"{name}:{lineno + 1}  ——  {why}")
        self.assertEqual([], blind,
                         "这些写法让「每个创建点都走唯一来源」那条闸看不见对应的调用点,"
                         "而看不见的表现是**全绿**:\n  " + "\n  ".join(blind))

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
