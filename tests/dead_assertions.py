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

`tests/dead_assertions.allow` 一行一个 `文件 :: 那一行的源码  # 理由`。
**必须写理由** —— 没理由的例外就是把这道闸关掉。

⚠️ 认的是**内容不是行号**(2026-08-18 改)。原来按 `文件:行号` 认,而行号漂了四次
(203/303 → 220/320 → 221/321 → 222/322 → 224/324),四次都是有人往文件上半部分
加了一行 import,四次都红在无辜的地方、修法都是把数字改大。**行号不是一条断言的身份。**
清单里某一条在文件里找不到对应的行 ⇒ **当场红**(清单过期了,不许静默放过)。

用法:
    python3 tests/dead_assertions.py          # 报告 + 退出码(0 干净 / 1 有死断言)
    python3 tests/dead_assertions.py --list   # 只列出所有断言行(调试用)
"""
from __future__ import annotations

import ast
import inspect
import io
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout

# 判据目录可被 `DEAD_ASSERT_TESTS_DIR` 覆盖 —— **这个接缝是为了这道闸自己能被判**:
# 不给接缝的话,它的判据只能拿真判据目录跑,那就没法造一条"确定是死的"断言来问它。
_SELF = os.path.dirname(os.path.abspath(__file__))
HERE = os.path.abspath(os.environ.get("DEAD_ASSERT_TESTS_DIR") or _SELF)
ROOT = os.path.dirname(HERE)
ALLOW_FILE = os.path.join(HERE, "dead_assertions.allow")
# 一条放行条目匹配到多行时记在这里(报告要印出来,见 load_allow)
ALLOW_WIDE: list[tuple[str, list[int], str]] = []

_CLIP_LIMIT = 120
_CLIP_MARK = " …(截断,写进 allow 要用整行)"


def clip(full: str) -> str:
    """报告里的源码行超长就截断 —— 但**必须留记号**。

    放行清单按**整行内容**认,而人会直接从报告里复制这一行。不留记号的话他复制到的
    是半句,清单当场对不上 ⇒ 误红成"过期条目" ⇒ 他会去改那条无辜的断言。
    2026-08-18 四审 subkimi 3:这个记号原来只加在 note()(死断言那一节),
    "同一行守卫"那一节是静默 `[:120]` —— 而两节的行都一样会被人复制。
    抽到这里是为了**下一节也别再漏**:要截断就走这个函数。
    """
    return full if len(full) <= _CLIP_LIMIT else full[:_CLIP_LIMIT] + _CLIP_MARK

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
            full = src[ln - 1].strip() if ln <= len(src) else why
            out[ln] = clip(full)          # 截断必须留记号,理由见 clip()

    # `except` 里的断言是**错误路径的兜底**(`self.fail("并发把配置写坏了")` 那种):
    # 健康的时候它本来就不该跑,拿"没执行过"去报它就是纯误报。先把这些行标出来跳过。
    in_handler: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            for sub in ast.walk(node):
                ln = getattr(sub, "lineno", None)
                if ln:
                    in_handler.add(ln)

    for node in ast.walk(tree):
        if getattr(node, "lineno", None) in in_handler:
            continue
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


def same_line_guarded(path: str) -> dict[int, str]:
    """**行粒度问不出跑没跑过**的那些断言 —— 这道闸对它们是瞎的,所以当场报。

    `if got: self.assertIn(...)` 里,LINE 事件是在这一行的**第一条字节码**
    (`got` 的取值)上触发的:这一行"执行过"了,而那条断言一次没跑。
    于是 08-06 那个事故换个换行位置就能躲过整道闸(2026-08-07 评审抓到)。

    该问的**不是"这一行挤了几条语句"**,是:
    **排在这条断言前面的东西,能不能把它绕过去。**
    (第一版问的是前者,于是把"会分流"和"只是挤在一行"混成一件事 ——
    单行 `with self.assertRaises(X): raise X()` 和 `x = f(); self.assertX(...)`
    都被误报,而它们的断言明明必然跑过。2026-08-07 第二轮评审两腿同时打在这。)

    两种绕得过去的形状:
    ① 断言在一个**会跳过自己 body 的头部**(`if` / `for` / `while`)的同一行上
       —— `if got: self.assertIn(...)`,08-06 那个事故的单行写法;
    ② 断言**不在语句位上**,而是嵌在表达式里(`got and self.assertX(...)`、
       三元、推导式、未被调用的 lambda)—— 它只有一条语句,躲过形状①,
       但短路 / 空序列时同样一次不跑。

    反过来这些**不算**(断言必然随该行一起跑):`self.assertX(...)` 独占一行、
    `with self.assertRaises(...)` 的头部(with/try 不会跳过 body)、
    `x = f(); self.assertX(...)` 这种同行但不分流的写法。
    """
    try:
        tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
    except SyntaxError:
        return {}
    src = open(path, encoding="utf-8").read().splitlines()
    asserts = set(assertion_lines(path))

    # 形状①:会跳过 body 的头部,且 body 的第一条语句和它挤在同一行。
    # 只看**那条 body 语句自己的子树**,不看整行 —— 否则头部里的断言
    # (`with self.assertRaises(X):`)会被自己的 body 连累。
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While)):
            continue
        for child in list(node.body) + list(getattr(node, "orelse", []) or []):
            if getattr(child, "lineno", None) != node.lineno:
                continue
            for sub in ast.walk(child):
                ln = getattr(sub, "lineno", None)
                if ln == node.lineno and ln in asserts:
                    guarded.add(ln)

    # 形状②:"在语句位上"= 整条语句就是这个调用,或它是 `with` 的头部。
    plain: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            plain.add(id(node.value))
        elif isinstance(node, ast.withitem) and isinstance(node.context_expr, ast.Call):
            plain.add(id(node.context_expr))

    embedded: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and id(node) not in plain:
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else (
                fn.id if isinstance(fn, ast.Name) else "")
            if name.startswith(_ASSERT_PREFIXES) or name == "check":
                embedded.add(node.lineno)

    # 走 clip():这一节原来是**静默** `[:120]`,从这儿复制长行进 allow 会拿到半句。
    return {ln: clip(src[ln - 1].strip())
            for ln in sorted(guarded | embedded) if ln <= len(src)}


def skipped_method_ranges(skipped) -> list[tuple[str, int, int]]:
    """被 skip 掉的判据方法的源码行范围。

    **跳过 ≠ 死**:被 skip 的方法里的断言当然没跑过,但那是"这台机器上没条件问",
    不是"断言没被问出口"。总跑自己的规矩就是「SKIP 不是 PASS,但它是 exit 3
    不是 exit 1」—— 把两者混成一个红,没起 gateway 的机器上这一段就会
    因为 16 条 SKIP 变红(2026-08-07 评审抓到,当场复现过)。

    只取**方法**的范围,不取整个类:类级 `@skipIf` 时 unittest 仍会把每个
    方法各报一条,方法范围就够;而按类取会把同类里跑过的方法一起豁免掉。
    """
    out: list[tuple[str, int, int]] = []
    for entry in skipped:
        test = entry[0] if isinstance(entry, tuple) else entry
        cls = type(test)
        meth = getattr(cls, getattr(test, "_testMethodName", ""), None)
        if meth is None:
            continue
        try:
            # 文件和行号**必须来自同一个来源(方法自己)**:方法可能是从别的模块里
            # 继承来的,那时 `getsourcefile(cls)` 是子类的文件、`getsourcelines(meth)`
            # 是基类的行号 —— 拼起来就是在错误的文件上圈了一段豁免区,
            # 把正在跑的判据里的真死断言静默吞掉(2026-08-07 收口时自攻发现并复现)。
            src_file = inspect.getsourcefile(meth)
            lines, start = inspect.getsourcelines(meth)
        except (OSError, TypeError):
            continue
        if src_file:
            out.append((os.path.realpath(src_file), start, start + len(lines) - 1))
    return out


def run_suite_recording_lines() -> tuple[set[tuple[str, int]], bool, str,
                                         list[tuple[str, int, int]]]:
    """跑一遍 python 判据,记下 tests/ 下真正执行过的行。

    返回 (执行过的行, 判据是否全绿, 判据的原始输出, 被 skip 的方法的行范围)。
    **它是总跑里 python 那一段的替身**(一次跑、两个信号),所以判据本身红了
    必须能报出来,汇总行也要原样透出去 —— 否则总跑数不出"跑了多少条/跳过多少条"。
    """
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
        # 真判据目录用 ROOT 当顶层(各文件自己往 sys.path 塞 bin/);
        # 被覆盖成临时夹具目录时它不可导入 ⇒ 退回以自身为顶层。
        try:
            suite = loader.discover(HERE, top_level_dir=ROOT)
        except ImportError:
            sys.path.insert(0, HERE)
            suite = loader.discover(HERE, top_level_dir=HERE)
        # 判据自己的输出不进这份报告(它只关心"哪一行跑过了")
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            result = unittest.TextTestRunner(stream=buf, verbosity=0).run(suite)
    finally:
        mon.set_events(tool_id, 0)
        mon.free_tool_id(tool_id)
    return (executed, result.wasSuccessful(), buf.getvalue(),
            skipped_method_ranges(result.skipped))


def load_allow() -> tuple[dict[tuple[str, int], str], list[str]]:
    """读放行清单,返回 ({(文件, 行号): 理由}, [过期条目的原文])。

    格式 `<文件> :: <那一行 strip 后的源码>  # 理由`。**按内容认,不按行号** ——
    行号会随上面加一行 import 就漂,而漂动和"这条断言变了"是两回事
    (2026-08-18 之前漂过四次,每次都红在无辜的地方,每次修法都是改数字)。

    - 一条目在文件里匹配到多行:全部放行 —— 同一份理由对逐字节相同的代码同样成立。
    - 匹配到 **0 行**:算**过期条目**,由调用方报红。清单指着一条不存在的断言时,
      沉默地少放行一条正是"报警器指错门"的形状,必须响。
    """
    allow: dict[tuple[str, int], str] = {}
    stale: list[str] = []
    global ALLOW_WIDE
    ALLOW_WIDE = []
    if not os.path.exists(ALLOW_FILE):
        return allow, stale
    for raw in open(ALLOW_FILE, encoding="utf-8"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # 理由用 `  #`(两个空格加井号)分隔:源码里出现的 `#` 多半没有前导双空格,
        # 而万一切错了,结果是"这条匹配不上" ⇒ 报成过期条目,响,而不是静默放行。
        head, sep, why = line.rpartition("  #")
        if not sep or not why.strip():
            continue      # 没写理由的例外**不生效** —— 例外必须说得出为什么
        f, sep2, want = head.partition(" :: ")
        if not sep2 or not want.strip():
            stale.append(line)
            continue
        f, want = f.strip(), want.strip()
        # 路径既接受"相对仓库根"(报告里印的那种),也接受"相对判据目录"。
        # **只登记真实存在的那一个** —— 两个都登记会让报告里的"放行清单 N 条"翻倍
        # (2026-08-07 实测:清单 2 条印成 4 条)。一个会撒谎的机器输出,
        # 恰恰长在"别信自述、信机器打印的"这道闸身上。
        path = ""
        for base in (ROOT, HERE):
            cand = os.path.realpath(os.path.join(base, f))
            if os.path.exists(cand):
                path = cand
                break
        if not path:
            stale.append(line)
            continue
        hits = [i for i, src in enumerate(
            open(path, encoding="utf-8").read().splitlines(), start=1)
            if src.strip() == want]
        if not hits:
            stale.append(line)
            continue
        # 一条目盖住不止一行 ⇒ **红**。内容相同的断言可能在别处也有一份,而那一份
        # 未必适用同一个理由;放行清单一旦能一条盖两处,它就开始变成垃圾桶。
        # 2026-08-18 四审两腿各自指出:原来这里只打印一行 ⚠️、不进退出码,而总跑的
        # 汇总行只抠"N 条死断言" ⇒ 那行告警**在总跑里根本不可见** = 等于静默放行。
        # 本仓库自己的规矩就是"静默吞掉就是新的假绿",所以改成拦。
        if len(hits) > 1:
            ALLOW_WIDE.append((line, hits, path))
        for n in hits:
            allow[(path, n)] = why.strip()
    return allow, stale


def main() -> int:
    files = sorted(
        os.path.join(HERE, f) for f in os.listdir(HERE)
        if f.startswith("test_") and f.endswith(".py")
    )
    wanted: dict[tuple[str, int], tuple[str, str]] = {}
    ambiguous: dict[tuple[str, int], tuple[str, str]] = {}
    for f in files:
        rel = os.path.relpath(f, ROOT)
        for ln, src in assertion_lines(f).items():
            wanted[(os.path.realpath(f), ln)] = (rel, src)
        for ln, src in same_line_guarded(f).items():
            ambiguous[(os.path.realpath(f), ln)] = (rel, src)

    if "--list" in sys.argv:
        for (f, ln), (rel, src) in sorted(wanted.items()):
            print(f"{rel}:{ln}  {src}")
        return 0

    executed, suite_ok, suite_out, skip_ranges = run_suite_recording_lines()
    print(suite_out, end="")          # 判据自己的汇总行原样透出(总跑要解析它)
    allow, stale_allow = load_allow()

    def in_skipped(key: tuple[str, int]) -> bool:
        f, ln = key
        return any(f == sf and lo <= ln <= hi for sf, lo, hi in skip_ranges)

    missing = [(k, v) for k, v in sorted(wanted.items())
               if k not in executed and k not in allow]
    skipped = [(k, v) for k, v in missing if in_skipped(k)]
    dead = [(k, v) for k, v in missing if not in_skipped(k) and k not in ambiguous]

    print("=== 死断言检查(断言在那儿、却从没被执行过)===")
    if not suite_ok:
        print("  ⚠️ 判据本身有红的 —— 先修那个;下面的死断言统计在红的判据上没有意义。")
    print(f"  扫了 {len(files)} 个判据文件、{len(wanted)} 条断言;"
          f"放行清单 {len(allow)} 条")

    # 跳过的**必须印出来**(静默吞掉就是新的假绿),但它不算红:
    # 「SKIP 不是 PASS」由总跑那一层管,它是 exit 3 不是 exit 1。
    if skipped:
        print(f"  ⏭️ {len(skipped)} 条断言在**被跳过的判据**里 —— 这台机器上没条件问,"
              f"不算死断言(要真跑它们,见对应文件头的前置条件):")
        for (_f, ln), (rel, src) in skipped[:10]:
            print(f"     {rel}:{ln}  {src}")
        if len(skipped) > 10:
            print(f"     …… 还有 {len(skipped) - 10} 条")

    if ambiguous:
        print(f"  ❌ {len(ambiguous)} 条断言**和它的守卫写在同一行** —— "
              f"行粒度问不出它跑没跑过,等于这道闸对它是瞎的:")
        for (_f, ln), (rel, src) in sorted(ambiguous.items()):
            print(f"     {rel}:{ln}  {src}")
        print("  拆成两行(守卫一行、断言一行)这道闸才看得见它。")

    if dead:
        print(f"  ❌ {len(dead)} 条断言一次都没执行过 —— 它们看起来是绿的,其实什么都没问:")
        for (_f, ln), (rel, src) in dead:
            print(f"     {rel}:{ln}  {src}")
        print("  要么把断言搬到问得出的地方,要么写进 tests/dead_assertions.allow"
              "(**必须写理由**)。")

    if ALLOW_WIDE:
        print(f"  ❌ 放行清单里有 {len(ALLOW_WIDE)} 条**盖住了不止一行**"
              f"(同样的源码在同一个文件里出现多次):")
        for line, hits, path in ALLOW_WIDE:
            rel = os.path.relpath(path, ROOT)
            print(f"     盖住 {len(hits)} 行 ← {line}")
            # 不点名就等于让人自己去 grep,而他很可能挑错那一行下手 —— 当年行号版
            # 被换掉,正是因为"报警器指错门"。(2026-08-18 四审两腿各自指到这里)
            print(f"       命中:{', '.join(f'{rel}:{n}' for n in hits)}")
        print("  一条理由放行两处 = 另一处即使是真死断言也没人问过它。")
        # ── E:原来这句写着"或者给每一处各写一条" —— 对**逐字相同**的两行根本不成立
        #    (写几条都还是同时盖住它们)。四审两腿各自指出这句在指错路。
        print("  消歧只有一条路:**给其中一行加个尾注释**,让两行不再逐字相同;")
        print("  改完记得把 allow 里那条也跟着改成带注释的整行。")

    if stale_allow:
        # 清单指着一条文件里已经不存在的断言。可能是那条断言被改了/删了/挪走了 ——
        # 三种都意味着"当初写的那个理由还成不成立"要重新过问一次,不许顺手放过。
        print(f"  ❌ 放行清单里有 {len(stale_allow)} 条对不上任何一行(清单过期了):")
        for line in stale_allow:
            print(f"     {line}")
        print("  改成那一行现在的源码,或者删掉它 —— 别让清单指着不存在的东西。")

    if not dead and not ambiguous and not stale_allow and not ALLOW_WIDE:
        print("  ✅ 没有从没跑过的断言。")
    return 0 if (suite_ok and not dead and not ambiguous
                 and not stale_allow and not ALLOW_WIDE) else 1


if __name__ == "__main__":
    sys.exit(main())
