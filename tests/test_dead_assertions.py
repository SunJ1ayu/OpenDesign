#!/usr/bin/env python3
"""`tests/dead_assertions.py` 的判据 —— **给判官造判官**。

这道闸要抓的是"断言在那儿、却从没被执行过"(2026-08-06 我自己犯的:
`if d:` 里的 assert 因为 d 恒为 None,一次没跑过,而每一层看到的都是绿的)。

所以这份判据必须问清三件事:
  1. **真的死断言要被抓到**(不然这道闸是摆设);
  2. **活着的断言不许被误报**(误报的闸活不过一周);
  3. **放行清单要有理由才生效** —— 没理由的例外等于把闸关掉。
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

    def test_allow_needs_a_reason(self):
        allow = os.path.join(self.dir, "dead_assertions.allow")
        # ① 没写理由的例外**不生效**
        with open(allow, "w", encoding="utf-8") as fh:
            fh.write("test_fixture.py:11\n")
        r = run_tool(self.dir)
        self.assertEqual(r.returncode, 1, "没写理由的例外不许生效")
        # ② 写了理由才放行
        with open(allow, "w", encoding="utf-8") as fh:
            fh.write("test_fixture.py:11  # 夹具:这条本来就是用来演示死断言的\n")
        r = run_tool(self.dir)
        self.assertEqual(r.returncode, 0, f"写了理由的例外应当放行:{r.stdout}")

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


if __name__ == "__main__":
    unittest.main()
