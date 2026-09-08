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

    def test_w6_the_watchdog_asks_why_a_leg_died_not_just_that_it_did(self):
        """08-16 现场:外壳只打了 `[后台退出] ['网关']`,一个退出码都没有 ⇒
        拿到两份真机日志也答不了「它是被杀的还是自己崩的」。
        带退出码 + 日志尾巴的是 `take_dead()`(判据 c20/c21);
        这一条只查外壳**真的问了它** —— 光在 core 里做好没人用,等于没做。

        08-17:入口从 `dead_reports()` 换成 `take_dead()`(F5 只看一眼)。
        **题面跟着实现搬,不是放宽** —— 守的仍是"死了要说清为什么",
        而且由下面的 w7 补上了更强的一问:不许分两次看。"""
        self.find("take_dead")

    def test_w7_the_watchdog_looks_once_not_twice(self):
        """F5:先问「谁死了」再问「为什么」,两问之间名册会变(业主恰好存了 key
        触发重启)⇒ 弹窗照弹、原因是空的 —— c20 消灭掉的那种没线索的弹窗
        换个入口又长出来。行为面由 c21 咬着,这一条守的是**外壳这侧不许再问两遍**。"""
        fn = next((n for n in ast.walk(self.tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "run_watchdog"), None)
        self.assertIsNotNone(fn, "看门狗没了 —— 腿死了没人说话")
        names = {_name_of(c) for c in _calls(fn)}
        self.assertIn("take_dead", names, "看门狗没用单次快照")

    # ---- 更新交棒(track opendesign-in-app-update-install)--------------------

    def test_w8_the_lock_carries_an_update_callback(self):
        """只接 on_show/on_restart 的话,ds-web 发来的 UPDATE-HANDOFF 会被当成
        「把窗口叫到前台」—— 业主看到窗口闪一下,更新一动没动。

        而这一条比 w3 更要紧:那时 `.new` 已经装好、接力脚本已经在跑了。
        外壳不收摊 ⇒ 接力脚本等不到端口空 ⇒ 超时删掉 `.new` ⇒ 白下 43MB。
        """
        for call in self.find("InstanceLock"):
            self.assertIn("on_update", self.kwargs(call),
                          "锁没接交棒回调 ⇒ 交棒帧到了也没人处理,更新永远走不完")

    def test_w9_the_update_callback_actually_tears_the_backend_down(self):
        """接上了还不够 —— 得接到**真的会收摊**的那个东西上。

        h3 那条教训:静态闸看得见调用、看不见空转。所以这里再问一步:
        `on_update=` 指过去的那个名字,它的函数体里必须真的去收摊
        (`stop_backend` / `sup.shutdown`),不能是一个只写了日志的空壳。
        """
        target = None
        for call in self.find("InstanceLock"):
            for kw in call.keywords:
                if kw.arg == "on_update":
                    target = kw.value
        self.assertIsNotNone(target, "没接 on_update(w8 会先红)")
        name = getattr(target, "attr", None) or getattr(target, "id", None)
        self.assertIsNotNone(name, "on_update 接的不是一个具名函数,静态闸看不进去")
        fn = next((n for n in ast.walk(self.tree)
                   if isinstance(n, ast.FunctionDef) and n.name == name), None)
        self.assertIsNotNone(fn, "on_update 指向 %s,但 ds_shell.py 里没有这个函数" % name)
        called = {_name_of(c) for c in _calls(fn)}
        self.assertTrue({"stop_backend", "shutdown"} & called,
                        "%s() 里没有任何收摊动作 —— 交棒之后软件不会关,"
                        "接力脚本会一直等到超时" % name)
        for two_step in ("poll_dead", "dead_reports"):
            self.assertNotIn(two_step, names,
                             f"看门狗还在调 {two_step}() ⇒ 又变成分两眼看,"
                             "两眼之间名册一变就是「名字有、原因空」")


if __name__ == "__main__":
    unittest.main(verbosity=2)
