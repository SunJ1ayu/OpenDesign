#!/usr/bin/env python3
"""ds_lock 的互斥 oracle — "写操作持排他锁"这条铁律此前没有任何测试锁着。

跑法:  python3 tests/test_ds_lock.py
fcntl.flock 按 open file description 记账:同进程两次独立 open() 就是两个持锁方,
足以验证互斥,无需双进程。msvcrt 分支无 Windows CI,留待真机验证(deploy 清单项)。
"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_lock  # noqa: E402


class LockOracle(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(prefix="dslock-")
        os.write(fd, b"x")
        os.close(fd)

    def tearDown(self):
        os.unlink(self.path)

    def test_exclusive_blocks_second_holder_and_releases(self):
        try:
            import fcntl
        except ImportError:
            self.skipTest("无 fcntl(Windows):msvcrt 分支走真机首装验证")
        with open(self.path, "r+") as fh1, open(self.path, "r+") as fh2:
            with ds_lock.exclusive(fh1):
                # 持锁期间,第二个持锁方非阻塞抢锁必须失败
                with self.assertRaises(OSError):
                    fcntl.flock(fh2, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # with 退出(含异常路径同一 finally)后必须立刻可拿
            fcntl.flock(fh2, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fh2, fcntl.LOCK_UN)

    def test_exception_path_releases(self):
        try:
            import fcntl
        except ImportError:
            self.skipTest("无 fcntl(Windows):msvcrt 分支走真机首装验证")
        with open(self.path, "r+") as fh1, open(self.path, "r+") as fh2:
            with self.assertRaises(RuntimeError):
                with ds_lock.exclusive(fh1):
                    raise RuntimeError("boom")
            fcntl.flock(fh2, fcntl.LOCK_EX | fcntl.LOCK_NB)  # 异常后锁已释放
            fcntl.flock(fh2, fcntl.LOCK_UN)


if __name__ == "__main__":
    unittest.main(verbosity=2)
