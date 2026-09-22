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
HOST = os.path.join(ROOT, "bin", "ds_host.py")


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

    # 2026-08-16:接线口从 `child_env` 换成了 `service_envs`(key 只进网关那条腿,
    # 四审 BLOCK 的第一条)。**这两条守的东西没变** —— 锁端口和变量名仍然必须一路传
    # 下去,只是现在经由 service_envs 转交。⇒ 题面跟着实现搬,不是放宽。
    # 顺带比原来强了一点:`find()` 只认这一个入口,谁绕过 service_envs 自己拼 env
    # 就会让这两条空转 —— 那种情况由 test_ds_shell_core 的 J5 接线闸兜着。
    def test_w1_child_env_is_told_the_lock_port(self):
        """不传的话 ds-web 那侧的 DS_SHELL_LOCK_PORT 永远是空的 ⇒ 它只会回 manual,
        业主每次填完 key 都被要求手动重启程序 —— 而 k 组判据全绿(它们自己塞了 env)。"""
        for call in self.find("service_envs"):
            self.assertIn("lock_port", self.kwargs(call),
                          "service_envs 没拿到锁端口 ⇒ 填完 key 自动重启这条路整条空转")

    def test_w2_child_env_is_told_which_variable_to_set(self):
        """key_var 不传 + 有 key ⇒ child_env 直接抛(e9)。这条是提前把它挡在启动之前。"""
        for call in self.find("service_envs"):
            self.assertIn("key_var", self.kwargs(call),
                          "变量名没传 ⇒ 有 key 时外壳会在启动阶段抛 ValueError")

    # ---- 锁与后台在管家里接(track opendesign-electron-shell)-----------------------
    # 2026-09-22 判据迁移账:锁在 `bin/ds_host.py` 里建(Electron 起管家,ds_shell 只剩后台那一半)。
    # w3/w4 **跟着接线点搬家,守的东西不变**;行为版由 tests/test_ds_host.py h1/h11 钉,这里是第二道。
    # w6/w7(看门狗问 take_dead、只看一眼)退役:看门狗搬进管家,h7 用一个 poll_dead/dead_reports
    # 一被调就炸的假 Supervisor 从行为上钉同一件事 —— 比查函数名更强。

    @staticmethod
    def _host_calls():
        with open(HOST, encoding="utf-8") as fh:
            return _calls(ast.parse(fh.read(), filename=HOST))

    def test_w3_the_lock_carries_a_restart_callback(self):
        """只接 on_show 的话,ds-web 发来的 RESTART-BACKEND 会被当成"叫窗口到前台" ——
        业主看到窗口闪一下,key 却还是没生效。"""
        hits = [c for c in self._host_calls() if _name_of(c) == "make_lock"]
        self.assertTrue(hits, "ds_host.py 里没有 make_lock(...) 调用(接缝见 design.md)")
        for call in hits:
            self.assertIn("on_restart", self.kwargs(call),
                          "锁没接重启回调 ⇒ 重启帧到了也没人处理")

    def test_w4_start_backend_receives_the_lock_port(self):
        hits = [c for c in self._host_calls() if _name_of(c) == "start_backend"]
        self.assertTrue(hits, "ds_host.py 里没有调用 start_backend(...)")
        for call in hits:
            self.assertIn("lock_port", self.kwargs(call),
                          "start_backend 没拿到锁端口,build_env 只能传 None")

    def test_w5_the_gateway_is_started_from_the_plan_not_unconditionally(self):
        """缺 key 时网关不许起(它会死在缺变量上,而业主要的是那个引导页)。
        判断本身在 core.startup_plan(判据 d1/d2),这里只查外壳真的问过它。"""
        self.find("startup_plan")

    # ---- 每家厂商各存各的 key(track opendesign-per-vendor-keys)------------------

    def test_w10_every_gateway_start_prepares_the_extra_vendors_in_the_same_place_it_injects_keys(self):
        """额外厂商的配置条目与它们的 key 必须在**同一处**产生:`build_env` 里先
        `prepare_gateway`(写条目 + 读 key),再把结果交给 `service_envs`。
        拆开的话,「配置引用 ⊆ 网关手里的 key」就不再由结构保证 —— 实验 p2 证实,
        不成立时网关会**悄悄**用着旧厂商而界面说换了。

        放在 build_env 里而不是 start_backend 里是有讲究的:重启网关(业主刚存了第二家的 key)
        走的也是 build_env;只在启动时准备 ⇒ 存了 key 要等到下次开机才用得上。"""
        fn = next((n for n in ast.walk(self.tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "build_env"), None)
        self.assertIsNotNone(fn, "build_env 没了 —— 启动与重启共用的那一处 env 构造")
        names = [_name_of(c) for c in _calls(fn)]
        self.assertIn("prepare_gateway", names, "build_env 没调 prepare_gateway ⇒ 第二家永远进不了网关")
        self.assertIn("service_envs", names)
        # 第 1 轮 G4:只查「写了 extra_keys=」挡不住 `extra_keys={}` —— 要查**传进去的就是
        # prepare_gateway 的返回值**(同一个名字,在 build_env 里由那次调用赋值)。
        bound = {t.id for n in ast.walk(fn) if isinstance(n, ast.Assign)
                 and isinstance(n.value, ast.Call) and _name_of(n.value) == "prepare_gateway"
                 for t in n.targets if isinstance(t, ast.Name)}
        self.assertTrue(bound, "prepare_gateway 的返回值没接住 ⇒ 额外 key 无从交给网关")
        envs_calls = [c for c in _calls(fn) if _name_of(c) == "service_envs"]
        for call in envs_calls:
            self.assertIn("extra_keys", self.kwargs(call),
                          "prepare_gateway 给的额外 key 没交给 service_envs ⇒ 配置引用了、网关手里却没有")
            value = next(k.value for k in call.keywords if k.arg == "extra_keys")
            self.assertTrue(isinstance(value, ast.Name) and value.id in bound,
                            "交给 service_envs 的 extra_keys 不是 prepare_gateway 的返回值 "
                            f"(实际 {ast.unparse(value)})⇒ 配置写了条目、网关却拿不到 key")


if __name__ == "__main__":
    unittest.main(verbosity=2)
