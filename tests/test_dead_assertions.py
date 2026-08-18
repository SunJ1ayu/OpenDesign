#!/usr/bin/env python3
"""`tests/dead_assertions.py` 的判据 —— **给判官造判官**。

这道闸要抓的是"断言在那儿、却从没被执行过"(2026-08-06 我自己犯的:
`if d:` 里的 assert 因为 d 恒为 None,一次没跑过,而每一层看到的都是绿的)。

所以这份判据必须问清这几件事:
  1. **真的死断言要被抓到**(不然这道闸是摆设);
  2. **活着的断言不许被误报**(误报的闸活不过一周);
  3. **放行清单要有理由才生效** —— 没理由的例外等于把闸关掉;
  4. (2026-08-18)**放行认的是那一行的源码,不是行号** —— 行号漂过四次,
     四次都红在无辜的断言上;过期条目要当场响,盖住多行要吭声。
"""
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOL = os.path.join(HERE, "dead_assertions.py")

FIXTURE = textwrap.dedent('''
    import unittest

    class Fixture(unittest.TestCase):
        def test_live(self):
            self.assertEqual(1, 1)          # 活的:一定跑

        def test_dead(self):
            got = None                      # 模拟"服务端把连接掐了,没有响应体"
            if got:
                self.assertIn("收件箱", got)  # 死的:一次都不会跑
''')


def run_tool(tests_dir: str, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, DEAD_ASSERT_TESTS_DIR=tests_dir)
    return subprocess.run([sys.executable, TOOL, *args],
                          capture_output=True, text=True, env=env)


class DeadAssertionGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        with open(os.path.join(self.dir, "test_fixture.py"), "w", encoding="utf-8") as fh:
            fh.write(FIXTURE)

    def test_flags_the_dead_assertion(self):
        r = run_tool(self.dir)
        self.assertEqual(r.returncode, 1, f"有死断言就该非零退出:{r.stdout}{r.stderr}")
        self.assertIn("收件箱", r.stdout, "报告要点名那一行的源码,不能只给个数字")
        self.assertIn("test_fixture.py", r.stdout)

    def test_does_not_flag_live_assertions(self):
        """误报会让这道闸活不过一周 —— 活着的断言一条都不许出现在报告里。"""
        r = run_tool(self.dir)
        self.assertNotIn("assertEqual(1, 1)", r.stdout,
                         f"活着的断言被误报了:{r.stdout}")

    # 放行清单的一行长这样(2026-08-18 起按**内容**认,不按行号):
    #   <文件> :: <那一行 strip 后的源码>  # 理由
    DEAD_LINE = 'self.assertIn("收件箱", got)  # 死的:一次都不会跑'
    ALLOW_OK = f"test_fixture.py :: {DEAD_LINE}  # 夹具:这条本来就是用来演示死断言的\n"

    def _write_allow(self, text: str) -> None:
        with open(os.path.join(self.dir, "dead_assertions.allow"), "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_allow_needs_a_reason(self):
        # ① 没写理由的例外**不生效**
        self._write_allow(f"test_fixture.py :: {self.DEAD_LINE}\n")
        r = run_tool(self.dir)
        self.assertEqual(r.returncode, 1, "没写理由的例外不许生效")
        # ② 写了理由才放行
        self._write_allow(self.ALLOW_OK)
        r = run_tool(self.dir)
        self.assertEqual(r.returncode, 0, f"写了理由的例外应当放行:{r.stdout}")

    def test_allow_survives_line_drift(self):
        """行号漂了,放行**必须还在** —— 这就是 2026-08-18 那一刀要买的东西。

        在那之前清单按 `<文件>:<行号>` 认,而行号漂过四次(每次都是有人往文件
        上半部分加了一行 import),四次都红在**无辜的断言**上,四次修法都是把数字改大。
        报警器指错门和报警器被调钝一样坏,所以这条钉死:**只要那一行的源码没变,
        它上面加多少行都不许改变放行结论。**
        """
        self._write_allow(self.ALLOW_OK)
        with open(os.path.join(self.dir, "test_fixture.py"), "w", encoding="utf-8") as fh:
            fh.write("import os  # 上面多出来的一行,把下面所有行号推下去\n" + FIXTURE)
        r = run_tool(self.dir)
        self.assertEqual(r.returncode, 0, f"行号漂了就不放行了 ⇒ 又回到按行号认:{r.stdout}")

    def test_stale_allow_entry_is_loud(self):
        """清单指着一条**文件里已经不存在**的断言时,必须当场红。

        沉默地少放行一条 = 那条断言以"死断言"的身份红出来,而人会去改那条无辜的断言;
        沉默地放过 = 清单变成垃圾桶。两头都不许,所以这里要求它**点名那一条**。
        """
        self._write_allow("test_fixture.py :: self.assertIn(\"不存在的断言\", got)  # 早就删掉了\n")
        r = run_tool(self.dir)
        self.assertEqual(r.returncode, 1, "过期条目必须让闸红")
        self.assertIn("清单过期", r.stdout, f"要说清是清单过期,别让人去改无辜的断言:{r.stdout}")

    def test_allow_covering_two_lines_is_red(self):
        """一条目盖住不止一行 ⇒ **红**。同样的源码在别处未必适用同一个理由。

        2026-08-18 四审两腿各自指出:原来这里只打印一行 ⚠️ 不进退出码,而总跑的汇总
        只抠"N 条死断言" ⇒ 那行告警在总跑里根本看不见 = 等于静默放行。
        本仓库自己的规矩是"静默吞掉就是新的假绿",所以这里要求它**拦**。
        """
        self._write_allow(self.ALLOW_OK)
        with open(os.path.join(self.dir, "test_fixture.py"), "w", encoding="utf-8") as fh:
            fh.write(FIXTURE + textwrap.dedent('''
                class Fixture2(unittest.TestCase):
                    def test_dead2(self):
                        got = None
                        if got:
                            self.assertIn("收件箱", got)  # 死的:一次都不会跑
            '''))
        r = run_tool(self.dir)
        self.assertEqual(r.returncode, 1, f"放行悄悄变宽了却是绿的:{r.stdout}")
        self.assertIn("盖住了不止一行", r.stdout, f"红了却没说清为什么:{r.stdout}")

    def test_reports_suite_result_and_fails_with_it(self):
        """它要**替代**总跑里的 python 那一段(一次跑、两个信号),所以:
        判据本身红了它必须非零,而且要把 unittest 的汇总行原样透出来 ——
        否则总跑解析不到"跑了多少条/跳过多少条",汇总会变成瞎子。"""
        with open(os.path.join(self.dir, "test_fixture.py"), "w", encoding="utf-8") as fh:
            fh.write(textwrap.dedent("""
                import unittest

                class Broken(unittest.TestCase):
                    def test_red(self):
                        self.assertEqual(1, 2, "故意红")
            """))
        r = run_tool(self.dir)
        self.assertNotEqual(r.returncode, 0, "判据红了它必须非零(不能只报死断言)")
        self.assertIn("Ran 1 test", r.stdout + r.stderr,
                      f"要透出 unittest 的汇总行:{r.stdout}{r.stderr}")

    def test_clean_suite_passes(self):
        """一份干净的判据不许被判红(否则这道闸就是噪音发生器)。"""
        with open(os.path.join(self.dir, "test_fixture.py"), "w", encoding="utf-8") as fh:
            fh.write(textwrap.dedent('''
                import unittest

                class OK(unittest.TestCase):
                    def test_a(self):
                        self.assertTrue(True)
            '''))
        r = run_tool(self.dir)
        self.assertEqual(r.returncode, 0, f"干净判据应当全绿:{r.stdout}")
        self.assertIn("没有从没跑过的断言", r.stdout)

    # ── 2026-08-07 评审(DeepSeek 腿)抓到的两个洞,以下四条是它们的判据 ────────

    def _write(self, body: str) -> None:
        with open(os.path.join(self.dir, "test_fixture.py"), "w", encoding="utf-8") as fh:
            fh.write(textwrap.dedent(body))

    def test_flags_single_line_guarded_assertion(self):
        """**同一个事故,写成一行就躲过去了** —— 这是 08-07 评审抓到的第一个洞。

        `sys.monitoring` 的 LINE 事件是在这一行的**第一条字节码**上触发的,而
        `if got:` 的取值就是第一条 —— 于是这一行"执行过"了,里面那条从没跑过的
        断言却因此被判成活的。行粒度天然问不出这件事,所以这种写法必须当场报。
        """
        self._write('''
            import unittest

            class Fixture(unittest.TestCase):
                def test_dead_oneline(self):
                    got = None
                    if got: self.assertIn("收件箱", got)
        ''')
        r = run_tool(self.dir)
        self.assertEqual(r.returncode, 1,
                         f"单行守卫里的断言机器问不出来,必须当场报:{r.stdout}{r.stderr}")
        self.assertIn("收件箱", r.stdout, "报告要点名那一行,不能只给个数字")

    def test_truncation_marker_on_guarded_lines_too(self):
        """超 120 字符的截断记号,**两节都要有** —— 少一边人就会复制到半句。

        放行清单按**整行内容**认。`note()`(dead_assertions.py:77)超长会补
        "…(截断,写进 allow 要用整行)";而"同一行守卫"那一节(:169)是**静默**
        `[:120]`。于是从后者复制一行进 allow ⇒ 拿到的是半句 ⇒ 清单对不上 ⇒
        红成"过期条目",而报告不会告诉他是被截断害的。
        2026-08-18 四审 subkimi 指出:这个记号此前**没有任何判据钉它**。
        """
        long_msg = "收件箱" + "补" * 160         # 整行 ~193 字符,稳过 120 那道线
        self._write(f'''
            import unittest

            class Fixture(unittest.TestCase):
                def test_dead_oneline(self):
                    got = None
                    if got: self.assertIn("{long_msg}", got)
        ''')
        r = run_tool(self.dir)
        self.assertEqual(r.returncode, 1,
                         f"单行守卫本来就该报红:{r.stdout}{r.stderr}")
        self.assertIn("和它的守卫写在同一行", r.stdout,
                      f"这一行该落在'同一行守卫'那一节:{r.stdout}")
        self.assertIn("…(截断,写进 allow 要用整行)", r.stdout,
                      f"这一节的长行被静默截断了,复制进 allow 会对不上:{r.stdout}")

    def test_does_not_flag_assertRaises_context(self):
        """防止上一条修过头:`with self.assertRaises(...)` 的断言**就在头部**,
        这一行跑过了就是真问过了,一条都不许误报(本仓库现有 7 处这种写法)。"""
        self._write('''
            import unittest

            class Fixture(unittest.TestCase):
                def test_raises(self):
                    with self.assertRaises(ValueError):
                        raise ValueError("boom")
        ''')
        r = run_tool(self.dir)
        self.assertEqual(r.returncode, 0, f"assertRaises 上下文被误报了:{r.stdout}")

    def test_skipped_test_is_not_a_dead_assertion(self):
        """**跳过 ≠ 死** —— 08-07 评审抓到的第二个洞。

        被 skip 的判据里的断言当然没跑过,但那是"这台机器上没条件问",
        不是"断言没被问出口"。把两者混成一个红,总跑在没起 gateway 的机器上
        就会因为 16 条 SKIP 变红 —— 而 `run-all.sh` 自己的规矩是
        「SKIP 不是 PASS,但它是 exit 3,不是 exit 1」。
        要求:不算红,但**必须单独印出来**(静默吞掉就成了新的假绿)。
        """
        self._write('''
            import unittest

            @unittest.skipIf(True, "这台机器上没条件跑")
            class Fixture(unittest.TestCase):
                def test_skipped(self):
                    self.assertIn("收件箱", "收件箱里有东西")
        ''')
        r = run_tool(self.dir)
        self.assertEqual(r.returncode, 0,
                         f"跳过的判据不该被算成死断言:{r.stdout}{r.stderr}")
        self.assertIn("跳过", r.stdout, f"跳过的断言必须单独印出来,不许静默吞掉:{r.stdout}")

    def test_skip_does_not_hide_a_real_dead_assertion(self):
        """防止上一条变成新后门:同一份判据里既有 skip、也有真死断言时,
        真死的那条**照样要红**。

        **这条判据证明的事没有它的名字听起来那么大**(第二轮评审两腿都点了这里):
        它只证明"skip 不会溢出到**别的方法**",证明不了"skip 不能当关闸的万能钥匙"——
        把死断言塞进**被 skip 的那个方法自己**,照样豁免。那是设计取舍不是 bug
        (跳过的测试本来就没条件问),兜底在于 skip 数进总跑的 n_skip ⇒ exit 3,
        关闸这个动作是看得见的。别再把这条读成"后门已堵死"。
        """
        self._write('''
            import unittest

            @unittest.skipIf(True, "这台机器上没条件跑")
            class Skipped(unittest.TestCase):
                def test_skipped(self):
                    self.assertIn("跳过的那条", "跳过的那条")

            class Live(unittest.TestCase):
                def test_dead(self):
                    got = None
                    if got:
                        self.assertIn("收件箱", got)
        ''')
        r = run_tool(self.dir)
        self.assertEqual(r.returncode, 1,
                         f"skip 不许把同一份里的真死断言一起豁免:{r.stdout}{r.stderr}")
        self.assertIn("收件箱", r.stdout)

    # ── 2026-08-07 收口时我自己攻这轮修复,又抓到两个 —— 上一格那条"防后门"判据
    #    防的是**我想得到的那种后门**(同一个文件)。以下两条是它漏掉的形状。

    def test_skip_exemption_stays_in_its_own_file(self):
        """skip 豁免**不许跨文件圈错行** —— 会把正在跑的判据里的真死断言吞掉。

        `inspect.getsourcefile(cls)` 给的是**子类**所在的文件,
        `inspect.getsourcelines(meth)` 给的是方法**真正定义处**(可能是别的文件)的行号。
        两个拼在一起 = 在错误的文件上圈了一段豁免区;真死断言正好落在里面就被静默吞掉,
        而且往**多豁免**(危险的一侧)错,不是往噪音错。
        """
        with open(os.path.join(self.dir, "mixin_base.py"), "w", encoding="utf-8") as fh:
            # 方法故意写长:它的行范围会被原样套到子类文件上,要能盖住下面那条死断言
            body = "\n".join("        self.assertEqual(1, 1)" for _ in range(20))
            fh.write("import unittest\n\n\nclass Mixin:\n"
                     "    def test_inherited(self):\n" + body + "\n")
        self._write('''
            import os
            import sys
            import unittest

            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from mixin_base import Mixin

            class Live(unittest.TestCase):
                def test_dead(self):
                    got = None
                    if got:
                        self.assertIn("收件箱", got)

            @unittest.skipIf(True, "这台机器上没条件跑")
            class Child(Mixin, unittest.TestCase):
                pass
        ''')
        r = run_tool(self.dir)
        self.assertEqual(r.returncode, 1,
                         f"别的文件里的 skip 不许豁免这个文件里的真死断言:{r.stdout}{r.stderr}")
        self.assertIn("收件箱", r.stdout)

    def test_flags_short_circuit_guarded_assertion(self):
        """`got and self.assertIn(...)` —— `if got:` 的等价写法,只是它是**一条**语句。

        单行守卫那条判法数的是"一行上起了几条语句",这种写法只有一条,
        于是从缝里漏过去:LINE 事件照常触发(短路的取值就是第一条字节码),
        断言一次没跑,闸却说干净。
        """
        self._write('''
            import unittest

            class Fixture(unittest.TestCase):
                def test_dead_shortcircuit(self):
                    got = None
                    got and self.assertIn("收件箱", got)
        ''')
        r = run_tool(self.dir)
        self.assertEqual(r.returncode, 1,
                         f"短路里的断言机器问不出来,必须当场报:{r.stdout}{r.stderr}")
        self.assertIn("收件箱", r.stdout)

    # ── 第二轮评审(DeepSeek + Kimi 双腿 BLOCK)抓到的:**误报那一侧**。
    #    "一行上起了两条以上语句" 这条判法把「会分流」和「只是挤在一行」混成了一件事。
    #    真正该问的是:**排在这条断言前面的东西,能不能把它绕过去**。

    def test_does_not_flag_one_line_assertRaises(self):
        """单行 `with self.assertRaises(X): raise X()` —— 断言在 with 的**头部**,
        这一行跑了就是真问过了,报它就是误报。

        Kimi 指出:文件头声称"assertRaises 不在此列",而实现里**根本没有这个排除** ——
        现有 7 处不误报纯粹因为它们都写成两行(body 在下一行)。
        排除是格式上的巧合,不是判据声称的机制。
        """
        self._write('''
            import unittest

            class Fixture(unittest.TestCase):
                def test_raises_oneline(self):
                    with self.assertRaises(ValueError): raise ValueError("boom")
        ''')
        r = run_tool(self.dir)
        self.assertEqual(r.returncode, 0,
                         f"单行 assertRaises 的断言在头部,跑过了就是问过了:{r.stdout}")

    def test_does_not_flag_sequential_same_line(self):
        """`x = f(); self.assertEqual(...)` —— 同一行两条语句,但**没有任何分流**,
        行跑了两条必然都跑。报它是把排版风格执法包装成认知判断(Kimi L1)。"""
        self._write('''
            import unittest

            class Fixture(unittest.TestCase):
                def test_sequential(self):
                    got = "收件箱"; self.assertIn("收", got)
        ''')
        r = run_tool(self.dir)
        self.assertEqual(r.returncode, 0,
                         f"同一行但不分流的断言必然跑过,不许报:{r.stdout}")

    def test_flags_ternary_and_comprehension_guarded(self):
        """短路之外的同族形状:三元、单行推导式。

        (这两条写下来时已经是绿的 —— 上一轮我把判法从"补一个 BoolOp"改成了
        "断言没在语句位上就算问不出",三元/推导式/lambda 一并盖住。
        **它们没红过,是覆盖不是红检**,这里写清楚,别让后来的人以为红检过。)
        """
        for body in ('self.assertIn("收件箱", got) if got else None',
                     '[self.assertIn("收件箱", x) for x in []]'):
            with self.subTest(body=body):
                self._write(f'''
                    import unittest

                    class Fixture(unittest.TestCase):
                        def test_dead_expr(self):
                            got = None
                            {body}
                ''')
                r = run_tool(self.dir)
                self.assertEqual(r.returncode, 1,
                                 f"表达式里的断言机器问不出来,必须当场报:{r.stdout}")


if __name__ == "__main__":
    unittest.main()
