#!/usr/bin/env python3
"""ds_todo 特征化测试(golden)+ list_todos 错误路径 — track opendesign-windows-prep T2。

跑法:  python3 tests/test_ds_todo.py
golden 锁的是 2026-07-03 时 Python 版的既定行为(bash 原版已不存在,无从对照);
DS_TODAY 注入冻结"今天",保证跨日稳定。
"""
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # design-studio/
BIN = os.path.join(ROOT, "bin")
sys.path.insert(0, BIN)
import ds_todo  # noqa: E402
import ds_tools  # noqa: E402

TODAY = date(2026, 7, 3)

A_OPEN = """# a-open

## 变更记录
- [待确认] C1 2026-06-20 改推拉门
- [已完成] C2 2026-06-18 完事

---
最后更新: 2026-07-02
"""

B_STALE = """# b-stale

- [已关闭] C1 2026-06-01 旧事

---
最后更新: 2026-06-20
"""

C_CLEAN = """# c-clean

- [已完成] C1 2026-06-30 完事

---
最后更新: 2026-07-01
"""

GOLDEN_MIXED = """== 未关闭事项(待确认 / 进行中) ==
▸ a-open
    4:- [待确认] C1 2026-06-20 改推拉门

== 超过 7 天未更新的项目 ==
▸ b-stale — 13天未更新 (最后 2026-06-20)
"""

GOLDEN_CLEAN = """== 未关闭事项(待确认 / 进行中) ==
  (无)

== 超过 7 天未更新的项目 ==
  (无)
"""

GOLDEN_OPEN_ONLY = """== 未关闭事项(待确认 / 进行中) ==
▸ a-open
    4:- [待确认] C1 2026-06-20 改推拉门

== 超过 7 天未更新的项目 ==
  (无)
"""


def _mkroot(files: dict) -> str:
    d = tempfile.mkdtemp(prefix="ds_todo_test_")
    proj = os.path.join(d, "projects")
    os.makedirs(proj)
    for name, text in files.items():
        with open(os.path.join(proj, name), "w", encoding="utf-8") as fh:
            fh.write(text)
    return d


class TestDsTodo(unittest.TestCase):

    # ① golden:未关闭 + 超期同时在
    def test_01_golden_mixed(self):
        root = _mkroot({"a-open.md": A_OPEN, "b-stale.md": B_STALE, "c-clean.md": C_CLEAN})
        self.assertEqual(ds_todo.render(root, 7, TODAY), GOLDEN_MIXED)

    # ② golden:全干净
    def test_02_golden_clean(self):
        root = _mkroot({"c-clean.md": C_CLEAN})
        self.assertEqual(ds_todo.render(root, 7, TODAY), GOLDEN_CLEAN)

    # ③ golden:只有未关闭,无超期
    def test_03_golden_open_only(self):
        root = _mkroot({"a-open.md": A_OPEN})
        self.assertEqual(ds_todo.render(root, 7, TODAY), GOLDEN_OPEN_ONLY)

    # ④ CLI 薄入口:输出与 render 一致,DS_TODAY 生效
    def test_04_cli_entry(self):
        root = _mkroot({"a-open.md": A_OPEN, "b-stale.md": B_STALE, "c-clean.md": C_CLEAN})
        env = dict(os.environ, DS_ROOT=root, DS_TODAY="2026-07-03")
        proc = subprocess.run([sys.executable, os.path.join(BIN, "ds-todo"), "7"],
                              capture_output=True, encoding="utf-8", env=env, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, GOLDEN_MIXED)

    # ⑤ list_todos 直调:ok + 文本与 render 一致(DS_TODAY 冻结)
    def test_05_list_todos_ok(self):
        root = _mkroot({"a-open.md": A_OPEN, "b-stale.md": B_STALE})
        os.environ["DS_TODAY"] = "2026-07-03"
        try:
            r = ds_tools.list_todos(7, ds_root=root)
        finally:
            del os.environ["DS_TODAY"]
        self.assertTrue(r.get("ok"))
        self.assertIn("▸ a-open", r["text"])
        self.assertIn("▸ b-stale — 13天未更新", r["text"])

    # ⑥ list_todos 错误路径:核心崩溃 → 显式 error,不得静默 ok:true
    def test_06_list_todos_error(self):
        orig = ds_todo.render
        ds_todo.render = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            r = ds_tools.list_todos(7, ds_root="/nonexistent")
        finally:
            ds_todo.render = orig
        self.assertNotIn("ok", r)
        self.assertIn("error", r)
        self.assertIn("boom", r["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
