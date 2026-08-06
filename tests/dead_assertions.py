#!/usr/bin/env python3
"""**从没被执行过的断言** —— 判据里最阴的一种失效,这个脚本专门找它。

## 为什么要有它(2026-08-06 实事故)

我在 `tests/test_ds_web_upload.py` 里写过这样一条:

    st, d = _post(...)          # 文件太大 → 服务端在读 body 前就掐断连接
    if d:                       # ← d 永远是 None
        self.assertIn("收件箱", ...)   # ← **这一行一次都没执行过**

判据是绿的、总跑是绿的、四审前三层全看不见 —— 因为**每一层看到的都是"通过"**。
它不是"断言写错了",是"断言压根没被问出口"。同一个文件里早有一条注释警告过这种写法
(u15:"改成声称 20MB、只发几个字节,否则断言变成空跑,自欺"),我照样又犯了一遍。
⇒ 规矩靠记不住,得靠机器看。

## 它怎么判

跑一遍 python 判据(`unittest discover -s tests`),用 `sys.monitoring`(3.12 自带,
**不装任何依赖**)记下 `tests/` 下每一行有没有真的执行过;再用 `ast` 把每个测试文件里的
**断言语句**挑出来(`self.assert*` / `self.fail` / 裸 `assert` / `check(...)`),
两边一对:**断言在那儿、却从没跑过 ⇒ 报出来**。

只盯断言,不盯普通语句 —— 没执行的 `else: pass` 不值得管,没执行的断言几乎一定是洞。

## 例外怎么办

`tests/dead_assertions.allow` 一行一个 `文件:行号  # 理由`。**必须写理由** ——
没理由的例外就是把这道闸关掉。

用法:
    python3 tests/dead_assertions.py          # 报告 + 退出码(0 干净 / 1 有死断言)
    python3 tests/dead_assertions.py --list   # 只列出所有断言行(调试用)
"""
from __future__ import annotations

import ast
import io
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ALLOW_FILE = os.path.join(HERE, "dead_assertions.allow")

_ASSERT_PREFIXES = ("assert", "fail")


def assertion_lines(path: str) -> dict[int, str]:
    """文件里所有**断言语句**的行号 → 源码片段。"""
    try:
        tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
    except SyntaxError:
        return {}
    out: dict[int, str] = {}
    src = open(path, encoding="utf-8").read().splitlines()

    def note(node: ast.AST, why: str) -> None:
        ln = getattr(node, "lineno", None)
        if ln:
            out[ln] = (src[ln - 1].strip() if ln <= len(src) else why)[:120]

    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            note(node, "assert")
        elif isinstance(node, ast.Call):
            fn = node.func
            name = ""
            if isinstance(fn, ast.Attribute):
                name = fn.attr
            elif isinstance(fn, ast.Name):
                name = fn.id
            if name.startswith(_ASSERT_PREFIXES) or name == "check":
                note(node, name)
    return out


def run_suite_recording_lines() -> set[tuple[str, int]]:
    """跑一遍 python 判据,记下 tests/ 下真正执行过的行。"""
    executed: set[tuple[str, int]] = set()
    mon = sys.monitoring
    tool_id = mon.PROFILER_ID
    mon.use_tool_id(tool_id, "dead-assertions")

    def on_line(code, line_number):  # noqa: ANN001
        fn = code.co_filename
        if fn.startswith(HERE + os.sep):
            executed.add((os.path.realpath(fn), line_number))
        return mon.DISABLE if not fn.startswith(HERE + os.sep) else None

    mon.register_callback(tool_id, mon.events.LINE, on_line)
    mon.set_events(tool_id, mon.events.LINE)
    try:
        loader = unittest.TestLoader()
        suite = loader.discover(HERE, top_level_dir=ROOT)
        # 判据自己的输出不进这份报告(它只关心"哪一行跑过了")
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            unittest.TextTestRunner(stream=buf, verbosity=0).run(suite)
    finally:
        mon.set_events(tool_id, 0)
        mon.free_tool_id(tool_id)
    return executed


def load_allow() -> dict[tuple[str, int], str]:
    allow: dict[tuple[str, int], str] = {}
    if not os.path.exists(ALLOW_FILE):
        return allow
    for raw in open(ALLOW_FILE, encoding="utf-8"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        head, _, why = line.partition("#")
        loc = head.strip()
        if ":" not in loc or not why.strip():
            continue      # 没写理由的例外**不生效** —— 例外必须说得出为什么
        f, _, ln = loc.rpartition(":")
        try:
            allow[(os.path.realpath(os.path.join(ROOT, f)), int(ln))] = why.strip()
        except ValueError:
            continue
    return allow


def main() -> int:
    files = sorted(
        os.path.join(HERE, f) for f in os.listdir(HERE)
        if f.startswith("test_") and f.endswith(".py")
    )
    wanted: dict[tuple[str, int], tuple[str, str]] = {}
    for f in files:
        for ln, src in assertion_lines(f).items():
            wanted[(os.path.realpath(f), ln)] = (os.path.relpath(f, ROOT), src)

    if "--list" in sys.argv:
        for (f, ln), (rel, src) in sorted(wanted.items()):
            print(f"{rel}:{ln}  {src}")
        return 0

    executed = run_suite_recording_lines()
    allow = load_allow()
    dead = [(k, v) for k, v in sorted(wanted.items())
            if k not in executed and k not in allow]

    print("=== 死断言检查(断言在那儿、却从没被执行过)===")
    print(f"  扫了 {len(files)} 个判据文件、{len(wanted)} 条断言;"
          f"放行清单 {len(allow)} 条")
    if not dead:
        print("  ✅ 没有从没跑过的断言。")
        return 0
    print(f"  ❌ {len(dead)} 条断言一次都没执行过 —— 它们看起来是绿的,其实什么都没问:")
    for (_f, ln), (rel, src) in dead:
        print(f"     {rel}:{ln}  {src}")
    print("  要么把断言搬到问得出的地方,要么写进 tests/dead_assertions.allow(**必须写理由**)。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
