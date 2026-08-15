#!/usr/bin/env python3
"""接线闸:bin/ds_shell.py 那层在 Linux 上一条行为判据都跑不了(pywebview/pystray/
WebView2 全要 Windows 桌面会话),而本单最关键的一段恰好穿过它:

    业主填完 key → ds-web 通过锁端口回来 → 外壳重启网关

core 那侧每一环都有行为判据(e10 锁端口进 env / b11 动词分派 / c15~c17 只换一条腿),
**但"外壳到底有没有把这些接起来"没有任何东西在看**。已经吃过两次同款亏:
data-outside 那单三个 MCP 拿不到 DS_DATA_ROOT,47 处改动等于没改。

⚠️ 这是**静态闸,不是行为判据**:它只能证明"写了",证明不了"跑起来对"
(h3 看得见调用、看不见空转)。真的通不通,只有 Windows 真机答得了 ⇒ 真机清单里有一条。
"""
from __future__ import annotations

import ast
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, "bin", "ds_shell.py")


def _calls(tree: ast.AST):
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)]


def _name_of(call: ast.Call) -> str:
    f = call.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return ""


class ShellWiring(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(SHELL, encoding="utf-8") as fh:
            cls.tree = ast.parse(fh.read(), filename=SHELL)
        cls.calls = _calls(cls.tree)

    def find(self, name):
        hits = [c for c in self.calls if _name_of(c) == name]
        self.assertTrue(hits, f"ds_shell.py 里根本没有调用 {name}()")
        return hits

    def kwargs(self, call):
        return {k.arg for k in call.keywords if k.arg}

    def test_w1_child_env_is_told_the_lock_port(self):
        """不传的话 ds-web 那侧的 DS_SHELL_LOCK_PORT 永远是空的 ⇒ 它只会回 manual,
        业主每次填完 key 都被要求手动重启程序 —— 而 k 组判据全绿(它们自己塞了 env)。"""
        for call in self.find("child_env"):
            self.assertIn("lock_port", self.kwargs(call),
                          "child_env 没拿到锁端口 ⇒ 填完 key 自动重启这条路整条空转")

    def test_w2_child_env_is_told_which_variable_to_set(self):
        """key_var 不传 + 有 key ⇒ child_env 直接抛(e9)。这条是提前把它挡在启动之前。"""
        for call in self.find("child_env"):
            self.assertIn("key_var", self.kwargs(call),
                          "变量名没传 ⇒ 有 key 时外壳会在启动阶段抛 ValueError")

    def test_w3_the_lock_carries_a_restart_callback(self):
        """只接 on_show 的话,ds-web 发来的 RESTART-BACKEND 会被当成"叫窗口到前台" ——
        业主看到窗口闪一下,key 却还是没生效。"""
        for call in self.find("InstanceLock"):
            self.assertIn("on_restart", self.kwargs(call),
                          "锁没接重启回调 ⇒ 重启帧到了也没人处理")

    def test_w4_start_backend_receives_the_lock_port(self):
        for call in self.find("start_backend"):
            self.assertIn("lock_port", self.kwargs(call),
                          "start_backend 没拿到锁端口,build_env 只能传 None")

    def test_w5_the_gateway_is_started_from_the_plan_not_unconditionally(self):
        """缺 key 时网关不许起(它会死在缺变量上,而业主要的是那个引导页)。
        判断本身在 core.startup_plan(判据 d1/d2),这里只查外壳真的问过它。"""
        self.find("startup_plan")


if __name__ == "__main__":
    unittest.main(verbosity=2)
